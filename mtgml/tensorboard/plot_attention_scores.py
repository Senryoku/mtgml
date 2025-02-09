import io
import itertools

import matplotlib.pyplot as plt
import numpy as np
import tensorflow as tf

from mtgml.constants import is_debug

WIDTH = 10
DPI = 100
CHANNELS = 3


def plot_to_image(figure):
  """Converts the matplotlib plot specified by 'figure' to a PNG image and
  returns it. The supplied figure is closed and inaccessible after this call."""
  # Save the plot to a PNG in memory.
  buf = io.BytesIO()
  plt.savefig(buf, format='png', dpi=DPI)
  # Closing the figure prevents it from being displayed directly inside
  # the notebook.
  plt.close(figure)
  buf.seek(0)
  # Convert PNG buffer to TF image
  image = tf.io.decode_png(buf.getvalue(), channels=CHANNELS)
  return image


def plot_attention_head_scores(scores, mask, name=''):
    scores = scores.reshape((-1, *scores.shape[-2:]))
    count = np.sum(mask[0])
    scores = scores[0, :count, :count]
    figure = plt.figure(figsize=(WIDTH, WIDTH))
    plt.imshow(scores, interpolation='nearest', cmap=plt.cm.Blues)
    plt.title(name)
    plt.colorbar()
    tick_marks = np.arange(scores.shape[0])
    plt.xticks(tick_marks, [str(x) for x in tick_marks], rotation=45)
    plt.yticks(tick_marks, [str(x) for x in tick_marks])
    # Compute the labels from the normalized confusion matrix.
    labels = np.around(scores, decimals=2)
    # Use white text if squares are dark; otherwise black.
    threshold = scores.max() / 2.
    for i, j in itertools.product(range(scores.shape[0]), range(scores.shape[1])):
        color = "white" if scores[i, j] > threshold else "black"
        plt.text(j, i, labels[i, j], horizontalalignment="center", color=color, fontsize=6)
    plt.tight_layout()
    image = plot_to_image(figure)
    if is_debug():
        image = tf.ensure_shape(image, (WIDTH * DPI, WIDTH * DPI, CHANNELS))
    return image



def plot_attention_scores(scores, mask, multihead=False, name='Attention'):
    if not isinstance(scores, np.ndarray):
        scores = scores.numpy()
    images = []
    for i, subscores in enumerate(np.split(scores, scores.shape[-3], axis=-3)):
        images.append(plot_attention_head_scores(subscores, mask, name=f'{name} Head {i}'))
    return images
