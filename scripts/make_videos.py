import cv2
import glob
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def make_video(session_path, fps=20):
    # check both old and new folder structure
    for images_path in [
        os.path.join(session_path, "camera/front"),
        os.path.join(session_path, "images")
    ]:
        frames = sorted(glob.glob(os.path.join(images_path, "*.png")))
        if frames:
            break

    if not frames:
        print(f"No frames found in {session_path}")
        return

    output_path = os.path.join(session_path, "rgb_video.mp4")
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
    sessions = []
    for base in ["data", "Data"]:
        if os.path.exists(base):
            for d in sorted(os.listdir(base)):
                full = os.path.join(base, d)
                if d.startswith("session_") and os.path.isdir(full):
                    sessions.append(full)

    if not sessions:
        print("No sessions found in data/ or Data/")
        sys.exit(1)

    print(f"Found {len(sessions)} sessions\n")
    for session in sessions:
        make_video(session)

    print("\nAll videos created!")