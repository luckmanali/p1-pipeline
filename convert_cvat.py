"""Convert reviewed CVAT COCO rectangles into video-associated benchmark labels."""

import argparse
import hashlib
import json
from pathlib import Path

from evaluate import _boxes, _integer, _json, _number, _require, _sha256, in_scope, validate_scope


CLASS_NAMES = {
    "player": "player", "football": "football",
    "person": "player", "sports ball": "football",
}


def _basename(value):
    _require(isinstance(value, str) and value and "\0" not in value,
             "Image file_name must be a nonempty string")
    name = value.replace("\\", "/").rsplit("/", 1)[-1]
    _require(name not in ("", ".", ".."), "Image file_name must identify a file")
    return name


def _indexed(items, context):
    _require(isinstance(items, list), f"{context} must be an array")
    result = {}
    for item in items:
        _require(isinstance(item, dict) and _integer(item.get("id")),
                 f"{context} must have nonnegative integer IDs")
        _require(item["id"] not in result, f"Duplicate {context} ID: {item['id']}")
        result[item["id"]] = item
    return result


def _export_frames(manifest):
    _require(isinstance(manifest, dict) and type(manifest.get("schema_version")) is int
             and manifest["schema_version"] == 1, "Unsupported frame export schema")
    _require(manifest.get("kind") == "frame_export"
             and manifest.get("status") == "completed", "Frame export must be completed")
    video = manifest.get("video")
    _require(isinstance(video, dict) and _sha256(video.get("sha256"))
             and isinstance(video.get("path"), str) and video["path"],
             "Frame export must contain video path and SHA-256")
    sampling = manifest.get("sampling")
    _require(isinstance(sampling, dict) and "max_frames" in sampling
             and (sampling["max_frames"] is None or _integer(sampling["max_frames"], 1)),
             "Invalid export sampling")
    if sampling.get("mode") == "interval":
        _require(_number(sampling.get("every_seconds")) and sampling["every_seconds"] > 0
                 and "stride" in sampling and sampling["stride"] is None,
                 "Invalid interval sampling")
    else:
        _require(sampling.get("mode") == "stride" and _integer(sampling.get("stride"), 1)
                 and "every_seconds" in sampling and sampling["every_seconds"] is None,
                 "Invalid stride sampling")
    frames = manifest.get("frames")
    _require(isinstance(frames, list) and frames, "Frame export must contain frames")
    _require(sampling["max_frames"] is None or len(frames) <= sampling["max_frames"],
             "Frame export exceeds max_frames")
    by_name, indices = {}, set()
    for frame in frames:
        _require(isinstance(frame, dict) and _integer(frame.get("frame_index")),
                 "Export frame_index must be a nonnegative integer")
        index = frame["frame_index"]
        _require(index not in indices, f"Duplicate exported frame_index: {index}")
        indices.add(index)
        _require(_number(frame.get("timestamp_ms")) and frame["timestamp_ms"] >= 0
                 and _number(frame.get("source_time_ms")), "Invalid export timestamps")
        _require(all(_integer(frame.get(key), 1) and _number(frame[key])
                     for key in ("width", "height")), "Invalid export dimensions")
        _require(_sha256(frame.get("sha256")), "Invalid exported image SHA-256")
        name = _basename(frame.get("file_name"))
        expected = f"frame_{video['sha256'][:12]}_{index:09d}.png"
        _require(frame["file_name"] == f"images/{expected}",
                 "Export filename must match its video hash and frame index")
        by_name[name] = frame
    return by_name


def _rectangle_only(annotation):
    _require(annotation.get("segmentation", []) == [], "Segmentation is unsupported; use rectangles")
    _require(annotation.get("keypoints", []) == [], "Keypoints are unsupported; use rectangles")
    _require(type(annotation.get("num_keypoints", 0)) is int
             and annotation.get("num_keypoints", 0) == 0, "Keypoints are unsupported")
    attributes = annotation.get("attributes", {})
    _require(isinstance(attributes, dict), "Annotation attributes must be an object")
    for values in (annotation, attributes):
        for key, value in values.items():
            normalized = key.strip().lower().replace("-", "_")
            if normalized in ("iscrowd", "is_crowd", "crowd", "ignore", "ignored", "difficult"):
                _require(type(value) in (bool, int) and value == 0,
                         f"Unsupported or ambiguous {key} flag; exclude and document the whole frame")
            if normalized == "rotation":
                _require(_number(value) and value == 0, "Rotated boxes are unsupported")


def convert_cvat(coco_path, manifest_path, *, reviewed=False, scope_path=None):
    """Return validated labels; reviewed asserts all included images were reviewed."""
    _require(reviewed is True, "Confirm all COCO images were reviewed with --reviewed")
    manifest_bytes = Path(manifest_path).read_bytes()
    coco_bytes = Path(coco_path).read_bytes()
    manifest, coco = _json(manifest_bytes), _json(coco_bytes)
    scope_bytes = Path(scope_path).read_bytes() if scope_path is not None else None
    scope = validate_scope(_json(scope_bytes)) if scope_bytes is not None else None
    exported = _export_frames(manifest)
    _require(isinstance(coco, dict), "COCO must be an object")
    images = _indexed(coco.get("images"), "COCO images")
    _require(images, "COCO must include at least one reviewed image")
    categories = _indexed(coco.get("categories"), "COCO categories")
    mapped_categories = {}
    for identifier, category in categories.items():
        name = category.get("name")
        _require(isinstance(name, str) and name in CLASS_NAMES,
                 "Categories must be player/football or person/sports ball")
        mapped = CLASS_NAMES[name]
        _require(mapped not in mapped_categories.values(), f"Duplicate category mapping: {mapped}")
        mapped_categories[identifier] = mapped

    selected, names = {}, set()
    for identifier, image in images.items():
        name = _basename(image.get("file_name"))
        _require(name not in names, f"Duplicate COCO image filename: {name}")
        names.add(name)
        _require(name in exported, f"Unknown exported image: {name}")
        frame = exported[name]
        _require(all(_integer(image.get(key), 1) and image[key] == frame[key]
                     for key in ("width", "height")), f"Dimensions differ for {name}")
        selected[identifier] = {"frame_index": frame["frame_index"], "annotations": []}

    for annotation in _indexed(coco.get("annotations"), "COCO annotations").values():
        image_id, category_id = annotation.get("image_id"), annotation.get("category_id")
        _require(_integer(image_id) and image_id in selected, "Annotation refers to an unknown image")
        _require(_integer(category_id) and category_id in mapped_categories,
                 "Annotation refers to an unknown category")
        _rectangle_only(annotation)
        box = annotation.get("bbox")
        _require(isinstance(box, list) and len(box) == 4 and all(_number(value) for value in box),
                 "COCO bbox must contain four finite xywh coordinates")
        x, y, width, height = box
        image = images[image_id]
        _require(x >= 0 and y >= 0 and width > 0 and height > 0
                 and x + width <= image["width"] and y + height <= image["height"],
                 "COCO bbox must have positive area and stay within the image")
        item = {"class": mapped_categories[category_id], "bbox": [
            x / image["width"], y / image["height"],
            (x + width) / image["width"], (y + height) / image["height"],
        ]}
        _boxes([item], "Converted annotation")
        if scope is not None:
            _require(in_scope(item, scope),
                     f"Annotation {annotation['id']} outside evaluation scope; review labels/region")
        selected[image_id]["annotations"].append(item)

    included = {frame["frame_index"] for frame in selected.values()}
    excluded = sorted(frame["frame_index"] for frame in exported.values()
                      if frame["frame_index"] not in included)
    labels = {
        "schema_version": 2 if scope is not None else 1, "video_sha256": manifest["video"]["sha256"],
        "frames": sorted(selected.values(), key=lambda frame: frame["frame_index"]),
        "provenance": {
            "format": "cvat_coco", "reviewed": True,
            "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
            "coco_sha256": hashlib.sha256(coco_bytes).hexdigest(),
            "exported_frames": len(exported), "included_frames": len(included),
            "excluded_frame_indices": excluded,
        },
    }
    if scope is not None:
        labels["evaluation_scope"] = scope
        labels["provenance"]["scope_sha256"] = hashlib.sha256(scope_bytes).hexdigest()
    return labels


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("coco", type=Path, help="Extracted CVAT COCO instances JSON")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reviewed", action="store_true",
                        help="Confirm every included image was human-reviewed, including empty ones")
    parser.add_argument("--scope", type=Path,
                        help="Reviewed fixed-camera main-pitch polygon JSON; creates scoped v2 labels")
    args = parser.parse_args(argv)
    created = False
    try:
        labels = convert_cvat(args.coco, args.manifest, reviewed=args.reviewed, scope_path=args.scope)
        serialized = json.dumps(labels, indent=2, allow_nan=False) + "\n"
        try:
            with args.output.open("x", encoding="utf-8") as target:
                created = True
                target.write(serialized)
        except BaseException:
            if created:
                args.output.unlink(missing_ok=True)
            raise
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(json.dumps({"output": str(args.output), "labelled_frames": len(labels["frames"]),
                      "excluded_frame_indices": labels["provenance"]["excluded_frame_indices"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
