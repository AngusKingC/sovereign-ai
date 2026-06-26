"""System monitor for resource tracking."""

from typing import Any

import psutil


class SystemMonitor:
    """Monitor system resources."""

    def __init__(self):
        """Initialize system monitor."""
        self.start_time = psutil.boot_time()

    def get_stats(self) -> dict[str, Any]:
        """Return system stats for UI consumption."""
        # TODO: implement when system monitor is complete
        return {
            "cpu_percent": 0.0,
            "memory_percent": 0.0,
            "uptime_seconds": 0,
            "active_workers": 0,
        }
