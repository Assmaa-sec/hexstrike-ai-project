"""
Phase-1 analyst agent: reads source (+ recon context) and emits structured
Findings. Reasons about code only — it holds no offensive tools.

Prompt-injection stance (docs/THREAT_MODEL.md): source files are wrapped and
presented as untrusted DATA. The system prompt fixes the agent's task and output
schema; instructions embedded in the code under review must not be able to change
what the agent does or reports.
"""

from __future__ import annotations

from ..config import Settings
from ..contracts import Finding, IngestResult, ReconResult
from .llm import LLMClient


class AnalystAgent:
    def __init__(self, llm: LLMClient, settings: Settings):
        self.llm = llm
        self.settings = settings

    def find_bugs(self, ingest: IngestResult, recon: ReconResult) -> list[Finding]:
        """Analyze selected source and return SAST Findings.

        Implementation sketch:
          * pick + chunk high-signal code (route handlers, authN/authZ middleware,
            query construction, deserialization, file/OS/command sinks)
          * for each chunk, ask the LLM (via structured output) for candidate
            weaknesses with cwe / code_location / severity / confidence /
            suggested_validation
          * wrap file contents as untrusted data; keep the task/schema in the
            system prompt where the reviewed code can't reach it
          * normalize into Finding(source=FindingSource.SAST, ...)
        """
        raise NotImplementedError("agents.analyst_agent.AnalystAgent.find_bugs")
