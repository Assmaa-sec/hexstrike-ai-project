"""
Runtime configuration for the pipeline.

Everything the stages need to reach the outside world (the PentrAI tool server,
the LLM, Docker) is centralized here and sourced from the environment so the same
code runs on a dev laptop and in the eventual hosted product. Defaults match the
existing PentrAI setup (server on :8888, the llm_proxy on :8889).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from .contracts import Posture


@dataclass
class LLMSettings:
    # Provider-agnostic, OpenAI-compatible. Points at the existing llm_proxy by
    # default (which forwards to DeepSeek and logs tool calls); override to hit any
    # OpenAI-compatible endpoint directly.
    base_url: str = field(default_factory=lambda: os.getenv("PENTRAI_LLM_BASE_URL", "http://127.0.0.1:8889/v1"))
    api_key: str = field(default_factory=lambda: os.getenv("PENTRAI_LLM_API_KEY", ""))
    model: str = field(default_factory=lambda: os.getenv("PENTRAI_LLM_MODEL", "deepseek-chat"))
    request_timeout_s: int = 300


@dataclass
class SandboxSettings:
    # The containment boundary. See docs/THREAT_MODEL.md.
    docker_bin: str = field(default_factory=lambda: os.getenv("PENTRAI_DOCKER_BIN", "docker"))
    # The sandbox network gets NO route to the public internet by default: the
    # target and the attacker tooling can reach each other and nothing else.
    allow_egress: bool = False
    # Hosts the sandbox may still reach even when egress is off (e.g. a local CVE
    # mirror). Keep empty for full isolation.
    egress_allowlist: list[str] = field(default_factory=list)
    build_timeout_s: int = 900
    healthcheck_timeout_s: int = 120


@dataclass
class Settings:
    # The existing PentrAI tool server (150-tool catalog) that stages drive.
    pentrai_server_url: str = field(default_factory=lambda: os.getenv("PENTRAI_SERVER_URL", "http://127.0.0.1:8888"))

    # Where the pipeline stages write working copies, logs and artifacts.
    work_dir: str = field(default_factory=lambda: os.getenv("PENTRAI_WORK_DIR", os.path.join(os.getcwd(), ".pentrai_runs")))

    default_posture: Posture = Posture.EXTERNAL

    # Which SCA backend to shell out to (all deterministic CVE scanners).
    sca_tool: str = field(default_factory=lambda: os.getenv("PENTRAI_SCA_TOOL", "osv-scanner"))

    # Budget guards for the exploitation agent so a job can't run forever / spend
    # unbounded tokens attempting one hypothesis.
    max_exploit_steps_per_finding: int = 20
    max_findings_to_validate: int = 25

    llm: LLMSettings = field(default_factory=LLMSettings)
    sandbox: SandboxSettings = field(default_factory=SandboxSettings)

    @classmethod
    def from_env(cls) -> "Settings":
        return cls()
