# First real reviewed-result handoff

**31 October 2026 — prepared and validated.** The development recording now has a private, portable version-1 result bundle. It contains the three human-confirmed goals and their existing replay clips. Both the Python validator and the Flutter app's existing Dart parser accept the exact result. This is an assisted, partially reviewed result, not automatic goal detection or a working app import/playback flow.

## Contents and meaning

The immutable local revision is under `data/football-clip-iqLnW_238X8-20261030/reviewed-result-r1-20261031/`. Its `bundle/` contains `result.json`, `README.md`, and `clips/G01.mp4`, `clips/G09.mp4`, `clips/G10.mp4`. The sibling `player1-reviewed-result-r1.zip` packages those five files, with relative media references preserved. The original full recording is not duplicated in the bundle; its SHA-256 and video timeline identify it.

| Event | Source review anchor | Credited team | Scorer | Replay source interval |
| --- | --- | --- | --- | --- |
| G10 | 1:01.72 / frame 1543 | Red | Unknown (`null`) | 0:58–1:08 |
| G01 | 2:47.88 / frame 4197 | Blue | B1 | 2:42–2:56 |
| G09 | 4:31.52 / frame 6788 | Blue | B1 | 4:26–4:38 |

These timestamps are existing review anchors verified against exact source PTS, not measured whole-ball crossing instants. Event IDs retain discovery order; the file lists them chronologically. The nine rejected candidates remain in CVAT and the provenance ledger, and are absent from the confirmed-event result. Normal goal credit follows the supplied scoring decisions and reviewed sequences; no own goal was reported.

Coverage is **partial**, comprising the twelve human-adjudicated replay windows: 193 seconds of the 494-second video. The AI-sampled gaps do not become human-reviewed intervals. Neither the recording nor the review establishes whole-match completeness. Python `final_score` and Dart `finalScore` therefore return `None`/`null`. Blue 2 / Red 1 is a count of confirmed events only; consumers must not label it the final score or derive a winner.

The roster contains the user's numbered aliases R1–R6 and B1–B6, with display names such as “Blue 1”. These are not verified account identities, tracked trajectories or approved image anchors. Only B1's two attributed goals are recorded as a player count. Other goal counts, all assists and all saves remain `null`; no missing count becomes zero. Red player goal counts must remain unavailable while G10's scorer is unknown. The goal review does not establish complete goalkeeper statistics, ratings, XP or Points.

The review method is `ai_assisted`: a person supplied the decisions, and the assistant prepared the export. `local-match-owner` is a stable local reviewer pseudonym, not an authenticated CVAT account. `reviewed_at` records the latest stored human event-decision receipt, rounded down to whole seconds; it is not export time or a claim about the exact moment the footage was watched. The private provenance retains the decision text and original receipt timestamps. Acceptance of goal geometry is separate from this result; v1 does not carry goal polygons or calibration.

## Reproduce verification

Run from the pipeline repository after extracting the bundle or using its existing directory:

    .venv/bin/python - <<'PY'
    from pathlib import Path
    from match_result import loads_match_result, final_score
    root = Path('data/football-clip-iqLnW_238X8-20261030/reviewed-result-r1-20261031/bundle')
    result = loads_match_result((root / 'result.json').read_text())
    assert final_score(result) is None
    assert {e['id'] for e in result['events']} == {'G01', 'G09', 'G10'}
    assert all((root / c['media_ref']).is_file() for c in result['clips'])
    PY

This prepared local package is trusted development evidence. The existence check above is not a general safe archive importer or path/symlink resolver. A production importer needs its own validation and tests.

The preparation operation and direct Dart consumer check are retained under the private revision's `operations/`. This is a reviewed export of one recording, not a new reusable CLI or automatic CVAT-to-result publisher. Existing production validators and the mirrored [v1 contract](../contracts/match-result-v1/README.md) are unchanged. Future exports must use new revision directories; retain the stable match/event IDs and follow the contract's correction rules.

Checks completed for this bundle:

- Source SHA-256, exact first/last frame PTS, event-anchor PTS and final-frame duration agree with the 494,000 ms video timeline. The slightly longer audio/container duration is not used.
- Three clips are unchanged copies of frozen replays: 900 frames / 36 seconds total, silent H.264 at 2560×1440. Every copied frame's dimensions and playback PTS were verified.
- Python and Dart parse/serialize the real result without changing identity, coverage, unavailable statistics or clip references. Both return no final score.
- Existing Python contract tests pass (six test methods, including the shared conformance corpus); all 313 focused Flutter contract tests pass. No new production code, dependencies or schema change was needed.
- Contract mirrors, prior frozen artifacts, CVAT annotation preservation, package hashes, documentation links and whitespace are checked separately in the revision's verification record.

## Next app work, in order

1. Import a user-selected local result package and validate its JSON before storing anything. Resolve clip keys inside the selected package; handle missing files, unsafe archive entries/symlinks, cancellation and interrupted copying.
2. Persist a match's full replacement snapshot and durable local media. Identical reimport must be a no-op, older revisions rejected, same-revision conflicts surfaced and newer corrections applied without duplicate contributions.
3. Pass the real `MatchResult` into the existing analysis screens. Show “reviewed goals” and partial coverage, “unknown scorer” for G10, and unavailable statistics explicitly. Preserve the original roster aliases; do not treat them as logged-in users.
4. Add clip playback. Inside a replay, seek to `event.timestamp_ms - clip.start_ms`; the full video's timestamps must not be used as clip-local offsets. Handle loading, failure, disposal and app restart.
5. Verify import, reopen, playback, duplicate import and correction on supported devices. Original-video selection, saved identity anchors and wider review can build on that path. Awards remain separate until correction-safe persistence and the applicable contribution rules are implemented.

The [technical plan](../../player1/docs/player1_technical_plan.md) owns milestone ordering. Human continuous-clip review, an optional G10 scorer identification, varied training/held-out matches and temporal detection evaluation remain independent work. The existing [goal-review record](goal-review.md) and detector comparisons are preserved.
