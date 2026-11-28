#!/usr/bin/env python3
"""Run the shared read-only mailbox reader from a checkout or installed package."""
from pathlib import Path
import sys

source = Path(__file__).resolve().parents[3] / 'src'
if (source / 'websmith/inbox_check.py').is_file():
    sys.path.insert(0, str(source))

from websmith.inbox_check import main

if __name__ == '__main__':
    raise SystemExit(main())
