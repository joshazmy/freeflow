"""Platform selection: pick the OS-specific adapter."""
from __future__ import annotations

import sys

from freeflow.platform.base import Platform


def get_platform() -> Platform:
    if sys.platform == "linux":
        from freeflow.platform.linux import LinuxPlatform

        return LinuxPlatform()
    if sys.platform == "darwin":
        raise NotImplementedError("macOS adapter is planned — see docs/MACOS.md")
    raise NotImplementedError(f"Unsupported platform: {sys.platform}")
