# Labelling with CVAT and an AI assistant

For new Frame 2 matches and multiple reviewers, see the [team collection/review plan](frame-two-labelling-plan.md) and [reusable prompt](team-labelling-prompt.md). The recommended shared host and batch prelabelling remain proposals; existing local tasks and frozen annotations are preserved.

A separate [full-video goal/event review task](goal-review.md) is available as task 4/job 4. On 31 October the user's near and far goal corrections were accepted; the near mouth bottom edge was aligned to the exact manually corrected line. All twelve event windows are now human-adjudicated: G01/G09 are confirmed for Blue 1 (B1), G10 for Red with scorer unknown, and nine candidates are rejected. G11 hit the post then had a saved follow-up; G12 was saved. All fourteen geometry/event issues are resolved, including near-goal issue 87. Physical occlusion flags remain despite review acceptance; these markings are image geometry, not calibrated crossing measurements. The search is documented separately from human adjudication and does not certify exhaustive clip coverage. The approved detector-box tasks and exports below are unchanged. A separate [partial reviewed-result bundle](reviewed-result-handoff.md) now packages the three confirmed goals and clips for the app; it does not alter COCO labels or publish a final score.


Updated 30 October 2026. The user approved all [42 pilot frames in task 2/job 2](http://localhost:8080/tasks/2/jobs/2) and requested resolution of every issue. The remaining 12 issues were resolved; the job is acceptance/completed, with 493 person and 32 football boxes unchanged during export. The approved main-game scope, COCO export, v2 labels and backup are frozen in private revision `reviewed-v1-20261030`. Both detectors completed the [first pilot comparison](benchmark-results-2026-10-30.md). Future corrections must create a new dataset revision rather than overwrite this scored answer key. The workflow below remains the rule for subsequent batches; see [verification](verification.md) for evidence.

New reviewers should start with the illustrated [CVAT reviewer guide](cvat-reviewer-guide.md), covering access, practice, corrections, issues and handover. This document covers setup and the agent/data workflow.

## Ball-only re-review draft

**Review completed later on 30 October:** the user reported “labels reviewed” and supplied CVAT comments. Eight issues were already resolved; the remaining five were resolved with read-back checks. Task 3 is now **acceptance/completed**, renamed **DEVELOPMENT — ball review complete — 42 frames — revision 2**. The saved 493 person and 75 ball rectangles were unchanged during approval/export. Private `reviewed-v2-20261030/` retains the frozen labels, review comments, full backup and equal re-scoring of all saved outputs. See [revision-2 results](benchmark-revision-2-2026-10-30.md). The paragraphs below record how the draft was prepared and reviewed; they are not a request to repeat the completed review.

**Latest correction, also 30 October:** task 3 is now named **DEVELOPMENT — ball review complete — 42 frames — revision 3**, still acceptance/completed. The user identified a ball behind the net at frame 35/7:00 and requested resolution. Source frames through 421 seconds show the goalkeeper rolling it out. One assistant-adjudicated rectangle was added and read back, with all 568 previous rectangles unchanged; the prior shoe interpretation was incorrect. Revision 3 has 34 playing and 42 spare balls, plus 493 people. Separate snapshots, COCO export, full backup and review provenance are in private `reviewed-v3-20261030/`; all previous outputs remain frozen. See the [correction and crop experiment](crop-experiment-2026-10-30.md). No further human box approval is invented: the record distinguishes the user's object identification/instruction from assistant-drawn coordinates.

**30 October 2026:** the user confirmed that the pale round item on the near-goal equipment is a spare football. It belongs to the existing generic `football` class because it is inside the agreed main-game scope. The equipment itself remains unlabelled. Detecting the spare does not establish detection or tracking of the playing ball.

Open [task 3/job 3](http://localhost:8080/tasks/3/jobs/3), the separate **DRAFT — ball re-review v2** task. It contains the same 42 images and 493 unchanged approved player rectangles. The assistant inspected all images, original-pixel ball crops and temporal context, then added **75 draft ball rectangles: 33 playing-ball candidates and 42 spare-ball instances**. Frame 16 has a newly proposed partly visible playing ball; frame 18's ball-versus-boot interpretation is particularly uncertain. All coordinates remain proposals, including those around the user-confirmed spare.

Review every frame **0–41** for balls in Standard mode, using the [editing controls](cvat-reviewer-guide.md#review-and-amend-each-frame). Save corrections and resolve issues only after checking them. Thirteen issues cover eight unresolved playing-ball-visibility frames (8, 10, 12, 24, 32, 35, 37, 38), four difficult proposed boxes (14, 16, 18, 30), and the spare-ball addition. Context supports the playing ball being off-screen at frame 19. The spare is visible in all 42 images and changes position after frame 35, so these are no longer proposed generic zero-ball images. Do not invent boxes for fully hidden objects.

The draft was held in **validation/new** until that review. Task 2 and `reviewed-v1-20261030` are unchanged. Private `data/football-clip-iqLnW_238X8-20261030/ball-relabel-draft-v2-20261030/REVIEW_HANDOVER.md` preserves the original handover, mappings, proposed coordinates, clean crops, context and issue IDs. Revision 2 has its own reviewed role ledger verified against saved shape IDs/coordinates; it is not a new CVAT class, track or supported evaluator attribute.

After explicit whole-frame review and adjudication, export/backup a new reviewed revision and re-score every saved YOLO and D-FINE setting with the same revised labels, scope and thresholds. This step is now complete for revision 2. Preserve historical scores. Explain total-ball counts and playing-ball performance separately: adding an easier static spare changes the denominator and must not masquerade as improved detection of play. The user's requirement to avoid tracking the spare applies to future active-ball selection; generic sports-ball matches remain diagnostic. No preprocessing runs have occurred.

## What each part does

CVAT is the browser editor and annotation store. The assistant will inspect images, draft boxes, flag questions and manage the work. You can open the same task to correct a box, add a missed object or resolve an issue. Our [frame exporter and converter](../README.md#prepare-reviewed-labels) preserve the connection between these labels and the exact source video.

We use self-hosted [CVAT Community](https://docs.cvat.ai/docs/products/community/) so its database and uploaded images stay in the local Docker deployment. This does not make images viewed by the assistant offline: inspecting a frame in this conversation makes that frame available to the assistant.

The community MCP connector is a convenience for reading task state. It is not a detector, annotation model or substitute for image inspection. The configured connection is restricted to audited read-only tools. Annotation changes use CVAT's official API or SDK, with targeted updates and read-back checks. This split retains convenient inspection while avoiding broad third-party write operations that could replace existing work. The assistant can inspect frames and create drafts during an active chat; no unattended labelling service or automatic detector has been installed.

## Local installation

The deployment uses:

- Official CVAT **v2.80.0**, commit `bb0a873fe071e70d71458cd82127052025e05807`, under ignored `vendor/CVAT/`.
- The upstream `docker-compose.yml` plus the repository's [local override](../cvat.compose.yml).
- Compose project `p1-cvat`, with the browser interface at [http://localhost:8080](http://localhost:8080).
- A proxy bound to `127.0.0.1`; the override removes upstream published ports and exposes only port 8080 locally. Server, import, export and chunk worker process counts are reduced for the local pilot.

With Docker running, execute from the repository root:

```sh
docker compose -p p1-cvat -f vendor/CVAT/docker-compose.yml -f cvat.compose.yml up -d
docker compose -p p1-cvat -f vendor/CVAT/docker-compose.yml -f cvat.compose.yml ps
```

Open the browser address after services become ready. The human account is `player1-admin`; its generated login details are in ignored `data/cvat/login.json`. The separate `player1-agent` account owns the [benchmark project](http://localhost:8080/projects/1). A [synthetic setup task](http://localhost:8080/tasks/1/jobs/1) demonstrates boxes and a review issue; it is explicitly marked as test data and must not enter a benchmark. Keep credentials and access tokens out of Git, terminal output and documentation. Do not change the project name or compose-file combination between commands; they identify this deployment's resources. See the [official installation guide](https://docs.cvat.ai/docs/administration/community/basics/installation/) for upstream prerequisites and administration.

The official server/UI images are AMD64 and run under OrbStack's emulation on this ARM Mac; the local annotation smoke passed. This deployment is for labelling, not inference-speed measurement. Docker must be running to use it. Named volumes hold the database, images and related state independently of this checkout.

Stop the services without deleting stored work:

```sh
docker compose -p p1-cvat -f vendor/CVAT/docker-compose.yml -f cvat.compose.yml stop
```

Use the same `up -d` command to resume. Do not use `down -v`: it deletes the deployment's named volumes, including stored data. Export task backups and retain the original PNGs, source video and export manifest before upgrades or cleanup; see [CVAT backup guidance](https://docs.cvat.ai/docs/dataset_management/backup/).

The [community CVAT MCP](https://github.com/jangjs1216/CVAT-MCP) is pinned to commit `c1b3ce7461598a9f96edbfe7819e79e8732623b3` under ignored `vendor/CVAT-MCP/`. Codex's `cvat` connection uses that checkout as its working directory, Node 24.19.0, a separate read-only personal access token and this explicit `enabled_tools` allowlist:

```text
cvat_server_about
cvat_list_tasks
cvat_get_task
cvat_get_task_annotations
cvat_list_projects
cvat_list_jobs
cvat_get_job
cvat_get_request
cvat_list_labels
```

Do not load a generated tool catalogue or enable the complete upstream tool surface. Private credentials are in ignored `data/cvat/` (directory mode `0700`, credential files `0600`). The MCP reads `mcp-readonly.env`; official SDK operations read the separate `api-token.txt`. Both tokens expire on **23 January 2027** and can be replaced through the agent account's Personal Access Tokens settings. Never copy tokens into tracked configuration.

The connection is saved in `~/.codex/config.toml`, with an adjacent `config.toml.before-cvat-20261025` backup. Its launcher clears inherited token/organization variables, reads only the designated read-only token file, fixes the local base URL, and disables generated catalogues. `codex mcp get cvat --json` shows the non-secret configuration. The server advertises 15 tools; Codex permits only the nine above. The tools are available in the current chat and read the real pilot job successfully on 30 October. Restart Codex after future connection changes if its tool catalogue has not refreshed. Official SDK access works independently of that refresh.

The audit found unrestricted local-file uploads, potentially overwriting downloads, generic destructive API calls, no inline image output and limited timeout/protocol handling. Those write/download/generic tools are excluded; server-side read-only authentication also rejects mutations. No upstream code was changed. All eight upstream tests and nine live read calls passed, including reading the synthetic task's annotations. See the pinned [client](https://github.com/jangjs1216/CVAT-MCP/blob/c1b3ce7461598a9f96edbfe7819e79e8732623b3/src/cvat-client.js) and [dispatchers](https://github.com/jangjs1216/CVAT-MCP/blob/c1b3ce7461598a9f96edbfe7819e79e8732623b3/src/static-tools.js). Use the official API/SDK for writes even if the connector exposes similar write tools.

## Prepare a small first batch

Start with **30–50 frames** to establish the annotation convention and check the complete round trip. This is a workflow rehearsal within the larger [benchmark sampling plan](benchmarking.md#recommended-pilot-and-expansion), not enough evidence to choose a detector.

1. Keep the selected original, upright, square-pixel video in ignored `data/`. Export images with the existing tool, using a new output directory:

   ```sh
   uv run --locked python export_frames.py data/match.mp4 --output data/match-pilot-frames --every-seconds 3 --max-frames 40
   ```

2. Create a CVAT project or task with exactly two **rectangle** labels:

   | Label | What to include |
   |---|---|
   | `player` | Every visible person within the agreed match area, including any referee/spectator inside it. This is the COCO-person class, not roster identity. |
   | `football` | Every visible sports ball within that area. Exclude other pitches; do not infer an invisible ball. |

3. Upload only the PNGs inside `data/match-pilot-frames/images/`. Preserve their filenames. Keep the manifest beside the local images; it is not another frame to upload.
4. Read CVAT's frame metadata after upload. Match each server frame to the manifest by its unique filename and dimensions. Record task/job IDs and the mapping with the private dataset.

For main-game work, retain and review a fixed-camera `main-pitch-scope.json` alongside the dataset, following the [region and anchor rules](benchmarking.md#main-game-scope). Keep this polygon out of the CVAT object categories/COCO rectangles. Pass it to conversion with `--scope`. The legacy no-scope workflow evaluates the entire image and still requires all background labels; never mix its scoring with main-game-only annotation.

CVAT frame 1 means the second image in that task. It does **not** necessarily mean decoded video frame 1: a three-second sample might instead correspond to video frame 90. Never derive this mapping from nominal frame rate, upload order or an assumed stride. Read `Task.get_frames_info()` or `GET /api/tasks/{id}/data/meta` and match actual names. [Official task SDK recipes](https://docs.cvat.ai/docs/api_sdk/sdk/examples/tasks/).

## Draft, inspect and correct

The assistant should inspect original-resolution pixels and draft tight, axis-aligned rectangles around visible object extent, following the [annotation procedure](benchmarking.md#annotation-procedure). Use zoomed crops or adjacent frames when needed to understand an object; preserve coordinates in the original uploaded image. A missing or fully hidden object gets no invented box.

The assistant should flag uncertainty with a CVAT issue tied to the frame and region, explaining what needs checking. Examples include a possible distant ball, overlapping people, uncertain boundaries and a suspected missing annotation. An issue can flag a region even when no defensible box exists. You can navigate the Issues tab, switch to the Standard workspace to edit annotations, and resolve an issue after correcting or explaining it. [Official manual review workflow](https://docs.cvat.ai/docs/qa-analytics/manual-qa/).

Optional attributes on the existing two labels may record `origin`, `review_status` and `review_note`. Use `origin` to distinguish an assistant draft from manual or model-generated work; `review_status` can be `draft`, `needs_review` or `accepted`. These are workflow metadata, not new classes. Do not introduce labels such as `review` or `uncertain`, or use `ignore`/`difficult` flags: the converter deliberately rejects unknown categories and unsupported ignore semantics.

These attributes are optional conventions, not automatic approval controls. The converter currently ignores ordinary custom attributes and relies on its explicit `--reviewed` assertion. A shape-level status cannot prove that an empty frame was checked, or that all objects were found. Keep whole-frame review progress and final approval with the task/job record, including reviewed negative frames.

For the first batch, the assistant drafts and you inspect **every included frame**, with particular attention to small balls and missed objects. This shifts the work from drawing every box to checking and correcting proposed labels. Keep jobs in annotation/validation until the agreed review is complete; changing a job state is a record of review, not evidence that review happened. The normal workflow supports `annotation`, `validation` and `acceptance` stages. [Official job recipes](https://docs.cvat.ai/docs/api_sdk/sdk/examples/jobs/).

## Practise in the sample job

Follow the illustrated [reviewer guide](cvat-reviewer-guide.md#practise-before-reviewing-footage) in the [synthetic sample job](http://localhost:8080/tasks/1/jobs/1). It covers navigation, resizing/relabeling, adding/removing boxes, saving, issue resolution and review handover. The practice images and fake boxes teach the controls and must never enter the benchmark. The job remains in validation; an agent's UI demonstration is not human approval of ground truth.

## Safe API editing for agents

Use the authenticated official API or matching SDK against this local instance. The optional `cvat` dependency extra pins `cvat-sdk==2.80.0`; run SDK operations with `uv run --locked --extra cvat python`. Keep its write credential separate from the MCP's read-only token. Read current annotations and label IDs before making a change; never assume numeric label IDs are stable across tasks. Work on an agreed task/job while the user is not editing the same shapes.

| Operation | API or SDK method |
|---|---|
| Read original frame pixels | `Task.get_frame(frame_id, quality="original")`, or `GET /api/tasks/{id}/data/?type=frame&number=N&quality=original` |
| Read current annotations | `GET /api/tasks/{id}/annotations/` |
| Add new rectangles | `PATCH /api/tasks/{id}/annotations/?action=create` |
| Amend specific rectangles | Same endpoint with `action=update`, including the existing server shape IDs |
| Open a review issue | `POST /api/issues` with job ID, CVAT frame number, region position and message |
| Update review assignment/stage | `PATCH /api/jobs/{id}` |

After every mutation, read back affected annotations/issues and confirm the intended frame, class, coordinates and object IDs. Preserve user corrections. Re-read before updating a shape; targeted PATCH protects unrelated objects but does not make concurrent edits to the same object safe. If a request times out, inspect server state before retrying a create, to avoid duplicate boxes.

Do not use `PUT /api/tasks/{id}/annotations/` for incremental edits: it replaces the task's annotations. Annotation-file imports also default to replacing existing annotations unless configured otherwise. Keep a snapshot/export before substantial changes. [Official annotation recipes](https://docs.cvat.ai/docs/api_sdk/sdk/examples/annotations/), [Tasks API](https://docs.cvat.ai/docs/api_sdk/sdk/reference/apis/tasks-api/), [Issues API](https://docs.cvat.ai/docs/api_sdk/sdk/reference/apis/issues-api/).

CVAT also has an official [auto-annotation API](https://docs.cvat.ai/docs/api_sdk/sdk/auto-annotation/) for running a local detection function over a task. That is an optional later batch-generation mechanism, not required for the first agent-assisted pilot. Automatic proposals remain drafts regardless of confidence.

## Approve and export benchmark labels

For a **frozen benchmark set**, a person must inspect every included image before the labels become the answer key. Reviewing only issues the assistant flags is not sufficient: an unflagged missed object has no box or confidence score to inspect. The two tested detectors must not define their own uncorrected ground truth. Keep pilot annotation independent of YOLO26n/D-FINE-N predictions, resolve disagreements against the pixels, and freeze the reviewed labels before evaluating those models.

Later training-data preparation may use issue triage plus random audits of apparently clear frames, but record that reduced review level honestly. Such drafts do not satisfy the current benchmark converter's `--reviewed` contract.

Once all included frames have been human-reviewed:

1. Export **COCO 1.0** from CVAT and extract the downloaded archive locally. Object annotations must remain unrotated, ungrouped rectangles; masks, object polygons and per-object ignore flags are unsupported. The separate match-area polygon is supplied through `--scope`.
2. If a frame remains impossible to label reliably, document the reason and exclude the entire frame from the scored subset. Remove its COCO image entry and all referencing annotations. Deleting its boxes while leaving the image would falsely declare a negative.
3. Preserve reviewed empty images. An empty list means neither class is visible, not merely that the ball is absent.
4. Run the converter with a new output filename:

   ```sh
   uv run --locked python convert_cvat.py data/cvat-pilot-export/annotations/instances_default.json --manifest data/match-pilot-frames/manifest.json --scope data/main-pitch-scope.json --output data/match-pilot-labels.json --reviewed
   ```

`--reviewed` continues to mean **every included image was human-reviewed**, including images without boxes. It must never be supplied merely because an AI pass finished or all reported issues were resolved. The converter validates image/frame association and geometry, preserves negatives, and records omitted frame indices; it cannot certify completeness or inspect CVAT issue status. [Converter contract](architecture.md#annotation-preparation-contracts--version-1), [official COCO export](https://docs.cvat.ai/docs/dataset_management/formats/format-coco/).

Retain the source video, export manifest, original PNGs, CVAT backup, COCO export, reviewed scope file, review/exclusion record and converted labels in private storage. The example uses generic paths; the current pilot's scope is `data/football-clip-iqLnW_238X8-20261030/main-pitch-scope.json`. Both detector runs then use the same original video and reviewed label file, following the [benchmark protocol](benchmarking.md).

## Live checks and future changes

The synthetic setup task passed upload, original-pixel comparison, rectangle creation, targeted amendment while preserving another rectangle, issue creation/resolution/reopening, and COCO conversion with an empty frame retained. Repeat those checks after an SDK/server upgrade. Check the saved MCP allowlist and its read-only token; do not assume a working source checkout is a working configured connection.

Record the actual versions, IDs, commands and outcomes in [verification](verification.md). Do not describe source inspection, offline unit tests or container startup as proof of a completed labelling round trip. Manual review/issues are the planned Community workflow; paid-edition immediate feedback and quality analytics are not dependencies. [CVAT quality-control availability](https://docs.cvat.ai/docs/qa-analytics/quality-control/).
