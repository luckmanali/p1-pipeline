# Goal geometry and event review

Updated 31 October 2026. [CVAT task 4/job 4](http://localhost:8080/tasks/4/jobs/4) contains the **full 8:14 development clip**, four goal tracks and twelve event tags. The user confirmed **G01 and G09 for Blue 1 (B1)** and **G10 for Red, scorer unknown**, and rejected the other nine candidates. G11 contains a first shot off the post and a second saved by the goalkeeper; G12 was also saved. **All twelve event issues are resolved; no event decisions remain pending.** **Both near and far goal geometry are now user-corrected/accepted, and all fourteen geometry/event issues are resolved.** The near mouth bottom edge matches the user's manually corrected yellow line exactly. The job remains validation/in progress; sampled search does not certify exhaustive event coverage or a final score. Tasks 2/3 and frozen detector comparisons are unchanged.

This is assisted review of original footage, not automatic goal detection, ball tracking, scorer identification or pitch calibration. The [general CVAT guide](cvat-reviewer-guide.md) covers login, navigation, saving and issue comments.

## What the markings mean

| Label | Meaning | Review |
| --- | --- | --- |
| `goal_mouth` | Cyan four-corner outline of the opening between the posts/crossbar and ground. | Check the opening, not the back/side net. |
| `goal_line` | Yellow line joining the two post-ground endpoints. | Check both feet; this is not the penalty arc or back of the net. |
| `goal_candidate` | Pink tag at a replay anchor, with event ID and decision fields. | A bookmark, not a confirmed goal or exact crossing time. |

Geometry has `goal_id=near/far` and `review_status=draft/accepted/uncertain`. All tracks remain visible through frame 12,349. The accepted near-goal tracks have one keyframe at frame 0; correcting that keyframe adjusts the position throughout this recording. Editing later creates another keyframe and changes interpolation. Keep the polygon's bottom corners and line endpoints consistent.

**Far-goal correction, 31 October:** the user's saved mouth/line edits are at source frames 87 and 4208. Both manual keyframes were preserved exactly. The assistant copied the earliest correction to frame 0 so the clip starts with the corrected geometry, then marked the two far tracks accepted and resolved issue 88. CVAT interpolates between frames 87 and 4208 and extends the last keyframe to the end. Do not replace these tracks with the original draft or assume a later edit automatically changes earlier frames. This acceptance covers the far geometry only; it does not approve event decisions, near geometry, identities or complete clip coverage.

**Near-goal human correction, 31 October:** the user manually corrected the yellow line and the corresponding cyan corner at frame 0, then resolved issue 87 and reported “I fixed it”. These edits were initially pending in the browser; the assistant saved them before making any API update. The exact user line is (170.20000000000073, 524.9000000000015) to (264, 730) in the original 2560×1440 image. Its coordinates were preserved exactly. The mouth's matching corner was moved from the user's approximately (171.4, 527.7) to the line endpoint (about 3 pixels), so both lower corners now agree. Upper mouth corners (155, 343) / (235, 466) are unchanged. Both near tracks are accepted; issue 87 remains resolved by the user. Source overlays at frames 0, 10000 and 12349 were visually checked. Single visible frame-0 keyframes extend the same geometry throughout frames 0–12349, with no extra interpolation keyframes.

The original hidden-post estimate (175, 610) and assistant revision (174, 554) are superseded. Their frozen evidence remains historical. The opening is viewed through the side net, so the physical occlusion flags remain true even though the image annotations are reviewed. Acceptance records the user's correction; it does not make an obscured endpoint directly visible, establish measured three-dimensional geometry or prove that the whole ball crossed a physical line.

### Manually correct the goal line

Choose **Standard**, enter frame **0**, and select the near **goal_line** in Objects (shown as UI object 14 in this session; identify it by label and goal_id, not a permanent UI number). Unlock it if necessary, then drag each endpoint onto the corresponding post-ground contact. Temporarily hide the cyan **goal_mouth** with its eye icon if selection overlaps. Use Undo for an accidental whole-line move. Click **Save** before handing the job back; resolving an issue saves the discussion state separately and does not save pending geometry edits.

The mouth's bottom corners must then match the corrected line endpoints exactly. The assistant can align those corners after reading back the user's saved line, preserving every other vertex/keyframe. For this fixed-camera near goal, editing frame 0 avoids adding an unintended later keyframe. Review status and issue resolution should record the actual human correction, while occlusion flags continue to describe visibility. Keep before/after evidence and verify unrelated annotations are unchanged.

## Review the event windows

Choose **Standard** in the top-right workspace selector to amend annotations; Review mode locks editing. Enter a frame number in the top frame field and press Enter. Use **Issues** to find each question. At its anchor frame, open **Objects → goal_candidate → Details** to edit its decision.

The first shortlist came from 247 two-second previews plus selected denser crops. After the user adjudicated those eight windows, the assistant searched their 342-second complement using 692 approximately 2 fps previews, 399 original-pixel 5 fps crops across 27 selected windows, and 146 consecutive source frames across eight critical moments. All generated sheets were visually inspected. This completes an **AI sampled pass**, not exhaustive all-frame viewing or human approval of the remainder. Replay clips preserve every source frame in each window. Times are video-relative, not a match clock.

| ID | Replay window | Anchor frame | Decision / evidence |
| --- | --- | ---: | --- |
| G01 | 2:42–2:56 | 4197 | **Human confirmed:** Blue team player 1 (B1), using the user's numbered reference screenshot. Near-goal event around 2:47.8; frame 4197 / 167.88s is a review anchor, not an exact whole-ball crossing measurement. Issue 89 resolved. |
| G02 | 3:04–3:26 | 4750 | **Human rejected:** the user confirmed no goal in 3:04–3:26. Issue 90 resolved. |
| G03 | 3:32–3:46 | 5500 | **Human rejected:** the user confirmed no goal in 3:32–3:46. Issue 91 resolved. |
| G04 | 4:40–5:02 | 7375 | **Human rejected:** the user confirmed there is no goal in this window. Issue 92 resolved. |
| G05 | 5:18–5:42 | 8100 | **Human rejected:** the user confirmed no goal in 5:18–5:42. Issue 93 resolved. |
| G06 | 6:50–7:06 | 10403 | **Human rejected:** “No, it did not count.” Dense inspection found a high attempt/rebound around 6:54, then a follow-up volley around 6:55.7–6:55.8 and apparent net entry around 6:56.1. Marker moved from 10360 to 10403 to review that follow-up. No goal credited; reason unspecified. Issue 94 resolved. |
| G07 | 7:10–7:32 | 11050 | **Human rejected:** the user confirmed there is no goal in this window. Issue 95 resolved. |
| G08 | 7:56–8:14 | 12130 | **Human rejected:** the user confirmed no goal in 7:56–8:14. Issue 96 resolved. |
| G09 | 4:26–4:38 | 6788 | **Human confirmed:** Blue team player 1 (B1) scored. Near-goal event around 4:31.5; preserved anchor 6788 / 271.52s is not an exact crossing measurement. Issue 97 resolved. |
| G10 | 0:58–1:08 | 1543 | **Human confirmed:** Red team scored near the far goal around 1:01.7. Scorer not supplied; retain `unknown`. Issue 98 resolved. |
| G11 | 1:39–1:51 | 2615 | **Human rejected:** first shot hit the post; second shot was saved by the goalkeeper. Both attempts remain in the notes; neither counted as a goal. Issue 99 resolved. |
| G12 | 6:42–6:49 | 10149 | **Human rejected:** saved by the goalkeeper; no goal. Issue 100 resolved. |

These are **twelve review windows, not twelve goals**: three human-confirmed, nine human-rejected and none pending. Recorded confirmed events total **Blue 2, Red 1**, with both Blue goals credited to B1 and the Red scorer unknown. This is a tally of reviewed events, **not a final match score**. The G11/G12 explanations do not create complete shot or goalkeeper-save statistics; those need their own event definitions and coverage review. IDs retain discovery order rather than chronological order. G06 demonstrates why apparent entry/net retrieval is insufficient to decide whether an event counts under the game's rules. Do not invent a high-ball violation, foul or other rejection reason when none was supplied.

1. Watch the lead-up and aftermath, then step through important frames. Follow the playing ball rather than the spare on the near net. Distinguish saves, wall rebounds, balls over/behind the net and valid goals under this game's rules. A still showing a ball inside the net is insufficient on its own.
2. Set the tag's `decision` to `confirmed`, `rejected` or `uncertain`; keep `pending` if unreviewed. Preserve `event_id`. Record the actual event frame/time in `notes` if the anchor needs correction; the assistant can then move the tag with a targeted update. One window may contain multiple events: note each separately.
3. Set `team_id` and `scorer_id` only when established. `red`/`blue` mean the user's numbered teams, not clothing colour; kits are mixed. Leave identities unknown when uncertain. Adjudicate own-goal credit separately before creating a result.
4. **Save** annotations. Comment on the issue with your decision/evidence and resolve it once settled. Keep unresolved visibility/rule questions open. Resolving an issue alone does not update its tag or establish complete clip coverage.

All twelve candidate windows now have explicit user decisions. The remaining footage has an AI sampled search, not exhaustive human review. G10 scorer identification is still optional work; an unknown scorer is allowed in the reviewed-result contract. The three confirmed events now appear in the first [partial reviewed-result bundle](reviewed-result-handoff.md), with explicit coverage limits and unchanged replay media. The goal-geometry review is now settled; image annotations remain subject to the visibility and calibration limits above. Human continuous-clip review is still needed before asserting all clip goals have been found: sparse previews can miss fast or occluded events, even after targeted 25 fps checks. Neither this 8:14 excerpt nor the search establishes whole-match completeness or a final score.

## Evidence and reproducible clips

Private artifacts are under `data/football-clip-iqLnW_238X8-20261030/goal-review-v1-20261030/`:

- `draft-events.json`, `geometry-draft.json`: proposals, uncertainty and source association, separate from published match results.
- `review.html`, `README.md`: local replay index/handover; `clips/G01.mp4` through `G08.mp4` are silent full-resolution H.264 review copies.
- `clips/manifest.json`, `clip-readback.json`: source/output hashes, exact ranges, timestamps, encoding and decoded-output verification.
- `inspection/`: timestamped preview/crop sheets and sampling provenance. No detector predictions were used to assert goals or geometry.
- CVAT intake, requests/read-backs, issue receipts, source-task snapshots and `integrity.json`: traceability/preservation checks. Credentials are excluded.

The original draft artifacts are frozen. The subsequent far-goal correction has its own private `goal-review-far-correction-20261031/` directory alongside them: user-review context, before/after annotations, targeted request, issue/comment read-backs and verification. Keep both revisions; the original draft's review counts are historical.

`goal-review-evidence-v2-20261031/` retains the subsequent near-goal/G01/G06 inspection, original-pixel crops with exact source PTS, the user's two decision replies, narrow annotation update and read-back checks. G06's original issue remains at frame 10360 for context; its event tag is now at 10403. The old AI assessment and earlier draft marker remain in the frozen first revision. Rejected G06 stays in the review evidence and must be excluded from any confirmed-goal export.

`goal-review-negatives-v3-20261031/` retains the subsequent user decisions that G04 (4:40–5:02) and G07 (7:10–7:32) contain no goal. Only their decision/notes fields and issues 92/95 changed; anchors, identities, all geometry and other decisions were preserved. Rejected G04/G06/G07 remain review evidence and are excluded from confirmed-goal exports. Earlier revisions remain frozen.

`goal-review-decisions-v4-20261031/` retains the user's final four no-goal decisions for G02/G03/G05/G08, targeted tag updates and resolved issues 90/91/93/96. Read-back verifies all geometry, anchors, identities and other decisions unchanged. The event shortlist is fully adjudicated; near geometry and complete clip coverage remain unresolved. All seven rejected candidates are excluded from confirmed-goal exports.

`goal-coverage-v5-20261031/` retains the subsequent search outside G01–G08. The prior windows cover 152 seconds; their complement is 342 seconds. `coverage-review.json` records all eight remaining ranges, the inspected sheets and 27 detailed observations. Twenty-three detailed windows produced no additional candidate; this is an AI search outcome, not human-certified negative ground truth. Four produced pending questions G09–G12. `overview/`, `dense/` and `critical/` retain timestamped evidence; critical crops also have lossless source-pixel PNGs. No AI enhancement or detector predictions were used. Original-frame inspection matters because compressed replay copies can obscure small details.

The four new replays are `clips/G09.mp4`, `far-clips/G10.mp4`, `far-clips/G11.mp4` and `save-clips/G12.mp4` in that revision. Their manifests and decoded read-back checks preserve source/output hashes and all 1,025 frames (41 seconds). Targeted official-SDK creation added only four tags and issues 97–100; exact read-back verified all previous annotations, issue records and detector-task labels unchanged. The private README provides replay links and the full observation ledger. All earlier revisions remain frozen. Coverage search and event adjudication are separate: decoding every source frame verifies timing, not that every frame was visually reviewed.

`goal-review-decisions-v6-20261031/` retains the subsequent explicit user adjudication of G09–G12. Targeted updates changed only their decision/notes fields and the supplied G09/G10 team/scorer fields. Issues 97–100 received the quoted decisions and were resolved. Exact read-back verified all other annotations, anchors, geometry, prior comments and detector-task labels preserved. G10 remains scorer-unknown; no identity was guessed. The independent read-only MCP confirmed three confirmed and nine rejected tags, with no pending tags. The v5 evidence remains frozen as the original proposal/search record; its pending statuses are historical.

`near-goal-correction-v7-20261031/` retains the user's geometry objection, ten exact-PTS source crops, a previous/revised overlay, the two-track targeted request, before/after annotations and preservation checks. Only the hidden-endpoint coordinates and near-track provenance changed; far tracks, twelve event tags and detector tasks 2/3 were preserved exactly. Issue 87 received an explanation and remains open. Earlier revisions retain their historical geometry.

The private revision **near-goal-human-correction-v8-20261031/** retains the server state before saving the pending browser edits, the saved human correction, the narrow mouth-alignment/status update and exact read-back. The user's line endpoints and issue resolution were preserved; only the small mouth-corner alignment and two review-status fields were subsequently changed. All far keyframes, twelve event tags, previous comments and detector-task 2/3 annotations remain unchanged. Source overlays at the start, near the end and final frame, live CVAT screenshot, documentation delta and integrity manifest complete the record.

CVAT received the original **2560×1440, 25 fps** video without frame filtering. Here **CVAT frame index equals original decoded index**: frame 4197 is 167.88 seconds. Tasks 2/3 instead map CVAT frame 14 to source frame 4200. Native annotation evidence does not change the separate 1080p detector experiment. CVAT browser previews use quality 90; original video/native crops remain available for ambiguous details.

The reusable exporter needs no extra dependency or CVAT account. Example windows file:

```json
[
  {"id": "G01", "start_frame": 4050, "stop_frame": 4400},
  {"id": "G06", "start_frame": 10250, "stop_frame": 10650}
]
```

Save that JSON locally, then run:

```sh
uv run --locked python export_review_clips.py data/match.mp4 \
  --windows data/review-windows.json --output data/review-clips-v1 --fps 25
```

Ranges are **start-inclusive, stop-exclusive**, ordered and non-overlapping; merge overlaps. IDs must be unique safe filenames, including on case-insensitive filesystems. The exporter streams source frames once, verifies their presentation timestamps against the supplied integer FPS and writes native-size MP4s with zero-based playback time. Its manifest maps clips to original frames/source time. It rejects fractional-rate/VFR input, odd dimensions and within-clip size changes rather than retiming/resizing evidence. Supported integer rates are 1–240; this is a limited review utility, not the app's general media pipeline.

Output must be a new directory. Decoder/encoder errors, incomplete windows and interruption leave a failed manifest; partial files are not complete clips. Retry into a new directory after diagnosis. These lossy CRF-18, silent copies are not substitutes for original frames in detector scoring or precise geometry inspection. Exporting clips never asserts human review or publishes a result.

## After adjudication

The first [reviewed revision and app handoff](reviewed-result-handoff.md) is now prepared and validated in Python and Dart. It contains three confirmed events, nine excluded rejected candidates, partial coverage and three replay clips. Future corrections must create a new result revision with preserved stable IDs. Read back saved tags, geometry and comments before each export. Resolve scorer/credited-team questions separately from whether a goal occurred. Only confirmed events with established team credit belong in [reviewed match-result v1](../contracts/match-result-v1/README.md); unknown scorers are allowed, but unresolved events/teams remain outside it. Retain explicit partial coverage and unavailable statistics. The contract and Flutter parser exist; actual result import into screens, persistence and playback remain the next integration work.
