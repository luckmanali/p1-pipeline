from ultralytics import YOLO
import sys
import os

def test_yolo_on_video(video_path: str):
    """
    Runs YOLO26-large-pose on a video file and prints detection
    results every 15 frames. Use this to validate that player and
    ball detection works on real 5-a-side footage before building
    the full pipeline.

    Args:
        video_path: path to your test video file
    """
    if not os.path.exists(video_path):
        print(f"Error: video not found at {video_path}")
        sys.exit(1)

    print("Loading YOLO26-large-pose model...")
    print("(weights will download automatically on first run ~50MB)\n")

    model = YOLO("yolo26l-pose.pt")

    print(f"Running inference on: {video_path}")
    print("Sampling every 15th frame (= 1 second at 15fps)\n")

    results = model(
        video_path,
        stream=True,
        imgsz=640,
        conf=0.3
    )

    frame_count = 0
    person_detections = []
    ball_detections = []

    for i, r in enumerate(results):
        frame_count += 1

        if r.boxes is not None:
            for box in r.boxes:
                cls = int(box.cls)
                conf = float(box.conf)
                label = model.names[cls]
                if label == "person":
                    person_detections.append(conf)
                elif label == "sports ball":
                    ball_detections.append(conf)

        if i % 15 == 0:
            persons_this_frame = sum(
                1 for box in r.boxes
                if model.names[int(box.cls)] == "person"
            ) if r.boxes is not None else 0

            balls_this_frame = sum(
                1 for box in r.boxes
                if model.names[int(box.cls)] == "sports ball"
            ) if r.boxes is not None else 0

            keypoints_this_frame = len(r.keypoints) if r.keypoints is not None else 0

            print(f"Frame {i:5d} | "
                  f"Players: {persons_this_frame:2d} | "
                  f"Ball: {balls_this_frame} | "
                  f"Keypoints: {keypoints_this_frame}")

    print("\n--- Summary ---")
    print(f"Total frames processed: {frame_count}")
    if person_detections:
        avg_person_conf = sum(person_detections) / len(person_detections)
        print(f"Person detections: {len(person_detections)} total, avg confidence: {avg_person_conf:.2f}")
    else:
        print("Person detections: none — check video or lower conf threshold")
    if ball_detections:
        avg_ball_conf = sum(ball_detections) / len(ball_detections)
        print(f"Ball detections: {len(ball_detections)} total, avg confidence: {avg_ball_conf:.2f}")
    else:
        print("Ball detections: none — ball detection may need fine-tuning")

if __name__ == "__main__":
    video_path = sys.argv[1] if len(sys.argv) > 1 else "test_clip.mp4"
    test_yolo_on_video(video_path)
