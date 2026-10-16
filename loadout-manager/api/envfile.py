"""Read and update docker/.env without disturbing anything else in it."""

import re
from pathlib import Path
from typing import Dict


def read_env(path: Path) -> Dict[str, str]:
    """KEY=value pairs from a .env file; {} when it does not exist."""
    if not path.exists():
        return {}
    env = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            env[key.strip()] = value
    return env


def set_env_values(path: Path, values: Dict[str, str]) -> None:
    """Replace or append ``values`` in one pass; every other line (comments,
    ordering, unrelated keys) is kept byte-for-byte.

    Writes in place rather than via temp-file + rename: in the container
    docker/.env is a single-file bind mount, and a rename would replace the
    inode and detach it from the host file.
    """
    content = path.read_text() if path.exists() else ""
    for key, value in values.items():
        pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
        line = f"{key}={value}"
        if pattern.search(content):
            content = pattern.sub(lambda _m: line, content, count=1)
        else:
            content = (content.rstrip("\n") + "\n" if content else "") + line + "\n"
    with open(path, "r+" if path.exists() else "w") as f:
        f.seek(0)
        f.write(content)
        f.truncate()
