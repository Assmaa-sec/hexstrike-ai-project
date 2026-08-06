"""
Phase-2 operator agent: given one hypothesis, drives the PentrAI tool catalog
against the running target to prove or refute it, capturing evidence.

This is the agent with real offensive capability, so it is the most tightly
bounded: it can reach only the sandbox network (all tool calls go through
`tools.pentrai_client`, which is pointed at the isolated target), it runs under a
per-finding step budget, and it cannot write to the report data model — it returns
a ValidatedFinding and nothing else decides severity for it.
"""

from __future__ import annotations

from ..config import Settings
from ..contracts import DeployedTarget, Finding, ValidatedFinding
from ..tools.pentrai_client import PentrAIClient
from .llm import LLMClient


class OperatorAgent:
    def __init__(self, llm: LLMClient, tools: PentrAIClient, settings: Settings):
        self.llm = llm
        self.tools = tools
        self.settings = settings

    def validate(self, finding: Finding, deployed: DeployedTarget) -> ValidatedFinding:
        """Attempt to reproduce `finding` against the running target.

        Implementation sketch:
          * a bounded tool-use loop (<= settings.max_exploit_steps_per_finding):
            the LLM proposes a tool call, `self.tools` runs it against the target,
            the result feeds the next step
          * decide CONFIRMED / REFUTED / INCONCLUSIVE from concrete evidence
            (e.g. a real flag/secret read, an auth bypass observed, a shell) — not
            from the model's say-so
          * on CONFIRMED, assemble Evidence (working request/response, commands,
            saved artifacts) and ordered reproduction steps
          * refuse any tool target that is not the sandboxed instance
        """
        raise NotImplementedError("agents.operator_agent.OperatorAgent.validate")
