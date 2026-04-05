# REFERENCE.md — Aviation Customer Analytics Domain Knowledge

## Purpose

This file contains all domain-specific knowledge the LLM must consult when interpreting
results, labelling segments, and generating recommendations. It must NOT hallucinate
industry facts — all benchmarks and archetypes below are the authoritative source.

---

## 1. Airline Industry Benchmarks

### Customer Lifetime Value (CLV) Benchmarks — India-Based Carriers
| Segment | Avg Annual Flights | Avg Annual Spend (INR) | Typical Tier | CLV Multiplier |
|---|---|---|---|---|
| Ultra-high value (top 5%) | 25–40 | ₹8,00,000–₹25,00,000 | Platinum | 12× average |
| High value (top 15%) | 12–25 | ₹3,00,000–₹8,00,000 | Gold/Platinum | 5× average |
| Mid value (next 30%) | 5–12 | ₹80,000–₹3,00,000 | Silver/Gold | 2× average |
| Low value (bottom 50%) | 1–5 | ₹15,000–₹80,000 | Bronze/Silver | 0.4× average |

### NPS Industry Benchmarks — Aviation
| Metric | Poor | Industry Average | Good | Excellent |
|---|---|---|---|---|
| NPS Score (0–10 scale) | < 5.0 | 6.5–7.0 | 7.0–8.0 | > 8.5 |
| Overall Satisfaction (1–5) | < 3.0 | 3.4–3.7 | 3.8–4.2 | > 4.3 |
| On-Time Rate | < 70% | 78–82% | 83–87% | > 88% |
| Recommend Rate | < 40% | 50–55% | 60–70% | > 75% |

### Cabin Class Revenue Distribution
| Cabin | % of Passengers | % of Revenue | Avg Fare Index |
|---|---|---|---|
| Economy | 60–65% | 30–35% | 1.0× |
| Premium Economy | 12–15% | 15–18% | 3.5× |
| Business | 18–22% | 38–42% | 8–10× |
| First | 3–6% | 12–15% | 20–30× |

### Booking Behaviour Benchmarks
| Metric | Leisure | Business | Premium |
|---|---|---|---|
| Avg booking lead days | 45–90d | 3–14d | 7–30d |
| Cabin upgrade rate | 5–10% | 30–50% | 60–80% |
| Ancillary attach rate | 8–12% | 5–8% | 15–25% |
| Repeat booking rate (90d) | 15–25% | 60–75% | 40–60% |

---

## 2. Customer Segment Archetypes

### Champions
**Definition**: Highest RFM score (rfm_score ≥ 12). Flew recently, frequently, spend heavily.

**Typical profile**:
- Recency: < 60 days
- Frequency: ≥ 15 flights/year
- Monetary: > ₹20,00,000 lifetime (top 5%)
- Cabin: > 50% Business/First
- Tier: Platinum / Gold
- NPS: > 8.0
- Business travel: > 40%

**What they mean**: The airline's most valuable passengers. Likely frequent business travellers or affluent leisure flyers. They have high switching costs (accrued miles, tier status) but will defect if service quality drops.

**Risk**: Despite loyalty, price sensitivity to competing offers from rival airlines is real at this tier. 40% are estimated to hold competitor status simultaneously.

**Action templates**:
1. Platinum Fast-Track: waive qualifying criteria for tier renewal for 1 year
2. Complimentary lounge access for all travel, including domestic
3. Seat upgrade confirmation at booking (not gate) for all revenue flights
4. Invite to advisory panel with direct access to product team
5. Proactive service recovery: auto-compensate if delayed > 2 hours

---

### Loyal Flyers
**Definition**: High RFM score (rfm_score 10–12). Fly regularly, decent spend, but not yet Champions.

**Typical profile**:
- Recency: < 90 days
- Frequency: 8–15 flights/year
- Monetary: ₹5,00,000–₹20,00,000 lifetime
- Cabin: 20–50% Business/First
- Tier: Silver / Gold
- NPS: 6.5–7.5
- Business travel: 25–40%

**What they mean**: The core, reliable revenue base. Most are 1–2 steps from becoming Champions. They respond well to tier progression incentives and feel valued when recognised.

**Action templates**:
1. Double miles on next 5 bookings (accelerator programme)
2. Business cabin trial offer: 50% off upgrade for one-way sector
3. Quarterly status progress report with personalised milestone email
4. Family miles sharing: extend loyalty benefits to spouse/children

---

### Potential Loyalists
**Definition**: Mid RFM score (rfm_score 6–10). Some flights, moderate spend, haven't committed fully.

**Typical profile**:
- Recency: 30–180 days
- Frequency: 3–8 flights/year
- Monetary: ₹80,000–₹5,00,000 lifetime
- Cabin: mostly Economy
- Tier: Bronze / Silver
- NPS: 5.5–7.0
- Mix of leisure and business

**What they mean**: The largest segment by volume. These passengers choose the airline for some trips but split wallet with competitors. They are price-sensitive but respond to value-adds.

**Action templates**:
1. Second booking incentive: bonus miles if booked within 60 days of last flight
2. Route affinity targeting: identify most-used route, offer exclusive fare alerts
3. Ancillary bundle (meal + extra baggage) at 10% discount, presented at search
4. Milestone communication: "You're 60% of the way to Silver tier"

---

### At-Risk Travellers
**Definition**: Declining RFM (previously mid-high, now recency-poor). rfm_score 5–8 but recency > 120d.

**Typical profile**:
- Recency: 120–365 days
- Frequency: previously ≥ 5/year, now declining
- Monetary: moderate to high historical spend
- Tier: Silver to Gold
- Possible NPS: 4–6 (may have had a bad experience)

**What they mean**: These customers used to fly with the airline but have drifted. The cause is typically: bad experience (delay, lost baggage), better competitor offer, or life change (moved city, changed job). Urgency is high — recovery is much cheaper than acquisition.

**Action templates**:
1. Win-back offer: 30% fare discount, valid 30 days, no blackout dates
2. Service recovery: if NPS < 6 in last feedback, trigger apology + ₹2,000 voucher
3. Points expiry reminder: "Your X,XXX miles expire in 90 days"
4. For Gold/Platinum at-risk: personal outreach from loyalty team within 7 days

---

### Hibernating
**Definition**: No activity for 12–24 months. rfm_score 3–6, recency > 365d.

**Typical profile**:
- Recency: > 365 days
- Frequency: low (1–3 historical flights)
- Monetary: < ₹80,000 lifetime
- Tier: Bronze (likely expired)
- NPS: unknown or < 5

**What they mean**: Low-cost engagement only. Most hibernating customers are either permanently lost or occasional flyers who travel infrequently by nature (once every 2–3 years). Mass re-activation campaigns have < 5% effectiveness; targeted, personalised nudges work better.

**Action templates**:
1. Re-activation email: "We miss you" + 40% discount, 14-day booking window
2. Opt-in survey: understand reason for absence
3. Seasonal inspiration: holiday travel ideas (low-commitment content)
4. Do NOT invest in phone outreach (negative ROI at this segment value)

---

### Lost Passengers
**Definition**: Churned. No activity > 24 months. Points likely expired.

**Action**: Email-only; segment for exclusion from premium campaigns; preserve in database for 12 months then archive.

---

### New Passengers
**Definition**: Enrolled < 6 months, 1–3 flights. Not yet segmentable by RFM pattern.

**Action**: Onboarding sequence; first booking experience optimisation; tier progress communication.

---

## 3. Feature Interpretation Guidelines

### Recency
- < 30 days: Very recent — high engagement
- 30–90 days: Active — normal inter-flight period for mid-frequency flyers
- 90–180 days: Cooling — monitor
- 180–365 days: At-risk — trigger win-back
- > 365 days: Hibernating — minimal investment

### Cabin Upgrade Ratio
- < 10%: Economy traveller — price-led
- 10–30%: Occasional upgrader — opportunity for targeted upgrade offers
- 30–60%: Premium-inclined — respond to upgrade bundles
- > 60%: Premium-first — treat as high-value by default

### Business Travel Ratio
- < 15%: Leisure dominant — price sensitive, seasonal demand
- 15–40%: Mixed — both price and convenience matter
- > 40%: Business dominant — convenience, reliability, status more important than price

### Route Diversity
- 1–2 routes: Point-to-point commuter — route-specific offers effective
- 3–5 routes: Regional traveller — network connectivity matters
- > 5 routes: Network traveller — global alliance benefits relevant

### NPS Interpretation (0–10 scale)
- 9–10: Promoters — ask for referrals, testimonials
- 7–8: Passives — upgrade to promoter with personalised touch
- 0–6: Detractors — service recovery mandatory before marketing

---

## 4. Recommendation Channels & Economics

| Channel | CPM (INR) | Response Rate | Best For |
|---|---|---|---|
| Dedicated RM call | ₹800–₹1,200/call | 40–60% | Champions, At-Risk Gold+ |
| Push notification | ₹0.50–₹2 | 5–12% | All active app users |
| Email personalised | ₹1–₹5 | 8–15% | Loyal, Potential Loyalists |
| Email batch | ₹0.10–₹0.50 | 2–5% | Hibernating, Lost |
| Direct mail | ₹80–₹150 | 3–8% | Ultra-high value, Platinum |
| SMS | ₹0.30–₹0.80 | 15–25% | At-risk, time-sensitive |

---

## 5. Algorithm Selection Criteria

### When to Use K-Means
- Dataset > 1,000 customers
- Expecting roughly spherical, equal-sized clusters
- Computational speed is important
- Baseline for comparison

### When to Use Hierarchical
- Smaller datasets (< 2,000)
- Want a dendrogram for business interpretation
- Expect unequal cluster sizes
- No prior assumption about k

### When to Use DBSCAN
- Expecting irregular cluster shapes
- Presence of noise / outlier passengers expected
- No strong prior on number of segments
- Dense core with sparse periphery (e.g., ultra-high flyers surrounded by noise)

### Silhouette Score Guidance (Aviation-Specific)
Real-world airline RFM data typically yields silhouette scores of 0.25–0.50 due to:
1. Continuous rather than discrete spending behaviour
2. Large intermediate segment (Potential Loyalists) overlapping both directions
3. Seasonal effects blurring recency boundaries

A silhouette of 0.25–0.40 is considered **acceptable and actionable** for airline segmentation.
Do not reject a model purely on silhouette < 0.50 in this domain — validate with business logic.

---

## 6. RFM Score → Segment Label Mapping

```
rfm_score 12–15  → Champions
rfm_score 9–11   → Loyal Flyers
rfm_score 6–8    → Potential Loyalists  (largest group)
rfm_score 4–5    → At-Risk Travellers
rfm_score 3      → Hibernating / Lost
```

Adjust boundaries by ±1 if cluster assignment from algorithm conflicts with rfm_score expectation for > 20% of segment.

---

## 7. Data Quality Flags (Aviation-Specific)

| Flag | Condition | Severity | Action |
|---|---|---|---|
| Single-transaction customers > 50% | >50% of customers have frequency=1 | WARN | Note in report; reduce k |
| Extremely long recency | Max recency > 1,000 days | WARN | Check if loyalty data is current |
| Negative or zero fares | base_fare_inr ≤ 0 | ERROR | Remove or investigate |
| NPS = 0 for all feedbacks | Possible encoding error | WARN | Verify NPS scale (some surveys use 1–10) |
| No feedback data | Empty customer_feedback.csv | WARN | Proceed; set engagement_score = NaN |
| Fare outliers (z > 4) | base_fare_inr > μ + 4σ | WARN | Likely First Class or charter; keep but note |

---

## 8. Segment Sizing Guidelines

| Number of Segments | When Appropriate |
|---|---|
| 3 | Small dataset (< 500), early-stage programme, limited CRM capability |
| 4 | Standard; recommended default; actionable with typical airline marketing team |
| 5 | Mature programme; separate "New" from "Potential Loyalists" |
| 6–7 | Large dataset (> 10,000); dedicated CRM team; sub-national regional analysis |

Minimum viable segment size: 50 customers (for statistical stability of mean profiles).
Reject any segment with < 50 customers; merge with nearest neighbour.
