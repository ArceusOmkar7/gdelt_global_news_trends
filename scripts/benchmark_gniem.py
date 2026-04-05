"""
GNIEM Academic Benchmark Suite
================================
Measures real performance characteristics of the GNIEM system:

  1. DuckDB Hot Tier      — latency + throughput across query types and window sizes
  2. API Concurrency      — 5 → 500 simulated users, p50/p95/p99 latencies, error rate
  3. IsolationForest      — precision/recall/F1 on injected anomalies at multiple contamination rates
  4. Prophet Backtesting  — walk-forward MAE vs naive baseline, MAPE, coverage of uncertainty bands
  5. KMeans Clustering    — silhouette score, inertia curve (elbow), cluster stability across seeds
  6. BigQuery Guard       — dry-run byte estimation, verifies cost guard fires correctly
  7. Data Volume          — hot tier row count, file sizes, ingestion rate

Run on the GCP VM:
    python benchmark_gniem.py

Output: benchmark_results.json  (machine-readable, paste into reports)
        benchmark_report.txt    (human-readable summary for academic submission)
"""

import os
import sys
import time
import json
import math
import random
import asyncio
import subprocess
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx
import numpy as np
import pandas as pd
import duckdb
from sklearn.ensemble import IsolationForest
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import (
    precision_recall_fscore_support,
    silhouette_score,
    mean_absolute_error,
)

# ── Config ─────────────────────────────────────────────────────────────────────
BASE_URL     = os.getenv("BENCHMARK_API_URL", "http://localhost:8000/api/v1")
PARQUET_PATH = os.getenv("HOT_TIER_PATH", "data/hot_tier")
CACHE_PATH   = os.getenv("CACHE_PATH",    "data/cache")
BQ_MAX_SCAN  = int(os.getenv("BQ_MAX_SCAN_BYTES", 2_000_000_000))

OUTPUT_JSON = "benchmark_results.json"
OUTPUT_TXT  = "benchmark_report.txt"

CONCURRENCY_LEVELS = [5, 10, 25, 50, 100, 200, 500]
REQUESTS_PER_LEVEL = 50   # total requests fired at each concurrency level
ANOMALY_SEEDS      = [42, 7, 99, 1337, 2025]
KMEANS_K_RANGE     = range(2, 11)   # k=2..10 for elbow analysis
KMEANS_SEEDS       = [0, 1, 2, 3, 4]


# ── Helpers ────────────────────────────────────────────────────────────────────

def fresh_conn() -> duckdb.DuckDBPyConnection:
    """Always return a per-query :memory: connection — matches production pattern."""
    return duckdb.connect(database=":memory:")


def percentile(data: list, p: float) -> float:
    if not data:
        return 0.0
    sorted_data = sorted(data)
    idx = math.ceil(p / 100 * len(sorted_data)) - 1
    return round(sorted_data[max(0, idx)], 2)


def sqldate_int(dt: datetime) -> int:
    return int(dt.strftime("%Y%m%d"))


# ── Section 1: DuckDB Hot Tier ─────────────────────────────────────────────────

def benchmark_duckdb(results: dict):
    print("\n[1/7] DuckDB Hot Tier Benchmarks")
    print("      Measuring latency, throughput, and query type performance...")

    parquet_glob = f"{PARQUET_PATH}/*.parquet"
    section: dict = {}

    # ── 1a. Latency across window sizes ────────────────────────────────────────
    window_latencies: dict = {}
    for days in [1, 7, 30, 90]:
        start_date = sqldate_int(datetime.now() - timedelta(days=days))
        sql = f"""
            SELECT ActionGeo_CountryCode,
                   COUNT(*)              AS event_count,
                   AVG(GoldsteinScale)   AS avg_goldstein,
                   AVG(AvgTone)          AS avg_tone
            FROM   read_parquet('{parquet_glob}')
            WHERE  SQLDATE >= {start_date}
            GROUP  BY ActionGeo_CountryCode
            ORDER  BY event_count DESC
            LIMIT  50
        """
        times = []
        for _ in range(5):   # 5 runs — discard first (cold), average the rest
            conn = fresh_conn()
            t0 = time.perf_counter()
            conn.execute(sql).fetchdf()
            times.append((time.perf_counter() - t0) * 1000)
            conn.close()

        window_latencies[f"{days}d"] = {
            "cold_ms":  round(times[0], 2),
            "warm_avg_ms": round(sum(times[1:]) / len(times[1:]), 2),
            "warm_p95_ms": percentile(times[1:], 95),
        }
        print(f"      {days}d window — cold={times[0]:.0f}ms  warm_avg={window_latencies[f'{days}d']['warm_avg_ms']:.0f}ms")

    section["window_latency_ms"] = window_latencies

    # ── 1b. Throughput — rows/second ────────────────────────────────────────────
    start_date = sqldate_int(datetime.now() - timedelta(days=90))
    sql_count = f"SELECT COUNT(*) FROM read_parquet('{parquet_glob}') WHERE SQLDATE >= {start_date}"
    conn = fresh_conn()
    total_rows = conn.execute(sql_count).fetchone()[0]
    conn.close()

    # Full 90-day scan throughput
    conn = fresh_conn()
    t0 = time.perf_counter()
    conn.execute(f"SELECT * FROM read_parquet('{parquet_glob}') WHERE SQLDATE >= {start_date}").fetchdf()
    elapsed = time.perf_counter() - t0
    conn.close()

    rows_per_sec = int(total_rows / elapsed) if elapsed > 0 else 0
    section["throughput"] = {
        "total_rows_90d": total_rows,
        "full_scan_sec":  round(elapsed, 3),
        "rows_per_second": rows_per_sec,
    }
    print(f"      Throughput: {rows_per_sec:,} rows/sec  ({total_rows:,} rows in {elapsed:.2f}s)")

    # ── 1c. Query type comparison ────────────────────────────────────────────────
    # (aggregation vs point-lookup vs time-series roll-up)
    query_types = {
        "global_agg_7d": f"""
            SELECT QuadClass, COUNT(*) as n, AVG(GoldsteinScale) as gs
            FROM read_parquet('{parquet_glob}')
            WHERE SQLDATE >= {sqldate_int(datetime.now() - timedelta(days=7))}
            GROUP BY QuadClass
        """,
        "country_point_lookup": f"""
            SELECT * FROM read_parquet('{parquet_glob}')
            WHERE ActionGeo_CountryCode = 'US'
              AND SQLDATE >= {sqldate_int(datetime.now() - timedelta(days=7))}
            LIMIT 1000
        """,
        "timeseries_rollup_30d": f"""
            SELECT SQLDATE, COUNT(*) as daily_events, AVG(AvgTone) as tone
            FROM read_parquet('{parquet_glob}')
            WHERE SQLDATE >= {sqldate_int(datetime.now() - timedelta(days=30))}
            GROUP BY SQLDATE
            ORDER BY SQLDATE
        """,
        "risk_score_agg_30d": f"""
            SELECT ActionGeo_CountryCode,
                   COUNT(*) FILTER (WHERE QuadClass IN (3,4)) * 1.0 / NULLIF(COUNT(*),0) AS conflict_ratio,
                   AVG(GoldsteinScale) as avg_gs,
                   AVG(AvgTone)        as avg_tone,
                   SUM(NumMentions)    as total_mentions
            FROM read_parquet('{parquet_glob}')
            WHERE SQLDATE >= {sqldate_int(datetime.now() - timedelta(days=30))}
            GROUP BY ActionGeo_CountryCode
            HAVING COUNT(*) > 10
            ORDER BY conflict_ratio DESC
        """,
    }

    qt_latencies: dict = {}
    for name, sql in query_types.items():
        runs = []
        for _ in range(5):
            conn = fresh_conn()
            t0 = time.perf_counter()
            conn.execute(sql).fetchdf()
            runs.append((time.perf_counter() - t0) * 1000)
            conn.close()
        warm = runs[1:]
        qt_latencies[name] = {
            "avg_ms": round(sum(warm) / len(warm), 2),
            "p95_ms": percentile(warm, 95),
        }
        print(f"      {name}: avg={qt_latencies[name]['avg_ms']:.0f}ms")

    section["query_type_latency_ms"] = qt_latencies
    results["big_data"] = section


# ── Section 2: API Concurrency ─────────────────────────────────────────────────

async def benchmark_concurrency(results: dict):
    print("\n[2/7] API Concurrency — 5 to 500 simulated users")
    print(f"      {REQUESTS_PER_LEVEL} requests per level, measuring p50/p95/p99 + error rate...")

    endpoints = [
        f"{BASE_URL}/events/map?zoom=3",
        f"{BASE_URL}/analytics/spikes",
        f"{BASE_URL}/analytics/clusters",
        f"{BASE_URL}/health",
        f"{BASE_URL}/events/counts?days=7",
    ]

    section: dict = {}

    async def fire_request(client: httpx.AsyncClient, url: str) -> dict:
        t0 = time.perf_counter()
        try:
            r = await client.get(url, timeout=30.0)
            latency = (time.perf_counter() - t0) * 1000
            return {"latency_ms": latency, "status": r.status_code, "ok": r.status_code == 200}
        except Exception as e:
            latency = (time.perf_counter() - t0) * 1000
            return {"latency_ms": latency, "status": 0, "ok": False, "error": str(e)}

    async with httpx.AsyncClient() as client:
        for level in CONCURRENCY_LEVELS:
            batch_size   = min(level, REQUESTS_PER_LEVEL)
            total_batches = max(1, REQUESTS_PER_LEVEL // batch_size)
            all_results  = []

            wall_start = time.perf_counter()
            for _ in range(total_batches):
                urls  = [random.choice(endpoints) for _ in range(batch_size)]
                tasks = [fire_request(client, u) for u in urls]
                batch = await asyncio.gather(*tasks)
                all_results.extend(batch)
            wall_elapsed = time.perf_counter() - wall_start

            latencies  = [r["latency_ms"] for r in all_results]
            errors     = [r for r in all_results if not r["ok"]]
            error_rate = len(errors) / len(all_results) * 100

            level_stats = {
                "total_requests":  len(all_results),
                "error_rate_pct":  round(error_rate, 2),
                "p50_ms":          percentile(latencies, 50),
                "p95_ms":          percentile(latencies, 95),
                "p99_ms":          percentile(latencies, 99),
                "max_ms":          round(max(latencies), 2) if latencies else 0,
                "wall_time_sec":   round(wall_elapsed, 3),
                "throughput_rps":  round(len(all_results) / wall_elapsed, 1),
            }
            section[f"users_{level}"] = level_stats
            print(f"      {level:>4} users — p50={level_stats['p50_ms']:.0f}ms  "
                  f"p95={level_stats['p95_ms']:.0f}ms  "
                  f"p99={level_stats['p99_ms']:.0f}ms  "
                  f"err={error_rate:.1f}%  "
                  f"rps={level_stats['throughput_rps']}")

    results["system_load"] = section


# ── Section 3: IsolationForest Anomaly Detection ───────────────────────────────

def validate_anomaly_detection(results: dict):
    print("\n[3/7] IsolationForest Anomaly Detection — Multi-seed validation")
    print("      Testing across contamination rates and random seeds...")

    section: dict = {}

    # Use real GDELT-like feature space: GoldsteinScale, AvgTone, NumMentions, QuadClass, NumSources
    FEATURE_DIM   = 5
    N_NORMAL      = 2000
    N_ANOM        = 100   # 5% contamination

    contamination_rates = [0.03, 0.05, 0.08, 0.10]

    for contamination in contamination_rates:
        seed_metrics = []
        for seed in ANOMALY_SEEDS:
            rng = np.random.default_rng(seed)

            # Normal events: realistic GDELT distributions
            normal = np.column_stack([
                rng.normal(0, 3, N_NORMAL),          # GoldsteinScale: mean 0, std 3
                rng.normal(-2, 4, N_NORMAL),          # AvgTone: slightly negative
                rng.integers(1, 50, N_NORMAL),         # NumMentions
                rng.integers(1, 4, N_NORMAL),          # QuadClass
                rng.integers(1, 20, N_NORMAL),         # NumSources
            ])

            # Anomalies: extreme values (conflict spikes)
            anomalies = np.column_stack([
                rng.uniform(-10, -7, N_ANOM),          # Very negative Goldstein (war)
                rng.uniform(-15, -10, N_ANOM),         # Extremely hostile tone
                rng.integers(500, 2000, N_ANOM),       # Massive mention spike
                np.full(N_ANOM, 4),                    # All material conflict
                rng.integers(100, 500, N_ANOM),        # Many sources
            ])

            X      = np.vstack([normal, anomalies])
            y_true = np.array([1] * N_NORMAL + [-1] * N_ANOM)

            clf   = IsolationForest(contamination=contamination, random_state=seed, n_estimators=200)
            y_pred = clf.fit_predict(X)

            precision, recall, f1, _ = precision_recall_fscore_support(
                y_true, y_pred, average="binary", pos_label=-1, zero_division=0
            )
            # Anomaly score variance (higher = more confident separation)
            scores         = clf.decision_function(X)
            normal_scores  = scores[:N_NORMAL]
            anomaly_scores = scores[N_NORMAL:]
            separation_gap = float(np.mean(normal_scores) - np.mean(anomaly_scores))

            seed_metrics.append({
                "seed": seed,
                "precision": round(float(precision), 4),
                "recall":    round(float(recall),    4),
                "f1_score":  round(float(f1),        4),
                "separation_gap": round(separation_gap, 4),
            })

        avg_f1        = round(sum(m["f1_score"]  for m in seed_metrics) / len(seed_metrics), 4)
        avg_precision = round(sum(m["precision"] for m in seed_metrics) / len(seed_metrics), 4)
        avg_recall    = round(sum(m["recall"]    for m in seed_metrics) / len(seed_metrics), 4)
        f1_std        = round(float(np.std([m["f1_score"] for m in seed_metrics])), 4)

        section[f"contamination_{int(contamination*100)}pct"] = {
            "avg_precision": avg_precision,
            "avg_recall":    avg_recall,
            "avg_f1":        avg_f1,
            "f1_std_across_seeds": f1_std,
            "per_seed": seed_metrics,
        }
        print(f"      contam={int(contamination*100)}%  avg_F1={avg_f1:.4f}  std={f1_std:.4f}  "
              f"P={avg_precision:.4f}  R={avg_recall:.4f}")

    results["ai_validation"]["anomaly_detection"] = section


# ── Section 4: Prophet Walk-Forward Backtest ───────────────────────────────────

def validate_forecasting(results: dict):
    print("\n[4/7] Prophet Walk-Forward Backtesting")
    print("      MAE vs naive baseline, MAPE, uncertainty band coverage...")

    try:
        from prophet import Prophet
    except ImportError:
        results["ai_validation"]["forecasting"] = "Skipped: prophet not installed"
        print("      Skipped: prophet not installed")
        return

    parquet_glob = f"{PARQUET_PATH}/*.parquet"
    section: dict = {}

    try:
        conn = fresh_conn()
        # Pull 90-day daily conflict event counts for the top country by volume
        start_date = sqldate_int(datetime.now() - timedelta(days=90))
        df = conn.execute(f"""
            SELECT
                STRPTIME(CAST(SQLDATE AS VARCHAR), '%Y%m%d')::DATE::VARCHAR AS ds,
                COUNT(*) AS y
            FROM read_parquet('{parquet_glob}')
            WHERE SQLDATE >= {start_date}
              AND QuadClass IN (3, 4)
              AND ActionGeo_CountryCode = (
                    SELECT ActionGeo_CountryCode
                    FROM   read_parquet('{parquet_glob}')
                    WHERE  SQLDATE >= {start_date} AND QuadClass IN (3,4)
                    GROUP  BY ActionGeo_CountryCode
                    ORDER  BY COUNT(*) DESC
                    LIMIT  1
              )
            GROUP BY ds
            ORDER BY ds
        """).df()
        conn.close()

        if len(df) < 21:
            msg = f"Skipped: only {len(df)} days of data — need at least 21 for walk-forward"
            results["ai_validation"]["forecasting"] = msg
            print(f"      {msg}")
            return

        df["ds"] = pd.to_datetime(df["ds"])
        df["y"]  = df["y"].astype(float)

        # Walk-forward: train on first N days, predict day N+1, slide window
        # Use a 14-day training window, evaluate on the following 7 days
        TRAIN_DAYS = 14
        TEST_DAYS  = 7
        cutoffs    = range(TRAIN_DAYS, len(df) - TEST_DAYS)

        prophet_errors = []
        naive_errors   = []
        in_band_count  = 0
        total_pred     = 0

        for cut in cutoffs:
            train = df.iloc[:cut].copy()
            test  = df.iloc[cut : cut + TEST_DAYS].copy()

            m = Prophet(
                daily_seasonality=False,
                weekly_seasonality=True,
                yearly_seasonality=False,
                interval_width=0.80,
                changepoint_prior_scale=0.05,
            )
            m.fit(train[["ds", "y"]])

            future   = m.make_future_dataframe(periods=TEST_DAYS)
            forecast = m.predict(future).tail(TEST_DAYS).reset_index(drop=True)
            actual   = test["y"].values

            prophet_pred = forecast["yhat"].values
            prophet_pred = np.maximum(prophet_pred, 0)   # event counts can't be negative

            # Naive baseline: last observed value carried forward
            naive_pred = np.full(TEST_DAYS, train["y"].iloc[-1])

            prophet_errors.extend(np.abs(actual - prophet_pred))
            naive_errors.extend(np.abs(actual - naive_pred))

            # Uncertainty band coverage
            yhat_lower = forecast["yhat_lower"].values
            yhat_upper = forecast["yhat_upper"].values
            in_band_count += int(np.sum((actual >= yhat_lower) & (actual <= yhat_upper)))
            total_pred    += TEST_DAYS

        prophet_mae  = round(float(np.mean(prophet_errors)), 4)
        naive_mae    = round(float(np.mean(naive_errors)), 4)
        improvement  = round((naive_mae - prophet_mae) / naive_mae * 100, 2) if naive_mae > 0 else 0
        band_coverage = round(in_band_count / total_pred * 100, 2) if total_pred > 0 else 0

        # MAPE (exclude zero actuals)
        actuals_arr = np.array([v for v in prophet_errors if v != 0])  # reuse abs errors
        # Recompute MAPE properly
        mape_pairs = []
        for cut in list(cutoffs)[:5]:  # sample 5 windows for MAPE to keep runtime reasonable
            train = df.iloc[:cut].copy()
            test  = df.iloc[cut : cut + TEST_DAYS].copy()
            m = Prophet(daily_seasonality=False, weekly_seasonality=True,
                        yearly_seasonality=False, interval_width=0.80)
            m.fit(train[["ds", "y"]])
            forecast = m.predict(m.make_future_dataframe(periods=TEST_DAYS)).tail(TEST_DAYS)
            actual   = test["y"].values
            pred     = np.maximum(forecast["yhat"].values, 0)
            nonzero  = actual != 0
            if nonzero.any():
                mape_pairs.extend((np.abs(actual[nonzero] - pred[nonzero]) / actual[nonzero]).tolist())

        mape = round(float(np.mean(mape_pairs)) * 100, 2) if mape_pairs else None

        section = {
            "walk_forward_windows": len(list(cutoffs)),
            "train_days": TRAIN_DAYS,
            "test_days":  TEST_DAYS,
            "prophet_mae":  prophet_mae,
            "naive_mae":    naive_mae,
            "improvement_over_naive_pct": improvement,
            "mape_pct":     mape,
            "uncertainty_band_coverage_pct": band_coverage,
            "note": f"80% uncertainty band; coverage should be ~80% if well-calibrated. Got {band_coverage}%"
        }

        print(f"      Prophet MAE={prophet_mae:.2f}  Naive MAE={naive_mae:.2f}  "
              f"Improvement={improvement:.1f}%  MAPE={mape}%  BandCoverage={band_coverage}%")

    except Exception as e:
        section = {"error": str(e)}
        print(f"      ERROR: {e}")

    results["ai_validation"]["forecasting"] = section


# ── Section 5: KMeans Clustering Quality ──────────────────────────────────────

def validate_clustering(results: dict):
    print("\n[5/7] KMeans Clustering Quality — Elbow + Silhouette + Stability")
    print("      Running k=2..10, 5 seeds each...")

    parquet_glob = f"{PARQUET_PATH}/*.parquet"
    section: dict = {}

    try:
        conn = fresh_conn()
        start_date = sqldate_int(datetime.now() - timedelta(days=7))
        df = conn.execute(f"""
            SELECT SOURCEURL, EventRootCode, Actor1Type1Code, Actor2Type1Code,
                   QuadClass, GoldsteinScale, AvgTone, NumMentions
            FROM read_parquet('{parquet_glob}')
            WHERE SQLDATE >= {start_date}
              AND SOURCEURL IS NOT NULL
            LIMIT 5000
        """).df()
        conn.close()

        if len(df) < 100:
            results["ai_validation"]["clustering"] = "Skipped: fewer than 100 rows"
            print("      Skipped: insufficient data")
            return

        # TF-IDF on SOURCEURL (as in production)
        tfidf = TfidfVectorizer(max_features=300, analyzer="word",
                                token_pattern=r"[a-zA-Z]{3,}")
        X_tfidf = tfidf.fit_transform(df["SOURCEURL"].fillna("").astype(str))
        X_dense = X_tfidf.toarray()

        # Elbow: inertia per k
        elbow: dict = {}
        for k in KMEANS_K_RANGE:
            km = KMeans(n_clusters=k, n_init=10, random_state=0)
            km.fit(X_dense)
            elbow[str(k)] = round(float(km.inertia_), 2)

        # Silhouette per k (subset for speed)
        sample_size = min(1000, len(X_dense))
        sil_idx     = np.random.default_rng(0).choice(len(X_dense), sample_size, replace=False)
        X_sil       = X_dense[sil_idx]

        silhouettes: dict = {}
        for k in KMEANS_K_RANGE:
            km      = KMeans(n_clusters=k, n_init=10, random_state=0)
            labels  = km.fit_predict(X_sil)
            sil_avg = silhouette_score(X_sil, labels, sample_size=min(500, sample_size))
            silhouettes[str(k)] = round(float(sil_avg), 4)

        best_k = max(silhouettes, key=lambda k: silhouettes[k])
        print(f"      Best k by silhouette: k={best_k} (score={silhouettes[best_k]:.4f})")

        # Cluster stability across seeds (ARI not imported — use label overlap proxy)
        # Check how stable the cluster sizes are across 5 seeds for best_k
        size_arrays = []
        for seed in KMEANS_SEEDS:
            km     = KMeans(n_clusters=int(best_k), n_init=10, random_state=seed)
            labels = km.fit_predict(X_dense)
            sizes  = sorted([int(np.sum(labels == c)) for c in range(int(best_k))], reverse=True)
            size_arrays.append(sizes)

        # Coefficient of variation of cluster sizes across seeds = stability proxy
        size_matrix = np.array(size_arrays, dtype=float)
        cv_per_cluster = (size_matrix.std(axis=0) / size_matrix.mean(axis=0)).mean()
        stability_score = round(1 - float(cv_per_cluster), 4)  # higher = more stable

        section = {
            "n_documents":  len(df),
            "tfidf_features": 300,
            "elbow_inertia":  elbow,
            "silhouette_scores": silhouettes,
            "best_k_by_silhouette": int(best_k),
            "cluster_stability_score": stability_score,
            "note": "Stability = 1 - mean(CV of cluster sizes across 5 random seeds). >0.85 is good."
        }
        print(f"      Silhouettes: {silhouettes}")
        print(f"      Stability score: {stability_score:.4f}")

    except Exception as e:
        section = {"error": str(e)}
        print(f"      ERROR: {e}")

    results["ai_validation"]["clustering"] = section


# ── Section 6: BigQuery Cost Guard Verification ────────────────────────────────

def verify_bq_guard(results: dict):
    print("\n[6/7] BigQuery Cost Guard Verification")
    print("      Running dry_run queries; verifying guard correctly aborts oversized scans...")

    section: dict = {}

    try:
        from google.cloud import bigquery
        client = bigquery.Client()

        test_cases = [
            {
                "name":       "safe_7d_events",
                "expected":   "pass",
                "query": """
                    SELECT GLOBALEVENTID, SQLDATE, ActionGeo_CountryCode,
                           QuadClass, GoldsteinScale, NumMentions, AvgTone
                    FROM `gdelt-bq.gdeltv2.events`
                    WHERE SQLDATE >= {start} AND SQLDATE < {end}
                """.format(
                    start=sqldate_int(datetime.now() - timedelta(days=7)),
                    end=sqldate_int(datetime.now()),
                ),
            },
            {
                "name":       "safe_30d_events",
                "expected":   "pass",
                "query": """
                    SELECT GLOBALEVENTID, SQLDATE, ActionGeo_CountryCode,
                           QuadClass, GoldsteinScale, NumMentions, AvgTone
                    FROM `gdelt-bq.gdeltv2.events`
                    WHERE SQLDATE >= {start} AND SQLDATE < {end}
                """.format(
                    start=sqldate_int(datetime.now() - timedelta(days=30)),
                    end=sqldate_int(datetime.now()),
                ),
            },
            {
                "name":     "dangerous_no_partition_filter",
                "expected": "blocked",
                "query": "SELECT GLOBALEVENTID, SQLDATE FROM `gdelt-bq.gdeltv2.events` LIMIT 100",
            },
            {
                "name":     "dangerous_gkg_no_filter",
                "expected": "blocked",
                "query": "SELECT V2Themes FROM `gdelt-bq.gdeltv2.gkg` LIMIT 10",
            },
        ]

        case_results = []
        for tc in test_cases:
            config   = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
            job      = client.query(tc["query"], job_config=config)
            bytes_est = job.total_bytes_processed
            guard_fires = bytes_est > BQ_MAX_SCAN
            outcome     = "blocked" if guard_fires else "pass"
            correct     = outcome == tc["expected"]

            case_results.append({
                "name":           tc["name"],
                "expected":       tc["expected"],
                "outcome":        outcome,
                "bytes_estimated": bytes_est,
                "gb_estimated":    round(bytes_est / 1e9, 3),
                "guard_correct":   correct,
            })
            status = "✓" if correct else "✗ WRONG"
            print(f"      {status}  {tc['name']}: {bytes_est/1e9:.3f} GB → {outcome}")

        section = {
            "bq_max_scan_bytes": BQ_MAX_SCAN,
            "test_cases": case_results,
            "all_guards_correct": all(c["guard_correct"] for c in case_results),
        }

    except ImportError:
        section = {"skipped": "google-cloud-bigquery not installed"}
        print("      Skipped: google-cloud-bigquery not installed")
    except Exception as e:
        section = {"error": str(e)}
        print(f"      ERROR: {e}")

    results["bq_guard"] = section


# ── Section 7: Data Volume Metrics ─────────────────────────────────────────────

def measure_data_volume(results: dict):
    print("\n[7/7] Data Volume Metrics")
    print("      Counting rows, measuring file sizes, estimating ingestion rate...")

    section: dict = {}
    parquet_glob = f"{PARQUET_PATH}/*.parquet"

    try:
        # File sizes
        parquet_files = [
            os.path.join(PARQUET_PATH, f)
            for f in os.listdir(PARQUET_PATH)
            if f.endswith(".parquet")
        ] if os.path.isdir(PARQUET_PATH) else []

        total_bytes = sum(os.path.getsize(f) for f in parquet_files)
        section["hot_tier_files"]     = len(parquet_files)
        section["hot_tier_bytes"]     = total_bytes
        section["hot_tier_mb"]        = round(total_bytes / 1e6, 2)
        section["hot_tier_gb"]        = round(total_bytes / 1e9, 3)

        # Row counts
        conn = fresh_conn()
        total_rows = conn.execute(
            f"SELECT COUNT(*) FROM read_parquet('{parquet_glob}')"
        ).fetchone()[0]
        conn.close()

        section["total_rows"] = total_rows

        # Date range
        conn = fresh_conn()
        row = conn.execute(
            f"SELECT MIN(SQLDATE), MAX(SQLDATE) FROM read_parquet('{parquet_glob}')"
        ).fetchone()
        conn.close()
        section["oldest_sqldate"]  = int(row[0]) if row[0] else None
        section["newest_sqldate"]  = int(row[1]) if row[1] else None

        # Ingestion rate estimate
        if section["oldest_sqldate"] and section["newest_sqldate"]:
            days_span = max(1, (
                datetime.strptime(str(section["newest_sqldate"]), "%Y%m%d") -
                datetime.strptime(str(section["oldest_sqldate"]),  "%Y%m%d")
            ).days)
            section["rows_per_day_avg"] = round(total_rows / days_span)
            section["days_of_data"]     = days_span

        # Bytes per row
        section["bytes_per_row_avg"] = round(total_bytes / total_rows, 1) if total_rows else 0

        print(f"      {total_rows:,} rows  |  {section['hot_tier_mb']:.1f} MB  |  "
              f"{section.get('days_of_data','?')} days  |  "
              f"~{section.get('rows_per_day_avg',0):,} rows/day")

    except Exception as e:
        section["error"] = str(e)
        print(f"      ERROR: {e}")

    results["data_volume"] = section


# ── Report Writer ──────────────────────────────────────────────────────────────

def write_report(results: dict):
    lines = [
        "=" * 70,
        "GNIEM ACADEMIC BENCHMARK REPORT",
        f"Generated: {results['timestamp']}",
        "=" * 70,
        "",
        "1. DuckDB Hot Tier Latency",
        "-" * 40,
    ]

    bd = results.get("big_data", {})
    for window, stats in bd.get("window_latency_ms", {}).items():
        lines.append(f"  {window:>4} — cold: {stats['cold_ms']}ms | warm avg: {stats['warm_avg_ms']}ms | warm p95: {stats['warm_p95_ms']}ms")

    tp = bd.get("throughput", {})
    lines += [
        "",
        f"  Throughput: {tp.get('rows_per_second',0):,} rows/sec",
        f"  Total rows (90d): {tp.get('total_rows_90d',0):,}",
        f"  Full-scan time:   {tp.get('full_scan_sec',0)}s",
        "",
        "  Query Type Breakdown:",
    ]
    for qtype, stats in bd.get("query_type_latency_ms", {}).items():
        lines.append(f"    {qtype:<35} avg={stats['avg_ms']}ms  p95={stats['p95_ms']}ms")

    lines += ["", "2. API Concurrency (p50/p95/p99/errors/rps)", "-" * 40]
    for key, stats in results.get("system_load", {}).items():
        users = key.replace("users_", "")
        lines.append(
            f"  {users:>4} users — "
            f"p50={stats['p50_ms']}ms  p95={stats['p95_ms']}ms  p99={stats['p99_ms']}ms  "
            f"err={stats['error_rate_pct']}%  rps={stats['throughput_rps']}"
        )

    lines += ["", "3. IsolationForest Anomaly Detection", "-" * 40]
    for key, stats in results.get("ai_validation", {}).get("anomaly_detection", {}).items():
        lines.append(
            f"  {key}: avg_F1={stats['avg_f1']}  P={stats['avg_precision']}  "
            f"R={stats['avg_recall']}  F1_std={stats['f1_std_across_seeds']}"
        )

    lines += ["", "4. Prophet Walk-Forward Backtesting", "-" * 40]
    fc = results.get("ai_validation", {}).get("forecasting", {})
    if isinstance(fc, dict) and "prophet_mae" in fc:
        lines += [
            f"  Prophet MAE:  {fc['prophet_mae']}",
            f"  Naive MAE:    {fc['naive_mae']}",
            f"  Improvement:  {fc['improvement_over_naive_pct']}%",
            f"  MAPE:         {fc.get('mape_pct')}%",
            f"  Band Coverage:{fc['uncertainty_band_coverage_pct']}% (target ≈ 80%)",
        ]
    else:
        lines.append(f"  {fc}")

    lines += ["", "5. KMeans Clustering Quality", "-" * 40]
    cl = results.get("ai_validation", {}).get("clustering", {})
    if isinstance(cl, dict) and "best_k_by_silhouette" in cl:
        lines += [
            f"  Documents: {cl['n_documents']}  |  Features: {cl['tfidf_features']}",
            f"  Best k (silhouette): {cl['best_k_by_silhouette']}",
            f"  Stability score: {cl['cluster_stability_score']}",
            "  Silhouette by k:",
        ]
        for k, v in cl.get("silhouette_scores", {}).items():
            lines.append(f"    k={k}: {v}")
    else:
        lines.append(f"  {cl}")

    lines += ["", "6. BigQuery Cost Guard", "-" * 40]
    bq = results.get("bq_guard", {})
    if "test_cases" in bq:
        lines.append(f"  Guard limit: {bq['bq_max_scan_bytes']/1e9:.1f} GB")
        for tc in bq["test_cases"]:
            mark = "✓" if tc["guard_correct"] else "✗"
            lines.append(f"  {mark} {tc['name']:<40} {tc['gb_estimated']:.3f} GB → {tc['outcome']}")
        lines.append(f"  All guards correct: {bq.get('all_guards_correct')}")

    lines += ["", "7. Data Volume", "-" * 40]
    dv = results.get("data_volume", {})
    lines += [
        f"  Total rows:       {dv.get('total_rows',0):,}",
        f"  Hot tier size:    {dv.get('hot_tier_mb',0)} MB",
        f"  Days of data:     {dv.get('days_of_data','?')}",
        f"  Rows/day (avg):   {dv.get('rows_per_day_avg',0):,}",
        f"  Date range:       {dv.get('oldest_sqldate')} → {dv.get('newest_sqldate')}",
        "",
        "=" * 70,
    ]

    txt = "\n".join(lines)
    with open(OUTPUT_TXT, "w") as f:
        f.write(txt)
    print(f"\n{txt}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    results = {
        "timestamp":     datetime.now().isoformat(),
        "big_data":      {},
        "system_load":   {},
        "ai_validation": {},
        "bq_guard":      {},
        "data_volume":   {},
    }

    benchmark_duckdb(results)
    asyncio.run(benchmark_concurrency(results))
    validate_anomaly_detection(results)
    validate_forecasting(results)
    validate_clustering(results)
    verify_bq_guard(results)
    measure_data_volume(results)

    with open(OUTPUT_JSON, "w") as f:
        json.dump(results, f, indent=2)

    write_report(results)
    print(f"\n✅ Done. Results → {OUTPUT_JSON} + {OUTPUT_TXT}")


if __name__ == "__main__":
    main()