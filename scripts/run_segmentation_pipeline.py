#!/usr/bin/env python3
"""
CARLA Synthetic AV Dataset — Segmentation & Distribution Pipeline
===================================================================

Continues the project documented in PROJECT_DOCUMENTATION.md (Goal G9) and
follows the methodology established in Myra Cropper's prior work
("Verification of Simulated Data", CMU DRIVE Lab):

    CARLA frames -> Mask2Former panoptic segmentation -> per-frame instance
    counts -> averaged class distribution -> (optional) distribution
    comparison against a reference dataset (e.g. RaDelft) via JSD / L1 / KL.

Runs unmodified on:
  - Google Colab (free T4 GPU)  <- recommended, ~30 min for ~9.3k frames
  - A local machine with a CUDA GPU (incl. small-VRAM cards, e.g. 3 GB)
  - CPU only (slow, but works — useful for smoke-testing on a handful
    of frames before committing to a full run)

The script auto-detects the best available device and adapts batch size
accordingly, so no edits are needed when moving between environments.

--------------------------------------------------------------------------
USAGE
--------------------------------------------------------------------------

1) Segment a dataset and build the class/instance distribution:

    python3 run_segmentation_pipeline.py segment \
        --data-root /content/drive/MyDrive/carla_data \
        --out-dir   /content/drive/MyDrive/carla_data/segmentation_results

   `--data-root` must contain session folders matching:
        <data-root>/session_NNN_<scenario>/camera/front/<10-digit-frame>.png
   (exactly the layout in PROJECT_DOCUMENTATION.md §7).

2) Compare two already-built distributions (e.g. CARLA vs Delft):

    python3 run_segmentation_pipeline.py compare \
        --dist-a carla_data/segmentation_results/class_distribution.json \
        --dist-b delft_distribution.json \
        --label-a CARLA --label-b Delft \
        --out-dir comparison_results

3) Smoke-test the whole thing on a handful of frames before a full run:

    python3 run_segmentation_pipeline.py segment \
        --data-root /content/drive/MyDrive/carla_data \
        --out-dir   /tmp/smoke_test \
        --limit 20

--------------------------------------------------------------------------
"""

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path


# ===========================================================================
# Dependency bootstrap
# ===========================================================================
# Colab ships most of this already; local/CPU machines often don't.
# We install only what's missing, so re-running in an already-set-up
# environment is instant.

def _ensure_dependencies(packages):
    """
    Install any of `packages` (dict: module_name -> pip_name) that aren't
    already importable. Only installs what a given subcommand actually
    needs — `compare` needs numpy/scipy/matplotlib but not torch/transformers.

    On Debian/Ubuntu systems (PEP 668 "externally managed environment",
    e.g. the project's own Ubuntu 24 box per PROJECT_DOCUMENTATION.md §3),
    a plain `pip install` is blocked. We detect that failure mode and
    retry once with --break-system-packages, matching the convention
    already used elsewhere in this project. Colab/most other environments
    never hit this path and install normally on the first try.
    """
    import importlib
    import subprocess

    missing = []
    for module_name, pip_name in packages.items():
        try:
            importlib.import_module(module_name)
        except ImportError:
            missing.append(pip_name)

    if not missing:
        return

    print(f"[setup] Installing missing packages: {missing}")
    base_cmd = [sys.executable, "-m", "pip", "install", "--quiet", *missing]
    try:
        subprocess.check_call(base_cmd)
    except subprocess.CalledProcessError:
        print("[setup] Plain pip install failed (likely an externally-managed "
              "environment) — retrying with --break-system-packages")
        subprocess.check_call(base_cmd + ["--break-system-packages"])
    print("[setup] Done.")


# Dependency sets per subcommand — keeps `compare` lightweight and avoids
# ever installing torch/transformers when they're not needed.
SEGMENT_DEPS = {
    "torch": "torch",
    "torchvision": "torchvision",
    "transformers": "transformers",
    "PIL": "Pillow",
    "numpy": "numpy",
    "matplotlib": "matplotlib",
    "tqdm": "tqdm",
}

COMPARE_DEPS = {
    "numpy": "numpy",
    "scipy": "scipy",
}


# ===========================================================================
# Cityscapes panoptic label space
# ===========================================================================
# facebook/mask2former-swin-tiny-cityscapes-panoptic predicts these 19
# classes. Eight of them are "thing" classes (countable objects -> get
# instance IDs); the rest are "stuff" classes (background regions, no
# instance IDs). This split matches slide 11 of the prior work ("before
# removing features" = all 19; the final comparison uses only the 8
# countable classes from slide 9).

CITYSCAPES_CLASSES = [
    "road", "sidewalk", "building", "wall", "fence", "pole",
    "traffic light", "traffic sign", "vegetation", "terrain", "sky",
    "person", "rider", "car", "truck", "bus", "train", "motorcycle",
    "bicycle",
]

# The exact 8-class set used for the final CARLA/Delft comparison
# (slide 9: "Bicycle, building, bus, car, motorcycle, person, rider, truck").
# Note "building" is a stuff class with no instance IDs in panoptic output;
# for stuff classes we report presence-per-frame (0/1) rather than an
# instance count, since "instances" isn't a meaningful concept for them.
# This mirrors the prior work treating it as a feature in the same table.
COMPARISON_CLASSES = [
    "bicycle", "building", "bus", "car", "motorcycle",
    "person", "rider", "truck",
]

THING_CLASSES = {
    "person", "rider", "car", "truck", "bus", "train",
    "motorcycle", "bicycle",
}


# ===========================================================================
# Stage 1: Segmentation
# ===========================================================================

def discover_sessions(data_root: Path):
    """
    Find session folders matching PROJECT_DOCUMENTATION.md §7:
        <data_root>/session_NNN_<scenario>/camera/front/*.png
    Returns list of (session_name, scenario_name, [frame_paths sorted]).
    """
    sessions = []
    if not data_root.exists():
        raise FileNotFoundError(f"data-root does not exist: {data_root}")

    for session_dir in sorted(data_root.iterdir()):
        if not session_dir.is_dir() or not session_dir.name.startswith("session_"):
            continue
        cam_dir = session_dir / "camera" / "front"
        if not cam_dir.exists():
            print(f"[warn] {session_dir.name}: no camera/front/ — skipping")
            continue

        frames = sorted(cam_dir.glob("*.png"))
        if not frames:
            print(f"[warn] {session_dir.name}: camera/front/ has no .png frames — skipping")
            continue

        # session name convention: session_NNN_scenario -> scenario is
        # everything after the second underscore.
        parts = session_dir.name.split("_", 2)
        scenario = parts[2] if len(parts) == 3 else session_dir.name

        sessions.append((session_dir.name, scenario, frames))

    return sessions


def pick_device_and_batch_size():
    """
    Auto-detect compute device and a sane batch size for it.
    Conservative on small-VRAM GPUs (the 3 GB GTX 970M case from
    PROJECT_DOCUMENTATION.md §9.2) to avoid the VRAM-exhaustion failure
    mode documented there.
    """
    import torch

    if torch.cuda.is_available():
        device = "cuda"
        total_vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
        if total_vram_gb < 4:
            batch_size = 1       # e.g. GTX 970M 3GB — match VRAM-ceiling lesson from §9.2
        elif total_vram_gb < 8:
            batch_size = 2
        else:
            batch_size = 4       # T4 (Colab) and similar have plenty of headroom
        print(f"[device] CUDA GPU detected: {torch.cuda.get_device_name(0)} "
              f"({total_vram_gb:.1f} GB) — batch_size={batch_size}")
    else:
        device = "cpu"
        batch_size = 1
        print("[device] No CUDA GPU detected — running on CPU (will be slow; "
              "fine for --limit smoke tests, not recommended for a full run)")

    return device, batch_size


def load_model(device):
    from transformers import Mask2FormerForUniversalSegmentation, AutoImageProcessor

    checkpoint = "facebook/mask2former-swin-tiny-cityscapes-panoptic"
    print(f"[model] Loading {checkpoint} ...")
    processor = AutoImageProcessor.from_pretrained(checkpoint)
    model = Mask2FormerForUniversalSegmentation.from_pretrained(checkpoint)
    model.to(device)
    model.eval()
    print("[model] Ready.")
    return model, processor


def segment_frame(model, processor, device, image):
    """
    Run panoptic inference on a single PIL image.
    Returns: (panoptic_seg: 2D np.ndarray of segment ids,
              segments_info: list of dicts with 'id', 'label_id', 'score', ...)
    """
    import torch

    inputs = processor(images=image, return_tensors="pt").to(device)
    with torch.no_grad():
        outputs = model(**inputs)

    result = processor.post_process_panoptic_segmentation(
        outputs, target_sizes=[image.size[::-1]]  # (height, width)
    )[0]

    panoptic_seg = result["segmentation"].cpu().numpy()
    segments_info = result["segments_info"]
    return panoptic_seg, segments_info


def count_instances_per_frame(segments_info, id2label):
    """
    Given Mask2Former's segments_info for one frame, return a dict
    {class_name: instance_count} for "thing" classes, and
    {class_name: 1} (presence) for "stuff" classes that appear at all.

    This is the core operation that matches slide 11: converting raw
    segmentation output into per-frame instance counts per class.
    """
    counts = defaultdict(int)
    seen_stuff = set()

    for seg in segments_info:
        label_id = seg["label_id"]
        class_name = id2label.get(label_id, f"unknown_{label_id}")

        if class_name in THING_CLASSES:
            counts[class_name] += 1
        else:
            seen_stuff.add(class_name)

    for class_name in seen_stuff:
        counts[class_name] = 1  # presence indicator, not a true instance count

    return dict(counts)


def run_segmentation(args):
    data_root = Path(args.data_root)
    out_dir = Path(args.out_dir)

    # Validate inputs before installing torch/transformers, so a typo'd
    # --data-root fails in milliseconds instead of after a multi-minute install.
    try:
        sessions = discover_sessions(data_root)
    except FileNotFoundError as e:
        print(f"[error] {e}")
        sys.exit(1)

    if not sessions:
        print(f"[error] No valid session_* folders with camera/front/*.png "
              f"found under {data_root}")
        sys.exit(1)

    _ensure_dependencies(SEGMENT_DEPS)

    import numpy as np
    from PIL import Image
    from tqdm import tqdm

    out_dir.mkdir(parents=True, exist_ok=True)

    total_frames = sum(len(frames) for _, _, frames in sessions)
    print(f"[discover] Found {len(sessions)} session(s), {total_frames} total frames")
    for name, scenario, frames in sessions:
        print(f"           - {name} ({scenario}): {len(frames)} frames")

    device, _batch_size = pick_device_and_batch_size()
    # NOTE: Mask2Former's HF pipeline is run one image at a time below.
    # True batched inference is possible but post_process_panoptic_segmentation
    # handles variable image sizes per-call; for the 3GB-VRAM case especially,
    # single-image inference is the safer default (see §9.2 VRAM lessons).
    model, processor = load_model(device)
    id2label = model.config.id2label

    per_frame_overlay_dir = out_dir / "overlays"
    save_overlays = args.save_overlays
    if save_overlays:
        per_frame_overlay_dir.mkdir(parents=True, exist_ok=True)

    # per_frame_records: list of dicts, one per processed frame
    #   {session, scenario, frame_id, counts: {class: count}}
    per_frame_records = []

    frames_processed = 0
    t_start = time.time()

    for session_name, scenario, frames in sessions:
        if args.limit is not None and frames_processed >= args.limit:
            break

        for frame_path in tqdm(frames, desc=f"{session_name}", unit="frame"):
            if args.limit is not None and frames_processed >= args.limit:
                break

            image = Image.open(frame_path).convert("RGB")
            panoptic_seg, segments_info = segment_frame(model, processor, device, image)
            counts = count_instances_per_frame(segments_info, id2label)

            per_frame_records.append({
                "session": session_name,
                "scenario": scenario,
                "frame_id": frame_path.stem,
                "counts": counts,
            })

            if save_overlays:
                _save_overlay(image, panoptic_seg, segments_info, id2label,
                               per_frame_overlay_dir / f"{session_name}_{frame_path.stem}.png")

            frames_processed += 1

    elapsed = time.time() - t_start
    print(f"\n[done] Segmented {frames_processed} frames in "
          f"{elapsed/60:.1f} min ({elapsed/max(frames_processed,1):.2f} s/frame)")

    # Persist raw per-frame counts (useful for debugging / re-aggregating
    # later without re-running inference).
    per_frame_path = out_dir / "per_frame_counts.json"
    with open(per_frame_path, "w") as f:
        json.dump(per_frame_records, f, indent=2)
    print(f"[save] Per-frame counts -> {per_frame_path}")

    distribution = build_distribution(per_frame_records)
    dist_path = out_dir / "class_distribution.json"
    with open(dist_path, "w") as f:
        json.dump(distribution, f, indent=2)
    print(f"[save] Class distribution -> {dist_path}")

    plot_path = out_dir / "class_distribution_chart.png"
    plot_distribution(distribution, plot_path)
    print(f"[save] Distribution chart -> {plot_path}")


def _save_overlay(image, panoptic_seg, segments_info, id2label, out_path):
    """Save a simple colorized panoptic overlay for visual QA."""
    import numpy as np
    from PIL import Image

    rng = np.random.RandomState(42)  # fixed seed -> stable colors across frames
    seg_ids = np.unique(panoptic_seg)
    color_map = {seg_id: rng.randint(0, 255, size=3) for seg_id in seg_ids}

    h, w = panoptic_seg.shape
    overlay = np.zeros((h, w, 3), dtype=np.uint8)
    for seg_id, color in color_map.items():
        overlay[panoptic_seg == seg_id] = color

    base = np.array(image.resize((w, h))).astype(np.float32)
    blended = (0.5 * base + 0.5 * overlay.astype(np.float32)).astype(np.uint8)
    Image.fromarray(blended).save(out_path)


# ===========================================================================
# Stage 2: Distribution building
# ===========================================================================

def build_distribution(per_frame_records):
    """
    Aggregate per-frame instance counts into average-instances-per-frame,
    matching slide 11's "Average Instances Per Frame" bar chart — both
    overall (across the whole dataset) and broken out per scenario.
    """
    def aggregate(records):
        n = len(records)
        totals = defaultdict(float)
        for rec in records:
            for cls, cnt in rec["counts"].items():
                totals[cls] += cnt
        return {cls: round(total / n, 4) for cls, total in totals.items()} if n else {}

    overall = aggregate(per_frame_records)

    by_scenario = defaultdict(list)
    for rec in per_frame_records:
        by_scenario[rec["scenario"]].append(rec)

    per_scenario = {
        scenario: aggregate(recs) for scenario, recs in sorted(by_scenario.items())
    }

    return {
        "description": "Average instances per frame per Cityscapes-panoptic class.",
        "num_frames": len(per_frame_records),
        "classes": CITYSCAPES_CLASSES,
        "comparison_classes": COMPARISON_CLASSES,
        "overall": overall,
        "per_scenario": per_scenario,
    }


def plot_distribution(distribution, out_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    overall = distribution["overall"]
    classes = sorted(overall.keys(), key=lambda c: -overall[c])
    values = [overall[c] for c in classes]

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.bar(classes, values, color="#4C72B0")
    ax.set_ylabel("Average Instances Per Frame")
    ax.set_title("CARLA — Average Instances Per Frame (all scenarios)")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


# ===========================================================================
# Stage 3: Distribution comparison (CARLA vs Delft, or any two distributions)
# ===========================================================================
# Matches slides 13-14: JSD, L1 distance, and KL divergence (both
# directions, since KL is asymmetric) between two class distributions.

def _to_probability_vector(dist_section, classes):
    """
    Convert a {class: avg_instances_per_frame} dict into a normalized
    probability vector over `classes` (missing classes -> 0).
    Distribution comparison metrics (JSD/KL) require probability
    distributions, i.e. values that sum to 1.
    """
    import numpy as np

    raw = np.array([dist_section.get(c, 0.0) for c in classes], dtype=np.float64)
    total = raw.sum()
    if total <= 0:
        raise ValueError("Distribution has zero total mass over the given classes — "
                          "check that class names match between the two distributions.")
    return raw / total


def compute_comparison_metrics(dist_a, dist_b, classes, epsilon=1e-10):
    """
    dist_a, dist_b: {class: avg_instances_per_frame} dicts (e.g. the
                    "overall" section of two class_distribution.json files).
    classes: list of class names to compare over (typically COMPARISON_CLASSES,
             matching slide 9's 8-class set).

    Returns dict with l1, jsd, kl_a_to_b, kl_b_to_a.
    """
    import numpy as np
    from scipy.spatial.distance import jensenshannon
    from scipy.stats import entropy as kl_divergence

    p = _to_probability_vector(dist_a, classes)
    q = _to_probability_vector(dist_b, classes)

    # Smooth with epsilon to avoid log(0) / div-by-0 in KL, then renormalize.
    p_smooth = (p + epsilon) / (p + epsilon).sum()
    q_smooth = (q + epsilon) / (q + epsilon).sum()

    l1 = float(np.sum(np.abs(p - q)))
    jsd = float(jensenshannon(p_smooth, q_smooth) ** 2)  # scipy returns sqrt(JSD); square for the divergence itself
    kl_a_to_b = float(kl_divergence(p_smooth, q_smooth))  # KL(P||Q)
    kl_b_to_a = float(kl_divergence(q_smooth, p_smooth))  # KL(Q||P)

    return {
        "classes_compared": classes,
        "l1": round(l1, 4),
        "jsd": round(jsd, 4),
        "kl_a_to_b": round(kl_a_to_b, 4),
        "kl_b_to_a": round(kl_b_to_a, 4),
    }


def run_comparison(args):
    _ensure_dependencies(COMPARE_DEPS)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(args.dist_a) as f:
        dist_a_full = json.load(f)
    with open(args.dist_b) as f:
        dist_b_full = json.load(f)

    dist_a = dist_a_full.get("overall", dist_a_full)
    dist_b = dist_b_full.get("overall", dist_b_full)

    # Compare only over classes present in BOTH inputs' declared comparison
    # set (falls back to the standard 8-class set if a file doesn't specify
    # one, e.g. a hand-built Delft reference distribution).
    classes_a = dist_a_full.get("comparison_classes", COMPARISON_CLASSES)
    classes_b = dist_b_full.get("comparison_classes", COMPARISON_CLASSES)
    classes = [c for c in classes_a if c in classes_b]

    if not classes:
        print("[error] No overlapping comparison classes between the two "
              "distributions — check class naming.")
        sys.exit(1)

    metrics = compute_comparison_metrics(dist_a, dist_b, classes)

    result = {
        "label_a": args.label_a,
        "label_b": args.label_b,
        "metrics": metrics,
    }

    out_path = out_dir / f"comparison_{args.label_a}_vs_{args.label_b}.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\n[{args.label_a} vs {args.label_b}]")
    print(f"  Classes compared : {classes}")
    print(f"  L1 distance      : {metrics['l1']}")
    print(f"  JSD              : {metrics['jsd']}")
    print(f"  KL({args.label_a}||{args.label_b})  : {metrics['kl_a_to_b']}")
    print(f"  KL({args.label_b}||{args.label_a})  : {metrics['kl_b_to_a']}")
    print(f"[save] -> {out_path}")


# ===========================================================================
# CLI
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(
        description="CARLA dataset segmentation + class distribution + comparison pipeline."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    seg = sub.add_parser("segment", help="Run Mask2Former panoptic segmentation over a CARLA dataset.")
    seg.add_argument("--data-root", required=True,
                      help="Path containing session_NNN_<scenario>/camera/front/*.png folders.")
    seg.add_argument("--out-dir", required=True,
                      help="Where to write per_frame_counts.json, class_distribution.json, chart, overlays.")
    seg.add_argument("--limit", type=int, default=None,
                      help="Process only the first N frames total (for smoke-testing before a full run).")
    seg.add_argument("--save-overlays", action="store_true",
                      help="Also save colorized panoptic overlay images for visual QA (slower, more disk).")
    seg.set_defaults(func=run_segmentation)

    cmp_parser = sub.add_parser("compare", help="Compare two class_distribution.json files (e.g. CARLA vs Delft).")
    cmp_parser.add_argument("--dist-a", required=True, help="Path to first distribution JSON.")
    cmp_parser.add_argument("--dist-b", required=True, help="Path to second distribution JSON.")
    cmp_parser.add_argument("--label-a", default="A", help="Display label for distribution A.")
    cmp_parser.add_argument("--label-b", default="B", help="Display label for distribution B.")
    cmp_parser.add_argument("--out-dir", required=True, help="Where to write the comparison result JSON.")
    cmp_parser.set_defaults(func=run_comparison)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()