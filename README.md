# p1-pipeline

Player 1's local Python detector benchmark workspace. Compare **YOLO26n / YOLO26s / YOLO26m / YOLO26l detection** and **D-FINE-N COCO** on the same video and sampled frames, then evaluate saved boxes against labelled frames. YOLO inputs support 640, 1280, 1920 or 2560 pixels; D-FINE supports 640/1280. The default remains 640. The old person-only pose experiment has been replaced. A shared reviewed-result format is also implemented; tracking, identity, calibration, automatic events, training and app screen/file integration remain to build.

**Latest results:** the user-identified ball at 7:00 is corrected in [CVAT task 3/job 3](http://localhost:8080/tasks/3/jobs/3), and revision 3 is frozen with **34 playing-ball labels, 42 spare-ball labels and 493 preserved person boxes**. All thirteen historical runs were re-scored equally. The new YOLO26l/1280 test starts both arms from the same 1080p image: **20/34 playing-ball matches full-frame versus 22/34 with six overlapping crops**, with no unmatched generic ball predictions in either arm. Crops cost **6.84×** the prediction time. Read the [correction, protocol and measured crop results](docs/crop-experiment-2026-10-30.md). The optional experiment is implemented and tested; native processing remains the default. Training, selective retries, learned enhancement and temporal evaluation remain to build. Task 2 and every historical frozen result remain intact.

Read [AGENTS.md](AGENTS.md) before changes. Documentation:

- [CVAT reviewer guide for new teammates](docs/cvat-reviewer-guide.md)
- [Frame 2 team labelling plan and starting dataset budget](docs/frame-two-labelling-plan.md)
- [Reusable AI labelling prompt and reviewer handover](docs/team-labelling-prompt.md)
- [Goal markings, event review and replay clip export](docs/goal-review.md)
- [First real reviewed-result bundle and app handoff](docs/reviewed-result-handoff.md)
- [Shared reviewed match-result format v1](contracts/match-result-v1/README.md)
- [Architecture and output contracts](docs/architecture.md)
- [Benchmark and annotation protocol](docs/benchmarking.md)
- [First reviewed pilot results — 30 October 2026](docs/benchmark-results-2026-10-30.md)
- [Ball detail and model-size experiment](docs/ball-detail-experiment-2026-10-30.md)
- [Corrected ball labels and revision-2 comparison](docs/benchmark-revision-2-2026-10-30.md)
- [Revision-3 correction and overlapping crops at 1080p](docs/crop-experiment-2026-10-30.md)
- [Local CVAT and AI-assisted labelling](docs/labelling.md)
- [Decisions and rationale](docs/decisions.md)
- [Verification and remaining gaps](docs/verification.md)

## Setup

Use Python 3.12 and [uv](https://docs.astral.sh/uv/). Run commands from this repository root. `uv.lock` fixes the environment; model downloads are explicit.

```sh
uv sync --locked --python 3.12 --extra dfine
mkdir -p weights vendor data runs
curl --fail --location https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26n.pt --output weights/yolo26n.pt
curl --fail --location https://github.com/Peterande/storage/releases/download/dfinev1.0/dfine_n_coco.pth --output weights/dfine_n_coco.pth
git clone https://github.com/Peterande/D-FINE.git vendor/D-FINE
git -C vendor/D-FINE checkout 956d1709314c2c6a4df6f34de232054578a7449f
```

Run downloads/clone once; preserve existing files if already set up. Use trusted checkpoints: native loading executes upstream code. D-FINE uses restricted `weights_only=True` loading. Its ignored source checkout is separately pinned above and its revision/dirty state recorded per run. YOLO-only setup can omit `--extra dfine`.

The optional larger baseline uses `--model yolo26s` and `weights/yolo26s.pt`; its explicit official download and experiment commands are in [the follow-up protocol](docs/ball-detail-experiment-2026-10-30.md#commands). Model scale is checked against checkpoint metadata even when a file has been renamed.

The focused capacity test uses `--model yolo26m` and `weights/yolo26m.pt`; see the [medium download and 1920/1280 protocol](docs/ball-detail-experiment-2026-10-30.md#focused-follow-up-1920-nano-and-1280-medium). No checkpoint downloads occur in default tests or implicitly through the runner. The requested large-model investigation uses `--model yolo26l` and the [1280/1920/2560 protocol](docs/ball-detail-experiment-2026-10-30.md#large-model-and-source-detail-test). Model input is a square side length, not video height: for this 2560×1440 source, 1920 retains a 1920×1080 picture plus padding; 2560 retains full source detail.

## Prepare reviewed labels

The user approved the [42-frame pilot in CVAT](http://localhost:8080/tasks/2/jobs/2): 493 person boxes and 32 football boxes after excluding the other pitch and correcting false equipment labels. All remaining issues are resolved and the job is complete. The scoped labels are frozen in private dataset revision `reviewed-v1-20261030`; both detectors have completed the [first measured comparison](docs/benchmark-results-2026-10-30.md). YOLO had higher person precision and lower local latency; D-FINE had higher recall. Ball recall was only 2/32 versus 8/32, so no production model is selected. See [the dataset record](docs/benchmarking.md#current-development-recording--supplied-30-october-2026) for provenance.

The [six-cell follow-up](docs/ball-detail-experiment-2026-10-30.md) is also complete: YOLO26n, D-FINE-N and YOLO26s at 640/1280. Both YOLO 1280 runs match 10/32 balls; YOLO26s has fewer unmatched ball predictions (2 versus 5) but higher local latency. D-FINE 1280 adds substantial false alarms. Both repeated 640 baseline files are byte-identical to the originals. The labels remain frozen; a possible spare-ball ambiguity near the goal is logged for a separate audit. The requested focused tests then scored 11/32 (nano/1920) and 13/32 (medium/1280). YOLO26l scored 14/32 at 1280, 13/32 at 1920 and 11/32 at 2560: full source detail did not close the gap. Read the report's error audit before interpreting unmatched boxes: some ball boxes disagree in tightness, and most medium/large unmatched predictions repeat the same uncertain near-goal item. Next: adjudicate annotations and re-evaluate saved runs consistently, then ball-focused data/crop experiments; reviewed goal geometry/events and the app handoff can proceed in parallel.

Use the local recording selected for the benchmark; no footage is bundled. Keep one upright, square-pixel source file at `data/match.mp4` for frame export and both model runs. Resolve any [geometry issues](#geometry-and-platform-limits) before annotation.

```sh
uv run --locked python export_frames.py data/match.mp4 --output data/match-frames --every-seconds 3
```

This creates lossless, original-resolution RGB PNGs in `data/match-frames/images/` and a `manifest.json` associating filenames with the source video hash, decoded frame indices, presentation timestamps, dimensions and image hashes. It selects the first frame at or after each three-second target, starting with frame 0; it does not crop, resize or transcode the video. The output directory must be new. Use `--stride N` instead of time sampling when you want indices 0, N, 2N, …; `--max-frames N` limits exported images.

Local CVAT is set up at [localhost:8080](http://localhost:8080); see the [login, agent workflow and start/stop guide](docs/labelling.md). Upload only the PNG files from `images/`, retain their filenames, and use two rectangle labels: `player` and `football`. The assistant can draft boxes and flag questions; review every included benchmark image using the [annotation procedure](docs/benchmarking.md#annotation-procedure). Export **COCO 1.0**, extract the archive locally, and convert its annotation JSON:

```sh
uv run --locked python convert_cvat.py data/cvat-export/annotations/instances_default.json --manifest data/match-frames/manifest.json --output data/match-labels.json --reviewed
```

For the current main-game pilot, **also pass `--scope data/football-clip-iqLnW_238X8-20261030/main-pitch-scope.json`**, after reviewing that boundary. Other datasets need their own region. This produces version-2 labels carrying the region, so both models' background detections are excluded consistently. Without `--scope`, conversion retains the legacy full-frame v1 convention, which requires labels for every visible person/ball. See [main-game scope](docs/benchmarking.md#main-game-scope); do not evaluate this revised pilot as full-frame labels.

`--reviewed` asserts that every image in that COCO JSON was reviewed, including images without boxes. COCO cannot distinguish an intentional empty annotation from an unfinished image. To exclude an unresolved frame, omit its image entry and all associated annotations from the COCO subset; do not simply delete its boxes. The converter records excluded frame indices. It preserves reviewed empty images, checks image references/names/dimensions and box validity, and rejects crowd/ignore/segmentation annotations. It never uploads footage or creates a CVAT task. See the [full export/import contract](docs/benchmarking.md#frame-export-and-cvat-import).

## Exchange reviewed match results

`match_result.py` provides `validate_match_result`, `loads_match_result`, `dumps_match_result` and `final_score`. The Flutter app has a matching immutable model/parser. Both validate the same [example and conformance cases](contracts/match-result-v1/README.md), including partial coverage, unknown scorers, nullable statistics, own goals, revisions and clip references.

This is a reviewed-result boundary, separate from CVAT box labels and detector predictions. It does not generate goals or clips, import results into screens, store matches or award Points. The example is synthetic. [Task 4/job 4](http://localhost:8080/tasks/4/jobs/4) provides the continuous real clip and four goal tracks. The user-corrected near and far goal mouths/lines are accepted; the near mouth bottom edge matches the user's corrected line exactly. All twelve candidate windows are human-adjudicated: G01/G09 are confirmed for Blue 1 (B1), G10 for Red with scorer unknown, and the other nine are rejected. G11 hit the post then had a saved follow-up; G12 was saved. All fourteen geometry/event issues are resolved. Image-geometry acceptance does not establish calibrated whole-ball crossings or full-clip review. Recorded goals total Blue 2 / Red 1, not a final match score. The separate `export_review_clips.py` utility has produced twelve frame-exact replays. Sampled search does not establish exhaustive clip coverage. Follow the [review guide and exporter contract](docs/goal-review.md). The first [real reviewed-result bundle](docs/reviewed-result-handoff.md) now contains the three confirmed goals, numbered roster aliases, explicit partial coverage and three unchanged replay clips. Python and Dart validate it; no final score is available. App import, persistence and playback remain to build.

## Compare detectors

Place upright, square-pixel footage at `data/match.mp4`. CPU is the default; use the same `--device cuda:0` for both on a CUDA machine. MPS is outside this baseline. Each output directory must be new.

```sh
uv run --locked --extra dfine python benchmark.py data/match.mp4 --model yolo26n --output runs/match-yolo26n --stride 1 --confidence 0.05
uv run --locked --extra dfine python benchmark.py data/match.mp4 --model dfine-n --output runs/match-dfine-n --stride 1 --confidence 0.05
```

For time-selected labels, use stride 1 on the **same original video**, with no frame cap, so every labelled index exists in both runs. If frames were exported with `--stride N`, both runs can use the same stride instead. `--stride 5` infers frames 0, 5, 10, … while still decoding intervening frames. `--max-frames 100` limits sampled frames and must not omit any labelled index. Three warmup predictions on the first sampled frame are excluded from prediction latency/counts; change with `--warmup`. All models use batch 1 and FP32 with native preprocessing. `--input-size 640` is the unchanged default; `--input-size 1280` and YOLO-only `--input-size 1920` / `2560` record their chosen size in the manifest. D-FINE sizes above 1280 and all other sizes are rejected. Compare equal sizes across models, or explicitly describe a within-model size experiment.

Outputs are `manifest.json` (status, hashes, settings, environment, revisions and measurements) and `detections.jsonl` (sampled frame indices, timestamps, dimensions and normalized boxes). The schema's `player` means **COCO person**, including spectators/referees; `football` means **COCO sports ball**. Counts/confidence are not accuracy measures.

Optional `--spatial-mode full-1080p` and `--spatial-mode ball-crops-1080p` run the [fixed crop experiment](docs/crop-experiment-2026-10-30.md#reproduction). Both require 16:9 source pixels at least 1920×1080 and use the same resize/ball merge; the second adds six ball-only views. Keep model/input/device/thresholds identical and use new output directories. Saved coordinates and timestamps still refer to the original source. The default `native` path is unchanged. This experiment does not implement app upload rules or AI enhancement.

## Evaluate labels

Use the converted `data/match-labels.json`, or create it directly using the [label contract](docs/benchmarking.md#label-file). It must identify the exact video hash and frame indices present in both runs. Label all relevant objects on included frames; an empty annotation list explicitly marks a negative frame.

```sh
uv run --locked python evaluate.py runs/match-yolo26n --labels data/match-labels.json --confidence 0.25 --iou 0.5 > runs/match-yolo26n/evaluation.json
uv run --locked python evaluate.py runs/match-dfine-n --labels data/match-labels.json --confidence 0.25 --iou 0.5 > runs/match-dfine-n/evaluation.json
```

Reports contain per-class precision/recall and TP/FP/FN at these thresholds, not COCO mAP. Unlabelled frames are excluded; missing labelled frames fail. Scoped v2 labels additionally exclude detections outside the recorded region and report excluded counts per class. Ground-truth boxes outside that scope fail validation. Evaluation confidence cannot be below the saved inference floor. Shell redirection replaces an existing report; use new filenames to retain threshold experiments.

For comparisons, evaluate strictly above that floor (as above): YOLO's native gate is strict `>`, while the common evaluator uses `>=`. This avoids an exact-floor equality difference between adapters.

## Checks and CI

```sh
uv run --locked python -m coverage run --branch -m unittest discover -s tests -v
uv run --locked python -m coverage report -m
git diff --check
```

Tests cover mocked model boundaries, lifecycle/timing contracts, malformed inputs/evaluation, lossless frame export, reviewed COCO conversion and their generated-video round trip. They require no weights, private recordings, network calls or GPU. CI installs only the `dev` group and uploads coverage, including both annotation tools. Reproduce its lightweight environment without replacing your model environment:

```sh
UV_PROJECT_ENVIRONMENT=.venv-ci uv sync --locked --only-group dev --python 3.12
.venv-ci/bin/python -m coverage run --branch -m unittest discover -s tests -v
.venv-ci/bin/python -m coverage report -m
```

Real-checkpoint smoke test (FFmpeg on PATH is needed to create the pattern):

```sh
ffmpeg -hide_banner -loglevel error -f lavfi -i testsrc2=size=320x180:rate=10:duration=1 -c:v libx264 -pix_fmt yuv420p data/smoke.mp4
uv run --locked --extra dfine python benchmark.py data/smoke.mp4 --model yolo26n --output runs/smoke-yolo26n --stride 2 --max-frames 3 --warmup 1
uv run --locked --extra dfine python benchmark.py data/smoke.mp4 --model dfine-n --output runs/smoke-dfine-n --stride 2 --max-frames 3 --warmup 1
```

Synthetic footage validates execution and contracts, not football accuracy. See the verification record for actual checks/hardware.

## Geometry and platform limits

The decoder requires strictly increasing presentation timestamps and rejects display-rotation/mirroring metadata and non-square pixels. Normalize geometry **before annotation** and use that exact file for both models. For conventional rotation metadata, FFmpeg's default autorotation can be applied while transcoding:

```sh
ffmpeg -i data/original.mp4 -map 0:v:0 -an -vf "scale=trunc(iw*sar/2)*2:ih,setsar=1" -c:v libx264 -pix_fmt yuv420p -metadata:s:v:0 rotate=0 data/match.mp4
```

Inspect orientation/aspect ratio; complex transforms need explicit verification. Transcoding changes hashes and may change frame indexing, so regenerate labels. The runner fails rather than guessing geometry.

macOS PyAV/OpenCV wheels load different bundled FFmpeg libraries and can emit duplicate AVFoundation-class warnings. Headless OpenCV retains this collision. Successful file-based CPU smoke tests do not establish long-run or camera/audio stability. Use the intended Linux/CUDA environment for deployment-performance comparisons.

## Upstream references

- [YOLO26](https://docs.ultralytics.com/models/yolo26/) and [prediction conventions](https://docs.ultralytics.com/modes/predict/)
- [D-FINE](https://github.com/Peterande/D-FINE) and [native inference](https://github.com/Peterande/D-FINE/blob/956d1709314c2c6a4df6f34de232054578a7449f/tools/inference/torch_inf.py)
- [PyAV timestamps](https://pyav.basswood.io/docs/stable/api/time.html) and [side data](https://pyav.basswood.io/docs/stable/api/sidedata.html)

Review upstream code, checkpoint and dataset licences before commercial integration; this benchmark makes no app-distribution decision.
