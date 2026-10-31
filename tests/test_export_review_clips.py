from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import av
import numpy as np

from benchmark import sha256_file, video_frames
from export_review_clips import export_review_clips, main, validate_windows


class ReviewClipTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.video = self.root / 'source.mp4'
        self.output = self.root / 'clips'
        with av.open(str(self.video), 'w') as destination:
            stream = destination.add_stream('libx264', rate=10)
            stream.width, stream.height, stream.pix_fmt = 64, 48, 'yuv420p'
            for index in range(7):
                rgb = np.full((48, 64, 3), 20 + 30 * index, dtype=np.uint8)
                for packet in stream.encode(av.VideoFrame.from_ndarray(rgb, format='rgb24')):
                    destination.mux(packet)
            for packet in stream.encode():
                destination.mux(packet)
        self.windows = [dict(id='first', start_frame=0, stop_frame=2),
                        dict(id='later', start_frame=3, stop_frame=7)]

    def test_real_clips_keep_exact_frames_duration_dimensions_and_source_mapping(self):
        result = export_review_clips(self.video, self.output, self.windows, fps=10)
        originals = list(video_frames(self.video, 1))
        self.assertEqual(result['status'], 'completed')
        self.assertFalse(result['human_reviewed'])
        self.assertFalse(result['encoding']['resize'])
        self.assertFalse(result['encoding']['audio'])
        self.assertEqual(result['video']['sha256'], sha256_file(self.video))
        self.assertEqual(result, json.loads((self.output / 'manifest.json').read_text()))
        for clip in result['clips']:
            path = self.output / clip['file_name']
            decoded = list(video_frames(path, 1))
            start, stop = clip['start_frame'], clip['stop_frame']
            self.assertEqual(len(decoded), stop - start)
            self.assertEqual(clip['frames'], len(decoded))
            self.assertEqual(clip['start_ms'], originals[start][1])
            self.assertEqual(clip['source_start_time_ms'], originals[start][2])
            self.assertEqual(clip['stop_ms'], stop * 100)
            self.assertEqual((clip['width'], clip['height']), (64, 48))
            self.assertEqual(clip['sha256'], sha256_file(path))
            for index, row in enumerate(decoded):
                self.assertAlmostEqual(row[1], index * 100)
                self.assertLess(np.abs(row[3].astype(float) - originals[start + index][3]).mean(), 4)
            with av.open(str(path)) as container:
                self.assertEqual(len(container.streams.audio), 0)
                self.assertAlmostEqual(float(container.streams.video[0].duration * container.streams.video[0].time_base), len(decoded) / 10)

    def test_adjacent_and_single_frame_windows_are_allowed_and_caller_data_is_unchanged(self):
        windows = [dict(id='one', start_frame=1, stop_frame=2), dict(id='two', start_frame=2, stop_frame=3)]
        before = json.dumps(windows)
        result = export_review_clips(self.video, self.output, windows, fps=10)
        self.assertEqual([clip['frames'] for clip in result['clips']], [1, 1])
        self.assertEqual(json.dumps(windows), before)

    def test_long_clip_muxes_streamed_and_delayed_encoder_packets(self):
        with av.open(str(self.video), 'w') as destination:
            stream = destination.add_stream('libx264', rate=10)
            stream.width, stream.height, stream.pix_fmt = 64, 48, 'yuv420p'
            for index in range(100):
                rgb = np.full((48, 64, 3), 20 + index * 2, dtype=np.uint8)
                for packet in stream.encode(av.VideoFrame.from_ndarray(rgb, format='rgb24')):
                    destination.mux(packet)
            for packet in stream.encode():
                destination.mux(packet)
        export_review_clips(self.video, self.output, [dict(id='long', start_frame=0, stop_frame=100)], fps=10)
        decoded = list(video_frames(self.output / 'long.mp4', 1))
        self.assertEqual(len(decoded), 100)
        self.assertAlmostEqual(decoded[-1][1], 9900)
        self.assertLess(decoded[0][3].mean(), 25)
        self.assertGreater(decoded[-1][3].mean(), 210)

    def test_invalid_windows_fail_before_creating_output(self):
        valid = dict(id='ok', start_frame=0, stop_frame=1)
        bad = [None, {}, [], [None], [dict(valid, unexpected=True)],
               [{k: v for k, v in valid.items() if k != 'id'}]]
        bad += [[dict(valid, id=name)] for name in ('', '..', '../x', 'a/b', 'a\\b', 'a b', 'a' * 65, None, 7)]
        bad += [[dict(valid, start_frame=v)] for v in (-1, True, 0.5, '0', None)]
        bad += [[dict(valid, stop_frame=v)] for v in (0, -1, True, 0.5, '1', None)]
        bad += [[dict(valid, start_frame=2)], [valid, valid], [valid, dict(valid, id='OK', start_frame=1, stop_frame=2)],
                [dict(valid, stop_frame=3), dict(valid, id='next', start_frame=2, stop_frame=4)],
                [dict(valid, start_frame=2, stop_frame=3), dict(valid, id='next')]]
        for windows in bad:
            with self.subTest(windows=windows), self.assertRaises(ValueError):
                export_review_clips(self.video, self.output, windows, fps=10)
            self.assertFalse(self.output.exists())
        validate_windows([dict(valid, id='A' * 64)])

    def test_invalid_source_fps_and_existing_output_preserve_files(self):
        for fps in (0, -1, True, 25.0, '25', None, 241):
            with self.subTest(fps=fps), self.assertRaises(ValueError):
                export_review_clips(self.video, self.output, self.windows, fps=fps)
            self.assertFalse(self.output.exists())
        with self.assertRaisesRegex(ValueError, 'does not exist'):
            export_review_clips(self.root / 'missing', self.output, self.windows, fps=10)
        self.output.mkdir()
        sentinel = self.output / 'manifest.json'
        sentinel.write_text('preserve')
        with self.assertRaises(FileExistsError):
            export_review_clips(self.video, self.output, self.windows, fps=10)
        self.assertEqual(sentinel.read_text(), 'preserve')

    def test_wrong_rate_and_variable_timestamps_fail_even_in_gaps(self):
        with self.assertRaisesRegex(ValueError, 'constant FPS'):
            export_review_clips(self.video, self.output, self.windows, fps=25)
        self.assertEqual(json.loads((self.output / 'manifest.json').read_text())['status'], 'failed')
        rows = list(video_frames(self.video, 1))
        rows[2] = (2, 205, 205, rows[2][3])
        with patch('export_review_clips.video_frames', return_value=iter_generator(rows)):
            with self.assertRaisesRegex(ValueError, 'constant FPS'):
                export_review_clips(self.video, self.root / 'vfr', self.windows, fps=10)

    def test_source_clock_offset_is_recorded_without_shifting_clip_playback(self):
        rows = [(i, ms, source + 5000, rgb) for i, ms, source, rgb in video_frames(self.video, 1)]
        with patch('export_review_clips.video_frames', return_value=iter_generator(rows)):
            result = export_review_clips(self.video, self.output, self.windows, fps=10)
        self.assertEqual(result['clips'][1]['source_start_time_ms'], 5300)
        self.assertEqual(result['clips'][1]['start_ms'], 300)
        self.assertEqual(next(video_frames(self.output / 'later.mp4', 1))[1], 0)

    def test_empty_truncated_and_corrupt_sources_leave_failed_manifest(self):
        for number, windows in enumerate(([dict(id='too_long', start_frame=3, stop_frame=8)],
                                           [dict(id='after_end', start_frame=7, stop_frame=8)])):
            out = self.root / str(number)
            with self.assertRaisesRegex(ValueError, 'ended before'):
                export_review_clips(self.video, out, windows, fps=10)
            self.assertEqual(json.loads((out / 'manifest.json').read_text())['status'], 'failed')
        self.video.write_bytes(b'corrupt')
        with self.assertRaises(av.error.InvalidDataError):
            export_review_clips(self.video, self.output, self.windows, fps=10)
        self.assertEqual(json.loads((self.output / 'manifest.json').read_text())['clips'], [])

    def test_odd_or_changing_dimensions_fail_instead_of_resizing(self):
        rows = list(video_frames(self.video, 1))
        for n, dimensions in enumerate(((47, 64, 3), (48, 62, 3))):
            changed = rows.copy()
            changed[1] = (1, 100, 100, np.zeros(dimensions, dtype=np.uint8))
            with patch('export_review_clips.video_frames', return_value=iter_generator(changed)):
                with self.assertRaisesRegex(ValueError, 'dimensions'):
                    export_review_clips(self.video, self.root / f'dim{n}', self.windows, fps=10)

    def test_encoder_failure_and_interrupt_close_decoder_and_record_failure(self):
        for number, error in enumerate((RuntimeError('encoder failed'), KeyboardInterrupt())):
            closed = []
            def source(*args):
                try:
                    yield (0, 0, 0, np.zeros((48, 64, 3), dtype=np.uint8))
                    raise error
                finally:
                    closed.append(True)
            out = self.root / f'fail{number}'
            with patch('export_review_clips.video_frames', side_effect=source):
                with self.assertRaises(type(error)):
                    export_review_clips(self.video, out, self.windows, fps=10)
            self.assertEqual(closed, [True])
            self.assertIn(type(error).__name__, json.loads((out / 'manifest.json').read_text())['error'])
        with patch('av.open', side_effect=RuntimeError('encoder unavailable')):
            with self.assertRaisesRegex(RuntimeError, 'unavailable'):
                export_review_clips(self.video, self.output, self.windows, fps=10)
        self.assertEqual(json.loads((self.output / 'manifest.json').read_text())['status'], 'failed')

    def test_cli_success_and_strict_json_failure_and_interrupt(self):
        windows = self.root / 'windows.json'
        windows.write_text(json.dumps(self.windows))
        args = [str(self.video), '--windows', str(windows), '--output', str(self.output), '--fps', '10']
        script = Path(__file__).resolve().parents[1] / 'export_review_clips.py'
        completed = subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True, timeout=20)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)['clips'], 2)
        for contents in ('[{"id":"a","id":"b","start_frame":0,"stop_frame":1}]', '[NaN]', 'not json'):
            windows.write_text(contents)
            with redirect_stderr(io.StringIO()) as stderr:
                self.assertEqual(main(args), 1)
            self.assertIn('failed', stderr.getvalue())
        windows.write_text(json.dumps(self.windows))
        with patch('export_review_clips.export_review_clips', side_effect=KeyboardInterrupt()):
            with redirect_stderr(io.StringIO()):
                self.assertEqual(main(args), 130)
        with patch('export_review_clips.export_review_clips', return_value={'clips': []}):
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(args), 0)


def iter_generator(rows):
    yield from rows


if __name__ == '__main__':
    unittest.main()
