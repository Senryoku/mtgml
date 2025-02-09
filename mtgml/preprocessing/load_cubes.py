import glob
import json
import locale
import logging
import random
import struct
import sys
from pathlib import Path

from jsonslicer import JsonSlicer
from tqdm.auto import tqdm

from mtgml.constants import MAX_CUBE_SIZE

locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')

with open('data/maps/int_to_card.json') as fp:
    int_to_card = json.load(fp)
name_to_int = {card['name_lower']: i for i, card in enumerate(int_to_card)}
original_to_new_path = Path('data/maps/original_to_new_index.json')
if original_to_new_path.exists():
    with original_to_new_path.open('r') as fp:
        original_to_new_index = json.load(fp)
else:
    original_to_new_index = tuple(range(len(int_to_card) + 1))
max_index = max(original_to_new_index)


def pad(arr, desired_length, value=0):
    if isinstance(arr, tuple):
        if len(arr) < desired_length:
            arr = list(arr)
        else:
            return arr[:desired_length]
    return arr + [value for _ in range(desired_length - len(arr))]


DESTS = [0, 0, 0, 0, 0, 0, 0, 0, 1, 2]


def load_all_cubes(cube_dirs):
    num_cubes = 0
    for cube_dir in cube_dirs.split(';'):
        for cubes_file in tqdm(glob.glob(f'{cube_dir}/*.json'), leave=False, dynamic_ncols=True,
                                unit='file', unit_scale=1):
            try:
                with open(cubes_file, 'rb') as fp:
                    cubes = JsonSlicer(fp, (None,))
                    for cube in tqdm(cubes, leave=False, dynamic_ncols=True, unit='cube', unit_scale=1,
                                      smoothing=0.001, initial=num_cubes):
                        if MAX_CUBE_SIZE >= len(cube['cards']) >= 120 and all(isinstance(x, int) for x in cube['cards']):
                            cards = tuple(original_to_new_index[x + 1] for x in cube['cards'])
                            if all(max_index >= x > 0 for x in cards):
                                num_cubes += 1
                                rand_val = random.randint(0, 9)
                                dest = DESTS[rand_val]
                                yield (dest, cards)
            except:
                logging.exception(f'Error in file {cubes_file}')
    print(f'Total cubes {num_cubes:n}')


def load_all_cubes2(cube_dirs):
    num_cubes = 0
    for cube_dir in cube_dirs.split(';'):
        for cubes_file in tqdm(glob.glob(f'{cube_dir}/*.json'), leave=False, dynamic_ncols=True,
                                unit='file', unit_scale=1):
            with open(cubes_file, 'rb') as fp:
                cubes = JsonSlicer(fp, (None, 'cards'))
                for cube in tqdm(cubes, leave=False, dynamic_ncols=True, unit='cube', unit_scale=1,
                                  smoothing=0.001, initial=num_cubes):
                    if MAX_CUBE_SIZE >= len(cube) >= 120 and all(x in name_to_int for x in cube):
                        cards = tuple(original_to_new_index[name_to_int[x] + 1] for x in cube)
                        if all(max_index >= x > 0 for x in cards):
                            num_cubes += 1
                            rand_val = random.randint(0, 9)
                            dest = DESTS[rand_val]
                            yield (dest, cards)
    print(f'Total cubes {num_cubes:n}')


PREFIX = struct.Struct(f'{MAX_CUBE_SIZE}H')


def write_cube(cards, output_file):
    if any(x > len(int_to_card) for x in cards):
        print('Cube had invalid idxs')
        return
    prefix = PREFIX.pack(*pad(cards, MAX_CUBE_SIZE))
    output_file.write(prefix)


def load_cubes(input_stream):
    return PREFIX.iter_unpack(input_stream)


if __name__ == '__main__':
    train_filename = Path('data/train_cubes.bin')
    validation_filename = Path('data/validation_cubes.bin')
    evaluation_filename = Path('data/evaluation_cubes.bin')
    with open(train_filename, 'wb') as train_file, open(validation_filename, 'wb') as validation_file, \
          open(evaluation_filename, 'wb') as evaluation_file:
        output_files = [train_file, validation_file, evaluation_file]
        for dest, cards in load_all_cubes(sys.argv[1]):
            write_cube(cards, output_files[dest])
        for dest, cards in load_all_cubes2(sys.argv[2]):
            write_cube(cards, output_files[dest])
