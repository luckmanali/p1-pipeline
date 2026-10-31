"""Export lossless, indexed video frames for manual detector-benchmark annotation."""

import argparse
from contextlib import closing
from datetime import datetime, timezone
from fractions import Fraction
from importlib import metadata
import json
import math
from pathlib import Path
import sys

from benchmark import positive_int, sha256_file, video_frames, write_manifest
from detectors import repo_state
from evaluate import _integer, _number


def positive_seconds(value):
    seconds = float(value)
    if not _number(seconds) or seconds <= 0 or not _number(seconds * 1000):
        raise argparse.ArgumentTypeError('Seconds must be finite, positive and representable in milliseconds')
    return seconds


def interval_frames(frames, every_seconds):
    """First frame at/after each PTS target; gaps never duplicate an image."""
    if not _number(every_seconds) or every_seconds <= 0 or not _number(every_seconds * 1000):
        raise ValueError('every-seconds must be finite, positive and representable in milliseconds')
    period = every_seconds * 1000
    target = 0.0
    for row in frames:
        timestamp = row[1]
        if timestamp >= target:
            yield row
            # Keep the schedule anchored at zero even when a timestamp gap crosses several targets.
            intervals = timestamp / period
            if math.isfinite(intervals):
                next_interval = math.floor(intervals) + 1
                target = next_interval * period
                # Rounded division can put us on the target we just satisfied.
                if target <= timestamp:
                    target = (next_interval + 1) * period
            if target <= timestamp:
                target = math.nextafter(timestamp, math.inf)


def write_png(path, rgb):
    """Use the existing PyAV runtime; no lossy resize or new image dependency."""
    import av

    encoder = av.CodecContext.create('png', 'w')
    encoder.width, encoder.height = int(rgb.shape[1]), int(rgb.shape[0])
    encoder.pix_fmt = 'rgb24'
    encoder.time_base = Fraction(1)
    packets = encoder.encode(av.VideoFrame.from_ndarray(rgb, format='rgb24')) + encoder.encode(None)
    with Path(path).open('xb') as destination:
        for packet in packets:
            destination.write(bytes(packet))


def export_frames(video, output, *, every_seconds=None, stride=None, max_frames=None):
    video, output = Path(video), Path(output)
    if not video.is_file():
        raise ValueError(f'Video does not exist: {video}')
    if every_seconds is not None and stride is not None:
        raise ValueError('Choose either every-seconds or stride, not both')
    if stride is not None and not _integer(stride, 1):
        raise ValueError('Stride must be a positive integer')
    if max_frames is not None and not _integer(max_frames, 1):
        raise ValueError('max-frames must be a positive integer')
    if stride is None:
        every_seconds = 3.0 if every_seconds is None else every_seconds
        if not _number(every_seconds) or every_seconds <= 0 or not _number(every_seconds * 1000):
            raise ValueError('every-seconds must be finite, positive and representable in milliseconds')
    output.mkdir(parents=True, exist_ok=False)
    manifest = {
        'schema_version': 1, 'kind': 'frame_export', 'status': 'running',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'video': {'path': str(video.resolve())},
        'sampling': {
            'mode': 'stride' if stride is not None else 'interval',
            'every_seconds': every_seconds, 'stride': stride, 'max_frames': max_frames,
        },
        'decoder': {'library': 'PyAV', 'version': metadata.version('av')},
        'pipeline': repo_state(Path(__file__).resolve().parent),
        'frames': [],
    }
    write_manifest(output, manifest)
    try:
        manifest['video']['sha256'] = sha256_file(video)
        (output / 'images').mkdir()
        with closing(video_frames(video, stride or 1)) as decoded:
            selected = decoded if stride is not None else interval_frames(decoded, every_seconds)
            for index, timestamp, source_time, rgb in selected:
                filename = f"images/frame_{manifest['video']['sha256'][:12]}_{index:09d}.png"
                path = output / filename
                write_png(path, rgb)
                manifest['frames'].append({
                    'file_name': filename, 'frame_index': index,
                    'timestamp_ms': timestamp, 'source_time_ms': source_time,
                    'width': int(rgb.shape[1]), 'height': int(rgb.shape[0]),
                    'sha256': sha256_file(path),
                })
                if max_frames is not None and len(manifest['frames']) >= max_frames:
                    break
        if not manifest['frames']:
            raise ValueError('Input produced no video frames')
        manifest['status'] = 'completed'
    except (Exception, KeyboardInterrupt) as error:
        manifest.update(status='failed', error=f'{type(error).__name__}: {error}')
        raise
    finally:
        write_manifest(output, manifest)
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('video', type=Path)
    parser.add_argument('--output', type=Path, required=True, help='New directory for images and manifest; never overwritten')
    sampling = parser.add_mutually_exclusive_group()
    sampling.add_argument('--every-seconds', type=positive_seconds, help='First frame at/after each interval; default 3 seconds')
    sampling.add_argument('--stride', type=positive_int, help='Export frame indices 0, N, 2N, ... instead of time sampling')
    parser.add_argument('--max-frames', type=positive_int, help='Maximum number of exported images')
    args = parser.parse_args(argv)
    try:
        manifest = export_frames(args.video, args.output, every_seconds=args.every_seconds,
                                 stride=args.stride, max_frames=args.max_frames)
    except KeyboardInterrupt:
        print('Frame export interrupted.', file=sys.stderr)
        return 130
    except Exception as error:
        print(f'Frame export failed: {error}', file=sys.stderr)
        return 1
    print(json.dumps({'manifest': str(args.output / 'manifest.json'),
                      'video_sha256': manifest['video']['sha256'],
                      'exported_frames': len(manifest['frames'])}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
