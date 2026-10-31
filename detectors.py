"""Native detector adapters; output boxes use original-image coordinates in [0, 1]."""

from __future__ import annotations

import importlib
import math
from numbers import Real
from pathlib import Path
import subprocess
import sys


CLASS_NAMES = {"person": "player", "sports ball": "football"}
DFINE_CLASSES = {0: "player", 32: "football"}


def normalize_detections(labels, boxes, scores, width, height, classes, confidence):
    """Validate model output and retain the two football benchmark classes."""
    if any(not isinstance(size, Real) or not math.isfinite(size) or size <= 0 for size in (width, height)):
        raise ValueError("Image dimensions must be finite and positive")
    if not len(labels) == len(boxes) == len(scores):
        raise ValueError("Detector labels, boxes and scores have different lengths")
    detections = []
    for label, box, score in zip(labels, boxes, scores):
        values = [label, score, *box]
        if len(box) != 4 or any(
            isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value)
            for value in values
        ):
            raise ValueError("Detector output must contain finite numeric labels, scores and xyxy boxes")
        if int(label) != label or label < 0 or not 0 <= score <= 1:
            raise ValueError("Detector class IDs must be non-negative integers and scores must be in [0, 1]")
        if label not in classes or score < confidence:
            continue
        normalized = [
            min(1.0, max(0.0, float(value) / size))
            for value, size in zip(box, (width, height, width, height))
        ]
        if normalized[0] >= normalized[2] or normalized[1] >= normalized[3]:
            continue
        detections.append({"class": classes[label], "confidence": float(score), "bbox": normalized})
    return detections


def yolo_classes(model):
    if model.task != "detect":
        raise ValueError("YOLO benchmark requires a detection checkpoint, not a pose or other task checkpoint")
    names = model.names
    if isinstance(names, list):
        names = dict(enumerate(names))
    classes = {index: CLASS_NAMES[name] for index, name in names.items() if name in CLASS_NAMES}
    if set(classes.values()) != {"player", "football"}:
        raise ValueError("YOLO checkpoint must include both 'person' and 'sports ball' classes")
    return classes


class YoloDetector:
    def __init__(self, weights, device, confidence, model_name="yolo26n", input_size=640):
        import torch
        import ultralytics

        self.model = ultralytics.YOLO(str(weights), task="detect")
        self.classes = yolo_classes(self.model)
        architecture = self.model.model.yaml
        config_name = Path(architecture.get("yaml_file", "")).name
        scale = {"yolo26n": "n", "yolo26s": "s", "yolo26m": "m", "yolo26l": "l"}[model_name]
        if (
            config_name not in {"yolo26.yaml", f"{model_name}.yaml"}
            or architecture.get("scale") != scale
            or architecture.get("nc") != 80
            or architecture.get("end2end") is not True
            or architecture.get("reg_max") != 1
        ):
            raise ValueError(f"YOLO benchmark requires an 80-class YOLO26{scale} detection checkpoint")
        # A torch.device prevents Ultralytics from remapping CUDA indices or changing CPU threads.
        self.device = torch.device(device)
        self.confidence = confidence
        self.input_size = input_size
        self.metadata = {
            "model": model_name, "runtime": "ultralytics", "runtime_version": ultralytics.__version__,
            "architecture_config": config_name, "architecture_scale": architecture["scale"],
            "parameter_count": sum(parameter.numel() for parameter in self.model.model.parameters()),
            "input_size": [input_size, input_size], "batch_size": 1, "precision": "float32",
            "preprocessing": f"RGB input; Ultralytics square letterbox to {input_size}x{input_size}; scale to [0,1]",
            "postprocessing": "native detection output; score strictly above saved floor; max_det=300; person and sports ball only",
        }

    def predict(self, rgb):
        # Ultralytics interprets numpy inputs as BGR.
        result = self.model.predict(
            source=rgb[:, :, ::-1].copy(), imgsz=self.input_size, rect=False, device=self.device,
            conf=self.confidence, half=False, max_det=300, classes=list(self.classes), verbose=False,
        )[0]
        boxes = result.boxes
        return normalize_detections(
            boxes.cls.cpu().tolist(), boxes.xyxy.cpu().tolist(), boxes.conf.cpu().tolist(),
            rgb.shape[1], rgb.shape[0], self.classes, self.confidence,
        )


def repo_state(repo):
    if not (repo / ".git").exists():
        return {"revision": None, "dirty": None}
    try:
        revision = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "-C", str(repo), "status", "--porcelain"], check=True, capture_output=True, text=True, timeout=5,
        ).stdout
        return {"revision": revision, "dirty": bool(status)}
    except (OSError, subprocess.SubprocessError):
        return {"revision": None, "dirty": None}


class DFineDetector:
    def __init__(self, weights, device, confidence, repo, input_size=640):
        config = repo / "configs/dfine/dfine_hgnetv2_n_coco.yml"
        if not config.is_file() or not (repo / "src/core/__init__.py").is_file():
            raise ValueError("--dfine-repo must point to an official D-FINE checkout containing the N COCO config")
        import torch
        import torchvision.transforms as transforms
        from PIL import Image

        sys.path.insert(0, str(repo))
        try:
            core = importlib.import_module("src.core")
        finally:
            sys.path.pop(0)
        if not Path(core.__file__).resolve().is_relative_to(repo):
            raise RuntimeError("Another 'src' package is already imported; run D-FINE in a fresh Python process")
        cfg = core.YAMLConfig(str(config), resume=str(weights))
        cfg.yaml_cfg["HGNetv2"]["pretrained"] = False
        cfg.yaml_cfg["eval_spatial_size"] = [640, 640]
        if cfg.yaml_cfg.get("num_classes") != 80:
            raise ValueError("D-FINE benchmark requires the official 80-class COCO configuration")
        checkpoint = torch.load(str(weights), map_location="cpu", weights_only=True)
        state = checkpoint["ema"]["module"] if "ema" in checkpoint else checkpoint["model"]
        cfg.model.load_state_dict(state)
        if input_size != 640:
            # Load strictly at the checkpoint's size, then rebuild only derived geometry.
            cfg.model.encoder.eval_spatial_size = [input_size, input_size]
            cfg.model.encoder._reset_parameters()  # Pinned upstream: positional embeddings only.
            cfg.model.decoder.eval_spatial_size = [input_size, input_size]
            cfg.model.decoder.anchors, cfg.model.decoder.valid_mask = cfg.model.decoder._generate_anchors()
        self.model = cfg.model.deploy().to(device).float().eval()
        self.postprocessor = cfg.postprocessor.deploy().to(device).float().eval()
        self.transform = transforms.Compose([transforms.Resize((input_size, input_size)), transforms.ToTensor()])
        self.Image = Image
        self.torch = torch
        self.device = device
        self.confidence = confidence
        self.metadata = {
            "model": "dfine-n", "runtime": "pytorch", "runtime_version": torch.__version__,
            "input_size": [input_size, input_size], "batch_size": 1, "precision": "float32",
            "preprocessing": f"RGB input; PIL bilinear stretch to {input_size}x{input_size}; scale to [0,1]",
            "postprocessing": "native deploy postprocessor; top 300 queries; contiguous COCO IDs 0 and 32",
            "config": str(config), "repo": str(repo), **repo_state(repo),
        }

    def predict(self, rgb):
        width, height = rgb.shape[1], rgb.shape[0]
        with self.torch.inference_mode():
            image = self.transform(self.Image.fromarray(rgb)).unsqueeze(0).to(self.device)
            size = self.torch.tensor([[width, height]], device=self.device)
            labels, boxes, scores = self.postprocessor(self.model(image), size)
        return normalize_detections(
            labels[0].cpu().tolist(), boxes[0].cpu().tolist(), scores[0].cpu().tolist(),
            width, height, DFINE_CLASSES, self.confidence,
        )


def load_detector(model_name, weights: Path, device: str, confidence: float, dfine_repo: Path | None = None,
                  input_size: int = 640):
    weights = Path(weights).resolve()
    if not weights.is_file():
        raise ValueError(f"Checkpoint does not exist: {weights}. Download the documented weights first.")
    if device != "cpu" and device != "cuda" and not (device.startswith("cuda:") and device[5:].isdigit()):
        raise ValueError("Device must be cpu, cuda or cuda:N; MPS is not part of this baseline")
    if not math.isfinite(confidence) or not 0 <= confidence <= 1:
        raise ValueError("Confidence must be finite and in [0, 1]")
    if type(input_size) is not int or input_size not in (640, 1280, 1920, 2560):
        raise ValueError("Input size must be 640, 1280, 1920 or 2560 pixels")
    if model_name in ("yolo26n", "yolo26s", "yolo26m", "yolo26l"):
        if weights.suffix != ".pt":
            raise ValueError("YOLO native benchmarking requires a local .pt checkpoint")
        return YoloDetector(weights, device, confidence, model_name=model_name, input_size=input_size)
    if model_name == "dfine-n":
        if input_size not in (640, 1280):
            raise ValueError("D-FINE supports only 640 or 1280 inputs in this benchmark")
        if dfine_repo is None:
            raise ValueError("D-FINE requires --dfine-repo pointing to its official source checkout")
        return DFineDetector(weights, device, confidence, Path(dfine_repo).resolve(), input_size=input_size)
    raise ValueError(f"Unsupported detector: {model_name}")
