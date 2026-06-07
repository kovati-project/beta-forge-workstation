#!/usr/bin/env python3
"""Test setup API module."""

try:
    from api import setup
    print('[OK] setup API module imports OK')
    print(f'[OK] {len(setup.router.routes)} setup routes created')
    print('[OK] Setup module test passed')
except Exception as e:
    print(f'[ERROR] {e}')
    import traceback
    traceback.print_exc()
