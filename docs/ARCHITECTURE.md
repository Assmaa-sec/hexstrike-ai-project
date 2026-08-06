# PentrAI Pipeline — Architecture

**Status:** scaffold. Contracts and orchestration are wired; stages are stubs.

## What it is

An end-to-end, autonomous **pentest-as-a-service** pipeline: a company points it at
its own codebase and gets back (a) a technical report and (b) a client-facing report
describing which attacks *actually worked* and what to fix.

It is a **productization of the existing PentrAI engine**, not a rewrite. The engine
(`pentrai_server.py` + `pentrai_mcp.py`) already exposes a 150-tool offensive
catalog over HTTP/MCP. The pipeline wraps that engine in the four things a product
needs and the engine doesn't have: an **ingestion front**, a **sandbox**, a
**two-phase agent workflow**, and a **reporting layer**.

## The pipeline

```
 Target (folder | zip | git url, + optional secrets, + authorization)
   │
   ▼
 1. INGEST        normalize source, detect stack, REQUIRE a container recipe
   │              (Dockerfile / compose / prebuilt image — we do not auto-build
   ▼              arbitrary repos; that is the classic failure mode)
 2. DEPLOY        build + run inside an isolated, egress-controlled sandbox
   │
   ▼
 3. RECON         map the running target's surface (ports, tech, endpoints)
   │
   ├── 4a. SCA    dependencies → known CVEs        (deterministic; no LLM)
   ├── 4b. SAST   LLM over source → logic/authz bugs (the model's real job)
   │
   ▼
 5. SYNTHESIZE    merge + rank into ONE typed AttackPlan   ← phase-1 → phase-2 seam
   │
   ▼
 6. EXPLOIT       operator agent proves/refutes each hypothesis LIVE
   │              (the attack is the verification oracle)
   ▼
 7. REPORT        technical report + client report
```

Each arrow is a **typed artifact** (`contracts.py`), not a blob of prose. That is
what makes the two LLM phases a coupled *hypothesis → verification* loop rather than
two disconnected passes.

## Three design decisions that shape everything

### 1. White-box analysis, live validation

We have the source (the user uploads it), so **analysis is white/grey-box** — the
model reads code to know *where* bugs likely are. But a finding is only ever
**CONFIRMED** by *reproducing it against the running target*. Static analysis
produces hypotheses; the live attack is the oracle that separates real bugs from
false positives. That validated-finding — "we actually did this" — is the product's
core value, and (not incidentally) a verification-oracle experiment.

### 2. The attack may use secrets; posture is a label, not a gate

The exploitation phase is allowed to use whatever access the user provides: the
source, and — optionally — credentials/config. `posture` (`EXTERNAL` vs
`AUTHENTICATED`) only **records** what access a given finding actually needed, so
the report can flag the more severe pre-auth cases. It does **not** restrict what
the attack may attempt.

### 3. Two static engines, not one

- **SCA** (dependencies → CVE via OSV/NVD/trivy/grype): deterministic, cheap, and a
  scanner does it better than any LLM. Keep the model out of this path.
- **SAST** (logic / missing-check / authZ bugs in the target's own code): the hard
  semantic work where the LLM earns its keep, and the project's research focus.

They run in parallel and both emit `Finding`s into the same synthesis step.

## How it maps to the code

| Concern | Module |
|---|---|
| Typed artifacts between stages | `pentrai_pipeline/contracts.py` |
| Stage sequence + guaranteed sandbox teardown | `pentrai_pipeline/orchestrator.py` |
| Config (server/LLM/sandbox, budgets) from env | `pentrai_pipeline/config.py` |
| The seven stages | `pentrai_pipeline/stages/*.py` |
| Phase-1 analyst / phase-2 operator agents | `pentrai_pipeline/agents/*.py` |
| Provider-agnostic LLM client (defaults to `llm_proxy`) | `pentrai_pipeline/agents/llm.py` |
| Bridge to the 150-tool PentrAI server | `pentrai_pipeline/tools/pentrai_client.py` |
| Job model the web layer will poll | `pentrai_pipeline/jobs/job.py` |
| CLI (until the web front-end exists) | `pentrai_pipeline/cli.py` |

## Deliberately out of scope (for now)

- **Web front-end** — comes last, once the backend pipeline runs end-to-end.
- **Multi-tenancy / queueing / persistence** — the `Job` abstraction is the seam
  where these slot in; today it is single-process and in-memory.
- **PDF/branded reports** — the reporter emits Markdown; presentation wraps it later.

## Build order (recommended)

The UI and the report are the easy ~10%; the sandbox + orchestration is the ~90%.
Prove the hard seam once, on a narrow vertical (**web apps**, where the existing
tool catalog is strongest), then broaden:

1. `ingest` + `sandbox` for one stack (e.g. a Flask/compose app) — get a target
   *running and reachable* in isolation. This is the make-or-break step.
2. `recon` + `pentrai_client` — reach the running target through the engine.
3. `analyze_sca` (deterministic, quick win) then `analyze_sast` (the LLM half).
4. `synthesize` → `exploit` on **one** vuln class end-to-end (e.g. SQLi or a missing
   authZ check) — the first fully validated finding.
5. `report`. Then widen vuln classes and stacks.

A deliberately vulnerable **guinea-pig** target (`guinea_pig/`) is built alongside
step 1 so every later stage has something real to run against.
