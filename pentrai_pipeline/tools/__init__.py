"""
The bridge from the pipeline to the existing PentrAI engine. The 150-tool catalog
already lives in `pentrai_server.py` (HTTP) / `pentrai_mcp.py` (MCP); the pipeline
does NOT reimplement any of it — it calls it through `pentrai_client`.
"""

from __future__ import annotations
