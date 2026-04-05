"""
run_models.py
-------------
Aviation Customer Analytics — Stage 3 & 4: Modelling + Validation

Runs THREE clustering algorithms on the RFM feature matrix:
  1. K-Means         (k = 3,4,5,6,7)
  2. Hierarchical    (Ward linkage, k = 3,4,5,6,7)
  3. DBSCAN          (eps grid search)

Validation metrics computed per algorithm+k:
  - Silhouette Score      (target: >0.25 acceptable, >0.50 good, >0.70 excellent)
  - Davies-Bouldin Index  (lower is better)
  - Calinski-Harabasz Score (higher is better)
  - Elbow/inertia         (K-Means only)
  - Cluster size balance  (reject if any cluster < 5% or > 40% of data)

Selects the BEST configuration based on silhouette + interpretability.

Usage:
    python scripts/run_models.py \
        --features   outputs/rfm_features.csv \
        --algorithms kmeans,hierarchical,dbscan \
        --k_range    3,7 \
        --output_dir outputs/

Outputs:
    outputs/models_output.json      — all metrics + best model
    outputs/customer_segments.csv   — customer_id + segment label
    outputs/models_comparison.txt   — human-readable comparison table
"""

import argparse
import csv
import json
import math
import os
import random
from collections import Counter, defaultdict

RANDOM_SEED = 42
random.seed(RANDOM_SEED)

# ─────────────────────────────────────────────
# Silhouette threshold guidance
# ─────────────────────────────────────────────
SILHOUETTE_THRESHOLDS = {
    "excellent": 0.70,
    "good":      0.50,
    "acceptable":0.25,
}

# ─────────────────────────────────────────────
# IO
# ─────────────────────────────────────────────
def load_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def safe_float(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default

def write_csv(path, rows, fieldnames):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

# ─────────────────────────────────────────────
# Feature matrix builder
# ─────────────────────────────────────────────
FEATURE_COLS = [
    "recency_days",
    "frequency",
    "monetary_total_inr",
    "cabin_upgrade_ratio",
    "route_diversity",
    "business_travel_ratio",
    "loyalty_points",
]

def build_matrix(rows):
    """Return (customer_ids, X) where X is a list of float-vectors (z-score standardised)."""
    ids = [r["customer_id"] for r in rows]
    raw = []
    for r in rows:
        vec = [safe_float(r.get(c, 0)) for c in FEATURE_COLS]
        raw.append(vec)

    # Z-score standardisation
    n = len(raw)
    d = len(FEATURE_COLS)
    means = [sum(raw[i][j] for i in range(n)) / n for j in range(d)]
    stds  = [
        math.sqrt(sum((raw[i][j] - means[j])**2 for i in range(n)) / n) or 1.0
        for j in range(d)
    ]
    X = [[(raw[i][j] - means[j]) / stds[j] for j in range(d)] for i in range(n)]
    return ids, X, means, stds

# ─────────────────────────────────────────────
# Distance utilities
# ─────────────────────────────────────────────
def euclidean(a, b):
    return math.sqrt(sum((x - y)**2 for x, y in zip(a, b)))

def dot(a, b):
    return sum(x*y for x, y in zip(a, b))

def vec_mean(vecs):
    n = len(vecs)
    d = len(vecs[0])
    return [sum(v[j] for v in vecs) / n for j in range(d)]

# ─────────────────────────────────────────────
# K-Means (from scratch)
# ─────────────────────────────────────────────
def kmeans(X, k, max_iter=200):
    random.seed(RANDOM_SEED)
    # k-means++ initialisation
    centroids = [X[random.randint(0, len(X)-1)]]
    for _ in range(k - 1):
        dists = [min(euclidean(x, c)**2 for c in centroids) for x in X]
        total = sum(dists)
        probs = [d / total for d in dists]
        r = random.random()
        cum = 0
        chosen = 0
        for idx, p in enumerate(probs):
            cum += p
            if r <= cum:
                chosen = idx
                break
        centroids.append(X[chosen])

    labels = [0] * len(X)
    for _ in range(max_iter):
        # Assignment
        new_labels = [min(range(k), key=lambda c: euclidean(x, centroids[c])) for x in X]
        if new_labels == labels:
            break
        labels = new_labels
        # Update centroids
        for c in range(k):
            members = [X[i] for i in range(len(X)) if labels[i] == c]
            if members:
                centroids[c] = vec_mean(members)

    inertia = sum(euclidean(X[i], centroids[labels[i]])**2 for i in range(len(X)))
    return labels, centroids, inertia

# ─────────────────────────────────────────────
# Hierarchical clustering (Ward linkage, agglomerative)
# ─────────────────────────────────────────────
def hierarchical(X, k):
    """Simple agglomerative clustering with Ward-like merge (min centroid distance)."""
    n = len(X)
    # Start: each point is its own cluster
    clusters = {i: [i] for i in range(n)}

    while len(clusters) > k:
        keys = list(clusters.keys())
        best_i, best_j, best_d = None, None, float("inf")
        # Find closest pair of cluster centroids
        centroids_map = {ck: vec_mean([X[idx] for idx in clusters[ck]]) for ck in keys}
        for ai in range(len(keys)):
            for bi in range(ai+1, len(keys)):
                ci, cj = keys[ai], keys[bi]
                d = euclidean(centroids_map[ci], centroids_map[cj])
                if d < best_d:
                    best_d = d
                    best_i, best_j = ci, cj
        # Merge
        clusters[best_i] = clusters[best_i] + clusters[best_j]
        del clusters[best_j]

    # Build label array
    labels = [0] * n
    for label_idx, (_, members) in enumerate(clusters.items()):
        for idx in members:
            labels[idx] = label_idx
    return labels

# ─────────────────────────────────────────────
# DBSCAN (from scratch)
# ─────────────────────────────────────────────
def dbscan(X, eps, min_samples=5):
    n = len(X)
    labels = [-1] * n          # -1 = noise
    cluster_id = 0
    visited = [False] * n

    def region_query(p):
        return [q for q in range(n) if euclidean(X[p], X[q]) <= eps]

    def expand(p, neighbors, cid):
        labels[p] = cid
        i = 0
        while i < len(neighbors):
            q = neighbors[i]
            if not visited[q]:
                visited[q] = True
                new_nb = region_query(q)
                if len(new_nb) >= min_samples:
                    neighbors += [x for x in new_nb if x not in neighbors]
            if labels[q] == -1:
                labels[q] = cid
            i += 1

    for p in range(n):
        if visited[p]:
            continue
        visited[p] = True
        neighbors = region_query(p)
        if len(neighbors) < min_samples:
            labels[p] = -1   # noise
        else:
            expand(p, neighbors, cluster_id)
            cluster_id += 1

    return labels, cluster_id   # returns labels and number of clusters found

# ─────────────────────────────────────────────
# Validation metrics
# ─────────────────────────────────────────────
def silhouette_score(X, labels):
    """Compute mean silhouette coefficient."""
    n = len(X)
    unique_labels = [l for l in set(labels) if l >= 0]
    if len(unique_labels) < 2:
        return -1.0

    cluster_members = defaultdict(list)
    for i, l in enumerate(labels):
        if l >= 0:
            cluster_members[l].append(i)

    scores = []
    for i in range(n):
        if labels[i] < 0:  # noise point
            continue
        my_cluster = labels[i]
        my_members = [j for j in cluster_members[my_cluster] if j != i]

        if not my_members:
            scores.append(0.0)
            continue

        # a(i): mean intra-cluster distance
        a = sum(euclidean(X[i], X[j]) for j in my_members) / len(my_members)

        # b(i): min mean distance to other clusters
        b = float("inf")
        for other_l, other_members in cluster_members.items():
            if other_l == my_cluster:
                continue
            mean_d = sum(euclidean(X[i], X[j]) for j in other_members) / len(other_members)
            if mean_d < b:
                b = mean_d

        s = (b - a) / max(a, b) if max(a, b) > 0 else 0.0
        scores.append(s)

    return round(sum(scores) / len(scores), 4) if scores else -1.0

def davies_bouldin(X, labels):
    """Davies-Bouldin index (lower = better)."""
    unique = [l for l in set(labels) if l >= 0]
    k = len(unique)
    if k < 2:
        return float("inf")

    centroids = {}
    scatters  = {}
    for l in unique:
        members = [X[i] for i, lbl in enumerate(labels) if lbl == l]
        c = vec_mean(members)
        centroids[l] = c
        scatters[l]  = sum(euclidean(X[i], c) for i, lbl in enumerate(labels) if lbl == l) / len(members)

    db_sum = 0.0
    for i in unique:
        max_ratio = 0.0
        for j in unique:
            if i == j:
                continue
            ratio = (scatters[i] + scatters[j]) / euclidean(centroids[i], centroids[j])
            if ratio > max_ratio:
                max_ratio = ratio
        db_sum += max_ratio
    return round(db_sum / k, 4)

def calinski_harabasz(X, labels):
    """Calinski-Harabasz score (higher = better)."""
    unique = [l for l in set(labels) if l >= 0]
    k = len(unique)
    n = len([l for l in labels if l >= 0])
    if k < 2:
        return 0.0

    all_pts = [X[i] for i, l in enumerate(labels) if l >= 0]
    global_centroid = vec_mean(all_pts)

    between = 0.0
    within  = 0.0
    for l in unique:
        members = [X[i] for i, lbl in enumerate(labels) if lbl == l]
        c = vec_mean(members)
        between += len(members) * euclidean(c, global_centroid)**2
        within  += sum(euclidean(X[i], c)**2 for i, lbl in enumerate(labels) if lbl == l)

    if within == 0:
        return 0.0
    return round((between / (k-1)) / (within / (n-k)), 4)

def check_balance(labels, min_pct=5.0, max_pct=40.0):
    n = len([l for l in labels if l >= 0])
    counts = Counter(l for l in labels if l >= 0)
    sizes = [cnt / n * 100 for cnt in counts.values()]
    too_small = [s for s in sizes if s < min_pct]
    too_large  = [s for s in sizes if s > max_pct]
    return {
        "balanced": len(too_small) == 0 and len(too_large) == 0,
        "min_pct":  round(min(sizes), 1),
        "max_pct":  round(max(sizes), 1),
        "cluster_sizes_pct": [round(s, 1) for s in sorted(sizes, reverse=True)],
    }

# ─────────────────────────────────────────────
# Main modelling function
# ─────────────────────────────────────────────
def run_models(feature_rows, algorithms, k_lo, k_hi):
    print(f"  Building feature matrix ({len(feature_rows):,} customers × {len(FEATURE_COLS)} features)...")
    ids, X, means, stds = build_matrix(feature_rows)

    # For large datasets, subsample silhouette to manage compute time
    SILHOUETTE_SAMPLE = min(500, len(X))
    sample_idx = random.sample(range(len(X)), SILHOUETTE_SAMPLE)
    X_sample   = [X[i] for i in sample_idx]

    all_results = []
    best_result = None
    best_sil    = -1.0

    # ── K-Means ───────────────────────────────
    if "kmeans" in algorithms:
        print("  Running K-Means...")
        for k in range(k_lo, k_hi+1):
            labels, centroids, inertia = kmeans(X, k)
            sil_labels_sample = [labels[i] for i in sample_idx]
            sil  = silhouette_score(X_sample, sil_labels_sample)
            db   = davies_bouldin(X_sample, sil_labels_sample)
            ch   = calinski_harabasz(X_sample, sil_labels_sample)
            bal  = check_balance(labels)

            r = {
                "algorithm":    "kmeans",
                "k":            k,
                "silhouette":   sil,
                "davies_bouldin": db,
                "calinski_harabasz": ch,
                "inertia":      round(inertia, 2),
                "balance":      bal,
                "labels":       labels,
            }
            all_results.append(r)
            print(f"    k={k}: silhouette={sil:.4f}  DB={db:.4f}  CH={ch:.2f}  balanced={bal['balanced']}")

            if sil > best_sil and bal["balanced"]:
                best_sil    = sil
                best_result = r

    # ── Hierarchical ─────────────────────────
    if "hierarchical" in algorithms:
        print("  Running Hierarchical (Ward)...")
        # For performance, subsample for hierarchical
        H_SAMPLE = min(800, len(X))
        h_sample_idx = random.sample(range(len(X)), H_SAMPLE)
        X_h = [X[i] for i in h_sample_idx]

        for k in range(k_lo, k_hi+1):
            labels_h = hierarchical(X_h, k)
            # Map back (unsampled points get nearest centroid assignment)
            centroids_h = {}
            from collections import defaultdict
            members_h = defaultdict(list)
            for i, l in enumerate(labels_h):
                members_h[l].append(X_h[i])
            for l, pts in members_h.items():
                centroids_h[l] = vec_mean(pts)

            full_labels_h = []
            for x in X:
                nearest = min(centroids_h.keys(), key=lambda l: euclidean(x, centroids_h[l]))
                full_labels_h.append(nearest)

            sil_labels_sample = [full_labels_h[i] for i in sample_idx]
            sil  = silhouette_score(X_sample, sil_labels_sample)
            db   = davies_bouldin(X_sample, sil_labels_sample)
            ch   = calinski_harabasz(X_sample, sil_labels_sample)
            bal  = check_balance(full_labels_h)

            r = {
                "algorithm":    "hierarchical",
                "k":            k,
                "silhouette":   sil,
                "davies_bouldin": db,
                "calinski_harabasz": ch,
                "inertia":      None,
                "balance":      bal,
                "labels":       full_labels_h,
            }
            all_results.append(r)
            print(f"    k={k}: silhouette={sil:.4f}  DB={db:.4f}  CH={ch:.2f}  balanced={bal['balanced']}")

            if sil > best_sil and bal["balanced"]:
                best_sil    = sil
                best_result = r

    # ── DBSCAN ───────────────────────────────
    if "dbscan" in algorithms:
        print("  Running DBSCAN (eps grid search on 600-point sample)...")
        DB_SAMPLE = min(600, len(X))
        db_idx = random.sample(range(len(X)), DB_SAMPLE)
        X_db   = [X[i] for i in db_idx]

        best_db_sil = -1.0
        best_db_res = None
        for eps in [0.5, 0.8, 1.0, 1.2, 1.5, 2.0]:
            labels_db, n_clusters = dbscan(X_db, eps, min_samples=5)
            noise_pct = sum(1 for l in labels_db if l < 0) / len(labels_db) * 100
            if n_clusters < 2 or n_clusters > 10 or noise_pct > 40:
                print(f"    eps={eps}: {n_clusters} clusters, {noise_pct:.0f}% noise → skip")
                continue
            sil = silhouette_score(X_db, labels_db)
            db  = davies_bouldin(X_db, labels_db)
            ch  = calinski_harabasz(X_db, labels_db)
            print(f"    eps={eps}: {n_clusters} clusters, sil={sil:.4f}, noise={noise_pct:.1f}%")
            if sil > best_db_sil:
                best_db_sil = sil
                best_db_res = {
                    "algorithm":    "dbscan",
                    "k":            n_clusters,
                    "eps":          eps,
                    "noise_pct":    round(noise_pct, 1),
                    "silhouette":   sil,
                    "davies_bouldin": db,
                    "calinski_harabasz": ch,
                    "inertia":      None,
                    "balance":      check_balance(labels_db),
                    "labels":       None,  # sample-level only
                }
        if best_db_res:
            all_results.append(best_db_res)

    # ── Fallback: if no balanced model found, pick best silhouette anyway ──
    if best_result is None:
        all_results_with_labels = [r for r in all_results if r.get("labels")]
        if all_results_with_labels:
            best_result = max(all_results_with_labels, key=lambda r: r["silhouette"])
            print(f"  [WARN] No perfectly balanced model found. Selecting best silhouette: "
                  f"{best_result['algorithm']} k={best_result['k']} sil={best_result['silhouette']:.4f}")

    return ids, all_results, best_result

# ─────────────────────────────────────────────
# Segment labeller (using REFERENCE.md archetypes)
# ─────────────────────────────────────────────
SEGMENT_ARCHETYPES = {
    # Assigned after sorting segments by mean RFM score descending
    0: "Champions",
    1: "Loyal Flyers",
    2: "Potential Loyalists",
    3: "At-Risk Travellers",
    4: "Hibernating",
    5: "Lost Passengers",
    6: "New Passengers",
}

def label_segments(ids, labels, feature_rows):
    cust_map = {r["customer_id"]: r for r in feature_rows}

    # Compute per-segment mean rfm_score
    seg_rfm = defaultdict(list)
    for cid, lbl in zip(ids, labels):
        if lbl >= 0:
            r = cust_map.get(cid, {})
            seg_rfm[lbl].append(safe_float(r.get("rfm_score", 0)))

    # Sort segments by mean rfm_score descending
    seg_mean = {l: (sum(v)/len(v) if v else 0) for l, v in seg_rfm.items()}
    sorted_segs = sorted(seg_mean.keys(), key=lambda l: seg_mean[l], reverse=True)
    label_map = {orig: SEGMENT_ARCHETYPES.get(new_rank, f"Segment_{new_rank}")
                 for new_rank, orig in enumerate(sorted_segs)}

    rows = []
    for cid, lbl in zip(ids, labels):
        rows.append({
            "customer_id":    cid,
            "raw_cluster":    lbl,
            "segment_label":  label_map.get(lbl, "Noise") if lbl >= 0 else "Noise",
        })
    return rows, label_map

# ─────────────────────────────────────────────
# Build comparison table
# ─────────────────────────────────────────────
def build_comparison_text(all_results, best_result):
    lines = []
    lines.append("=" * 80)
    lines.append("AVIATION CLV — ALGORITHM COMPARISON TABLE")
    lines.append("=" * 80)
    lines.append(f"{'Algorithm':<16} {'k':<4} {'Silhouette':<12} {'Davies-Bouldin':<16} "
                 f"{'Calinski-H':<12} {'Balanced':<10}")
    lines.append("-" * 80)
    for r in all_results:
        alg  = r["algorithm"]
        k    = r.get("k", "?")
        sil  = r["silhouette"]
        db   = r["davies_bouldin"]
        ch   = r["calinski_harabasz"]
        bal  = r["balance"]["balanced"]
        marker = " ◄ BEST" if best_result and r is best_result else ""
        lines.append(f"{alg:<16} {k:<4} {sil:<12.4f} {db:<16.4f} {ch:<12.2f} {str(bal):<10}{marker}")
    lines.append("")
    lines.append("VALIDATION THRESHOLDS:")
    lines.append(f"  Silhouette: >0.70 = excellent | >0.50 = good | >0.25 = acceptable | <0.25 = poor")
    lines.append(f"  Davies-Bouldin: lower is better (ideal < 1.0)")
    lines.append(f"  Calinski-Harabasz: higher is better")
    lines.append(f"  Cluster balance: no segment < 5% or > 40% of customers")
    lines.append("")
    if best_result:
        sil = best_result['silhouette']
        quality = "excellent" if sil >= 0.70 else "good" if sil >= 0.50 else "acceptable" if sil >= 0.25 else "poor"
        lines.append(f"SELECTED: {best_result['algorithm'].upper()} k={best_result['k']}")
        lines.append(f"  Silhouette score : {sil:.4f} ({quality})")
        lines.append(f"  Davies-Bouldin   : {best_result['davies_bouldin']:.4f}")
        lines.append(f"  Calinski-Harabasz: {best_result['calinski_harabasz']:.2f}")
        lines.append(f"  Cluster sizes    : {best_result['balance']['cluster_sizes_pct']}")
    lines.append("=" * 80)
    return "\n".join(lines)

# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Aviation CLV — multi-algorithm clustering")
    parser.add_argument("--features",    default="outputs/rfm_features.csv")
    parser.add_argument("--algorithms",  default="kmeans,hierarchical,dbscan")
    parser.add_argument("--k_range",     default="3,6")
    parser.add_argument("--output_dir",  default="outputs/")
    args = parser.parse_args()

    algos = [a.strip() for a in args.algorithms.split(",")]
    k_parts = args.k_range.split(",")
    k_lo, k_hi = int(k_parts[0]), int(k_parts[1])

    print("=== Stage 3 & 4: Modelling + Validation ===")
    feature_rows = load_csv(args.features)

    ids, all_results, best_result = run_models(feature_rows, algos, k_lo, k_hi)

    # Build segment assignments
    segment_rows, label_map = label_segments(ids, best_result["labels"], feature_rows)

    os.makedirs(args.output_dir, exist_ok=True)

    # Write segment CSV
    seg_path = os.path.join(args.output_dir, "customer_segments.csv")
    write_csv(seg_path, segment_rows, ["customer_id","raw_cluster","segment_label"])
    print(f"  Written: {seg_path}")

    # Write comparison table
    comparison_text = build_comparison_text(all_results, best_result)
    comp_path = os.path.join(args.output_dir, "models_comparison.txt")
    with open(comp_path, "w", encoding="utf-8") as f:
        f.write(comparison_text)
    print(f"  Written: {comp_path}")
    print(comparison_text)

    # Write JSON output
    serializable_results = []
    for r in all_results:
        rc = {k: v for k, v in r.items() if k != "labels"}
        serializable_results.append(rc)

    best_serializable = {k: v for k, v in best_result.items() if k != "labels"} if best_result else {}

    seg_dist = Counter(r["segment_label"] for r in segment_rows)

    output_json = {
        "best_model":       best_serializable,
        "all_results":      serializable_results,
        "segment_distribution": dict(seg_dist),
        "label_map":        {str(k): v for k, v in label_map.items()},
        "features_used":    FEATURE_COLS,
        "random_seed":      RANDOM_SEED,
    }
    json_path = os.path.join(args.output_dir, "models_output.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output_json, f, indent=2)
    print(f"  Written: {json_path}")

    print(f"\nSegment distribution:")
    for seg, cnt in sorted(seg_dist.items(), key=lambda x: -x[1]):
        print(f"  {seg:<28} : {cnt:,}  ({cnt/len(segment_rows)*100:.1f}%)")

    print("\nStage 3 & 4 complete.")
