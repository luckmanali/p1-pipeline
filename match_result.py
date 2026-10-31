"""Validate the version 1 reviewed match-result handoff to Flutter.

This boundary does not infer events, authenticate reviewers or award Points.
See contracts/match-result-v1/README.md for the wire contract.
"""

from datetime import datetime
import json
import re

from evaluate import _integer, _json, _number, _require, _sha256


MAX_SAFE_INTEGER = 9007199254740991


def _object(value, fields, context):
    _require(isinstance(value, dict) and set(value) == set(fields.split()),
             f"{context}: expected exactly {fields}")
    return value


def _text(value, context):
    _require(isinstance(value, str) and 0 < len(value) <= 200
             and value == value.strip(" ") and not any(ord(c) < 32 for c in value),
             f"{context}: expected nonempty text without control characters")


def _id(value, context):
    _require(isinstance(value, str)
             and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", value) is not None,
             f"{context}: invalid ID")


def _count(value, context, minimum=0):
    _require(_integer(value, minimum) and value <= MAX_SAFE_INTEGER,
             f"{context}: expected integer in [{minimum}, {MAX_SAFE_INTEGER}]")


def _time(value, context):
    _require(_number(value) and abs(value) <= MAX_SAFE_INTEGER,
             f"{context}: expected finite milliseconds in the safe numeric range")


def _period(value, duration, context):
    _object(value, "start_ms end_ms", context)
    _time(value["start_ms"], context)
    _time(value["end_ms"], context)
    _require(0 <= value["start_ms"] < value["end_ms"] <= duration,
             f"{context}: expected 0 <= start_ms < end_ms <= video duration")


def _index(value, fields, context):
    _require(isinstance(value, list), f"{context}: expected array")
    indexed = {}
    for item in value:
        _object(item, fields, context)
        _id(item["id"], context)
        _require(item["id"] not in indexed, f"{context}: duplicate ID {item['id']}")
        indexed[item["id"]] = item
    return indexed


def validate_match_result(value):
    """Return the input unchanged after structural and semantic validation.

    Values are JSON objects; bools are never counts/timestamps. Null statistics
    remain unavailable. Call again after mutating a validated Python dictionary.
    """
    _object(value, "kind schema_version match_id revision run_id producer review video "
            "coverage teams players events clips", "result")
    _require(value["kind"] == "reviewed_match_result", "Unsupported result kind")
    _require(type(value["schema_version"]) is int and value["schema_version"] == 1,
             "Unsupported result schema_version")
    _id(value["match_id"], "match_id")
    _id(value["run_id"], "run_id")
    _count(value["revision"], "revision", 1)
    producer = _object(value["producer"], "name version", "producer")
    for key in producer:
        _text(producer[key], f"producer.{key}")
    review = _object(value["review"], "method reviewer_id reviewed_at", "review")
    _require(review["method"] in ("human", "ai_assisted"), "Invalid review method")
    _id(review["reviewer_id"], "reviewer_id")
    date = review["reviewed_at"]
    _require(isinstance(date, str) and re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", date) is not None,
        "reviewed_at: expected UTC YYYY-MM-DDTHH:MM:SSZ")
    datetime.strptime(date, "%Y-%m-%dT%H:%M:%SZ")

    video = _object(value["video"], "sha256 duration_ms source_start_ms", "video")
    _require(_sha256(video["sha256"]), "video.sha256: expected lowercase SHA-256")
    _time(video["duration_ms"], "duration_ms")
    _require(video["duration_ms"] > 0, "duration_ms must be positive")
    _time(video["source_start_ms"], "source_start_ms")
    duration = video["duration_ms"]
    coverage = _object(value["coverage"], "status reviewed_intervals", "coverage")
    _require(coverage["status"] in ("partial", "complete"), "Invalid coverage status")
    periods = coverage["reviewed_intervals"]
    _require(isinstance(periods, list) and periods, "At least one reviewed interval required")
    previous_end = -1
    for period in periods:
        _period(period, duration, "reviewed interval")
        _require(period["start_ms"] > previous_end,
                 "Reviewed intervals must be sorted, disjoint; merge adjacent intervals")
        previous_end = period["end_ms"]
    if coverage["status"] == "complete":
        _require(len(periods) == 1 and periods[0]["start_ms"] == 0
                 and periods[0]["end_ms"] == duration,
                 "Complete coverage requires review of the entire recording")

    teams = _index(value["teams"], "id name", "teams")
    _require(len(teams) == 2, "Exactly two teams required")
    for team in teams.values():
        _text(team["name"], "team.name")
    players = _index(value["players"], "id name team_id stats", "players")
    for player in players.values():
        _text(player["name"], "player.name")
        _id(player["team_id"], "player.team_id")
        _require(player["team_id"] in teams, "Unknown player team_id")
        _object(player["stats"], "goals assists saves", "player.stats")
        for key, count in player["stats"].items():
            if count is not None:
                _count(count, f"player.stats.{key}")

    events = _index(value["events"], "id revision type timestamp_ms team_id player_id own_goal",
                    "events")
    goals = dict.fromkeys(players, 0)
    unknown_scorer_teams = set()
    for event in events.values():
        _count(event["revision"], "event.revision", 1)
        _require(event["revision"] <= value["revision"], "Event revision exceeds result revision")
        _require(event["type"] == "goal", "v1 supports confirmed goal events only")
        _time(event["timestamp_ms"], "event.timestamp_ms")
        _require(any(p["start_ms"] <= event["timestamp_ms"] < p["end_ms"] for p in periods),
                 "Event must lie within a reviewed interval")
        _id(event["team_id"], "event.team_id")
        _require(event["team_id"] in teams, "Unknown event team_id")
        _require(type(event["own_goal"]) is bool, "own_goal must be boolean")
        player_id = event["player_id"]
        if player_id is None:
            if not event["own_goal"]:
                unknown_scorer_teams.add(event["team_id"])
        else:
            _id(player_id, "event.player_id")
            _require(player_id in players, "Unknown event player_id")
            same_team = players[player_id]["team_id"] == event["team_id"]
            _require(same_team != event["own_goal"], "Scorer team conflicts with own_goal")
            if not event["own_goal"]:
                goals[player_id] += 1
    for player_id, player in players.items():
        count = player["stats"]["goals"]
        if count is not None:
            _require(player["team_id"] not in unknown_scorer_teams,
                     "Player goals must be null when their team has an unknown scorer")
            _require(count == goals[player_id], "Player goals disagree with confirmed events")

    clips = _index(value["clips"], "id event_id start_ms end_ms media_ref", "clips")
    for clip in clips.values():
        _id(clip["event_id"], "clip.event_id")
        _require(clip["event_id"] in events, "Unknown clip event_id")
        _period({key: clip[key] for key in ("start_ms", "end_ms")}, duration, "clip")
        _require(clip["start_ms"] <= events[clip["event_id"]]["timestamp_ms"] < clip["end_ms"],
                 "Clip must contain its event timestamp")
        ref = clip["media_ref"]
        _require(isinstance(ref, str) and len(ref) <= 512 and re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9._-]*(?:/[A-Za-z0-9][A-Za-z0-9._-]*)*", ref) is not None,
            "media_ref must be a relative media key, not a URL or filesystem traversal")
    return value


def loads_match_result(text):
    """Parse strict JSON and validate, rejecting duplicate keys/non-finite numbers."""
    return validate_match_result(_json(text))


def dumps_match_result(value):
    """Validate before serialization; caller owns file lifecycle and access control."""
    return json.dumps(validate_match_result(value), indent=2, allow_nan=False) + "\n"


def final_score(value):
    """Return team-ID counts only for an explicitly complete reviewed match."""
    validate_match_result(value)
    if value["coverage"]["status"] != "complete":
        return None
    score = {team["id"]: 0 for team in value["teams"]}
    for event in value["events"]:
        score[event["team_id"]] += 1
    return score
