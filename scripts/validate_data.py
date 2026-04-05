"""
validate_data.py
----------------
Aviation Customer Analytics — Stage 1: Data Validation & Profiling

Performs comprehensive data quality checks on:
  1. customer_master.csv
  2. flight_transactions.csv
  3. customer_feedback.csv

Produces:
  - data_quality_report.json  (machine-readable)
  - data_quality_summary.txt  (human-readable)

Usage:
    python scripts/validate_data.py \
        --customers  data/customer_master.csv \
        --transactions data/flight_transactions.csv \
        --feedback   data/customer_feedback.csv \
        --output_dir outputs/

Exit codes:
    0 = All checks passed / warnings only
    1 = Critical data quality failure (execution should stop)
"""

import argparse
import csv
import json
import os
import sys
from collections import defaultdict, Counter
from datetime import date

# ─────────────────────────────────────────────
# Quality thresholds
# ─────────────────────────────────────────────
THRESHOLDS = {
    "max_null_pct_critical":   5.0,   # >5% nulls in a required column → ERROR
    "max_null_pct_warn":       2.0,   # >2% nulls in a required column → WARN
    "max_duplicate_pct":       1.0,   # >1% duplicate primary keys → ERROR
    "min_unique_customers":  100,     # < 100 unique customers → ERROR
    "min_date_span_months":    6,     # < 6 months of history → WARN
    "max_negative_fare_pct":   0.0,   # Any negative fares → ERROR
    "min_nps_score":           0,
    "max_nps_score":          10,
    "min_satisfaction":        1.0,
    "max_satisfaction":        5.0,
}

REQUIRED_CUSTOMER_COLS = [
    "customer_id","first_name","last_name","email","age","gender",
    "home_city","home_country","home_airport","loyalty_tier",
    "loyalty_points","enrolment_date","preferred_cabin"
]
REQUIRED_TRANSACTION_COLS = [
    "booking_id","customer_id","booking_date","flight_date",
    "origin_airport","destination_airport","airline","cabin_class",
    "base_fare_inr","ancillary_spend_inr","total_spend_inr",
    "miles_earned","travel_purpose","booking_lead_days","flight_on_time"
]
REQUIRED_FEEDBACK_COLS = [
    "feedback_id","booking_id","customer_id","feedback_date",
    "overall_satisfaction","seat_comfort","cabin_crew_service",
    "food_quality","in_flight_entertainment","punctuality_score",
    "nps_score","would_recommend"
]

VALID_TIERS   = {"Bronze","Silver","Gold","Platinum"}
VALID_CABINS  = {"Economy","Premium Economy","Business","First"}
VALID_GENDERS = {"M","F","Other"}

# ─────────────────────────────────────────────
# CSV loading
# ─────────────────────────────────────────────
def load_csv(filepath):
    if not os.path.exists(filepath):
        return None, f"File not found: {filepath}"
    rows = []
    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows, None

# ─────────────────────────────────────────────
# Generic column profiler
# ─────────────────────────────────────────────
def profile_column(rows, col):
    vals = [r.get(col, "") for r in rows]
    total = len(vals)
    nulls = sum(1 for v in vals if v is None or v.strip() == "")
    null_pct = (nulls / total * 100) if total else 0
    non_null = [v for v in vals if v and v.strip()]
    unique_cnt = len(set(non_null))
    sample = non_null[:3]
    return {
        "total":     total,
        "nulls":     nulls,
        "null_pct":  round(null_pct, 2),
        "unique":    unique_cnt,
        "sample":    sample,
    }

def profile_numeric(rows, col):
    vals = []
    non_parseable = 0
    for r in rows:
        v = r.get(col, "")
        try:
            vals.append(float(v))
        except (ValueError, TypeError):
            non_parseable += 1
    if not vals:
        return {"error": "No parseable values"}
    vals.sort()
    n = len(vals)
    mean = sum(vals) / n
    variance = sum((x - mean)**2 for x in vals) / n
    std = variance**0.5
    return {
        "count":    n,
        "non_parseable": non_parseable,
        "min":      round(vals[0], 2),
        "p25":      round(vals[n//4], 2),
        "median":   round(vals[n//2], 2),
        "p75":      round(vals[3*n//4], 2),
        "max":      round(vals[-1], 2),
        "mean":     round(mean, 2),
        "std":      round(std, 2),
        "negatives": sum(1 for v in vals if v < 0),
    }

# ─────────────────────────────────────────────
# Domain-specific checks
# ─────────────────────────────────────────────
def check_date_range(rows, col):
    dates = []
    errors = 0
    for r in rows:
        v = r.get(col, "")
        try:
            dates.append(date.fromisoformat(v))
        except Exception:
            errors += 1
    if not dates:
        return {"parse_errors": errors, "min": None, "max": None, "span_months": 0}
    dates.sort()
    span_days = (dates[-1] - dates[0]).days
    return {
        "parse_errors": errors,
        "min":          str(dates[0]),
        "max":          str(dates[-1]),
        "span_months":  round(span_days / 30.44, 1),
    }

def check_referential_integrity(child_rows, child_col, parent_ids, label):
    missing = [r[child_col] for r in child_rows
               if r.get(child_col) and r[child_col] not in parent_ids]
    return {
        "label":         label,
        "total_checked": len(child_rows),
        "missing_refs":  len(missing),
        "missing_pct":   round(len(missing)/len(child_rows)*100, 2) if child_rows else 0,
    }

# ─────────────────────────────────────────────
# Main validation function
# ─────────────────────────────────────────────
def validate(customers_path, transactions_path, feedback_path, output_dir):
    errors   = []
    warnings = []
    report   = {}

    # ── Load files ───────────────────────────
    customers, err = load_csv(customers_path)
    if err:
        errors.append(f"CRITICAL: {err}")
        _write_report(output_dir, {"errors": errors, "warnings": warnings}, 1)
        return 1

    transactions, err = load_csv(transactions_path)
    if err:
        errors.append(f"CRITICAL: {err}")
        _write_report(output_dir, {"errors": errors, "warnings": warnings}, 1)
        return 1

    feedbacks, err = load_csv(feedback_path)
    if err:
        errors.append(f"CRITICAL: {err}")
        _write_report(output_dir, {"errors": errors, "warnings": warnings}, 1)
        return 1

    # ── Schema checks ─────────────────────────
    def check_schema(rows, required, table_name):
        if not rows:
            errors.append(f"CRITICAL: {table_name} is empty.")
            return
        actual = set(rows[0].keys())
        missing = set(required) - actual
        if missing:
            errors.append(f"CRITICAL: {table_name} missing columns: {sorted(missing)}")

    check_schema(customers,    REQUIRED_CUSTOMER_COLS,    "customer_master")
    check_schema(transactions, REQUIRED_TRANSACTION_COLS, "flight_transactions")
    check_schema(feedbacks,    REQUIRED_FEEDBACK_COLS,    "customer_feedback")

    if errors:
        _write_report(output_dir, {"errors": errors, "warnings": warnings}, 1)
        return 1

    # ── Customer profiling ────────────────────
    cust_profile = {}
    for col in REQUIRED_CUSTOMER_COLS:
        cust_profile[col] = profile_column(customers, col)
        if cust_profile[col]["null_pct"] > THRESHOLDS["max_null_pct_critical"]:
            errors.append(f"customer_master.{col}: {cust_profile[col]['null_pct']}% nulls (threshold {THRESHOLDS['max_null_pct_critical']}%)")
        elif cust_profile[col]["null_pct"] > THRESHOLDS["max_null_pct_warn"]:
            warnings.append(f"customer_master.{col}: {cust_profile[col]['null_pct']}% nulls")

    # Duplicate customer IDs
    cust_ids = [r["customer_id"] for r in customers]
    dup_custs = len(cust_ids) - len(set(cust_ids))
    if dup_custs / len(cust_ids) * 100 > THRESHOLDS["max_duplicate_pct"]:
        errors.append(f"customer_master: {dup_custs} duplicate customer_ids ({dup_custs/len(cust_ids)*100:.1f}%)")

    # Value distribution checks
    tier_dist  = Counter(r["loyalty_tier"] for r in customers)
    cabin_dist = Counter(r["preferred_cabin"] for r in customers)
    invalid_tiers  = [r["customer_id"] for r in customers if r["loyalty_tier"] not in VALID_TIERS]
    invalid_cabins = [r["customer_id"] for r in customers if r["preferred_cabin"] not in VALID_CABINS]
    if invalid_tiers:
        errors.append(f"customer_master: {len(invalid_tiers)} invalid loyalty_tier values")
    if invalid_cabins:
        errors.append(f"customer_master: {len(invalid_cabins)} invalid preferred_cabin values")

    age_profile = profile_numeric(customers, "age")
    if age_profile.get("min", 0) < 0 or age_profile.get("max", 0) > 120:
        errors.append("customer_master: age values out of [0,120] range")

    report["customer_master"] = {
        "row_count":       len(customers),
        "unique_customers":len(set(cust_ids)),
        "duplicate_ids":   dup_custs,
        "column_profiles": cust_profile,
        "tier_distribution": dict(tier_dist),
        "cabin_preference_distribution": dict(cabin_dist),
        "age_profile":     age_profile,
    }


    # ── Transaction profiling ─────────────────
    txn_profile = {}
    for col in REQUIRED_TRANSACTION_COLS:
        txn_profile[col] = profile_column(transactions, col)
        if txn_profile[col]["null_pct"] > THRESHOLDS["max_null_pct_critical"]:
            errors.append(f"flight_transactions.{col}: {txn_profile[col]['null_pct']}% nulls")

    bk_ids = [r["booking_id"] for r in transactions]
    dup_bks = len(bk_ids) - len(set(bk_ids))
    if dup_bks > 0:
        errors.append(f"flight_transactions: {dup_bks} duplicate booking_ids")

    fare_profile = profile_numeric(transactions, "base_fare_inr")
    if fare_profile.get("negatives", 0) > 0:
        errors.append(f"flight_transactions: {fare_profile['negatives']} negative base_fare_inr values")

    total_spend_profile = profile_numeric(transactions, "total_spend_inr")
    ancillary_profile   = profile_numeric(transactions, "ancillary_spend_inr")
    miles_profile       = profile_numeric(transactions, "miles_earned")
    lead_profile        = profile_numeric(transactions, "booking_lead_days")

    flight_date_range   = check_date_range(transactions, "flight_date")
    if flight_date_range["span_months"] < THRESHOLDS["min_date_span_months"]:
        warnings.append(f"flight_transactions: only {flight_date_range['span_months']} months of data (min recommended: {THRESHOLDS['min_date_span_months']})")

    cabin_dist_txn = Counter(r["cabin_class"] for r in transactions)
    purpose_dist   = Counter(r["travel_purpose"] for r in transactions)
    airline_dist   = Counter(r["airline"] for r in transactions)
    on_time_rate   = sum(1 for r in transactions if r.get("flight_on_time") == "1") / len(transactions) * 100

    # Referential integrity: transactions → customers
    cust_id_set = set(cust_ids)
    ref_check_txn = check_referential_integrity(transactions, "customer_id", cust_id_set, "transactions→customers")
    if ref_check_txn["missing_refs"] > 0:
        errors.append(f"flight_transactions: {ref_check_txn['missing_refs']} customer_ids not in customer_master")

    unique_customers_in_txn = len(set(r["customer_id"] for r in transactions))
    if unique_customers_in_txn < THRESHOLDS["min_unique_customers"]:
        errors.append(f"Only {unique_customers_in_txn} unique customers in transactions (min {THRESHOLDS['min_unique_customers']})")

    report["flight_transactions"] = {
        "row_count":               len(transactions),
        "unique_bookings":         len(set(bk_ids)),
        "unique_customers":        unique_customers_in_txn,
        "duplicate_booking_ids":   dup_bks,
        "flight_date_range":       flight_date_range,
        "fare_profile_inr":        fare_profile,
        "total_spend_profile_inr": total_spend_profile,
        "ancillary_profile_inr":   ancillary_profile,
        "miles_earned_profile":    miles_profile,
        "lead_days_profile":       lead_profile,
        "cabin_distribution":      dict(cabin_dist_txn),
        "travel_purpose_distribution": dict(purpose_dist),
        "airline_distribution":    dict(airline_dist),
        "on_time_rate_pct":        round(on_time_rate, 2),
        "referential_integrity":   ref_check_txn,
    }


    # ── Feedback profiling ────────────────────
    fb_profile = {}
    for col in REQUIRED_FEEDBACK_COLS:
        fb_profile[col] = profile_column(feedbacks, col)

    nps_profile  = profile_numeric(feedbacks, "nps_score")
    sat_profile  = profile_numeric(feedbacks, "overall_satisfaction")

    if nps_profile.get("min", 0) < THRESHOLDS["min_nps_score"] or \
       nps_profile.get("max", 11) > THRESHOLDS["max_nps_score"]:
        errors.append("customer_feedback: nps_score out of [0,10] range")

    if sat_profile.get("min", 0) < THRESHOLDS["min_satisfaction"] or \
       sat_profile.get("max", 6) > THRESHOLDS["max_satisfaction"]:
        warnings.append("customer_feedback: overall_satisfaction values outside [1,5]")

    fb_ids = [r["feedback_id"] for r in feedbacks]
    dup_fb = len(fb_ids) - len(set(fb_ids))
    if dup_fb > 0:
        errors.append(f"customer_feedback: {dup_fb} duplicate feedback_ids")

    bk_id_set = set(bk_ids)
    ref_check_fb = check_referential_integrity(feedbacks, "booking_id", bk_id_set, "feedback→transactions")
    if ref_check_fb["missing_refs"] > 0:
        errors.append(f"customer_feedback: {ref_check_fb['missing_refs']} booking_ids not in transactions")

    recommend_rate = sum(1 for r in feedbacks if r.get("would_recommend") == "1") / len(feedbacks) * 100

    report["customer_feedback"] = {
        "row_count":               len(feedbacks),
        "unique_feedbacks":        len(set(fb_ids)),
        "feedback_response_rate":  round(len(feedbacks)/len(transactions)*100, 2),
        "duplicate_feedback_ids":  dup_fb,
        "nps_profile":             nps_profile,
        "satisfaction_profile":    sat_profile,
        "recommendation_rate_pct": round(recommend_rate, 2),
        "referential_integrity":   ref_check_fb,
    }

    # ── Summary ───────────────────────────────
    status = "FAIL" if errors else ("WARN" if warnings else "PASS")
    report["summary"] = {
        "status":        status,
        "error_count":   len(errors),
        "warning_count": len(warnings),
        "errors":        errors,
        "warnings":      warnings,
    }

    exit_code = 1 if errors else 0
    _write_report(output_dir, report, exit_code)
    return exit_code

# ─────────────────────────────────────────────
# Output writers
# ─────────────────────────────────────────────
def _write_report(output_dir, report, exit_code):
    os.makedirs(output_dir, exist_ok=True)

    json_path = os.path.join(output_dir, "data_quality_report.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"  Written: {json_path}")

    txt_path = os.path.join(output_dir, "data_quality_summary.txt")
    lines = []
    lines.append("=" * 70)
    lines.append("AVIATION CUSTOMER ANALYTICS — DATA QUALITY REPORT")
    lines.append("=" * 70)

    summary = report.get("summary", {})
    lines.append(f"Status        : {summary.get('status','?')}")
    lines.append(f"Errors        : {summary.get('error_count', 0)}")
    lines.append(f"Warnings      : {summary.get('warning_count', 0)}")
    lines.append("")

    if summary.get("errors"):
        lines.append("--- ERRORS ---")
        for e in summary["errors"]:
            lines.append(f"  [ERROR] {e}")
        lines.append("")

    if summary.get("warnings"):
        lines.append("--- WARNINGS ---")
        for w in summary["warnings"]:
            lines.append(f"  [WARN]  {w}")
        lines.append("")

    for table in ["customer_master","flight_transactions","customer_feedback"]:
        t = report.get(table, {})
        if not t:
            continue
        lines.append(f"--- {table.upper()} ---")
        lines.append(f"  Rows        : {t.get('row_count','?'):,}")
        if "on_time_rate_pct" in t:
            lines.append(f"  On-time %   : {t['on_time_rate_pct']}%")
        if "feedback_response_rate" in t:
            lines.append(f"  Response %  : {t['feedback_response_rate']}%")
        if "recommendation_rate_pct" in t:
            lines.append(f"  Recommend % : {t['recommendation_rate_pct']}%")
        if "fare_profile_inr" in t:
            fp = t["fare_profile_inr"]
            lines.append(f"  Fare (INR)  : min={fp['min']:,.0f}  median={fp['median']:,.0f}  max={fp['max']:,.0f}")
        if "nps_profile" in t:
            np_ = t["nps_profile"]
            lines.append(f"  NPS         : mean={np_['mean']}  min={np_['min']}  max={np_['max']}")
        lines.append("")

    lines.append(f"Exit code: {exit_code}  ({'PASS' if exit_code == 0 else 'FAIL'})")
    lines.append("=" * 70)

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  Written: {txt_path}")
    print("\n".join(lines))


# ─────────────────────────────────────────────
# CLI Entry-point
# ─────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate aviation analytics dataset")
    parser.add_argument("--customers",    default="data/customer_master.csv")
    parser.add_argument("--transactions", default="data/flight_transactions.csv")
    parser.add_argument("--feedback",     default="data/customer_feedback.csv")
    parser.add_argument("--output_dir",   default="outputs/")
    args = parser.parse_args()

    code = validate(args.customers, args.transactions, args.feedback, args.output_dir)
    sys.exit(code)
