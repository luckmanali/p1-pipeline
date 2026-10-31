"""Evaluate saved detector boxes against explicitly labelled video frames."""

import argparse
import hashlib
import json
import math
from pathlib import Path


CLASSES = ("player", "football")


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def _integer(value, minimum=0):
    return type(value) is int and value >= minimum


def _reject_constant(value):
    raise ValueError(f"Non-finite JSON number: {value}")


def _finite_float(value):
    result = float(value)
    if not math.isfinite(result):
        _reject_constant(value)
    return result


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _json(text):
    return json.loads(text, parse_constant=_reject_constant, parse_float=_finite_float,
                      object_pairs_hook=_unique_object)


def _sha256(value):
    return isinstance(value, str) and len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )


def _boxes(items, context, predictions=False):
    _require(isinstance(items, list), f"{context} must be an array")
    for item in items:
        _require(isinstance(item, dict), f"{context}: box must be an object")
        _require(item.get("class") in CLASSES, f"{context}: unknown class")
        bbox = item.get("bbox")
        _require(
            isinstance(bbox, list) and len(bbox) == 4
            and all(_number(value) and 0 <= value <= 1 for value in bbox),
            f"{context}: bbox must contain four finite normalized coordinates",
        )
        _require(bbox[0] < bbox[2] and bbox[1] < bbox[3]
                 and (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]) > 0,
                 f"{context}: bbox must have positive area")
        if predictions:
            confidence = item.get("confidence")
            _require(_number(confidence) and 0 <= confidence <= 1,
                     f"{context}: confidence must be between 0 and 1")
    return items


def box_iou(left, right):
    intersection = max(0, min(left[2], right[2]) - max(left[0], right[0])) * max(
        0, min(left[3], right[3]) - max(left[1], right[1])
    )
    left_area = (left[2] - left[0]) * (left[3] - left[1])
    right_area = (right[2] - right[0]) * (right[3] - right[1])
    return intersection / (left_area + right_area - intersection)


def _cross(start, end, point):
    return ((end[0] - start[0]) * (point[1] - start[1])
            - (end[1] - start[1]) * (point[0] - start[0]))


def validate_scope(scope):
    """Validate a fixed-camera main-match region in original normalized coordinates."""
    _require(isinstance(scope, dict) and set(scope) == {"type", "polygon"}
             and scope["type"] == "main_pitch", "Invalid evaluation_scope")
    polygon = scope["polygon"]
    _require(isinstance(polygon, list) and len(polygon) >= 3
             and all(isinstance(point, list) and len(point) == 2
                     and all(_number(v) and 0 <= v <= 1 for v in point) for point in polygon),
             "Scope polygon needs at least three finite normalized xy points")
    _require(len({tuple(point) for point in polygon}) == len(polygon),
             "Scope polygon vertices must be unique; do not repeat the closing vertex")
    edges = list(zip(polygon, polygon[1:] + polygon[:1]))
    area = sum(a[0] * b[1] - b[0] * a[1] for a, b in edges)
    _require(abs(area) > 1e-12, "Scope polygon must have positive area")
    orientation = 1 if area > 0 else -1
    # Every vertex on the same side of every edge also rejects self-intersecting stars.
    _require(all(orientation * _cross(a, b, p) >= -1e-12
                 for a, b in edges for p in polygon),
             "Scope polygon must be convex, with vertices in boundary order")
    return scope


def in_scope(item, scope):
    """Persons use bottom-centre; balls use centre. Boundary points are included."""
    x1, y1, x2, y2 = item["bbox"]
    point = ((x1 + x2) / 2, y2 if item["class"] == "player" else (y1 + y2) / 2)
    polygon = scope["polygon"]
    sides = [_cross(a, b, point) for a, b in zip(polygon, polygon[1:] + polygon[:1])]
    return all(v >= -1e-12 for v in sides) or all(v <= 1e-12 for v in sides)


def evaluate(run_dir, labels_path, iou=0.5, confidence=0.25):
    _require(_number(iou) and 0 < iou <= 1, "IoU threshold must be in (0, 1]")
    _require(_number(confidence) and 0 <= confidence <= 1,
             "Confidence threshold must be in [0, 1]")
    run_dir = Path(run_dir)
    manifest = _json((run_dir / "manifest.json").read_text())
    _require(isinstance(manifest, dict) and type(manifest.get("schema_version")) is int
             and manifest["schema_version"] == 1, "Unsupported manifest schema")
    _require(manifest.get("status") == "completed", "Run must have status completed")
    video = manifest.get("video")
    _require(isinstance(video, dict) and _sha256(video.get("sha256")),
             "Manifest must contain video.sha256")
    sampling = manifest.get("sampling")
    _require(isinstance(sampling, dict) and _integer(sampling.get("stride"), 1)
             and "max_frames" in sampling and (sampling["max_frames"] is None
             or _integer(sampling["max_frames"], 1)), "Invalid manifest sampling")
    _require("model" in manifest, "Manifest must contain model metadata")
    inference = manifest.get("inference")
    _require(isinstance(inference, dict) and _number(inference.get("confidence"))
             and 0 <= inference["confidence"] <= 1,
             "Manifest must contain an inference confidence threshold in [0, 1]")
    _require(confidence >= inference["confidence"],
             "Evaluation confidence cannot be lower than the saved inference threshold")

    labels_bytes = Path(labels_path).read_bytes()
    labels = _json(labels_bytes)
    _require(isinstance(labels, dict) and type(labels.get("schema_version")) is int
             and labels["schema_version"] in (1, 2), "Unsupported labels schema")
    scope = None
    if labels["schema_version"] == 2:
        scope = validate_scope(labels.get("evaluation_scope"))
    else:
        _require("evaluation_scope" not in labels, "Scoped labels require schema_version 2")
    _require(_sha256(labels.get("video_sha256")), "Labels must contain video_sha256")
    _require(labels["video_sha256"] == video["sha256"], "Labels refer to a different video")
    _require(isinstance(labels.get("frames"), list), "Label frames must be an array")
    _require(labels["frames"], "At least one explicitly labelled frame is required")
    labelled_frames = {}
    for frame in labels["frames"]:
        _require(isinstance(frame, dict) and _integer(frame.get("frame_index")),
                 "Labels must contain a nonnegative integer frame_index")
        index = frame["frame_index"]
        _require(index not in labelled_frames, f"Duplicate labelled frame: {index}")
        labelled_frames[index] = _boxes(frame.get("annotations"), f"Labels frame {index}")
        if scope is not None:
            _require(all(in_scope(item, scope) for item in labelled_frames[index]),
                     f"Labels frame {index}: annotation outside evaluation scope; review labels/region")

    predictions = {}
    processed_frames = set()
    with (run_dir / "detections.jsonl").open() as source:
        for line_number, line in enumerate(source, 1):
            frame = _json(line)
            context = f"Detections line {line_number}"
            _require(isinstance(frame, dict) and _integer(frame.get("frame_index")),
                     f"{context}: nonnegative integer frame_index required")
            index = frame["frame_index"]
            _require(index not in processed_frames, f"Duplicate detection frame: {index}")
            _require(_integer(frame.get("width"), 1) and _integer(frame.get("height"), 1),
                     f"{context}: positive integer width and height required")
            _require(_number(frame.get("timestamp_ms")) and frame["timestamp_ms"] >= 0,
                     f"{context}: finite nonnegative timestamp_ms required")
            boxes = _boxes(frame.get("detections"), context, predictions=True)
            processed_frames.add(index)
            if index in labelled_frames:
                predictions[index] = boxes
    missing = labelled_frames.keys() - processed_frames
    _require(not missing, f"Labelled frames missing from run: {sorted(missing)}")

    metrics = {}
    excluded = {name: 0 for name in CLASSES}
    for name in CLASSES:
        tp = fp = fn = 0
        for index, annotations in labelled_frames.items():
            unmatched = [item["bbox"] for item in annotations if item["class"] == name]
            selected = sorted(
                (item for item in predictions[index]
                 if item["class"] == name and item["confidence"] >= confidence),
                key=lambda item: item["confidence"], reverse=True,
            )
            for detection in selected:
                if scope is not None and not in_scope(detection, scope):
                    excluded[name] += 1
                    continue
                overlaps = [box_iou(detection["bbox"], box) for box in unmatched]
                if overlaps and max(overlaps) >= iou:
                    unmatched.pop(overlaps.index(max(overlaps)))
                    tp += 1
                else:
                    fp += 1
            fn += len(unmatched)
        metrics[name] = {
            "tp": tp, "fp": fp, "fn": fn,
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
        }
    report = {
        "schema_version": labels["schema_version"],
        "metric": "bbox_precision_recall",
        "video_sha256": video["sha256"],
        "labels_sha256": hashlib.sha256(labels_bytes).hexdigest(),
        "model": manifest["model"],
        "sampling": sampling,
        "inference_confidence": inference["confidence"],
        "iou_threshold": iou,
        "confidence_threshold": confidence,
        "coverage": {
            "processed_frames": len(processed_frames),
            "labelled_frames": len(labelled_frames),
            "unlabelled_frames": len(processed_frames) - len(labelled_frames),
        },
        "classes": metrics,
    }
    if scope is not None:
        report.update(evaluation_scope=scope, excluded_detections=excluded)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--iou", type=float, default=0.5)
    parser.add_argument("--confidence", type=float, default=0.25)
    args = parser.parse_args()
    try:
        report = evaluate(args.run_dir, args.labels, args.iou, args.confidence)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
