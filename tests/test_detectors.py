from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from detectors import DFINE_CLASSES, DFineDetector, YoloDetector, load_detector, normalize_detections, repo_state, yolo_classes


class DetectorOutputTests(unittest.TestCase):
    def test_normalizes_clips_filters_and_retains_ball_class_32(self):
        detections = normalize_detections(
            [0, 32, 37, 0, 32, 0],
            [[-10, 10, 110, 40], [40, 20, 60, 30], [0, 0, 10, 10],
             [0, 0, 10, 10], [200, 0, 300, 10], [20, 20, 10, 30]],
            [0.8, 0.3, 0.9, 0.1, 0.9, 0.9], 100, 50, DFINE_CLASSES, 0.3,
        )
        self.assertEqual(detections, [
            {"class": "player", "confidence": 0.8, "bbox": [0.0, 0.2, 1.0, 0.8]},
            {"class": "football", "confidence": 0.3, "bbox": [0.4, 0.4, 0.6, 0.6]},
        ])

    def test_rejects_corrupt_output_instead_of_writing_invalid_json(self):
        cases = [
            ([0], [], [0.9]),
            ([0], [[0, 0, 1]], [0.9]),
            ([0.5], [[0, 0, 1, 1]], [0.9]),
            ([0], [[0, 0, float("nan"), 1]], [0.9]),
            ([0], [[0, 0, 1, 1]], [float("inf")]),
            ([0], [[0, 0, 1, 1]], [1.1]),
            ([-1], [[0, 0, 1, 1]], [0.9]),
            ([True], [[0, 0, 1, 1]], [0.9]),
            ([0], [[0, 0, "1", 1]], [0.9]),
            ([0], [[0, 0, 1, 1]], [-0.1]),
            ([0], [[0, 0, 1, 1]], [True]),
        ]
        for labels, boxes, scores in cases:
            with self.subTest(labels=labels, boxes=boxes, scores=scores), self.assertRaises(ValueError):
                normalize_detections(labels, boxes, scores, 100, 50, DFINE_CLASSES, 0.3)

    def test_empty_frame_is_valid(self):
        self.assertEqual(normalize_detections([], [], [], 100, 50, DFINE_CLASSES, 0.3), [])

    def test_invalid_image_dimensions_fail_even_for_empty_frames(self):
        for width, height in ((0, 50), (100, -1), (float("nan"), 50), (100, float("inf"))):
            with self.subTest(width=width, height=height), self.assertRaisesRegex(ValueError, "dimensions"):
                normalize_detections([], [], [], width, height, DFINE_CLASSES, 0.3)

    def test_pose_checkpoint_cannot_silently_report_zero_balls(self):
        with self.assertRaisesRegex(ValueError, "detection checkpoint"):
            yolo_classes(SimpleNamespace(task="pose", names={0: "person"}))
        with self.assertRaisesRegex(ValueError, "sports ball"):
            yolo_classes(SimpleNamespace(task="detect", names={0: "person"}))

    def test_yolo_mapping_uses_names(self):
        model = SimpleNamespace(task="detect", names={0: "person", 1: "bicycle", 32: "sports ball"})
        self.assertEqual(yolo_classes(model), DFINE_CLASSES)
        self.assertEqual(yolo_classes(SimpleNamespace(task="detect", names=["person", "sports ball"])),
                         {0: "player", 1: "football"})

    def test_yolo_predict_returns_normalized_native_results(self):
        def tensor(values):
            return SimpleNamespace(cpu=lambda: SimpleNamespace(tolist=lambda: values))

        detector = YoloDetector.__new__(YoloDetector)
        detector.classes = DFINE_CLASSES
        detector.confidence = 0.3
        detector.device = "cpu"
        detector.input_size = 2560
        boxes = SimpleNamespace(cls=tensor([32]), xyxy=tensor([[40, 20, 60, 30]]), conf=tensor([0.9]))
        detector.model = SimpleNamespace(predict=MagicMock(return_value=[SimpleNamespace(boxes=boxes)]))
        rgb = MagicMock(shape=(50, 100, 3))
        self.assertEqual(detector.predict(rgb), [
            {"class": "football", "confidence": 0.9, "bbox": [0.4, 0.4, 0.6, 0.6]},
        ])
        arguments = detector.model.predict.call_args.kwargs
        self.assertFalse(arguments["half"])
        self.assertFalse(arguments["rect"])
        self.assertEqual(arguments["imgsz"], 2560)
        self.assertEqual(arguments["classes"], [0, 32])
        self.assertEqual(arguments["conf"], 0.3)
        rgb.__getitem__.assert_called_once_with((slice(None), slice(None), slice(None, None, -1)))
        self.assertIs(arguments["source"], rgb.__getitem__.return_value.copy.return_value)

    def test_missing_checkpoint_fails_without_importing_ml_libraries(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "does not exist"):
                load_detector("yolo26n", Path(directory) / "absent.pt", "cpu", 0.3)

    def test_invalid_setup_fails_before_loading_model(self):
        with tempfile.TemporaryDirectory() as directory:
            weights = Path(directory) / "weights.pt"
            weights.touch()
            with self.assertRaisesRegex(ValueError, "MPS"):
                load_detector("yolo26n", weights, "mps", 0.3)
            with self.assertRaisesRegex(ValueError, "Confidence"):
                load_detector("yolo26n", weights, "cpu", float("nan"))
            with self.assertRaisesRegex(ValueError, "--dfine-repo"):
                load_detector("dfine-n", weights, "cpu", 0.3)

    def test_loader_rejects_unsupported_model_checkpoint_format_and_cuda_syntax(self):
        with tempfile.TemporaryDirectory() as directory:
            weights = Path(directory) / "weights.onnx"
            weights.touch()
            with self.assertRaisesRegex(ValueError, "Unsupported detector"):
                load_detector("unknown", weights, "cpu", 0.3)
            with self.assertRaisesRegex(ValueError, "local .pt"):
                load_detector("yolo26n", weights, "cpu", 0.3)
            for device in ("cuda:-1", "cuda:", "cuda:0,1", "gpu"):
                with self.subTest(device=device), self.assertRaisesRegex(ValueError, "Device must"):
                    load_detector("yolo26n", weights, device, 0.3)

    def test_loader_routes_local_paths_and_valid_devices(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            weights = root / "weights.pt"
            weights.touch()
            for device in ("cpu", "cuda", "cuda:2"):
                with self.subTest(device=device), patch("detectors.YoloDetector") as adapter:
                    self.assertIs(load_detector("yolo26n", weights, device, 0.3), adapter.return_value)
                    adapter.assert_called_once_with(weights.resolve(), device, 0.3,
                                                    model_name="yolo26n", input_size=640)
            with patch("detectors.DFineDetector") as adapter:
                self.assertIs(load_detector("dfine-n", weights, "cpu", 0.3, root), adapter.return_value)
                adapter.assert_called_once_with(weights.resolve(), "cpu", 0.3, root.resolve(), input_size=640)

    def test_loader_forwards_requested_scale_and_input_size(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            weights = root / "weights.pt"
            weights.touch()
            for name in ("yolo26n", "yolo26s", "yolo26m", "yolo26l"):
                for size in (640, 1280, 1920, 2560):
                    with self.subTest(name=name, size=size), patch("detectors.YoloDetector") as adapter:
                        load_detector(name, weights, "cpu", 0.05, input_size=size)
                        adapter.assert_called_once_with(weights.resolve(), "cpu", 0.05,
                                                        model_name=name, input_size=size)
            with patch("detectors.DFineDetector") as adapter:
                load_detector("dfine-n", weights, "cpu", 0.05, root, input_size=1280)
                adapter.assert_called_once_with(weights.resolve(), "cpu", 0.05, root.resolve(), input_size=1280)

    def test_invalid_input_size_fails_before_model_loading(self):
        with tempfile.TemporaryDirectory() as directory:
            weights = Path(directory) / "weights.pt"
            weights.touch()
            for size in (0, -640, 641, 960, 640.0, "640", True, None, 1920.0, 1921, 2560.0, 2561):
                with self.subTest(size=size), patch("detectors.YoloDetector") as adapter:
                    with self.assertRaisesRegex(ValueError, "Input size"):
                        load_detector("yolo26n", weights, "cpu", 0.05, input_size=size)
                    adapter.assert_not_called()

    def test_unverified_dfine_sizes_fail_before_loading_model(self):
        with tempfile.TemporaryDirectory() as directory:
            weights = Path(directory) / "weights.pth"
            weights.touch()
            for size in (1920, 2560):
                with self.subTest(size=size), patch("detectors.DFineDetector") as adapter:
                    with self.assertRaisesRegex(ValueError, "D-FINE supports only"):
                        load_detector("dfine-n", weights, "cpu", 0.05, Path(directory), input_size=size)
                    adapter.assert_not_called()


class YoloAdapterTests(unittest.TestCase):
    def setUp(self):
        self.architecture = {
            "yaml_file": "yolo26n.yaml", "scale": "n", "nc": 80, "end2end": True, "reg_max": 1,
        }
        self.model = SimpleNamespace(
            task="detect", names={0: "person", 32: "sports ball"},
            model=SimpleNamespace(yaml=self.architecture,
                                  parameters=lambda: [SimpleNamespace(numel=lambda: 2572280)]),
        )
        self.ultralytics = SimpleNamespace(__version__="test", YOLO=MagicMock(return_value=self.model))
        self.torch = SimpleNamespace(device=MagicMock(return_value=object()))
        self.imports = patch.dict(sys.modules, {"ultralytics": self.ultralytics, "torch": self.torch})
        self.imports.start()
        self.addCleanup(self.imports.stop)

    def test_device_object_preserves_cuda_index_and_cpu_thread_policy(self):
        empty = SimpleNamespace(cpu=lambda: SimpleNamespace(tolist=lambda: []))
        self.model.predict = MagicMock(return_value=[SimpleNamespace(
            boxes=SimpleNamespace(cls=empty, xyxy=empty, conf=empty),
        )])
        for device in ("cpu", "cuda:2"):
            with self.subTest(device=device):
                detector = YoloDetector(Path("weights.pt"), device, 0.3)
                self.torch.device.assert_called_with(device)
                self.assertIs(detector.device, self.torch.device.return_value)
                self.assertEqual(detector.predict(MagicMock(shape=(50, 100, 3))), [])
                self.assertIs(self.model.predict.call_args.kwargs["device"], self.torch.device.return_value)

    def test_records_actual_architecture_and_parameter_count(self):
        detector = YoloDetector(Path("renamed.pt"), "cpu", 0.3)
        self.assertEqual(detector.metadata["architecture_config"], "yolo26n.yaml")
        self.assertEqual(detector.metadata["architecture_scale"], "n")
        self.assertEqual(detector.metadata["parameter_count"], 2572280)
        self.ultralytics.YOLO.assert_called_once_with("renamed.pt", task="detect")

    def test_accepts_family_yaml_with_explicit_nano_scale(self):
        self.architecture["yaml_file"] = "models/26/yolo26.yaml"
        self.assertEqual(YoloDetector(Path("weights.pt"), "cpu", 0.3).metadata["architecture_scale"], "n")

    def test_small_checkpoint_and_requested_size_are_recorded(self):
        self.architecture.update(yaml_file="yolo26s.yaml", scale="s")
        detector = YoloDetector(Path("renamed.pt"), "cpu", 0.3, model_name="yolo26s", input_size=1280)
        self.assertEqual(detector.metadata["model"], "yolo26s")
        self.assertEqual(detector.metadata["architecture_scale"], "s")
        self.assertEqual(detector.metadata["input_size"], [1280, 1280])
        self.assertIn("1280x1280", detector.metadata["preprocessing"])
        self.architecture["yaml_file"] = "yolo26.yaml"
        self.assertEqual(YoloDetector(Path("s.pt"), "cpu", 0.3, model_name="yolo26s").metadata["input_size"],
                         [640, 640])

    def test_medium_checkpoint_and_1920_metadata(self):
        self.architecture.update(yaml_file="yolo26m.yaml", scale="m")
        detector = YoloDetector(Path("renamed.pt"), "cpu", 0.05, model_name="yolo26m", input_size=1920)
        self.assertEqual(detector.metadata["model"], "yolo26m")
        self.assertEqual(detector.metadata["architecture_scale"], "m")
        self.assertEqual(detector.metadata["input_size"], [1920, 1920])
        self.assertIn("1920x1920", detector.metadata["preprocessing"])
        self.architecture["yaml_file"] = "yolo26.yaml"
        self.assertEqual(YoloDetector(Path("m.pt"), "cpu", 0.05, model_name="yolo26m").metadata["input_size"],
                         [640, 640])

    def test_medium_scale_mismatch_fails_in_both_directions(self):
        for scale in ("n", "s"):
            with self.subTest(scale=scale):
                self.architecture.update(yaml_file=f"yolo26{scale}.yaml", scale=scale)
                with self.assertRaisesRegex(ValueError, "YOLO26m"):
                    YoloDetector(Path("m.pt"), "cpu", 0.05, model_name="yolo26m")
                self.architecture.update(yaml_file="yolo26m.yaml", scale="m")
                with self.assertRaisesRegex(ValueError, f"YOLO26{scale}"):
                    YoloDetector(Path("other.pt"), "cpu", 0.05, model_name=f"yolo26{scale}")

    def test_requested_scale_cannot_silently_load_different_checkpoint(self):
        with self.assertRaisesRegex(ValueError, "YOLO26s"):
            YoloDetector(Path("misnamed-s.pt"), "cpu", 0.3, model_name="yolo26s")
        self.architecture.update(yaml_file="yolo26s.yaml", scale="s")
        with self.assertRaisesRegex(ValueError, "YOLO26n"):
            YoloDetector(Path("misnamed-n.pt"), "cpu", 0.3)

    def test_large_checkpoint_and_full_width_metadata(self):
        for yaml_file in ("yolo26l.yaml", "models/26/yolo26.yaml"):
            with self.subTest(yaml_file=yaml_file):
                self.architecture.update(yaml_file=yaml_file, scale="l")
                detector = YoloDetector(Path("renamed.pt"), "cpu", 0.05,
                                        model_name="yolo26l", input_size=2560)
                self.assertEqual(detector.metadata["model"], "yolo26l")
                self.assertEqual(detector.metadata["architecture_scale"], "l")
                self.assertEqual(detector.metadata["input_size"], [2560, 2560])
                self.assertIn("2560x2560", detector.metadata["preprocessing"])

    def test_large_scale_mismatch_fails_in_both_directions(self):
        for scale in ("n", "s", "m"):
            with self.subTest(scale=scale):
                self.architecture.update(yaml_file=f"yolo26{scale}.yaml", scale=scale)
                with self.assertRaisesRegex(ValueError, "YOLO26l"):
                    YoloDetector(Path("l.pt"), "cpu", 0.05, model_name="yolo26l")
                self.architecture.update(yaml_file="yolo26l.yaml", scale="l")
                with self.assertRaisesRegex(ValueError, f"YOLO26{scale}"):
                    YoloDetector(Path("other.pt"), "cpu", 0.05, model_name=f"yolo26{scale}")

    def test_rejects_wrong_or_missing_architecture_before_prediction(self):
        for field, value in (("yaml_file", "yolo11n.yaml"), ("scale", "l"), ("nc", 2),
                             ("end2end", False), ("reg_max", 16), ("yaml_file", "")):
            original = self.architecture[field]
            with self.subTest(field=field, value=value), self.assertRaisesRegex(ValueError, "YOLO26n"):
                self.architecture[field] = value
                YoloDetector(Path("weights.pt"), "cpu", 0.3)
            self.architecture[field] = original

    def test_rejects_pose_even_when_filename_says_yolo26n(self):
        self.model.task = "pose"
        with self.assertRaisesRegex(ValueError, "detection checkpoint"):
            YoloDetector(Path("yolo26n.pt"), "cpu", 0.3)


class DFineAdapterTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name).resolve()
        self.config = self.repo / "configs/dfine/dfine_hgnetv2_n_coco.yml"
        self.config.parent.mkdir(parents=True)
        self.config.touch()
        self.core_file = self.repo / "src/core/__init__.py"
        self.core_file.parent.mkdir(parents=True)
        self.core_file.touch()
        self.weights = self.repo / "weights.pth"
        self.weights.touch()

        def deployable():
            module = MagicMock()
            for method in ("deploy", "to", "float", "eval"):
                getattr(module, method).return_value = module
            return module

        self.model, self.postprocessor = deployable(), deployable()
        self.model.decoder._generate_anchors.return_value = (object(), object())
        self.cfg = SimpleNamespace(
            yaml_cfg={"HGNetv2": {"pretrained": True}, "num_classes": 80, "eval_spatial_size": [320, 320]},
            model=self.model, postprocessor=self.postprocessor,
        )
        self.core = SimpleNamespace(__file__=str(self.core_file), YAMLConfig=MagicMock(return_value=self.cfg))
        self.torch, self.transforms, self.image = MagicMock(), MagicMock(), MagicMock()
        self.torch.__version__ = "test"
        self.state = {"weights": "state"}
        self.torch.load.return_value = {"ema": {"module": self.state}}
        imports = patch.dict(sys.modules, {
            "torch": self.torch,
            "torchvision": SimpleNamespace(transforms=self.transforms),
            "torchvision.transforms": self.transforms,
            "PIL": SimpleNamespace(Image=self.image),
        })
        imports.start()
        self.addCleanup(imports.stop)
        self.import_core = patch("detectors.importlib.import_module", return_value=self.core)
        self.core_import = self.import_core.start()
        self.addCleanup(self.import_core.stop)

    def create(self, input_size=640):
        return DFineDetector(self.weights, "cpu", 0.3, self.repo, input_size=input_size)

    def test_loads_ema_safely_and_deploys_native_fp32_modules(self):
        path_before = list(sys.path)
        detector = self.create()
        self.assertEqual(sys.path, path_before)
        self.torch.load.assert_called_once_with(str(self.weights), map_location="cpu", weights_only=True)
        self.model.load_state_dict.assert_called_once_with(self.state)
        self.assertFalse(self.cfg.yaml_cfg["HGNetv2"]["pretrained"])
        self.assertEqual(self.cfg.yaml_cfg["eval_spatial_size"], [640, 640])
        for module in (self.model, self.postprocessor):
            module.deploy.assert_called_once_with()
            module.to.assert_called_once_with("cpu")
            module.float.assert_called_once_with()
            module.eval.assert_called_once_with()
        self.transforms.Resize.assert_called_once_with((640, 640))
        self.transforms.ToTensor.assert_called_once_with()
        self.assertEqual(detector.metadata["config"], str(self.config))
        self.assertEqual(detector.metadata["repo"], str(self.repo))
        self.model.encoder._reset_parameters.assert_not_called()
        self.model.decoder._generate_anchors.assert_not_called()

    def test_larger_input_rebuilds_geometry_after_strict_load_before_deploy(self):
        events = []
        self.model.load_state_dict.side_effect = lambda state: events.append("load")
        self.model.encoder._reset_parameters.side_effect = lambda: events.append("position")
        anchors, mask = object(), object()
        def generate():
            events.append("anchors")
            self.assertEqual(self.model.decoder.eval_spatial_size, [1280, 1280])
            return anchors, mask
        self.model.decoder._generate_anchors.side_effect = generate
        self.model.deploy.side_effect = lambda: events.append("deploy") or self.model
        detector = self.create(input_size=1280)
        self.assertEqual(events, ["load", "position", "anchors", "deploy"])
        self.model.load_state_dict.assert_called_once_with(self.state)
        self.assertEqual(self.cfg.yaml_cfg["eval_spatial_size"], [640, 640])
        self.assertEqual(self.model.encoder.eval_spatial_size, [1280, 1280])
        self.assertIs(self.model.decoder.anchors, anchors)
        self.assertIs(self.model.decoder.valid_mask, mask)
        self.transforms.Resize.assert_called_once_with((1280, 1280))
        self.assertEqual(detector.metadata["input_size"], [1280, 1280])
        self.assertIn("1280x1280", detector.metadata["preprocessing"])

    def test_larger_input_does_not_relax_checkpoint_validation(self):
        self.model.load_state_dict.side_effect = RuntimeError("state shape mismatch")
        with self.assertRaisesRegex(RuntimeError, "state shape mismatch"):
            self.create(input_size=1280)
        self.model.encoder._reset_parameters.assert_not_called()
        self.model.decoder._generate_anchors.assert_not_called()
        self.model.deploy.assert_not_called()

    def test_geometry_rebuild_failure_prevents_deploy(self):
        self.model.decoder._generate_anchors.side_effect = RuntimeError("geometry failed")
        with self.assertRaisesRegex(RuntimeError, "geometry failed"):
            self.create(input_size=1280)
        self.model.deploy.assert_not_called()

    def test_loads_model_state_when_ema_is_absent(self):
        self.torch.load.return_value = {"model": self.state}
        self.create()
        self.model.load_state_dict.assert_called_once_with(self.state)

    def test_predict_scales_original_width_height_and_maps_contiguous_ball_id(self):
        def tensor(values):
            return SimpleNamespace(cpu=lambda: SimpleNamespace(tolist=lambda: values))

        self.postprocessor.return_value = (
            [tensor([0, 32, 37])], [tensor([[0, 0, 100, 50], [40, 20, 60, 30], [0, 0, 10, 10]])],
            [tensor([0.8, 0.9, 0.9])],
        )
        detector = self.create(input_size=1280)
        rgb = SimpleNamespace(shape=(50, 100, 3))
        self.assertEqual(detector.predict(rgb), [
            {"class": "player", "confidence": 0.8, "bbox": [0.0, 0.0, 1.0, 1.0]},
            {"class": "football", "confidence": 0.9, "bbox": [0.4, 0.4, 0.6, 0.6]},
        ])
        self.torch.tensor.assert_called_once_with([[100, 50]], device="cpu")
        self.image.fromarray.assert_called_once_with(rgb)
        self.torch.inference_mode.return_value.__enter__.assert_called_once_with()
        self.postprocessor.assert_called_once_with(self.model.return_value, self.torch.tensor.return_value)

    def test_rejects_missing_config_or_source_before_loading_weights(self):
        for path in (self.config, self.core_file):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, "official D-FINE checkout"):
                path.unlink()
                self.create()
            path.touch()
        self.torch.load.assert_not_called()

    def test_rejects_non_coco_config_before_loading_weights(self):
        self.cfg.yaml_cfg["num_classes"] = 2
        with self.assertRaisesRegex(ValueError, "80-class COCO"):
            self.create()
        self.torch.load.assert_not_called()

    def test_rejects_src_package_collision_and_restores_import_path(self):
        self.core.__file__ = str(self.repo.parent / "unrelated/src/core/__init__.py")
        path_before = list(sys.path)
        with self.assertRaisesRegex(RuntimeError, "fresh Python process"):
            self.create()
        self.assertEqual(sys.path, path_before)
        self.torch.load.assert_not_called()

    def test_missing_upstream_dependency_does_not_leak_import_path(self):
        self.core_import.side_effect = ImportError("missing dependency")
        path_before = list(sys.path)
        with self.assertRaisesRegex(ImportError, "missing dependency"):
            self.create()
        self.assertEqual(sys.path, path_before)

    def test_restricted_load_failure_never_retries_unsafe_deserialization(self):
        self.torch.load.side_effect = RuntimeError("unsupported pickle")
        with self.assertRaisesRegex(RuntimeError, "unsupported pickle"):
            self.create()
        self.torch.load.assert_called_once_with(str(self.weights), map_location="cpu", weights_only=True)
        self.model.load_state_dict.assert_not_called()

    def test_incompatible_state_fails_before_deploying(self):
        self.model.load_state_dict.side_effect = RuntimeError("state shape mismatch")
        with self.assertRaisesRegex(RuntimeError, "state shape mismatch"):
            self.create()
        self.model.deploy.assert_not_called()


class RepositoryStateTests(unittest.TestCase):
    def test_directory_without_git_never_inherits_parent_revision(self):
        with tempfile.TemporaryDirectory() as directory, patch("detectors.subprocess.run") as run:
            self.assertEqual(repo_state(Path(directory)), {"revision": None, "dirty": None})
            run.assert_not_called()

    def test_records_revision_and_clean_or_dirty_worktree(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            (repo / ".git").touch()
            for status in ("", " M detectors.py\n"):
                with self.subTest(status=status), patch("detectors.subprocess.run", side_effect=[
                    SimpleNamespace(stdout="abc123\n"), SimpleNamespace(stdout=status),
                ]):
                    self.assertEqual(repo_state(repo), {"revision": "abc123", "dirty": bool(status)})

    def test_git_failure_is_reported_as_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            (repo / ".git").touch()
            with patch("detectors.subprocess.run", side_effect=subprocess.TimeoutExpired("git", 5)):
                self.assertEqual(repo_state(repo), {"revision": None, "dirty": None})


if __name__ == "__main__":
    unittest.main()
