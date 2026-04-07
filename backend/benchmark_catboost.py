"""
Performance benchmark for CatBoost demand models.

Measures:
- Training time on full consumption records
- Inference time per item
- R² score validation
- Early stopping effectiveness
- Cross-validation performance
"""
import sys
import time
import json
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from database.db import SessionLocal, init_db
from database.models import ConsumptionRecord
from data.feature_engineering import load_consumption_df, build_demand_features
from models.catboost_model import (
    build_model as build_catboost_model,
    cross_validate_r2 as catboost_cv_r2,
)
from models.demand_model import train as train_baseline_models


def benchmark_models():
    """Run comprehensive benchmark for CatBoost demand model."""
    print("=" * 70)
    print("CATBOOST DEMAND MODEL - PERFORMANCE BENCHMARK")
    print("=" * 70)
    print(f"Timestamp: {datetime.now().isoformat()}\n")
    
    db = SessionLocal()
    try:
        # Check and prepare data
        record_count = db.query(ConsumptionRecord).count()
        if record_count < 5000:
            print(f"Database has only {record_count:,} records (need 5k+)")
            print("Using demo data for benchmark...\n")
        else:
            print(f"Using existing {record_count:,} consumption records\n")
        
        # === LOAD AND PREPARE DATA ===
        print("Step 1: Loading and engineering features...")
        load_start = time.time()
        
        df = load_consumption_df(db)
        features_df = build_demand_features(df)
        
        feature_cols = ['rolling_7d', 'rolling_30d', 'lag_7', 'lag_14', 'day_of_week', 
                       'month', 'velocity', 'stock_ratio', 'avg_lead_time_days', 'reliability_score']
        X = features_df[feature_cols].values
        y = features_df['quantity_used'].values
        
        # Remove NaN/inf
        mask = np.isfinite(X).all(axis=1) & np.isfinite(y)
        X = X[mask]
        y = y[mask]
        
        load_time = time.time() - load_start
        print(f"  ✓ Loaded {X.shape[0]:,} samples with {X.shape[1]} features")
        print(f"  ✓ Data loading time: {load_time:.2f}s\n")
        
        # === BASELINE COMPARISON ===
        print("Step 2: Baseline model (existing XGBoost)...")
        try:
            baseline_start = time.time()
            baseline_results = train_baseline_models(features_df)
            baseline_time = time.time() - baseline_start
            baseline_r2 = baseline_results.get('xgb', {}).get('r2') or baseline_results.get('lgbm', {}).get('r2', 0.0)
            baseline_mae = baseline_results.get('xgb', {}).get('mae') or baseline_results.get('lgbm', {}).get('mae')
            print(f"  ✓ Baseline R²: {baseline_r2:.4f}")
            if baseline_mae is not None:
                print(f"  ✓ Baseline MAE: {baseline_mae:.4f}")
            print(f"  ✓ Baseline training time: {baseline_time:.2f}s\n")
        except Exception as e:
            print(f"  ⚠ Baseline training skipped: {e}\n")
            baseline_r2 = None
            baseline_time = None
        
        # === CATBOOST CROSS-VALIDATION ===
        print("Step 3: CatBoost cross-validation (5-fold, with early stopping)...")
        catboost_cv_start = time.time()
        catboost_cv_scores = catboost_cv_r2(X, y, [], random_seed=42, folds=5)
        catboost_cv_time = time.time() - catboost_cv_start
        
        print(f"  ✓ CatBoost CV R² scores: {[f'{s:.4f}' for s in catboost_cv_scores]}")
        print(f"  ✓ Mean CV R²: {np.mean(catboost_cv_scores):.4f} (+/- {np.std(catboost_cv_scores):.4f})")
        print(f"  ✓ CV time: {catboost_cv_time:.2f}s\n")
        
        # === FULL MODEL TRAINING ===
        print("Step 4: Full CatBoost model training (with early stopping on validation split)...")

        # Hold out last 20% as a temporal validation set for early stopping
        split_idx = int(len(X) * 0.8)
        X_train_full, X_val_full = X[:split_idx], X[split_idx:]
        y_train_full, y_val_full = y[:split_idx], y[split_idx:]

        catboost_train_start = time.time()
        catboost_model = build_catboost_model(random_seed=42)
        catboost_model.fit(
            X_train_full,
            y_train_full,
            eval_set=[(X_val_full, y_val_full)],
            early_stopping_rounds=50,
            verbose=False,
        )
        catboost_train_time = time.time() - catboost_train_start
        catboost_r2 = catboost_model.score(X_val_full, y_val_full)
        best_iteration = catboost_model.get_best_iteration()

        print(f"  ✓ CatBoost training time: {catboost_train_time:.2f}s")
        print(f"  ✓ CatBoost best iteration: {best_iteration}")
        print(f"  ✓ CatBoost validation R²: {catboost_r2:.4f}\n")
        
        # === INFERENCE BENCHMARK ===
        print("Step 5: Inference time benchmark (1,000 iterations)...")
        
        sample = X[0:1]  # Single sample
        
        catboost_inf_times = []
        for _ in range(1000):
            inf_start = time.perf_counter()
            _ = catboost_model.predict(sample)
            inf_end = time.perf_counter()
            catboost_inf_times.append((inf_end - inf_start) * 1000)
        
        catboost_avg_inf = float(np.mean(catboost_inf_times))
        catboost_p95_inf = float(np.percentile(catboost_inf_times, 95))
        catboost_p99_inf = float(np.percentile(catboost_inf_times, 99))
        
        print(f"  ✓ CatBoost avg inference: {catboost_avg_inf:.2f}ms")
        print(f"  ✓ CatBoost P95 inference: {catboost_p95_inf:.2f}ms")
        print(f"  ✓ CatBoost P99 inference: {catboost_p99_inf:.2f}ms\n")
        
        # === MAE CALCULATION ===
        print("Step 6: Mean Absolute Error calculation...")
        predictions = catboost_model.predict(X_val_full)
        mae = np.mean(np.abs(predictions - y_val_full))
        print(f"  ✓ CatBoost MAE: {mae:.2f}\n")
        
        # === RESULTS SUMMARY ===
        print("=" * 70)
        print("PERFORMANCE SUMMARY")
        print("=" * 70)
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "data_samples": int(X.shape[0]),
            "features": int(X.shape[1]),
            "data_loading_time_sec": round(load_time, 4),
            
            "baseline": {
                "model": "LightGBM",
                "training_r2": round(float(baseline_r2), 4) if baseline_r2 else None,
                "training_time_sec": round(baseline_time, 4) if baseline_time else None,
            } if baseline_r2 else None,
            
            "catboost": {
                "cv_r2_mean": round(float(np.mean(catboost_cv_scores)), 4),
                "cv_r2_std": round(float(np.std(catboost_cv_scores)), 4),
                "cv_r2_scores": [round(float(s), 4) for s in catboost_cv_scores],
                "cv_time_sec": round(catboost_cv_time, 4),
                "training_time_sec": round(catboost_train_time, 4),
                "training_r2": round(catboost_r2, 4),
                "mae": round(mae, 4),
                "avg_inference_ms": round(catboost_avg_inf, 4),
                "p95_inference_ms": round(catboost_p95_inf, 4),
                "p99_inference_ms": round(catboost_p99_inf, 4),
                "early_stopping_enabled": True,
                "early_stopping_best_iteration": best_iteration,
            },
            
            "comparison_to_baseline": {
                "r2_improvement": round(catboost_r2 - float(baseline_r2), 4) if baseline_r2 else None,
                "catboost_better": bool(catboost_r2 > baseline_r2) if baseline_r2 else None,
            } if baseline_r2 else None,
            
            "acceptance_criteria": {
                "training_time_under_3min": bool(catboost_train_time < 180),
                "inference_time_under_50ms": bool(catboost_avg_inf < 50),
                "r2_score_above_0_96": bool(catboost_r2 >= 0.96),
                "mae_under_7": bool(mae < 7),
            }
        }
        
        # Pretty print results
        print(f"{'Metric':<30} {'Value':<15} {'Target':<15}")
        print("-" * 70)
        print(f"{'CV R² (mean)':<30} {results['catboost']['cv_r2_mean']:<15} ≥0.96")
        print(f"{'Training R²':<30} {results['catboost']['training_r2']:<15} ≥0.96")
        print(f"{'MAE':<30} {results['catboost']['mae']:<15} <7.0")
        print(f"{'Training Time':<30} {results['catboost']['training_time_sec']}s{'':<10} <180s")
        print(f"{'Avg Inference':<30} {results['catboost']['avg_inference_ms']:.2f}ms{'':<8} <50ms")
        
        if baseline_r2:
            print(f"{'Improvement vs baseline':<30} {results['comparison_to_baseline']['r2_improvement']:<15}")
        
        print("\n" + "=" * 70)
        print("CATBOOST ACCEPTANCE CRITERIA")
        print("=" * 70)
        criteria_pass = []
        criteria_pass.append(results['acceptance_criteria']['training_time_under_3min'])
        criteria_pass.append(results['acceptance_criteria']['inference_time_under_50ms'])
        criteria_pass.append(results['acceptance_criteria']['r2_score_above_0_96'])
        criteria_pass.append(results['acceptance_criteria']['mae_under_7'])
        
        print(f"Training time <3 min: {'✓ PASS' if results['acceptance_criteria']['training_time_under_3min'] else '✗ FAIL'} ({results['catboost']['training_time_sec']}s)")
        print(f"Inference <50ms: {'✓ PASS' if results['acceptance_criteria']['inference_time_under_50ms'] else '✗ FAIL'} ({results['catboost']['avg_inference_ms']:.2f}ms)")
        print(f"R² score ≥0.96: {'✓ PASS' if results['acceptance_criteria']['r2_score_above_0_96'] else '✗ FAIL'} ({results['catboost']['training_r2']})")
        print(f"MAE <7: {'✓ PASS' if results['acceptance_criteria']['mae_under_7'] else '✗ FAIL'} ({results['catboost']['mae']})")
        
        all_pass = all(criteria_pass)
        print(f"\n{'='*70}")
        if all_pass:
            print("✓ ALL CRITERIA PASSED")
        else:
            print(f"⚠ {sum(criteria_pass)}/4 criteria passed")
        print(f"{'='*70}")
        # Save results
        results_file = Path(__file__).parent / "benchmark_results_catboost.json"
        with open(results_file, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\n✓ Results saved to: {results_file}")

        return results

    finally:
        db.close()


if __name__ == "__main__":
    benchmark_models()
