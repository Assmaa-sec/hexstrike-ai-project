"""
Stage 3 — RECON.

Map the attack surface of the *running* target from inside the sandbox network:
open ports, service/tech fingerprints, and (for web targets) reachable endpoints
and their parameters. This gives the exploitation phase concrete places to aim and
gives SAST real routes to correlate its source-level findings against.

Drives the existing PentrAI tool catalog (nmap, httpx, katana/hakrawler, etc.)
through `tools.pentrai_client`; it does not reimplement scanning.
"""

from __future__ import annotations

from ..config import Settings
from ..contracts import DeployedTarget, ReconResult


def recon(deployed: DeployedTarget, settings: Settings) -> ReconResult:
    """Enumerate the running target's surface into a ReconResult.

    Responsibilities:
      * port scan `deployed.internal_base_url` / exposed_ports
      * fingerprint services and versions
      * for HTTP targets: crawl for endpoints, methods, and input parameters
      * keep it observational — recon does not exploit anything

    All calls go through the sandbox network to the target only.
    """
    raise NotImplementedError("stages.recon.recon")
