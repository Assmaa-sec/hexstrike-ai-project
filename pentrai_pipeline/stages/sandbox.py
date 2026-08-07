"""
Stage 2 — SANDBOX (deploy + teardown).

Build the target from its recipe and run it inside an ISOLATED, egress-controlled
network. This is the containment boundary of the whole product; see
docs/THREAT_MODEL.md.

Isolation model (v1): the target runs on a dedicated Docker network created with
`--internal` (for a Dockerfile) or with a compose override `networks.default.internal:
true` (for compose). An internal network keeps Docker's embedded DNS — so other
containers on it can reach the target by name — while cutting all routes to the
public internet. The target is NOT published to a host port; recon/exploit reach it
by running their tooling in a container attached to `network_name`. Health and
reachability are checked with a throwaway probe container on that same network.

The image BUILD happens on the host daemon (which has internet, to pull the base
image and install deps); only the target's RUNTIME network is isolated.

Scope: single-service targets (a Dockerfile, or a compose file whose services share
one default network). Multi-service compose with bespoke internal topology is a
later refinement. `teardown` is idempotent and always called by the orchestrator.
"""

from __future__ import annotations

import re
import subprocess
import time
import uuid
from pathlib import Path

from ..config import Settings
from ..contracts import Containerization, DeployedTarget, IngestResult


class SandboxError(RuntimeError):
    """Raised when the target cannot be built, started, or made reachable."""


# --- subprocess helpers ------------------------------------------------------

def _run(args, timeout, check=True):
    proc = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    if check and proc.returncode != 0:
        raise SandboxError(f"`{' '.join(args)}` failed ({proc.returncode}):\n"
                           f"{(proc.stderr or proc.stdout).strip()}")
    return proc


def _quiet(args, timeout=60):
    try:
        subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    except Exception:
        pass


def _capture(args, timeout=60):
    try:
        return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout).stdout
    except Exception:
        return ""


# --- deploy ------------------------------------------------------------------

def deploy(ingest: IngestResult, settings: Settings) -> DeployedTarget:
    token = "pentrai_" + uuid.uuid4().hex[:10]
    logs_dir = Path(settings.work_dir) / "sandbox" / token
    logs_dir.mkdir(parents=True, exist_ok=True)

    if ingest.containerization is Containerization.COMPOSE:
        deployed = _deploy_compose(ingest, settings, token, logs_dir)
    elif ingest.containerization in (Containerization.DOCKERFILE, Containerization.PREBUILT_IMAGE):
        deployed = _deploy_single(ingest, settings, token, logs_dir)
    else:
        raise SandboxError(f"unsupported containerization: {ingest.containerization}")

    try:
        _wait_healthy(deployed, settings)
    except Exception:
        _dump_logs(deployed, settings)
        teardown(deployed, settings)  # never leave a half-started sandbox running
        raise
    _dump_logs(deployed, settings)
    return deployed


def _deploy_single(ingest, settings, token, logs_dir) -> DeployedTarget:
    sb = settings.sandbox
    docker = sb.docker_bin
    net = token
    port = _first_port(ingest) or 8000

    if ingest.containerization is Containerization.PREBUILT_IMAGE:
        image = ingest.container_ref
        _run([docker, "pull", image], timeout=sb.build_timeout_s)
    else:
        image = f"{token}:latest"
        dockerfile = ingest.container_ref
        context = str(Path(dockerfile).parent)
        _run([docker, "build", "-t", image, "-f", dockerfile, context], timeout=sb.build_timeout_s)

    net_args = [docker, "network", "create"]
    if not sb.allow_egress:
        net_args.append("--internal")
    net_args.append(net)
    _run(net_args, timeout=60)

    # No host port published: the target is reachable only from inside the network.
    _run([docker, "run", "-d", "--name", token, "--network", net, image], timeout=120)
    cid = _capture([docker, "inspect", "-f", "{{.Id}}", token]).strip()

    return DeployedTarget(
        internal_base_url=f"http://{token}:{port}",
        network_name=net,
        container_ids=[c for c in [cid] if c],
        exposed_ports=[port],
        teardown_token=token,
        logs_dir=str(logs_dir),
    )


def _deploy_compose(ingest, settings, token, logs_dir) -> DeployedTarget:
    sb = settings.sandbox
    docker = sb.docker_bin
    recipe = ingest.container_ref
    files = ["-f", recipe]

    # Egress off: make the default network internal WITHOUT editing the original recipe.
    if not sb.allow_egress:
        override = logs_dir / "pentrai-egress-off.yml"
        override.write_text("networks:\n  default:\n    internal: true\n")
        files += ["-f", str(override)]

    _run([docker, "compose", *files, "-p", token, "up", "-d", "--build"], timeout=sb.build_timeout_s)

    ids = _capture([docker, "compose", "-p", token, "ps", "-q"]).split()
    service, port = _compose_service_and_port(recipe, ingest)

    return DeployedTarget(
        internal_base_url=f"http://{service}:{port}",
        network_name=f"{token}_default",
        container_ids=ids,
        exposed_ports=[port],
        teardown_token=token,
        logs_dir=str(logs_dir),
    )


# --- health + logs -----------------------------------------------------------

def _wait_healthy(deployed: DeployedTarget, settings: Settings) -> None:
    sb = settings.sandbox
    docker = sb.docker_bin
    url = deployed.internal_base_url
    _quiet([docker, "pull", sb.probe_image], timeout=120)  # host pull; probe runs isolated
    deadline = time.time() + sb.healthcheck_timeout_s
    last = ""
    while time.time() < deadline:
        proc = subprocess.run(
            [docker, "run", "--rm", "--network", deployed.network_name, sb.probe_image,
             "wget", "-q", "-T", "4", "-O", "-", url],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=40,
        )
        # exit 0 (2xx) OR an HTTP error both mean the server responded => it's up.
        if proc.returncode == 0 or "returned error" in (proc.stderr or "").lower():
            return
        last = (proc.stderr or proc.stdout).strip()
        time.sleep(2)
    raise SandboxError(f"target not healthy at {url} within {sb.healthcheck_timeout_s}s: {last}")


def _dump_logs(deployed: DeployedTarget, settings: Settings) -> None:
    docker = settings.sandbox.docker_bin
    out = ""
    for cid in deployed.container_ids:
        out += _capture([docker, "logs", "--tail", "200", cid])
    try:
        Path(deployed.logs_dir, "target.log").write_text(out, errors="ignore")
    except OSError:
        pass


# --- teardown ----------------------------------------------------------------

def teardown(deployed: DeployedTarget, settings: Settings) -> None:
    """Destroy everything created for this job. Idempotent; never raises."""
    docker = settings.sandbox.docker_bin
    token = deployed.teardown_token

    # compose containers (by project label) + our single-run container(s)
    for cid in _capture([docker, "ps", "-aq", "--filter",
                         f"label=com.docker.compose.project={token}"]).split():
        _quiet([docker, "rm", "-f", cid])
    for cid in deployed.container_ids:
        _quiet([docker, "rm", "-f", cid])
    _quiet([docker, "rm", "-f", token])

    # networks (single-run net == token; compose net == <token>_default)
    _quiet([docker, "network", "rm", deployed.network_name])
    _quiet([docker, "network", "rm", f"{token}_default"])

    # compose volumes, then the image we built
    for vol in _capture([docker, "volume", "ls", "-q", "--filter",
                         f"label=com.docker.compose.project={token}"]).split():
        _quiet([docker, "volume", "rm", vol])
    _quiet([docker, "rmi", "-f", f"{token}:latest"])


# --- helpers -----------------------------------------------------------------

def _first_port(ingest: IngestResult):
    for entry in ingest.entrypoints:
        if str(entry).isdigit():
            return int(entry)
    return None


def _compose_service_and_port(recipe, ingest):
    """First service name under `services:` (its DNS alias on the compose network) and
    the container port to hit."""
    text = Path(recipe).read_text(errors="ignore")
    service = "app"
    m = re.search(r"(?ms)^services:[ \t]*\n(?:[ \t]*\n|[ \t]*#.*\n)*[ \t]+([A-Za-z0-9._-]+):", text)
    if m:
        service = m.group(1)
    return service, (_first_port(ingest) or 8000)
