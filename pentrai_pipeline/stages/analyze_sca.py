"""
Stage 4a — ANALYZE / SCA (Software Composition Analysis).

The deterministic engine: inventory the target's dependencies and look each one up
against known-vulnerability data (OSV / NVD / a scanner like trivy or grype). This
barely needs an LLM — a scanner does it better and reproducibly — so keep the model
OUT of this path. Its output is CVE-backed Findings that the LLM half never has to
guess at.

Emits Findings with FindingSource.SCA: dependency + cve + a CVSS-derived severity.
Whether each is realistically reachable on the running surface is a ranking signal
set here (best-effort) and refined in `synthesize`.
"""

from __future__ import annotations

from ..config import Settings
from ..contracts import Finding, IngestResult


def analyze_sca(ingest: IngestResult, settings: Settings) -> list[Finding]:
    """Return CVE-backed Findings for vulnerable dependencies.

    Responsibilities:
      * build a dependency inventory from lockfiles/manifests (or via syft)
      * run `settings.sca_tool` (osv-scanner / trivy / grype) over it
      * map each hit to a Finding: dependency="pkg@ver", cve=..., severity from CVSS
      * set `network_reachable` best-effort (is the vulnerable component exposed?)

    Deterministic and side-effect free w.r.t. the target; safe to run in parallel
    with SAST.
    """
    raise NotImplementedError("stages.analyze_sca.analyze_sca")
