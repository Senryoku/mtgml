import tensorflow as tf

from mtgml.layers.extended_dropout import ExtendedDropout
from mtgml.layers.mlp import MLP
from mtgml.layers.wrapped import MultiHeadAttention
from mtgml.layers.zero_masked import ZeroMasked


class AdditiveSetEmbedding(tf.keras.layers.Layer):
    @classmethod
    def get_properties(cls, hyper_config, input_shapes=None):
        decoding_dropout = hyper_config.get_float('decoding_dropout', min=0, max=0.99, step=0.01,
                                                  help='The percent of values to dropout from the result of dense layers in the decoding step.')
        return {
            'encoder': hyper_config.get_sublayer('Encoder', layer_type=MLP, seed_mod=13,
                                                 help='The mapping from the item embeddings to the embeddings to add.'),
            'decoder': hyper_config.get_sublayer('Decoder', layer_type=MLP, seed_mod=17,
                                                 fixed={"dropout": decoding_dropout},
                                                 help='The mapping from the added item embeddings to the embeddings to return.'),
            'zero_masked': hyper_config.get_sublayer('ZeroMasked', layer_type=ZeroMasked, seed_mod=71,
                                                     help='Zero out the masked values for adding.'),
            'item_dropout': hyper_config.get_sublayer('ItemDropout' layer_type=ExtendedDropout,
                                                      seed_mod=53, fixed={'all_last_dim': True},
                                                      help='Drops out entire items from the set.'),
            'decoding_dropout': hyper_config.get_sublayer('DecodingDropout', layer_type=Dropout,
                                                          seed_mod=43, fixed={'rate': decoding_dropout
                                                                              'blank_last_dim': True},
                                                      help='Drops out values from the decoding layers to improve generalizability.'),
            'normalize_sum': hyper_config.get_bool('normalize_sum', default=False,
                                                   help='Average the sum of embeddings by the number of non-masked items.'),
        }

    def call(self, inputs, training=False, mask=None):
        encoded_items = self.encoder(inputs, training=training)
        dropped_inputs = self.zero_masked(self.item_dropout(encoded_items, training=training))
        summed_embeds = tf.math.reduce_sum(item_embeds, -2, name='summed_embeds')
        if self.normalize_sum:
            num_valid = tf.math.reduce_sum(tf.cast(tf.keras.layers.Masking().compute_mask(dropped_inputs),
                                                   dtype=self.compute_dtype, name='mask'),
                                           axis=-1, keepdims=True, name='num_valid')
            summed_embeds = tf.math.divide(summed_embeds, num_valid + 1e-09, name='normalized_embeds')
        summed_embeds = self.decoding_dropout(self.activation_layer(summed_embeds), training=training)
        return self.decoder(summed_embeds, training=training)
        hidden = self.dropout(self.hidden(summed_embeds), training=training)
        return self.output_layer(hidden)

    def compute_mask(self, inputs, mask=None):
        if not mask:
            return None
        return tf.math.reduce_any(mask, axis=-1)


class AttentiveSetEmbedding(tf.keras.layers.Layer):
    @classmethod
    def get_properties(cls, hyper_config, input_shapes=None):
        decoding_dropout = hyper_config.get_float('decoding_dropout', min=0, max=0.99, step=0.01,
                                                  help='The percent of values to dropout from the result of dense layers in the decoding step.')
        return {
            'encoder': hyper_config.get_sublayer('Encoder', layer_type=MultiHeadAttention, seed_mod=37,
                                                 help='The mapping from the item embeddings to the embeddings to add.'),
            'decoder': hyper_config.get_sublayer('Decoder', layer_type=MLP, seed_mod=17,
                                                 fixed={"dropout": decoding_dropout},
                                                 help='The mapping from the added item embeddings to the embeddings to return.'),
            'zero_masked': hyper_config.get_sublayer('ZeroMasked', layer_type=ZeroMasked, seed_mod=71,
                                                     help='Zero out the masked values for adding.'),
            'item_dropout': hyper_config.get_sublayer('ItemDropout' layer_type=ExtendedDropout,
                                                      seed_mod=53, fixed={'all_last_dim': True},
                                                      help='Drops out entire items from the set.'),
            'decoding_dropout': hyper_config.get_sublayer('DecodingDropout', layer_type=Dropout,
                                                          seed_mod=43, fixed={'rate': decoding_dropout
                                                                              'blank_last_dim': True},
                                                      help='Drops out values from the decoding layers to improve generalizability.'),
            'normalize_sum': hyper_config.get_bool('normalize_sum', default=False,
                                                   help='Average the sum of embeddings by the number of non-masked items.'),
        }

    def call(self, inputs, training=False, mask=None):
        dropped, dropout_mask = self.item_dropout(inputs, training=training)
        dropout_mask = tf.squeeze(dropout_mask, -1)
        product_mask = tf.logical_or(tf.expand_dims(dropout_mask, -1), tf.expand_dims(dropout_mask, -2), name='product_mask')
        encoded_items, attention_scores = self.encoder(dropped, dropped, training=training,
                                                       attention_mask=product_mask,
                                                       return_attention_scores=True)
        dropped_inputs = self.zero_masked(encoded_items, mask=dropout_mask)
        summed_embeds = tf.math.reduce_sum(item_embeds, -2, name='summed_embeds')
        if self.normalize_sum:
            num_valid = tf.math.reduce_sum(tf.cast(dropout_mask, dtype=self.compute_dtype, name='mask'),
                                           axis=-1, keepdims=True, name='num_valid')
            summed_embeds = tf.math.divide(summed_embeds, num_valid + 1e-09, name='normalized_embeds')
        summed_embeds = self.decoding_dropout(self.activation_layer(summed_embeds), training=training)
        return self.decoder(summed_embeds, training=training)
        hidden = self.dropout(self.hidden(summed_embeds), training=training)
        return self.output_layer(hidden)

    def compute_mask(self, inputs, mask=None):
        if not mask:
            return None
        return tf.math.reduce_any(mask, axis=-1)
