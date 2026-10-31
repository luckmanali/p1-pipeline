# Benchmark protocol

Goal mouths, goal lines and event tags belong to the separate [continuous-video review workflow](goal-review.md), currently CVAT task 4. They do not add detector classes or change frozen labels. The eight replay windows are a development shortlist, not an independently sampled goal-accuracy test set.


Use [README commands](../README.md). This protocol defines a comparison and the evidence still required.

## Evaluation material

Use consented fixed-camera small-sided football footage representative of the recording setup. Record match ID, camera/venue, resolution, lighting and normalization steps beside the dataset. Keep identifiable recordings/labels outside Git in ignored `data/` or approved private storage.

Split by whole matches, with venue/camera separation where appropriate; never place adjacent frames from a match across training and evaluation. Reserve test matches before tuning. Select labelled frames before inspecting predictions, including distant/occluded balls, crowds, poor lighting and negatives. Document exclusions.

For this COCO baseline, annotate every visible person and sports ball **within the agreed evaluation scope**. The current user-selected scope is the main game, excluding the adjacent pitch at the top. The region filters space, not identity: a spectator/referee inside it remains a person. Legacy full-frame v1 datasets still require all visible people/balls across the image. Do not describe either result as participant identification accuracy.

## Recommended pilot and expansion

The [Frame 2 team plan](frame-two-labelling-plan.md) proposes a separate first fine-tuning dataset: six training, two validation and two test matches, totalling about 2,800–3,400 reviewed images. Its smaller within-venue evaluation is a starting experiment; the broader six-evaluation-match benchmark below remains a later coverage target. All parts of one physical match must share a split, and the existing development clip cannot enter a new untouched test set.

These are practical starting annotation budgets, not statistically validated sample-size guarantees. Select samples before inspecting either model's outputs.

1. **Pilot:** start with about 200–300 systematically spaced frames from one recording. For an 11½-minute recording, a frame at or just after every three-second target produces roughly 230 samples. Use `export_frames.py --every-seconds 3` to preserve original decoded frame indices and PTS in a manifest; do not create a lower-FPS video and renumber it. Run both models at stride 1 without a frame cap to include all time-selected indices, or export and infer with the same integer stride.
2. **Challenge examples:** separately select about 30–50 frames showing distant/partially occluded balls, motion blur, crowded players, edge truncation and ball-absent scenes. Keep their metrics separate from systematic samples so deliberate difficulty selection does not distort headline results.
3. **Model-selection benchmark:** expand to roughly 600–1,000 labelled frames across at least six independent matches covering intended venues/cameras/lighting. For example, use two matches for validation/threshold selection and four untouched matches for testing. Treat these as starting budgets; add matches if rankings vary. Different parts of one match stay in the same split. Do not tune on pilot material and later describe it as unseen test data.

Prefer original, continuous, upright recordings at 1080p or above when available, with a stable wide view representative of the intended app capture setup. Include near/far play, both goal areas, overlapping players, routine inactive periods and difficult lighting. Preserve source frame rate; verify actual dimensions/timestamps from the file. Additional frames from one camera cannot establish performance across other cameras or venues.

## Annotation procedure

- Annotate original-resolution decoded frames, using tight axis-aligned boxes around visible object extent. Clip partial objects at image boundaries. Apply this visible-extent convention consistently; do not invent a fully hidden person's body or an invisible ball. For blur, include the discernible object extent without treating an indistinguishable patch as a certain ball.
- Label every visible person and sports ball within the agreed region, including substitutes/referees/spectators or spare balls inside it. Exclude objects on other pitches outside the region. Individual player IDs, teams, poses, passes and goals are outside this detector benchmark.
- A frame with no visible ball still needs its person boxes. `annotations: []` means neither class has visible objects, not merely that the ball is absent. Entirely hidden or off-screen objects receive no box.
- Review all ball boxes with another annotator where possible, plus a sample of person boxes. Zoom in and use adjacent frames for context, without guessing invisible coordinates. Resolve disagreements before scoring. Avoid presenting one candidate model's predictions as ground truth; annotate without predictions for the pilot.
- If an object cannot be labelled reliably after review, log the uncertainty. This evaluator cannot ignore one region/object: exclude the whole unresolved frame from scored labels and retain it for unscored failure inspection. Report exclusion counts/reasons; do not silently remove difficult but labelable cases. The challenge set above contains adjudicated, scoreable frames.
- Preserve exact image-to-video mapping and explicit empty frames when exporting. Normalization to the evaluator's xyxy format happens after annotation, using each original image's dimensions.

### Frame export and CVAT import

Prepare an upright, square-pixel local recording before starting. Export the frames without changing the source video:

```sh
uv run --locked python export_frames.py data/match.mp4 --output data/match-frames --every-seconds 3
```

`--every-seconds 3` is the default. Time sampling starts at the first decoded frame and selects the first frame at or after each interval target relative to that frame's PTS. It does not select the nearest frame. If a timestamp gap crosses several targets, the next frame is exported once and targets already passed are skipped. Alternatively, `--stride N` selects decoded indices 0, N, 2N, …; the two sampling options are mutually exclusive. `--max-frames N` caps the exported count.

Each new output directory contains lossless native-resolution RGB PNGs under `images/` and `manifest.json`. The version-1 manifest has kind `frame_export`, a lifecycle status, source video SHA-256, sampling settings and each exported frame's filename, decoded index, timestamps, dimensions and PNG SHA-256. Only a completed export can be imported. No cropping, rescaling or video re-encoding occurs. If geometry normalization is needed, follow the [README](../README.md#geometry-and-platform-limits) first and treat that normalized file as the source throughout.

Use the [CVAT COCO workflow](https://docs.cvat.ai/docs/dataset_management/formats/format-coco/):

1. Create a task in your chosen CVAT environment with two rectangle labels, exactly `player` and `football`. Upload only the exported files inside `images/`; preserve their filenames. The local tools do not create an account/task or upload files.
2. Use the [agent-assisted workflow](labelling.md) to draft boxes and flag questions, or label manually. A person reviews every image intended for scoring, including images without objects. The exporter/converter do not generate predictions; unreviewed assistant/model proposals are not benchmark ground truth.
3. Export **COCO 1.0** and extract the archive locally. Pass its `annotations/instances_default.json` to the converter; the converter does not read ZIP archives.
4. Confirm the COCO `images` array contains only reviewed frames. A reviewed subset is allowed. To exclude an unresolved frame, remove its image entry and all annotations referencing its image ID, or prepare a task/export containing only that reviewed subset. Deleting its boxes while retaining the image would falsely mark it as a negative.
5. Convert to the evaluator contract using a new output path:

   ```sh
   uv run --locked python convert_cvat.py data/cvat-export/annotations/instances_default.json --manifest data/match-frames/manifest.json --output data/match-labels.json --reviewed
   ```

`--reviewed` is your assertion that **every included image** was reviewed. COCO has no reliable distinction between an unfinished empty image and a confirmed negative. The converter preserves included empty images and records excluded manifest frame indices in its provenance/summary so omissions remain visible.

Conversion associates images by their known unique filename basenames and matching dimensions, then follows COCO image/category IDs and annotation references rather than array order. Accepted class names are `player`/`football` or their COCO aliases `person`/`sports ball`. COCO pixel `xywh` boxes become normalized `xyxy`; unknown images/classes, invalid references/boxes and unsupported crowd, ignore or segmentation annotations fail instead of being silently dropped. Keep the source export and manifest with the converted labels for review.

Run both detectors on the **same original video**, not the PNGs or a reconstructed video. For the time-sampling example, use `--stride 1` and no `--max-frames` so all labelled indices exist. When exporting by integer stride, the detector runs can use that same stride. Evaluate both runs with the same converted label file, including its scope when present. Unlabelled frames remain excluded.

### Main-game scope

For a fixed camera showing multiple pitches, define a convex polygon around the selected match area before scoring. Store it separately from CVAT's object rectangles in normalized original-image coordinates, with vertices in boundary order and no repeated closing point. An illustrative lower-image region is:

```json
{"type":"main_pitch","polygon":[[0,0.2],[1,0.2],[1,1],[0,1]]}
```

Use the recording's reviewed region, not these example coordinates. Both `convert_cvat.py --scope path/to/scope.json --reviewed ...` and `evaluate.py` use **bottom-centre of the visible person box** and **centre of the ball box** to determine membership. Boundary points are included; boxes keep their full original coordinates and are never clipped to the polygon. A person's head crossing the boundary does not remove them when their bottom-centre remains inside. The same rule applies to labels and both models.

Conversion with `--scope` writes **label schema v2**, embeds `evaluation_scope`, and hashes the exact scope-file bytes in provenance. V2 requires a valid region; v1 must not carry one. This makes old evaluators reject scoped labels instead of silently counting other-pitch detections as false positives. Conversion and evaluation reject out-of-scope ground truth rather than silently dropping annotations. Review and fix misplaced boxes or the region before exporting.

Evaluation validates every saved detection, then excludes out-of-scope predictions on labelled frames at or above the evaluation confidence threshold. Reports include the region and per-class `excluded_detections`; excluded predictions are neither true nor false positives. In-region misses and false positives still count normally. Freeze the region with the reviewed labels and use the identical label file for both models.

This is a spatial selection rule, not automatic participant identification, tracking or camera calibration. Review ambiguous boundary cases and the entire selected region, including areas without draft boxes. A fixed polygon is unsuitable for camera moves/cuts or visually inseparable overlapping matches; per-frame regions are not implemented. Perspective, partially hidden bodies and airborne balls can make the anchor rule ambiguous. Document/exclude unresolved frames rather than tune the boundary after seeing detector results. Inference still runs on the unchanged full image, so this does not claim a speed improvement.

### Current development recording — supplied 30 October 2026

The user supplied `FOOTBALL_CLIP_1440p.mp4` and [this YouTube reference](https://www.youtube.com/watch?v=iqLnW_238X8), describing a six-a-side match and providing a numbered red/blue team screenshot. The local file is the source of truth; the YouTube page could not be independently fetched during intake. Its video stream is **2560×1440, 25 fps, 12,350 frames, 494 seconds**, H.264 with square pixels and no reported display transform. The container duration is 494.050975 seconds; use video timestamps, not the slightly longer container/audio duration. The preserved source hash is `eac1a39d83c727f142d33e6a8ede112224ab14d925680a3584254a83fa397984`.

The clip is assigned to **development**, not a held-out test split. Sampled views show an elevated corner camera, wide-angle distortion, netting, overlapping people and another pitch in view. These make useful initial cases but cannot establish generalization across venues. Full-match completeness, goals and identities throughout the recording have not been reviewed. The user supplied it for local development; training/redistribution permission is not recorded.

An unchanged local copy, numbered screenshot, metadata, review progress and exact image mapping are retained under ignored `data/football-clip-iqLnW_238X8-20261030/`. Original media is not committed. Before inspecting either candidate detector, the existing exporter produced **42 native-resolution PNGs at stride 300**: decoded indices 0, 300, …, 12,300, with relative times 0, 12, …, 492 seconds. This modest first batch spans the clip and allows both models to use the same integer stride; it does not replace the larger multi-match benchmark above.

```sh
# Intake command already completed; use a new directory for any later export.
.venv-ci/bin/python export_frames.py data/football-clip-iqLnW_238X8-20261030/source/FOOTBALL_CLIP_1440p.mp4 --output data/football-clip-iqLnW_238X8-20261030/pilot-frames --stride 300
```

[CVAT task 2 / job 2](http://localhost:8080/tasks/2/jobs/2) contains all 42 images. The first full draft had 864 person and 34 football boxes. At the user's request, **329 background-person boxes and two other-pitch balls were removed**, followed by **42 false person boxes on goal-net equipment**. The final set has **493 person boxes and 32 football boxes**. The user subsequently approved the labels and instructed all issues be resolved. Twelve remained unresolved at that point; these were closed with the approval recorded. All issues are resolved and the job is **acceptance/completed**. The approval snapshot retained 64 issues; the final check retained 63 after already-resolved issue 2 disappeared. Image mapping, source pixels and annotation coordinates were unchanged by approval/export.

The private `REVIEW_HANDOVER.md` and `review-progress.json` record the user's approval for all 42 frames and the retained main-game scope. CVAT frames **8, 10, 12, 16, 19, 24, 32, 35, 37 and 38** have no in-scope football in the approved export; their person labels remain included. Goal-net equipment remains in scope as a person-negative example, not an ignore zone. The user also confirmed the existing far-right red-player box on frame 40. Initial drafts and correction snapshots remain as history; the immutable approved source, scope, annotation export, backup and v2 labels are in `reviewed-v1-20261030/`. The COCO export is named `instances_development.json` because CVAT uses the task's subset name. No candidate predictions were used to create the answer key.

Both models have now completed the [initial reviewed comparison](benchmark-results-2026-10-30.md), using CPU, four Torch threads, FP32, batch 1, 640 input, stride 300, floor 0.05 and evaluation confidence/IoU 0.25/0.50. The frozen label SHA-256 is `02e38f01f36c88d060fe3320dfb737534333c395ecbd34f565912ce1f51fff0b`. All 42 frames were scored, with no exclusions. YOLO person precision/recall was 91.0%/78.1%; D-FINE was 64.2%/91.1%. Ball matches were 2/32 and 8/32 respectively. These development results identify the need for better ball evidence and further evaluation; they do not select a production model or establish GPU/full-match performance. Keep future label corrections or tuning in a new revision/run protocol.

The user markers define provisional roster references **R1–R6 / B1–B6**, independent of shirt colour. The screenshot has been matched to source frame **6,944 at 277,760 ms (4:37.760)** by pixel comparison and visual inspection. The clean original frame and 12 provisional interior reference points are saved separately; marker transcription and identity continuity remain separate review work. This is a single-frame identity reference, not a replacement for person/ball boxes. The frame is not part of the systematic 42-frame benchmark sample. Approval of the detector labels does not establish player identities, goals, goal-line geometry or full-match results.

### Historical candidate — withdrawn on 25 October 2026

The user proposed [frame 2 bradford v oldham 31 03 19 part 5](https://www.youtube.com/watch?v=D57mvWw9l_M), published by Frame Two. The browser player displayed 11:32 duration and quality options up to 1440p. Samples near the opening, 3:24 and 8:10 showed an elevated, apparently fixed corner view of indoor small-sided football, netting near the camera, near/far scale variation and people beyond the pitch boundary. These are useful pilot conditions; a full recording review, actual file metadata and annotation-quality inspection have not been performed.

The user subsequently chose to supply different footage, so this recording is withdrawn from the proposed benchmark. It remains here only as inspection history; the current development recording is documented above. One indoor camera/venue and YouTube compression would limit generalization, and other parts of the same match would not count as independent matches. No reuse permission was established by the inspection; see [YouTube's licence/permission guidance](https://support.google.com/youtube/answer/2797468?hl=en-GB). No footage was downloaded or benchmarked during this review.

## Comparable runs and timing

Run models separately with identical video hash, stride, frame limit, device, FP32, batch 1, 640 size, saved confidence floor and warmup count. Keep the machine idle and CPU thread environment consistent. Native preprocessing differs and is recorded. Use new directories for repetitions.

Check both manifests are completed, hashes/settings match, architecture/checkpoint metadata are expected, and sampled indices/timestamps agree. Evaluation accepts one run at a time; it does not certify two runs are comparable.

`prediction` includes preprocessing, inference, postprocessing and CPU result transfer. It excludes decoding/JSON writing and warmup. CUDA is synchronized around measured predictions. `decode_predict_write_seconds` includes decoding, warmup, predictions and writing, excluding loading/hashing (reported separately). Prediction FPS is not end-to-end throughput. Stride skips inference, not decoding.

Repeat sufficiently long runs on target hardware and report variation. Three synthetic frames establish no speed ranking. CUDA peak allocated bytes cover PyTorch's allocator, not total device memory or CPU RSS. Measure cloud costs separately; this tool makes no cost estimates.

## Label file

Copy `video.sha256` from the manifest. Frame indices identify the exact decoded video before stride filtering. Draw boxes in upright original decoded dimensions; divide x by width and y by height. Replace the illustrative hash/coordinates below with actual annotations:

```json
{
  "schema_version": 1,
  "video_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "frames": [
    {
      "frame_index": 0,
      "annotations": [
        {"class": "player", "bbox": [0.10, 0.15, 0.22, 0.85]},
        {"class": "football", "bbox": [0.45, 0.70, 0.48, 0.74]}
      ]
    },
    {"frame_index": 5, "annotations": []}
  ]
}
```

Only `player`/`football` are accepted. Boxes must have finite normalized xyxy coordinates and positive area. Include at least one labelled frame; every labelled index must be present in both runs. `annotations: []` explicitly marks a negative. Omitted frames are unlabelled and excluded.

The [frame export and CVAT converter](#frame-export-and-cvat-import) produce this contract from reviewed images. Directly authored labels must obey the same mapping and validation rules. There is no bundled labelling UI. Renaming a video preserves its hash; transcoding does not.

## Scoring

The historical tables below refer to **frozen revision 1**. The user has now approved [revision 2](benchmark-revision-2-2026-10-30.md), with 33 playing-ball and 42 spare-ball labels, and every saved run has been re-scored equally. Generic ball recall uses 75; playing-ball recall uses 33. A private role diagnostic partitions matched reference labels and reconciles to the official generic TP/FN totals; unmatched predictions remain shared generic false positives. The public evaluator has no role-specific metric or active-ball identity prediction. Preserve the generic class/scope and report these distinctions rather than silently excluding the spare. The spare must not become the active-ball track in later product work.

For each class/frame, filter at evaluation confidence and sort predictions descending by confidence. Match each to the highest-IoU unmatched annotation if overlap meets the threshold. Matched predictions are TP, unmatched predictions FP, unmatched annotations FN. Each can be matched once.

The current pilot has 42 evaluated images but only 32 ball annotations. Ball recall therefore uses 32; all 42 images still contribute unmatched ball predictions. A zero-ball-label image is not necessarily an independently certified negative: the later [visibility and box audit](ball-detail-experiment-2026-10-30.md#why-42-images-produce-a-denominator-of-32) records uncertainty in the frozen development revision. Adjudicate original pixels/context before a stronger benchmark. A visible ball located with insufficient box overlap fails this metric even when its position is approximately right; distinguish localization, confidence and missing-response failures.

Precision = TP/(TP+FP); recall = TP/(TP+FN). Zero denominators yield `null` (undefined). Reports include class totals, labelled/unlabelled coverage, settings/model metadata and video/label hashes. Evaluation confidence must be at least the inference floor; discarded predictions cannot be reconstructed.

These are operating-point precision/recall, not AP/mAP. Always report thresholds. Tune model-specific thresholds on validation matches and freeze them before final testing. Examine ball/person metrics separately. Confidence scores are not calibrated equivalently between models.

Use an evaluation threshold **strictly above the saved inference floor** for model comparisons (the defaults are 0.25 versus 0.05). Ultralytics' native end-to-end gate uses `score > floor`, whereas D-FINE's common filtering and this evaluator use `score >= threshold`. Predictions exactly equal to the saved floor can therefore differ; evaluating above it removes that boundary discrepancy. In particular, a YOLO floor of 1 retains no predictions. Native postprocessing is deliberately preserved.

Pair quality with timing, failure cases and hardware constraints when choosing a detector. Tracking continuity, calibration, event correctness, clip usefulness and cost need separate metrics when those stages exist.

## Result record

Keep manifests, predictions, label hashes, evaluation reports, exact source state, protocol date and interpretation together in private experiment storage. Include repetition variation and exclusions. Promote anonymized aggregate findings and reasons into the decision log. [Verification](verification.md) distinguishes completed checks from missing evidence.

## Fixed 1080p crop comparison

The [overlapping-crop protocol](crop-experiment-2026-10-30.md) uses label revision 3: 34 playing-ball and 42 spare-ball instances, after the user-identified net-occluded ball at 7:00 was confirmed in neighbouring source frames. All 493 person boxes and earlier frozen revisions remain unchanged. Dataset revision 3 still uses label schema v2. The role ledger separates playing/spare reference matches; generic false positives are shared, and no active-ball precision is claimed.

Use the same `--model`, checkpoint, `--input-size`, device, original source indices, scope, floor and evaluation thresholds for both arms. Compare `--spatial-mode full-1080p` with `--spatial-mode ball-crops-1080p`. Both first resize the source to a common 1920×1080 image, and both use ball-only NMS; the crop arm additionally infers six fixed overlapping views. Retain source timestamps/dimensions and normalized source-coordinate outputs. The manifest records the analysis image and crop grid separately from tensor size. Historical `native` inference has no added merge and is a separate comparison, not a substitute for this freshly run control. Count lost matches/false alarms and total prediction cost as well as recovered balls. No test-label-guided crop selection or removal of hard frames is allowed.

## Ball detail follow-up

The [30 October six-cell protocol](ball-detail-experiment-2026-10-30.md) compares YOLO26n, D-FINE-N and the larger YOLO26s at 640 and 1280. It reuses the frozen development labels without altering scope or scoring. Each cell has a new run directory; the original pilot remains intact. Input size is an explicit runner/adapter setting, not a change to source pixels or label coordinates. Report size, preprocessing, model scale and checkpoint hash together. Higher resolution and greater model capacity are hypotheses to measure, not guarantees of better ball detection.

All six cells completed. Both YOLO 1280 runs matched the same ten balls (10/32), with five versus two unmatched ball predictions for nano/small. D-FINE 1280 matched nine and produced 77 unmatched ball predictions. These results retain the development-only limitation. Two small-model unmatched ball boxes point to an ambiguous round near-goal item; its possible spare-ball status is a separate annotation-audit question, not a reason to rewrite the frozen answer key after seeing outputs. Any correction requires a new version and equal re-evaluation of every candidate.


The requested focused tests and three large-model cells are also complete: nano/1920 11/32, medium/1280 13/32, large/1280 14/32, large/1920 13/32 and large/2560 11/32 at the same thresholds. For this 2560×1440 source, square input 1280 contains a 1280×720 picture, 1920 contains 1920×1080, and 2560 retains original detail plus padding. These settings do not imply input video height equals the CLI number.

The [complete measured report](ball-detail-experiment-2026-10-30.md#large-model-measured-results) separates low confidence, insufficient overlap and no saved overlapping response. Some reviewed boxes appear loose; repeated near-goal-item predictions dominate larger-model unmatched counts. Preserve historical scores, adjudicate all annotation uncertainties into a new reviewed revision, and evaluate every saved candidate equally. Do not lower IoU, discard hard cases or replace annotations with candidate predictions to reach 32/32. Even a perfect development result would require false-alarm and independent-match evidence.
