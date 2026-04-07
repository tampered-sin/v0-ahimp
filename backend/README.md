# AHIMP – Python ML Backend

FastAPI service providing real ML-powered predictions for the AHIMP hospital inventory system.

## Tech Stack
| Component | Technology |
|-----------|------------|
| API Framework | FastAPI + Uvicorn |
| Database | PostgreSQL 15 (Docker) / SQLite (dev) |
| ORM | SQLAlchemy |
| Demand Forecast | **XGBoost** + Linear Regression + ARIMA |
| Stockout Risk | **Random Forest** Classifier |
| Expiry Risk | **Logistic Regression** |

## Quick Start with Docker (Recommended)

```bash
# From project root (where docker-compose.yml is)
docker-compose up --build

# First boot will:
# 1. Start PostgreSQL container
# 2. Create database & tables
# 3. Seed 20 years of daily consumption (~7.3M records)
# 4. Train ML models (5-10 minutes for large dataset)
# 5. Serve API at http://localhost:8000

# Check logs:
docker-compose logs -f backend
```

## Quick Start without Docker (SQLite - Dev Only)

```bash
# Navigate to backend
cd backend

# Create + activate virtualenv (recommended)
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Start the server (uses SQLite ahimp.db locally)
uvicorn main:app --reload --port 8000
```

On first boot the server will automatically:
1. Create the SQLite database (`ahimp.db`)
2. Seed all 14 tables with synthetic data (~20 years of daily consumption)
3. Train all 3 ML models (takes ~5-10 minutes for 7.3M records)
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

The default setup now uses PostgreSQL via Docker. To use PostgreSQL without Docker:

```bash
# Set PostgreSQL connection string
set DATABASE_URL=postgresql://user:password@localhost:5432/ahimp
uvicorn main:app --reload --port 8000
```

## Docker Operations

```bash
# Start services
docker-compose up

# Start in background
docker-compose up -d

# View logs
docker-compose logs -f backend
docker-compose logs -f postgres

# Stop services
docker-compose down

# Stop and remove volumes (resets database)
docker-compose down -v

# Rebuild images
docker-compose up --build
```

## Environment Variables

Configure via `.env` file or `docker-compose.yml`:

```bash
# PostgreSQL credentials
POSTGRES_DB=ahimp
POSTGRES_USER=ahimp_user
POSTGRES_PASSWORD=ahimp_secure_password_2024

# Database URL (auto-set in Docker)
DATABASE_URL=postgresql://ahimp_user:ahimp_secure_password_2024@postgres:5432/ahimp
```

## Fallback to SQLite (Development Only)

To use SQLite instead of PostgreSQL:

```bash
export DATABASE_URL=sqlite:///ahimp.db
uvicorn main:app --reload --port 8000
```

**Note**: SQLite is not recommended for production or large datasets (>500K records). Use PostgreSQL + Docker for best performance.

## Data Generation & Scale

### Synthetic Data Statistics

The seeder generates **20 years** of realistic hospital inventory data:

```
Timeframe:         20 years (7,300 days)
Inventory Items:   28 items (medicines, equipment, PPE, blood)
Consumption Recs:  ~7.3 Million records (28 items × 365 days × 20 years)
Departments:       6 (Pharmacy, Surgery, Emergency, ICU, Pediatrics, Lab)
Suppliers:         8 (with lead times & reliability scores)
Equipment Usage:   ~360 records (4 equipment × 90 days)

Database Size:     ~500-800 MB (PostgreSQL optimized)
Feature Matrix:    ~380K rows × 10 features (after aggregation)
```

### Performance Notes

**First Boot Times** (with 20-year data):
- Data seeding: 2-3 minutes
- ML model training: 5-7 minutes (XGBoost on 7.3M records)
- Total startup: ~10 minutes
- Subsequent boots: <5 seconds (pkl caching)

**Query Performance** (PostgreSQL):
- Demand forecasting: <100ms per item
- Stockout risk analysis: <200ms (all items)
- Expiry risk detection: <150ms (all batches)

### Data Seasonality

Generated consumption includes realistic patterns:
- **Weekly**: Peak demand mid-week, lower weekends
- **Seasonal**: Higher in winter months (flu season analogy)
- **Noise**: ±8% Gaussian variation per day
- **Trends**: Item-specific baseline demand rates

## Next.js Integration

The frontend (port 3000) calls this backend automatically.
If the backend is offline, the frontend shows an offline banner — it never crashes.
