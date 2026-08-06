# PentrAI Pipeline — Build Progress & Playbook

**Shared source of truth for the pipeline build.** If you're picking up work, read this
file top to bottom once, then start at [How to build a phase](#how-to-build-a-phase).

- **What we're building & why:** [`ARCHITECTURE.md`](ARCHITECTURE.md)
- **Containment / safety rules:** [`THREAT_MODEL.md`](THREAT_MODEL.md)
- **This file:** where things stand · how to build the next phase · how to document a done one.

### How to use this file
1. The **[Phase status](#phase-status)** table is the at-a-glance tracker. Update the Status/Owner cells when you start and finish.
2. **[Invariants](#invariants-hold-in-every-phase)** must hold in every phase — read them once and don't break them.
3. **[How to build a phase](#how-to-build-a-phase)** is the repeatable process. Follow it every time.
4. When you finish, add a **[Phase log](#phase-logs)** entry from the template. *A phase is not "done" until its log exists.*
5. Manual/visual verification is **batched**: the product owner verifies in one pass. Never mark a phase user-verified yourself — append items to **[Pending manual verification](#pending-manual-verification)** instead.

---

## Phase status

Legend: ⬜ not started · 🟨 in progress · ✅ code-complete (verified programmatically) · ✔️ user-verified

Model = suggested effort if building with Claude Code (Opus for the hard/security-critical spots, Sonnet for the bulk, Haiku for trivial edits). Wt = rough build/limit cost.

| # | Phase | Owner | Model | Wt | Status | Manual input / verification needed |
|---|-------|-------|-------|----|--------|-------------------------------------|
| 0 | Scaffold (contracts, orchestrator, stubs, docs) | — | Opus | med | ✅ | Skim `ARCHITECTURE.md` + `contracts.py`, confirm design matches intent (verif #1) |
| 1 | **Guinea pig** — vuln containerized web app + ground-truth `SOLUTIONS.md` | — | Sonnet | med | ⬜ | Docker running; eyeball that planted bugs are the classes we want |
| 2 | `ingest` + `sandbox` — target runs, isolated, egress blocked · **make-or-break** | — | Opus | high | ⬜ | Docker/WSL; verify a target comes up **and** egress is actually cut |
| 3 | `recon` + `pentrai_client` — reach the running target via the engine | — | Sonnet | med | ⬜ | `pentrai_server.py` running on `PENTRAI_SERVER_URL` |
| 4 | `analyze_sca` — deps → CVE (deterministic) | — | Sonnet | low | ⬜ | `osv-scanner`/`trivy` installed |
| 5 | `analyze_sast` — LLM logic/authz, injection-hardened | — | Opus | high | ⬜ | LLM endpoint (`llm_proxy` + key) |
| 6 | `synthesize` + `exploit` — first validated finding end-to-end | — | Opus | high | ⬜ | **Verify the CONFIRMED finding + its evidence are real** |
| 7 | `report` — technical + client-facing | — | Sonnet | med | ⬜ | Read both reports for accuracy |
| 8 | Widen vuln classes / stacks | — | Sonnet | ongoing | ⬜ | — |
| 9 | Web front-end (deferred — last) | — | Sonnet | later | ⬜ | — |

---

## Invariants (hold in EVERY phase)

These are non-negotiable; a change that breaks one is wrong even if it "works":

1. **Never modify `pentrai_server.py` / `pentrai_mcp.py`.** Reach the 150-tool engine only through `pentrai_pipeline/tools/pentrai_client.py`.
2. **Stages communicate only through `contracts.py` artifacts.** If you must change a contract, update *every* consumer in the same change and note it in your phase log.
3. **Safety holds** (see `THREAT_MODEL.md`): sandbox egress stays **off** by default; code-under-test is treated as **data, never instructions**; the `Target.authorized` gate stays; every tool call is scoped to the sandbox target.
4. **Each stage stub names itself** in its `NotImplementedError` (e.g. `stages.ingest.ingest`). Replacing that stub with a real implementation is the unit of work — don't widen a phase's scope silently.
5. **The engine stays untouched and the package stays importable.** `python -m compileall pentrai_pipeline` and `import pentrai_pipeline` must pass at the end of every phase.

---

## How to build a phase

The process is the same for every stage — the stub's own docstring is the spec.

1. **Claim it.** In the table above, set the phase Status to 🟨 and put your name in Owner.
2. **Read the spec.** The stage module's docstring lists its exact responsibilities and I/O. Cross-read the [build order in `ARCHITECTURE.md`](ARCHITECTURE.md#build-order-recommended) and the [Invariants](#invariants-hold-in-every-phase) above.
3. **Branch.** `git checkout -b phase-<N>-<short-name>` (e.g. `phase-2-ingest-sandbox`).
4. **Build against the guinea pig.** Everything from Phase 2 on is tested against the Phase 1 target. If there's no guinea pig yet, you're on Phase 1 or 2.
5. **Implement to the contract.** Fill the stub; consume the previous artifact, return the next one. Keep contracts stable (Invariant 2).
6. **Prove it** — see [Definition of done](#definition-of-done-per-phase). Write the exact command that reproduces your result; you'll paste it into the log.
7. **Document it.** Add a [Phase log](#phase-logs) entry from the template. Append anything needing human eyes to [Pending manual verification](#pending-manual-verification).
8. **Land it.** Set Status ✅, commit, and open a PR / hand off. Reference the phase number in the commit.

### Definition of done (per phase)

A phase is code-complete (✅) when **all** of these are true:

- [ ] The stage's `NotImplementedError` is gone and the orchestrator flows past it (the stage trail advances one step further).
- [ ] A **documented command** reproduces the result (a `curl`, `python -m pentrai_pipeline …`, or a test).
- [ ] Programmatic checks pass: `python -m compileall pentrai_pipeline`, `import pentrai_pipeline`, and the orchestrator smoke test.
- [ ] The [Invariants](#invariants-hold-in-every-phase) still hold — spot-check: engine files untouched, sandbox egress off.
- [ ] A **Phase log entry exists**, and anything needing human eyes is in [Pending manual verification](#pending-manual-verification) (never assumed done).

✅ means *the builder verified it programmatically*. ✔️ (user-verified) is set **only** by the product owner after the batched manual pass.

---

## How to document a done phase

Copy this template into [Phase logs](#phase-logs) and fill every field. Keep it terse but reproducible — someone should be able to re-run and re-check your phase from the log alone.

```markdown
### Phase <N> — <name>  <status emoji>
- **Owner:** <name>   **Model:** <model>   **Date:** <YYYY-MM-DD>   **Commit:** <short sha / PR #>
- **Goal:** <one line — what this phase makes true>
- **Built / changed:**
  - `path/to/file.py` — <one line>
- **Key decisions / deviations:** <anything that differs from ARCHITECTURE.md, or a judgment call a reviewer should know; "none" is a valid answer>
- **Run / verify:**
  ```bash
  <exact command(s) that reproduce the result>
  ```
- **Verified (programmatic):** <what was checked and the outcome — compile/import/smoke test/curl result>
- **Pending manual verification:** <cross-ref the numbered item(s) you added below, or "none">
- **Known gaps / handoffs:** <TODOs, things a later phase must handle>
```

---

## Pending manual verification

Batched — the product owner checks these in one pass, not per phase. Add a numbered item whenever a phase produces something only a human should sign off (a rendered report, a running target, a planted-bug set). Give enough detail to check it **cold**.

1. **(Phase 0)** Read `docs/ARCHITECTURE.md`, `docs/THREAT_MODEL.md`, and `pentrai_pipeline/contracts.py` and confirm the pipeline shape, the posture=label-not-gate decision, and the typed artifacts match what we actually want before stages get built on top of them.

---

## Phase logs

### Phase 0 — Scaffold  ✅  *(worked example of the template above)*
- **Owner:** — (initial scaffold)   **Model:** Opus   **Date:** 2026-08-06   **Commit:** _uncommitted (working tree)_
- **Goal:** wire the whole pipeline skeleton so every stage is independently buildable against a stable, typed contract — without touching the engine.
- **Built / changed:**
  - `pentrai_pipeline/contracts.py` — typed artifacts passed between stages (the backbone: `Target`, `IngestResult`, `DeployedTarget`, `ReconResult`, `Finding`, `AttackPlan`, `ValidatedFinding`, `Report`, plus the enums).
  - `pentrai_pipeline/orchestrator.py` — `run_pipeline()`: the stage sequence + authorization gate + guaranteed sandbox teardown in `finally`.
  - `pentrai_pipeline/config.py` — env-driven `Settings` (PentrAI server, LLM, sandbox egress, budgets).
  - `pentrai_pipeline/cli.py` + `__main__.py` — `python -m pentrai_pipeline <src> --authorized`.
  - `pentrai_pipeline/stages/*.py` — the 7 stage stubs (ingest, sandbox, recon, analyze_sca, analyze_sast, synthesize, exploit, report), each a spec in its docstring.
  - `pentrai_pipeline/agents/*.py` — `LLMClient` (provider-agnostic, defaults to `llm_proxy`), `AnalystAgent` (phase 1), `OperatorAgent` (phase 2).
  - `pentrai_pipeline/tools/pentrai_client.py` — the single bridge to the engine.
  - `pentrai_pipeline/jobs/job.py` — `Job`/`JobStore` the web layer will poll.
  - `docs/ARCHITECTURE.md`, `docs/THREAT_MODEL.md`, `guinea_pig/README.md`, this file.
- **Key decisions / deviations:** three locked calls — (1) ingest **requires a container recipe**, no auto-build; (2) **white-box analysis, live validation** (the attack is the verification oracle); (3) **secrets are allowed to the attacker → `posture` is a label, not a gate** (reversed from an earlier black-box idea; do not reintroduce a no-secrets constraint). Two static engines (deterministic SCA + LLM SAST). Egress-off sandbox is the containment boundary.
- **Run / verify:**
  ```bash
  python -m compileall -q pentrai_pipeline
  python -c "import pentrai_pipeline as p; print(p.__version__)"
  python -m pentrai_pipeline --help
  python -c "from pentrai_pipeline.contracts import Target, SourceKind; from pentrai_pipeline.orchestrator import run_pipeline; from pentrai_pipeline.jobs.job import Job; t=Target(source_ref='./x', kind=SourceKind.FOLDER, authorized=True); j=Job.create(t); run_pipeline(t, job=j); print(' -> '.join(e.status.value for e in j.events))"
  ```
- **Verified (programmatic):** compile OK; import OK (v0.0.1); CLI `--help` OK; orchestrator smoke test flows `queued -> ingesting -> failed` and reports `stage not yet implemented: stages.ingest.ingest`; the unauthorized path refuses before any stage. Engine files (`pentrai_server.py`/`pentrai_mcp.py`) untouched.
- **Pending manual verification:** item **#1** above (design/contract review).
- **Known gaps / handoffs:** all 7 stages + both agents + `pentrai_client` + `LLMClient` are stubs (`NotImplementedError`); no guinea pig yet (Phase 1); Job store is in-memory (persistence lands with the web layer, Phase 9).
