#!/usr/bin/env python3
"""Comprehensive Step 12 Voice I/O Test Suite."""

import sys

def test_backend():
    """Test backend voice API."""
    print("\n=== BACKEND VERIFICATION ===")
    
    try:
        from main import app
        from api import voice
        
        print("✓ FastAPI app initialized")
        print("✓ Voice module imported")
        
        # Check routes
        routes = [str(route) for route in voice.router.routes]
        endpoints = [
            'POST /api/voice/transcribe',
            'POST /api/voice/synthesize',
            'GET /api/voice/status',
            'GET /api/voice/voices',
            'GET /api/voice/models',
        ]
        
        for endpoint in endpoints:
            if any(endpoint in r for r in routes):
                print(f"✓ {endpoint}")
            else:
                print(f"✗ {endpoint} MISSING")
                return False
        
        return True
    except Exception as e:
        print(f"✗ Backend error: {e}")
        return False

def test_frontend():
    """Test frontend components."""
    print("\n=== FRONTEND VERIFICATION ===")
    
    import os
    from pathlib import Path
    
    ui_root = Path("../ui/src")
    files = [
        "components/VoiceChat.jsx",
        "components/VoiceChat.css",
        "pages/Voice.jsx",
        "pages/Voice.css",
        "utils/voiceAPI.js",
    ]
    
    all_exist = True
    for file in files:
        path = ui_root / file
        if path.exists():
            print(f"✓ {file}")
        else:
            print(f"✗ {file} MISSING")
            all_exist = False
    
    return all_exist

def test_integration():
    """Test integration."""
    print("\n=== INTEGRATION VERIFICATION ===")
    
    import os
    
    # Check App.jsx
    app_file = "../ui/src/App.jsx"
    if os.path.exists(app_file):
        with open(app_file) as f:
            content = f.read()
            if "import { Voice }" in content and 'path="/voice"' in content:
                print("✓ App.jsx has Voice route")
            else:
                print("✗ App.jsx missing Voice route")
                return False
    
    # Check Sidebar.jsx
    sidebar_file = "../ui/src/components/Sidebar.jsx"
    if os.path.exists(sidebar_file):
        with open(sidebar_file) as f:
            content = f.read()
            if 'to="/voice"' in content:
                print("✓ Sidebar.jsx has Voice link")
            else:
                print("✗ Sidebar.jsx missing Voice link")
                return False
    
    return True

if __name__ == "__main__":
    print("Step 12: Voice I/O Integration Test")
    print("=" * 50)
    
    backend_ok = test_backend()
    frontend_ok = test_frontend()
    integration_ok = test_integration()
    
    print("\n" + "=" * 50)
    if backend_ok and frontend_ok and integration_ok:
        print("✓ ALL TESTS PASSED - Step 12 Complete")
        sys.exit(0)
    else:
        print("✗ SOME TESTS FAILED")
        sys.exit(1)
