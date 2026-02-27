# AHIMP – Python ML Backend

FastAPI service providing real ML-powered predictions for the AHIMP hospital inventory system.

## Tech Stack
| Component | Technology |
|-----------|------------|
| API Framework | FastAPI + Uvicorn |
| Database | SQLite (dev) / PostgreSQL (prod) |
| ORM | SQLAlchemy |
| Demand Forecast | **XGBoost** + Linear Regression + ARIMA |
| Stockout Risk | **Random Forest** Classifier |
| Expiry Risk | **Logistic Regression** |

## Quick Start

```bash
# Navigate to backend
cd backend

# Create + activate virtualenv (recommended)
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Start the server
uvicorn main:app --reload --port 8000
```

On first boot the server will automatically:
1. Create the SQLite database (`ahimp.db`)
2. Seed all 14 tables with synthetic data (~2 years of daily consumption)
3. Train all 3 ML models (takes ~30–60 seconds)
4. Serve the API at **http://localhost:8000**

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/demand-items` | List items for dropdown |
| GET | `/api/demand-forecast?item_id=<n>` | 14-day XGBoost demand forecast |
| GET | `/api/stockout-risk` | Random Forest stockout probability for all items |
| GET | `/api/expiry-risk` | Logistic Regression expiry risk + ROC curve |
| GET | `/api/cost-savings` | Estimated savings from ML-driven decisions |
| GET | `/api/model-overview` | All metrics + SHAP feature importance + pipeline |

Interactive docs: **http://localhost:8000/docs**

## Folder Structure

```
backend/
├── main.py                  ← FastAPI app (auto-trains on startup)
├── config.py                ← Settings (DB URL, CORS, ML params)
├── requirements.txt
│
├── database/
│   ├── schema.sql           ← Full 14-table DDL
│   ├── db.py                ← SQLAlchemy engine + session
│   ├── models.py            ← ORM models
│   └── seed.py              ← Synthetic data generator
│
├── data/
│   └── feature_engineering.py  ← Rolling avg, lag, seasonality features
│
├── models/
│   ├── demand_model.py      ← XGBoost + LR + ARIMA
│   ├── stockout_model.py    ← Random Forest
│   ├── expiry_model.py      ← Logistic Regression
│   └── pkl/                 ← Saved .pkl model files (auto-created)
│
└── api/
    ├── demand.py
    ├── stockout.py
    ├── expiry.py
    ├── cost_savings.py
    └── overview.py
```

## Running with PostgreSQL

Set the `DATABASE_URL` environment variable before starting:

```bash
set DATABASE_URL=postgresql://user:password@localhost/ahimp
uvicorn main:app --reload --port 8000
```

## Next.js Integration

The frontend (port 3000) calls this backend automatically.
If the backend is offline, the frontend shows an offline banner — it never crashes.
