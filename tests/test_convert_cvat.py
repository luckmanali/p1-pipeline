import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from convert_cvat import convert_cvat, main
from evaluate import evaluate


class ConvertCvatTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.manifest_path = self.root / "manifest.json"
        self.coco_path = self.root / "instances_default.json"
        self.output_path = self.root / "labels.json"
        self.manifest = {
            "schema_version": 1, "kind": "frame_export", "status": "completed",
            "video": {"path": "data/original.mp4", "sha256": "a" * 64},
            "sampling": {"mode": "interval", "every_seconds": 3, "stride": None,
                         "max_frames": None},
            "frames": [
                {"frame_index": index, "timestamp_ms": index * 100,
                 "source_time_ms": index * 100 - 500, "width": 200, "height": 100,
                 "file_name": f"images/frame_aaaaaaaaaaaa_{index:09d}.png",
                 "sha256": "b" * 64}
                for index in (0, 30, 90)
            ],
        }
        self.coco = {
            "images": [
                {"id": identifier, "file_name": self.manifest["frames"][position]["file_name"],
                 "width": 200, "height": 100}
                for identifier, position in ((900, 2), (40, 0), (7, 1))
            ],
            "categories": [{"id": 53, "name": "football"}, {"id": 11, "name": "player"}],
            "annotations": [
                {"id": 82, "image_id": 7, "category_id": 53,
                 "bbox": [180, 90, 20, 10], "iscrowd": 0, "segmentation": [], "area": 200},
                {"id": 3, "image_id": 40, "category_id": 11,
                 "bbox": [20, 10, 40, 80], "attributes": {"occluded": True, "rotation": 0}},
            ],
        }

    def write_inputs(self):
        self.manifest_path.write_text(json.dumps(self.manifest))
        self.coco_path.write_text(json.dumps(self.coco))

    def convert(self):
        self.write_inputs()
        return convert_cvat(self.coco_path, self.manifest_path, reviewed=True)

    def cli(self, *extra, reviewed=True):
        script = Path(__file__).resolve().parents[1] / "convert_cvat.py"
        args = [sys.executable, str(script), str(self.coco_path), "--manifest",
                str(self.manifest_path), "--output", str(self.output_path), *extra]
        if reviewed:
            args.append("--reviewed")
        return subprocess.run(args, capture_output=True, text=True, timeout=10)

    def test_noncontiguous_ids_reordered_images_xywh_and_explicit_negative(self):
        labels = self.convert()
        self.assertEqual(labels["frames"], [
            {"frame_index": 0, "annotations": [{"class": "player", "bbox": [0.1, 0.1, 0.3, 0.9]}]},
            {"frame_index": 30, "annotations": [{"class": "football", "bbox": [0.9, 0.9, 1, 1]}]},
            {"frame_index": 90, "annotations": []},
        ])
        self.assertEqual(labels["video_sha256"], "a" * 64)
        self.assertEqual(labels["schema_version"], 1)

    def test_provenance_hashes_exact_files_and_records_subset(self):
        self.coco["images"].pop(0)
        labels = self.convert()
        self.assertEqual(labels["provenance"], {
            "format": "cvat_coco", "reviewed": True,
            "manifest_sha256": hashlib.sha256(self.manifest_path.read_bytes()).hexdigest(),
            "coco_sha256": hashlib.sha256(self.coco_path.read_bytes()).hexdigest(),
            "exported_frames": 3, "included_frames": 2, "excluded_frame_indices": [90],
        })

    def test_scoped_cli_round_trip_records_region_and_excludes_background_predictions(self):
        self.write_inputs()
        scope = {"type": "main_pitch", "polygon": [[0, 0.4], [1, 0.4], [1, 1], [0, 1]]}
        scope_path = self.root / "scope.json"
        scope_path.write_text(json.dumps(scope))
        result = self.cli("--scope", str(scope_path))
        self.assertEqual(result.returncode, 0, result.stderr)
        labels = json.loads(self.output_path.read_text())
        self.assertEqual(labels["schema_version"], 2)
        self.assertEqual(labels["evaluation_scope"], scope)
        self.assertEqual(labels["provenance"]["scope_sha256"], hashlib.sha256(scope_path.read_bytes()).hexdigest())
        self.assertEqual(labels["frames"][-1]["annotations"], [])
        run = self.root / "run"
        run.mkdir()
        (run / "manifest.json").write_text(json.dumps({
            "schema_version": 1, "status": "completed", "video": {"sha256": "a" * 64},
            "sampling": {"stride": 1, "max_frames": None}, "model": {"name": "test"},
            "inference": {"confidence": 0.05}}))
        (run / "detections.jsonl").write_text("".join(json.dumps({
            "frame_index": f["frame_index"], "timestamp_ms": 0, "width": 200, "height": 100,
            "detections": [{**a, "confidence": 0.9} for a in f["annotations"]] + [
                {"class": "player", "confidence": 0.8, "bbox": [0.1, 0.1, 0.2, 0.2]}],
        }) + "\n" for f in labels["frames"]))
        report = evaluate(run, self.output_path)
        self.assertEqual(report["excluded_detections"], {"player": 3, "football": 0})
        for stats in report["classes"].values():
            self.assertEqual((stats["tp"], stats["fp"], stats["fn"]), (1, 0, 0))

    def test_scope_requires_valid_file_review_and_in_scope_annotations_before_output(self):
        self.write_inputs()
        scope_path = self.root / "scope.json"
        result = self.cli("--scope", str(scope_path))
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.output_path.exists())
        for content in ('null', '{}', '{"type":"main_pitch","type":"main_pitch"}',
                        '{"polygon": NaN}', '{"type":"main_pitch","polygon":[[0,0],[1,1],[0,0]]}'):
            scope_path.write_text(content)
            with self.subTest(content=content):
                result = self.cli("--scope", str(scope_path))
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.output_path.exists())
        scope_path.write_text(json.dumps({"type": "main_pitch", "polygon":
                                        [[0, 0.96], [1, 0.96], [1, 1], [0, 1]]}))
        result = self.cli("--scope", str(scope_path))
        self.assertIn("outside evaluation scope", result.stderr)
        self.assertFalse(self.output_path.exists())
        result = self.cli("--scope", str(scope_path), reviewed=False)
        self.assertIn("--reviewed", result.stderr)
        self.assertFalse(self.output_path.exists())

    def test_scope_function_preserves_provenance_and_rejects_misplaced_ground_truth(self):
        self.write_inputs()
        scope_path = self.root / "scope.json"
        scope = {"type": "main_pitch", "polygon": [[0, 0.4], [1, 0.4], [1, 1], [0, 1]]}
        scope_path.write_text(json.dumps(scope))
        labels = convert_cvat(self.coco_path, self.manifest_path, reviewed=True, scope_path=scope_path)
        self.assertEqual(labels["evaluation_scope"], scope)
        self.assertEqual(labels["provenance"]["scope_sha256"], hashlib.sha256(scope_path.read_bytes()).hexdigest())
        self.coco["annotations"][0]["bbox"] = [10, 10, 5, 5]
        self.write_inputs()
        with self.assertRaisesRegex(ValueError, "Annotation 82 outside evaluation scope"):
            convert_cvat(self.coco_path, self.manifest_path, reviewed=True, scope_path=scope_path)

    def test_cvat_prefixes_and_windows_separators_are_only_used_for_basename(self):
        for image, prefix in zip(self.coco["images"], ("nested/task/images/", "C:\\task\\", "../")):
            image["file_name"] = prefix + Path(image["file_name"]).name
        labels = self.convert()
        self.assertEqual([frame["frame_index"] for frame in labels["frames"]], [0, 30, 90])
        self.assertFalse((self.root / "images").exists())

    def test_canonical_coco_names_map_to_pipeline_classes(self):
        self.coco["categories"] = [{"id": 53, "name": "sports ball"}, {"id": 11, "name": "person"}]
        labels = self.convert()
        self.assertEqual([frame["annotations"][0]["class"] for frame in labels["frames"][:2]],
                         ["player", "football"])

    def test_review_acknowledgement_is_explicit_and_strict(self):
        for reviewed in (False, None, 1, "yes"):
            with self.subTest(reviewed=reviewed), self.assertRaisesRegex(ValueError, "reviewed"):
                convert_cvat(self.coco_path, self.manifest_path, reviewed=reviewed)

    def test_all_negative_images_are_retained_with_empty_categories(self):
        self.coco["annotations"] = []
        self.coco["categories"] = []
        self.assertEqual([frame["annotations"] for frame in self.convert()["frames"]], [[], [], []])

    def test_stride_export_is_supported(self):
        self.manifest["sampling"] = {"mode": "stride", "stride": 30,
                                     "every_seconds": None, "max_frames": 3}
        self.assertEqual(len(self.convert()["frames"]), 3)

    def test_full_image_box_and_fractional_coordinates(self):
        self.coco["annotations"][0]["bbox"] = [0, 0, 200, 100]
        self.coco["annotations"][1]["bbox"] = [0.5, 0.25, 20.5, 10.25]
        frames = self.convert()["frames"]
        self.assertEqual(frames[1]["annotations"][0]["bbox"], [0, 0, 1, 1])
        self.assertEqual(frames[0]["annotations"][0]["bbox"], [0.0025, 0.0025, 0.105, 0.105])

    def test_duplicate_ids_fail_in_each_coco_collection(self):
        for collection in ("images", "categories", "annotations"):
            original = copy.deepcopy(self.coco)
            with self.subTest(collection=collection):
                self.coco[collection].append(copy.deepcopy(self.coco[collection][0]))
                with self.assertRaisesRegex(ValueError, "Duplicate"):
                    self.convert()
            self.coco = original

    def test_ids_are_integers_and_not_inferred_from_positions(self):
        original = copy.deepcopy(self.coco)
        for collection in ("images", "categories", "annotations"):
            for identifier in (None, True, -1, 1.5, "40"):
                with self.subTest(collection=collection, identifier=identifier):
                    self.coco = copy.deepcopy(original)
                    self.coco[collection][0]["id"] = identifier
                    with self.assertRaises(ValueError):
                        self.convert()
        self.coco = original
        self.coco["annotations"][0]["image_id"] = 0
        with self.assertRaisesRegex(ValueError, "unknown image"):
            self.convert()

    def test_zero_ids_are_valid(self):
        self.coco["images"][0]["id"] = 0
        self.coco["categories"][0]["id"] = 0
        self.coco["annotations"][0].update(id=0, category_id=0)
        self.assertEqual(len(self.convert()["frames"]), 3)

    def test_missing_or_wrong_coco_collections_and_items(self):
        original = copy.deepcopy(self.coco)
        for collection in ("images", "categories", "annotations"):
            for value in (None, {}, "text", [None], [[]], [{}]):
                with self.subTest(collection=collection, value=value):
                    self.coco = copy.deepcopy(original)
                    self.coco[collection] = value
                    with self.assertRaises(ValueError):
                        self.convert()
            self.coco = copy.deepcopy(original)
            del self.coco[collection]
            with self.assertRaises(ValueError):
                self.convert()
        self.coco = original
        self.coco["images"] = []
        with self.assertRaisesRegex(ValueError, "at least one"):
            self.convert()

    def test_duplicate_basename_even_with_different_prefix_is_ambiguous(self):
        self.coco["images"][0]["file_name"] = "other/" + Path(self.coco["images"][1]["file_name"]).name
        with self.assertRaisesRegex(ValueError, "Duplicate COCO image filename"):
            self.convert()

    def test_unknown_and_invalid_filenames_fail(self):
        for value in (None, True, "", ".", "..", "dir/", "file\0.png", "unknown.png",
                      "frame_bbbbbbbbbbbb_000000000.png"):
            with self.subTest(value=value):
                self.coco["images"][0]["file_name"] = value
                with self.assertRaises(ValueError):
                    self.convert()

    def test_changed_missing_or_noninteger_dimensions_fail(self):
        original = copy.deepcopy(self.coco)
        for key in ("width", "height"):
            for value in (None, 0, -1, True, 100.0, 99, "200"):
                with self.subTest(key=key, value=value):
                    self.coco = copy.deepcopy(original)
                    self.coco["images"][0][key] = value
                    with self.assertRaisesRegex(ValueError, "Dimensions differ"):
                        self.convert()

    def test_categories_are_exact_supported_names_without_alias_collisions(self):
        original = copy.deepcopy(self.coco)
        for name in (None, [], 1, "Player", "ball", "car", " person"):
            with self.subTest(name=name):
                self.coco = copy.deepcopy(original)
                self.coco["categories"][0]["name"] = name
                with self.assertRaisesRegex(ValueError, "Categories must"):
                    self.convert()
        self.coco = original
        self.coco["categories"].append({"id": 99, "name": "person"})
        with self.assertRaisesRegex(ValueError, "Duplicate category mapping"):
            self.convert()

    def test_annotation_references_must_exist_and_have_integer_types(self):
        original = copy.deepcopy(self.coco)
        for key in ("image_id", "category_id"):
            for value in (None, False, -1, 1.0, "7", 99):
                with self.subTest(key=key, value=value):
                    self.coco = copy.deepcopy(original)
                    self.coco["annotations"][0][key] = value
                    with self.assertRaisesRegex(ValueError, "unknown"):
                        self.convert()

    def test_crowd_ignore_and_custom_flags_cannot_silently_drop_objects(self):
        original = copy.deepcopy(self.coco)
        for attribute in (False, True):
            for key in ("iscrowd", "is_crowd", "crowd", "ignore", "ignored", "difficult", " Ignore "):
                for value in (True, 1, -1, "true", "false", None):
                    with self.subTest(attribute=attribute, key=key, value=value):
                        self.coco = copy.deepcopy(original)
                        target = self.coco["annotations"][0]
                        if attribute:
                            target = target.setdefault("attributes", {})
                        target[key] = value
                        with self.assertRaisesRegex(ValueError, "flag"):
                            self.convert()

    def test_false_flags_and_zero_rotation_are_supported(self):
        self.coco["annotations"][0].update(ignore=False, rotation=0, keypoints=[], num_keypoints=0)
        self.coco["annotations"][0]["attributes"] = {"iscrowd": 0, "ignore": False}
        self.assertEqual(len(self.convert()["frames"]), 3)

    def test_non_rectangle_annotations_are_rejected(self):
        original = copy.deepcopy(self.coco)
        for key, values in {
            "segmentation": (None, {}, [[0, 0, 1, 0, 1, 1]], {"counts": "rle"}),
            "keypoints": (None, [1, 2, 2]), "num_keypoints": (None, True, 1, 1.5),
            "rotation": (None, True, 90, "0"), "attributes": (None, [], "text"),
        }.items():
            for value in values:
                with self.subTest(key=key, value=value):
                    self.coco = copy.deepcopy(original)
                    self.coco["annotations"][0][key] = value
                    with self.assertRaises(ValueError):
                        self.convert()
        self.coco = original
        self.coco["annotations"][0]["attributes"] = {"rotation": 1}
        with self.assertRaisesRegex(ValueError, "Rotated"):
            self.convert()

    def test_invalid_xywh_rejected_instead_of_clamping_or_dropping(self):
        cases = [None, {}, [], [1, 2, 3], [1, 2, 3, 4, 5], [True, 0, 1, 1],
                 ["0", 0, 1, 1], [float("nan"), 0, 1, 1], [0, float("inf"), 1, 1],
                 [0, 0, 10 ** 1000, 1], [-0.1, 0, 1, 1], [0, -1, 1, 1],
                 [0, 0, 0, 1], [0, 0, 1, 0], [0, 0, -1, 1], [0, 0, 1, -1],
                 [199, 0, 2, 1], [0, 99, 1, 2], [200, 0, 1, 1],
                 [0, 0, 1e-300, 1e-300], [1, 0, 1e-300, 1]]
        for value in cases:
            with self.subTest(value=value):
                self.coco["annotations"][0]["bbox"] = value
                with self.assertRaises(ValueError):
                    self.convert()

    def test_manifest_identity_and_status_are_required(self):
        original = copy.deepcopy(self.manifest)
        for key, values in {
            "schema_version": (None, True, 1.0, 2), "kind": (None, "benchmark"),
            "status": (None, "running", "failed"),
            "video": (None, {}, {"path": "v", "sha256": "x" * 64},
                      {"path": "", "sha256": "a" * 64}, {"sha256": "a" * 64}),
            "frames": (None, {}, [], [None], [{}]),
        }.items():
            for value in values:
                with self.subTest(key=key, value=value):
                    self.manifest = copy.deepcopy(original)
                    self.manifest[key] = value
                    with self.assertRaises(ValueError):
                        self.convert()

    def test_manifest_sampling_validation(self):
        for sampling in (None, {}, {"mode": "other", "max_frames": None},
                         {"mode": "stride", "stride": 1, "max_frames": None},
                         {"mode": "stride", "stride": 0, "max_frames": None, "every_seconds": None},
                         {"mode": "stride", "stride": True, "max_frames": None, "every_seconds": None},
                         {"mode": "interval", "every_seconds": 0, "stride": None, "max_frames": None},
                         {"mode": "interval", "every_seconds": True, "stride": None, "max_frames": None},
                         {"mode": "interval", "every_seconds": 3, "stride": 1, "max_frames": None},
                         {"mode": "interval", "every_seconds": 3, "stride": None, "max_frames": 0},
                         {"mode": "interval", "every_seconds": 3, "stride": None, "max_frames": 2}):
            with self.subTest(sampling=sampling):
                self.manifest["sampling"] = sampling
                with self.assertRaises(ValueError):
                    self.convert()

    def test_exported_frame_fields_and_exact_identity_are_validated(self):
        original = copy.deepcopy(self.manifest)
        for key, values in {
            "frame_index": (None, True, -1, 1.5, 30),
            "timestamp_ms": (None, True, -1, float("nan"), 10 ** 1000),
            "source_time_ms": (None, True, float("inf")),
            "width": (None, 0, True, 1.5, 10 ** 1000), "height": (None, -1),
            "sha256": (None, "x" * 64, "b" * 63),
            "file_name": (None, "unknown.png", "images/frame_bbbbbbbbbbbb_000000000.png",
                          "images/frame_aaaaaaaaaaaa_000000030.png"),
        }.items():
            for value in values:
                with self.subTest(key=key, value=value):
                    self.manifest = copy.deepcopy(original)
                    self.manifest["frames"][0][key] = value
                    with self.assertRaises(ValueError):
                        self.convert()
        self.manifest = original
        self.manifest["frames"].append(copy.deepcopy(self.manifest["frames"][0]))
        with self.assertRaisesRegex(ValueError, "Duplicate exported frame_index"):
            self.convert()

    def test_strict_json_rejects_bad_shapes_duplicate_keys_and_nonfinite_values(self):
        for target in (self.manifest_path, self.coco_path):
            for content in ("null", "[]", "1", '"text"', "{bad", "", '{"images":[],"images":[]}',
                            '{"value": NaN}', '{"value": Infinity}', '{"value": 1e999}'):
                with self.subTest(target=target.name, content=content):
                    self.write_inputs()
                    target.write_text(content)
                    with self.assertRaises(ValueError):
                        convert_cvat(self.coco_path, self.manifest_path, reviewed=True)

    def test_cli_success_reports_omissions_and_labels_evaluate_without_changes(self):
        self.coco["images"].pop(0)
        self.write_inputs()
        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {
            "output": str(self.output_path), "labelled_frames": 2, "excluded_frame_indices": [90],
        })
        labels = json.loads(self.output_path.read_text())
        run_dir = self.root / "run"
        run_dir.mkdir()
        (run_dir / "manifest.json").write_text(json.dumps({
            "schema_version": 1, "status": "completed", "video": {"sha256": "a" * 64},
            "sampling": {"stride": 1, "max_frames": None}, "model": {"name": "test"},
            "inference": {"confidence": 0.05},
        }))
        (run_dir / "detections.jsonl").write_text("".join(json.dumps({
            "frame_index": frame["frame_index"], "timestamp_ms": 0, "width": 200, "height": 100,
            "detections": [{**annotation, "confidence": 0.9} for annotation in frame["annotations"]],
        }) + "\n" for frame in labels["frames"]))
        report = evaluate(run_dir, self.output_path)
        for metrics in report["classes"].values():
            self.assertEqual(metrics, {"tp": 1, "fp": 0, "fn": 0, "precision": 1, "recall": 1})

    def test_cli_requires_review_and_validation_before_creating_output(self):
        self.write_inputs()
        result = self.cli(reviewed=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--reviewed", result.stderr)
        self.assertFalse(self.output_path.exists())
        self.coco["annotations"][-1]["bbox"] = [0, 0, 0, 0]
        self.write_inputs()
        result = self.cli()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("positive area", result.stderr)
        self.assertFalse(self.output_path.exists())

    def test_main_refuses_to_overwrite_existing_output(self):
        self.write_inputs()
        self.output_path.write_text("existing labels")
        with contextlib.redirect_stderr(io.StringIO()) as error:
            with self.assertRaises(SystemExit) as raised:
                main([str(self.coco_path), "--manifest", str(self.manifest_path),
                      "--output", str(self.output_path), "--reviewed"])
        self.assertEqual(raised.exception.code, 2)
        self.assertIn("File exists", error.getvalue())
        self.assertEqual(self.output_path.read_text(), "existing labels")

    def test_cli_missing_input_is_an_actionable_error_without_output(self):
        result = self.cli()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("No such file", result.stderr)
        self.assertFalse(self.output_path.exists())

    def test_main_cleans_partial_output_after_write_failure(self):
        self.write_inputs()
        original_open = Path.open

        class FailedWriter:
            def __init__(self, handle):
                self.handle = handle

            def __enter__(self):
                return self

            def write(self, text):
                self.handle.write(text[:12])
                raise OSError("disk full")

            def __exit__(self, *args):
                self.handle.close()

        def fail_output(path, *args, **kwargs):
            handle = original_open(path, *args, **kwargs)
            return FailedWriter(handle) if path == self.output_path else handle

        with patch.object(Path, "open", fail_output), contextlib.redirect_stderr(io.StringIO()) as error:
            with self.assertRaises(SystemExit) as raised:
                main([str(self.coco_path), "--manifest", str(self.manifest_path),
                      "--output", str(self.output_path), "--reviewed"])
        self.assertEqual(raised.exception.code, 2)
        self.assertIn("disk full", error.getvalue())
        self.assertFalse(self.output_path.exists())

    def test_main_success_returns_zero(self):
        self.write_inputs()
        with contextlib.redirect_stdout(io.StringIO()) as output:
            result = main([str(self.coco_path), "--manifest", str(self.manifest_path),
                           "--output", str(self.output_path), "--reviewed"])
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(output.getvalue())["labelled_frames"], 3)


if __name__ == "__main__":
    unittest.main()
