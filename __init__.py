"""
NocEngine — Remote Charger Management Module
============================================
Independent module under A-core. Runs as a standalone process
alongside charging_controller, evAllocationEngine, and errorGenerationEngine.

Usage:
    python main.py

Communication:
    - Collects telemetry from local APIs (ports 8003, 8002, 8006)
    - Connects to NOC server via WebSocket (configured in config.json)
"""
from pathlib import Path

try:
    __version__ = (Path(__file__).with_name("VERSION")).read_text(encoding="utf-8").strip()
except Exception:
    __version__ = "0.0.0+unknown"
