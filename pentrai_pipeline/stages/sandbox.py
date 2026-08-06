"""
Stage 2 — SANDBOX (deploy + teardown).

Build the target from its container recipe and run it inside an ISOLATED, egress-
controlled network. This is the containment boundary of the whole product; read
docs/THREAT_MODEL.md before touching it.

Two dangers are contained here:
  * we are running UNTRUSTED code submitted by a stranger, and
  * we are about to point real offensive tooling at it.

So the target (and the attacker tooling that will hit it) live on a private Docker
network with NO route to the public internet by default (Settings.sandbox). The
attack traffic must be physically unable to leave the sandbox and reach a third
party. `deploy` returns a handle; `teardown` MUST destroy everything it created
and is always called by the orchestrator in a finally block.
"""

from __future__ import annotations

from ..config import Settings
from ..contracts import DeployedTarget, IngestResult


def deploy(ingest: IngestResult, settings: Settings) -> DeployedTarget:
    """Build + start the target inside the sandbox and return a handle to it.

    Responsibilities:
      * create a dedicated Docker network with egress locked down per
        Settings.sandbox (allow_egress / egress_allowlist)
      * build from Dockerfile / bring up docker-compose / pull the prebuilt image
      * start the container(s); wait for health up to healthcheck_timeout_s
      * expose an INTERNAL base URL reachable only from inside the sandbox network
        (recon/exploit run from an attacker container on that same network)
      * record container ids, ports, and a teardown_token for cleanup

    Never publish the target on a host port that is reachable from outside the
    sandbox; the only thing that talks to it is our own attacker tooling.
    """
    raise NotImplementedError("stages.sandbox.deploy")


def teardown(deployed: DeployedTarget, settings: Settings) -> None:
    """Destroy every container, network and volume created for this job.

    Must be idempotent and must not raise on already-gone resources — the
    orchestrator calls it in a finally block, possibly after a partial deploy.
    """
    raise NotImplementedError("stages.sandbox.teardown")
