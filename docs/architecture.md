# Implemented architecture

Updated 30 October 2026. This is a local benchmark workspace with a shared reviewed-result boundary, not a completed football analysis service. See [decisions](decisions.md) for rationale and [benchmarking](benchmarking.md) for measurement rules.

## Execution flow

```text
local video -> export_frames.py -> native RGB PNGs + completed export manifest
  -> human annotation/review in CVAT -> extracted COCO rectangle JSON
  -> convert_cvat.py + original export manifest + reviewed match-area scope + explicit review assertion
  -> video-associated labels, including negatives and recorded omissions

video + local checkpoint + CLI settings
  -> benchmark.py: validate paths, create new run, hash inputs, load adapter
  -> PyAV: decode first video stream using presentation timestamps
  -> sample_frames: choose indices 0, stride, 2*stride, ...
  -> detector: preprocess -> native model -> postprocess -> normalized boxes
  -> detections.jsonl + completed manifest with timings/provenance

completed run + labels for the exact video
  -> evaluate.py: validate -> confidence/scope filter -> per-class matching
  -> precision/recall JSON on explicitly labelled frames
```

Each benchmark CLI process owns one model/video. Run models sequentially to avoid resource contention. There is no analysis-service queue, backend, database or Flutter transport. The optional local CVAT deployment has its own containers, database and workers for annotation storage and review; it is separate from inference.

| Module | Responsibility |
|---|---|
| `benchmark.py` | CLI, output lifecycle, hashing, decoder, sampling, warmup, synchronized timing and manifests. |
| `detectors.py` | Lazy model imports, checkpoint/config checks, native adapters and common normalization. |
| `crop_inference.py` | Optional fixed 1080p analysis resize, six overlapping ball views, source-coordinate mapping and identical ball-only merge for the experiment/control. |
| `evaluate.py` | Strict JSON/schema/scope validation, video/label association, spatial filtering, greedy matching and scoring. |
| `export_frames.py` | Shared video decoder, time/stride sampling, lossless PNG encoding, export lifecycle and frame provenance. |
| `export_review_clips.py` | Stream disjoint frame windows into silent native-size H.264 clips; verify integer CFR timestamps and retain source/output hashes and failure state. No event inference or review assertion. |
| `convert_cvat.py` | Validate reviewed COCO rectangles against an export manifest; convert to evaluator labels with source hashes and omissions. |
| `match_result.py` | Validate/serialize reviewed match-result v1 snapshots and expose a final score only for complete coverage. Uses the existing strict JSON helpers; no ML imports. |
| `contracts/match-result-v1/` | Normative wire contract, fabricated example and shared Python/Dart acceptance/rejection cases, mirrored in Flutter. |
| `cvat.compose.yml` | Override the pinned upstream CVAT deployment for loopback-only access and smaller local worker counts. |
| `tests/` | Offline behavioral tests and generated-video integration; ML libraries are faked at boundaries. |

CI's `dev` dependency group contains coverage, NumPy and PyAV, without Torch/Ultralytics. Runtime versions are in `uv.lock`; official D-FINE source is separately pinned in the README and recorded per run.

Goal/event annotation uses a separate CVAT project and full-video task. Four fixed-camera geometry tracks and event tags sit outside the detector-label and reviewed-result schemas. Geometry review is separate from event approval: all four goal tracks are user-corrected/accepted, with the near mouth bottom edge aligned to the exact user-corrected line at frame 0. The single near keyframes extend through the clip; near occlusion flags remain because review acceptance does not remove physical obstruction or establish calibrated crossings. G01/G09 are human-confirmed for Blue/B1 and G10 for Red with an unknown scorer. The other nine candidates are human-rejected; G11 includes a post hit and saved follow-up, and G12 was saved. All twelve event decisions are settled; all fourteen geometry/event issues are resolved. The subsequent AI sampled search and its proposals remain a separate frozen evidence revision from the user decisions. Search coverage is recorded independently of human adjudication; exhaustive clip coverage is not established. Human decisions can override the assistant's visual interpretation; apparent net entry does not establish that a goal counted. Targeted updates preserve manual keyframes and retain before/after evidence. The [goal-review workflow](goal-review.md) owns definitions, uncertainty, clip range semantics and human adjudication. The exporter uses the existing decoder and PyAV encoder; unsupported timing/geometry fails instead of silently normalizing evidence. Clip creation does not establish a goal or human review. A private [reviewed-result bundle](reviewed-result-handoff.md) now packages the three human-confirmed goals, twelve numbered roster aliases and three unchanged clips. Its explicit partial coverage and unavailable statistics pass both existing validators. This one-recording reviewed export is not a reusable automatic CVAT publisher; automatic conversion into published results remains unimplemented.


## Detector boundary

Adapters accept an RGB `uint8` array at original decoded dimensions. `predict(rgb)` returns a list of:

```json
{"class": "football", "confidence": 0.82, "bbox": [0.40, 0.30, 0.43, 0.34]}
```

Boxes are `[left, top, right, bottom]`, normalized by original width/height, clipped to `[0,1]`. Zero/inverted areas are discarded. Malformed/non-finite output fails. Predictions below the saved floor and unrelated classes are removed.

YOLO resolves classes by names and checks the requested YOLO26 nano/small/medium/large architecture against checkpoint metadata. It converts RGB arrays to BGR for Ultralytics, requests square input/FP32 and keeps native postprocessing. Supported YOLO sizes are 640 (default), 1280, 1920 and 2560, recorded in both inference settings and model metadata. D-FINE remains limited to its verified 640/1280 path; 1920/2560 fail before model loading. A `torch.device` object prevents Ultralytics changing CPU thread policy or remapping a CUDA index.

YOLO's native confidence gate is strict `>`; common filtering/evaluation use `>=`. Compare at an evaluation threshold strictly above the saved floor, as explained in the benchmark protocol.

D-FINE uses the official N COCO config and EMA weights when present (otherwise `model` weights), disables backbone downloading, loads state strictly with restricted deserialization and deploys model/postprocessor in FP32 eval mode. Native PIL preprocessing stretches to the selected square size. Original width/height are passed to the postprocessor. Deployed contiguous COCO IDs are person 0 and sports ball 32.

For 1280, load the checkpoint strictly at its original 640 geometry first. Then set encoder/decoder `eval_spatial_size` and regenerate only the encoder's positional embeddings and decoder's anchors/validity mask before deployment. At the pinned upstream revision, `HybridEncoder._reset_parameters()` only creates positional embeddings; it does not reinitialize learned weights. This deliberately uses that pinned internal API, so changing the vendor revision requires renewed source inspection and real-checkpoint checks. Loading incompatible learned weights still fails, and the 640 path does no geometry rebuilding. Simply resizing the input would leave incompatible cached geometry; relaxing checkpoint loading would risk hiding real weight mismatches.

Resize strategies differ intentionally. Neither adapter identifies participants, assigns identity or tracks objects between frames. `player` means COCO person, including spectators/referees; `football` means COCO sports ball.

### Optional 1080p spatial experiment

`benchmark.py --spatial-mode native` is the unchanged default. `full-1080p` and `ball-crops-1080p` wrap the same native adapter in `SpatialDetector`. Both require RGB uint8, 16:9 sources at least 1920×1080, and apply the same PyAV bilinear resize to that analysis size. Original pixels at exactly 1080p pass through unchanged. No frame is upscaled or stretched into a different aspect ratio.

The crop arm runs the full frame plus six 960×640 views at x=0/480/960 and y=0/440. Only crop football predictions are retained. Crop boxes map through their offset/extent into whole-image normalized coordinates; those coordinates also refer to the same-aspect original source. Both arms apply confidence-ordered ball NMS, suppressing overlap IoU ≥0.5 with stable input-order ties. All full-frame person boxes remain unchanged. This retains full-frame context while measuring whether larger apparent balls in crop views help; it does not select the active ball or recover hidden detail.

The model manifest's `spatial_processing` records exact resize, grid, detector-call count, merge and coordinate rules; `inference.spatial_mode` identifies the optional mode. Saved row dimensions/video hash/PTS remain original. Existing label/evaluation schema and scope rules therefore remain applicable. Resize, all views and merging are inside measured prediction time and complete-frame warmup. Exceptions propagate through the existing failed-run lifecycle; no incomplete multi-view frame is saved. Tests cover geometry, original-coordinate matching, exact merge boundaries, malformed outputs, source pixel order, duplicate handling, manifests and recovery boundaries. See the [protocol and measured results](crop-experiment-2026-10-30.md).

## Saved contracts — version 1

Detection rows contain `frame_index` (zero-based decoded index), `timestamp_ms` (relative to first decoded frame), `source_time_ms` (original PTS × time base), `width`, `height` and `detections`. Presentation timestamps preserve variable-rate timing; no timestamps are inferred from nominal FPS. Skipped inference frames are still decoded and their timestamps validated.

The manifest contains:

- `schema_version`, UTC `created_at`, `status` (`running`, `completed`, `failed`).
- `video`: path/hash; `model`: checkpoint path/hash, requested name and actual adapter/config/runtime metadata.
- `sampling`: stride/optional frame limit; `inference`: floor, input size, batch, precision, device and warmup count.
- `environment`: Python, platform/machine, package versions, Torch threads and CUDA device name when applicable.
- `pipeline`: Git revision/dirty flag. D-FINE also records its source checkout state.
- `measurements` on completion: prediction mean/median/p95/FPS, warmup time, decode/predict/write time, detection counts, timestamp range, source-time origin and CUDA peak allocated bytes where applicable. Hashing/loading durations are separate.
- `error` on failure. Partial rows remain diagnostic evidence; evaluation rejects incomplete runs.

A dirty flag does not capture source changes: preserve the diff or commit the intended version before publishing results. Provenance does not guarantee bitwise-identical inference across hardware.

Existing output directories are rejected. The manifest is replaced atomically and detections stream to disk. Exceptions/keyboard interruption mark failure; a hard process kill can leave `running`, which evaluation also rejects.

Evaluation validates completed status, video hash, schema, settings and all detection rows, including unlabelled ones. Duplicate keys/frame IDs, missing labelled frames, invalid boxes/classes and non-finite numbers fail. Matching is confidence-ordered, one-to-one, same-class and highest-IoU-first. Undefined precision/recall is JSON `null`. See [label/scoring rules](benchmarking.md).

### Scoped labels and reports — version 2

Detection rows and inference manifests remain v1. Full-frame labels/reports remain v1. Main-game labels/reports use v2, with a required `evaluation_scope` object containing exactly `type: main_pitch` and `polygon`: at least three unique normalized xy vertices in convex boundary order. Invalid, degenerate, concave and self-intersecting regions fail. A v1 label file carrying a scope also fails; older evaluators reject v2 instead of silently evaluating it as full-frame.

The shared `validate_scope`/`in_scope` helpers use person bottom-centres and ball centres, include boundary points, and retain full boxes for IoU. Conversion rejects out-of-scope ground truth. Evaluation revalidates labels and all predictions, then excludes out-of-scope predictions at or above the evaluation threshold on labelled frames. The report embeds the scope and per-class `excluded_detections`; excluded predictions do not enter TP/FP/FN. Label hashes include the region. Neither adapter nor inference timing/preprocessing changes.

This fixed-camera spatial rule selects a match area, not roster membership. A person inside that region is still COCO person even if they are a spectator. Camera moves/cuts and per-frame regions require future work. See [scope semantics and limitations](benchmarking.md#main-game-scope).

## Annotation preparation contracts — version 1

The exporter uses the same `video_frames` decoder and geometry/timestamp checks as inference. It writes original decoded RGB pixels through PyAV's PNG encoder; no extra image dependency, resizing or lossy encoding is involved. Default time sampling starts at zero relative to the first PTS and selects the first frame at/after each three-second target. Targets stay anchored to zero; gaps skip already-passed targets without duplicating an image. Integer stride and an optional exported-frame cap are alternatives. Early completion closes the decoder.

The separate export manifest has `kind: frame_export`, `schema_version: 1`, lifecycle status, creation time, source video path/SHA-256, sampling settings, PyAV version and pipeline revision/dirty state. Each frame records `file_name`, decoded `frame_index`, relative `timestamp_ms`, original `source_time_ms`, original dimensions and PNG SHA-256. Filenames are `images/frame_<first-12-video-hash>_<9-digit-index>.png`; the full hash stays in the manifest. Existing directories are rejected; failures retain diagnostic partial files and a failed manifest, which the converter rejects.

The converter reads extracted COCO JSON and a completed manifest. It validates unique IDs, exact supported category names, known filename basenames and matching dimensions; file prefixes are not opened or trusted as paths. It converts finite, positive, in-bounds pixel `xywh` rectangles to normalized `xyxy`. Unknown references/classes, duplicate alias mappings, crowd/ignore flags, segmentation, keypoints and rotated boxes fail; there is no silent clamping or dropping. Native `player`/`football` and COCO `person`/`sports ball` names map to the two evaluator classes.

Every included image is retained, even with zero boxes. `--reviewed` explicitly asserts human review of all included images because COCO cannot distinguish unfinished images from true negatives. A nonempty reviewed subset is allowed; omitted manifest indices are recorded, not scored as negatives. Output provenance hashes the exact COCO/manifest bytes and records reviewed/included/exported counts and exclusions. Validation completes before exclusive output creation; a failed write removes only the newly created partial file. Source COCO, manifest and PNGs must be retained for audit. Metadata matching and a review assertion cannot prove annotation completeness or that an image was not modified; the converter does not reread image pixels.

With `--scope`, the converter reads strict JSON from a separate region file, validates it, embeds it in v2 labels and records its exact SHA-256 in provenance. Its `--reviewed` assertion includes review of the scope as well as the included images. Without this option, existing full-frame v1 conversion remains unchanged. CVAT object polygons/ignore flags remain unsupported; the region is not an extra COCO category or object.

Both models still run on the original video. Time-selected labels require stride 1 with no cap in the documented workflow so every required index exists; stride-selected labels can share that integer stride. The exporter/converter themselves do not upload images, parse ZIPs or split datasets. Optional `cvat-sdk==2.80.0` supports the agent's task uploads, original-image retrieval, targeted box edits, issues and exports. The configured community MCP has only nine allowed read tools and a read-only token; writes use the official API. See [labelling](labelling.md) for accounts, provenance, human approval and safe editing. There is no unattended annotation service.

## Reviewed match results

The [v1 contract](../contracts/match-result-v1/README.md) now defines the offline Python-to-Dart data boundary. `loads_match_result` rejects malformed JSON, duplicate keys, unknown fields/versions and invalid semantic references. `dumps_match_result` revalidates before serializing. The Python dictionary remains mutable; callers revalidate after changes. The Flutter consumer produces detached immutable models.

Snapshots carry stable match/roster/event IDs, result/event revisions, source-video identity and timing, reviewed intervals, reviewer/producer provenance, confirmed goals (including own goals and unknown scorers), nullable player counts and optional relative clip keys. Complete coverage is an explicit human assertion, requires full-recording review, and gates `final_score`; partial coverage never produces a final score. Unknown counts remain null, not zero.

The format is a replacement snapshot contract, not an award ledger. Historical revision/conflict handling, persistence, authenticated access, file/clip resolution and screen integration are not implemented. Structural validation cannot prove human review, full-match capture or media content. CVAT person/ball boxes do not establish goals: real match-result production still requires separate event review.

The mirrored contract directory is checked with `diff -ru` during coordinated changes. Each CI validates its own copy independently through the full unit suite. No schema-engine, code-generation or model-runtime dependency was added.

## Tests and gaps

Tests cover normalization, class/architecture checks, device forwarding, deployment/load failures, RGB/size ordering, timestamps/stride, lifecycle/overwrite protection, timing, malformed inputs, matching and CLIs. Annotation tests cover fractional/irregular time sampling, PNG pixel round trips, manifest association, reviewed negatives/subsets, malformed COCO and write failures. A generated H.264 → exporter CLI → COCO fixture → converter → saved-prediction evaluation test checks the contracts together without ML dependencies.

Reviewed-result tests execute the same valid/invalid fixture cases as Dart, round-trip accepted snapshots, preserve unknown/zero values, validate goal attribution/counts and exercise replacement corrections. Real checkpoint integration/native operations and hardware timing require separate runtime checks. The first real 42-frame comparison is recorded in [pilot results](benchmark-results-2026-10-30.md); the [model/input-size follow-ups](ball-detail-experiment-2026-10-30.md) retain their historical labels and scores. Corrected labels and the user-identified 7:00 ball are now frozen as revision 3, with all thirteen earlier runs re-scored equally. The new [1080p crop experiment](crop-experiment-2026-10-30.md) gives 20/34 playing-ball matches full-frame versus 22/34 with six extra views, at 6.84× CPU prediction cost. The wrapper's resize/mapping/merge, optional manifests and failure paths have comprehensive offline tests and completed real-checkpoint runs; native inference remains the default. CUDA/MPS/mobile, held-out accuracy, full-match inference stability, training, active-ball selection and app screen/file integration remain unverified/unimplemented. Current coverage/checks are in [verification](verification.md).
