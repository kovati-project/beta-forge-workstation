#!/usr/bin/env python3
"""Test Step 12 Voice API module and integration."""

import sys

try:
    # Test backend
    from main import app
    from api import voice
    
    print('[OK] FastAPI app created successfully')
    print('[OK] Voice API module imports OK')
    print(f'[OK] Voice routes created: {len(voice.router.routes)}')
    
    # Verify voice endpoints
    expected_endpoints = [
        '/api/voice/status',
        '/api/voice/transcribe',
        '/api/voice/synthesize',
        '/api/voice/voices',
        '/api/voice/models',
    ]
    
    routes = [route.path for route in voice.router.routes]
    for endpoint in expected_endpoints:
        if any(endpoint in r for r in routes):
            print(f'[OK] Endpoint {endpoint} registered')
        else:
            print(f'[ERROR] Missing endpoint {endpoint}')
            sys.exit(1)
    
    print('[OK] Step 12 backend verified')
    sys.exit(0)
    
except Exception as e:
    print(f'[ERROR] {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
