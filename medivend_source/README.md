# MediVend — Smart Pharmacy Platform
### Full Source Code

```
medivend/
├── frontend/
│   └── index.html              ← Full web app (single-file, no build needed)
├── backend/
│   ├── main.py                 ← FastAPI server
│   ├── routes/
│   │   ├── auth.py             ← Login / register
│   │   ├── prescriptions.py    ← Queue management
│   │   ├── inventory.py        ← Stock CRUD
│   │   ├── predictions.py      ← ML forecast API
│   │   └── analytics.py        ← Revenue & audit
│   ├── models.py               ← Pydantic schemas
│   └── supabase_client.py      ← DB connection
├── ml_model/
│   ├── forecast_model.py       ← Seasonal regression forecaster
│   ├── train.py                ← Training pipeline
│   └── requirements.txt
├── scraper/
│   ├── drug_scraper.py         ← Main scraper (SFDA + OpenFDA)
│   ├── sales_simulator.py      ← Augment scraped data with trends
│   └── requirements.txt
└── database/
    └── schema.sql              ← Supabase table definitions
```

## Quick Start

### 1. Frontend
Open `frontend/index.html` directly in browser — no server needed.

### 2. Backend API
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 3. ML Model
```bash
cd ml_model
pip install -r requirements.txt
python train.py
```

### 4. Scraper
```bash
cd scraper
pip install -r requirements.txt
python drug_scraper.py          # scrape drug data
python sales_simulator.py       # generate sales from scraped data
```

## Environment Variables (.env)
```
SUPABASE_URL=https://hdpbzflntprxnctucyfp.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_KEY=your_service_role_key_here
```
