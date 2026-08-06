"""
PentrAI Pipeline
================
The productized, end-to-end pipeline that sits ON TOP OF the existing PentrAI
engine (`pentrai_server.py` + its 150-tool catalog, exposed over MCP/HTTP).

Given a company's own codebase (folder / zip / git repo), the pipeline:

  1. INGEST     normalize the input, detect the stack, locate a container recipe
  2. DEPLOY     build + run it inside an isolated, egress-controlled sandbox
  3. RECON      map the external attack surface of the running target
  4. ANALYZE    two engines in parallel:
                  - SCA  : dependencies -> known CVEs   (deterministic, cheap)
                  - SAST : LLM over source -> logic/authz/missing-check bugs
  5. SYNTHESIZE merge findings into a ranked, externally-validatable attack plan
  6. EXPLOIT    a live agent attempts each hypothesis against the running target;
                a finding is only "CONFIRMED" if it is actually reproduced (the
                attack is the verification oracle for the static hypothesis)
  7. REPORT     render two artifacts: a technical report and a client-facing one

Design posture (see docs/ARCHITECTURE.md):
  * white-box ANALYSIS driving live VALIDATION on the running target
  * the attack may use whatever access the user provides — the source, and,
    optionally, secrets/credentials. `posture` only RECORDS what access was used
    (a finding that works with no creds is flagged as the more severe pre-auth case)
  * phase 1 hands phase 2 a *typed* attack plan, not prose (contracts.py)

The web front-end is deliberately OUT OF SCOPE for now; drive the pipeline from
`cli.py` (`python -m pentrai_pipeline <source>`).
"""

from __future__ import annotations

__version__ = "0.0.1"

from .orchestrator import run_pipeline  # noqa: E402

__all__ = ["run_pipeline", "__version__"]
