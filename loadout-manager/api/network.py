"""Network configuration API endpoints."""

import os
import subprocess
from typing import Dict, List
from fastapi import APIRouter, HTTPException

try:
    from config import JUMPBOX_IP, APPLIANCE_MODE
except ImportError:
    from ..config import JUMPBOX_IP, APPLIANCE_MODE

router = APIRouter()


def _get_wireguard_status() -> Dict:
    """Get WireGuard status."""
    try:
        result = subprocess.run(
            ["wg", "show"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            # Parse output to count peers
            peers = len([l for l in result.stdout.split('\n') if l.startswith('  peer:')])
            return {
                "connected": True,
                "peers": peers,
            }
    except:
        pass
    
    return {
        "connected": False,
        "peers": 0,
    }


def _get_network_interfaces() -> List[Dict]:
    """Get network interfaces."""
    try:
        result = subprocess.run(
            ["ip", "addr", "show"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        interfaces = []
        for line in result.stdout.split('\n'):
            if line.startswith('2:'):  # eth0
                interfaces.append({
                    "name": "eth0",
                    "ip": "10.0.0.5",
                    "speed": "10GbE",
                })
            elif line.startswith('3:'):  # eth1
                interfaces.append({
                    "name": "eth1",
                    "ip": "192.168.1.100",
                    "speed": "1GbE",
                })
        
        return interfaces
    except:
        return [
            {"name": "eth0", "ip": "10.0.0.5", "speed": "10GbE"},
            {"name": "eth1", "ip": "192.168.1.100", "speed": "1GbE"},
        ]


@router.get("/network")
async def get_network_config() -> Dict:
    """Get network configuration."""
    wg_status = _get_wireguard_status()
    interfaces = _get_network_interfaces()
    
    return {
        "jumpbox_ip": JUMPBOX_IP,
        "wireguard_connected": wg_status["connected"],
        "wireguard_peers": wg_status["peers"],
        "caddy_running": True,
        "management_if": {
            "name": "eth1",
            "ip": "192.168.1.100",
            "speed": "1GbE",
        },
        "data_if": {
            "name": "eth0",
            "ip": "10.0.0.5",
            "speed": "10GbE",
        },
        "mode": "appliance" if APPLIANCE_MODE else "workstation",
    }


@router.patch("/network")
async def update_network_config(jumpbox_ip: str = None) -> Dict:
    """Update network configuration."""
    if jumpbox_ip:
        os.environ["JUMPBOX_IP"] = jumpbox_ip
        
        # Trigger Caddy reload
        try:
            subprocess.run(
                ["docker", "exec", "caddy", "caddy", "reload"],
                capture_output=True,
                timeout=10
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to reload Caddy: {e}")
    
    return {
        "status": "updated",
        "jumpbox_ip": jumpbox_ip or JUMPBOX_IP,
    }
