# Reviewed ball revision 2 — 30 October 2026

**YOLO26l/1280 matches 19 of 33 reviewed playing-ball instances (57.6%)**, the highest playing-ball recall among the eleven saved settings. It also matches 21 of 42 spare-ball instances and leaves one unmatched generic ball prediction. These are new scores for unchanged predictions against corrected labels, not a trained or improved model. More input resolution still does not consistently improve playing-ball recall.

**Subsequent correction resolved in revision 3:** the user marked the net-occluded ball at CVAT frame 35 (source 10,500, 7:00) and requested resolution. Dense source context shows the goalkeeper rolling it out. One rectangle was added, all others preserved, and all old settings re-scored against **34 playing-ball labels**. Historical large/1280 is now 19/34. This document retains the exact revision-2 results; the [revision-3 correction and 1080p crop comparison](crop-experiment-2026-10-30.md) own the latest evidence.

## Review and frozen data

The user replied **“labels reviewed”** to the task-3 handover. Saved annotations were unchanged from the draft: 493 previously approved person rectangles and 75 ball rectangles across the same 42 images. The ball ledger separates **33 playing-ball instances** (including the added frame-16 label) and **42 spare-ball instances**. No frames were excluded. The nine images without a playing-ball box still contain the spare; there are no generic zero-ball images in this revision.

Eight of thirteen issues had already been resolved in CVAT. The assistant preserved those resolutions and reviewer comments, resolved the remaining five on the review confirmation, and read back [task 3/job 3](http://localhost:8080/tasks/3/jobs/3) as acceptance/completed. The user supplied context about the ball being hidden at frames 12 and 24, possibly above the image at frame 10, and behind the net after a goal at frame 14. Those comments are retained as reviewer context; they do not constitute a separately verified goal-event record. Issues without a human explanation were accepted through the overall review confirmation; no detailed explanation or independent second-annotator agreement is invented.

The user also stated that the spare **must not be tracked as the ball in play**. That requirement is retained. The current detector class is generic sports ball, so its benchmark includes the visible spare while reporting playing-ball performance separately. The role ledger describes the reviewed objects; it does not mean a detector identified which ball was in play. An active-ball selector/tracker remains to build.

Private `data/football-clip-iqLnW_238X8-20261030/reviewed-v2-20261030/` contains the approval/comments, frozen API snapshot, full CVAT backup, COCO export, frame manifest, scope, reviewed role ledger, converted labels, scoring script/self-checks, per-run evaluations and comparison. Dataset revision **2** and label-schema version **2** are different concepts. The labels file is `benchmark-labels-v2.json`, SHA-256 `f339f8a87c8c47ba2f5a3683c7f84dc6477ffb385d26115950f314f65697f570`.

Task 2, frozen revision 1, the earlier AI draft and all historical detector outputs/scores remain intact. Revision 1's 32-ball scores should not be compared directly with revision 2's 75-ball generic denominator.

## Equal re-scoring protocol

Re-evaluate the **13 saved runs representing 11 unique model/input settings**, including the two original 640 baselines duplicated by the later experiment. Use all 42 original source indices, the same main-game scope, confidence **0.25**, IoU **0.50**, and saved inference floor **0.05**. No new inference, checkpoint, threshold tuning, preprocessing or training occurred. Original video SHA-256 remains `eac1a39d83c727f142d33e6a8ede112224ab14d925680a3584254a83fa397984`.

The existing evaluator performs generic one-to-one matching. A private diagnostic reproduces that ordering/matching and assigns each matched reference box its playing/spare role. Every per-role TP/FN total reconciles to the official generic totals. Unmatched predictions remain shared **generic ball false positives**; per-role precision is not claimed. In particular, spare detections would still need rejecting when selecting an active-ball track.

## Results

Input is the model's square tensor side. For this 2560×1440 footage, YOLO 1280 contains a 1280×720 picture, 1920 a 1920×1080 picture, and 2560 retains full source detail plus padding.

| Model | Input | Playing matches / 33 | Playing recall | Spare matches / 42 | Generic TP / FP / FN | Generic precision |
|---|---:|---:|---:|---:|---|---:|
| YOLO26n | 640 | 2 | 6.1% | 0 | 2 / 0 / 73 | 100.0% |
| YOLO26n | 1280 | 10 | 30.3% | 2 | 12 / 3 / 63 | 80.0% |
| YOLO26n | 1920 | 11 | 33.3% | 2 | 13 / 1 / 62 | 92.9% |
| YOLO26s | 640 | 4 | 12.1% | 0 | 4 / 0 / 71 | 100.0% |
| YOLO26s | 1280 | 10 | 30.3% | 2 | 12 / 0 / 63 | 100.0% |
| YOLO26m | 1280 | 16 | 48.5% | 31 | 47 / 0 / 28 | 100.0% |
| YOLO26l | 1280 | **19** | **57.6%** | 21 | 40 / 1 / 35 | 97.6% |
| YOLO26l | 1920 | 17 | 51.5% | 25 | 42 / 1 / 33 | 97.7% |
| YOLO26l | 2560 | 15 | 45.5% | 2 | 17 / 0 / 58 | 100.0% |
| D-FINE-N | 640 | 10 | 30.3% | 0 | 10 / 11 / 65 | 47.6% |
| D-FINE-N | 1280 | 6 | 18.2% | 3 | 9 / 77 / 66 | 10.5% |

Generic recall uses 75 reference balls: for example, medium/1280 is 47/75 (62.7%), while large/1280 is 40/75 (53.3%). Medium's higher generic recall is driven by finding the spare more often; **large/1280 is better on the playing ball**. Neither figure establishes active-ball identity or tracking. Zero unmatched predictions in this small sample does not establish perfect precision on other recordings.

Person metrics are exactly unchanged for every run. Historical timing is also unchanged because inference was not repeated: large/1280 averaged 640.3 ms per sampled prediction on the local CPU, versus 528.8 ms for medium/1280. These are descriptive prior timings, not new performance measurements or full-match throughput. See the [original experiment](ball-detail-experiment-2026-10-30.md) for all timing and hardware details.

## What the corrections explain

Large/1280's playing-ball matches increase from 14 to 19 when five previously unmatched predictions now meet the tighter reviewed boxes: CVAT frames **7, 11, 17, 22 and 27**. Its original 27 unmatched ball predictions become one: 21 now match the confirmed spare and five match corrected playing-ball boxes. The additional frame-16 playing-ball label remains missed. The remaining unmatched prediction is at frame 23, where another prediction already matches the playing ball.

Medium/1280's original 34 unmatched predictions become zero: 31 match the spare and three match corrected playing-ball boxes. This demonstrates that many apparent false alarms were annotation omissions or localization disagreements. It does not recover the remaining missed balls.

For large/1280's **14 remaining playing-ball misses**, saved-response inspection finds three with sufficient overlap but confidence below 0.25 (frames 26, 28, 31), one nearby response with insufficient overlap (frame 20), and ten with no saved in-scope ball response reaching IoU 0.1. The saved floor is 0.05; this does not prove there was no weaker raw model response. Lowering the confidence threshold alone cannot recover all fourteen and may admit more false alarms.

D-FINE-N/640 reaches 10/33 playing-ball matches. At 1280 it reaches 6/33, with 77 unmatched generic ball predictions; three of its nine generic matches are the spare. Corrected tighter boxes can lower scores as well as raise them. D-FINE-N remains a baseline; this is not evidence against every D-FINE model or a fine-tuned checkpoint.

## Verification and next work

**73 focused tests passed:** 39 evaluator and 34 CVAT-converter tests. The private role diagnostic also passed checks for duplicate predictions, ordering/ties, confidence and IoU boundaries, empty cases, scope exclusion and isolation of per-run diagnostic metadata. Its totals reproduce all 13 official evaluations. A first diagnostic attempt shared mutable miss-category metadata across models; it was retained as superseded, fixed with copied metadata and an isolation regression, then regenerated. Official score totals were unaffected.

The real COCO conversion matched all 568 saved rectangles by original frame/class/coordinates. Source-video and all 42 PNG hashes, ZIP integrity, label/scope association, frame timestamps/dimensions, preserved person boxes and unchanged historical scores were checked. The original/repeated 640 detections are byte-identical and re-score identically. The approval operation initially stopped on an overly strict count expecting thirteen new resolutions; read-back showed eight already resolved and five newly resolved, and export resumed without repeating mutations. These operational checks changed no pipeline/app runtime or dependencies; the preceding full 156-test code baseline remains applicable.

Next, define and implement a bounded overlapping-crop test against the large/1280 baseline while collecting varied labelled footage and independent held-out recordings. Preserve coordinate mapping, merge duplicate crop detections and count false alarms. Then establish football-specific fine-tuning and evaluate temporal continuity on dense sequences. Keep the [contrast/inversion proposal](ball-detail-experiment-2026-10-30.md#preprocessing-idea-not-yet-tested) optional and bounded. Goal geometry and continuous-footage event review remain separate work. No new training, cropping, preprocessing, tracking or automatic goal detection was implemented by this re-scoring operation.

## Proposed capture policy and quality targets

These are engineering proposals following the user's 1080p/enhancement question, not implemented upload rules or validated product guarantees.

- Use native **1920×1080 as the minimum capture guideline**, accept higher-resolution originals, and establish a common 1080p analysis baseline. Resolution alone cannot qualify a recording: assess pitch/goal coverage, camera stability, lighting, compression, motion blur and far-side ball visibility. An upscale does not establish native capture quality. The supplied source is 1440p; our 1920-tensor run contains a 1080p picture, but downscaling it does not validate compressed/native-1080p uploads.
- Capture resolution and detector input remain separate. For this 16:9 clip, YOLO 1280 uses a 1280×720 picture; 1920 uses 1920×1080 plus padding. A 1080p experiment must record the exact common resize and preprocessing for all candidates, retain originals and use new run directories. Crop comparisons must start from that same analysis image; results using additional 1440p detail must be reported separately.
- **19/33 = 57.6%** is a baseline; **25/33 = 75.8%** is a useful intermediate improvement but still misses about one in four labelled playing-ball instances. Aim initially for **at least 90% visible playing-ball recall** at the fixed IoU/confidence protocol, approximately 30/33 on the present tiny sample. Evaluate any confidence change on validation data before freezing a held-out test. The desired **at least 95% active-ball precision** also requires a selector that rejects the spare; current generic precision cannot establish this.
- Validate these targets on separate matches and dense sequences, reporting sample counts, uncertainty and difficult subsets. This repeatedly inspected development clip cannot be the release gate. Measure track gaps/identity errors and review time as well as frame recall; estimated positions through occlusion must remain marked as estimates. Good average recall does not guarantee that goal-line crossings or player contacts were observed.
- For the first reviewed-goal pilot, propose **at least 95% goal-event recall and precision on independent annotated sequences**, with every published goal human-confirmed. The evaluation must include manual full-sequence review to find missed goals, not just acceptance of generated candidates. Event time, scoring team and any player attribution need their own verification; leave ambiguous details unknown. Human-reviewed imports can be developed before automated detectors meet these targets. Fully automatic scoring and possession/pass statistics need separate validation.

## Selective enhancement experiment proposal

AI restoration can combine information across nearby frames: [BasicVSR](https://arxiv.org/abs/2012.02181) studies temporal propagation/alignment for video super-resolution. However, a visually convincing restoration is not necessarily faithful to the source; the [perception–distortion tradeoff](https://arxiv.org/abs/1711.06077) motivates evaluating detection accuracy rather than appearance. Neither paper establishes a benefit for this football detector.

Proposed processing order: baseline detection → flag missing/ambiguous ball evidence → inspect an overlapping crop and a short source-time window → optionally restore that same crop/window → re-run detection and compare with the original evidence → retain uncertainty or request human review. Trigger on missing detections or future track gaps as well as low confidence; a completely missed ball has no confidence score. No tracker or automatic retry mechanism exists yet.

Test unchanged crop pixels, ordinary resizing, gentle contrast and learned restoration separately using the same model, windows, merge rules and independent labels. Select regions/windows without looking at test labels, include no-ball regions and spare-ball distractors, and score the complete pipeline including the retry trigger. Report recall, false alarms, localization error and added latency. Keep the original imagery/timestamps and map output boxes back to source coordinates. An enhanced image cannot establish a genuinely hidden ball or prove a goal-line crossing by itself. Retain enhancement only if the measured benefit justifies its false-positive and runtime costs; do not implement it as a default prerequisite for analysis.
