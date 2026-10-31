"""Run one detector over reproducibly sampled video frames; no cloud services."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from importlib import metadata
import json
import math
from pathlib import Path
import platform
import statistics
import sys
import time

from detectors import load_detector, repo_state
from crop_inference import SPATIAL_MODES, SpatialDetector


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def write_manifest(output, manifest):
    temporary = output / 'manifest.tmp'
    temporary.write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n')
    temporary.replace(output / 'manifest.json')


def sample_frames(frames, stride, max_frames=None):
    """Preserve presentation timestamps; stride skips inference, not decoding."""
    if stride < 1 or (max_frames is not None and max_frames < 1):
        raise ValueError('Stride and max-frames must be positive')
    origin = previous = None
    sampled = 0
    for index, frame in enumerate(frames):
        if frame.pts is None or not frame.time_base:
            raise ValueError(f'Frame {index} has no presentation timestamp')
        source_time = float(frame.pts * frame.time_base)
        if not math.isfinite(source_time) or (previous is not None and source_time <= previous):
            raise ValueError(f'Frame {index} has an invalid or non-increasing timestamp')
        if origin is None:
            origin = source_time
        previous = source_time
        if index % stride:
            continue
        yield index, (source_time - origin) * 1000, source_time * 1000, frame
        sampled += 1
        if max_frames is not None and sampled >= max_frames:
            return


def video_frames(path, stride, max_frames=None):
    import av

    with av.open(str(path)) as container:
        if not container.streams.video:
            raise ValueError('Input has no video stream')
        stream = container.streams.video[0]
        if stream.sample_aspect_ratio and float(stream.sample_aspect_ratio) != 1.0:
            raise ValueError('Use square-pixel footage; normalize its display geometry before benchmarking')
        if float(stream.metadata.get('rotate', 0)) % 360:
            raise ValueError('Rotate the video into upright pixels first; see README')
        for index, timestamp, source_time, frame in sample_frames(
            container.decode(stream), stride, max_frames
        ):
            # shortcut: reject display transforms; add verified rotation/mirroring when the dataset needs it.
            if any(side.type.name == 'DISPLAYMATRIX' for side in frame.side_data.values()):
                raise ValueError('Video has a display transform; normalize orientation first (see README)')
            yield index, timestamp, source_time, frame.to_ndarray(format='rgb24')


def latency_summary(seconds):
    ordered = sorted(seconds)
    return {
        'frames': len(ordered),
        'total_seconds': sum(ordered),
        'mean_ms': statistics.mean(ordered) * 1000,
        'median_ms': statistics.median(ordered) * 1000,
        'p95_ms': ordered[math.ceil(len(ordered) * 0.95) - 1] * 1000,
        'frames_per_second': len(ordered) / sum(ordered) if sum(ordered) else None,
    }


def process_frames(frames, detector, output, synchronize, warmup):
    latencies = []
    counts = {'player': 0, 'football': 0}
    first_timestamp = last_timestamp = source_origin = None
    warmup_seconds = 0.0
    with (output / 'detections.jsonl').open('x') as destination:
        for index, timestamp, source_time, rgb in frames:
            if not latencies:
                synchronize()
                start = time.perf_counter()
                for _ in range(warmup):
                    detector.predict(rgb)
                synchronize()
                warmup_seconds = time.perf_counter() - start
                first_timestamp = timestamp
                source_origin = source_time - timestamp
            synchronize()
            start = time.perf_counter()
            detections = detector.predict(rgb)
            synchronize()
            latencies.append(time.perf_counter() - start)
            row = {
                'frame_index': index, 'timestamp_ms': timestamp, 'source_time_ms': source_time,
                'width': int(rgb.shape[1]), 'height': int(rgb.shape[0]), 'detections': detections,
            }
            destination.write(json.dumps(row, allow_nan=False) + '\n')
            for detection in detections:
                counts[detection['class']] += 1
            last_timestamp = timestamp
    if not latencies:
        raise ValueError('Input produced no video frames')
    return {
        'prediction': latency_summary(latencies),
        'warmup_seconds': warmup_seconds,
        'detections_by_class': counts,
        'first_timestamp_ms': first_timestamp,
        'last_timestamp_ms': last_timestamp,
        'source_origin_ms': source_origin,
    }


def benchmark(args):
    spatial_mode = getattr(args, 'spatial_mode', 'native')
    if spatial_mode not in SPATIAL_MODES:
        raise ValueError('Unsupported spatial mode')
    if not args.video.is_file():
        raise ValueError(f'Video does not exist: {args.video}')
    if not args.weights.is_file():
        raise ValueError(f'Checkpoint does not exist: {args.weights}; see README download commands')
    args.output.mkdir(parents=True, exist_ok=False)
    manifest = {
        'schema_version': 1, 'status': 'running',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'video': {'path': str(args.video.resolve())},
        'model': {'name': args.model, 'weights': str(args.weights.resolve())},
        'sampling': {'stride': args.stride, 'max_frames': args.max_frames},
        'inference': {
            'confidence': args.confidence, 'input_size': args.input_size, 'batch_size': 1,
            'precision': 'float32', 'device': args.device, 'warmup_frames': args.warmup,
        },
        'environment': {
            'python': platform.python_version(), 'platform': platform.platform(),
            'machine': platform.machine(),
            'packages': {d.metadata['Name']: d.version for d in metadata.distributions()},
        },
        'pipeline': repo_state(Path(__file__).resolve().parent),
    }
    if spatial_mode != 'native':
        manifest['inference']['spatial_mode'] = spatial_mode
    write_manifest(args.output, manifest)
    start = time.perf_counter()
    try:
        manifest['video']['sha256'] = sha256_file(args.video)
        manifest['model']['sha256'] = sha256_file(args.weights)
        manifest['hashing_seconds'] = time.perf_counter() - start
        start = time.perf_counter()
        import torch

        if args.device.startswith('cuda'):
            if not torch.cuda.is_available():
                raise ValueError('CUDA was requested but is unavailable; select --device cpu')
            torch.cuda.reset_peak_memory_stats(args.device)
            synchronize = lambda: torch.cuda.synchronize(args.device)
            manifest['environment']['gpu'] = torch.cuda.get_device_name(args.device)
        else:
            synchronize = lambda: None
        manifest['environment']['torch_threads'] = torch.get_num_threads()
        detector = load_detector(args.model, args.weights, args.device, args.confidence, args.dfine_repo,
                                 input_size=args.input_size)
        if spatial_mode != 'native':
            detector = SpatialDetector(detector, spatial_mode)
        manifest['model'].update(detector.metadata)
        manifest['load_seconds'] = time.perf_counter() - start
        write_manifest(args.output, manifest)
        start = time.perf_counter()
        measurements = process_frames(
            video_frames(args.video, args.stride, args.max_frames), detector,
            args.output, synchronize, args.warmup,
        )
        measurements['decode_predict_write_seconds'] = time.perf_counter() - start
        if args.device.startswith('cuda'):
            measurements['peak_cuda_allocated_bytes'] = torch.cuda.max_memory_allocated(args.device)
        manifest.update(status='completed', measurements=measurements)
    except (Exception, KeyboardInterrupt) as error:
        manifest.update(status='failed', error=f'{type(error).__name__}: {error}')
        raise
    finally:
        write_manifest(args.output, manifest)
    return manifest


def positive_int(value):
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError('Must be a positive integer')
    return parsed


def confidence(value):
    parsed = float(value)
    if not math.isfinite(parsed) or not 0 <= parsed <= 1:
        raise argparse.ArgumentTypeError('Must be a finite number in [0, 1]')
    return parsed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('video', type=Path)
    parser.add_argument('--model', choices=['yolo26n', 'yolo26s', 'yolo26m', 'yolo26l', 'dfine-n'], required=True)
    parser.add_argument('--weights', type=Path, help='Local checkpoint; default weights/<model checkpoint>')
    parser.add_argument('--dfine-repo', type=Path, default=Path('vendor/D-FINE'))
    parser.add_argument('--output', type=Path, required=True, help='New output directory; never overwritten')
    parser.add_argument('--device', default='cpu', help='cpu, cuda or cuda:N; same device for both runs')
    parser.add_argument('--input-size', type=int, choices=[640, 1280, 1920, 2560], default=640,
                        help='Square input side in pixels; 1920/2560 are YOLO-only; default 640 preserves the baseline')
    parser.add_argument('--spatial-mode', choices=SPATIAL_MODES, default='native',
                        help='native (unchanged), full-1080p, or full frame plus six overlapping ball crops')
    parser.add_argument('--stride', type=positive_int, default=1, help='Infer frames 0, N, 2N, ...; still decode intervening frames')
    parser.add_argument('--max-frames', type=positive_int, help='Maximum sampled frames, excluding warmup')
    parser.add_argument('--confidence', type=confidence, default=0.05, help='Saved detection floor; evaluation may use a higher threshold')
    parser.add_argument('--warmup', type=positive_int, default=3, help='Untimed repeats of first sampled frame')
    args = parser.parse_args(argv)
    if args.weights is None:
        args.weights = Path('weights') / ('dfine_n_coco.pth' if args.model == 'dfine-n' else f'{args.model}.pt')
    try:
        manifest = benchmark(args)
    except KeyboardInterrupt:
        print('Benchmark interrupted; output is marked failed.', file=sys.stderr)
        return 130
    except Exception as error:
        print(f'Benchmark failed: {error}', file=sys.stderr)
        return 1
    print(json.dumps(manifest['measurements'], indent=2, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
