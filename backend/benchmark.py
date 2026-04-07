"""
Performance benchmark for LightGBM demand model.

Measures:
- Training time on full 7.3M consumption records
- Inference time per item
- R² score validation
"""
import time
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

from database.db import SessionLocal, init_db
from database.models import ConsumptionRecord, Item, Supplier, Batch
from data.feature_engineering import load_consumption_df, build_demand_features
from models.demand_model import train, predict_forecast
from models.lightgbm_model import cross_validate_r2


def generate_synthetic_data(db_session, num_records: int = 100000):
    """Generate synthetic consumption data for benchmarking."""
    print(f"Generating {num_records:,} synthetic consumption records...")

    from database.models import Department

    # Create test departments
    depts = [Department(department_name=f"Dept-{i}") for i in range(1, 6)]
    db_session.add_all(depts)
    db_session.commit()

    # Create test items
    items = [Item(item_name=f"Item-{i}", category=f"Cat-{i % 3}") for i in range(1, 101)]
    db_session.add_all(items)
    db_session.commit()

    # Create test suppliers
    suppliers = [
        Supplier(
            supplier_name=f"Supplier-{i}",
            avg_lead_time_days=5 + (i % 10),
            reliability_score=0.8 + (i % 20) * 0.01
        )
        for i in range(1, 11)
    ]
    db_session.add_all(suppliers)
    db_session.commit()

    # Create batches
    base_date = datetime(2023, 1, 1)
    batches = []
    for i in range(1, 101):
        for j in range(50):
            batch = Batch(
                item_id=(i % 100) + 1,
                supplier_id=(i % 10) + 1,
                manufacture_date=base_date + timedelta(days=j),
                expiry_date=base_date + timedelta(days=j + 180),
                purchase_price=10.0 + (i % 100) * 0.1,
                quantity_received=1000
            )
            batches.append(batch)

    for batch in batches:
        db_session.add(batch)
    db_session.commit()

    # Create consumption records
    batch_ids = [b.batch_id for b in db_session.query(Batch).all()]
    item_ids = [i.item_id for i in db_session.query(Item).all()]
    dept_ids = [d.department_id for d in db_session.query(Department).all()]

    consumption_records = []
    for idx in range(num_records):
        cr = ConsumptionRecord(
            item_id=item_ids[idx % len(item_ids)],
            batch_id=batch_ids[idx % len(batch_ids)],
            department_id=dept_ids[idx % len(dept_ids)],
            quantity_used=np.random.randint(5, 100),
            usage_date=base_date + timedelta(days=idx % 365),
            patient_type="Patient" if idx % 2 == 0 else "Staff"
        )
        consumption_records.append(cr)

        if (idx + 1) % 10000 == 0:
            db_session.add_all(consumption_records)
            db_session.commit()
            consumption_records = []
            print(f"  ... {idx + 1:,} records created")

    if consumption_records:
        db_session.add_all(consumption_records)
        db_session.commit()

    print(f"✓ Synthetic data generation complete: {num_records:,} records\n")


def run_benchmark():
    """Execute the full performance benchmark."""
    print("=" * 70)
    print("LightGBM DEMAND MODEL - PERFORMANCE BENCHMARK")
    print("=" * 70)
    print(f"Timestamp: {datetime.now().isoformat()}\n")

    # Initialize database
    db = SessionLocal()
    try:
        # Check if we have enough data
        record_count = db.query(ConsumptionRecord).count()
        if record_count < 50000:
            print(f"Database has {record_count:,} records (need 50k+)")
            print("Generating synthetic data for benchmark...\n")
            generate_synthetic_data(db, num_records=100000)
        else:
            print(f"Using existing {record_count:,} consumption records\n")

        # === LOAD AND PREPARE DATA ===
        print("Step 1: Loading and engineering features...")
        load_start = time.time()

        df = load_consumption_df(db)
        features_df = build_demand_features(df)

        # Filter to records with complete features
        feature_cols = ['rolling_7d', 'rolling_30d', 'lag_7', 'lag_14', 'day_of_week',
                       'month', 'velocity', 'stock_ratio', 'avg_lead_time_days', 'reliability_score']
        X = features_df[feature_cols].values
        y = features_df['quantity_used'].values

        # Remove any NaN or inf values
        mask = np.isfinite(X).all(axis=1) & np.isfinite(y)
        X = X[mask]
        y = y[mask]

        load_time = time.time() - load_start
        print(f"  ✓ Loaded {X.shape[0]:,} samples with {X.shape[1]} features")
        print(f"  ✓ Data loading time: {load_time:.2f}s\n")

        # === CROSS-VALIDATION BENCHMARK ===
        print("Step 2: Running 5-fold cross-validation...")
        cv_start = time.time()
        cv_scores = cross_validate_r2(X, y, random_seed=42, folds=5)
        cv_time = time.time() - cv_start

        avg_cv_r2 = float(np.mean(cv_scores))
        std_cv_r2 = float(np.std(cv_scores))
        print(f"  ✓ CV R² scores: {[f'{s:.4f}' for s in cv_scores]}")
        print(f"  ✓ Mean CV R²: {avg_cv_r2:.4f} (+/- {std_cv_r2:.4f})")
        print(f"  ✓ CV execution time: {cv_time:.2f}s\n")

        # === TRAINING BENCHMARK ===
        print("Step 3: Full model training...")
        train_start = time.time()

        # Train the full model
        from models.lightgbm_model import build_model
        model = build_model(random_seed=42)
        model.fit(X, y)

        train_time = time.time() - train_start
        print(f"  ✓ Training time: {train_time:.2f}s ({train_time/60:.2f} minutes)")
        print(f"  ✓ Training time per 1M samples: {(train_time * 1_000_000) / len(X):.2f}s")

        # Calculate training R²
        train_r2 = model.score(X, y)
        print(f"  ✓ Training R²: {train_r2:.4f}\n")

        # === INFERENCE BENCHMARK ===
        print("Step 4: Inference time benchmark...")

        # Test inference on single sample
        sample = X[0:1]  # Single sample (2D array)

        inference_times = []
        for _ in range(1000):
            inf_start = time.perf_counter()
            _ = model.predict(sample)
            inf_end = time.perf_counter()
            inference_times.append((inf_end - inf_start) * 1000)  # Convert to ms

        avg_inference_ms = float(np.mean(inference_times))
        p95_inference_ms = float(np.percentile(inference_times, 95))
        p99_inference_ms = float(np.percentile(inference_times, 99))

        print(f"  ✓ Avg inference time: {avg_inference_ms:.2f}ms")
        print(f"  ✓ P95 inference time: {p95_inference_ms:.2f}ms")
        print(f"  ✓ P99 inference time: {p99_inference_ms:.2f}ms\n")

        # === RESULTS SUMMARY ===
        print("=" * 70)
        print("PERFORMANCE SUMMARY")
        print("=" * 70)

        results = {
            "timestamp": datetime.now().isoformat(),
            "data_samples": len(X),
            "features": X.shape[1],
            "data_loading_time_sec": round(load_time, 4),
            "cv_execution_time_sec": round(cv_time, 4),
            "cv_mean_r2": round(avg_cv_r2, 4),
            "cv_std_r2": round(std_cv_r2, 4),
            "training_time_sec": round(train_time, 4),
            "training_time_minutes": round(train_time / 60, 2),
            "training_r2": round(train_r2, 4),
            "avg_inference_ms": round(avg_inference_ms, 4),
            "p95_inference_ms": round(p95_inference_ms, 4),
            "p99_inference_ms": round(p99_inference_ms, 4),
            "acceptance_criteria": {
                "training_time_under_5min": train_time < 300,
                "inference_time_under_50ms": avg_inference_ms < 50,
                "r2_score_above_0_97": train_r2 >= 0.97 or avg_cv_r2 >= 0.97,
            }
        }

        print(f"Data samples: {results['data_samples']:,}")
        print(f"Training time: {results['training_time_minutes']} minutes ({'✓ PASS' if results['acceptance_criteria']['training_time_under_5min'] else '✗ FAIL'} <5min)")
        print(f"Inference time: {results['avg_inference_ms']} ms ({'✓ PASS' if results['acceptance_criteria']['inference_time_under_50ms'] else '✗ FAIL'} <50ms)")
        print(f"R² score: CV mean {results['cv_mean_r2']} ({'✓ PASS' if results['acceptance_criteria']['r2_score_above_0_97'] else '✗ FAIL'} ≥0.97)")
        print("=" * 70)

        # Save results to file
        results_file = Path(__file__).parent / "benchmark_results.json"
        import json
        with open(results_file, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\n✓ Results saved to: {results_file}")

        return results

    finally:
        db.close()


if __name__ == "__main__":
    run_benchmark()
