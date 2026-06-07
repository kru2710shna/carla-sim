import os
import sys
import glob
import json
import numpy as np
import csv

def validate_session(session_path):
    """
    End-to-end validation of a collected session.
    Checks frame alignment, data integrity, file counts.
    """
    print(f"\n{'='*60}")
    print(f"VALIDATING: {session_path}")
    print(f"{'='*60}\n")

    results = {
        "session":  session_path,
        "passed":   [],
        "warnings": [],
        "failed":   []
    }

    # ── 1. check folder structure ────────────────────────────────
    print("1. Checking folder structure...")
    required = ["camera/front", "lidar", "radar", "gnss",
                "metadata.json", "annotations.json"]
    for item in required:
        full = os.path.join(session_path, item)
        if os.path.exists(full):
            results["passed"].append(f"  ✅ {item} exists")
        else:
            results["failed"].append(f"  ❌ {item} MISSING")

    # ── 2. count files ───────────────────────────────────────────
    print("2. Counting files...")
    cam_files   = sorted(glob.glob(
        os.path.join(session_path, "camera/front/*.png")))
    lidar_files = sorted(glob.glob(
        os.path.join(session_path, "lidar/*.npy")))
    radar_files = sorted(glob.glob(
        os.path.join(session_path, "radar/*.csv")))

    print(f"   Camera frames: {len(cam_files)}")
    print(f"   LiDAR scans:   {len(lidar_files)}")
    print(f"   Radar files:   {len(radar_files)}")

    if len(cam_files) == 0:
        results["failed"].append("  ❌ No camera frames found")
    else:
        results["passed"].append(f"  ✅ Camera: {len(cam_files)} frames")

    if len(lidar_files) == 0:
        results["failed"].append("  ❌ No LiDAR scans found")
    else:
        results["passed"].append(f"  ✅ LiDAR: {len(lidar_files)} scans")

    if len(radar_files) == 0:
        results["warnings"].append("  ⚠️  No radar files found")
    else:
        results["passed"].append(f"  ✅ Radar: {len(radar_files)} files")

    # ── 3. frame alignment check ─────────────────────────────────
    print("3. Checking frame alignment...")
    cam_ids   = set(
        os.path.splitext(os.path.basename(f))[0]
        for f in cam_files
    )
    lidar_ids = set(
        os.path.splitext(os.path.basename(f))[0]
        for f in lidar_files
    )
    radar_ids = set(
        os.path.splitext(os.path.basename(f))[0]
        for f in radar_files
    )

    matched_cam_lidar  = cam_ids & lidar_ids
    matched_all        = cam_ids & lidar_ids & radar_ids
    only_cam           = cam_ids - lidar_ids
    only_lidar         = lidar_ids - cam_ids

    print(f"   Camera ∩ LiDAR matched: {len(matched_cam_lidar)}")
    print(f"   All 3 sensors matched:  {len(matched_all)}")
    print(f"   Camera only (no LiDAR): {len(only_cam)}")
    print(f"   LiDAR only (no camera): {len(only_lidar)}")

    alignment_pct = len(matched_cam_lidar) / max(len(cam_ids), 1) * 100
    print(f"   Alignment: {alignment_pct:.1f}%")

    if alignment_pct == 100.0:
        results["passed"].append(
            f"  ✅ Perfect alignment: 100% ({len(matched_cam_lidar)} pairs)")
    elif alignment_pct >= 95.0:
        results["warnings"].append(
            f"  ⚠️  Alignment: {alignment_pct:.1f}% "
            f"({len(only_cam)} camera frames missing LiDAR)")
    else:
        results["failed"].append(
            f"  ❌ Poor alignment: {alignment_pct:.1f}%")

    # ── 4. validate LiDAR data integrity ─────────────────────────
    print("4. Validating LiDAR data...")
    sample_files = lidar_files[:5]
    lidar_ok     = True
    for f in sample_files:
        try:
            pts = np.load(f)
            if pts.ndim != 2 or pts.shape[1] != 4:
                results["failed"].append(
                    f"  ❌ LiDAR shape wrong: {pts.shape} in {f}")
                lidar_ok = False
            elif pts.shape[0] == 0:
                results["warnings"].append(
                    f"  ⚠️  Empty LiDAR scan: {f}")
        except Exception as e:
            results["failed"].append(f"  ❌ LiDAR read error: {e}")
            lidar_ok = False

    if lidar_ok:
        pts = np.load(lidar_files[0])
        results["passed"].append(
            f"  ✅ LiDAR shape valid: {pts.shape} (N, 4)")

    # ── 5. validate GNSS ─────────────────────────────────────────
    print("5. Validating GNSS...")
    gnss_file = os.path.join(session_path, "gnss/gnss_log.csv")
    if os.path.exists(gnss_file):
        with open(gnss_file) as f:
            rows = list(csv.DictReader(f))
        if len(rows) > 0:
            first = rows[0]
            last  = rows[-1]
            duration = float(last["timestamp"]) - float(first["timestamp"])
            print(f"   GNSS rows: {len(rows)}")
            print(f"   Duration:  {duration:.1f}s")
            print(f"   Start pos: x={float(first['ego_x']):.1f} "
                  f"y={float(first['ego_y']):.1f}")
            print(f"   End pos:   x={float(last['ego_x']):.1f} "
                  f"y={float(last['ego_y']):.1f}")

            # check car actually moved
            dx = abs(float(last['ego_x']) - float(first['ego_x']))
            dy = abs(float(last['ego_y']) - float(first['ego_y']))
            dist = (dx**2 + dy**2) ** 0.5
            print(f"   Distance:  {dist:.1f}m")

            if dist > 10.0:
                results["passed"].append(
                    f"  ✅ Vehicle moved {dist:.1f}m")
            else:
                results["failed"].append(
                    f"  ❌ Vehicle barely moved: {dist:.1f}m — stuck?")

            results["passed"].append(
                f"  ✅ GNSS: {len(rows)} rows, {duration:.1f}s duration")
    else:
        results["failed"].append("  ❌ GNSS file missing")

    # ── 6. validate annotations.json ─────────────────────────────
    print("6. Validating annotations...")
    ann_file = os.path.join(session_path, "annotations.json")
    if os.path.exists(ann_file):
        with open(ann_file) as f:
            ann = json.load(f)
        print(f"   Annotation frames: {len(ann)}")
        if len(ann) > 0:
            sample = ann[0]
            has_pose = "ego_pose" in sample
            has_vel  = "ego_velocity" in sample
            has_ts   = "timestamp" in sample
            if has_pose and has_vel and has_ts:
                results["passed"].append(
                    f"  ✅ Annotations: {len(ann)} frames, "
                    f"pose+velocity+timestamp")
            else:
                results["warnings"].append(
                    f"  ⚠️  Annotations missing fields: "
                    f"pose={has_pose} vel={has_vel} ts={has_ts}")
    else:
        results["failed"].append("  ❌ annotations.json missing")

    # ── 7. validate metadata ─────────────────────────────────────
    print("7. Validating metadata...")
    meta_file = os.path.join(session_path, "metadata.json")
    if os.path.exists(meta_file):
        with open(meta_file) as f:
            meta = json.load(f)
        required_keys = ["scenario", "map", "route", "sensors", "timestamp"]
        missing = [k for k in required_keys if k not in meta]
        if not missing:
            results["passed"].append(
                f"  ✅ Metadata complete: scenario={meta['scenario']}")
        else:
            results["warnings"].append(
                f"  ⚠️  Metadata missing keys: {missing}")
    else:
        results["failed"].append("  ❌ metadata.json missing")

    # ── summary ──────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("VALIDATION SUMMARY")
    print(f"{'='*60}")

    print(f"\n✅ PASSED ({len(results['passed'])}):")
    for r in results["passed"]:
        print(r)

    if results["warnings"]:
        print(f"\n⚠️  WARNINGS ({len(results['warnings'])}):")
        for r in results["warnings"]:
            print(r)

    if results["failed"]:
        print(f"\n❌ FAILED ({len(results['failed'])}):")
        for r in results["failed"]:
            print(r)

    total   = len(results["passed"]) + len(results["warnings"]) + len(results["failed"])
    score   = len(results["passed"]) / total * 100
    status  = "PASS" if not results["failed"] else "FAIL"

    print(f"\nScore: {score:.0f}%  |  Status: {status}")
    print(f"{'='*60}\n")

    # save report
    report_path = os.path.join(session_path, "validation_report.json")
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Report saved → {report_path}")

    return status == "PASS"


if __name__ == "__main__":
    if len(sys.argv) == 2:
        validate_session(sys.argv[1])
    else:
        # validate latest session automatically
        sessions = sorted([
            os.path.join("data", d)
            for d in os.listdir("data")
            if d.startswith("session_") and
            os.path.isdir(os.path.join("data", d))
        ])
        if not sessions:
            print("No sessions found in data/")
            sys.exit(1)

        latest = sessions[-1]
        validate_session(latest)