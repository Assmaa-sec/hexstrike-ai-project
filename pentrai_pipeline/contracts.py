"""
Typed artifacts passed between pipeline stages.

These contracts ARE the backbone of the design. Each stage consumes the artifact
produced by the previous one and emits the next. Keeping the handoffs explicit is
what lets phase 1 (analysis) give phase 2 (exploitation) a structured attack plan
instead of a wall of prose, and what lets the reporter render two audiences from
one dataset.

Nothing here does work; these are pure data classes. Stages live in `stages/`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Posture(str, Enum):
    """How much access the live attack actually used. This is a LABEL for the
    report, not a restriction on what the attack may try.

    EXTERNAL       no secrets/credentials were supplied; the attack worked with
                   only what an unauthenticated client can reach. A finding that
                   holds here is more severe — it is exploitable pre-auth.
    AUTHENTICATED  the user supplied credentials/config and the attack was allowed
                   to use them. This is fine and is the natural default whenever
                   secrets are provided; it yields a deeper, less "outsider" check.
    """

    EXTERNAL = "external"
    AUTHENTICATED = "authenticated"


class SourceKind(str, Enum):
    FOLDER = "folder"
    ZIP = "zip"
    GIT = "git"


class Containerization(str, Enum):
    """How we will stand the target up. Decision 1.a + 1.c: we REQUIRE one of
    these; we do NOT try to infer-and-build an arbitrary repo (too fragile)."""

    DOCKERFILE = "dockerfile"
    COMPOSE = "compose"
    PREBUILT_IMAGE = "prebuilt_image"
    NONE = "none"  # -> ingest fails with an actionable message


class FindingSource(str, Enum):
    SCA = "sca"      # dependency -> known CVE (deterministic)
    SAST = "sast"    # LLM over source -> logic/authz/missing-check bug
    RECON = "recon"  # observed on the running surface (exposed admin panel, etc.)


class Severity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Confidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ValidationOutcome(str, Enum):
    CONFIRMED = "confirmed"        # actually exploited from the allowed posture
    REFUTED = "refuted"           # tried, could not reproduce -> likely false positive
    INCONCLUSIVE = "inconclusive"  # ran out of budget / ambiguous
    SKIPPED = "skipped"           # not reachable from posture, or out of scope


# ---------------------------------------------------------------------------
# Stage 0 — the input
# ---------------------------------------------------------------------------


@dataclass
class Target:
    """What the user submits, plus their authorization to test it."""

    source_ref: str                     # path to folder/zip, or a git URL
    kind: SourceKind
    posture: Posture = Posture.EXTERNAL
    secrets_path: Optional[str] = None  # only read in AUTHENTICATED mode
    # The user must attest they own / are authorized to test this. The sandbox
    # rebuilds a private copy, but scope/authorization is still recorded.
    authorized: bool = False
    scope_note: str = ""
    id: str = field(default_factory=new_id)
    created_at: datetime = field(default_factory=_now)


# ---------------------------------------------------------------------------
# Stage 1 — ingest
# ---------------------------------------------------------------------------


@dataclass
class IngestResult:
    """Normalized source on disk + how we intend to run it."""

    source_dir: str                     # local, normalized working copy of the code
    stack: list[str] = field(default_factory=list)      # e.g. ["python", "flask", "postgres"]
    containerization: Containerization = Containerization.NONE
    container_ref: str = ""             # Dockerfile path, compose path, or image name
    entrypoints: list[str] = field(default_factory=list)  # exposed services/ports hinted by the recipe
    has_secrets: bool = False


# ---------------------------------------------------------------------------
# Stage 2 — deploy (sandbox)
# ---------------------------------------------------------------------------


@dataclass
class DeployedTarget:
    """A running instance inside the isolated sandbox network.

    `internal_base_url` is how the recon/exploit stages reach the target from
    WITHIN the sandbox network. The target has no route to the public internet
    (see docs/THREAT_MODEL.md); `teardown_token` is what sandbox.teardown() needs
    to destroy every container/network/volume created for this job.
    """

    internal_base_url: str
    network_name: str
    container_ids: list[str] = field(default_factory=list)
    exposed_ports: list[int] = field(default_factory=list)
    teardown_token: str = ""
    logs_dir: str = ""


# ---------------------------------------------------------------------------
# Stage 3 — recon
# ---------------------------------------------------------------------------


@dataclass
class Endpoint:
    method: str
    path: str
    params: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class ReconResult:
    """The externally observable surface of the running target."""

    open_ports: list[int] = field(default_factory=list)
    fingerprints: list[str] = field(default_factory=list)  # detected tech/versions
    endpoints: list[Endpoint] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Stage 4 — findings (from SCA + SAST)
# ---------------------------------------------------------------------------


@dataclass
class Finding:
    """A *hypothesis* about a weakness. Not yet proven — that's phase 2's job."""

    title: str
    source: FindingSource
    severity: Severity = Severity.MEDIUM
    confidence: Confidence = Confidence.MEDIUM
    cwe: str = ""                       # e.g. "CWE-89"
    description: str = ""

    # Location is polymorphic depending on `source`; fill what applies:
    code_location: str = ""             # SAST: "path/to/file.py:120"
    dependency: str = ""                # SCA:  "flask@2.0.1"
    cve: str = ""                       # SCA:  "CVE-2023-XXXXX"
    endpoint: str = ""                  # RECON/validation target: "POST /login"

    # Is there a network path to trigger this on the RUNNING target (vs a purely
    # static/theoretical concern)? Used to RANK the attack plan, not to hard-filter
    # it — the attack may use supplied secrets, so auth-gated issues still qualify.
    network_reachable: bool = True
    suggested_validation: str = ""      # how phase 2 should try to prove it

    id: str = field(default_factory=new_id)


# ---------------------------------------------------------------------------
# Stage 5 — synthesize -> attack plan (the phase 1 -> phase 2 handoff)
# ---------------------------------------------------------------------------


@dataclass
class AttackPlan:
    """Ranked, de-duplicated hypotheses the exploitation agent will attempt, in
    order. This is the ONLY thing that crosses the boundary between the analysis
    agent and the exploitation agent."""

    hypotheses: list[Finding] = field(default_factory=list)
    rationale: str = ""
    posture: Posture = Posture.EXTERNAL


# ---------------------------------------------------------------------------
# Stage 6 — exploitation -> validated findings
# ---------------------------------------------------------------------------


@dataclass
class Evidence:
    """Reproducible proof captured during a validation attempt."""

    summary: str = ""
    request: str = ""                   # e.g. the raw HTTP request that worked
    response_excerpt: str = ""
    commands: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)  # paths to saved files


@dataclass
class ValidatedFinding:
    finding: Finding
    outcome: ValidationOutcome
    evidence: Optional[Evidence] = None
    reproduction: list[str] = field(default_factory=list)  # ordered steps
    notes: str = ""


# ---------------------------------------------------------------------------
# Stage 7 — reports
# ---------------------------------------------------------------------------


class Audience(str, Enum):
    TECHNICAL = "technical"   # full detail: PoC, repro, CWE/CVE, remediation
    CLIENT = "client"         # business-risk framing, prioritized fixes, what worked


@dataclass
class Report:
    audience: Audience
    title: str
    body_markdown: str
    generated_at: datetime = field(default_factory=_now)


# ---------------------------------------------------------------------------
# The bundle produced by a full run
# ---------------------------------------------------------------------------


@dataclass
class PipelineResult:
    target: Target
    ingest: Optional[IngestResult] = None
    recon: Optional[ReconResult] = None
    findings: list[Finding] = field(default_factory=list)
    attack_plan: Optional[AttackPlan] = None
    validated: list[ValidatedFinding] = field(default_factory=list)
    reports: list[Report] = field(default_factory=list)
