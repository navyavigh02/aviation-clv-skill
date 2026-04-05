"""
generate_synthetic_data.py
--------------------------
Aviation Customer Analytics — Synthetic Data Generator

Generates a realistic airline loyalty/transaction dataset with:
  - customer_master.csv  : passenger demographics & loyalty tier
  - flight_transactions.csv : booking/flight history per customer
  - customer_feedback.csv   : post-flight survey scores

Usage:
    python scripts/generate_synthetic_data.py \
        --num_customers 2000 \
        --start_date 2022-01-01 \
        --end_date  2024-12-31 \
        --output_dir data/ \
        --seed 42

Outputs:
    data/customer_master.csv
    data/flight_transactions.csv
    data/customer_feedback.csv
    data/data_dictionary.md
"""

import argparse
import random
import math
import csv
import os
from datetime import date, timedelta

# ─────────────────────────────────────────────
# Reproducibility
# ─────────────────────────────────────────────
SEED = 42

def set_seed(s):
    random.seed(s)

# ─────────────────────────────────────────────
# Reference tables
# ─────────────────────────────────────────────
FIRST_NAMES = ["Aarav","Aditi","Ananya","Arjun","Deepa","Divya","Gaurav","Ishaan","Kavya",
               "Kiran","Meera","Neel","Pooja","Rahul","Riya","Rohan","Sanjay","Sneha","Suresh","Tanvi",
               "James","Emily","Michael","Sarah","David","Jessica","Robert","Ashley","William","Amanda",
               "Li Wei","Zhang Min","Chen Jing","Wang Fang","Liu Yang","Wu Hao","Zhao Lei","Sun Na",
               "Mohammed","Fatima","Ahmed","Aisha","Omar","Layla","Hassan","Zara","Ali","Nour"]

LAST_NAMES  = ["Sharma","Patel","Singh","Kumar","Gupta","Mehta","Joshi","Shah","Verma","Reddy",
               "Smith","Johnson","Williams","Brown","Jones","Miller","Davis","Wilson","Taylor","Anderson",
               "Chen","Wang","Li","Zhang","Liu","Xu","Yang","Huang","Wu","Zhou",
               "Khan","Ali","Ahmed","Hassan","Ibrahim","Malik","Rahman","Siddiqui","Akhtar","Qureshi"]

CITIES = [
    ("Delhi","India","DEL"),("Mumbai","India","BOM"),("Bangalore","India","BLR"),
    ("Hyderabad","India","HYD"),("Chennai","India","MAA"),("Kolkata","India","CCU"),
    ("Dubai","UAE","DXB"),("Abu Dhabi","UAE","AUH"),
    ("London","UK","LHR"),("Frankfurt","Germany","FRA"),("Paris","France","CDG"),
    ("Singapore","Singapore","SIN"),("Bangkok","Thailand","BKK"),
    ("New York","USA","JFK"),("Los Angeles","USA","LAX"),("Chicago","USA","ORD"),
    ("Sydney","Australia","SYD"),("Tokyo","Japan","NRT"),("Seoul","South Korea","ICN"),
    ("Nairobi","Kenya","NBO"),("Johannesburg","South Africa","JNB"),
]

ROUTE_PAIRS = [
    ("DEL","DXB"),("DEL","LHR"),("DEL","JFK"),("DEL","SIN"),("DEL","BOM"),
    ("DEL","BLR"),("BOM","DXB"),("BOM","LHR"),("BLR","SIN"),("BLR","DXB"),
    ("HYD","DXB"),("MAA","SIN"),("CCU","BKK"),("DEL","NRT"),("DEL","CDG"),
    ("BOM","JFK"),("DXB","LHR"),("SIN","NRT"),("SIN","SYD"),("LHR","JFK"),
]

CABIN_CLASSES = ["Economy","Premium Economy","Business","First"]
CABIN_WEIGHTS = [0.60, 0.15, 0.20, 0.05]

FARE_BASE = {
    "Economy": (8000, 35000),
    "Premium Economy": (35000, 75000),
    "Business": (75000, 200000),
    "First": (200000, 500000),
}

LOYALTY_TIERS = ["Bronze","Silver","Gold","Platinum"]
TIER_WEIGHTS   = [0.45, 0.30, 0.18, 0.07]

TRAVEL_PURPOSES = ["Leisure","Business","Family Visit","Medical","Education"]
PURPOSE_WEIGHTS  = [0.40, 0.30, 0.15, 0.08, 0.07]

AIRLINES = ["AirIndia","IndiGo","Vistara","Emirates","Lufthansa","SingaporeAir","Etihad"]

# ─────────────────────────────────────────────
# Helper utilities
# ─────────────────────────────────────────────
def weighted_choice(choices, weights):
    r = random.random()
    cum = 0.0
    for c, w in zip(choices, weights):
        cum += w
        if r < cum:
            return c
    return choices[-1]

def rand_date(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))

def date_str(d: date) -> str:
    return d.strftime("%Y-%m-%d")

def generate_customer_id(i: int) -> str:
    return f"CUST{i:06d}"

def generate_booking_id(i: int) -> str:
    return f"BK{i:08d}"

# ─────────────────────────────────────────────
# Customer master generator
# ─────────────────────────────────────────────
def build_customers(n: int, end_date: date):
    customers = []
    for i in range(1, n+1):
        cid   = generate_customer_id(i)
        fname = random.choice(FIRST_NAMES)
        lname = random.choice(LAST_NAMES)
        age   = random.randint(18, 75)
        gender = random.choice(["M","F","Other"])
        city_row = random.choice(CITIES)
        home_city, home_country, home_airport = city_row

        tier = weighted_choice(LOYALTY_TIERS, TIER_WEIGHTS)
        loyalty_points = {
            "Bronze":  random.randint(0, 5000),
            "Silver":  random.randint(5000, 25000),
            "Gold":    random.randint(25000, 75000),
            "Platinum":random.randint(75000, 300000),
        }[tier]

        # enrolment date: 1-5 years before analysis end
        enrol_date = end_date - timedelta(days=random.randint(365, 1825))

        email = f"{fname.lower()}.{lname.lower()}{random.randint(10,99)}@email.com"

        # preferred cabin correlated with tier
        cabin_pref_weights = {
            "Bronze":   [0.80, 0.12, 0.07, 0.01],
            "Silver":   [0.60, 0.20, 0.18, 0.02],
            "Gold":     [0.30, 0.20, 0.40, 0.10],
            "Platinum": [0.10, 0.10, 0.50, 0.30],
        }[tier]
        preferred_cabin = weighted_choice(CABIN_CLASSES, cabin_pref_weights)

        customers.append({
            "customer_id":       cid,
            "first_name":        fname,
            "last_name":         lname,
            "email":             email,
            "age":               age,
            "gender":            gender,
            "home_city":         home_city,
            "home_country":      home_country,
            "home_airport":      home_airport,
            "loyalty_tier":      tier,
            "loyalty_points":    loyalty_points,
            "enrolment_date":    date_str(enrol_date),
            "preferred_cabin":   preferred_cabin,
        })
    return customers

# ─────────────────────────────────────────────
# Flight transactions generator
# ─────────────────────────────────────────────
def build_transactions(customers, start_date: date, end_date: date):
    transactions = []
    bk_counter = 1

    # Flight frequency per year by tier
    freq_map = {
        "Bronze":  (1, 4),
        "Silver":  (3, 8),
        "Gold":    (6, 14),
        "Platinum":(10, 25),
    }

    for cust in customers:
        tier = cust["loyalty_tier"]
        lo, hi = freq_map[tier]
        span_years = (end_date - start_date).days / 365.0
        total_flights = int(random.uniform(lo, hi) * span_years)
        total_flights = max(1, total_flights)

        for _ in range(total_flights):
            flight_date = rand_date(start_date, end_date)
            route = random.choice(ROUTE_PAIRS)
            origin, destination = route if random.random() > 0.5 else (route[1], route[0])

            # cabin class correlated with tier
            cabin_weights = {
                "Bronze":   [0.80, 0.12, 0.07, 0.01],
                "Silver":   [0.60, 0.20, 0.18, 0.02],
                "Gold":     [0.30, 0.20, 0.40, 0.10],
                "Platinum": [0.10, 0.10, 0.50, 0.30],
            }[tier]
            cabin = weighted_choice(CABIN_CLASSES, cabin_weights)

            lo_f, hi_f = FARE_BASE[cabin]
            fare = round(random.uniform(lo_f, hi_f), 2)

            # ancillary spend: meal upgrades, baggage, lounge, etc.
            ancillary = round(random.uniform(0, fare * 0.15), 2)
            total_spend = fare + ancillary

            miles = int(fare / 10 * random.uniform(0.8, 1.2))
            purpose = weighted_choice(TRAVEL_PURPOSES, PURPOSE_WEIGHTS)
            airline = random.choice(AIRLINES)

            # booking lead time (days before flight)
            lead_days = random.randint(0, 180)
            booking_date = flight_date - timedelta(days=lead_days)
            if booking_date < start_date:
                booking_date = start_date

            # on-time: random but slightly worse for busy airports
            on_time = random.random() > 0.18  # ~82% on-time

            transactions.append({
                "booking_id":        generate_booking_id(bk_counter),
                "customer_id":       cust["customer_id"],
                "booking_date":      date_str(booking_date),
                "flight_date":       date_str(flight_date),
                "origin_airport":    origin,
                "destination_airport": destination,
                "airline":           airline,
                "cabin_class":       cabin,
                "base_fare_inr":     fare,
                "ancillary_spend_inr": ancillary,
                "total_spend_inr":   total_spend,
                "miles_earned":      miles,
                "travel_purpose":    purpose,
                "booking_lead_days": lead_days,
                "flight_on_time":    int(on_time),
            })
            bk_counter += 1

    return transactions

# ─────────────────────────────────────────────
# Customer feedback generator
# ─────────────────────────────────────────────
def build_feedback(transactions, customers):
    """30% of flights get a survey response."""
    cust_tier = {c["customer_id"]: c["loyalty_tier"] for c in customers}
    feedbacks = []

    for i, txn in enumerate(transactions):
        if random.random() > 0.30:
            continue

        tier = cust_tier.get(txn["customer_id"], "Bronze")
        on_time = txn["flight_on_time"]

        # base satisfaction by cabin + tier
        base = {
            "Economy": 3.2, "Premium Economy": 3.6,
            "Business": 4.1, "First": 4.5
        }[txn["cabin_class"]]
        base += {"Bronze": 0.0, "Silver": 0.1, "Gold": 0.15, "Platinum": 0.2}[tier]
        if not on_time:
            base -= 0.5

        def score(b, noise=0.5):
            return max(1, min(5, round(b + random.gauss(0, noise), 1)))

        feedbacks.append({
            "feedback_id":          f"FB{i:08d}",
            "booking_id":           txn["booking_id"],
            "customer_id":          txn["customer_id"],
            "feedback_date":        txn["flight_date"],
            "overall_satisfaction": score(base),
            "seat_comfort":         score(base - 0.1),
            "cabin_crew_service":   score(base + 0.1),
            "food_quality":         score(base - 0.2),
            "in_flight_entertainment": score(base - 0.3),
            "punctuality_score":    score(4.5 if on_time else 2.5, 0.3),
            "nps_score":            max(0, min(10, int(base * 2 + random.gauss(0, 1)))),
            "would_recommend":      int(base >= 3.5),
        })

    return feedbacks

# ─────────────────────────────────────────────
# Write CSV
# ─────────────────────────────────────────────
def write_csv(filepath, rows, fieldnames):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Written: {filepath}  ({len(rows):,} rows)")

# ─────────────────────────────────────────────
# Data dictionary
# ─────────────────────────────────────────────
DATA_DICT_CONTENT = """# Data Dictionary — Aviation Customer Analytics Dataset

## customer_master.csv
| Column | Type | Description | Valid Range / Values |
|---|---|---|---|
| customer_id | string | Unique passenger identifier (PK) | CUST000001 … |
| first_name | string | Passenger first name | Non-null |
| last_name | string | Passenger last name | Non-null |
| email | string | Contact email | Valid email format |
| age | integer | Age in years | 18–75 |
| gender | string | Gender identity | M / F / Other |
| home_city | string | City of residence | Non-null |
| home_country | string | Country of residence | Non-null |
| home_airport | string | Nearest hub airport (IATA) | 3-letter IATA code |
| loyalty_tier | string | Frequent-flyer tier | Bronze / Silver / Gold / Platinum |
| loyalty_points | integer | Accrued points balance | ≥ 0 |
| enrolment_date | date | Date joined loyalty programme | YYYY-MM-DD |
| preferred_cabin | string | Self-declared cabin preference | Economy / Premium Economy / Business / First |

## flight_transactions.csv
| Column | Type | Description | Valid Range / Values |
|---|---|---|---|
| booking_id | string | Unique booking identifier (PK) | BK00000001 … |
| customer_id | string | FK → customer_master | Must exist in customer_master |
| booking_date | date | Date booking was made | YYYY-MM-DD |
| flight_date | date | Actual travel date | YYYY-MM-DD, ≥ booking_date |
| origin_airport | string | Departure IATA code | 3-letter code |
| destination_airport | string | Arrival IATA code | 3-letter code, ≠ origin |
| airline | string | Operating carrier | Non-null |
| cabin_class | string | Cabin purchased | Economy / Premium Economy / Business / First |
| base_fare_inr | float | Ticket fare in INR | > 0 |
| ancillary_spend_inr | float | Ancillary add-ons (INR) | ≥ 0 |
| total_spend_inr | float | base_fare + ancillary | > 0 |
| miles_earned | integer | Loyalty miles credited | ≥ 0 |
| travel_purpose | string | Self-declared trip purpose | Leisure / Business / Family Visit / Medical / Education |
| booking_lead_days | integer | Days between booking & travel | 0–180 |
| flight_on_time | integer | 1 = on-time, 0 = delayed | 0 or 1 |

## customer_feedback.csv
| Column | Type | Description | Valid Range / Values |
|---|---|---|---|
| feedback_id | string | Unique survey response ID (PK) | FB00000000 … |
| booking_id | string | FK → flight_transactions | Must exist in transactions |
| customer_id | string | FK → customer_master | Must exist in customer_master |
| feedback_date | date | Date feedback was submitted | YYYY-MM-DD |
| overall_satisfaction | float | Overall flight rating | 1.0–5.0 |
| seat_comfort | float | Seat comfort score | 1.0–5.0 |
| cabin_crew_service | float | Crew rating | 1.0–5.0 |
| food_quality | float | Food & beverage rating | 1.0–5.0 |
| in_flight_entertainment | float | IFE rating | 1.0–5.0 |
| punctuality_score | float | On-time performance rating | 1.0–5.0 |
| nps_score | integer | Net Promoter Score (0–10) | 0–10 |
| would_recommend | integer | 1 = would recommend airline | 0 or 1 |

## Sources
Dataset is synthetically generated using `scripts/generate_synthetic_data.py` (seed=42).
All customer names, emails, and identifiers are fictitious.
Fare figures are approximate INR values for India-originated routes (2022-2024 range).
"""

# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Generate aviation analytics dataset")
    parser.add_argument("--num_customers", type=int, default=2000)
    parser.add_argument("--start_date", default="2022-01-01")
    parser.add_argument("--end_date",   default="2024-12-31")
    parser.add_argument("--output_dir", default="data/")
    parser.add_argument("--seed",       type=int, default=42)
    args = parser.parse_args()

    set_seed(args.seed)

    start = date.fromisoformat(args.start_date)
    end   = date.fromisoformat(args.end_date)

    print(f"\n=== Aviation Synthetic Data Generator (seed={args.seed}) ===")
    print(f"Customers : {args.num_customers:,}")
    print(f"Date range: {args.start_date} → {args.end_date}\n")

    print("[1/4] Generating customer master...")
    customers = build_customers(args.num_customers, end)

    print("[2/4] Generating flight transactions...")
    transactions = build_transactions(customers, start, end)

    print("[3/4] Generating customer feedback...")
    feedbacks = build_feedback(transactions, customers)

    print("[4/4] Writing files...")
    write_csv(
        os.path.join(args.output_dir, "customer_master.csv"),
        customers,
        ["customer_id","first_name","last_name","email","age","gender",
         "home_city","home_country","home_airport","loyalty_tier",
         "loyalty_points","enrolment_date","preferred_cabin"]
    )
    write_csv(
        os.path.join(args.output_dir, "flight_transactions.csv"),
        transactions,
        ["booking_id","customer_id","booking_date","flight_date",
         "origin_airport","destination_airport","airline","cabin_class",
         "base_fare_inr","ancillary_spend_inr","total_spend_inr",
         "miles_earned","travel_purpose","booking_lead_days","flight_on_time"]
    )
    write_csv(
        os.path.join(args.output_dir, "customer_feedback.csv"),
        feedbacks,
        ["feedback_id","booking_id","customer_id","feedback_date",
         "overall_satisfaction","seat_comfort","cabin_crew_service",
         "food_quality","in_flight_entertainment","punctuality_score",
         "nps_score","would_recommend"]
    )

    # write data dictionary
    dd_path = os.path.join(args.output_dir, "data_dictionary.md")
    with open(dd_path, "w", encoding="utf-8") as f:
        f.write(DATA_DICT_CONTENT)
    print(f"  Written: {dd_path}")

    print("\nDone. Dataset generation complete.")
    print(f"  Customers  : {len(customers):,}")
    print(f"  Bookings   : {len(transactions):,}")
    print(f"  Feedbacks  : {len(feedbacks):,}")

if __name__ == "__main__":
    main()
