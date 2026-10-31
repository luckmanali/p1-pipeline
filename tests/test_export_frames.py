import argparse
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import av
import numpy as np

from benchmark import process_frames, sha256_file, video_frames
from convert_cvat import main as convert_main
from evaluate import evaluate
from export_frames import export_frames, interval_frames, main, positive_seconds, write_png


class ExportFrameTests(unittest.TestCase):
    def make_video(self, path):
        with av.open(str(path), 'w') as output:
            stream = output.add_stream('libx264', rate=10)
            stream.width, stream.height, stream.pix_fmt = 64, 48, 'yuv420p'
            for index in range(7):
                pixels = np.zeros((48, 64, 3), dtype=np.uint8)
                pixels[:, :, 0] = 200
                pixels[:, :, 1] = index * 20
                for packet in stream.encode(av.VideoFrame.from_ndarray(pixels, format='rgb24')):
                    output.mux(packet)
            for packet in stream.encode():
                output.mux(packet)

    def test_real_video_exports_lossless_rgb_with_matching_indices_times_and_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video, output = root / 'test.mp4', root / 'frames'
            self.make_video(video)
            manifest = export_frames(video, output, every_seconds=0.2, max_frames=3)
            self.assertEqual(manifest['status'], 'completed')
            self.assertEqual(manifest['kind'], 'frame_export')
            self.assertEqual(manifest['video']['sha256'], sha256_file(video))
            self.assertEqual([f['frame_index'] for f in manifest['frames']], [0, 2, 4])
            originals = {row[0]: row for row in video_frames(video, 1)}
            for frame in manifest['frames']:
                png = output / frame['file_name']
                original = originals[frame['frame_index']]
                self.assertEqual(frame['timestamp_ms'], original[1])
                self.assertEqual(frame['source_time_ms'], original[2])
                self.assertEqual((frame['width'], frame['height']), (64, 48))
                self.assertEqual(frame['sha256'], sha256_file(png))
                self.assertIn(manifest['video']['sha256'][:12], png.name)
                with av.open(str(png)) as image:
                    pixels = next(image.decode(video=0)).to_ndarray(format='rgb24')
                np.testing.assert_array_equal(pixels, original[3])
            self.assertEqual(json.loads((output / 'manifest.json').read_text()), manifest)

    def test_stride_export_matches_benchmark_sampling(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / 'test.mp4'
            self.make_video(video)
            result = export_frames(video, root / 'frames', stride=3)
            self.assertEqual([f['frame_index'] for f in result['frames']], [0, 3, 6])
            self.assertEqual(result['sampling'], {'mode': 'stride', 'stride': 3,
                                                'every_seconds': None, 'max_frames': None})

    def test_irregular_times_choose_first_at_or_after_targets_without_duplicate_frames(self):
        times = [0, 1000, 2990, 3010, 6000, 10000, 10100, 12000]
        frames = [(i, timestamp, timestamp + 9000, None) for i, timestamp in enumerate(times)]
        selected = list(interval_frames(frames, 3))
        self.assertEqual([row[0] for row in selected], [0, 3, 4, 5, 7])
        self.assertEqual(selected[0][2], 9000)
        self.assertEqual(list(interval_frames([], 3)), [])

    def test_interval_below_timestamp_precision_does_not_duplicate_frames(self):
        frames = [(i, time, time, None) for i, time in enumerate([0, 1000, 2000])]
        for interval in (1e-300, 1e-320):
            with self.subTest(interval=interval):
                self.assertEqual(list(interval_frames(frames, interval)), frames)

    def test_fractional_interval_advances_past_satisfied_target(self):
        frames = [(i, float(i / 24) * 1000, 0, None) for i in range(122)]
        self.assertEqual([row[0] for row in interval_frames(frames, 1 / 3)],
                         list(range(0, 121, 8)))

    def test_png_writer_is_lossless_and_never_overwrites(self):
        rgb = np.arange(12 * 8 * 3, dtype=np.uint8).reshape((8, 12, 3))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'image.png'
            write_png(path, rgb)
            original = path.read_bytes()
            with self.assertRaises(FileExistsError):
                write_png(path, rgb)
            self.assertEqual(path.read_bytes(), original)
            with av.open(str(path)) as image:
                np.testing.assert_array_equal(next(image.decode(video=0)).to_ndarray(format='rgb24'), rgb)

    def test_invalid_settings_fail_without_creating_output(self):
        cases = [dict(stride=0), dict(stride=True), dict(stride=1.5), dict(max_frames=0),
                 dict(max_frames=True), dict(max_frames=1.5), dict(every_seconds=True),
                 dict(every_seconds=0), dict(every_seconds=-1), dict(every_seconds='3'),
                 dict(every_seconds=float('nan')), dict(every_seconds=float('inf')),
                 dict(every_seconds=1e308), dict(every_seconds=10 ** 308),
                 dict(every_seconds=10 ** 1000), dict(stride=2, every_seconds=3)]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / 'input'
            video.touch()
            for kwargs in cases:
                with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                    export_frames(video, root / 'frames', **kwargs)
                self.assertFalse((root / 'frames').exists())
            with self.assertRaisesRegex(ValueError, 'Video does not exist'):
                export_frames(root / 'missing', root / 'frames')
        for value in ('0', '-1', 'nan', 'inf', '1e308'):
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                positive_seconds(value)
        self.assertEqual(positive_seconds('0.25'), 0.25)
        for value in (0, True, '3', float('nan'), 1e308, 10 ** 308):
            with self.subTest(value=value), self.assertRaises(ValueError):
                list(interval_frames([], value))

    def test_export_cli_to_reviewed_coco_to_evaluation_preserves_subset_and_negative(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video, output = root / 'test.mp4', root / 'frames'
            self.make_video(video)
            script = Path(__file__).resolve().parents[1] / 'export_frames.py'
            result = subprocess.run([sys.executable, str(script), str(video), '--output', str(output),
                                     '--every-seconds', '0.2', '--max-frames', '3'],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['exported_frames'], 3)
            manifest = json.loads((output / 'manifest.json').read_text())
            coco = root / 'instances_default.json'
            coco.write_text(json.dumps({
                'images': [{'id': frame['frame_index'] + 10, 'file_name': Path(frame['file_name']).name,
                            'width': frame['width'], 'height': frame['height']}
                           for frame in reversed(manifest['frames']) if frame['frame_index'] != 2],
                'categories': [{'id': 5, 'name': 'player'}],
                'annotations': [{'id': 99, 'image_id': 10, 'category_id': 5,
                                 'bbox': [0, 0, 32, 24], 'segmentation': [], 'iscrowd': 0}],
            }))
            labels_path = root / 'labels.json'
            with redirect_stdout(io.StringIO()):
                self.assertEqual(convert_main([str(coco), '--manifest', str(output / 'manifest.json'),
                                               '--output', str(labels_path), '--reviewed']), 0)
            labels = json.loads(labels_path.read_text())
            self.assertEqual(labels['provenance']['excluded_frame_indices'], [2])
            self.assertEqual(labels['frames'][1], {'frame_index': 4, 'annotations': []})
            run = root / 'run'
            run.mkdir()
            (run / 'manifest.json').write_text(json.dumps({
                'schema_version': 1, 'status': 'completed', 'video': manifest['video'],
                'sampling': {'stride': 2, 'max_frames': 3}, 'model': {'name': 'test'},
                'inference': {'confidence': 0.05},
            }))
            detector = SimpleNamespace(predict=lambda rgb: [
                {'class': 'player', 'confidence': 0.9, 'bbox': [0, 0, 0.5, 0.5]}])
            process_frames(video_frames(video, 2, 3), detector, run, lambda: None, 0)
            report = evaluate(run, labels_path)
            self.assertEqual(report['classes']['player'],
                             {'tp': 1, 'fp': 1, 'fn': 0, 'precision': 0.5, 'recall': 1})

    def test_limit_one_closes_decoder_without_reading_next_frame_and_defaults_to_three_seconds(self):
        closed = []
        def frames(*args):
            try:
                yield 0, 0, 5000, np.zeros((8, 8, 3), dtype=np.uint8)
                raise AssertionError('Read beyond limit')
            finally:
                closed.append(True)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / 'input'
            video.touch()
            with patch('export_frames.video_frames', side_effect=frames):
                result = export_frames(video, root / 'frames', max_frames=1)
            self.assertEqual(result['sampling']['every_seconds'], 3)
            self.assertEqual(result['frames'][0]['source_time_ms'], 5000)
            self.assertEqual(closed, [True])

    def test_existing_output_is_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video, output = root / 'input', root / 'frames'
            video.touch()
            output.mkdir()
            marker = output / 'manifest.json'
            marker.write_text('preserve me')
            with self.assertRaises(FileExistsError):
                export_frames(video, output)
            self.assertEqual(marker.read_text(), 'preserve me')
            self.assertFalse((output / 'images').exists())

    def test_empty_corrupt_and_interrupted_exports_record_failure(self):
        def empty(*args):
            yield from []
        def interrupted(*args):
            raise KeyboardInterrupt
            yield
        for decoder, error, message in [(empty, ValueError, 'no video frames'),
                                        (interrupted, KeyboardInterrupt, 'KeyboardInterrupt')]:
            with self.subTest(message=message), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                video = root / 'input'
                video.touch()
                with patch('export_frames.video_frames', side_effect=decoder), self.assertRaises(error):
                    export_frames(video, root / 'frames')
                result = json.loads((root / 'frames/manifest.json').read_text())
                self.assertEqual(result['status'], 'failed')
                self.assertIn(message, result['error'])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / 'broken.mp4'
            video.write_bytes(b'not a video')
            with self.assertRaises(av.error.InvalidDataError):
                export_frames(video, root / 'frames')
            self.assertEqual(json.loads((root / 'frames/manifest.json').read_text())['status'], 'failed')

    def test_write_failure_preserves_completed_frame_records_and_marks_export_failed(self):
        def frames(*args):
            for index in range(2):
                yield index, index * 3000, index * 3000, np.zeros((8, 8, 3), dtype=np.uint8)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / 'input'
            video.touch()
            with patch('export_frames.video_frames', side_effect=frames), \
                 patch('export_frames.write_png', side_effect=[None, OSError('disk full')]), \
                 patch('export_frames.sha256_file', return_value='a' * 64):
                with self.assertRaisesRegex(OSError, 'disk full'):
                    export_frames(video, root / 'frames')
            result = json.loads((root / 'frames/manifest.json').read_text())
            self.assertEqual(result['status'], 'failed')
            self.assertEqual(len(result['frames']), 1)
            self.assertIn('disk full', result['error'])

    def test_input_hashing_failure_is_recorded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / 'input'
            video.touch()
            with patch('export_frames.sha256_file', side_effect=OSError('read failed')):
                with self.assertRaisesRegex(OSError, 'read failed'):
                    export_frames(video, root / 'frames')
            result = json.loads((root / 'frames/manifest.json').read_text())
            self.assertEqual(result['status'], 'failed')
            self.assertEqual(result['frames'], [])

    def test_cli_success_errors_and_sampling_exclusion(self):
        result = {'video': {'sha256': 'a' * 64}, 'frames': [{}, {}]}
        stdout = io.StringIO()
        with patch('export_frames.export_frames', return_value=result) as export, redirect_stdout(stdout):
            self.assertEqual(main(['v.mp4', '--output', 'frames', '--stride', '20', '--max-frames', '2']), 0)
            self.assertEqual(export.call_args.kwargs, {'every_seconds': None, 'stride': 20, 'max_frames': 2})
        self.assertEqual(json.loads(stdout.getvalue())['exported_frames'], 2)
        for exception, code in [(ValueError('bad input'), 1), (KeyboardInterrupt(), 130)]:
            with patch('export_frames.export_frames', side_effect=exception), redirect_stderr(io.StringIO()):
                self.assertEqual(main(['v.mp4', '--output', 'frames']), code)
        for options in (['--stride', '2', '--every-seconds', '3'], ['--max-frames', '0']):
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                main(['v.mp4', '--output', 'frames', *options])
            self.assertEqual(error.exception.code, 2)


if __name__ == '__main__':
    unittest.main()
