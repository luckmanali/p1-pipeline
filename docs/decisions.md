# Decisions

These choices were made while restoring the experiment on **25 October 2026**. They are not claims about the original author's intent. New entries include date, status, context, choice, alternatives, consequences and affected code/docs. Keep superseded entries and link their replacements.

## P001 — Dedicated Python benchmark repository

**Status: accepted.** Retain the old experiment as a focused workspace separate from Flutter. Alternatives were deletion or embedding ML code in the app. Native Python runtimes/datasets need independent iteration without coupling app releases to experiments. No service or app integration is implied. See [architecture](architecture.md).

## P002 — Detection checkpoints and shared box contract

**Status: accepted.** The old person-only pose checkpoint could not detect a ball. Use YOLO26n detection and official D-FINE-N COCO, validate architecture and map person/sports ball into normalized boxes for one evaluator. Pose remains a separate later stage. Native preprocessing is retained; `player` is the current name for person detection, not participant identity.

## P003 — Native FP32, batch 1, 640 baseline

**Status: accepted.** Use CPU/CUDA with equal size, precision, device and sampling, while preserving upstream preprocessing (YOLO letterbox; D-FINE stretch). Alternatives were forcing common resizing or adding exports immediately. This reduces export-related variables and establishes a working baseline; it does not isolate architecture speed or predict mobile/ONNX/TensorRT performance. Exports and other precisions require separate configurations/evidence.

## P004 — Presentation timestamps and explicit geometry limits

**Status: accepted.** PyAV PTS/time-base values preserve variable-rate timing; nominal FPS arithmetic does not. Stride controls inference frequency. Reject display transforms/non-square pixels until orientation handling has dedicated tests/evidence. Silent geometry changes could invalidate annotations and clips. Real smoke testing exposed PyAV mapping iteration semantics; a decoder regression test now covers frame side data.

## P005 — Saved predictions and labelled precision/recall

**Status: accepted.** Save boxes once and evaluate hash-associated labels at explicit IoU/confidence thresholds. This allows threshold experiments without rerunning models and separates confidence/counts from accuracy. The initial confidence-ordered one-to-one evaluator is not COCO mAP. Full COCO evaluation/training waits for a defined match dataset. Unlabelled frames are excluded; missing required frames fail.

## P006 — Documentation and comprehensive tests with every change

**Status: accepted by the user.** Both repos require explanations of behavior/how/why, comprehensive unit tests for new/changed logic, regression tests for fixes and honest verification. This repo adds generated-video integration and separate checkpoint smoke tests. CI installs locked lightweight dependencies without models/paid services and reports statement/branch coverage. There is no arbitrary coverage percentage gate: review uncovered changed behavior and record gaps. See [AGENTS.md](../AGENTS.md).

## P007 — Explicit assets and immutable run directories

**Status: accepted.** Explicitly download official checkpoints/source, ignore them plus recordings/results in Git, hash inputs and reject reused run directories. This prevents implicit large downloads during tests, accidental footage commits and overwritten evidence. D-FINE's source is pinned independently because it is not packaged here. Preserve source changes before distributing results from a dirty checkout.

## P008 — Local frame export and reviewed CVAT rectangles

**25 October 2026 — accepted.** Preparing an unbiased detector comparison requires images tied to exact decoded video frames and a reviewable label conversion. Export original-resolution lossless PNGs using the already-installed PyAV runtime, sharing inference's decoder and PTS validation. Sample by elapsed time by default, or explicit integer stride; store source/frame hashes and indices rather than reconstructing a lower-FPS video. This avoids coordinate drift, extra dependencies and a second frame-number convention.

Use CVAT's COCO rectangle export as the interchange format and convert locally to the existing evaluator schema. Alternatives were a custom annotation UI, CVAT account/API automation or changing the evaluator to depend on an annotation service. Those add unnecessary scope for this pilot. Preserve reviewed empty images, require an explicit review assertion and record omitted frames. Reject unsupported crowd/ignore/geometry instead of silently changing scoring. COCO cannot prove completeness; human review and exclusion reasons remain necessary. Existing outputs are immutable, and private images/annotations remain outside Git. See [annotation contracts](architecture.md#annotation-preparation-contracts--version-1) and [workflow](benchmarking.md#frame-export-and-cvat-import).

The account/API automation deferral above is superseded by P009 at the user's request; image/label contracts and the review requirement remain unchanged.

## P009 — Local CVAT, restricted MCP and assisted review

**25 October 2026 — accepted.** The user requested CVAT setup and AI-created labels with manual correction. Run official CVAT Community v2.80.0 locally on existing OrbStack, expose only loopback port 8080, and keep persistent annotation data in Docker volumes. This avoids adding a paid hosted service or uploading recordings to a separate annotation provider. Images inspected by the assistant are still shared with the assistant; local CVAT does not imply local-only AI inference.

Pin and audit the community MCP. Its unrestricted uploads, overwriting downloads and generic replacement/deletion operations are unnecessary risks for this workflow. Enable only nine read tools with a separate read-only PAT, and use the pinned official SDK for task uploads, targeted annotation PATCHes, read-back verification and review issues. Alternatives were enabling the complete connector or writing/maintaining a new MCP; neither is needed. No community-source patches were required. The remaining connector limitations and expiry/configuration details are in [labelling](labelling.md).

The assistant drafts from image pixels and flags ambiguities; the user can correct the same shapes in CVAT. Review all frames in the initial pilot and frozen benchmark, because a missed object may never be flagged. Candidate detector predictions must not become their own uncorrected answer key. Reduced human review may be considered later for training-data production with audits, but does not satisfy the benchmark's existing `--reviewed` contract. A real CVAT/COCO synthetic round trip now verifies the integration; match annotation quality remains untested.

## P010 — Shared reviewed match-result v1

**Status: accepted and implemented, 30 October 2026.** The app needs a stable handoff before real footage or complete event automation exists. [The contract](../contracts/match-result-v1/README.md) is strict JSON with Python validation/serialization and matching immutable Dart models. It carries confirmed goal events, stable IDs/revisions, video timing/provenance, explicit partial coverage, nullable counts and relative clip keys. Own goals credit the opposing team; unresolved scorer identity cannot become a false zero for a player.

The result is a replacement snapshot. Revision fields support future correction/retry handling, but persistence and award idempotency are not implemented by validation. Whole-match completeness is a review assertion, never inferred from video length or a successful detector run. Draft/rejected events remain outside published snapshots; more event types require a new version.

Alternatives were reusing the app's zero-default fixture stats, adding a schema/code-generation framework, or defining every future analysis feature now. The first loses availability semantics; the others expand this boundary beyond the immediate reviewed-match use case. Reuse existing Python strict-JSON helpers and standard Dart libraries. Mirrored contract/example/conformance files let each repository test independently; cross-repository changes also require a byte-for-byte parity check. See both repos' verification/architecture records for actual checks. UI import, media generation and storage remain next work.

## P011 — First real clip is development material with a small independent pilot

**30 October 2026 — adopted.** The user supplied a six-a-side video and numbered team screenshot. Preserve the exact source and its hash, assign the whole recording to development, and start with 42 native-resolution frames at stride 300 across the 494-second clip. This fits the first 30–50-frame review batch while including the whole clip; integer stride also lets both candidate runs sample exactly those source indices. Sampling was chosen before inspecting candidate predictions. More frames from this same match will not become independent test data.

Draft boxes by inspecting the pixels, without using YOLO26n/D-FINE-N predictions as the answer key, then require human review of every included frame. Keep R1–R6/B1–B6 identity references separate from the COCO-person/sports-ball benchmark. Shirt colour is insufficient because the user's team grouping includes mixed clothing, and spectators still need person labels. The screenshot was subsequently matched to frame 6,944 at 4:37.760 using pixel comparison and visual inspection; cross-frame identity continuity remains unresolved. Keep this deliberately selected reference frame outside the systematic benchmark sample. See [intake, verification and review status](benchmarking.md#current-development-recording--supplied-30-october-2026).

P012 supersedes the full-image annotation scope above for the current pilot; the source, sampling, independent annotation and human-review requirements remain.

## P012 — Select the main match before annotation and scoring

**30 October 2026 — user-requested scope, implemented.** The user asked to remove people on the other pitch because videos can show multiple matches. Remove those drafts while preserving all retained shapes, and keep the original full-frame backup. Merely deleting their labels would incorrectly penalize either detector for finding real background people. Define a fixed-camera convex match-area polygon, freeze it with the reviewed labels, and apply the same spatial filter to both models' predictions. Person boxes use bottom-centre and balls use centre; boundary points are included and boxes are not clipped.

The converter's optional `--scope` writes v2 labels with the region and its source-file hash. The evaluator accepts legacy full-frame v1 or scoped v2, rejects misplaced ground truth, and reports excluded detection counts. A schema bump makes older evaluators fail safely. Runtime prediction/image geometry remains unchanged, so existing full-frame inference outputs can be scored consistently without claiming a speed gain.

Alternatives were deleting labels alone (unfair scoring), cropping/masking detector input (changes model inputs and timing), or immediately implementing participant tracking (larger than spatial selection). The chosen region removes the separate pitch, but cannot identify roster members or disambiguate projected overlap. People inside it remain the person class. Review the boundary and difficult anchors, and exclude unresolved frames. Per-frame regions for camera motion/cuts are not implemented. The current boundary is an assistant proposal awaiting human confirmation; no labels were promoted to ground truth by this change.

The user subsequently approved the pilot and requested resolution of all issues; P013 records the frozen revision and first comparison. The earlier statement above describes the scope-change stage before that approval.

## P013 — Freeze the approved pilot and retain both measured baselines

**30 October 2026 — recorded after the first comparison.** The user stated that the labels looked fine and requested resolution of all issues and continuation. Record that approval, resolve the 12 outstanding issues, complete the CVAT job and freeze all 42 frames plus the existing scope before running either detector. The resulting development revision has 493 person and 32 football boxes; exact source/label/scope hashes, code snapshot, exports and runtime manifests are retained privately. Later edits require a new dataset revision.

Use the already documented 640/FP32/batch-1 baseline on local CPU with four threads, equal frame sampling and fixed 0.25 confidence/0.5 IoU scoring. Run sequentially without paid compute. [Measured results](benchmark-results-2026-10-30.md) show higher precision/lower local latency for YOLO26n and higher recall for D-FINE-N. Ball matches of 2/32 versus 8/32 are insufficient evidence for automatic event reliability, so neither model is selected for production.

Retain the baseline and investigate higher image detail/stronger detectors under a separate development protocol, then validate on independent matches and intended hardware. Do not tune this run's labels or scoring threshold after looking at predictions and present that as an untouched comparison. Choosing a winner from this small pilot or reporting sparse-sample timing as full-match throughput would overstate the evidence. Manual geometry/event review and the app demo remain viable parallel work.

## P014 — Separate image detail from model capacity in the next experiment

**30 October 2026 — adopted before follow-up inference.** The user requested continuation after the initial ball misses. Compare YOLO26n, D-FINE-N and YOLO26s at both 640 and 1280, with the same frozen answer key and fixed thresholds. YOLO26s reuses the installed native runtime and offers the next model scale without adding another framework or paid compute. It is a larger baseline candidate, not a promised accuracy improvement. Repeat the original two 640 cells under the updated runner to detect accidental behavior changes. Preserve the original runs and pre-record the [six-cell protocol](ball-detail-experiment-2026-10-30.md).

Add only the two required input sizes and small YOLO scale. Preserve default 640 behavior, actual-scale validation, FP32, original-coordinate boxes and strict checkpoint loading. For D-FINE 1280, rebuild only derived geometry after loading at native size; verify learned parameters are unchanged with the real checkpoint. Alternatives were immediately fine-tuning, tiling or adding a new detector family. Those mix more variables and can follow if this controlled experiment exposes their need. No threshold tuning or label corrections belong inside this fixed comparison.

**Measured follow-up:** all six cells completed. Both YOLO 1280 variants matched 10/32 balls; small had fewer unmatched ball boxes but greater latency. D-FINE 1280 increased false alarms sharply. Retain YOLO26s 640 as an assisted person-labelling candidate and the two YOLO 1280 runs as ball-development baselines, without production selection. Move product work to reviewed geometry/events and Flutter handoff rather than an open-ended size sweep on one clip. Audit the ambiguous round near-goal item separately before any label revision; the current counts remain tied to the unchanged approved answer key. [Results and limitations](ball-detail-experiment-2026-10-30.md#measured-results) record the evidence.

## P015 — Two bounded tests of additional detail and capacity

**30 October 2026 — requested by the user before inference.** Extend the existing runner for YOLO26n at 1920 and YOLO26m at 1280. These two cells test additional image detail and capacity separately against the saved 1280 nano/small baselines. Keep the approved label revision, source, sampling, confidence/IoU, locked runtime and native postprocessing fixed; preserve all earlier artifacts. No new runtime dependency, fine-tuning or broad model sweep is needed. D-FINE 1920 remains outside the verified path and is rejected explicitly. See the [pre-recorded focused protocol](ball-detail-experiment-2026-10-30.md#focused-follow-up-1920-nano-and-1280-medium).

The user also asked why recall uses 32 balls despite 42 images. Retain the distinction between labelled object instances and evaluated images: images without a ball annotation still contribute unmatched predictions/false alarms. Audit their original notes and pixels without rewriting the scored answer key. A missing box can mean genuine invisibility, unresolved visibility or an annotation mistake; user approval records review, not proof of physical absence. Corrections need a separate dataset revision and equal re-evaluation.


## P016 — Large-model comparison through full source detail

**30 October 2026 — adopted at the user's request.** After the focused runs returned 11/32 (nano/1920) and 13/32 (medium/1280, with 34 unmatched ball boxes), compare YOLO26l at 1280, 1920 and 2560 using the same frozen answers and fixed operating point. The first cell isolates capacity against medium/1280; the later cells isolate resolution within the large checkpoint. This explicitly requested three-cell protocol replaces P015's stopping point for this experiment, without authorizing an unlimited search.

Source dimensions are 2560×1440, while `--input-size` sets the square letterbox tensor side. At 1280 the picture is 720 pixels tall; 1920 provides 1080p-equivalent picture detail; 2560 retains source detail without enlargement. Keep model/size names explicit so resolution recommendations cannot confuse video height and tensor size. Add large-checkpoint scale validation and 2560 forwarding/validation tests; preserve D-FINE's verified 640/1280 boundary and the existing runtime.

A perfect 32/32 recall is only a pilot diagnostic target: false alarms, answer-key uncertainty and held-out generalization still matter. Inspect saved low-confidence responses/localization misses and original label crops rather than lower the score threshold or edit labels to meet a target. Independent recordings and adjudicated dense ball/event windows remain prerequisites for a defensible model-selection claim. See the [recorded protocol and results](ball-detail-experiment-2026-10-30.md#large-model-and-source-detail-test).


**Measured consequence:** large/1280/1920/2560 matched 14/13/11 of 32, with 27/30/6 unmatched predictions. The larger source-detail settings did not solve recall. Loose reviewed boxes, nine unresolved visibility cases and the recurring near-goal object require adjudication before stronger model conclusions; preserve this frozen revision and re-score all candidates against any new revision. The next detector experiment should be specified from adjudicated failures (ball-focused crops/data), rather than assuming a larger model/input guarantees perfect recall.

## P017 — Separate a corrected ball draft from the scored answer key

**30 October 2026 — implemented as a draft at the user's request.** The user confirmed the near-goal round object is a spare football. Keep the existing generic sports-ball class and scope, including that spare wherever visible. Create a separate CVAT task using the original 42 PNGs, copying the 493 approved player rectangles unchanged, and re-draw balls from original pixels and temporal context. Preserve task 2, frozen revision 1 and all historical metrics. This avoids replacing the scored answer key or treating model predictions as their own reference.

The [new review task](labelling.md#ball-only-re-review-draft) has 33 playing-ball candidates and 42 spare-ball proposals, 13 open issues and no new human approval. Retain roles in a private ledger for interpretation; no class/schema or project-attribute change is needed. After human adjudication, refresh the ledger and re-score every saved detector setting equally. Separate playing-ball performance from the easier spare; the generic denominator changes and cannot be compared directly with the old 32. Unresolved visibility must be adjudicated explicitly, not converted into invented boxes or silently dropped hard cases.

The user's colour/inversion idea is retained as a [proposed bounded experiment](ball-detail-experiment-2026-10-30.md#preprocessing-idea-not-yet-tested), pending reliable labels. Altering appearance may help or hurt the checkpoint and does not restore hidden detail. No preprocessing implementation or inference run was added during annotation work.

## P018 — Freeze reviewed revision 2 and distinguish playing-ball recall

**30 October 2026 — completed after user review.** The user reported “labels reviewed”; eight review issues were already resolved and saved comments clarified visibility and that the spare must not be tracked as the ball in play. Preserve those comments, resolve the five remaining issues, complete task 3 and freeze its unchanged saved annotations as dataset revision 2. Retain all previous tasks, labels, draft evidence and scores.

Re-score all 13 saved runs (11 unique settings) with the same 42 frames, scope, confidence and IoU. No new inference is needed because prediction coordinates refer to the unchanged source. Keep the generic sports-ball benchmark complete, then partition matched ground-truth instances using the reviewed playing/spare ledger. This avoids presenting spare-ball detections as improved tracking of play or quietly declaring real balls background. The diagnostic does not identify active balls in predictions; future tracking must reject the spare explicitly.

[Measured results](benchmark-revision-2-2026-10-30.md) favor large/1280 for playing-ball recall (19/33) over medium/1280 (16/33), even though medium has higher generic recall due to more spare matches. Correct labels explain many earlier unmatched boxes; fourteen playing-ball misses remain for large/1280. Use it as the next bounded crop-test baseline, retaining the other measured baselines. This is a development choice, not production model selection or validated goal detection.

## P019 — Correct the 7:00 label and isolate a bounded 1080p crop test

**30 October 2026 — user requested, implemented.** The user identified the net-occluded ball at frame 35 and explicitly requested resolution followed by overlapping crops at 1080p. Dense original-footage context shows the goalkeeper rolling it out; the earlier shoe interpretation was wrong. Add one assistant-adjudicated visible rectangle, retain the user's identification and source evidence, and freeze label revision 3 before inference. Re-score all thirteen old runs equally. Preserve every existing rectangle and historical dataset/result; do not use model predictions as the answer key or claim separate human approval of exact new coordinates.

Keep YOLO26l/1280 fixed and test one full-frame view against the full frame plus six 960×640 overlapping ball crops. Both arms start from exactly the same 1920×1080 analysis image and apply identical ball-only NMS. Grid positions are fixed before results, independent of labels, and include the whole image. Native full-frame people remain unchanged. This isolates the extra crop views while retaining full-frame context and preventing duplicate-removal differences from masquerading as crop gains. It adds no dependency and retains the existing default/native path. The [protocol](crop-experiment-2026-10-30.md) records boundaries, commands, metrics and results.

Alternatives were sourcing crops from the 1440p original (would not test the requested 1080p baseline), cropping only labelled/missed-ball regions (test leakage), or adding AI enhancement/training simultaneously (would confound the comparison). Those are excluded from this bounded test. Six extra calls increase compute; measure all seven views and merge together, and inspect higher-confidence crop boxes that suppress correct full-frame boxes. Ordinary image resizing is not learned enhancement. Independent matches, active-ball selection, dense temporal/event evaluation and intended-hardware timing remain separate work.

**Measured consequence:** the 1080p control matches 20/34 playing balls and the crop arm 22/34, with no lost matches or unmatched generic ball predictions in either arm. Person predictions are identical. Mean CPU prediction cost rises 6.84×. Keep the recipe as an optional experiment rather than the default; prioritise football-specific training data and independent validation. Selective crop retries could reduce cost but are not implemented or measured.

## P020 — Separate draft goal review from frozen detector labels and published results

**30 October 2026 — implemented after the user accepted the next step.** Put the original continuous clip in a separate CVAT project/task, with goal-mouth polygons, ground-line polylines and pending event tags. Keep the fixed-camera geometry as tracks from frame 0, and retain uncertainty around the near goal's hidden post. Sparse detector frames cannot establish goal events or exhaustive coverage. Two-second previews plus denser selected sequences produce a review shortlist, not a final score or automatic goal-accuracy result.

Use original pixels and source indices for annotation. Eight silent H.264 replay clips preserve every frame of their windows, with source/output hashes and timing in a manifest. The small exporter reuses PyAV and the existing validated decoder, rejects unsupported fractional/VFR timing and geometry, streams disjoint ranges once, and refuses existing output directories. Unit tests cover generated-video frame identity/timing, delayed encoder packets, invalid input, preservation and failures. The 1080p detector experiment and its frozen artifacts remain unchanged.

Alternatives were adding goals to the COCO rectangle task, inferring goals solely from a ball behind the net, or immediately building an automatic crossing detector. Those would mix evaluation contracts or overstate the evidence. [The review workflow](goal-review.md) retains likely negatives and uncertain sequences, unknown team/scorer identities, and a pending decision for every tag. Human adjudication and coverage review precede a separate reviewed-result revision. No app import, tracking, training, final score or event-accuracy claim is introduced.


## P021 — Hand off a partial reviewed result before automatic events

**31 October 2026 — applied to the first real bundle.** After the user adjudicated all twelve event windows and corrected both goals, package only G01/G09/G10 as confirmed goals using the unchanged strict v1 contract. Preserve the source hash/timeline, stable candidate IDs, exact replay bytes, numbered roster aliases and human decision evidence. Keep the twelve reviewed windows (193 seconds) separate from the AI-sampled remainder of the 494-second recording. Export partial coverage and unavailable statistics explicitly; Red's scorer remains unknown.

This exercises the existing Python/Dart boundary with real media without waiting for reliable automatic ball/event detection. A full score would overstate coverage; filling absent statistics with zero would invent performance data. Exporting rejected candidates as goals or identifying players by kit colour would contradict the user decisions. Keep the nine rejected candidates and all geometry outside the v1 confirmed-event payload, in the private provenance. Do not change the wire contract to carry this one recording's audit details.

The bundle is a manually reviewed local artifact, not a reusable CVAT publisher or app importer. Validate it with both languages, retain immutable revisions and byte hashes, and keep the original full recording outside the portable three-clip package. The next implementation is safe local import, durable revision-aware storage, availability-aware screens and playback. No cloud deployment, final score, automatic analysis claim or awards are introduced. [Handoff and verification](reviewed-result-handoff.md).

## P022 — Plan a shared Frame 2 dataset with AI drafts and human acceptance

**31 October 2026 — user direction recorded; budget and hosting are recommendations.** The user can obtain hour-long matches from several similar Frame 2 pitches and wants multiple people to review AI-first annotations. Preserve the two detector classes and main-pitch convention; propose approximately 2,800–3,400 reviewed frames across six training, two validation and two test matches. Split by physical match before sample/model selection, including every video part or camera view, and retain the existing clip as development material. This is an initial within-venue experiment, not a guaranteed data requirement or a replacement for broader held-out evaluation.

Calibrate reviewers, assign small non-overlapping jobs, record draft provenance, require human inspection of every selected image and second review of ball presence/absence, and freeze explicit acceptance records. Training-only model proposals may reduce drawing effort; validation/test drafting stays independent of the evaluated model. The existing MCP remains read-only and SDK writes must preserve manual corrections. A prompt alone does not provide access or unattended automation.

Recommend CVAT Online Team for remote collaboration if its recurring cost/cloud destination are acceptable. Self-hosted Community on a maintained shared server remains the alternative when infrastructure control or avoiding per-seat cost is preferred. The current localhost deployment cannot serve remote teammates as-is. Neither a migration nor a purchase is authorised by recording this comparison. Online annotation does not require cloud training.

Document the training-export gap: evaluation-only spatial filtering does not make full-frame images with unlabelled adjacent-pitch objects safe for ordinary YOLO training. Specify/test preprocessing or an explicit ignore-loss policy before training, keeping coordinate transforms and inference consistent. Goal geometry, identities and continuous event labels remain separate. [Plan and rationale](frame-two-labelling-plan.md), [assignment prompt](team-labelling-prompt.md).
