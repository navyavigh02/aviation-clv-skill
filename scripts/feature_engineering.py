"""
feature_engineering.py
-----------------------
Aviation Customer Analytics — Stage 2: Feature Engineering

Computes RFM (Recency/Frequency/Monetary) features plus aviation-specific
enrichments for each customer:

  Core RFM:
    recency_days       — days since last flight
    frequency          — total number of flights
    monetary_total_inr — total lifetime spend

  Aviation-Specific:
    avg_fare_inr           — average fare per booking
    avg_ancillary_inr      — average ancillary spend
    cabin_upgrade_ratio    — % bookings in Business/First
    route_diversity        — number of unique routes flown
    avg_booking_lead_days  — avg days between booking & travel
    business_travel_ratio  — % trips marked as Business
    on_time_experience_pct — % flights that were on-time
    loyalty_points         — current points balance
    membership_months      — months since loyalty enrolment
    avg_nps                — mean NPS score given (from feedback)
    avg_satisfaction       — mean overall satisfaction score

  Derived Scores (0–1, higher = better):
    value_score     — composite of monetary + frequency
    loyalty_score   — composite of points + tier + membership
    engagement_score— composite of feedback + recommendation rate

Usage:
    python scripts/feature_engineering.py \
        --customers     data/customer_master.csv \
        --transactions  data/flight_transactions.csv \
        --feedback      data/customer_feedback.csv \
        --analysis_date 2025-01-01 \
        --output_dir    outputs/

Output:
    outputs/rfm_features.csv
    outputs/feature_engineering_log.txt
"""

import argparse
import csv
import os
import math
from datetime import date
from collections import defaultdict

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def load_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def safe_float(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default

def safe_date(v):
    try:
        return date.fromisoformat(v.strip())
    except Exception:
        return None

def min_max_scale(val, lo, hi):
    """Normalise value to [0, 1]."""
    if hi == lo:
        return 0.0
    return max(0.0, min(1.0, (val - lo) / (hi - lo)))

def write_csv(path, rows, fieldnames):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Written: {path}  ({len(rows):,} rows)")

# ─────────────────────────────────────────────
# Tier numeric encoding
# ─────────────────────────────────────────────
TIER_SCORE = {"Bronze": 1, "Silver": 2, "Gold": 3, "Platinum": 4}
PREMIUM_CABINS = {"Business", "First"}

# ─────────────────────────────────────────────
# Main feature computation
# ─────────────────────────────────────────────
def compute_features(customers, transactions, feedbacks, analysis_date: date):
    log_lines = []
    log_lines.append(f"Analysis date : {analysis_date}")
    log_lines.append(f"Customers     : {len(customers):,}")
    log_lines.append(f"Transactions  : {len(transactions):,}")
    log_lines.append(f"Feedbacks     : {len(feedbacks):,}")
    log_lines.append("")

    # ── Index customers ───────────────────────
    cust_map = {r["customer_id"]: r for r in customers}

    # ── Aggregate transactions per customer ───
    txn_by_cust = defaultdict(list)
    for t in transactions:
        cid = t["customer_id"]
        fd  = safe_date(t["flight_date"])
        if fd and fd <= analysis_date:
            txn_by_cust[cid].append(t)

    # ── Aggregate feedback per customer ───────
    fb_by_cust = defaultdict(list)
    for f in feedbacks:
        fb_by_cust[f["customer_id"]].append(f)

    # ── Build feature rows ────────────────────
    feature_rows = []

    for cid, cust in cust_map.items():
        txns = txn_by_cust[cid]
        fbs  = fb_by_cust[cid]

        # ── RFM core ──────────────────────────
        if txns:
            flight_dates = [safe_date(t["flight_date"]) for t in txns if safe_date(t["flight_date"])]
            flight_dates = [d for d in flight_dates if d]
            last_flight  = max(flight_dates) if flight_dates else None
            recency_days = (analysis_date - last_flight).days if last_flight else 9999
        else:
            recency_days = 9999
            last_flight  = None

        frequency = len(txns)
        monetary  = sum(safe_float(t["total_spend_inr"]) for t in txns)

        # ── Aviation-specific features ────────
        avg_fare        = monetary / frequency if frequency else 0.0
        avg_ancillary   = (sum(safe_float(t["ancillary_spend_inr"]) for t in txns) / frequency) if frequency else 0.0
        premium_bookings = sum(1 for t in txns if t["cabin_class"] in PREMIUM_CABINS)
        cabin_upgrade_ratio = premium_bookings / frequency if frequency else 0.0

        routes = set(
            f"{t['origin_airport']}-{t['destination_airport']}" for t in txns
        )
        route_diversity = len(routes)

        lead_days = [safe_float(t["booking_lead_days"]) for t in txns]
        avg_lead  = sum(lead_days) / len(lead_days) if lead_days else 0.0

        business_trips = sum(1 for t in txns if t["travel_purpose"] == "Business")
        biz_ratio = business_trips / frequency if frequency else 0.0

        on_time_count = sum(1 for t in txns if t.get("flight_on_time") == "1")
        on_time_pct   = on_time_count / frequency * 100 if frequency else 0.0

        loyalty_points   = safe_float(cust.get("loyalty_points", 0))
        enrol_date       = safe_date(cust.get("enrolment_date", ""))
        membership_months = ((analysis_date - enrol_date).days / 30.44) if enrol_date else 0.0
        tier_num         = TIER_SCORE.get(cust.get("loyalty_tier", "Bronze"), 1)

        # ── Feedback aggregations ─────────────
        if fbs:
            avg_nps  = sum(safe_float(f["nps_score"]) for f in fbs) / len(fbs)
            avg_sat  = sum(safe_float(f["overall_satisfaction"]) for f in fbs) / len(fbs)
            rec_rate = sum(1 for f in fbs if f.get("would_recommend") == "1") / len(fbs)
        else:
            avg_nps  = None
            avg_sat  = None
            rec_rate = None

        feature_rows.append({
            "customer_id":            cid,
            "loyalty_tier":           cust.get("loyalty_tier","Bronze"),
            "tier_numeric":           tier_num,
            "home_airport":           cust.get("home_airport",""),
            "age":                    safe_float(cust.get("age", 0)),
            "gender":                 cust.get("gender",""),
            "preferred_cabin":        cust.get("preferred_cabin","Economy"),
            "enrolment_date":         cust.get("enrolment_date",""),
            "membership_months":      round(membership_months, 1),
            "loyalty_points":         int(loyalty_points),
            "last_flight_date":       str(last_flight) if last_flight else "",
            "recency_days":           recency_days,
            "frequency":              frequency,
            "monetary_total_inr":     round(monetary, 2),
            "avg_fare_inr":           round(avg_fare, 2),
            "avg_ancillary_inr":      round(avg_ancillary, 2),
            "cabin_upgrade_ratio":    round(cabin_upgrade_ratio, 4),
            "route_diversity":        route_diversity,
            "avg_booking_lead_days":  round(avg_lead, 1),
            "business_travel_ratio":  round(biz_ratio, 4),
            "on_time_experience_pct": round(on_time_pct, 2),
            "avg_nps":                round(avg_nps, 2) if avg_nps is not None else "",
            "avg_satisfaction":       round(avg_sat, 2) if avg_sat is not None else "",
            "recommendation_rate":    round(rec_rate, 4) if rec_rate is not None else "",
            "feedback_count":         len(fbs),
        })

    # ── Normalised composite scores ───────────
    monets = [r["monetary_total_inr"] for r in feature_rows]
    freqs  = [r["frequency"] for r in feature_rows]
    pts    = [r["loyalty_points"] for r in feature_rows]
    mems   = [r["membership_months"] for r in feature_rows]

    min_m, max_m = min(monets), max(monets)
    min_f, max_f = min(freqs),  max(freqs)
    min_p, max_p = min(pts),    max(pts)
    min_me,max_me= min(mems),   max(mems)

    for r in feature_rows:
        m_sc  = min_max_scale(r["monetary_total_inr"], min_m, max_m)
        f_sc  = min_max_scale(r["frequency"],          min_f, max_f)
        p_sc  = min_max_scale(r["loyalty_points"],     min_p, max_p)
        me_sc = min_max_scale(r["membership_months"],  min_me,max_me)
        t_sc  = (r["tier_numeric"] - 1) / 3.0          # 0..1

        r["value_score"]   = round(0.60 * m_sc + 0.40 * f_sc, 4)
        r["loyalty_score"] = round(0.40 * p_sc + 0.35 * t_sc + 0.25 * me_sc, 4)

        # engagement score from feedback (if available)
        if r["avg_nps"] != "" and r["avg_satisfaction"] != "":
            nps_sc = safe_float(r["avg_nps"]) / 10.0
            sat_sc = (safe_float(r["avg_satisfaction"]) - 1) / 4.0
            rec_sc = safe_float(r["recommendation_rate"]) if r["recommendation_rate"] != "" else 0.5
            r["engagement_score"] = round(0.4 * nps_sc + 0.35 * sat_sc + 0.25 * rec_sc, 4)
        else:
            r["engagement_score"] = ""

    # ── RFM quintile scoring (1–5) ────────────
    # Lower recency → better → reverse sort
    sorted_by_recency = sorted(feature_rows, key=lambda x: x["recency_days"])
    sorted_by_freq    = sorted(feature_rows, key=lambda x: x["frequency"], reverse=True)
    sorted_by_money   = sorted(feature_rows, key=lambda x: x["monetary_total_inr"], reverse=True)

    n = len(feature_rows)

    def quintile_score(idx, n):
        """1 (bottom 20%) to 5 (top 20%)"""
        return 5 - min(4, int(idx / n * 5))

    rec_rank  = {r["customer_id"]: quintile_score(i, n) for i, r in enumerate(sorted_by_recency)}
    freq_rank = {r["customer_id"]: quintile_score(i, n) for i, r in enumerate(sorted_by_freq)}
    mon_rank  = {r["customer_id"]: quintile_score(i, n) for i, r in enumerate(sorted_by_money)}

    for r in feature_rows:
        cid = r["customer_id"]
        r["r_score"] = rec_rank[cid]
        r["f_score"] = freq_rank[cid]
        r["m_score"] = mon_rank[cid]
        r["rfm_score"] = r["r_score"] + r["f_score"] + r["m_score"]  # 3–15

    # ── Log summary ───────────────────────────
    active = sum(1 for r in feature_rows if r["frequency"] > 0)
    inactive = n - active
    avg_recency = sum(r["recency_days"] for r in feature_rows if r["recency_days"] < 9999) / max(1, active)
    avg_monetary = sum(r["monetary_total_inr"] for r in feature_rows) / n

    log_lines.append(f"Features computed : {n:,}")
    log_lines.append(f"Active customers  : {active:,}")
    log_lines.append(f"Inactive (0 txns) : {inactive:,}")
    log_lines.append(f"Avg recency (days): {avg_recency:.0f}")
    log_lines.append(f"Avg monetary (INR): {avg_monetary:,.0f}")
    log_lines.append("")
    log_lines.append("FEATURE FORMULAS:")
    log_lines.append("  recency_days           = (analysis_date − max(flight_date)).days")
    log_lines.append("  frequency              = count of flight bookings ≤ analysis_date")
    log_lines.append("  monetary_total_inr     = sum(total_spend_inr)")
    log_lines.append("  avg_fare_inr           = monetary_total_inr / frequency")
    log_lines.append("  cabin_upgrade_ratio    = count(Business+First) / frequency")
    log_lines.append("  route_diversity        = len(unique origin-destination pairs)")
    log_lines.append("  business_travel_ratio  = count(purpose=Business) / frequency")
    log_lines.append("  on_time_experience_pct = count(flight_on_time=1) / frequency × 100")
    log_lines.append("  value_score            = 0.6×norm(monetary) + 0.4×norm(frequency)")
    log_lines.append("  loyalty_score          = 0.4×norm(points) + 0.35×norm(tier) + 0.25×norm(months)")
    log_lines.append("  r_score / f_score / m_score = quintile ranks (1=worst, 5=best)")
    log_lines.append("  rfm_score              = r_score + f_score + m_score  [3–15]")

    return feature_rows, log_lines


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────
FIELDNAMES = [
    "customer_id","loyalty_tier","tier_numeric","home_airport","age","gender",
    "preferred_cabin","enrolment_date","membership_months","loyalty_points",
    "last_flight_date","recency_days","frequency","monetary_total_inr",
    "avg_fare_inr","avg_ancillary_inr","cabin_upgrade_ratio","route_diversity",
    "avg_booking_lead_days","business_travel_ratio","on_time_experience_pct",
    "avg_nps","avg_satisfaction","recommendation_rate","feedback_count",
    "value_score","loyalty_score","engagement_score",
    "r_score","f_score","m_score","rfm_score",
]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Aviation RFM + feature engineering")
    parser.add_argument("--customers",     default="data/customer_master.csv")
    parser.add_argument("--transactions",  default="data/flight_transactions.csv")
    parser.add_argument("--feedback",      default="data/customer_feedback.csv")
    parser.add_argument("--analysis_date", default="2025-01-01")
    parser.add_argument("--output_dir",    default="outputs/")
    args = parser.parse_args()

    print("=== Stage 2: Feature Engineering ===")
    customers    = load_csv(args.customers)
    transactions = load_csv(args.transactions)
    feedbacks    = load_csv(args.feedback)
    analysis_date = date.fromisoformat(args.analysis_date)

    feature_rows, log_lines = compute_features(customers, transactions, feedbacks, analysis_date)

    os.makedirs(args.output_dir, exist_ok=True)
    write_csv(
        os.path.join(args.output_dir, "rfm_features.csv"),
        feature_rows,
        FIELDNAMES
    )

    log_path = os.path.join(args.output_dir, "feature_engineering_log.txt")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines))
    print(f"  Written: {log_path}")
    print("\n".join(log_lines))
    print("\nStage 2 complete.")
