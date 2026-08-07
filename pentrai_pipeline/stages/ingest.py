"""
Stage 1 — INGEST.

Turn whatever the user submitted (folder / zip / git URL) into a normalized local
source tree, figure out the stack, and locate the recipe we will use to run it.

Key decision (1.a + 1.c): we do NOT try to infer-and-build an arbitrary repo. We
REQUIRE a container recipe — a Dockerfile or a docker-compose file. If none is
found, we fail here with an actionable message. Attempting to auto-build random
repos is the classic failure mode of autonomous pentest systems; we sidestep it by
contract.

Nothing is built or run in this stage — that's the sandbox's job. We only inspect,
and we treat every file we read as untrusted DATA, never as instructions.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

from ..config import Settings
from ..contracts import Containerization, IngestResult, Posture, SourceKind, Target

# Never worth copying into the sandbox workspace.
_COPY_IGNORE = shutil.ignore_patterns(
    ".git", "__pycache__", "*.pyc", "node_modules", ".venv", "venv", "env",
    ".tox", ".mypy_cache", ".pytest_cache", ".pentrai_runs", "*.db",
)

# Manifest file -> language marker.
_STACK_MARKERS = {
    "requirements.txt": "python", "pyproject.toml": "python", "Pipfile": "python",
    "package.json": "node", "composer.json": "php", "go.mod": "go",
    "pom.xml": "java", "build.gradle": "java", "Gemfile": "ruby", "Cargo.toml": "rust",
}

_COMPOSE_NAMES = ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml")


def ingest(target: Target, settings: Settings) -> IngestResult:
    """Normalize `target` into an IngestResult (see module docstring)."""
    src_dir = Path(settings.work_dir) / target.id / "src"
    _materialize(target, src_dir)

    kind, ref = _find_recipe(src_dir)
    if kind is Containerization.NONE:
        raise ValueError(
            f"no container recipe found under {src_dir} "
            "(need a Dockerfile or a docker-compose file). The pipeline does not "
            "auto-build arbitrary repos — add one and resubmit."
        )

    return IngestResult(
        source_dir=str(src_dir),
        stack=_detect_stack(src_dir),
        containerization=kind,
        container_ref=str(ref),
        entrypoints=_guess_ports(ref, kind),
        has_secrets=bool(
            target.posture is Posture.AUTHENTICATED
            and target.secrets_path
            and os.path.exists(target.secrets_path)
        ),
    )


def _materialize(target: Target, src_dir: Path) -> None:
    """Fetch/unpack the source into `src_dir` (never touch the user's original)."""
    if src_dir.exists():
        shutil.rmtree(src_dir)
    src_dir.parent.mkdir(parents=True, exist_ok=True)

    if target.kind is SourceKind.FOLDER:
        src = Path(target.source_ref)
        if not src.is_dir():
            raise ValueError(f"source folder not found: {src}")
        shutil.copytree(src, src_dir, ignore=_COPY_IGNORE)
    elif target.kind is SourceKind.ZIP:
        _safe_extract(Path(target.source_ref), src_dir)
    elif target.kind is SourceKind.GIT:
        src_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "clone", "--depth", "1", target.source_ref, str(src_dir)],
            check=True, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600,
        )
    else:
        raise ValueError(f"unsupported source kind: {target.kind}")


def _safe_extract(zip_path: Path, dest: Path) -> None:
    """Extract a zip, refusing any member that would escape `dest` (zip-slip)."""
    if not zip_path.is_file():
        raise ValueError(f"zip not found: {zip_path}")
    dest.mkdir(parents=True, exist_ok=True)
    dest_resolved = str(dest.resolve())
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.namelist():
            if os.path.isabs(member) or not str((dest / member).resolve()).startswith(dest_resolved):
                raise ValueError(f"unsafe path in zip (zip-slip): {member}")
        zf.extractall(dest)


def _find_recipe(src_dir: Path):
    """Locate a container recipe. Compose wins over a bare Dockerfile (more complete);
    the shallowest match wins so a root recipe beats one nested in an example dir."""
    compose = _shallowest(src_dir, _COMPOSE_NAMES)
    if compose is not None:
        return Containerization.COMPOSE, compose
    dockerfile = _shallowest(src_dir, ("Dockerfile",))
    if dockerfile is not None:
        return Containerization.DOCKERFILE, dockerfile
    return Containerization.NONE, ""


def _shallowest(src_dir: Path, names):
    best, best_depth = None, None
    for name in names:
        for p in src_dir.rglob(name):
            if not p.is_file():
                continue
            depth = len(p.relative_to(src_dir).parts)
            if best_depth is None or depth < best_depth:
                best, best_depth = p, depth
    return best


def _detect_stack(src_dir: Path):
    found = []
    for marker, lang in _STACK_MARKERS.items():
        if lang in found:
            continue
        if next(iter(src_dir.rglob(marker)), None) is not None:
            found.append(lang)
    for req in src_dir.rglob("requirements.txt"):
        try:
            text = req.read_text(errors="ignore").lower()
        except OSError:
            continue
        for framework in ("flask", "django", "fastapi"):
            if framework in text and framework not in found:
                found.append(framework)
    return found


def _guess_ports(ref, kind):
    """Best-effort exposed container ports (a hint for recon; authoritative discovery
    is Phase 3). Stored as strings in IngestResult.entrypoints."""
    try:
        text = Path(ref).read_text(errors="ignore")
    except OSError:
        return []
    ports = []
    if kind is Containerization.DOCKERFILE:
        for m in re.finditer(r"(?im)^\s*EXPOSE\s+(.+)$", text):
            ports += [t.split("/")[0] for t in m.group(1).split() if t.split("/")[0].isdigit()]
    else:  # compose: take the container side of "host:container" mappings
        for m in re.finditer(r"(\d{2,5})\s*:\s*(\d{2,5})", text):
            ports.append(m.group(2))
    seen = []
    for p in ports:
        if p not in seen:
            seen.append(p)
    return seen
