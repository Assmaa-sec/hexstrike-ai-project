"""
The two agents that do the LLM work, kept deliberately separate:

  * analyst_agent  — phase 1, reads source, emits structured Findings. Has NO
                     offensive tools; it only reasons about code.
  * operator_agent — phase 2, drives the PentrAI tool catalog to prove findings
                     against the running target. Has NO ability to edit the report
                     data model's severities/outcomes.

Splitting them keeps privilege minimal on each side and makes the phase-1 -> phase-2
boundary a real trust boundary, not just a function call.
"""

from __future__ import annotations
