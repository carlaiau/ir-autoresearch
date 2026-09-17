#!/usr/bin/env python3
"""Download the pinned monoBERT files; performs no inference or document upload."""
from pathlib import Path
import argparse
import time
from monobert import MODEL, REVISION, ROOT

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model-cache', type=Path, default=ROOT / '.cache/monobert-model')
    args = p.parse_args()
    from huggingface_hub import snapshot_download
    start = time.perf_counter()
    path = snapshot_download(MODEL, revision=REVISION, cache_dir=args.model_cache,
                             allow_patterns=['*.json', 'vocab.txt', 'pytorch_model.bin'])
    print(f'Model: {MODEL}@{REVISION}\nSnapshot: {path}\nDownload/setup seconds: {time.perf_counter()-start:.3f}')
