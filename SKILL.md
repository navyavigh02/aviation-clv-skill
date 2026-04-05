# SKILL.md — Aviation Customer Lifetime Value (CLV) Segmentation

## Overview

This skill instructs an LLM to perform a complete, end-to-end customer analytics workflow
for the **aviation / airline loyalty** domain. It takes real or synthetic passenger booking
data and produces customer segments, profiles, and actionable business recommendations.

**Domain**: Customer Analytics — Aviation / Airline Loyalty Programmes  
**Output**: Multi-section HTML report with visualisations + CSV segment assignments  
**Seed**: 42 (all scripts must set `random.seed(42)` for full reproducibility)

---

## Input Requirements

### 1. Dataset Input (CSV files)

The skill accepts three CSV files. Run `scripts/validate_data.py` before any analysis.

#### customer_master.csv — Required columns:
| Column | Type | Constraint |
|---|---|---|
| customer_id | string | Unique, non-null PK |
| age | integer | 18–75 |
| gender | string | M / F / Other |
| home_airport | string | 3-letter IATA code |
| loyalty_tier | string | Bronze / Silver / Gold / Platinum |
| loyalty_points | integer | ≥ 0 |
| enrolment_date | date | YYYY-MM-DD, parseable |
| preferred_cabin | string | Economy / Premium Economy / Business / First |

Optional: first_name, last_name, email, home_city, home_country

#### flight_transactions.csv — Required columns:
| Column | Type | Constraint |
|---|---|---|
| booking_id | string | Unique PK |
| customer_id | string | FK → customer_master |
| flight_date | date | YYYY-MM-DD, ≥ booking_date |
| cabin_class | string | Economy / Premium Economy / Business / First |
| total_spend_inr | float | > 0 |
| base_fare_inr | float | > 0 |
| ancillary_spend_inr | float | ≥ 0 |
| miles_earned | integer | ≥ 0 |
| travel_purpose | string | Leisure / Business / Family Visit / Medical / Education |
| booking_lead_days | integer | 0–180 |
| flight_on_time | integer | 0 or 1 |

#### customer_feedback.csv — Required columns:
| Column | Type | Constraint |
|---|---|---|
| feedback_id | string | Unique PK |
| booking_id | string | FK → flight_transactions |
| customer_id | string | FK → customer_master |
| overall_satisfaction | float | 1.0–5.0 |
| nps_score | integer | 0–10 |
| would_recommend | integer | 0 or 1 |

### 2. User Configuration Inputs

| Parameter | Type | Default | Valid Range | Description |
|---|---|---|---|---|
| analysis_date | date | max(flight_date) + 1 day | Any future date | Reference date for recency calculation |
| num_segments | integer | 4 | 3–7 | Target number of customer segments |
| k_lo | integer | 3 | 2–5 | Minimum k for algorithm sweep |
| k_hi | integer | 5 | k_lo+1 to 8 | Maximum k for algorithm sweep |
| algorithms | string | kmeans,hierarchical | kmeans,hierarchical,dbscan | Algorithms to run |
| min_segment_pct | float | 5.0 | 2.0–15.0 | Minimum % of customers per segment |
| confidence_level | float | 0.95 | 0.90–0.99 | For future interval estimation |
| currency | string | INR | Any ISO code | Display currency label |

---

## Mandatory Pipeline Stages

### Stage 1 — Data Validation & Profiling

**Script**: `python scripts/validate_data.py --customers <path> --transactions <path> --feedback <path> --output_dir outputs/`

**What to compute**:
1. For each file: row count, column count, data types, null counts per column (as absolute and %)
2. Primary key uniqueness check (customer_id, booking_id, feedback_id)
3. Referential integrity: every transaction.customer_id must exist in customer_master; every feedback.booking_id must exist in transactions
4. Value domain checks: loyalty_tier ∈ {Bronze, Silver, Gold, Platinum}; cabin_class ∈ {Economy, Premium Economy, Business, First}; NPS ∈ [0,10]; satisfaction ∈ [1,5]; fares > 0
5. Date parseability and range: flight_date must be parseable; date span ≥ 6 months
6. Numeric distribution: min, p25, median, p75, max, mean, std for base_fare_inr and total_spend_inr

**Validation gates** (STOP if violated):
- Any required column missing → ERROR: "Missing required column: <name>"
- Null% > 5% in any required column → ERROR
- Duplicate PKs → ERROR
- Referential integrity failure > 0 rows → ERROR
- All base_fare_inr < 0 → ERROR

**Outputs**:
- `outputs/data_quality_report.json` — machine-readable full profile
- `outputs/data_quality_summary.txt` — human-readable summary with PASS/WARN/FAIL status

**Do NOT proceed to Stage 2 if exit code = 1.**

---

### Stage 2 — Feature Engineering

**Script**: `python scripts/feature_engineering.py --analysis_date <YYYY-MM-DD> --output_dir outputs/`

**What to compute per customer_id** (formulae are exact — do not deviate):

```
recency_days           = (analysis_date − max(flight_date)).days
                         If customer has no flights: 9999
frequency              = COUNT(bookings where flight_date ≤ analysis_date)
monetary_total_inr     = SUM(total_spend_inr for all flights ≤ analysis_date)
avg_fare_inr           = monetary_total_inr / frequency  (0 if frequency=0)
avg_ancillary_inr      = SUM(ancillary_spend_inr) / frequency
cabin_upgrade_ratio    = COUNT(cabin_class IN {Business, First}) / frequency
route_diversity        = NUNIQUE(CONCAT(origin_airport, '-', destination_airport))
avg_booking_lead_days  = MEAN(booking_lead_days)
business_travel_ratio  = COUNT(travel_purpose = 'Business') / frequency
on_time_experience_pct = COUNT(flight_on_time = 1) / frequency × 100
loyalty_points         = from customer_master (no computation needed)
membership_months      = (analysis_date − enrolment_date).days / 30.44
avg_nps                = MEAN(nps_score from feedback joined by customer_id)
avg_satisfaction       = MEAN(overall_satisfaction from feedback)
```

**Composite scores** (all in [0,1], min-max normalised across full dataset):
```
value_score    = 0.60 × norm(monetary_total_inr) + 0.40 × norm(frequency)
loyalty_score  = 0.40 × norm(loyalty_points) + 0.35 × norm(tier_numeric) + 0.25 × norm(membership_months)
                 where tier_numeric: Bronze=1, Silver=2, Gold=3, Platinum=4
engagement_score = 0.40 × (avg_nps/10) + 0.35 × ((avg_satisfaction-1)/4) + 0.25 × recommendation_rate
                   Set to blank string if customer has no feedback
```

**RFM quintile scoring** (assign 1=worst, 5=best independently for R, F, M):
```
r_score: rank recency_days ascending  → sort ascending, quintile 5 = lowest recency (most recent)
f_score: rank frequency descending    → quintile 5 = most flights
m_score: rank monetary descending     → quintile 5 = highest spend
rfm_score = r_score + f_score + m_score   [range: 3–15]
```

**Output**: `outputs/rfm_features.csv` with all 32 columns as defined in FIELDNAMES list.

**Validation**: Verify all 2,000 (or N) customers appear in output; no null monetary or recency values.

---

### Stage 3 — Modelling & Analysis

**Script**: `python scripts/run_models.py --features outputs/rfm_features.csv --algorithms <list> --k_range <lo,hi> --output_dir outputs/`

**Feature matrix for clustering** (7 features, Z-score standardised):
```
[recency_days, frequency, monetary_total_inr, cabin_upgrade_ratio,
 route_diversity, business_travel_ratio, loyalty_points]
```

**Standardisation formula**:
```
z = (x − mean(x)) / std(x)   per column across all customers
```

**K-Means**: Use k-means++ initialisation (distances to existing centroids). Max 200 iterations. Compute inertia (within-cluster sum-of-squared distances).

**Hierarchical**: Ward linkage approximated by minimum centroid distance. For N > 1000: subsample 800 points, compute centroids, assign full dataset by nearest centroid.

**DBSCAN**: Grid search eps ∈ {0.5, 0.8, 1.0, 1.2, 1.5, 2.0}, min_samples=5. Skip if clusters < 2, > 10, or noise > 40%.

---

### Stage 4 — Model/Result Validation

**For each (algorithm, k) configuration, compute**:

```
Silhouette Score = mean over all points of:
  s(i) = (b(i) − a(i)) / max(a(i), b(i))
  where a(i) = mean intra-cluster distance
        b(i) = min mean distance to any other cluster

Davies-Bouldin Index = (1/k) × SUM_i [ max_{j≠i} (scatter_i + scatter_j) / dist(centroid_i, centroid_j) ]
  where scatter_c = mean distance of points to cluster centroid c

Calinski-Harabasz Score = [between_cluster_SS / (k-1)] / [within_cluster_SS / (n-k)]

Cluster balance check:
  - Min segment size ≥ min_segment_pct% of total customers
  - Max segment size ≤ 40% of total customers
```

**Model selection rule**:
1. Filter to configurations where balance check passes
2. Among balanced configurations, select highest Silhouette score
3. If no balanced configuration: select highest Silhouette score and log WARNING

**Silhouette interpretation**:
- ≥ 0.70: Excellent — clusters very well separated
- ≥ 0.50: Good — meaningful structure
- ≥ 0.25: Acceptable — some structure (typical for airline RFM data)
- < 0.25: Poor — warn user, clusters may not be meaningful

**Segment labelling**: Sort clusters by mean rfm_score descending. Assign labels:
- Rank 0 (highest rfm_score): Champions
- Rank 1: Loyal Flyers
- Rank 2: Potential Loyalists
- Rank 3: At-Risk Travellers
- Rank 4: Hibernating
- Rank 5: Lost Passengers
- Rank 6: New Passengers

---

### Stage 5 — Insight Generation & Interpretation

**Per segment, compute from REFERENCE.md archetypes**:

1. Mean values of all 32 features → segment profile table
2. Revenue at stake: sum of monetary_total_inr for that segment
3. Premium cabin affinity: cabin_upgrade_ratio (compare to population mean in REFERENCE.md)
4. NPS vs population benchmark (benchmark: 7.0 per REFERENCE.md)
5. Assign recommended actions from REFERENCE.md action templates

**Business interpretation rules** (from REFERENCE.md):
- Champions: recency < 60d AND frequency > 15 AND monetary > ₹2,000,000 → confirm label
- At-Risk: recency > 180d AND was previously high-frequency → urgent action
- Hibernating: recency > 365d → low-cost re-activation only

---

### Stage 6 — Report Generation

**Script**: `python scripts/generate_report.py --output_dir outputs/`

**Output**: `outputs/aviation_clv_report.html`

**Required sections** (in order — do not omit any):
1. Executive Summary with 6 KPI cards (total customers, segments, silhouette, transactions processed, features, algorithms)
2. End-to-End Pipeline diagram (6 stages with inputs → outputs)
3. Data Quality Summary table (3 rows, one per file)
4. RFM Feature Analysis with 3 charts: donut (segment distribution), bar (avg spend by segment), radar (segment profiles on 5 dimensions)
5. Modelling Methodology — algorithm rationale table + validation results table + selected model explanation
6. Customer Segment Profiles — one card per segment with 8 metrics + recommended actions + revenue note + channel
7. Business Recommendations Summary table (segment, size, priority action, metric to track, timeline)
8. Parameter Sensitivity Analysis table (k vs silhouette vs balance)
9. Limitations & Assumptions table (7 rows minimum)
10. Data Appendix with dataset summary + run commands

**Chart specifications**:
- Chart 1: `doughnut` — labels = segment names, data = customer counts, backgroundColor = per-segment hex colours
- Chart 2: `bar` — x = segment names sorted by desc monetary, y = avg lifetime spend in INR
- Chart 3: `radar` — axes: Value Score×5, Loyalty Score×5, Cabin Upgrade×5, Business Travel×5, NPS×5
- Chart 4: `bar` — x = "algorithm k=N" labels, y = silhouette score, selected model highlighted in dark blue

**Segment card must include** (exact fields):
- Avg Recency (days), Avg Flights, Avg Lifetime Spend (₹), Avg Fare (₹), Premium Cabin %, Business Travel %, Avg NPS, Satisfaction score
- Recommended actions list (from REFERENCE.md)
- Revenue at stake note
- Channel recommendation

---

## Error Handling

If validation fails (exit code 1):
```
ANALYSIS HALTED — DATA QUALITY FAILURE
Error: <specific error message from data_quality_summary.txt>
Required fix: <actionable instruction>
Example: "column 'base_fare_inr' has 12% null values (threshold: 5%). 
          Fix: impute with median fare for that cabin class or remove affected rows."
```

If silhouette < 0.25:
```
WARNING: Low cluster separation (silhouette = X.XX).
Segments may not be clearly distinct. Possible causes:
1. Insufficient date range (< 6 months)
2. Too few customers (< 500 recommended)
3. Homogeneous customer base
Recommendation: Proceed with caution; validate segments with business team.
```

---

## Testing Scenarios

### Scenario 1 — Happy Path (Full Run)
- Input: 2,000 customers, 34,299 transactions, 10,299 feedback rows, seed=42
- Expected: PASS validation, 4 segments, silhouette ≈ 0.33, report generated
- Verify: All 6 pipeline stages execute, all output files created

### Scenario 2 — Bad Data (Validation Failure)
- Input: Inject 50 rows with negative base_fare_inr = -5000 into transactions
- Expected: validate_data.py exits with code 1, error message: "N negative base_fare_inr values"
- Verify: Pipeline halts at Stage 1, no partial outputs

### Scenario 3 — Sparse Feedback (Missing Feature)
- Input: Empty customer_feedback.csv (headers only)
- Expected: Feature engineering completes, engagement_score = "" for all customers
- Verify: Run models ignores engagement_score; report notes missing feedback data

---

## File Structure

```
aviation-clv-skill/
├── SKILL.md                          # This file — full pipeline instructions
├── REFERENCE.md                      # Domain knowledge, benchmarks, archetypes
├── scripts/
│   ├── generate_synthetic_data.py    # Synthetic data generator (seed=42)
│   ├── validate_data.py              # Stage 1: Data validation & profiling
│   ├── feature_engineering.py        # Stage 2: RFM + 7 aviation features
│   ├── run_models.py                 # Stage 3+4: Multi-algo clustering + validation
│   └── generate_report.py            # Stage 6: HTML report with Chart.js
├── data/
│   ├── customer_master.csv           # 2,000 passenger records
│   ├── flight_transactions.csv       # 34,299 flight bookings
│   ├── customer_feedback.csv         # 10,299 satisfaction surveys
│   └── data_dictionary.md            # Column definitions and valid values
├── outputs/
│   ├── data_quality_report.json      # Stage 1 output
│   ├── data_quality_summary.txt      # Stage 1 human-readable
│   ├── rfm_features.csv              # Stage 2 output (2,000 rows × 32 cols)
│   ├── feature_engineering_log.txt   # Stage 2 log with all formulas
│   ├── customer_segments.csv         # Stage 3+4 output
│   ├── models_comparison.txt         # Stage 4 comparison table
│   ├── models_output.json            # Stage 4 full results JSON
│   └── aviation_clv_report.html      # Stage 6 final report
└── templates/
    └── report_template.html          # Report structure reference
```
