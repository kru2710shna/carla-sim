import numpy as np
import os
import glob
import cv2
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

# ── CONFIG ───────────────────────────────────────────────
LIDAR_DIR  = "data/lidar"
IMAGE_DIR  = "data/images"
GNSS_FILE  = "data/gnss/gnss_logs.csv"
OUTPUT_DIR = "results"
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ── 1. RGB frames → MP4 ──────────────────────────────────
def rgb_to_video(fps=20):
    print("Creating RGB video...")
    frames = sorted(glob.glob(f"{IMAGE_DIR}/frame_*.png"))
    if not frames:
        print("No RGB frames found.")
        return

    sample = cv2.imread(frames[0])
    h, w = sample.shape[:2]

    writer = cv2.VideoWriter(
        f"{OUTPUT_DIR}/rgb_video.mp4",
        cv2.VideoWriter_fourcc(*'mp4v'),
        fps, (w, h)
    )
    for f in frames:
        img = cv2.imread(f)
        writer.write(img)
    writer.release()
    print(f"RGB video saved → {OUTPUT_DIR}/rgb_video.mp4 ({len(frames)} frames)")


# ── 2. LiDAR scans → MP4 (bird's eye view) ───────────────
def lidar_to_video(fps=10):
    print("Creating LiDAR video...")
    files = sorted(glob.glob(f"{LIDAR_DIR}/lidar_*.npy"))
    if not files:
        print("No LiDAR files found.")
        return

    fig, ax = plt.subplots(figsize=(8, 8), facecolor='black')
    writer  = cv2.VideoWriter(
        f"{OUTPUT_DIR}/lidar_video.mp4",
        cv2.VideoWriter_fourcc(*'mp4v'),
        fps, (800, 800)
    )

    for i, f in enumerate(files):
        points = np.load(f)
        x = points[:, 0]
        y = points[:, 1]
        intensity = points[:, 3]

        ax.clear()
        ax.set_facecolor('black')
        ax.scatter(x, y, c=intensity, cmap='plasma',
                   s=0.3, alpha=0.7, vmin=0, vmax=1)

        # draw ego vehicle position
        ax.plot(0, 0, 'ro', markersize=8, label='Ego Vehicle')

        ax.set_xlim(-50, 50)
        ax.set_ylim(-50, 50)
        ax.set_title(f'LiDAR Bird Eye View — Frame {i}',
                     color='white', fontsize=10)
        ax.set_xlabel('X (metres)', color='white')
        ax.set_ylabel('Y (metres)', color='white')
        ax.tick_params(colors='white')
        ax.legend(loc='upper right', fontsize=8)

        fig.canvas.draw()
        buf = np.frombuffer(fig.canvas.tostring_rgb(), dtype=np.uint8)
        buf = buf.reshape(fig.canvas.get_width_height()[::-1] + (3,))
        frame_bgr = cv2.cvtColor(buf, cv2.COLOR_RGB2BGR)
        frame_bgr = cv2.resize(frame_bgr, (800, 800))
        writer.write(frame_bgr)

        if i % 20 == 0:
            print(f"  Processing LiDAR frame {i}/{len(files)}")

    writer.release()
    plt.close()
    print(f"LiDAR video saved → {OUTPUT_DIR}/lidar_video.mp4")


# ── 3. GNSS → route plot saved as PNG ────────────────────
def plot_gnss_route():
    print("Plotting GNSS route...")
    import csv

    lats, lons, timestamps = [], [], []
    with open(GNSS_FILE, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            lats.append(float(row['latitude']))
            lons.append(float(row['longitude']))
            timestamps.append(float(row['timestamp']))

    if not lats:
        print("No GNSS data found.")
        return

    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    fig.suptitle('GNSS Route Analysis', fontsize=14, fontweight='bold')

    # plot 1 — route path
    scatter = axes[0].scatter(lons, lats,
                               c=range(len(lats)),
                               cmap='viridis', s=5)
    axes[0].plot(lons[0],  lats[0],  'go', markersize=12, label='Start')
    axes[0].plot(lons[-1], lats[-1], 'ro', markersize=12, label='End')
    axes[0].set_xlabel('Longitude')
    axes[0].set_ylabel('Latitude')
    axes[0].set_title('Vehicle Route (colour = time)')
    axes[0].legend()
    plt.colorbar(scatter, ax=axes[0], label='Time progression')

    # plot 2 — latitude over time
    axes[1].plot(timestamps, lats, 'b-', linewidth=1, label='Latitude')
    axes[1].plot(timestamps, lons, 'r-', linewidth=1, label='Longitude')
    axes[1].set_xlabel('Timestamp (s)')
    axes[1].set_ylabel('Coordinate value')
    axes[1].set_title('Position over Time')
    axes[1].legend()

    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/gnss_route.png", dpi=150, bbox_inches='tight')
    plt.close()
    print(f"GNSS plot saved → {OUTPUT_DIR}/gnss_route.png")


# ── MAIN ─────────────────────────────────────────────────
if __name__ == "__main__":
    rgb_to_video()
    lidar_to_video()
    plot_gnss_route()
    print("\nAll visualizations saved to results/")