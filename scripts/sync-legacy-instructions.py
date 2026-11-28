#!/usr/bin/env python3
"""Generate old download paths from skills; --check never writes files."""
import argparse
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
from websmith.instruction_bundle import legacy_projections


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    stale = []
    for name, content in legacy_projections(root).items():
        target = root / 'src/websmith/resources' / name
        if not target.is_file() or target.read_bytes() != content.encode('utf-8'):
            stale.append(str(target.relative_to(root)))
            if not args.check:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content.encode('utf-8'))
    if stale:
        print(('Da rigenerare: ' if args.check else 'Rigenerati: ') + ', '.join(stale))
    return 1 if args.check and stale else 0


if __name__ == '__main__':
    raise SystemExit(main())
