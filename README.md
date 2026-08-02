# dashboard-for-devs

Streamlit **ops / developer** harness for IntoTheOpen.

This is **not** the product frontend (Ade’s app). It is the internal dashboard for
corpus pipeline, validation, feedback loop, evaluation cycle, and agentic ops.

Backend logic lives in [`intotheopen/intotheopen-backend`](https://github.com/intotheopen/intotheopen-backend).
This repo only contains the Streamlit UI and imports backend Python packages.

## Setup (sibling checkouts)

```bash
# From a shared parent directory:
git clone https://github.com/intotheopen/intotheopen-backend.git
git clone https://github.com/intotheopen/dashboard-for-devs.git

cd intotheopen-backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
pip install -r requirements.txt   # if not already covered by editable extras

cd ../dashboard-for-devs
# Prefer the same venv that has the backend installed:
source ../intotheopen-backend/.venv/bin/activate
pip install -r requirements.txt
```

Copy env from the backend (secrets and `DATABASE_URL` stay there):

```bash
# Option A: symlink
ln -s ../intotheopen-backend/.env .env

# Option B: point loaders at the backend checkout (default path helpers
# resolve data/.env from the *backend* package location once installed).
```

**Shared data (required):** all runtime artefacts live in the backend
`data/` tree — raw scrapes, analysed JSONL/CSV, embeddings `.npy`,
validation, telemetry, etc. This repo must **not** keep its own copy.

```bash
./scripts/ensure-shared-data.sh
# creates: dashboard-for-devs/data -> ../<backend>/data
```

`run-dashboard.sh` / `keep-dashboard-alive.sh` call that helper on start.
Backend writers (`save_embeddings`, stores, etc.) resolve paths from the
backend package root via `config.paths.resolve_data_path`, so Streamlit’s
cwd cannot split files into a second tree again.

Start Postgres via the backend compose stack if needed:

```bash
cd ../intotheopen-backend
docker compose up -d db
```

## Run

```bash
cd dashboard-for-devs
source ../intotheopen-backend/.venv/bin/activate
streamlit run dashboard/app.py
# or:
./scripts/run-dashboard.sh
```

Open http://localhost:8501

## How dependency works

Pages import backend modules directly (`agents`, `processors`, `storage`,
`feedback`, `phase_10`, …). Install the backend editable (`pip install -e .`)
so those imports resolve. `dashboard/app.py` also adds a sibling
`intotheopen-backend` / `ITO-RND` checkout to `sys.path` as a fallback.

Data files, `.env`, and Docker Compose remain owned by the **backend** repo
(`config.paths.PROJECT_ROOT` points at the backend package root). Symlink
this repo’s `data/` to that backend tree with `./scripts/ensure-shared-data.sh`
(also run automatically by the start scripts).

## Tests (UI helpers only)

```bash
pytest tests/ -q
```

## Product API (for Ade)

HTTP / OpenAPI for the product frontend stays on the backend:

- http://localhost:8000/docs

This Streamlit app is not a full HTTP client for every ops page yet.
