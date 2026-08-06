# Guinea pig — GROUND TRUTH (do NOT ingest)

> ⚠️ This file is the answer key for the eval. It must **never** be fed to the
> pipeline. It lives in `guinea_pig/`, one level **above** the submitted target
> (`guinea_pig/target/`), precisely so the analysis phase cannot read it. Keep it
> out of any archive/zip you hand to `ingest`.

The target is `guinea_pig/target/` — a small Flask "shop" API. It contains **4
planted weakness classes** (one per pipeline capability) plus deliberate
**true-negatives** so false positives can be scored. Nothing in `target/` hints at
any of this; the bugs are in behavior, not comments.

Seeded data: users `alice/alice123` (role `user`), `bob/bobpass` (role `user`),
`admin/s3cr3t-admin-pw` (role `admin`); a planted secret in table `secrets`:
`aws_access_key_id = AKIAIOSFODNN7EXAMPLE` (matches the engine's `SECRET_PATTERNS`).

## Planted vulnerabilities

| ID | Class | CWE | Location (`target/app.py`) | Reachable as | Exercises |
|----|-------|-----|----------------------------|--------------|-----------|
| V1 | SQL injection | CWE-89 | `search()` — `/search` | unauthenticated | SAST (raw SQL sink) + exploit (`blind_sqli_extractor` / sqlmap) |
| V2 | Broken access control (authN present, authZ missing) | CWE-862 | `admin_export()` — `/admin/export` | any logged-in user (e.g. alice) | SAST (missing role guard) + exploit (reach admin data as non-admin) |
| V3 | OS command injection | CWE-78 | `diag_ping()` — `/diag/ping` | unauthenticated | SAST (`shell=True` sink) + exploit (`; id`) |
| V4 | Vulnerable dependencies | CWE-1104 | `target/requirements.txt` | n/a (composition) | SCA engine (osv-scanner / trivy) |

### V1 — SQL injection (`/search`)
`search()` builds SQL by string concatenation:
`"... WHERE name LIKE '%" + q + "%'"`. User input `q` reaches the query unsanitized.
- **Validate (UNION exfil of credentials):**
  ```bash
  curl -s http://TARGET:8000/search --get \
    --data-urlencode "q=%' UNION SELECT id, username || ':' || password, role FROM users -- "
  ```
  **Expected:** results include `alice:alice123` and `admin:s3cr3t-admin-pw` — data
  from `users`, not `products`. Boolean-blind extraction of the `secrets` table is
  also possible (this is the intended path for `blind_sqli_extractor`).
- **CONFIRMED** iff a value from `users`/`secrets` (e.g. `AKIAIOSFODNN7EXAMPLE`) is
  read out through this endpoint.

### V2 — Broken access control (`/admin/export`)
`admin_export()` checks that a session exists (`"user_id" not in session`) but
**never checks `role == "admin"`**. Any authenticated user can dump all users
(with passwords) and the `secrets` table.
- **Validate (as non-admin alice):**
  ```bash
  curl -s -c cj http://TARGET:8000/login --data "username=alice&password=alice123"
  curl -s -b cj http://TARGET:8000/admin/export
  ```
  **Expected:** JSON containing every user row and `AKIAIOSFODNN7EXAMPLE`, returned
  to a `user`-role account.
- **CONFIRMED** iff admin-only data is returned to a non-admin session.
- Note for SAST: the missing check is a *privileged-action / guard-site* omission —
  the project's target bug class. `login()` next to it is safe, so flagging *it*
  would be a false positive.

### V3 — OS command injection (`/diag/ping`)
`diag_ping()` runs `subprocess.check_output("ping -c 1 " + host, shell=True)`.
`host` is attacker-controlled and reaches a shell.
- **Validate (Linux target):**
  ```bash
  curl -s http://TARGET:8000/diag/ping --get --data-urlencode "host=127.0.0.1; id"
  ```
  **Expected:** response body contains `uid=...` from the injected `id`.
- **CONFIRMED** iff injected command output appears in the response.
- ⚠️ Runtime proof requires a **Linux** target (the payload and `ping -c 1` are
  POSIX). It is code-evident anywhere but only *demonstrable* once the container is
  running (Phase 2 sandbox / Docker), not on a Windows host.

### V4 — Vulnerable dependencies (`requirements.txt`)
Pinned to outdated releases with published CVEs. The **authoritative** list is
whatever `osv-scanner`/`trivy` reports on this file; representative known issues:

| Package | Pinned | Representative CVE |
|---------|--------|--------------------|
| Werkzeug | 2.0.3 | CVE-2023-25577 (DoS), CVE-2023-23934 (cookie) |
| Jinja2 | 3.0.3 | CVE-2024-22195 (SSTI via `xmlattr`) |
| PyYAML | 5.3.1 | CVE-2020-14343 (arbitrary code exec via unsafe load) |
| requests | 2.25.1 | CVE-2023-32681 (proxy-auth leak) |
| (urllib3, pulled by requests) | 1.26.x | multiple, fixed in ≥1.26.18 |

- **CONFIRMED** by SCA producing findings for these packages. Note: the app uses
  `yaml.safe_load` (safe), so PyYAML is a *composition* finding, not a code sink —
  a good test that SCA and SAST stay in their lanes.

## Intentional true-negatives (flagging these = false positive)
- `login()` uses a **parameterized** query — NOT injectable.
- `yaml.safe_load` in `load_config()` — NOT the unsafe `yaml.load`.
- The `secrets`/`config.yaml` values are seeded test data, not a code weakness in
  themselves.

## Scoring
Precision/recall for a run over `target/`:
- **SAST/analysis:** true positives = {V1, V2, V3} correctly located; false
  positives = anything flagged that isn't planted (esp. the true-negatives above);
  false negatives = any of V1–V3 missed. (V4 is SCA's, not SAST's.)
- **SCA:** true positives = the vulnerable packages above.
- **Exploitation:** count how many of V1–V3 reach `CONFIRMED` with evidence, and
  whether any planted item is wrongly `REFUTED` (false negative) or a non-issue is
  wrongly `CONFIRMED` (false positive).

Record each run's numbers in `docs/PROGRESS.md` as later phases come online.
