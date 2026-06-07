#!/usr/bin/env python3
"""Comprehensive Step 13 Admin Panel Test."""

import sys

print("Step 13: Admin & Auth Panel Integration Test")
print("=" * 50)

# Backend test
print("\n=== BACKEND VERIFICATION ===")
try:
    from main import app
    from api import admin
    
    print("[OK] FastAPI app initialized")
    print("[OK] Admin module imported")
    print(f"[OK] {len(admin.router.routes)} admin routes created")
    
    if len(admin.router.routes) >= 5:
        print("[OK] All admin endpoints registered")
        backend_ok = True
    else:
        print("[ERROR] Missing admin endpoints")
        backend_ok = False
except Exception as e:
    print(f"[ERROR] Backend error: {e}")
    backend_ok = False

# Frontend test
print("\n=== FRONTEND VERIFICATION ===")
import os
from pathlib import Path

ui_root = Path("../ui/src")
files = [
    "components/AdminPanel.jsx",
    "components/AdminPanel.css",
    "pages/Admin.jsx",
    "pages/Admin.css",
    "utils/adminAPI.js",
]

frontend_ok = True
for file in files:
    path = ui_root / file
    if path.exists():
        print(f"[OK] {file}")
    else:
        print(f"[ERROR] {file} MISSING")
        frontend_ok = False

# Integration test
print("\n=== INTEGRATION VERIFICATION ===")
app_file = "../ui/src/App.jsx"
if os.path.exists(app_file):
    with open(app_file) as f:
        content = f.read()
        if "import { Admin }" in content and 'path="/admin"' in content:
            print("[OK] App.jsx has Admin route")
            app_ok = True
        else:
            print("[ERROR] App.jsx missing Admin route")
            app_ok = False
else:
    app_ok = False

sidebar_file = "../ui/src/components/Sidebar.jsx"
if os.path.exists(sidebar_file):
    with open(sidebar_file) as f:
        content = f.read()
        if 'to="/admin"' in content:
            print("[OK] Sidebar.jsx has Admin link")
            sidebar_ok = True
        else:
            print("[ERROR] Sidebar.jsx missing Admin link")
            sidebar_ok = False
else:
    sidebar_ok = False

print("\n" + "=" * 50)
if backend_ok and frontend_ok and app_ok and sidebar_ok:
    print("[OK] ALL TESTS PASSED - Step 13 Complete")
    sys.exit(0)
else:
    print("[ERROR] SOME TESTS FAILED")
    sys.exit(1)
