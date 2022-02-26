import logging

import numpy as np
import numpy.ma as ma

from mtgml.constants import MAX_BASICS, MAX_CARDS_IN_PACK, MAX_PICKED, MAX_SEEN_PACKS
from mtgml.utils.grid import interpolate

def get_draft_scores(drafter_state, model, card_to_int):
    cards_in_pack = np.zeros((1, MAX_CARDS_IN_PACK), dtype=np.int32)
    original_cards_idx = []
    idx = 0
    for i, card_id in enumerate(drafter_state['cardsInPack']):
        if card_id in card_to_int and idx < MAX_CARDS_IN_PACK:
            cards_in_pack[0][idx] = card_to_int[card_id] + 1
            original_cards_idx.append(i)
            idx += 1
    basics = np.zeros((1, MAX_BASICS), dtype=np.int32)
    idx = 0
    for card_id in drafter_state['basics']:
        if card_id in card_to_int and idx < MAX_BASICS:
            basics[0][idx] = card_to_int[card_id] + 1
            idx += 1
    picked = np.zeros((1, MAX_PICKED), dtype=np.int32)
    idx = 0
    for card_id in drafter_state['picked']:
        if card_id in card_to_int and idx < MAX_PICKED:
            picked[0][idx] = card_to_int[card_id] + 1
            idx += 1
    seen_packs = np.zeros((1, MAX_SEEN_PACKS, MAX_CARDS_IN_PACK), dtype=np.int32)
    seen_coords = np.zeros((1, MAX_SEEN_PACKS, 4, 2), dtype=np.int32)
    seen_weights = np.zeros((1, MAX_SEEN_PACKS, 4), dtype=np.float32)
    idx_pack = 0
    for pack in drafter_state['seen']:
        if idx_pack >= MAX_SEEN_PACKS: break
        idx = 0
        seen_coords[0][idx_pack], seen_weights[0][idx_pack] = interpolate(pack['pickNum'], pack['numPicks'],
                                                                          pack['packNum'], drafter_state['numPacks'])
        for card_id in pack['pack']:
            if card_id in card_to_int and idx < MAX_CARDS_IN_PACK:
                seen_packs[0][idx_pack][idx] = card_to_int[card_id] + 1
                idx += 1
        idx_pack += 1
    coords, weights = interpolate(drafter_state['pickNum'], drafter_state['numPicks'], drafter_state['packNum'],
                                  drafter_state['numPacks'])
    oracle_scores, oracle_weights = model.draftbots((cards_in_pack, basics, picked, seen_packs, seen_coords, seen_weights,
                                                            [coords], [weights], model.embed_cards.embeddings), training=False)
    oracle_scores = oracle_scores.numpy()[0]
    oracle_scores = ma.masked_array(oracle_scores, mask=np.broadcast_to(np.expand_dims(cards_in_pack[0] == 0, -1), oracle_scores.shape))
    oracle_scores_min = np.amin(oracle_scores, axis=0)
    oracle_scores = oracle_scores - oracle_scores_min
    oracle_max_scores = np.max(oracle_scores, axis=0) / 10
    oracle_max_scores = np.where(oracle_max_scores > 0, oracle_max_scores, np.ones_like(oracle_max_scores))
    oracle_scores = oracle_scores / oracle_max_scores
    oracle_weights = oracle_weights.numpy()[0] * oracle_max_scores
    oracle_weights = oracle_weights / oracle_weights.sum()
    scores = (oracle_weights * oracle_scores).sum(axis=1)
    oracles = [[dict(metadata) | { 'weight': float(weight), 'score': float(score) }
                for metadata, weight, score
                in zip(model.draftbots.sublayer_metadata, oracle_weights, card_scores)]
               for card_scores in oracle_scores]
    returned_scores = [0.0 for _ in drafter_state["cardsInPack"]]
    returned_oracles = [[x | {'weight': 0, 'score': 0} for x in model.draftbots.sublayer_metadata] for _ in drafter_state['cardsInPack']]
    for i, score, oracle in zip(original_cards_idx, scores, oracles):
        returned_scores[i] = float(score)
        returned_oracles[i] = oracle
    return {
        "scores": returned_scores,
        "oracles": returned_oracles,
        "success": True,
    }
