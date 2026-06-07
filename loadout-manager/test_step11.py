#!/usr/bin/env python3
"""Verify FastAPI app and all API modules compile."""

import sys

try:
    from main import app
    print('[OK] FastAPI app created successfully')
    
    from api import setup
    print('[OK] Setup API module imports OK')
    print(f'[OK] Setup routes created: {len(setup.router.routes)}')
    
    print('[OK] Step 11 backend verified')
    sys.exit(0)
except Exception as e:
    print(f'[ERROR] {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
