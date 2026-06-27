"""System monitor for resource tracking."""

import time
from typing import Any

import psutil


class SystemMonitor:
    """Monitor system resources."""

    def __init__(self):
        """Initialize system monitor."""
        self.start_time = time.time()

    def get_stats(self) -> dict[str, Any]:
        """Get real system stats. Was returning hardcoded zeros — now uses psutil."""
        try:
            return {
                "cpu_percent": psutil.cpu_percent(interval=None),
                "memory_percent": psutil.virtual_memory().percent,
                "uptime_seconds": int(time.time() - self.start_time),
                "active_workers": 0,  # TODO: wire to orchestrator worker count
            }
        except Exception:
            return {
                "cpu_percent": 0.0,
                "memory_percent": 0.0,
                "uptime_seconds": 0,
                "active_workers": 0,
            }
