"""Export frame-exact, silent review clips from constant-frame-rate footage."""

import argparse
from contextlib import closing
from datetime import datetime, timezone
from fractions import Fraction
from importlib import metadata
import json
from pathlib import Path
import re
import sys

from benchmark import positive_int, sha256_file, video_frames, write_manifest
from evaluate import _integer, _json


def validate_windows(windows):
    """Keep filenames safe and require ordered, disjoint [start, stop) ranges."""
    if not isinstance(windows, list) or not windows:
        raise ValueError('Windows must be a nonempty array')
    ids, previous_stop = set(), 0
    for window in windows:
        if not isinstance(window, dict) or set(window) != {'id', 'start_frame', 'stop_frame'}:
            raise ValueError('Each window needs only id, start_frame and stop_frame')
        name = window['id']
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', name):
            raise ValueError('Window id must be 1–64 filename-safe letters, digits, underscores or hyphens')
        if name.casefold() in ids:
            raise ValueError('Window ids must be unique, including on case-insensitive filesystems')
        ids.add(name.casefold())
        start, stop = window['start_frame'], window['stop_frame']
        if not _integer(start) or not _integer(stop, 1) or stop <= start:
            raise ValueError('Window frames must be integers with 0 <= start < stop')
        if start < previous_stop:
            raise ValueError('Windows must be ordered and non-overlapping; merge overlapping review windows')
        previous_stop = stop


def export_review_clips(video, output, windows, *, fps):
    import av

    video, output = Path(video), Path(output)
    if not video.is_file():
        raise ValueError(f'Video does not exist: {video}')
    validate_windows(windows)
    if not _integer(fps, 1) or fps > 240:
        raise ValueError('FPS must be an integer from 1 to 240')
    output.mkdir(parents=True, exist_ok=False)
    manifest = {
        'schema_version': 1, 'kind': 'review_clips', 'status': 'running',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'human_reviewed': False, 'video': {'path': str(video.resolve())},
        'encoding': {'library': 'PyAV', 'version': metadata.version('av'),
                     'codec': 'libx264', 'pixel_format': 'yuv420p', 'crf': 18,
                     'preset': 'fast', 'fps': fps, 'audio': False, 'resize': False},
        'windows': windows, 'clips': [],
    }
    write_manifest(output, manifest)
    try:
        manifest['video']['sha256'] = sha256_file(video)
        # shortcut: reject VFR/fractional rates instead of retiming evidence; add a PTS-preserving path when needed.
        with closing(video_frames(video, 1, windows[-1]['stop_frame'])) as decoded:
            for window in windows:
                path = output / (window['id'] + '.mp4')
                count, stream, first = 0, None, None
                with av.open(str(path), 'w', options={'movflags': '+faststart'}) as destination:
                    for index, timestamp, source_time, rgb in decoded:
                        if abs(timestamp - index * 1000 / fps) > 0.001:
                            raise ValueError('Source timestamps do not match the requested constant FPS')
                        if index < window['start_frame']:
                            continue
                        height, width = rgb.shape[:2]
                        if width % 2 or height % 2:
                            raise ValueError('Review MP4 requires even dimensions; source is not resized')
                        if stream is None:
                            stream = destination.add_stream('libx264', rate=fps)
                            stream.width, stream.height, stream.pix_fmt = width, height, 'yuv420p'
                            stream.options = {'crf': '18', 'preset': 'fast'}
                            stream.thread_count = 4
                            first = (timestamp, source_time)
                        if (width, height) != (stream.width, stream.height):
                            raise ValueError('Source dimensions changed within a clip')
                        frame = av.VideoFrame.from_ndarray(rgb, format='rgb24')
                        frame.pts, frame.time_base = count, Fraction(1, fps)
                        for packet in stream.encode(frame):
                            destination.mux(packet)
                        count += 1
                        if index + 1 == window['stop_frame']:
                            break
                    if count != window['stop_frame'] - window['start_frame']:
                        raise ValueError(f"Source ended before window {window['id']} was complete")
                    for packet in stream.encode():
                        destination.mux(packet)
                manifest['clips'].append({
                    **window, 'file_name': path.name, 'frames': count,
                    'start_ms': first[0], 'source_start_time_ms': first[1],
                    'stop_ms': window['stop_frame'] * 1000 / fps,
                    'width': width, 'height': height, 'sha256': sha256_file(path),
                })
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
    parser.add_argument('--windows', type=Path, required=True, help='JSON array of id/start_frame/stop_frame; stop is exclusive')
    parser.add_argument('--output', type=Path, required=True, help='New directory; never overwritten')
    parser.add_argument('--fps', type=positive_int, required=True, help='Actual integer source FPS; verified against decoded timestamps')
    args = parser.parse_args(argv)
    try:
        manifest = export_review_clips(args.video, args.output, _json(args.windows.read_text()), fps=args.fps)
    except KeyboardInterrupt:
        print('Review clip export interrupted.', file=sys.stderr)
        return 130
    except Exception as error:
        print(f'Review clip export failed: {error}', file=sys.stderr)
        return 1
    print(json.dumps({'manifest': str(args.output / 'manifest.json'), 'clips': len(manifest['clips'])}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
