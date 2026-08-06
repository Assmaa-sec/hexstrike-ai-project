# pentrai_pipeline

The productized pipeline over the PentrAI engine: **codebase in → validated attack
report out.** See [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md) for the design
and [`../docs/THREAT_MODEL.md`](../docs/THREAT_MODEL.md) for the containment model.

## Status

Scaffold. The contracts (`contracts.py`), the orchestrator, config, the job model,
and the CLI are wired and import cleanly. Every **stage** and **agent** is a stub
that raises `NotImplementedError` with its own dotted name, so a run tells you
exactly which piece to build next.

**Contributing / where things stand:** [`../docs/PROGRESS.md`](../docs/PROGRESS.md)
is the shared build tracker — the phase table, how to build the next phase, and how
to document a finished one. Read it before starting work.

## Layout

```
pentrai_pipeline/
  contracts.py      typed artifacts passed between stages (the backbone)
  config.py         env-driven settings (PentrAI server, LLM, sandbox, budgets)
  orchestrator.py   the stage sequence + guaranteed sandbox teardown
  cli.py            run a job from the terminal
  stages/           ingest, sandbox, recon, analyze_sca, analyze_sast,
                    synthesize, exploit, report
  agents/           llm client + analyst (phase 1) + operator (phase 2)
  tools/            pentrai_client — the bridge to the 150-tool engine
  jobs/             Job model the future web layer will poll
```

## Run (once stages are implemented)

```bash
python -m pentrai_pipeline ./path/to/repo --authorized
python -m pentrai_pipeline https://github.com/acme/app.git --authorized --scope "acme staging clone"
python -m pentrai_pipeline ./app --authorized --posture authenticated --secrets ./creds.env
```

`--authorized` is required (you attest you may test this code). `--posture
authenticated` needs `--secrets`; without it the run is `external`.

## Config (environment)

| Var | Default | Meaning |
|---|---|---|
| `PENTRAI_SERVER_URL` | `http://127.0.0.1:8888` | the existing PentrAI tool server |
| `PENTRAI_LLM_BASE_URL` | `http://127.0.0.1:8889/v1` | OpenAI-compatible LLM (defaults to `llm_proxy`) |
| `PENTRAI_LLM_MODEL` | `deepseek-chat` | model id |
| `PENTRAI_LLM_API_KEY` | — | key for the LLM endpoint |
| `PENTRAI_SCA_TOOL` | `osv-scanner` | dependency CVE scanner |
| `PENTRAI_WORK_DIR` | `./.pentrai_runs` | working copies, logs, artifacts |

## Note

This package never modifies `pentrai_server.py` / `pentrai_mcp.py`; it only calls
the engine through `tools/pentrai_client.py`.
