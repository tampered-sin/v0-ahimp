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
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import CORS_ORIGINS
from config import PKL_DIR
from database.db import init_db, SessionLocal
from database.seed import seed as seed_db
from data.feature_engineering import (
    load_consumption_df,
    build_demand_features,
    build_stockout_features,
    build_expiry_features,
)
from models import demand_model, stockout_model, expiry_model, anomaly_detector
from api import (
    demand,
    stockout,
    expiry,
    cost_savings,
    overview,
    anomalies,
    consumption,
    ensemble,
    alerts,
    explain,
    agents,
    suppliers,
    supply_chain,
    purchase_orders,
    deliveries,
    approval_queue,
    inventory,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ahimp")


def _startup_models_ready() -> bool:
    required_artifacts = [
        PKL_DIR / "demand_lgbm.pkl",
        PKL_DIR / "demand_meta.pkl",
        PKL_DIR / "stockout_rf.pkl",
        PKL_DIR / "stockout_meta.pkl",
        PKL_DIR / "expiry_lr.pkl",
        PKL_DIR / "expiry_scaler.pkl",
        PKL_DIR / "expiry_meta.pkl",
        PKL_DIR / "anomaly_iforest.pkl",
        PKL_DIR / "anomaly_meta.pkl",
        PKL_DIR / "demand_lstm.h5",
        PKL_DIR / "demand_lstm_meta.pkl",
        PKL_DIR / "demand_lstm_scaler.pkl",
        PKL_DIR / "demand_lstm_y_scaler.pkl",
    ]
    return all(path.exists() and path.stat().st_size > 0 for path in required_artifacts)


def _log_stage(step: int, total: int, message: str) -> None:
    logger.info("  [%d/%d] %s", step, total, message)


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
    if _startup_models_ready():
        logger.info("  ✅ Model artifacts already present; skipping startup feature build and training")
    else:
        db = SessionLocal()
        try:
            total_steps = 6
            raw_df        = load_consumption_df(db)
            _log_stage(1, total_steps, f"Loaded {len(raw_df):,} consumption rows")

            _log_stage(2, total_steps, "Building demand, stockout, and expiry feature sets")
            demand_feat   = build_demand_features(raw_df)
            # Attach item_name for inference
            name_map = raw_df.groupby("item_id")["item_name"].first()
            demand_feat["item_name"] = demand_feat["item_id"].map(name_map)

            stockout_feat = build_stockout_features(raw_df)
            stockout_feat["item_name"] = stockout_feat["item_id"].map(name_map)

            expiry_feat   = build_expiry_features(raw_df)
            if not expiry_feat.empty:
                expiry_feat["item_name"] = expiry_feat["item_id"].map(name_map)

            _log_stage(3, total_steps, "Training demand model stack")
            if not demand_model.is_trained():
                stage_start = time.perf_counter()
                demand_model.train(demand_feat)
                logger.info("  [3/%d] Demand model stack finished in %.1fs", total_steps, time.perf_counter() - stage_start)
            else:
                logger.info("  ✅ Demand model already trained (loaded from pkl)")

            _log_stage(4, total_steps, "Training LSTM recurrent model")
            try:
                from models import lstm_model

                if not lstm_model.is_trained(model_type="lstm"):
                    stage_start = time.perf_counter()
                    lstm_model.train(
                        demand_feat,
                        model_type="lstm",
                        epochs=10,
                        batch_size=128,
                        verbose=1,
                    )
                    logger.info("  [4/%d] LSTM model finished in %.1fs", total_steps, time.perf_counter() - stage_start)
                else:
                    logger.info("  ✅ LSTM model already trained")
            except Exception as exc:
                logger.warning("  ⚠️ LSTM training skipped: %s", exc)

            _log_stage(5, total_steps, "Training stockout and expiry risk models")
            if not stockout_model.is_trained():
                stage_start = time.perf_counter()
                stockout_model.train(stockout_feat)
                logger.info("  [5/%d] Stockout model finished in %.1fs", total_steps, time.perf_counter() - stage_start)
            else:
                logger.info("  ✅ Stockout model already trained")

            if not expiry_model.is_trained() and not expiry_feat.empty:
                stage_start = time.perf_counter()
                expiry_model.train(expiry_feat)
                logger.info("  [5/%d] Expiry model finished in %.1fs", total_steps, time.perf_counter() - stage_start)
            else:
                logger.info("  ✅ Expiry model already trained")

            _log_stage(6, total_steps, "Training anomaly detector")
            if not anomaly_detector.is_trained():
                stage_start = time.perf_counter()
                anomaly_detector.train(raw_df)
                logger.info("  [6/%d] Anomaly detector finished in %.1fs", total_steps, time.perf_counter() - stage_start)
            else:
                logger.info("  ✅ Anomaly detector already trained")

        except Exception as e:
            logger.error(f"Training failed: {e}", exc_info=True)
        finally:
            db.close()

    logger.info("🚀 AHIMP ML backend ready at http://localhost:9000")
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
app.include_router(consumption.router,  prefix="/api", tags=["Consumption Ingestion"])
app.include_router(ensemble.router,     prefix="/api", tags=["Ensemble Forecast"])
app.include_router(alerts.router,       prefix="/api", tags=["Alerts"])
app.include_router(explain.router,      prefix="/api", tags=["Explainability"])
app.include_router(agents.router,       prefix="/api", tags=["AI Agents"])
app.include_router(suppliers.router,    prefix="/api", tags=["Suppliers"])
app.include_router(supply_chain.router, prefix="/api", tags=["Supply Chain Agent"])
app.include_router(purchase_orders.router, prefix="/api", tags=["Purchase Orders"])
app.include_router(deliveries.router, prefix="/api", tags=["Delivery Tracking"])
app.include_router(approval_queue.router, prefix="/api", tags=["Approval Queue"])
app.include_router(inventory.router, prefix="/api", tags=["Inventory"])


@app.get("/api/health", tags=["Health"])
def health():
    return {"status": "ok", "service": "AHIMP ML Backend", "version": "1.0.0"}
