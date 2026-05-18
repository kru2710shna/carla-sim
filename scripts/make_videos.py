import cv2
import glob
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def make_video(session_path, fps=20):
    """
    Converts RGB frames from a session into an MP4 video.
    """
    images_path = os.path.join(session_path, "images")
    output_path = os.path.join(session_path, "rgb_video.mp4")

    frames = sorted(glob.glob(os.path.join(images_path, "frame_*.png")))

    if not frames:
        print(f"No frames found in {images_path}")
        return

    # get dimensions from first frame
    sample = cv2.imread(frames[0])
    h, w   = sample.shape[:2]

    writer = cv2.VideoWriter(
        output_path,
        cv2.VideoWriter_fourcc(*'mp4v'),
        fps,
        (w, h)
    )

    for f in frames:
        img = cv2.imread(f)
        writer.write(img)

    writer.release()
    print(f"✅ {os.path.basename(session_path)}: {len(frames)} frames → {output_path}")


if __name__ == "__main__":
    # find all sessions
    sessions = sorted([
        os.path.join("Data", d)
        for d in os.listdir("Data")
        if d.startswith("session_") and os.path.isdir(os.path.join("Data", d))
    ])

    if not sessions:
        print("No sessions found in Data/")
        sys.exit(1)

    print(f"Found {len(sessions)} sessions\n")

    for session in sessions:
        make_video(session)

    print("\nAll videos created!")