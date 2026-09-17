#!/usr/bin/env python3
"""Compatibility import/CLI; implementation lives in reranking/jev.py."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'reranking'))
from jev import *  # noqa: F401,F403

if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(f'JEV reranking failed ({type(error).__name__}); no completed run written.', file=sys.stderr)
        sys.exit(1)
