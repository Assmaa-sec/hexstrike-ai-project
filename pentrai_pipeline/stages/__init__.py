"""
Pipeline stages. Each module owns exactly one step and communicates only through
the typed artifacts in `contracts.py`. The orchestrator calls them in order:

    ingest -> sandbox.deploy -> recon -> (analyze_sca + analyze_sast)
           -> synthesize -> exploit -> report.build_reports

Stages must be independently implementable: none of them reaches into another's
internals, they only pass artifacts.
"""

from __future__ import annotations
