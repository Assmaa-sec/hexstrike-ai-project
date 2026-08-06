# guinea_pig

The deliberately-vulnerable target used to build and test the pipeline against
something real. Building this is **part of the work**, alongside the `ingest` +
`sandbox` stages — every later stage needs a live thing to run against.

## What it must be

- A **containerized web app** (`Dockerfile` + `docker-compose.yml`) so it satisfies
  the ingest contract (recipe required; no auto-build) and comes up cleanly in the
  sandbox.
- **Seeded with known, planted vulnerabilities**, one per class the pipeline claims
  to find/validate — starting narrow:
  - a boolean/error-based **SQL injection** on a reachable endpoint,
  - a **missing authorization** check (an admin action reachable without the right
    role) — the project's logic-bug sweet spot,
  - a dependency with a **known CVE** (exercises the SCA engine),
  - one **injection sink** (command/template) reachable from user input.
- Each planted bug documented in a private `SOLUTIONS.md` (kept out of the image)
  as **ground truth**, so the pipeline's output can be scored: did SAST find it, did
  the live attack CONFIRM it, were there false positives/negatives?

## Why it matters beyond testing

It doubles as the **evaluation harness**: with ground-truth labels, a run over the
guinea pig yields precision/recall for the analysis phase and a confirmed-vs-planted
count for the exploitation phase — the numbers the thesis writeup needs.

Later: add more stacks (Node, PHP) and more vuln classes as the pipeline widens.
