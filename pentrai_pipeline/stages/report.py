"""
Stage 7 — REPORT.

Render two artifacts from the same validated dataset (their audiences differ, the
facts don't):

  * TECHNICAL — full detail per confirmed finding: CWE/CVE, code location, the PoC,
    exact reproduction steps, and remediation. For the client's engineers.
  * CLIENT    — business-risk framing: what an attacker could actually do, which
    attacks WORKED, a prioritized fix list. No exploit gore.

Only CONFIRMED findings carry the "we proved this" weight; refuted/inconclusive
ones are shown as such (or omitted from the client report) so the document never
overclaims. Markdown out now; PDF/branding can wrap this later.
"""

from __future__ import annotations

from ..config import Settings
from ..contracts import Audience, Report, ReconResult, Target, ValidatedFinding


def build_reports(
    validated: list[ValidatedFinding],
    target: Target,
    recon: ReconResult,
    settings: Settings,
) -> list[Report]:
    """Produce [technical_report, client_report] from the validated findings.

    Responsibilities:
      * summarize scope, posture (external vs authenticated), and what was tested
      * technical: per-finding PoC + reproduction + remediation + CWE/CVE refs
      * client: prioritized, plain-language "what worked / what to fix first"
      * an LLM may help with prose, but severities/outcomes come from the data,
        not the model — the report must not invent findings

    Returns both Report objects (Audience.TECHNICAL, Audience.CLIENT).
    """
    raise NotImplementedError("stages.report.build_reports")
