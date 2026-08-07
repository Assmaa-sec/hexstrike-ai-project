# guinea_pig

The deliberately-vulnerable target the pipeline is built and evaluated against.
It gives every later stage something real to run on, and — with its ground-truth
key — doubles as the **precision/recall eval harness**.

## Layout

```
guinea_pig/
  README.md        this file            (eval harness — NOT ingested)
  SOLUTIONS.md     ground-truth answer key (NOT ingested)
  target/          <-- THIS is what you submit to the pipeline
    app.py             Flask "shop" API with the planted weaknesses
    requirements.txt   pinned to known-CVE versions (feeds SCA)
    config.json        app config (loaded safely)
    Dockerfile         satisfies the ingest contract (recipe required)
    docker-compose.yml single-service bring-up
    .dockerignore
```

**Eval integrity — two hard rules:**
1. Submit **`target/` only**. `SOLUTIONS.md` and this `README.md` sit one level up
   and must never reach `ingest`, or the analysis phase reads the answers.
2. **No hints inside `target/`.** The code looks like an ordinary app; the mapping
   from bug → location lives solely in `SOLUTIONS.md`.

## What's planted (summary; details + validation in `SOLUTIONS.md`)

| ID | Class | CWE | Engine it exercises |
|----|-------|-----|---------------------|
| V1 | SQL injection (`/search`) | CWE-89 | SAST + exploit |
| V2 | Broken access control (`/admin/export`) | CWE-862 | SAST + exploit |
| V3 | OS command injection (`/diag/ping`) | CWE-78 | SAST + exploit |
| V4 | Vulnerable dependencies | CWE-1104 | SCA |

Plus deliberate true-negatives (a parameterized `login()`, stdlib `json` config
parsing) so false positives can be measured.

## Run it directly (sanity check, outside the pipeline)

```bash
docker compose -f guinea_pig/target/docker-compose.yml up --build
```

Then the target is on `http://localhost:8000`. Quick liveness + one exploit:

```bash
curl -s http://localhost:8000/ ; echo
curl -s http://localhost:8000/search --get --data-urlencode "q=%' UNION SELECT id, username || ':' || password, role FROM users -- "
```

Local (no Docker) also works for the OS-independent bugs (V1/V2): `pip install
flask` then `python guinea_pig/target/app.py`. V3 (command injection) only
demonstrates on a Linux target (i.e. in the container).

## Next stacks (later)

Add Node/PHP variants and more classes (SSTI, insecure deserialization, IDOR) as
the pipeline widens beyond the first web-app vertical.
