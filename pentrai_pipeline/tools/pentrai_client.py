"""
HTTP client for the existing PentrAI tool server (`pentrai_server.py`, default
127.0.0.1:8888). This is the pipeline's single door to the 150-tool catalog:
recon and the operator agent call tools through here rather than shelling out
themselves, so tool logging, timeouts, and (critically) target scoping all live in
one place.

Scoping is a safety invariant: every call is meant for the sandboxed target. The
client is the natural chokepoint to assert that a tool's target is the isolated
instance and nothing else (see docs/THREAT_MODEL.md).
"""

from __future__ import annotations

from typing import Any

from ..config import Settings


class PentrAIClient:
    def __init__(self, settings: Settings):
        self.base_url = settings.pentrai_server_url.rstrip("/")
        self.settings = settings

    def call(self, tool: str, **params: Any) -> dict[str, Any]:
        """Invoke a PentrAI tool route and return its JSON result.

        Implementation notes:
          * POST to `${base_url}/api/tools/<tool>` (match the server's routing)
          * enforce a timeout; surface non-2xx as a structured error, not an raise
          * assert the target host in `params` resolves to the sandbox instance
            before sending — refuse anything else
        """
        raise NotImplementedError("tools.pentrai_client.PentrAIClient.call")

    # A few typed conveniences the stages lean on; all defer to `call`.

    def port_scan(self, target: str, **kw: Any) -> dict[str, Any]:
        raise NotImplementedError("tools.pentrai_client.PentrAIClient.port_scan")

    def http_probe(self, url: str, **kw: Any) -> dict[str, Any]:
        raise NotImplementedError("tools.pentrai_client.PentrAIClient.http_probe")
