# Reviewed match result version 1

**Status: implemented boundary, 30 October 2026.** This JSON format lets the Python pipeline and Flutter app exchange one reviewed match-result snapshot. It is separate from detector rows, CVAT box labels and processing-job status. The supplied [example](example.json) is fabricated test data; its video hash and clip references do not identify real media.

Version 1 carries two teams, a roster, confirmed goals, reviewed player counts and optional clip references. Only goals are event records in this version. Draft/rejected events remain in the review workspace; shots, passes, identity anchors, calibration, ratings and awards require their own later work. A reviewed snapshot can still cover only part of a match.

## Files and ownership

This directory is mirrored byte for byte in `p1-pipeline` and the Flutter `player1` repository. The pipeline copy owns the wire contract; changes must update both implementations and both copies together. [cases.json](cases.json) contains shared valid/invalid examples applied to [example.json](example.json). Both test suites execute the same cases and round-trip every accepted result.

Each repository can test without a sibling checkout. When both are present, run this additional parity check from `p1-pipeline`:

```sh
diff -ru contracts/match-result-v1 ../player1/contracts/match-result-v1
```

Standalone CI checks its local copy; it cannot prove the other repository has been updated. Keep the parity check in cross-repository reviews. The contract is defined here and enforced by the two validators; there is no separate JSON Schema engine or generated model dependency.

## Root fields

All listed fields are required. Unknown fields, missing fields, unsupported versions and duplicate JSON keys are rejected at every object boundary. Arrays contain objects with the exact fields described below. Empty `players`, `events` and `clips` arrays are allowed; `teams` must contain exactly two teams. Collection order is not identity and need not be chronological.

| Field | Type and meaning |
|---|---|
| `kind` | Exactly `reviewed_match_result`. |
| `schema_version` | Integer `1`; the wire format version, not a match revision. |
| `match_id` | Stable ID of the match this snapshot belongs to. |
| `revision` | Positive integer, increasing when this match's reviewed result changes. |
| `run_id` | ID of the export/review run. Links to producer evidence retained separately. |
| `producer` | Exactly `name` and `version`, both nonempty text. Identifies the producing tool/version. |
| `review` | Exactly `method`, `reviewer_id` and `reviewed_at`. See review rules below. |
| `video` | Exactly `sha256`, `duration_ms` and `source_start_ms`. Identifies the source and timeline. |
| `coverage` | Exactly `status` and `reviewed_intervals`. Defines what has actually been reviewed. |
| `teams` | Two objects, each with `id` and `name`. Array position does not imply home/away. |
| `players` | Roster objects, each with `id`, `name`, `team_id` and `stats`. |
| `events` | Confirmed goal objects. |
| `clips` | Optional prepared clip references; use an empty array when no clips are ready. |

IDs match `[A-Za-z0-9][A-Za-z0-9._:-]{0,127}`. IDs must be unique within each collection; a person's display name is not an ID and names may repeat. `team_id` references one of this snapshot's teams. Player IDs are match-roster identities, not proof of an account, permission or ownership.

Names and producer text contain 1–200 Unicode code points, no leading/trailing ASCII spaces and no U+0000–U+001F characters. JSON integers must be actual integers, not booleans, numeric strings or decimal literals such as `1.0`, and cannot exceed `9007199254740991`. Revisions start at one; counts start at zero. Millisecond values may be fractional, must be finite and have absolute value at most that same limit. NaN/Infinity and overflowed JSON numbers are rejected.

## Review and time

`review.method` is `human` or `ai_assisted`. Both assert a person reviewed the exported result; AI assistance alone does not qualify. `reviewer_id` is the reviewer's stable ID. `reviewed_at` is a real UTC calendar date/time in exactly `YYYY-MM-DDTHH:MM:SSZ` format, without fractions or timezone offsets. These fields record an assertion; parsing does not authenticate the reviewer or certify football accuracy.

`video.sha256` is the lowercase 64-character hash of the exact source video bytes. `duration_ms` is positive and includes the playable recording through its end, not just the last frame's start timestamp. `source_start_ms` is the first decoded frame's original presentation timestamp in milliseconds and may be negative. Use the decoder's time base; do not derive time from nominal FPS.

All event times and interval endpoints are milliseconds **relative to that first decoded frame**, matching the benchmark's `timestamp_ms`. Original source time equals `source_start_ms + timestamp_ms`. These are video times, not a match clock with halftime removed.

Each reviewed interval has exactly `start_ms` and `end_ms`, with `0 <= start_ms < end_ms <= duration_ms`. Intervals are half-open: start included, end excluded. They must be sorted and disjoint, with a gap between intervals; merge adjacent intervals before export. At least one interval is required. A goal must fall inside a reviewed interval. A clip may include unreviewed context around its confirmed goal, but must remain within the source video.

| Coverage status | Meaning |
|---|---|
| `partial` | The source is an incomplete match, review covers only some intervals, or completeness is uncertain. Reviewing the whole recording does not prove it contains the whole match. |
| `complete` | The reviewer asserts the recording covers the entire match and all goals have been reviewed. Requires one interval `[0, duration_ms)`. |

The validators enforce the interval rule for `complete`; they cannot establish from JSON whether the camera captured the entire match. A final score is available only for complete coverage. Python's `final_score(result)` and Dart's `result.finalScore` return team-ID goal counts, or `None`/`null` for partial coverage. They count own goals for the credited team. An explicitly reviewed complete match with no goals produces zero for both teams.

## Players and available counts

Each player has exactly `id`, `name`, `team_id` and `stats`. `stats` has exactly `goals`, `assists` and `saves`; each is a nonnegative integer or explicit `null`.

- A number describes reviewed contributions in the listed intervals. With partial coverage, even a known zero is only a zero within those intervals.
- `null` means unavailable, unassessed or unresolved. Do not default it to zero.
- Goals must agree with the confirmed, attributed non-own-goal events for that player. Own goals never increase the scorer's `goals` count.
- When a team has a confirmed normal goal with an unknown scorer, every roster member on that team must have `goals: null`; otherwise a claimed exact count could be wrong. Known attributed goals remain available as events.
- Assists and saves are human-reviewed aggregate counts in v1. The validator checks their type/range, not their football meaning; they have no separate event records yet. Leave them null until reviewed over the stated intervals.

An empty roster is valid while identities are unresolved; then all goal `player_id` values must be null. This does not prevent a team score from being known.

Shots, distance, speed, clean sheets, ratings, XP and Points are not fields in this version and remain unavailable. In Flutter, the new `ResultPlayerStats` preserves nulls. Do not pass it through the prototype's zero-default `GamePlayerStats` without an explicit availability-aware UI integration. No awards are issued by this format or its parser.

## Confirmed goals and clips

Each goal contains exactly:

| Field | Meaning |
|---|---|
| `id` | Stable event ID, retained when the same event is corrected. |
| `revision` | Positive event revision, no greater than the result revision. |
| `type` | Exactly `goal`. Every exported event is confirmed by the snapshot's review. |
| `timestamp_ms` | Time of the confirmed goal within a reviewed interval. |
| `team_id` | The team credited with the goal. Must be known. |
| `player_id` | Roster ID of the scorer, or null when attribution is unknown. |
| `own_goal` | Required boolean. A known scorer must belong to the credited team for a normal goal and the other team for an own goal. |

Uncertain team attribution remains outside the confirmed result and prevents a completeness claim until settled. Keep the original review evidence, including rejected candidates, separately. The video hash plus event time is the source evidence reference; a prepared clip is not mandatory.

Each clip contains exactly `id`, `event_id`, `start_ms`, `end_ms` and `media_ref`. The event must exist, and `start_ms <= event.timestamp_ms < end_ms`. Clips need a positive interval within the source video. Clip timestamps refer to the source, not the encoded clip's internal start time.

`media_ref` is an opaque relative key such as `clips/goal-1.mp4`, 1–512 ASCII characters. Each slash-separated segment starts with an ASCII letter/digit and continues with letters, digits, `.`, `_` or `-`. Absolute paths, URLs, backslashes, empty segments, traversal segments, query strings and fragments are rejected. Do not put tokens or signed URLs in results.

The consuming app/service will resolve keys against approved local storage or private object storage. Validation does not open paths, check files exist, prevent symlink escapes in a later resolver, authorise a download or prove clip content/encoding. Clips may have different IDs pointing to shared media if their event/interval associations are correct.

## Corrections and repeated delivery

This is a **full replacement snapshot for one match**, never a list of new awards to append. Preserve `match_id` and unchanged event IDs. Raise the result revision for a changed export, raise an event's revision when that event changes, and retain unchanged event revisions. Remove a rejected/retracted event from the newer snapshot and update dependent clips/counts. IDs must never be recycled for different events.

The future persistence/import layer must compare incoming results with stored state: an identical delivery at the same revision is a no-op; different contents at the same revision are a conflict; an older revision must not replace a newer one. A newer revision replaces the previous result and recomputes/reverses affected awards transactionally. Validate the video association and match access before accepting it.

The current validators check a single snapshot, including duplicate IDs, reference integrity and event/result revision bounds. They do **not** implement storage, historical revision checks, access control or idempotent awards. Reimports/corrections across snapshots need those tests when persistence is added.

## Producer and consumer usage

Python, from `p1-pipeline`:

```python
from pathlib import Path
from match_result import dumps_match_result, final_score, loads_match_result

result = loads_match_result(Path("contracts/match-result-v1/example.json").read_text())
assert final_score(result) is None  # This example covers only part of the match.
payload = dumps_match_result(result)  # Validates again before serialization.
```

`validate_match_result(dict)` returns its input unchanged after validation. Python dictionaries remain mutable; revalidate before using/sending changed data. The producer owns immutable output filenames and file-write failure handling, using the same rules as other pipeline outputs.

Dart, with the JSON text supplied by a later file/network integration:

```dart
import 'dart:convert';
import 'package:mps/models/match_result.dart';

final result = MatchResult.decode(payloadText);
final score = result.finalScore; // null for partial coverage
final goals = result.players.first.stats.goals; // int?; never default to zero
final serialized = jsonEncode(result.toJson());
```

Dart models and nested lists are immutable and detached from input maps. `toJson()` returns fresh maps/lists. `MatchResult.fromJson(Object?)` validates an already-decoded object; use `decode(text)` at a raw JSON boundary because a previous generic decode may already have discarded duplicate keys. Errors are `ValueError` in Python and `FormatException` in Dart.

## Tests and changes

From the respective repository roots:

```sh
# p1-pipeline
uv run --locked python -m unittest discover -s tests -p test_match_result.py -v

# player1
flutter test --no-pub test/match_result_test.dart
```

The shared corpus covers partial/complete results, reviewed zeroes, unknown identities, own goals, revisions, malformed types, missing/extra keys, invalid dates, unsafe numbers, interval boundaries, duplicate IDs/keys, broken references and unsafe clip keys. Language-specific tests also cover non-finite in-memory values, serialization, input mutation, Dart immutability and replacement-snapshot examples. Existing CI runs these tests automatically with the full suites.

Any change to accepted fields or their meaning requires a new schema version and coordinated producer/consumer rollout; do not silently extend strict v1. Add matching fixtures for new acceptance/failure cases. Keep documentation-only clarification within v1 when it changes no behavior.

This milestone establishes the data boundary. Real video selection, result-file import, match storage, media playback, screen wiring, event generation and award application remain separate implementation work.
