import tensorflow as tf

from mtgml.config.hyper_config import HyperConfig
from mtgml.layers.bert import BERT
from mtgml.layers.configurable_layer import ConfigurableLayer
from mtgml.layers.extended_dropout import ExtendedDropout
from mtgml.layers.mlp import MLP
from mtgml.layers.wrapped import WDropout, WMultiHeadAttention
from mtgml.layers.zero_masked import ZeroMasked

SET_EMBEDDING_CHOICES = ("additive", "attentive")


class AdditiveSetEmbedding(ConfigurableLayer):
    @classmethod
    def get_properties(cls, hyper_config, input_shapes=None):
        decoding_dropout = hyper_config.get_float(
            "decoding_dropout_rate",
            min=0,
            max=0.99,
            step=0.01,
            default=0.1,
            help="The percent of values to dropout from the result of dense layers in the decoding step.",
        )
        return {
            "encoder": hyper_config.get_sublayer(
                "Encoder",
                sub_layer_type=MLP,
                seed_mod=13,
                help="The mapping from the item embeddings to the embeddings to add.",
            ),
            "decoder": hyper_config.get_sublayer(
                "Decoder",
                sub_layer_type=MLP,
                seed_mod=17,
                fixed={"Dropout": {"rate": decoding_dropout}},
                help="The mapping from the added item embeddings to the embeddings to return.",
            ),
            "zero_masked": ZeroMasked(HyperConfig(seed=hyper_config.seed * 47)),
            "item_dropout": hyper_config.get_sublayer(
                "ItemDropout",
                sub_layer_type=ExtendedDropout,
                seed_mod=53,
                fixed={"all_last_dim": True, "return_mask": False, "blank_last_dim": True},
                help="Drops out entire items from the set.",
            ),
            "decoder_dropout": hyper_config.get_sublayer(
                "DecodingDropout",
                sub_layer_type=WDropout,
                seed_mod=43,
                fixed={"rate": decoding_dropout, "blank_last_dim": True, "noise_shape": None},
                help="Drops out values from the decoding layers to improve generalizability.",
            ),
            "normalize_sum": hyper_config.get_bool(
                "normalize_sum", default=False, help="Average the sum of embeddings by the number of non-masked items."
            ),
        }

    def call(self, inputs, training=False, mask=None):
        encoded_items = self.encoder(inputs, training=training)
        dropped_inputs = self.zero_masked(self.item_dropout(encoded_items, training=training))
        summed_embeds = tf.math.reduce_sum(dropped_inputs, -2, name="summed_embeds")
        if self.normalize_sum:
            num_valid = tf.math.reduce_sum(
                tf.cast(tf.keras.layers.Masking().compute_mask(dropped_inputs), dtype=self.compute_dtype, name="mask"),
                axis=-1,
                keepdims=True,
                name="num_valid",
            )
            summed_embeds = tf.math.divide(summed_embeds, num_valid + 1e-09, name="normalized_embeds")
        summed_embeds = self.decoder_dropout(summed_embeds, training=training)
        return self.decoder(summed_embeds, training=training)
        hidden = self.dropout(self.hidden(summed_embeds), training=training)
        return self.output_layer(hidden)

    def compute_mask(self, inputs, mask=None):
        if mask is None:
            return None
        return tf.math.reduce_any(mask, axis=-1)


class AttentiveSetEmbedding(ConfigurableLayer):
    @classmethod
    def get_properties(cls, hyper_config, input_shapes=None):
        decoding_dropout = hyper_config.get_float(
            "decoding_dropout_rate",
            min=0,
            max=0.99,
            step=0.01,
            default=0.1,
            help="The percent of values to dropout from the result of dense layers in the decoding step.",
        )
        return {
            "encoder": hyper_config.get_sublayer(
                "Encoder",
                sub_layer_type=BERT,
                seed_mod=39,
                fixed={
                    "use_causal_mask": hyper_config.get_bool(
                        "use_causal_mask",
                        default=False,
                        help="Ensure items only attend to items that came before them.",
                    ),
                },
                help="The layers to model interactions between items.",
            ),
            "decoder": hyper_config.get_sublayer(
                "Decoder",
                sub_layer_type=MLP,
                seed_mod=17,
                fixed={"Dropout": {"rate": decoding_dropout}},
                help="The mapping from the added item embeddings to the embeddings to return.",
            ),
            "zero_masked": ZeroMasked(HyperConfig(seed=hyper_config.seed * 47)),
            "item_dropout": hyper_config.get_sublayer(
                "ItemDropout",
                sub_layer_type=ExtendedDropout,
                seed_mod=53,
                fixed={"all_last_dim": True, "return_mask": True, "blank_last_dim": False, "noise_shape": None},
                help="Drops out entire items from the set.",
            ),
            "pooling_attention": hyper_config.get_sublayer(
                "PoolingAttention",
                sub_layer_type=WMultiHeadAttention,
                seed_mod=37,
                help="The attention layer that combines the set elements.",
            ),
            "supports_masking": True,
        }

    def build(self, input_shapes):
        super(AttentiveSetEmbedding, self).build(input_shapes)
        self.seed_vector = self.add_weight("seed_vector", shape=(1, input_shapes[-1]), trainable=True)

    def call(self, inputs, training=False, mask=None):
        dropped, dropout_mask = self.item_dropout(inputs, training=training, mask=mask)
        dropout_mask = tf.cast(dropout_mask, tf.bool)
        dropout_mask = tf.math.reduce_any(dropout_mask, axis=-1)
        encoded_item_set = self.encoder(dropped, mask=dropout_mask, training=training)
        encoded_item_set._keras_mask = None
        shape = tf.concat([tf.shape(inputs)[:-2], tf.shape(self.seed_vector)[-2:]], axis=0)
        x = self.seed_vector + tf.zeros(shape, dtype=inputs.dtype)
        x._keras_mask = None
        encoded_items = tf.squeeze(
            self.pooling_attention(
                x, encoded_item_set, attention_mask=tf.expand_dims(dropout_mask, -2), training=training
            ),
            -2,
        )
        return self.decoder(encoded_items, training=training)
