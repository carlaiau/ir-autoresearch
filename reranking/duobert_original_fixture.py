"""Make tiny synthetic input for the unchanged upstream duoBERT evaluator.

Run inside TensorFlow 1.15. This tests execution, not retrieval effectiveness.
No downloaded checkpoint or collection text is needed.
"""
import json
import os
import sys

import tensorflow as tf


def main():
    destination = sys.argv[1]
    os.makedirs(destination, exist_ok=True)
    config = dict(
        vocab_size=128, hidden_size=32, num_hidden_layers=2,
        num_attention_heads=4, intermediate_size=64, hidden_act="gelu",
        hidden_dropout_prob=0.1, attention_probs_dropout_prob=0.1,
        max_position_embeddings=512, type_vocab_size=3, initializer_range=0.02,
    )
    if "--large" in sys.argv[2:]:
        config.update(vocab_size=30522, hidden_size=1024, num_hidden_layers=24,
                      num_attention_heads=16, intermediate_size=4096)
    with open(os.path.join(destination, "bert_config.json"), "w") as output:
        json.dump(config, output, indent=2)
    # Two ordered comparisons: (A, B), (B, A). Token IDs are synthetic.
    with tf.python_io.TFRecordWriter(os.path.join(destination, "dataset_dev.tf")) as output:
        for first, second, label in [(11, 21, 1), (21, 11, 0)]:
            values = {
                "input_ids": [101, 31, 102, first, 102, second, 102],
                "segment_ids": [0, 0, 0, 1, 1, 2, 2],
                "label": [label],
            }
            features = {
                key: tf.train.Feature(int64_list=tf.train.Int64List(value=value))
                for key, value in values.items()
            }
            output.write(tf.train.Example(features=tf.train.Features(feature=features)).SerializeToString())
    with open(os.path.join(destination, "query_doc_ids_dev.txt"), "w") as output:
        output.write("synthetic-query\tA\tB\nsynthetic-query\tB\tA\n")


if __name__ == "__main__":
    main()
