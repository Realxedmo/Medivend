# MediVend Local Running Guide

This guide uses a local Python virtual environment and works on macOS.

## 1) Open the project

```bash
cd /Users/mohamed/Documents/Adam_project/medivend3/files-2
```

## 2) Create and activate virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

## 3) Install all dependencies

```bash
pip install -r medivend_source/backend/requirements.txt
pip install -r medivend_source/ml_model/requirements.txt
pip install -r medivend_source/scraper/requirements.txt
```

## 4) Run backend API (FastAPI)

```bash
uvicorn main:app --app-dir medivend_source/backend --host 127.0.0.1 --port 8000 --reload
```

- API docs: `http://127.0.0.1:8000/docs`
- If port `8000` is already in use, run on a different port:

```bash
uvicorn main:app --app-dir medivend_source/backend --host 127.0.0.1 --port 8001 --reload
```

## 5) Open the full web app (single URL)

The backend now serves the frontend from the same server.

- Web app: `http://127.0.0.1:8000/`
- API docs: `http://127.0.0.1:8000/docs`
- API status JSON: `http://127.0.0.1:8000/api`

## One-command startup

From repository root:

```bash
./start_medivend.sh
```

DB/API health check:

```bash
./check_medivend_db.sh
```

## 6) Optional data/model utilities

### Train ML model

```bash
python medivend_source/ml_model/train.py
```

### Run scraper

```bash
python medivend_source/scraper/drug_scraper.py
python medivend_source/scraper/sales_simulator.py
```

## 7) Environment variables

Create `medivend_source/backend/.env` if you want live Supabase mode:

```env
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key
SUPABASE_SERVICE_KEY=your_supabase_service_key
```

Without valid Supabase keys, use Demo Mode in the UI.

## Troubleshooting

- If installs fail with Python compatibility issues, make sure you are using this project's `.venv`.
- If backend does not start, check whether another process is already using the selected port.
- If frontend appears cached, hard refresh your browser.
