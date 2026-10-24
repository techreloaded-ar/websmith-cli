#!/usr/bin/env python3
"""Compatibility launcher; install websmith-cli in this Python environment first."""
from websmith.engine import main

raise SystemExit(main())
