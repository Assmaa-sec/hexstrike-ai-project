"""
Stage 2 — SANDBOX (deploy + teardown).

Build the target from its recipe and run it inside an ISOLATED, egress-controlled,
hardened container. This is the containment boundary of the whole product; see
docs/THREAT_MODEL.md.

Isolation model:
  * Network: a dedicated Docker network created `--internal` (Dockerfile) or via a
    compose override `networks.default.internal: true` (compose). Internal networks
    keep Docker's embedded DNS — containers on them reach each other by name — while
    cutting every route to the public internet. The target is NOT published to a host
    port; recon/exploit reach it from a container attached to `network_name`.
  * Runtime hardening (limits the blast radius of running a stranger's code):
    `--cap-drop ALL`, `--security-opt no-new-privileges`, and pids/memory/cpu limits
    (SandboxSettings). Applied to the single-container run and to every service in
    the compose override.
  * Build: the image BUILD runs on the host daemon (which has internet, to pull the
    base image and install deps). That is a residual risk — build-time code executes
    on the host — addressed in THREAT_MODEL.md; `build_network` can cut build egress
    for targets that vendor their dependencies.

Multi-service compose is supported: all services come up on the internal network and
are hardened; the target URL points at the port-publishing (web-facing) service.
`teardown` is idempotent and always called by the orchestrator.
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
    proc = subprocess.run(args, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)
    if check and proc.returncode != 0:
        raise SandboxError(f"`{' '.join(args)}` failed ({proc.returncode}):\n"
                           f"{(proc.stderr or proc.stdout).strip()}")
    return proc


def _quiet(args, timeout=60):
    try:
        subprocess.run(args, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    except Exception:
        pass


def _capture(args, timeout=60):
    try:
        return subprocess.run(args, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout).stdout
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
        build = [docker, "build", "-t", image, "-f", dockerfile]
        if sb.build_network:
            build += ["--network", sb.build_network]
        build.append(context)
        _run(build, timeout=sb.build_timeout_s)

    net_args = [docker, "network", "create"]
    if not sb.allow_egress:
        net_args.append("--internal")
    net_args.append(net)
    _run(net_args, timeout=60)

    # No host port published: the target is reachable only from inside the network.
    run = [docker, "run", "-d", "--name", token, "--network", net]
    run += _hardening_run_flags(sb)
    run.append(image)
    _run(run, timeout=120)
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
    services = _compose_services(recipe)  # [(name, container_port|None)] in file order
    files = ["-f", recipe]

    # Isolation + hardening applied WITHOUT editing the original recipe.
    override = _compose_override(services, sb)
    if override:
        path = logs_dir / "pentrai-sandbox.yml"
        path.write_text(override)
        files += ["-f", str(path)]

    _run([docker, "compose", *files, "-p", token, "up", "-d", "--build"], timeout=sb.build_timeout_s)

    ids = _capture([docker, "compose", "-p", token, "ps", "-q"]).split()
    service, port = _target_service(services, ingest)

    return DeployedTarget(
        internal_base_url=f"http://{service}:{port}",
        network_name=f"{token}_default",
        container_ids=ids,
        exposed_ports=[port],
        teardown_token=token,
        logs_dir=str(logs_dir),
    )


# --- hardening ---------------------------------------------------------------

def _hardening_run_flags(sb):
    flags = []
    for cap in sb.cap_drop:
        flags += ["--cap-drop", cap]
    for cap in sb.cap_add:
        flags += ["--cap-add", cap]
    if sb.no_new_privileges:
        flags += ["--security-opt", "no-new-privileges:true"]
    if sb.pids_limit:
        flags += ["--pids-limit", str(sb.pids_limit)]
    if sb.memory_limit:
        flags += ["--memory", sb.memory_limit]
    if sb.cpu_limit:
        flags += ["--cpus", sb.cpu_limit]
    return flags


def _compose_override(services, sb) -> str:
    """A compose override that hardens every service and makes the default network
    internal — layered on top of the original recipe, which is never modified."""
    lines = []
    hardening = sb.cap_drop or sb.cap_add or sb.no_new_privileges or sb.pids_limit \
        or sb.memory_limit or sb.cpu_limit
    if services and hardening:
        lines.append("services:")
        for name, _port in services:
            lines.append(f"  {name}:")
            if sb.cap_drop:
                lines.append("    cap_drop:")
                for cap in sb.cap_drop:
                    lines.append(f"      - {cap}")
            if sb.cap_add:
                lines.append("    cap_add:")
                for cap in sb.cap_add:
                    lines.append(f"      - {cap}")
            if sb.no_new_privileges:
                lines += ["    security_opt:", "      - no-new-privileges:true"]
            if sb.pids_limit:
                lines.append(f"    pids_limit: {sb.pids_limit}")
            if sb.memory_limit:
                lines.append(f"    mem_limit: {sb.memory_limit}")
            if sb.cpu_limit:
                lines.append(f"    cpus: {sb.cpu_limit}")
    if not sb.allow_egress:
        lines += ["networks:", "  default:", "    internal: true"]
    return "\n".join(lines) + "\n" if lines else ""


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


# --- compose parsing ---------------------------------------------------------

def _first_port(ingest: IngestResult):
    for entry in ingest.entrypoints:
        if str(entry).isdigit():
            return int(entry)
    return None


def _compose_services(recipe):
    """[(service_name, first_container_port|None)] in file order — a light structural
    walk of the `services:` block (no YAML dependency)."""
    try:
        text = Path(recipe).read_text(errors="ignore")
    except OSError:
        return []
    result = []
    in_services = False
    base_indent = None
    cur = None
    cur_port = None
    for line in text.splitlines():
        if re.match(r"^services:\s*$", line):
            in_services = True
            continue
        if not in_services:
            continue
        if re.match(r"^\S", line):  # dedent to top level => services block ended
            break
        m = re.match(r"^(\s+)([A-Za-z0-9._-]+):\s*$", line)
        if m and (base_indent is None or len(m.group(1)) == base_indent):
            if base_indent is None:
                base_indent = len(m.group(1))
            if cur is not None:
                result.append((cur, cur_port))
            cur, cur_port = m.group(2), None
            continue
        if cur is not None and cur_port is None:
            pm = re.search(r"(\d{2,5})\s*:\s*(\d{2,5})", line)
            if pm:
                cur_port = int(pm.group(2))
    if cur is not None:
        result.append((cur, cur_port))
    return result


def _target_service(services, ingest):
    """The web-facing entry: prefer a service that publishes a port; else the first."""
    for name, port in services:
        if port:
            return name, port
    if services:
        return services[0][0], (_first_port(ingest) or 8000)
    return "app", (_first_port(ingest) or 8000)
