import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from evaluate import box_iou, evaluate, in_scope, validate_scope


class EvaluateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.manifest = {
            "schema_version": 1, "status": "completed", "video": {"sha256": "a" * 64},
            "sampling": {"stride": 1, "max_frames": None}, "model": {"name": "test"},
            "inference": {"confidence": 0.05},
        }
        self.annotation = {"class": "player", "bbox": [0.1, 0.1, 0.5, 0.5]}
        self.detection = {**self.annotation, "confidence": 0.9}
        self.frames = [{
            "frame_index": 0, "timestamp_ms": 0, "width": 1920, "height": 1080,
            "detections": [self.detection],
        }]
        self.labels = {
            "schema_version": 1, "video_sha256": "a" * 64,
            "frames": [{"frame_index": 0, "annotations": [self.annotation]}],
        }

    def write_inputs(self):
        (self.root / "manifest.json").write_text(json.dumps(self.manifest))
        (self.root / "detections.jsonl").write_text(
            "".join(json.dumps(frame) + "\n" for frame in self.frames)
        )
        labels_path = self.root / "labels.json"
        labels_path.write_text(json.dumps(self.labels))
        return labels_path

    def run_evaluation(self, **kwargs):
        labels_path = self.write_inputs()
        return evaluate(self.root, labels_path, **kwargs)

    def run_cli(self, *arguments):
        script = Path(__file__).resolve().parents[1] / "evaluate.py"
        return subprocess.run(
            [sys.executable, str(script), str(self.root), "--labels",
             str(self.root / "labels.json"), *arguments],
            capture_output=True, text=True, timeout=10,
        )

    def test_perfect_match_and_provenance(self):
        report = self.run_evaluation()
        self.assertEqual(report["classes"]["player"], {
            "tp": 1, "fp": 0, "fn": 0, "precision": 1, "recall": 1,
        })
        self.assertEqual(report["classes"]["football"]["precision"], None)
        self.assertEqual(report["classes"]["football"]["recall"], None)
        self.assertEqual(report["labels_sha256"], hashlib.sha256(
            (self.root / "labels.json").read_bytes()).hexdigest())

    def test_scope_excludes_other_pitch_but_retains_main_pitch_false_positives(self):
        scope = {"type": "main_pitch", "polygon": [[0, 0.4], [1, 0.4], [1, 1], [0, 1]]}
        self.labels.update(schema_version=2, evaluation_scope=scope)
        self.frames[0]["detections"] += [
            {"class": "player", "bbox": [0.6, 0.05, 0.7, 0.3], "confidence": 0.9},
            {"class": "football", "bbox": [0.6, 0.05, 0.7, 0.1], "confidence": 0.9},
            {"class": "football", "bbox": [0.6, 0.6, 0.7, 0.7], "confidence": 0.9},
            {"class": "player", "bbox": [0.6, 0.05, 0.7, 0.3], "confidence": 0.1},
        ]
        self.frames.append({**self.frames[0], "frame_index": 1})
        report = self.run_evaluation()
        self.assertEqual(report["schema_version"], 2)
        self.assertEqual(report["evaluation_scope"], scope)
        self.assertEqual(report["excluded_detections"], {"player": 1, "football": 1})
        self.assertEqual(report["classes"]["player"]["tp"], 1)
        self.assertEqual(report["classes"]["player"]["fp"], 0)
        self.assertEqual(report["classes"]["football"]["fp"], 1)

    def test_scope_ground_truth_outside_region_is_rejected_not_silently_dropped(self):
        self.labels.update(schema_version=2, evaluation_scope={
            "type": "main_pitch", "polygon": [[0, 0.6], [1, 0.6], [1, 1], [0, 1]]})
        with self.assertRaisesRegex(ValueError, "annotation outside evaluation scope"):
            self.run_evaluation()

    def test_scope_cannot_be_silently_ignored_by_v1_or_omitted_in_v2(self):
        self.labels["evaluation_scope"] = {"type": "main_pitch", "polygon": [[0, 0], [1, 0], [1, 1]]}
        with self.assertRaisesRegex(ValueError, "require schema_version 2"):
            self.run_evaluation()
        del self.labels["evaluation_scope"]
        self.labels["schema_version"] = 2
        with self.assertRaisesRegex(ValueError, "Invalid evaluation_scope"):
            self.run_evaluation()

    def test_scope_does_not_hide_invalid_background_predictions(self):
        self.labels.update(schema_version=2, evaluation_scope={
            "type": "main_pitch", "polygon": [[0, 0.4], [1, 0.4], [1, 1], [0, 1]]})
        self.frames[0]["detections"].append({
            "class": "player", "bbox": [0.1, 0.1, 0.2, 0.3], "confidence": 2})
        with self.assertRaisesRegex(ValueError, "confidence"):
            self.run_evaluation()

    def test_scoped_empty_frame_counts_inside_predictions_only(self):
        self.labels.update(schema_version=2, evaluation_scope={
            "type": "main_pitch", "polygon": [[0, 0.4], [1, 0.4], [1, 1], [0, 1]]})
        self.labels["frames"][0]["annotations"] = []
        self.frames[0]["detections"].append({
            "class": "player", "bbox": [0.1, 0.1, 0.2, 0.3], "confidence": 0.9})
        report = self.run_evaluation()
        self.assertEqual(report["classes"]["player"]["fp"], 1)
        self.assertEqual(report["excluded_detections"]["player"], 1)

    def test_scope_uses_class_anchors_and_inclusive_edges_in_both_windings(self):
        points = [[0, 0.4], [1, 0.4], [1, 1], [0, 1]]
        for polygon in (points, points[::-1]):
            scope = validate_scope({"type": "main_pitch", "polygon": polygon})
            # A person's head can be outside while their bottom-centre is inside.
            self.assertTrue(in_scope({"class": "player", "bbox": [0.1, 0.1, 0.3, 0.4]}, scope))
            self.assertFalse(in_scope({"class": "football", "bbox": [0.1, 0.1, 0.3, 0.4]}, scope))
            self.assertTrue(in_scope({"class": "football", "bbox": [0.1, 0.3, 0.3, 0.5]}, scope))
            self.assertFalse(in_scope({"class": "player", "bbox": [0.1, 0.1, 0.3, 0.39]}, scope))
            self.assertTrue(in_scope({"class": "player", "bbox": [0, 0.5, 1, 1]}, scope))
        triangle = validate_scope({"type": "main_pitch", "polygon": [[0, 0], [1, 1], [0, 1]]})
        self.assertFalse(in_scope({"class": "football", "bbox": [0.7, 0.1, 0.9, 0.3]}, triangle))
        self.assertTrue(in_scope({"class": "player", "bbox": [0.1, 0, 0.3, 0.2]}, triangle))

    def test_scope_validation_rejects_malformed_degenerate_and_self_crossing_polygons(self):
        for scope in (None, [], {}, {"type": "other", "polygon": []},
                      {"type": "main_pitch", "polygon": [], "extra": 1}):
            with self.subTest(scope=scope), self.assertRaises(ValueError):
                validate_scope(scope)
        for polygon in (None, [], [[0, 0], [1, 1]], [[0, 0], [1, 1], [0, 0]],
                        [[0, 0], [0.5, 0.5], [1, 1]],
                        [[0, 0], [1, 0], [0.4, 0.4], [1, 1], [0, 1]],
                        [[0, 0], [1, 1], [0, 1], [1, 0]],
                        [[0.5, 0], [0.8, 1], [0, 0.4], [1, 0.4], [0.2, 1]],
                        [[0, 0], [1, 0], [0, 1e-14]]):
            with self.subTest(polygon=polygon), self.assertRaises(ValueError):
                validate_scope({"type": "main_pitch", "polygon": polygon})
        for bad in (True, None, "0.5", float("nan"), float("inf"), -0.1, 1.1, 10**1000):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate_scope({"type": "main_pitch", "polygon": [[0, 0], [1, 0], [bad, 1]]})
        for point in (None, 0, [], [0], [0, 1, 2]):
            with self.subTest(point=point), self.assertRaises(ValueError):
                validate_scope({"type": "main_pitch", "polygon": [[0, 0], [1, 0], point]})
        self.assertEqual(validate_scope({"type": "main_pitch", "polygon":
                         [[0, 0], [0.5, 0], [1, 0], [1, 1], [0, 1]]})["type"], "main_pitch")

    def test_explicit_negative_counts_but_unlabelled_frame_does_not(self):
        self.labels["frames"][0]["annotations"] = []
        self.frames.append({**self.frames[0], "frame_index": 1})
        report = self.run_evaluation()
        self.assertEqual(report["classes"]["player"]["fp"], 1)
        self.assertIsNone(report["classes"]["player"]["recall"])
        self.assertEqual(report["coverage"], {
            "processed_frames": 2, "labelled_frames": 1, "unlabelled_frames": 1,
        })

    def test_duplicate_predictions_match_annotation_only_once(self):
        self.frames[0]["detections"].append(dict(self.detection))
        stats = self.run_evaluation()["classes"]["player"]
        self.assertEqual((stats["tp"], stats["fp"], stats["fn"]), (1, 1, 0))
        self.assertEqual(stats["precision"], 0.5)

    def test_explicit_negative_with_no_predictions_has_null_metrics(self):
        self.labels["frames"][0]["annotations"] = []
        self.frames[0]["detections"] = []
        report = self.run_evaluation()
        for stats in report["classes"].values():
            self.assertEqual(stats, {"tp": 0, "fp": 0, "fn": 0,
                                     "precision": None, "recall": None})
        self.assertEqual(report["coverage"]["labelled_frames"], 1)

    def test_missed_annotations_and_classes_aggregate_across_frames(self):
        self.labels["frames"].insert(0, {
            "frame_index": 4, "annotations": [self.annotation,
                {"class": "football", "bbox": [0, 0, 0.1, 0.1]}],
        })
        self.frames.append({**self.frames[0], "frame_index": 4, "detections": []})
        stats = self.run_evaluation()["classes"]
        self.assertEqual(stats["player"], {"tp": 1, "fp": 0, "fn": 1,
                                           "precision": 1, "recall": 0.5})
        self.assertEqual(stats["football"], {"tp": 0, "fp": 0, "fn": 1,
                                             "precision": None, "recall": 0})

    def test_matching_chooses_highest_iou_annotation(self):
        self.labels["frames"][0]["annotations"] = [
            {"class": "player", "bbox": [0, 0, 0.5, 1]},
            {"class": "player", "bbox": [0.3, 0, 0.8, 1]},
        ]
        self.frames[0]["detections"] = [
            {"class": "player", "bbox": [0.15, 0, 0.75, 1], "confidence": 0.9},
            {"class": "player", "bbox": [0, 0, 0.4, 1], "confidence": 0.5},
        ]
        stats = self.run_evaluation(iou=0.4)["classes"]["player"]
        self.assertEqual((stats["tp"], stats["fp"], stats["fn"]), (2, 0, 0))

    def test_duplicate_annotations_cannot_share_one_prediction(self):
        self.labels["frames"][0]["annotations"].append(dict(self.annotation))
        stats = self.run_evaluation()["classes"]["player"]
        self.assertEqual((stats["tp"], stats["fp"], stats["fn"]), (1, 0, 1))

    def test_confidence_order_controls_greedy_matching(self):
        self.labels["frames"][0]["annotations"] = [
            {"class": "player", "bbox": [0, 0, 0.5, 1]},
            {"class": "player", "bbox": [0.3, 0, 0.8, 1]},
        ]
        self.frames[0]["detections"] = [
            {"class": "player", "bbox": [0, 0, 0.5, 1], "confidence": 0.5},
            {"class": "player", "bbox": [0.1, 0, 0.6, 1], "confidence": 0.9},
        ]
        stats = self.run_evaluation()["classes"]["player"]
        self.assertEqual((stats["tp"], stats["fp"], stats["fn"]), (1, 1, 1))

    def test_class_and_thresholds(self):
        self.detection["confidence"] = 0.25
        self.assertEqual(self.run_evaluation()["classes"]["player"]["tp"], 1)
        stats = self.run_evaluation(confidence=0.26)["classes"]["player"]
        self.assertEqual((stats["tp"], stats["fp"], stats["fn"]), (0, 0, 1))
        self.detection["class"] = "football"
        report = self.run_evaluation()
        self.assertEqual(report["classes"]["football"]["fp"], 1)
        self.assertEqual(report["classes"]["player"]["fn"], 1)

    def test_iou(self):
        self.assertEqual(box_iou([0, 0, 1, 1], [0, 0, 0.5, 1]), 0.5)
        self.assertEqual(box_iou([0, 0, 0.1, 0.1], [0.9, 0.9, 1, 1]), 0)
        self.annotation["bbox"] = [0, 0, 1, 1]
        self.detection["bbox"] = [0, 0, 0.5, 1]
        self.assertEqual(self.run_evaluation(iou=0.5)["classes"]["player"]["tp"], 1)
        stats = self.run_evaluation(iou=0.51)["classes"]["player"]
        self.assertEqual((stats["tp"], stats["fp"], stats["fn"]), (0, 1, 1))

    def test_threshold_endpoints(self):
        for threshold in (0, 1):
            with self.subTest(threshold=threshold):
                self.manifest["inference"]["confidence"] = threshold
                self.detection["confidence"] = threshold
                stats = self.run_evaluation(confidence=threshold, iou=1)["classes"]["player"]
                self.assertEqual((stats["tp"], stats["fp"], stats["fn"]), (1, 0, 0))

    def test_duplicate_frame_ids_rejected(self):
        self.frames.append(copy.deepcopy(self.frames[0]))
        with self.assertRaisesRegex(ValueError, "Duplicate detection"):
            self.run_evaluation()
        self.frames.pop()
        self.labels["frames"].append(copy.deepcopy(self.labels["frames"][0]))
        with self.assertRaisesRegex(ValueError, "Duplicate labelled"):
            self.run_evaluation()

    def test_wrong_video_and_missing_frames_rejected(self):
        self.labels["video_sha256"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "different video"):
            self.run_evaluation()
        self.labels["video_sha256"] = "a" * 64
        self.labels["frames"][0]["frame_index"] = 1
        with self.assertRaisesRegex(ValueError, "missing from run"):
            self.run_evaluation()

    def test_incomplete_manifest_rejected(self):
        cases = [
            ("status", None), ("status", "running"), ("status", "failed"),
            ("schema_version", True), ("schema_version", 1.0), ("schema_version", 2),
            ("video", None), ("video", {}), ("video", {"sha256": 1}),
            ("video", {"sha256": "a" * 63}), ("video", {"sha256": "z" * 64}),
            ("sampling", None), ("sampling", {}),
            ("sampling", {"stride": 0, "max_frames": None}),
            ("sampling", {"stride": True, "max_frames": None}),
            ("sampling", {"stride": 1.5, "max_frames": None}),
            ("sampling", {"stride": 1}),
            ("sampling", {"stride": 1, "max_frames": 0}),
            ("sampling", {"stride": 1, "max_frames": True}),
            ("sampling", {"stride": 1, "max_frames": 1.5}),
        ]
        for key, value in cases:
            with self.subTest(key=key, value=value):
                original = self.manifest[key]
                self.manifest[key] = value
                with self.assertRaises(ValueError):
                    self.run_evaluation()
                self.manifest[key] = original
        for key in tuple(self.manifest):
            with self.subTest(missing=key):
                original = self.manifest.pop(key)
                with self.assertRaises(ValueError):
                    self.run_evaluation()
                self.manifest[key] = original

    def test_invalid_top_level_shapes_rejected(self):
        for filename in ("manifest.json", "labels.json", "detections.jsonl"):
            for content in ("null", "[]", "1", '"text"', "{broken", ""):
                with self.subTest(filename=filename, content=content):
                    labels_path = self.write_inputs()
                    (self.root / filename).write_text(content)
                    with self.assertRaises(ValueError):
                        evaluate(self.root, labels_path)

    def test_invalid_label_schema_and_hash_rejected(self):
        for key, value in [("schema_version", True), ("schema_version", 1.0),
                           ("schema_version", 2), ("video_sha256", None),
                           ("video_sha256", "invalid"), ("frames", None),
                           ("frames", {}), ("frames", "text")]:
            with self.subTest(key=key, value=value):
                original = self.labels[key]
                self.labels[key] = value
                with self.assertRaises(ValueError):
                    self.run_evaluation()
                self.labels[key] = original
        for key in tuple(self.labels):
            with self.subTest(missing=key):
                original = self.labels.pop(key)
                with self.assertRaises(ValueError):
                    self.run_evaluation()
                self.labels[key] = original

    def test_malformed_labels_rejected(self):
        for frame in [None, [], {}, {"frame_index": -1, "annotations": []},
                      {"frame_index": 0.0, "annotations": []},
                      {"frame_index": True, "annotations": []},
                      {"frame_index": 0},
                      {"frame_index": 0, "annotations": None},
                      {"frame_index": 0, "annotations": [
                          {"class": "player", "bbox": [0, 0, 0, 0]}]}]:
            with self.subTest(frame=frame):
                self.labels["frames"] = [frame]
                with self.assertRaises(ValueError):
                    self.run_evaluation()

    def test_malformed_frames_rejected_even_if_unlabelled(self):
        self.labels["frames"][0]["frame_index"] = 1
        self.frames.append({**copy.deepcopy(self.frames[0]), "frame_index": 1})
        for key, value in [("frame_index", True), ("frame_index", -1),
                           ("frame_index", 0.0), ("frame_index", "0"),
                           ("timestamp_ms", float("nan")), ("width", 0),
                           ("timestamp_ms", 10 ** 1000), ("timestamp_ms", -1),
                           ("timestamp_ms", True), ("width", True),
                           ("height", 1.5), ("detections", None), ("detections", {})]:
            with self.subTest(key=key, value=value):
                original = self.frames[0][key]
                self.frames[0][key] = value
                with self.assertRaises(ValueError):
                    self.run_evaluation()
                self.frames[0][key] = original
        for key in tuple(self.frames[0]):
            with self.subTest(missing=key):
                original = self.frames[0].pop(key)
                with self.assertRaises(ValueError):
                    self.run_evaluation()
                self.frames[0][key] = original

    def test_empty_labelled_set_rejected(self):
        self.labels["frames"] = []
        with self.assertRaisesRegex(ValueError, "At least one explicitly labelled"):
            self.run_evaluation()

    def test_inference_confidence_required_and_valid(self):
        for inference in [None, {}, {"confidence": -0.1}, {"confidence": 1.1},
                          {"confidence": True}, {"confidence": float("nan")}]:
            with self.subTest(inference=inference):
                self.manifest["inference"] = inference
                with self.assertRaises(ValueError):
                    self.run_evaluation()
        del self.manifest["inference"]
        with self.assertRaisesRegex(ValueError, "inference confidence"):
            self.run_evaluation()

    def test_evaluation_cannot_lower_inference_confidence(self):
        self.manifest["inference"]["confidence"] = 0.25
        self.assertEqual(self.run_evaluation()["inference_confidence"], 0.25)
        with self.assertRaisesRegex(ValueError, "cannot be lower"):
            self.run_evaluation(confidence=0.24)

    def test_invalid_boxes_rejected(self):
        for target in (self.detection, self.annotation):
            for bbox in [None, [], [0, 0, 1], [0, 0, 1, 1, 1], [0, 0, 0, 1],
                         [0, 0, 1.1, 1], [-0.1, 0, 1, 1], [0, 1, 1, 0],
                         [True, 0, 1, 1], [0, 0, float("inf"), 1], [0, 0, "1", 1]]:
                with self.subTest(bbox=bbox):
                    target["bbox"] = bbox
                    with self.assertRaises(ValueError):
                        self.run_evaluation()
            target["bbox"] = [0.1, 0.1, 0.5, 0.5]

    def test_underflowing_area_is_rejected_without_iou_crash(self):
        self.annotation["bbox"] = self.detection["bbox"] = [0, 0, 1e-200, 1e-200]
        with self.assertRaisesRegex(ValueError, "positive area"):
            self.run_evaluation()

    def test_malformed_box_objects_rejected(self):
        for collection, key in [(self.frames[0], "detections"),
                                (self.labels["frames"][0], "annotations")]:
            original = collection[key]
            for box in [None, [], {}, {"class": "player"}, {"bbox": [0, 0, 1, 1]},
                        {"class": [], "bbox": [0, 0, 1, 1]}]:
                with self.subTest(key=key, box=box):
                    collection[key] = [box]
                    with self.assertRaises(ValueError):
                        self.run_evaluation()
            collection[key] = original

    def test_invalid_confidence_and_class_rejected(self):
        for value in [None, -1, 1.1, True, float("nan")]:
            with self.subTest(confidence=value):
                self.detection["confidence"] = value
                with self.assertRaises(ValueError):
                    self.run_evaluation()
        del self.detection["confidence"]
        with self.assertRaisesRegex(ValueError, "confidence"):
            self.run_evaluation()
        self.detection["confidence"] = 0.9
        self.annotation["class"] = "referee"
        with self.assertRaisesRegex(ValueError, "unknown class"):
            self.run_evaluation()

    def test_invalid_thresholds_rejected(self):
        for kwargs in [{"iou": 0}, {"iou": 1.1}, {"iou": float("nan")},
                       {"iou": None}, {"iou": True}, {"iou": float("inf")},
                       {"confidence": -0.1}, {"confidence": True},
                       {"confidence": 1.1}, {"confidence": float("nan")},
                       {"confidence": float("inf")}, {"confidence": "0.5"}]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.run_evaluation(**kwargs)

    def test_nonfinite_json_numbers_rejected_in_all_files(self):
        for filename in ("manifest.json", "labels.json", "detections.jsonl"):
            for value in ("NaN", "Infinity", "-Infinity", "1e999", "-1e999"):
                with self.subTest(filename=filename, value=value):
                    labels_path = self.write_inputs()
                    path = self.root / filename
                    contents = path.read_text().rstrip()
                    path.write_text(contents[:-1] + ', "extra": ' + value + "}")
                    with self.assertRaisesRegex(ValueError, "Non-finite JSON number"):
                        evaluate(self.root, labels_path)

    def test_duplicate_json_keys_rejected_in_all_files(self):
        for filename in ("manifest.json", "labels.json", "detections.jsonl"):
            with self.subTest(filename=filename):
                labels_path = self.write_inputs()
                (self.root / filename).write_text('{"key": 1, "key": 2}')
                with self.assertRaisesRegex(ValueError, "Duplicate JSON key"):
                    evaluate(self.root, labels_path)

    def test_cli_outputs_json_without_changing_inputs(self):
        self.write_inputs()
        original = {path.name: path.read_bytes() for path in self.root.iterdir()}
        result = self.run_cli("--confidence", "0.5", "--iou", "0.75")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        report = json.loads(result.stdout)
        self.assertEqual(report["classes"]["player"]["tp"], 1)
        self.assertEqual(report["confidence_threshold"], 0.5)
        self.assertEqual(report["iou_threshold"], 0.75)
        self.assertEqual(original, {path.name: path.read_bytes() for path in self.root.iterdir()})

    def test_cli_errors_are_actionable_and_have_no_traceback(self):
        self.write_inputs()
        for arguments, message in [(("--iou", "nan"), "IoU threshold"),
                                   (("--confidence", "0.01"), "cannot be lower"),
                                   (("--confidence", "words"), "invalid float"),
                                   (("--unknown",), "unrecognized arguments")]:
            with self.subTest(arguments=arguments):
                result = self.run_cli(*arguments)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertIn(message, result.stderr)
                self.assertNotIn("Traceback", result.stderr)
        for filename in ("manifest.json", "labels.json", "detections.jsonl"):
            for invalid in (None, b"{broken", b"\xff"):
                with self.subTest(filename=filename, invalid=invalid):
                    self.write_inputs()
                    path = self.root / filename
                    if invalid is None:
                        path.unlink()
                    else:
                        path.write_bytes(invalid)
                    result = self.run_cli()
                    self.assertEqual(result.returncode, 2)
                    self.assertEqual(result.stdout, "")
                    self.assertIn("error:", result.stderr)
                    self.assertNotIn("Traceback", result.stderr)

    def test_cli_help_does_not_require_input_files(self):
        result = self.run_cli("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--labels", result.stdout)
        self.assertIn("--confidence", result.stdout)

    def test_cli_requires_labels_argument(self):
        script = Path(__file__).resolve().parents[1] / "evaluate.py"
        result = subprocess.run([sys.executable, str(script), str(self.root)],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("--labels", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
