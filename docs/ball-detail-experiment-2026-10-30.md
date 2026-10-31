# Ball detail and model size — 30 October 2026

**Latest:** [reviewed revision 2 and equal re-scoring](benchmark-revision-2-2026-10-30.md) are now complete. YOLO26l/1280 matches 19/33 playing-ball labels; spare matches are reported separately. This document retains the original revision-1 experiments, subsequent draft history and unrun future proposals. The 14/32 results below are historical, not the latest corrected scores.

**Completed:** the initial six-cell comparison, two focused tests and three requested YOLO26l resolution tests all scored the same frozen 42 frames. The highest primary ball match count is 14/32 with YOLO26l/1280; large/1920 and large/2560 score 13/32 and 11/32. Higher resolution is not consistently better. Error inspection also found loose-box disagreements and a recurring uncertain near-goal object, so annotation adjudication is needed before definitive model selection. No production model or automatic-goal capability is established.

## Protocol fixed before inference

The [first pilot](benchmark-results-2026-10-30.md) matched only 2/32 balls with YOLO26n and 8/32 with D-FINE-N. The median ball was approximately 7.5 pixels wide at 640 input. This follow-up tests whether more image detail or a larger model improves ball recall without unacceptable false positives. It is development exploration on the already-inspected clip, not held-out validation.

Run six cells: **YOLO26n, D-FINE-N and YOLO26s, each at 640 and 1280 square input**. Repeat the two original 640 cells with the updated runner to check compatibility. Compare sizes within each model; compare YOLO n/s at each equal size. YOLO26s is the first larger baseline because it reuses the installed runtime and class contract; upstream lists it as a higher-capacity COCO detector. That does not guarantee better football performance. See [official model variants](https://docs.ultralytics.com/models/yolo26/) and [input-size semantics](https://docs.ultralytics.com/modes/predict/).

Keep these controls fixed:

- Original video SHA-256 `eac1a39d83c727f142d33e6a8ede112224ab14d925680a3584254a83fa397984`; all 42 stride-300 samples, no frame cap.
- Frozen revision-1 labels SHA-256 `02e38f01f36c88d060fe3320dfb737534333c395ecbd34f565912ce1f51fff0b`, including the same scope, 493 people and 32 balls. No edits or extra exclusion regions.
- Native FP32/batch 1, CPU on the same host, four Torch threads, three warmups, saved floor 0.05, scoring confidence 0.25 and IoU 0.5.
- Same locked dependencies and existing N checkpoints; explicitly download the official `yolo26s.pt` asset and retain its hash. No fine-tuning, augmentation, tiling, per-model threshold search or paid compute.
- Sequential runs, one pass per cell, new output directories. Timing remains descriptive local CPU evidence; neither a full-frame match-processing measurement nor isolated/repeated performance evidence.
- YOLO retains square letterboxing; D-FINE retains native stretching. At 1280, each dimension doubles and the input pixel count quadruples. D-FINE strictly loads the original checkpoint at 640, then regenerates only positional embeddings, anchors and validity masks before deployment; learned weights remain unchanged.

Record per-class TP/FP/FN, precision/recall, scoped exclusions, mean/median/p95 prediction latency and decode/predict/write time. Inspect gains, remaining ball misses and extra ball predictions at the same operating point. A useful development configuration improves recall while keeping false alarms/review effort manageable; this small pilot does not establish a production acceptance threshold. Retain all cells even if 1280 is worse. Geometry/setup failures must be recorded and fixed before claiming a result.

Before inference, retain this protocol, executable source/test snapshots and hashes, checkpoint metadata, exact commands and environment under ignored `data/football-clip-iqLnW_238X8-20261030/ball-detail-v1-20261030/`. Never overwrite `reviewed-v1-20261030/` or its original runs. The original pre-inference protocol is retained in that source snapshot; measured results follow below.

## Commands

Download once, preserving any existing file:

```sh
test ! -e weights/yolo26s.pt && curl --fail --location https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26s.pt --output weights/yolo26s.pt
```

Use `--model yolo26n`, `dfine-n` or `yolo26s`, and `--input-size 640` or `1280`; the default remains 640. Example for a new run:

```sh
OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 VECLIB_MAXIMUM_THREADS=4 NUMEXPR_NUM_THREADS=4 .venv/bin/python benchmark.py data/football-clip-iqLnW_238X8-20261030/source/FOOTBALL_CLIP_1440p.mp4 --model yolo26s --input-size 1280 --output runs/football-ball-detail-v1-20261030-yolo26s-1280-cpu --stride 300 --confidence 0.05 --warmup 3
.venv-ci/bin/python evaluate.py runs/football-ball-detail-v1-20261030-yolo26s-1280-cpu --labels data/football-clip-iqLnW_238X8-20261030/reviewed-v1-20261030/benchmark-labels-v2.json --confidence 0.25 --iou 0.5 > runs/football-ball-detail-v1-20261030-yolo26s-1280-cpu/evaluation.json
```

Use a different new directory for each cell or later repeat. Evaluation redirection replaces an existing file, so preserve prior reports.

## Measured results

Confidence 0.25, IoU 0.50, unchanged main-game scope. TP/FP/FN are matches, unmatched predictions and missed labels against the approved answer key. These are operating-point counts, not COCO mAP.

### Football

| Model | Input | TP | FP | FN | Precision | Recall |
|---|---:|---:|---:|---:|---:|---:|
| yolo26n | 640 | 2 | 0 | 30 | 100.0% | 6.250% |
| yolo26n | 1280 | 10 | 5 | 22 | 66.7% | 31.250% |
| dfine-n | 640 | 8 | 13 | 24 | 38.1% | 25.000% |
| dfine-n | 1280 | 9 | 77 | 23 | 10.5% | 28.125% |
| yolo26s | 640 | 4 | 0 | 28 | 100.0% | 12.500% |
| yolo26s | 1280 | 10 | 2 | 22 | 83.3% | 31.250% |

YOLO’s 100% precision at 640 rests on only two or four ball predictions. It is not evidence of reliable ball detection. Both YOLO 1280 runs match the **same ten labelled balls**, retaining all their 640 matches. D-FINE at 1280 gains two matches but loses one from 640; its net increase is only one.

The 32 labels are one visible ball in each of 32 sampled frames; the remaining ten frames have no labelled in-scope ball. Thus 10/32 is 31.25% recall on these sampled ball instances at the chosen confidence/overlap thresholds. It does not measure the fraction of the full video where the ball was tracked or the fraction of goals detected. Samples are twelve seconds apart.

A subsequent read-only miss audit found three additional YOLO26n and five additional YOLO26s boxes with IoU ≥0.5 but confidence below 0.25. Of the other misses, nano has 19 labels with no saved in-scope ball box overlapping at IoU ≥0.1; small has 16 such labels plus one nearby box with insufficient overlap. The saved floor is 0.05, so this does not prove no weaker raw model response existed. Lowering the scoring threshold alone cannot recover all 22 misses and would also admit extra predictions. This diagnostic is retained privately as `miss-audit.json`; original scores remain unchanged.

### People

| Model | Input | TP | FP | FN | Precision | Recall |
|---|---:|---:|---:|---:|---:|---:|
| yolo26n | 640 | 385 | 38 | 108 | 91.0% | 78.1% |
| yolo26n | 1280 | 448 | 63 | 45 | 87.7% | 90.9% |
| dfine-n | 640 | 449 | 250 | 44 | 64.2% | 91.1% |
| dfine-n | 1280 | 405 | 514 | 88 | 44.1% | 82.2% |
| yolo26s | 640 | 436 | 23 | 57 | 95.0% | 88.4% |
| yolo26s | 1280 | 470 | 63 | 23 | 88.2% | 95.3% |

The person class is spatially scoped, not identity-verified roster membership. YOLO26s at 640 has the highest person precision in this experiment; at 1280 it has the highest recall. Scope exclusions for people are 16/259 for YOLO26n, 392/392 for D-FINE-N and 139/258 for YOLO26s at 640/1280; no ball predictions were excluded. Exclusions are reported rather than counted as false positives.

### Local CPU timing

| Model | Input | Mean prediction | Median | p95 | Decode/warmup/sampled prediction/write |
|---|---:|---:|---:|---:|---:|
| yolo26n | 640 | 30.7 ms | 29.8 ms | 35.6 ms | 55.0 s |
| yolo26n | 1280 | 100.4 ms | 95.9 ms | 123.2 ms | 57.9 s |
| dfine-n | 640 | 72.0 ms | 67.6 ms | 93.7 ms | 58.5 s |
| dfine-n | 1280 | 190.6 ms | 188.8 ms | 233.0 ms | 65.8 s |
| yolo26s | 640 | 56.5 ms | 54.0 ms | 68.0 ms | 57.8 s |
| yolo26s | 1280 | 224.8 ms | 211.2 ms | 316.9 ms | 67.1 s |

Apple M5 Pro, 48 GiB RAM, four threads, one pass per cell with desktop services active. Prediction includes native preprocessing/model/postprocessing; decoding and warmup are outside that column. The last column decodes the source and infers **only 42 samples**, not every video frame. This is not a repeated performance study or a GPU/mobile/full-match throughput claim. Existing macOS duplicate-AVFoundation warnings remained; all runs completed.

## Inspected errors and next decision

- At CVAT frame 1, YOLO26s 1280 recovers the near-right ball at a player's feet. At frame 40, the approved small ball box in crowded play remains unmatched. More pixels do not resolve all blur, occlusion or localization failures.
- D-FINE 1280 repeatedly assigns the ball class to a white pitch marking. The frame-3 and frame-30 overlays show this; frame 30 also loses a ball match that D-FINE 640 had found. Higher resolution is a poor trade-off for this checkpoint at the fixed threshold.
- YOLO26s 1280's two unmatched ball boxes, on frames 7 and 19, point to the same pale round object among the near-goal items. Original-resolution crops are retained. Its exact object type is uncertain from this inspection: audit whether it is a spare ball before expanding the answer key. It is counted as unmatched under the frozen labels, not established as a non-ball solely because the label is absent. Do not silently modify this scored revision to improve a candidate's result.

Use YOLO26s 640 as a candidate for efficient **assisted person-box drafting**, and retain YOLO26n/YOLO26s 1280 as ball-development baselines with different latency/false-alarm trade-offs. These are provisional workflow choices, not production selection; labels still need human review. In the initial six-cell comparison, the best measured ball recall was only 10/32, with 22 misses. Avoid more open-ended model-size searches on this same small clip.

The next product work is goal/pitch geometry and continuous-footage goal review, followed by a real reviewed result and playable clips in Flutter. For further ball work, audit the near-goal object separately, gather dense reviewed event windows and independent recordings, then define a separate ball-focused crop/tiling or training experiment. Any label correction requires a new version and re-evaluation of every candidate against that same version. Nothing in these sparse samples establishes ball trajectories, goal-line crossings or scorer identity.

The user subsequently requested the two focused tests and then a large-model/source-detail investigation. Their separate protocols and results follow below. Geometry and reviewed goal events can proceed independently of these detector experiments.

## Verification and retained evidence

149 offline tests passed (98% rounded overall statement/branch coverage, 100% adapters). The real D-FINE check confirmed all 367 deployed learned-parameter tensors remained identical between sizes, verified the 1280 input tensor and regenerated geometry, and completed synthetic prediction. YOLO native smoke checks also passed. Both new 640 baseline detection files are **byte-identical** to their original pilot files; no legacy behavior change was observed.

Every cell has 42 matching original frame indices, dimensions and timestamps; identical source/label/scope hashes, environment, sampling and scoring; and recorded actual input size and checkpoint metadata. The diagnostic matcher reproduced every official TP/FP/FN total. Frozen labels and prior run artifacts remain unchanged. See [verification](verification.md) for checks and unverified platforms.

Private evidence: `data/football-clip-iqLnW_238X8-20261030/ball-detail-v1-20261030/` contains the plan, exact commands, source/test snapshots, checkpoint-source record, native-smoke/test logs, comparison JSON, per-frame diagnostics and 30 ball overlays for frames 1, 2, 3, 30 and 40, plus near-goal crops. Both YOLO26s frame-1/frame-40 and D-FINE frame-3/frame-30 overlays and both near-goal crops were visually inspected. Model outputs are under `runs/football-ball-detail-v1-20261030-<model>-<size>-cpu/`; each has its completed manifest, detections and evaluation.

YOLO26s was downloaded from the official release linked above. SHA-256: `646f8bc3fe0a656803d95c294f7852321748cb29d13466a1af8862e2db384a1b`. The existing N checkpoint hashes and locked runtimes were unchanged. D-FINE used clean revision `956d1709314c2c6a4df6f34de232054578a7449f`. No new dependency, fine-tuning, threshold search, label edit, cloud deployment or paid compute was used.

## Focused follow-up: 1920 nano and 1280 medium

**Protocol recorded before these two runs, 30 October 2026.** The user requested the two proposed focused tests. Run YOLO26n at 1920 against its existing 1280 baseline to test extra detail, and YOLO26m at 1280 against the nano/small 1280 baselines to test extra capacity. Only these two new cells are planned; do not add a size/model sweep based on their outcomes.

Reuse the exact original video, frozen revision-1 labels/scope, all 42 stride-300 samples, CPU/four threads/FP32/batch 1, three warmups, saved confidence floor 0.05, evaluation confidence 0.25 and IoU 0.5. Keep native square letterboxing and existing postprocessing. Each cell is one sequential local CPU pass with a new output directory; compare timing descriptively because the previous cells were measured earlier. Retain the same locked runtime and existing nano checkpoint, explicitly download/hash the official medium checkpoint, and preserve the protocol, source/tests and commands before inference. The directory is `data/football-clip-iqLnW_238X8-20261030/ball-focus-v2-20261030/`; the `v2` identifies the experiment, not a new label revision.

Report person/ball TP/FP/FN, matched-frame gains/losses, scoped exclusions and latency. Audit the ten images with no labelled ball separately to explain the recall denominator. Do not silently add/remove ground truth or reclassify uncertain images as true negatives after looking at candidate outputs; any correction requires a new dataset revision and equal re-evaluation of all candidates.

The runner extension adds YOLO26m and YOLO input 1920. D-FINE remains restricted to its verified 640/1280 path. Original-coordinate output, checkpoint-scale validation, native defaults, existing file protection and failure handling remain required.

Explicit medium download, preserving an existing checkpoint:

```sh
test ! -e weights/yolo26m.pt && curl --fail --location https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26m.pt --output weights/yolo26m.pt
```

Use the earlier environment/evaluator commands, with `--model yolo26n --input-size 1920` or `--model yolo26m --input-size 1280`, and new `runs/football-ball-focus-v2-20261030-<model>-<size>-cpu/` directories.

### Focused measured results

Both runs completed with unchanged labels/settings. Previous 1280 baselines are shown for comparison; latency is descriptive across separate passes.

| Model | Input | Ball TP / FP / FN | Ball precision / recall | Person TP / FP / FN | Mean prediction |
|---|---:|---|---|---|---:|
| YOLO26n | 1280 | 10 / 5 / 22 | 66.7% / 31.25% | 448 / 63 / 45 | 100.4 ms |
| YOLO26s | 1280 | 10 / 2 / 22 | 83.3% / 31.25% | 470 / 63 / 23 | 224.8 ms |
| YOLO26n | 1920 | 11 / 3 / 21 | 78.6% / 34.375% | 464 / 54 / 29 | 232.0 ms |
| YOLO26m | 1280 | 13 / 34 / 19 | 27.7% / 40.625% | 473 / 42 / 20 | 528.8 ms |

Nano/1920 retains nine previous matches, gains CVAT 3/7 and loses 41: net one extra match for about 2.3× the earlier nano/1280 prediction time. Medium/1280 retains all ten and gains CVAT 3/6/30, with many more unmatched predictions. Neither establishes a strong overall ball solution. No parameters, labels or thresholds were adjusted after seeing these results.

153 offline tests passed at this stage (98% rounded overall coverage; adapters 100%). Native synthetic checks verified exact input tensors at 1920/1280, original-coordinate outputs and the requested architecture. Both runs contain all 42 original indices/timestamps/dimensions with matching source/label/scope/runtime settings, and diagnostic matching reproduces official counts. Private evidence includes `comparison.json`, `error-inspection.json`, native smoke/test logs and executable source snapshots. Medium checkpoint SHA-256: `401cea9ab23ad19246ff7744859816bc599f350e93c9dd30367b6f0a0745d0b7`.

### Why 42 images produce a denominator of 32

Recall counts labelled object instances, not images: this revision has one ball box in each of 32 images, and no ball box in ten. All 42 images are evaluated; unmatched ball predictions in any included image contribute false positives. An image without a visible ball is not a missed ball simply because the match physically contains one.

The ten zero-ball-label images are CVAT frames **8, 10, 12, 16, 19, 24, 32, 35, 37 and 38** (1:36, 2:00, 2:24, 3:12, 3:48, 4:48, 6:24, 7:00, 7:24, 7:36). Original draft notes recorded no confidently visible/separable ball, often around overlapping far-goal/right-board players or image boundaries. The user approved the task; that does not independently prove physical absence in every image.

A subsequent read-only visual audit retained all ten image previews and five-frame context sheets with source PTS. At frame 19, context shows the playing ball leaving the bottom of the image before the exact sample. The remaining nine still need visibility adjudication; some are consistent with occlusion, but this audit does not certify them as true negatives. The separate pale round near-goal item also remains unresolved. No frozen annotations were changed. See private `ball-focus-v2-20261030/absence-audit/findings.json` for per-frame findings and limitations.

For a stronger benchmark, adjudicate uncertain frames before scoring a new revision. Correct missed visible boxes, or exclude an unresolved whole frame under the existing protocol; apply the same revision to every candidate. Retain this historical revision and its scores rather than silently improving an answer key after inspecting predictions.


## Large-model and source-detail test

**Protocol recorded before inference, 30 October 2026.** Following the two focused runs, the user requested YOLO26l and higher resolution to investigate the gap to 32/32. Run exactly three new cells: **YOLO26l at 1280, 1920 and 2560**. Compare large/1280 against medium/1280 for capacity; compare the three large-model cells for detail. This supersedes the earlier restriction on additional cells only for this explicitly requested experiment.

Keep the same frozen revision-1 labels, 42 frames, video/scope hashes, locked runtime, CPU/four threads/FP32/batch 1, stride 300, three warmups, saved floor 0.05, confidence 0.25 and IoU 0.5. Use sequential passes and new output directories; no fine-tuning, augmentation, crops/tiles or implicit model downloads. Download the official large detection checkpoint explicitly and hash it. Save source/tests/protocol/commands before inference in `data/football-clip-iqLnW_238X8-20261030/ball-large-v3-20261030/`. Here v3 denotes the experiment, not a label change.

Source resolution and model input are different. The original file is 2560×1440. With the runner's aspect-preserving square letterbox, input 1280 contains a 1280×720 picture, 1920 contains 1920×1080, and 2560 contains the full 2560×1440 picture; the remaining rows are padding. Thus 1920 preserves 1080p-equivalent picture detail and 2560 preserves the original 1440p detail. Neither invents pixels missing from the recording. Verify actual native tensor dimensions before interpreting results. A median 30-pixel-wide source ball becomes approximately 15, 22.5 or 30 pixels wide respectively.

Report TP/FP/FN, precision/recall, latency and paired gains/losses. Diagnose all 32 labelled instances using saved boxes: correct overlap above the threshold, correct overlap below it, poor localization, or no nearby saved ball prediction. Also report fixed confidence 0.10 and 0.50 sensitivity at IoU 0.5 as diagnostics, without replacing the primary 0.25 score. Do not tune labels, confidence or IoU to manufacture 32/32. Even 32/32 on this repeatedly inspected development clip would need acceptable false alarms and independent-match validation.

```sh
test ! -e weights/yolo26l.pt && curl --fail --location https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26l.pt --output weights/yolo26l.pt
```

Use the earlier fixed environment/benchmark/evaluator commands with `--model yolo26l`, each listed size, and new `runs/football-ball-large-v3-20261030-yolo26l-<size>-cpu/` directories. D-FINE remains restricted to 640/1280. Measured results follow below.


### Large-model measured results

All three requested cells completed. Picture dimensions exclude letterbox padding. Primary scoring stays at confidence 0.25 / IoU 0.50; FP means unmatched against the frozen labels, not independently established non-ball objects.

| Model input | Picture detail | Ball TP / FP / FN | Precision / recall | Person TP / FP / FN | Mean prediction |
|---:|---|---|---|---|---:|
| 1280×1280 | 1280×720 | 14 / 27 / 18 | 34.1% / 43.750% | 480 / 37 / 13 | 640.3 ms |
| 1920×1920 | 1920×1080 | 13 / 30 / 19 | 30.2% / 40.625% | 483 / 20 / 10 | 1518.3 ms |
| 2560×2560 | 2560×1440 | 11 / 6 / 21 | 64.7% / 34.375% | 473 / 28 / 20 | 3069.6 ms |

Large/1280 retains all medium/1280 matches and adds CVAT 36. Moving large to 1920 gains CVAT 0 but loses 30/36; 2560 additionally loses 0/34 and gains none relative to 1920. More image detail therefore does not monotonically improve this pretrained detector on the clip. The full-source-detail run takes about 4.8× large/1280's mean CPU prediction time. All runs are single passes on the same Apple M5 Pro CPU/four threads, with desktop services active; no GPU, repeated timing study or full-frame match throughput is claimed.

Median/p95 prediction latency is 637.4/732.0 ms at 1280, 1495.8/1660.7 ms at 1920 and 3011.4/3566.1 ms at 2560. Decode/warmup/**sampled** prediction/write totals are 84.2, 124.3 and 195.8 seconds respectively. Each still infers only the 42 selected frames.

### What prevents 32/32 under these settings?

The large/1280 run divides the 32 labelled balls as follows:

| Saved response | Instances | Interpretation |
|---|---:|---|
| Matches at confidence ≥0.25, IoU ≥0.5 | 14 | Primary true positives. |
| IoU ≥0.5 but confidence below 0.25 | 3 | Correct overlap exists in saved output, below the operating threshold. |
| Best saved IoU ≥0.1 but below 0.5 | 6 | Localization/box-definition disagreement; includes saved predictions below 0.25. |
| No saved ball box with IoU ≥0.1 | 9 | No overlapping response at the saved floor 0.05; weaker raw responses were not retained. |

The corresponding counts for large/1920 are 13/3/8/8, and for large/2560 are 11/2/8/11. This is not solely a confidence-threshold problem. Predeclared confidence diagnostics at fixed IoU 0.5 give:

| Input | Confidence 0.10: TP / FP / FN | Confidence 0.50: TP / FP / FN |
|---:|---|---|
| 1280 | 16 / 39 / 16 | 12 / 9 / 20 |
| 1920 | 15 / 47 / 17 | 10 / 10 / 22 |
| 2560 | 11 / 18 / 21 | 9 / 1 / 23 |

These diagnostics do not replace the primary score. Across all nine tested YOLO settings, only 16 distinct labelled balls match at the primary threshold. Even choosing a different setting for every image with hindsight gives correct saved overlap for only 23/32 at any saved confidence. That union is a diagnostic, not an evaluated ensemble or attainable production score.

Inspection of all 32 original-resolution ball crops shows source widths from **15 to 64 pixels (median 30)**, with blur and partial occlusion in several examples. At 1280, the smallest source ball is only about 7.5 pixels wide. Full source resolution preserves existing information; it cannot recover detail lost to blur, compression or obstruction. General COCO training and changed object scale may also contribute, but these runs do not isolate those causes or establish that another architecture would fail.

### Annotation findings that affect interpretation

Some apparent misses are clearly located balls with a box-size disagreement. For large/1280, CVAT 7, 11, 22 and 27 have confidence above 0.25 but IoUs of approximately 0.475, 0.363, 0.402 and 0.387. In the retained overlays, several reviewed yellow boxes include visibly more background/shadow than the predicted cyan boxes. Recheck both against the documented tight visible-extent convention. Do not assume every disagreement is model failure, and do not copy a candidate's boxes as the new answer key. A new review should use original pixels/context and preferably a second annotator.

The recurring near-goal round item accounts for **31/34** medium/1280 unmatched ball boxes, **21/27** large/1280, **25/30** large/1920 and **2/6** large/2560. These are diagnostic location counts in the observed item's small region, not new scoring exclusions. Therefore the larger-model FP counts are dominated by a repeated object ambiguity, not dozens of unrelated hallucinations. Audit whether the item is a sports ball; the current generic class includes in-scope spare balls. Distinguishing the active playing ball is a separate identity/tracking task. The ten zero-ball-label images also retain the visibility limitations above.

Keep the frozen revision's results for reproducibility, but **do not use its current uncertainty to declare a production winner or specify a model guaranteed to reach 32/32**. Next order:

1. Adjudicate tight ball boxes, the near-goal item and nine unresolved visibility cases; retain original notes and issue history. Create a new reviewed label revision, then re-evaluate every saved candidate against it equally.
2. Gather dense, reviewed ball/event windows and independent match recordings. Keep the current whole clip in development; choose held-out matches before further tuning.
3. Run a separately specified ball-focused crop/tiling experiment, preserving coordinate mapping and counting duplicate/false detections; then test football-specific fine-tuning if misses remain. These workflows are not implemented by this change.
4. Add temporal tracking and confidence-aware review for continuous footage. Tracking may bridge brief gaps but must not present an invisible/interpolated ball as a direct detection. Goal geometry/event review can proceed independently with human review.

### What re-labelling changes, and D-FINE's position

The CVAT annotations have so far been used only as evaluation answers. Neither YOLO nor D-FINE has been trained on these 42 images. Correcting annotations therefore changes the reference against which saved predictions are measured, not a checkpoint's predictions. Correct labels could raise or lower a score, depending on whether we correct loose boxes, missed visible balls or incorrectly labelled objects. Fine-tuning on a separate, sufficiently varied reviewed training set is the subsequent step that changes model weights; both [YOLO training](https://docs.ultralytics.com/modes/train/) and [D-FINE custom-data training](https://github.com/Peterande/D-FINE#quick-start) support this. Do not train on this pilot and then present its re-tested score as independent validation.

Re-review all 42 images for balls, including images with no existing ball box, while preserving approved person work. Use tight visible-extent boxes, original pixels and neighboring video frames; distinguish fully hidden/off-screen balls from unresolved visibility. Keep the generic sports-ball class consistent, including any verified in-scope spare balls, and treat active-ball identity separately. The user should be able to inspect the changed/uncertain annotations before a new revision is marked reviewed. The [subsequent draft](#ball-re-review-draft-awaiting-human-adjudication) now implements this review step; it is not approved ground truth.

D-FINE-N remains a comparison baseline: at 640 it matched 8/32 balls with 13 unmatched boxes, outperforming YOLO26n/640's 2/32 on recall; at 1280 it matched 9/32 with 77 unmatched boxes. All primary D-FINE-N matches at both sizes are already among YOLO26l/1280's 14 matches on this revision, so the saved outputs offer no additional correctly matched ball instances at that operating point. That overlap alone does not evaluate an ensemble or settle the model-family comparison. The nano D-FINE checkpoint is not equivalent in capacity to large YOLO, and [larger D-FINE checkpoints exist](https://github.com/Peterande/D-FINE#model-zoo), but have not been tested here.

Re-score D-FINE-N on corrected labels alongside every YOLO setting; retain its original results. Then use the adjudicated failure types to choose a bounded ball-crop or fine-tuning comparison. Current results do not justify choosing D-FINE-N as the solution, discarding the whole D-FINE family, or promising that another model/input size will reach perfect recall.

### Large-model verification and retained evidence

156 offline tests passed, with 98% rounded overall coverage and 100% adapters. New behavior covers large-scale architecture validation and mismatches, 2560 routing/metadata/original-coordinate results, CLI/default weights, invalid sizes and D-FINE rejection before loading. Native smoke checks confirmed `[1,3,1280,1280]`, `[1,3,1920,1920]` and `[1,3,2560,2560]` forward tensors for the actual large checkpoint; no runtime dependency changed.

All eleven cells were checked for identical 42 source indices/timestamps/dimensions, source/label/scope hashes, sampling, environment, precision and thresholds except the intended model/input changes. Re-evaluation reproduces saved reports, and the separate per-frame diagnostic reproduces the ball TP/FP/FN counts. Native large checkpoint SHA-256: `9fe3c544f2b19bebad7ea41e76d7ad3d88b7c2f10d11d24430c5311f6b32db26` (53,211,173 bytes), from the official release above.

Private `ball-large-v3-20261030/` retains the pre-inference plan/source snapshots, commands/download provenance, smoke/test/run logs, comparison/diagnostic JSON, all 32 source-ball crops, localization overlays and integrity hashes. The two ball contact sheets, localization contact sheet and frame-7 overview were visually inspected. Frozen labels, prior run outputs and original protocol snapshots were not rewritten. Latest executable/test sources match the new snapshot; docs were subsequently completed with measured results. These local CPU checks do not establish independent accuracy, mobile/CUDA behavior or reliable automatic goals.

## Ball re-review draft awaiting human adjudication

**Later on 30 October 2026**, the user confirmed: “It’s a spare football.” This resolves the recurring near-goal object's identity. Earlier uncertainty and all measured tables above remain a record of revision 1, not the current interpretation of that object. The fixed scope already includes its location, and the documented generic sports-ball class includes spare balls.

The assistant created [CVAT task 3/job 3](http://localhost:8080/tasks/3/jobs/3) from the same 42 PNGs and preserved all 493 approved player rectangles exactly apart from server-assigned IDs. All whole-image previews, 32 original labelled-ball crops and 42 spare-ball crops were inspected, together with nearby source frames for the ten previously unlabelled playing-ball samples and difficult overlaps. New coordinates were drawn from clean original pixels; candidate detector boxes were not used as proposals. Original/proposed overlays were then checked.

The resulting **AI draft has 75 ball rectangles: 33 playing-ball candidates and 42 spare-ball instances**. Frame 16 has a new partly occluded playing-ball proposal. Frame 18 remains a ball-versus-boot question. Eight samples retain unresolved playing-ball visibility (8, 10, 12, 24, 32, 35, 37, 38); frame 19's context supports an off-screen playing ball. Thirteen CVAT issues flag these questions and difficult boundaries. The spare shifts after frame 35; later rectangles reflect the new visible position. All 75 coordinates still require human review, including those whose object identity is confirmed.

Task 3 remains validation/new. Task 2, its annotations, frozen labels and historical outputs are unchanged. Private `ball-relabel-draft-v2-20261030/` retains snapshots, the role/coordinate ledger, context provenance, review issues and `REVIEW_HANDOVER.md`. Follow [the review workflow](labelling.md#ball-only-re-review-draft) before exporting a new approved revision. No new scores have been produced. A corrected generic score may improve or worsen; it must not be compared to 14/32 as though the answer key and denominator stayed fixed. Re-score all saved candidates equally and separately explain detection of the playing ball and the static spare.

## Preprocessing idea not yet tested

The user proposed inversion, recolouring, colour filtering and highlighting before detection. These are hypotheses, not measured improvements. Inversion changes brightness and colour relationships without increasing the ball's pixel size or recovering hidden detail. Our expectation is that this large appearance change could hurt an unadapted COCO checkpoint; that is an inference, not a result from this footage. Selecting or outlining only the ball already requires a reliable way to locate it. Colour selection also needs to distinguish pale balls from lines, shoes and goal equipment.

Mild contrast normalization is a more conservative candidate. OpenCV documents both local contrast enhancement (CLAHE) and the risk that equalization amplifies noise or washes out useful detail. Use luminance-only processing if testing it while retaining RGB model input. [OpenCV histogram equalization guidance](https://docs.opencv.org/4.13.0/d5/daf/tutorial_py_histogram_equalization.html). Training augmentation is a different intervention: YOLO supports brightness, saturation, hue and optional CLAHE variations to improve robustness. Its documentation does not establish that an inference-only transformation will help these checkpoints. [Ultralytics augmentation guide](https://docs.ultralytics.com/guides/yolo-data-augmentation/).

After adjudication and equal re-scoring, a proposed bounded first test is **YOLO26l/1280** with three input variants: original RGB, luminance-only CLAHE (clip limit 2.0, 8×8 tiles), and full RGB inversion as a diagnostic control. Fix these settings before inference; retain all outcomes without a parameter sweep. Keep source frames, labels, checkpoint, letterboxing, device and confidence/IoU identical. Apply transformations in memory to copies; retain original footage and coordinate geometry, record exact transformation/version metadata, and include preprocessing latency. The runner does not yet implement these variants; implementation would need contract/geometry tests and a new experiment directory.

Report playing-ball gains/losses, spare-ball matches, total false alarms, person regressions and latency. A visually clearer image is not sufficient evidence. Any promising variant needs confirmation on independent recordings; these 42 frames remain development data. Ball-focused crops, varied football training data and temporal tracking remain separate candidates for detail, domain and continuity failures. No colour effect can make a fully hidden ball directly visible.

### Applying the additional training advice to this project

The user supplied another AI's suggestions for resolution, venue fine-tuning, blur/scale augmentation, tracking and inversion. The direction is plausible, but the proposed training snippet is not a validated recipe for our footage. We already tested large YOLO through full source detail; repeating “increase resolution” is not the next evidence gap. Our labels have only scored generic pretrained models: no venue-specific training has taken place.

Ultralytics recommends a default fine-tuning baseline and deliberate changes, with reduced augmentation for small datasets. Start there rather than adopt all suggested HSV/scale settings together. [Official fine-tuning guidance](https://docs.ultralytics.com/guides/yolo26-training-recipe/#fine-tuning-yolo26-on-your-own-dataset). For example, `scale=0.7` permits 0.3×–1.7× resizing; shrinking an already tiny ball may remove useful pixels. Inspect augmented examples and validate realistic blur/lighting changes separately. [Scale semantics](https://docs.ultralytics.com/guides/yolo-data-augmentation/#scale-scale). The cited [soccer support discussion](https://github.com/ultralytics/hub/issues/1116) proposes motion-blur augmentation, but does not validate it for this clip.

Gather varied labelled ball examples and confusing non-balls such as boots, lines and equipment. The verified spare remains a positive sports-ball example under the current contract. Hundreds of adjacent frames are not hundreds of independent situations: split training, validation and final testing by recording/match, keeping near-duplicates together. The repeatedly inspected current clip stays development material; a new untouched recording is needed for independent assessment. The quoted frame-count range is a planning estimate, not an established sufficiency threshold.

Tracking needs dense chronological windows, not our 12-second sampling. ByteTrack associates low-confidence detections with existing trajectories, which can reduce fragmented tracks. This does not guarantee a measured position when the detector has no usable response; predicted/interpolated positions must remain distinguishable from observations, especially near a goal line. [ByteTrack paper](https://arxiv.org/abs/2110.06864). Tracking quality and goal-event correctness need separate evaluation. Our current evaluator reports fixed-threshold precision/recall, not mAP50–95.

Recommended order remains: adjudicate the draft and re-score all saved outputs; run a bounded overlapping-crop experiment while collecting varied training/held-out footage; establish fine-tuning with conservative augmentation; evaluate temporal continuity on dense event windows. The contrast/inversion comparison above is an optional small diagnostic, not a replacement for this data work or another open-ended sweep. Inversion swaps intensity polarity and preserves absolute per-channel differences; it does not inherently add contrast information or ball detail.
