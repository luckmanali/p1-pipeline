# Frame 2 team labelling plan

31 October 2026. Proposed starting budget and hosting recommendation, following the user's plan to collect hour-long Frame 2 matches and have several people review AI drafts. This documents the workflow; it does not provision hosting, purchase a plan, import new matches or implement training.

The supplied development clip is from the venue the user calls **Frame 2 / Frame Two**. Existing frozen annotations and comparisons remain unchanged. Read the [reviewer guide](cvat-reviewer-guide.md) for editor controls, [technical guide](labelling.md) for agent operations, and [copyable agent prompt](team-labelling-prompt.md) for each new assignment.

## What to collect and how much to label

The first objective is a player/ball detector for new Frame 2 matches under the intended camera conditions. Success here does not establish performance at other venues. Include several actual pitches/camera positions, different dates, teams, kits, balls and lighting. Similar-looking pitches still need distinct pitch and camera IDs. Aim for at least three pitch/camera setups if available; identify which setups the first release actually supports.

Use original continuous recordings at 1080p or better. Keep the original pixels and frame rate for annotation and preserve source hashes, filenames, dimensions and timestamps. Source-video height and the model's tensor input size are different settings. Record any eventual 1080p processing transform separately; the current exporter does not resize images.

Count reviewed **frames and visible ball instances**, not hours of footage. An hour at 25 fps contains about 90,000 frames; drawing/checking all of them is unnecessary for the initial still-image detector.

| Split | Independent matches | Sampled frames per match | Reviewed frames | Purpose |
|---|---:|---:|---:|---|
| Training | 6 | About 300–400 | 1,800–2,400 | Learn the venue's player/ball appearances; add difficult cases here |
| Validation | 2 | About 200 | 400 | Choose checkpoints, thresholds and settings |
| Test | 2 | About 300 | 600 | Final evaluation after the model and settings are fixed |
| Total | 10 | — | 2,800–3,400 | Initial planning budget, not an accuracy guarantee |

For a roughly one-hour match, every 12 seconds gives approximately 300 images. Every 18 seconds gives approximately 200. Use timestamp-based sampling and the existing exporter, checking its completed manifest for the actual count; duration and timestamp gaps can change totals. Spread samples across the entire recording. On training matches, optionally add up to about 100 distinct hard examples per match: small far-end balls, blur, occlusion, feet, goal/net areas and realistic distractions. Retain ordinary play and images with no visible playing ball. Do not select only easy images or only goals.

For validation and test, record systematic sample times before looking at detector predictions. Keep deliberately selected challenge examples separate from the representative headline metrics. Do not remove hard but labelable examples to raise scores. No-visible-playing-ball images still need person boxes and any visible spare-ball boxes.

This is a staged plan: first calibrate reviewers on 30 shared examples, then review an initial 100-frame batch; prepare roughly 600–800 training frames spread across the training matches and the validation set for a first learning experiment. Expand toward the table's full budget based on validation failures. Do not spend the entire annotation budget before measuring whether the first fine-tune helps. Keep the test set closed during these iterations.

For effort planning only: 3,000 frames at one minute of human review per frame would be 50 person-hours, before additional QA and adjudication. This is arithmetic, not a measured annotation rate. Time the initial batch and use its actual rate to divide work. AI drafts can save drawing effort, but a missed ball still requires searching the image.

The earlier [600–1,000-frame model-selection benchmark](benchmarking.md#recommended-pilot-and-expansion) across at least six evaluation matches remains a broader evaluation goal. The four validation/test matches above are a smaller first within-venue fine-tuning experiment. Expand independent test coverage before making release-quality or cross-venue claims.

## Split by physical match before annotation

Assign each match an ID, date, pitch ID, camera ID, source files/hashes and one immutable split in the coordinator's private intake ledger. Several video parts, halves, duplicate uploads or camera views of the same physical match stay together. Crops, resized images and augmented copies inherit that split.

Reserve validation and test matches before training or model-guided sample selection. A new date on a familiar camera tests new-game performance; a separately reserved pitch/camera tests transfer to another setup. Report these separately where available. One new match is a useful check, but can be unusually easy or difficult, so the starting budget reserves two for testing.

The current 42-frame clip and every other part of its original match remain development material. They cannot become an untouched test merely by choosing different timestamps. Looking at test failures and adjusting the model turns that set into development evidence; obtain fresh test matches for the next final claim.

## Shared labels and match area

Use the existing two rectangle labels and [annotation convention](benchmarking.md#annotation-procedure):

- `player`: every visible person inside the agreed match area, including a keeper, referee, substitute or spectator inside it. It does not establish participation, identity or team membership.
- `football`: every visible sports ball inside that area, including spares. The class does not mean "the active ball". Record known playing/spare roles separately through the coordinator; do not add unapproved CVAT classes or attributes.
- Draw tight boxes around visible extent, clipped at image borders. Do not extend boxes to imagined hidden bodies or invisible balls. Use original-pixel crops and nearby source frames for context. Indistinguishable patches stay unresolved until adjudicated.
- Agree a main-pitch polygon for each fixed camera before starting. Use the existing bottom-centre rule for person boxes and centre rule for balls; preserve the full box once in scope. Exclude adjacent matches, with no forced count of 12 people. If the camera moves, cuts or changes zoom, stop and have the coordinator define a separate segment/scope; the current evaluator supports only a fixed region.
- Goal lines/mouths, player identities and goal events belong to separate tasks. These sampled boxes do not provide continuous tracking or a reviewed final score.

**Training-export requirement, still to implement:** the current scope polygon filters annotation/evaluation membership; it does not mask the training image. Do not feed ordinary full-frame YOLO training images containing unlabelled adjacent-pitch people/balls as though every visible target were labelled. Specify and test consistent pitch preprocessing (with transformed boxes where necessary), or a supported loss-ignore policy, before training. Apply the chosen policy consistently in validation, testing and inference. Preserve native source annotations so a derived training export can be rebuilt. Reusing the evaluation-only region is not enough.

## AI draft, human review, acceptance

One coordinator owns the match ledger, shared label definitions, exports and frozen revisions. Each reviewer has an individual account and assigned jobs of roughly 50–100 sampled frames. Assign one active editor per job; an agent must hand a job over before a person edits it. A second reviewer or coordinator adjudicates disagreements.

1. **Calibrate.** Review the same 30 examples independently in separate copies or recorded notes, including near/far balls, spares, occlusion, equipment and an adjacent pitch. Compare disagreements and agree examples of correct boxes before dividing work.
2. **Draft.** On training jobs, a configured detector can generate initial proposals, followed by AI visual inspection/correction and uncertainty issues. Record model/version/settings or visual-agent provenance. On validation/test jobs, use independent visual drafting, as in our pilot, and human inspection without the evaluated model's predictions as the answer key. Evaluated-model output must not determine which frames are annotated or accepted.
3. **Review every image.** A person checks all selected frames, including images with no boxes, no issues or confident-looking predictions. Search for missing objects, fix wrong/tight/duplicate boxes, remove background/equipment mistakes and save. AI confidence is not review evidence.
4. **Check again.** A second person checks balls and ball-absence decisions on every sampled image, plus a random 10% of person annotations, and all flagged cases. Expand the audit if systematic mistakes appear. This includes looking for missing balls, not just checking existing rectangles.
5. **Accept and freeze.** Record reviewer, completed frame range, unresolved cases and adjudicator decisions. A coordinator verifies the saved state before accepting a job and exporting a new immutable revision. Save source mapping, scope, draft provenance, reviewed annotations and checksums. Never overwrite a previously scored dataset.

If visibility remains unresolved, retain the evidence and mark the frame for adjudication. The current evaluator has no per-object ignore support: its coordinator must exclude a genuinely unlabelable whole frame from scoring, record the reason/count and report that limitation. Do not delete an uncertain object's box and treat the image as a reviewed negative. Training inclusion policy also needs to be explicit.

CVAT supports [automatic model proposals](https://docs.cvat.ai/docs/annotation/auto-annotation/automatic-annotation/) and an [SDK auto-annotation interface](https://docs.cvat.ai/docs/api_sdk/sdk/auto-annotation/). Availability depends on the configured model and deployment. Our existing local workflow has visual-agent drafting and official SDK writes; an unattended batch prelabelling service has **not** been installed. The current MCP is read-only. Any new model-to-CVAT automation needs tested class mapping, coordinate transforms, preservation of human edits and read-back checks. Run batch annotation only on an empty draft assignment or a deliberately separate draft revision; never clear reviewed annotations.

A teammate only needs CVAT browser access for manual review. The [prompt](team-labelling-prompt.md) needs an image-capable assistant with access to the assigned frames and authorised CVAT tools for actual AI writes; pasting it into an ordinary chat does not establish that access. The coordinator can generate all drafts centrally, so every reviewer need not install an MCP or share the agent's credentials.

## Hosting recommendation

For several reviewers working remotely, **CVAT Online Team is the recommended starting option**, assuming its recurring price and cloud storage are acceptable. It avoids making the user's laptop the shared server. This is a proposal; no account, subscription, upload, migration or new agent connection has been created.

The published Team price checked on 31 October 2026 is **US$33 per user/month** on monthly billing, or **US$23 per user/month equivalent** on annual billing, starting at two seats. Three monthly seats would therefore be US$99/month before any applicable tax. Confirm the current checkout, seat count, storage and AI-use allowance before subscribing. [CVAT Online pricing](https://www.cvat.ai/pricing/cvat-online).

[CVAT Community](https://docs.cvat.ai/docs/products/community/) is free self-hosted software. A shared deployment still requires reachable, reliable hosting, storage, backups, updates and access management. It is reasonable if avoiding per-seat charges or retaining infrastructure control is the priority and someone owns maintenance. An always-on shared server is a better team host than a sleeping laptop. Self-hosted annotation does not require a training GPU; model drafting can run separately.

The existing `http://localhost:8080` installation is reachable only on the user's Mac. The same address on another person's computer points to their computer. Retain this installation and its frozen work. For new team jobs, use one chosen shared service with individual accounts and explicit assignments; avoid separate independent CVAT installations for each reviewer. CVAT's [organization workflow](https://docs.cvat.ai/docs/account_management/organization/) describes shared ownership and roles.

Online annotation can still supply data for local training on the Mac; these are independent choices. Before adopting a shared host, run a tiny new task through upload, agent draft, manual correction, reload, annotation/image export and coordinate/filename checks. Reconfigure and verify authorised SDK access for that host; our local MCP's URL and credentials do not transfer automatically. Record the data owner's approval for the chosen cloud destination during intake.

## What this dataset will and will not establish

Report visible playing-ball recall separately from generic ball results containing spares, plus false detections, person metrics and results per match/pitch. Frame count is not the ball-recall denominator: an invisible ball has no valid box, while a spare adds another generic ball instance. Keep threshold selection on validation material and preserve speed/accuracy settings with each run.

Sparse samples can evaluate object detection. Later tracking and goal detection require separately reviewed continuous sequences with event decisions, including saves, near misses and ball disappearance. Reserve original videos for that work; do not claim successful goal detection from a high still-frame recall alone.

Next implementation: validated training export/split checks and safe batch prelabelling, followed by a small local fine-tune. The existing frame exporter and COCO benchmark converter already work; a reusable YOLO training pipeline, shared hosting and multi-user acceptance automation remain to build.
