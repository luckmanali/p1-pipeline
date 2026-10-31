import copy
import json
import math
from pathlib import Path
import unittest

from match_result import dumps_match_result, final_score, loads_match_result, validate_match_result


CONTRACT = Path(__file__).resolve().parents[1] / "contracts" / "match-result-v1"


def case_text(case, example):
    if "raw" in case:
        return case["raw"]
    data = copy.deepcopy(example)
    for change in case["changes"]:
        target = data
        for key in change["path"][:-1]:
            target = target[key]
        key = change["path"][-1]
        if change.get("remove"):
            del target[key]
        else:
            target[key] = copy.deepcopy(change["value"])
    return json.dumps(data, allow_nan=False)


class MatchResultTests(unittest.TestCase):
    def setUp(self):
        self.example = json.loads((CONTRACT / "example.json").read_text())

    def test_shared_python_dart_conformance_cases(self):
        corpus = json.loads((CONTRACT / "cases.json").read_text())
        self.assertEqual(corpus["schema_version"], 1)
        names = [case["name"] for case in corpus["cases"]]
        self.assertEqual(len(names), len(set(names)))
        for case in corpus["cases"]:
            with self.subTest(case=case["name"]):
                text = case_text(case, self.example)
                if case["valid"]:
                    result = loads_match_result(text)
                    self.assertEqual(result, json.loads(text))
                    self.assertEqual(loads_match_result(dumps_match_result(result)), result)
                    self.assertEqual(final_score(result), case["final_score"])
                else:
                    with self.assertRaises(ValueError):
                        loads_match_result(text)

    def test_unknown_is_not_zero_and_timestamps_keep_fractional_source_offset(self):
        result = loads_match_result((CONTRACT / "example.json").read_bytes())
        self.assertEqual(result["players"][1]["stats"]["goals"], 0)
        self.assertIsNone(result["players"][2]["stats"]["goals"])
        self.assertIsNone(result["players"][0]["stats"]["assists"])
        self.assertEqual(result["video"]["source_start_ms"] + result["events"][0]["timestamp_ms"],
                         11500.25)
        self.assertIsNone(final_score(result))

    def test_in_memory_non_finite_values_cannot_be_validated_or_serialized(self):
        for bad in (math.nan, math.inf, -math.inf, 10 ** 400):
            for path in (("video", "duration_ms"), ("video", "source_start_ms"),
                         ("events", 0, "timestamp_ms"), ("clips", 0, "start_ms")):
                with self.subTest(value=bad, path=path):
                    data = copy.deepcopy(self.example)
                    target = data
                    for key in path[:-1]:
                        target = target[key]
                    target[path[-1]] = bad
                    for validate in (validate_match_result, dumps_match_result, final_score):
                        with self.assertRaises(ValueError):
                            validate(data)

    def test_validation_and_score_do_not_mutate_the_input(self):
        original = copy.deepcopy(self.example)
        self.assertIs(validate_match_result(self.example), self.example)
        dumps_match_result(self.example)
        final_score(self.example)
        self.assertEqual(self.example, original)

    def test_serialization_revalidates_a_changed_dictionary(self):
        result = validate_match_result(self.example)
        result["players"][0]["stats"]["goals"] = 100
        with self.assertRaisesRegex(ValueError, "disagree"):
            dumps_match_result(result)

    def test_corrected_snapshot_removes_an_event_without_changing_other_ids(self):
        corrected = copy.deepcopy(self.example)
        corrected["revision"] = 2
        corrected["run_id"] = "review-example-2"
        corrected["events"].pop(0)
        corrected["clips"].pop(0)
        corrected["players"][0]["stats"]["goals"] = 0
        parsed = loads_match_result(dumps_match_result(corrected))
        self.assertEqual(parsed["match_id"], self.example["match_id"])
        self.assertEqual([e["id"] for e in parsed["events"]], ["goal-2", "goal-3"])
        self.assertEqual(parsed["events"][0]["revision"], 1)
        self.assertEqual(parsed["revision"], 2)


if __name__ == "__main__":
    unittest.main()
