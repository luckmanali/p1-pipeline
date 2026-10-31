# First reviewed football pilot — 30 October 2026

Both detectors completed the same 42-frame, main-game-scoped development comparison. **YOLO26n produced fewer false positives and lower local prediction latency; D-FINE-N matched more labelled players and balls. Neither baseline detected enough balls to support reliable automatic goal/event work on this clip.** This is an initial pilot result, not a held-out model-selection decision.

## Dataset and approval

The user reviewed the CVAT pilot and instructed: “the labels look fine, resolve them all then continue”. The remaining 12 issues were resolved with that approval recorded; all 64 issues in the approval snapshot were resolved. The final live check retained 63 issues, all resolved; previously resolved issue 2 was no longer present. Task 2/job 2 is acceptance/completed. No annotation coordinates were changed during approval/export.

Revision 1 contains **42 frames, 493 person boxes and 32 football boxes**, sampled at decoded indices 0, 300, …, 12,300 across the supplied 494-second recording. All frames are included; ten have no labelled in-scope football. Earlier other-pitch labels and 42 false person boxes on equipment were removed during review. The approved match-area polygon is frozen with the labels. This selects an image region, not roster identities.

The answer key was AI-drafted and user-approved before either candidate ran. This records the user's approval, not an independent second-annotator audit. The whole recording belongs to development; adjacent frames or future tuning on this clip must not be described as held-out evidence. Source, label and scope hashes:

```text
video:  eac1a39d83c727f142d33e6a8ede112224ab14d925680a3584254a83fa397984
labels: 02e38f01f36c88d060fe3320dfb737534333c395ecbd34f565912ce1f51fff0b
scope:  972cab8d464a11b090edb0fab7f92509be9ad994d192e90cb2f3581f5faafee7
```

## Fixed comparison settings

Both native checkpoints ran sequentially on this **Apple M5 Pro, 48 GiB RAM**, with CPU inference, four Torch threads, FP32, batch 1, 640×640 input and three excluded warmup predictions. Both used stride 300 without a frame cap. Saved confidence floor: **0.05**; scoring confidence: **0.25**; match IoU: **0.50**. One run per model was measured; settings were saved before inference.

Native preprocessing remains different: YOLO square-letterboxes the image; D-FINE stretches it. Original images and boxes were not cropped to the scope. Predictions outside the frozen polygon are excluded by the [documented anchor rule](benchmarking.md#main-game-scope). All saved detections still undergo schema validation. Precision is TP/(TP+FP); recall is TP/(TP+FN). Matching is confidence-ordered, one-to-one and same-class, not COCO mAP.

## Accuracy

| Class | Model | Matched labels (TP) | Unmatched predictions (FP) | Unmatched labels (FN) | Precision | Recall |
|---|---|---:|---:|---:|---:|---:|
| Person | YOLO26n | 385 | 38 | 108 | 91.0% | 78.1% |
| Person | D-FINE-N | 449 | 250 | 44 | 64.2% | 91.1% |
| Football | YOLO26n | 2 | 0 | 30 | 100.0% | 6.3% |
| Football | D-FINE-N | 8 | 13 | 24 | 38.1% | 25.0% |

YOLO's ball precision is based on just **two predictions**; it is not evidence of dependable ball detection. A false negative can be a missing prediction, insufficient confidence or inadequate box overlap. These counts measure the agreed visible-extent box convention, not just whether a model noticed an object.

At the scoring threshold, the scope excluded 16 YOLO and 392 D-FINE person predictions; neither had an excluded ball prediction. Those background predictions do not count as false positives in the table.

## Local timing

| Measurement | YOLO26n | D-FINE-N |
|---|---:|---:|
| Mean prediction latency | 32.1 ms | 69.5 ms |
| Median prediction latency | 29.3 ms | 67.0 ms |
| p95 prediction latency | 44.9 ms | 86.0 ms |
| Prediction-only throughput | 31.1 frames/s | 14.4 frames/s |
| Decode, warmup, sampled prediction and write | 54.7 s | 57.6 s |

Prediction latency includes native preprocessing, inference, postprocessing and result transfer. It excludes decoding and warmup. The last row decodes the source but **infers only 42 sampled frames**; it is not full-frame football-analysis throughput. This is one short pass while desktop services remained running, not a repeated, isolated performance study. GPU/mobile performance, peak CPU memory and cloud cost were not measured. Existing macOS OpenCV/PyAV duplicate-AVFoundation warnings appeared; both runs nevertheless completed.

## Inspected errors and implications

- D-FINE repeatedly predicts people on the near-goal equipment. Across the run, 86 unmatched person predictions overlap the equipment region at IoU ≥0.1, spanning 38 frames. YOLO has one such unmatched prediction. This is a diagnostic region count, not an extra scoring exclusion. The equipment remains a negative for the person class.
- Unmatched person predictions also overlap already-assigned labels: 32 for YOLO and 56 for D-FINE have IoU ≥0.5 with a label already used by the matcher. Visual examples show overlapping extra boxes. This group alone does not prove every error is a duplicate; nearby/occluded people and the greedy matching convention can interact.
- The inspected frame-40 overlays show missed ball evidence and difficult overlapping people; D-FINE also has extra boxes around the far players. Frame 2 shows D-FINE matching the ball held by the near goalkeeper while producing extra ball predictions elsewhere.
- The median labelled ball box is 30×27 original pixels. Under native preprocessing it becomes approximately 7.5×6.75 pixels for YOLO and 7.5×12 for D-FINE. This supports investigating image detail, but does not prove resolution alone caused the misses or explain the ranking.

Keep these baselines and the frozen answer key. Next, define a separate development experiment for higher input detail and a stronger detector baseline, focusing on ball recall and false alarms. Any adapter/input-size changes need tests, recorded preprocessing and a new run protocol. Add dense event windows for tracking/goal work; the 12-second sample interval cannot establish trajectories or goal events. Expand to independent matches before selecting a production model. Reviewed goals/geometry and the app demo can proceed without claiming automatic goal detection works.

## Evidence and reproduction

Private evidence is under `data/football-clip-iqLnW_238X8-20261030/reviewed-v1-20261030/`: approval record, resolved issue IDs, frozen annotation snapshot, COCO export, approved backup, original frame manifest, scope, converted v2 labels, source snapshot/hashes, comparison plan, logs, `comparison.json`, `error-inspection.json`, ball-size diagnostic and eight error overlays. No media/credentials are committed. CVAT names its COCO file `instances_development.json` because this task uses the development subset.

Runs are retained at:

```text
runs/football-pilot-reviewed-v1-20261030-yolo26n-cpu/
runs/football-pilot-reviewed-v1-20261030-dfine-n-cpu/
```

Each contains the completed manifest, sampled detections and `evaluation.json`. The plan records the exact shared environment and settings. To reproduce, use the [runner/evaluator commands](../README.md#compare-detectors), the preserved original video, stride 300, CPU, confidence floor 0.05, warmup 3 and a **new** run directory. Set `OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `VECLIB_MAXIMUM_THREADS` and `NUMEXPR_NUM_THREADS` to 4 for both processes. Evaluate against the frozen `benchmark-labels-v2.json` at confidence 0.25 and IoU 0.5.

Checkpoint SHA-256 values:

```text
YOLO26n:  9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef
D-FINE-N: 41973938d2784d38a9836990d805b8392855ebf611aba55f0f7add90e110744c
```

D-FINE's vendor checkout was clean at `956d1709314c2c6a4df6f34de232054578a7449f`. Pipeline source was uncommitted, so the executed source files, hashes and tracked diff were retained. Both run environments, original frame indices/timestamps/dimensions, label/scope hashes and scoring settings were checked for equality. All 525 converted annotations exactly matched the frozen CVAT snapshot, and all 42 backup PNG hashes matched the export manifest. No frozen labels were changed after inspecting predictions.
