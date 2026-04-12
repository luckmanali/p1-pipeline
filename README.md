# mps-pipeline

Computer vision pipeline for analysing 5-a-side football footage using YOLO pose estimation.

## Prerequisites

Install [UV](https://docs.astral.sh/uv/) if you don't have it:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Setup

Clone the repo and let UV handle the rest — no manual venv creation needed:

```bash
cd mps-pipeline
uv sync
```

## Running the test

Drop a test video into the project folder, then run:

```bash
uv run python tests/test_yolo.py path/to/your/video.mp4
```

If no path is given it defaults to `test_clip.mp4` in the current directory.

On first run the YOLO26-large-pose weights (~50MB) will download automatically.

## What to look for in the output

**Good signs:**
- `Players: 8-10` per frame (expected for 5-a-side + subs/ref)
- `Ball: 1` appearing in most frames
- Average confidence above `0.5` for person detections
- Keypoints detected alongside person detections (pose estimation working)

**Concerns:**
- `Players: 0` consistently — video may be too dark, low-res, or the confidence threshold is too high
- `Ball: 0` everywhere — ball detection often needs fine-tuning or a specialised model
- Very low confidence scores (`< 0.3`) — try lowering the `conf` parameter in the script

## Notes

- `.pt` model weight files and video files (`.mp4`, `.mov`, `.avi`) are gitignored and should **not** be committed
- This project uses `pyproject.toml` exclusively — there is no `requirements.txt`
