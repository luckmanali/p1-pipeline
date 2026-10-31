# Overlapping ball crops at 1080p — 30 October 2026

## Protocol recorded before inference

The user requested resolution of the missing ball at 7:00, then a bounded crop comparison. Original frames 418.4–422.8 seconds show the goalkeeper rolling the net-occluded object out onto the pitch. The earlier shoe interpretation was incorrect. One rectangle `[128,684,178,733]` was added at CVAT frame 35/source 10,500, following the user's object identification and explicit instruction to resolve it. The assistant adjudicated these bounds from source pixels; no separate human drawing/approval of the exact coordinates is claimed. All 568 existing rectangles are unchanged. Task 3 remains acceptance/completed with the correction recorded on its review issue.

Private `reviewed-v3-20261030` retains the API snapshots, correction comment, human instruction, full task backup, COCO export, role ledger and converted labels. Revision 3 contains **493 people, 34 playing-ball instances and 42 spare-ball instances** across all 42 images. Label-schema version remains 2. Label SHA-256 is `189c12833b539613b95911566ed119dbadf2f863bb0036df12b39c7cdb0731ff`. Previous tasks/frozen revisions and results are preserved. The added ball does not establish a goal event.

All thirteen previous runs were re-scored equally: playing-ball match counts are unchanged, so the previously best large/1280 result is now **19/34**. This is a label correction, not a detector regression. The following two new runs isolate an explicitly resized analysis image and crop processing; do not substitute that historical native-source result for the new control.

| Setting | Full-frame control | Ball-crop arm |
|---|---|---|
| Source | Same 2560×1440 RGB source, original SHA-256/timestamps | Same |
| Analysis image | PyAV RGB bilinear resize to 1920×1080 | Identical resize, before any cropping |
| Detector | Local YOLO26l COCO checkpoint, input 1280, CPU, FP32, batch 1, four Torch threads | Same |
| Views | One full frame | Full frame plus six 960×640 overlapping crops |
| Crop positions | None | x=0/480/960; y=0/440, row-major |
| Overlap | None | 50% horizontally; 200/640=31.25% vertically |
| Merge | Ball-only confidence-ordered NMS, IoU ≥0.50 suppressed; stable ties | Same across all views |
| People | Full-frame predictions preserved | Full-frame predictions preserved; crop people discarded |
| Sampling | Original indices 0,300,…,12,300; all 42 reviewed images | Same |
| Scoring | Confidence 0.25, matching IoU 0.50, reviewed main-pitch scope | Same |
| Saved floor / warmup | 0.05 / three complete frame predictions | Same; each warmup includes all seven views |

The model tensor remains 1280 square in both arms. Full-frame picture detail is 1280×720 after letterboxing; a 960×640 crop becomes approximately 1280×853 inside that tensor. The crop uses only information from the common 1080p image. It changes object scale/context and incurs seven model calls, not new source detail. No annotation-guided crop selection, enhancement, threshold search, fine-tuning or tracking is used. This fixed grid is a first development experiment, not a search over tile settings.

The wrapper maps crop-normalized boxes through crop origin/extent to full-frame normalized coordinates. Aspect ratio is unchanged, so these also describe the original source. Saved row dimensions, video hash and presentation timestamps remain original; the manifest separately describes the analysis image and every crop. The experiment rejects non-16:9 sources, smaller images and malformed RGB arrays rather than stretching/upscaling them. This is an experiment constraint, not implemented app upload enforcement.

Retain all ball candidates above the saved floor and apply the same merge to both arms. The full-frame control therefore also applies ball NMS, unlike historical native runs. IoU-only merging may leave duplicates for partial edge boxes or let a higher-confidence inaccurate crop box replace an accurate full-frame box; count these failures rather than tuning them away. Scope filtering remains in the evaluator after merging.

## Reproduction

From the pipeline root, with the existing trusted local checkpoint and locked environment, run sequentially in new directories:

```sh
OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 uv run --locked python benchmark.py data/football-clip-iqLnW_238X8-20261030/source/FOOTBALL_CLIP_1440p.mp4 --model yolo26l --input-size 1280 --spatial-mode full-1080p --stride 300 --max-frames 42 --warmup 3 --confidence 0.05 --output runs/football-crops-v1-20261030-full-1080p-cpu
OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 uv run --locked python benchmark.py data/football-clip-iqLnW_238X8-20261030/source/FOOTBALL_CLIP_1440p.mp4 --model yolo26l --input-size 1280 --spatial-mode ball-crops-1080p --stride 300 --max-frames 42 --warmup 3 --confidence 0.05 --output runs/football-crops-v1-20261030-ball-crops-1080p-cpu
uv run --locked python evaluate.py runs/football-crops-v1-20261030-full-1080p-cpu --labels data/football-clip-iqLnW_238X8-20261030/reviewed-v3-20261030/benchmark-labels-v2.json --confidence 0.25 --iou 0.5
uv run --locked python evaluate.py runs/football-crops-v1-20261030-ball-crops-1080p-cpu --labels data/football-clip-iqLnW_238X8-20261030/reviewed-v3-20261030/benchmark-labels-v2.json --confidence 0.25 --iou 0.5
```

These commands require the private source and labels. Default `--spatial-mode native` retains previous behavior and manifests. No new dependency or weights are required. Local execution can use `uv run --locked --no-sync` to retain the already-installed optional CVAT/D-FINE environment; the captured package manifest records the actual runtime.

## Acceptance and interpretation

Report playing-ball TP/FN separately from spare matches, generic ball precision/false alarms, unchanged person metrics, per-frame gains/losses and mean/median/p95 total prediction latency. The latency includes resize, every view and merge; decoding/writing and warmup remain separate. Generic precision is not active-ball precision. There is no active-ball selector.

The proposed initial quality goal remains ≥90% visible playing-ball recall and ≥95% active-ball precision, to be tested on independent matches and dense sequences. This repeatedly examined 42-image development sample cannot establish a release gate. Lower counts are useful evidence about this fixed crop recipe; do not discard difficult frames or rewrite labels to improve the score.

## Results

Both real-checkpoint runs completed with identical source/checkpoint/runtime/settings apart from spatial mode. At confidence 0.25 and matching IoU 0.50:

| Measure | Full-frame control | Full frame + six crops |
|---|---:|---:|
| Playing-ball matches | **20/34 (58.8%)** | **22/34 (64.7%)** |
| Missed playing balls | 14 | 12 |
| Spare-ball matches | 24/42 | 28/42 |
| Generic ball TP / FP / FN | 44 / 0 / 32 | 50 / 0 / 26 |
| Generic ball precision | 100% on this sample | 100% on this sample |
| Mean prediction time per sampled frame | 651.8 ms | 4459.1 ms |
| Median / p95 prediction time | 645.0 / 753.8 ms | 4408.9 / 4773.3 ms |
| Total prediction time, 42 frames | 27.4 s | 187.3 s |
| Decode/predict/write time, including warmup | 84.8 s | 258.3 s |

The crop arm recovers **two playing balls**, CVAT frames **26 and 28** (5:12 and 5:36), with no lost matches. Both already had low-confidence overlapping boxes in the control: confidence rises from 0.091→0.471 and 0.093→0.323; IoU rises from 0.758→0.877 and 0.603→0.761 respectively. Original-pixel inspection confirms those mapped predictions cover the reviewed playing balls. Four additional matches are spares, not playing-ball improvements. All full-frame person predictions are byte-identical between arms, giving 481 TP / 37 FP / 12 FN in scope.

Prediction takes **6.84× longer** for a **5.9 percentage-point** playing-ball recall gain. These single-run timings are from the local Apple M5 Pro CPU, four Torch threads, FP32; they are not GPU timings, repeated timing estimates or full-match throughput. No unmatched generic ball predictions occurred at this threshold, but the sample is small and this does not establish perfect precision or spare rejection in an active-ball tracker.

Of the crop arm's twelve remaining playing-ball misses, four have sufficiently overlapping saved responses below confidence 0.25 (frames 9,20,25,29), one has insufficient overlap (frame 0), and seven have no saved in-scope response reaching IoU 0.1 (4,14,16,18,21,35,40). The saved floor is 0.05, so absence of a saved response is not proof of no weaker raw activation. The newly labelled net-occluded ball at 7:00 is missed in both arms. Thresholds were not changed after seeing these diagnostics.

The new full-frame control is 20/34, versus historical native-source large/1280 at 19/34. The control has an explicit intermediate 1080p bilinear resize and ball merge, so it is a separate condition. Use **20 versus 22** to attribute the measured gain to crop views. Do not credit the entire historical 19→22 change to cropping.

## Verification and decision

**171 offline tests passed in both the full runtime environment and the lightweight CI environment**, including 15 new behavioral tests. Coverage is **100% statement/branch for `crop_inference.py`**, 99% for the runner and 98% overall. The existing suite covers the unchanged default/native path; new tests cover resize/geometry, RGB pixels, grid coverage and seam objects, source-coordinate mapping, exact IoU/tie rules, malformed outputs, people preservation, CLI/manifests, warmup and failure handling. CI discovers these tests automatically and now includes the new module in coverage. No dependency changed; hosted GitHub Actions was not run.

Real inference supplied the runtime smoke check as well as quality measurements. Both manifests completed, all 42 rows retained original dimensions/indices/timestamps, and every generic score reconciles with the independent playing/spare diagnostic. The two runs use the same source/checkpoint hashes, package environment and CPU thread count; person predictions match exactly. Historical labels, drafts and thirteen runs are retained, with checksums verified separately. The local CVAT read-back confirms 569 rectangles, the intended extra net-occluded ball, no open issues, and the original task 2 unchanged. COCO can reorder unchanged annotations; verification compares exact class/box multisets rather than array order.

Private `crop-experiment-v1-20261030/` retains the pre-inference plan and source snapshot, logs, both evaluations, role matches, miss diagnostics, a visual inspection of the recovered balls, tests and integrity records. `reviewed-v3-20261030/` separately retains correction/export provenance and re-scoring of all previous settings.

**Decision:** keep this fixed recipe as a measured experiment, not the default processing path. It helps a little but its cost and 64.7% playing-ball recall do not meet the proposed quality goal. Next prioritise varied football-specific training labels and independent validation, then evaluate confidence calibration and temporal continuity without tuning on this same clip. A selective crop retry could reduce average cost, but its trigger/quality must be measured before claiming that saving. Learned enhancement remains untested, and no tracking, training or automatic goal detection was added here.
