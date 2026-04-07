"""
FastAPI main entrypoint for the AHIMP ML backend.

Startup sequence:
  1. Create DB tables
  2. Seed data (idempotent)
  3. Train all three ML models (if pkl/ is empty)
  4. Start API server
"""
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import CORS_ORIGINS
from database.db import init_db, SessionLocal
from database.seed import seed as seed_db
from data.feature_engineering import (
    load_consumption_df,
    build_demand_features,
    build_stockout_features,
    build_expiry_features,
)
from models import demand_model, stockout_model, expiry_model, anomaly_detector
from api import demand, stockout, expiry, cost_savings, overview, anomalies

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ahimp")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🔧 Initialising database …")
    init_db()

    db = SessionLocal()
    try:
        seed_db(db)
    finally:
        db.close()

    logger.info("🤖 Training ML models …")
    db = SessionLocal()
    try:
        raw_df        = load_consumption_df(db)
        demand_feat   = build_demand_features(raw_df)
        # Attach item_name for inference
        name_map = raw_df.groupby("item_id")["item_name"].first()
        demand_feat["item_name"] = demand_feat["item_id"].map(name_map)

        stockout_feat = build_stockout_features(raw_df)
        stockout_feat["item_name"] = stockout_feat["item_id"].map(name_map)

        expiry_feat   = build_expiry_features(raw_df)
        if not expiry_feat.empty:
            expiry_feat["item_name"] = expiry_feat["item_id"].map(name_map)

        if not demand_model.is_trained():
            demand_model.train(demand_feat)
        else:
            logger.info("  ✅ Demand model already trained (loaded from pkl)")

        if not stockout_model.is_trained():
            stockout_model.train(stockout_feat)
        else:
            logger.info("  ✅ Stockout model already trained")

        if not expiry_model.is_trained() and not expiry_feat.empty:
            expiry_model.train(expiry_feat)
        else:
            logger.info("  ✅ Expiry model already trained")

        if not anomaly_detector.is_trained():
            anomaly_detector.train(raw_df)
        else:
            logger.info("  ✅ Anomaly detector already trained")

    except Exception as e:
        logger.error(f"Training failed: {e}", exc_info=True)
    finally:
        db.close()

    logger.info("🚀 AHIMP ML backend ready at http://localhost:8000")
    yield
    logger.info("Shutting down …")


app = FastAPI(
    title="AHIMP – AI Predictive Inventory Backend",
    description="FastAPI ML service for hospital inventory demand forecasting, stockout risk, and expiry risk.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(demand.router,       prefix="/api", tags=["Demand Forecast"])
app.include_router(stockout.router,     prefix="/api", tags=["Stockout Risk"])
app.include_router(expiry.router,       prefix="/api", tags=["Expiry Risk"])
app.include_router(cost_savings.router, prefix="/api", tags=["Cost Savings"])
app.include_router(overview.router,     prefix="/api", tags=["Model Overview"])
app.include_router(anomalies.router,    prefix="/api", tags=["Anomaly Detection"])


@app.get("/api/health", tags=["Health"])
def health():
    return {"status": "ok", "service": "AHIMP ML Backend", "version": "1.0.0"}
