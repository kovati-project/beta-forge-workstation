#!/usr/bin/env python3
"""
Step 14 Verification: Operations & Maintenance Panel
Tests backend API and frontend components compilation
"""

import sys
import subprocess
from pathlib import Path

def test_backend():
    """Test backend operations API module"""
    print("\n=== BACKEND: Operations API Module ===")
    
    try:
        # Add loadout-manager to path
        import sys
        sys.path.insert(0, str(Path(__file__).parent / "loadout-manager"))
        
        from api import operations
        print("✓ operations.py imports correctly")
        print(f"✓ {len(operations.router.routes)} routes created")
        
        endpoints = [
            "/api/operations/health",
            "/api/operations/services",
            "/api/operations/backup",
            "/api/operations/restart-service",
            "/api/operations/system-update",
            "/api/operations/diagnostics",
            "/api/operations/runbook",
            "/api/operations/logs",
        ]
        
        routes = {route.path for route in operations.router.routes}
        missing = [ep for ep in endpoints if ep not in routes]
        
        if missing:
            print(f"✗ Missing endpoints: {missing}")
            return False
        
        print(f"✓ All {len(endpoints)} expected endpoints found")
        return True
        
    except Exception as e:
        print(f"✗ Backend error: {e}")
        return False

def test_router_registration():
    """Test operations router is registered in __init__.py"""
    print("\n=== BACKEND: Router Registration ===")
    
    try:
        # Add loadout-manager to path
        import sys
        sys.path.insert(0, str(Path(__file__).parent / "loadout-manager"))
        
        from api import create_router
        router = create_router()
        
        # Count routes by path prefix
        ops_routes = [r for r in router.routes if "/api/operations" in r.path]
        
        if not ops_routes:
            print("✗ Operations routes not registered in main router")
            return False
        
        print(f"✓ {len(ops_routes)} operations routes registered in main router")
        return True
        
    except Exception as e:
        print(f"✗ Router registration error: {e}")
        return False

def test_frontend_components():
    """Test frontend components exist and have exports"""
    print("\n=== FRONTEND: Component Files ===")
    
    ui_path = Path(__file__).parent / "ui"
    required_files = [
        "src/components/OperationsPanel.jsx",
        "src/components/OperationsPanel.css",
        "src/pages/Operations.jsx",
        "src/pages/Operations.css",
        "src/utils/operationsAPI.js",
    ]
    
    missing = []
    for file in required_files:
        full_path = ui_path / file
        if not full_path.exists():
            missing.append(file)
            print(f"✗ {file} not found")
        else:
            print(f"✓ {file} exists")
    
    return len(missing) == 0

def test_routing():
    """Test App.jsx has Operations route"""
    print("\n=== FRONTEND: Routing ===")
    
    app_file = Path(__file__).parent / "ui" / "src" / "App.jsx"
    content = app_file.read_text()
    
    checks = [
        ("Operations import", "import { Operations } from './pages/Operations'"),
        ("Operations route", '<Route path="/operations" element={<Operations />}'),
    ]
    
    all_ok = True
    for name, pattern in checks:
        if pattern in content:
            print(f"✓ {name} configured")
        else:
            print(f"✗ {name} missing")
            all_ok = False
    
    return all_ok

def test_navigation():
    """Test Sidebar has Operations link"""
    print("\n=== FRONTEND: Navigation ===")
    
    sidebar_file = Path(__file__).parent / "ui" / "src" / "components" / "Sidebar.jsx"
    content = sidebar_file.read_text()
    
    if 'to="/operations"' in content and ">Operations<" in content:
        print("✓ Operations navigation link configured")
        return True
    else:
        print("✗ Operations navigation link missing")
        return False

def test_build():
    """Test npm build succeeds"""
    print("\n=== FRONTEND: Build ===")
    
    try:
        ui_path = Path(__file__).parent / "ui"
        # Use PowerShell to execute npm if on Windows
        result = subprocess.run(
            ["powershell", "-Command", "npm run build"],
            cwd=ui_path,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            # Extract module count from output
            output = result.stdout + result.stderr
            if "modules transformed" in output:
                modules = output.split("modules transformed")[0].strip().split()[-1]
                print(f"✓ Build successful ({modules} modules)")
            else:
                print("✓ Build successful")
            return True
        else:
            print(f"✗ Build failed:\n{result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("✗ Build timed out")
        return False
    except Exception as e:
        print(f"✗ Build error: {e}")
        return False

def main():
    """Run all verification tests"""
    print("=" * 50)
    print("STEP 14: Operations & Maintenance Panel")
    print("=" * 50)
    
    results = {
        "Backend Module": test_backend(),
        "Router Registration": test_router_registration(),
        "Frontend Components": test_frontend_components(),
        "Routing": test_routing(),
        "Navigation": test_navigation(),
        "Build": test_build(),
    }
    
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    
    for test_name, passed in results.items():
        status = "[OK]" if passed else "[ERROR]"
        print(f"{status} {test_name}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n✓ All tests passed! Step 14 is complete.")
        sys.exit(0)
    else:
        print("\n✗ Some tests failed. Review above for details.")
        sys.exit(1)

if __name__ == "__main__":
    main()
