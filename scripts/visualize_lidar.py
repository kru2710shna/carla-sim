import numpy as np
import cv2
import os
import glob
import json

def get_camera_matrix(fov=90, width=1280, height=720):
    """
    Build camera intrinsic matrix from CARLA camera settings.
    This is what Myra meant by using CARLA's calibration.
    """
    focal = width / (2.0 * np.tan(fov * np.pi / 360.0))
    K = np.array([
        [focal,   0,    width  / 2.0],
        [0,     focal,  height / 2.0],
        [0,       0,    1.0         ]
    ])
    return K


def lidar_to_camera(points, K):
    """
    Project 3D LiDAR points onto 2D camera image.

    How it works:
    - LiDAR is mounted at x=0, z=2.8 (roof)
    - Camera is mounted at x=1.5, z=2.4 (hood)
    - We transform LiDAR points into camera coordinate frame
    - Then project using camera intrinsic matrix K

    CARLA coordinate system:
    - x = forward
    - y = right  
    - z = up
    """
    # transform from LiDAR frame to camera frame
    # LiDAR at (0, 0, 2.8), Camera at (1.5, 0, 2.4)
    # offset: x_offset=1.5, z_offset=-0.4
    points_cam = points.copy()
    points_cam[:, 0] -= 1.5   # x offset
    points_cam[:, 2] -= 0.4   # z offset (lidar higher than camera)

    # CARLA to OpenCV convention
    # CARLA: x=forward, y=right, z=up
    # OpenCV: x=right,  y=down,  z=forward
    x =  points_cam[:, 1]   # right
    y = -points_cam[:, 2]   # down (flip z)
    z =  points_cam[:, 0]   # forward

    # only keep points in front of camera
    mask = z > 0.1
    x, y, z = x[mask], y[mask], z[mask]
    intensity = points[mask, 3]

    # project to 2D
    u = (K[0, 0] * x / z + K[0, 2]).astype(int)
    v = (K[1, 1] * y / z + K[1, 2]).astype(int)

    return u, v, z, intensity


def colorize_depth(depth, min_d=1.0, max_d=30.0):
    """Map depth to color — close=red, far=blue."""
    normalized = np.clip((depth - min_d) / (max_d - min_d), 0, 1)
    colors = []
    for d in normalized:
        r = int(255 * (1 - d))
        g = int(255 * 2 * min(d, 1 - d))
        b = int(255 * d)
        colors.append((b, g, r))  # BGR for OpenCV
    return colors


def overlay_lidar_on_image(img_path, lidar_path, output_path, K):
    img = cv2.imread(img_path)
    if img is None:
        return False

    points = np.load(lidar_path)
    if points.shape[0] == 0:
        return False

    # filter out points that hit the ego vehicle itself
    # ego car is within ~2.5m of sensor center
    dist_2d = np.sqrt(points[:, 0]**2 + points[:, 1]**2)
    
    mask = (
        (dist_2d > 2.5)          # remove ego car hits
        & (dist_2d < 50.0)       # remove far noise
        & (points[:, 2] > -2.5)  # remove ground points below car
        & (points[:, 2] < 5.0)   # remove points above buildings
    )
    points = points[mask]

    if points.shape[0] == 0:
        return False

    h, w = img.shape[:2]
    u, v, depth, intensity = lidar_to_camera(points, K)

    mask = (u >= 0) & (u < w) & (v >= 0) & (v < h) & (depth > 0)
    u, v, depth = u[mask], v[mask], depth[mask]

    if len(u) == 0:
        return False

    colors = colorize_depth(depth)
    for i in range(len(u)):
        cv2.circle(img, (u[i], v[i]), 2, colors[i], -1)

    cv2.imwrite(output_path, img)
    return True

def visualize_session(session_path, max_frames=50):
    """
    Create LiDAR overlay images for a session.
    Saves to session_path/lidar_overlay/
    """
    camera_dir  = os.path.join(session_path, "camera/front")
    lidar_dir   = os.path.join(session_path, "lidar")
    output_dir  = os.path.join(session_path, "lidar_overlay")
    os.makedirs(output_dir, exist_ok=True)

    K = get_camera_matrix()

    # get matching frame pairs
    cam_frames   = sorted(glob.glob(os.path.join(camera_dir, "*.png")))
    cam_frames   = cam_frames[:max_frames]

    success = 0
    for cam_path in cam_frames:
        frame_id   = os.path.splitext(os.path.basename(cam_path))[0]
        lidar_path = os.path.join(lidar_dir, f"{frame_id}.npy")

        if not os.path.exists(lidar_path):
            continue

        output_path = os.path.join(output_dir, f"{frame_id}_overlay.png")
        if overlay_lidar_on_image(cam_path, lidar_path, output_path, K):
            success += 1

    print(f"Created {success} overlay frames → {output_dir}")
    return output_dir


def make_overlay_video(session_path, fps=20):
    """Convert overlay frames to MP4."""
    overlay_dir = os.path.join(session_path, "lidar_overlay")
    frames      = sorted(glob.glob(os.path.join(overlay_dir, "*_overlay.png")))

    if not frames:
        print("No overlay frames found")
        return

    sample = cv2.imread(frames[0])
    h, w   = sample.shape[:2]
    output = os.path.join(session_path, "lidar_overlay_video.mp4")

    writer = cv2.VideoWriter(
        output,
        cv2.VideoWriter_fourcc(*'mp4v'),
        fps,
        (w, h)
    )

    for f in frames:
        writer.write(cv2.imread(f))

    writer.release()
    print(f"Overlay video saved → {output}")


if __name__ == "__main__":
    # find latest session
    sessions = sorted([
        os.path.join("data", d)
        for d in os.listdir("data")
        if d.startswith("session_") and os.path.isdir(os.path.join("data", d))
    ])

    if not sessions:
        print("No sessions found")
        exit(1)

    latest = sessions[-1]
    print(f"Visualizing: {latest}")

    # process ALL frames — no limit
    visualize_session(latest, max_frames=999999)
    make_overlay_video(latest)

    print("Done! Check lidar_overlay_video.mp4")