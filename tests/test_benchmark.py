import argparse
from contextlib import redirect_stderr, redirect_stdout
from enum import Enum
from fractions import Fraction
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from benchmark import benchmark, confidence, latency_summary, main, positive_int, process_frames, sample_frames, sha256_file, video_frames, write_manifest


class BenchmarkTests(unittest.TestCase):
    def test_sampling_uses_variable_presentation_times(self):
        frames = [SimpleNamespace(pts=n, time_base=Fraction(1, 1000)) for n in (2000, 2030, 2080, 2110, 2200)]
        sampled = list(sample_frames(frames, 2, 2))
        self.assertEqual([row[0] for row in sampled], [0, 2])
        self.assertAlmostEqual(sampled[1][1], 80)
        self.assertAlmostEqual(sampled[1][2], 2080)

    def test_missing_or_non_increasing_timestamps_fail(self):
        for pts in ((0, None), (2, 2), (2, 1)):
            with self.subTest(pts=pts), self.assertRaises(ValueError):
                list(sample_frames([SimpleNamespace(pts=n, time_base=Fraction(1, 30)) for n in pts], 1))

    def test_warmup_not_saved_or_counted(self):
        rgb = SimpleNamespace(shape=(50, 100, 3))
        calls = []
        detection = {'class': 'football', 'confidence': 0.9, 'bbox': [0.1, 0.2, 0.3, 0.4]}
        detector = SimpleNamespace(predict=lambda frame: calls.append(frame) or [detection])
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            result = process_frames([(0, 0, 2000, rgb), (6, 201, 2201, rgb)], detector, output, lambda: None, 3)
            rows = [json.loads(line) for line in (output / 'detections.jsonl').read_text().splitlines()]
        self.assertEqual(len(calls), 5)
        self.assertEqual(result['prediction']['frames'], 2)
        self.assertEqual(result['detections_by_class'], {'player': 0, 'football': 2})
        self.assertEqual([row['frame_index'] for row in rows], [0, 6])
        self.assertEqual(rows[1]['timestamp_ms'], 201)

    def test_empty_video_fails(self):
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(ValueError):
            process_frames([], None, Path(directory), lambda: None, 3)

    def test_invalid_sampling_and_thresholds_fail(self):
        for stride, limit in ((0, None), (1, 0), (-1, 1)):
            with self.assertRaises(ValueError):
                list(sample_frames([], stride, limit))
        for value in ('nan', 'inf', '-0.1', '1.1'):
            with self.assertRaises(argparse.ArgumentTypeError):
                confidence(value)

    def test_failure_is_recorded_and_existing_runs_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / 'input.mp4'
            weights = root / 'model.pt'
            video.write_bytes(b'video')
            weights.write_bytes(b'weights')
            args = SimpleNamespace(video=video, weights=weights, output=root / 'run', model='yolo26n',
                                   stride=1, max_frames=1, confidence=0.05, device='cpu', warmup=3,
                                   dfine_repo=None, input_size=640)
            with patch('benchmark.sha256_file', side_effect=RuntimeError('broken read')):
                with self.assertRaisesRegex(RuntimeError, 'broken read'):
                    benchmark(args)
            manifest = json.loads((args.output / 'manifest.json').read_text())
            self.assertEqual(manifest['status'], 'failed')
            self.assertIn('broken read', manifest['error'])
            with self.assertRaises(FileExistsError):
                benchmark(args)
            self.assertEqual(json.loads((args.output / 'manifest.json').read_text()), manifest)

    def test_file_hash_is_content_based(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'video'
            path.write_bytes(b'abc')
            self.assertEqual(sha256_file(path), 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad')

    def test_side_data_mapping_accepts_non_transform_metadata(self):
        types = Enum('SideTypes', ['SEI_UNREGISTERED', 'DISPLAYMATRIX'])
        frame = SimpleNamespace(pts=0, time_base=Fraction(1, 30),
                                side_data={types.SEI_UNREGISTERED: SimpleNamespace(type=types.SEI_UNREGISTERED)},
                                to_ndarray=MagicMock(return_value='rgb'))
        stream = SimpleNamespace(sample_aspect_ratio=Fraction(1), metadata={})
        container = SimpleNamespace(streams=SimpleNamespace(video=[stream]), decode=lambda stream: [frame])
        opener = MagicMock()
        opener.return_value.__enter__.return_value = container
        with patch.dict('sys.modules', {'av': SimpleNamespace(open=opener)}):
            self.assertEqual(list(video_frames('input.mp4', 1)), [(0, 0, 0, 'rgb')])
            frame.to_ndarray.assert_called_once_with(format='rgb24')
            frame.side_data = {types.DISPLAYMATRIX: SimpleNamespace(type=types.DISPLAYMATRIX)}
            with self.assertRaisesRegex(ValueError, 'display transform'):
                list(video_frames('input.mp4', 1))

    def test_decoder_rejects_missing_stream_and_ambiguous_geometry(self):
        for streams, message in (
            ([], 'no video stream'),
            ([SimpleNamespace(sample_aspect_ratio=Fraction(4, 3), metadata={})], 'square-pixel'),
            ([SimpleNamespace(sample_aspect_ratio=Fraction(1), metadata={'rotate': '90'})], 'Rotate'),
        ):
            with self.subTest(message=message):
                opener = MagicMock()
                opener.return_value.__enter__.return_value = SimpleNamespace(streams=SimpleNamespace(video=streams))
                with patch.dict('sys.modules', {'av': SimpleNamespace(open=opener)}):
                    with self.assertRaisesRegex(ValueError, message):
                        list(video_frames('input.mp4', 1))

    def test_invalid_timestamps_on_skipped_frames_still_fail(self):
        for frames in (
            [SimpleNamespace(pts=0, time_base=None)],
            [SimpleNamespace(pts=float('inf'), time_base=Fraction(1))],
            [SimpleNamespace(pts=n, time_base=Fraction(1)) for n in (0, -1, 2)],
        ):
            with self.subTest(frames=frames), self.assertRaises(ValueError):
                list(sample_frames(frames, 2))

    def test_frame_limit_does_not_decode_a_later_frame(self):
        def frames():
            yield SimpleNamespace(pts=0, time_base=Fraction(1))
            raise AssertionError('Decoded beyond requested limit')
        self.assertEqual(len(list(sample_frames(frames(), 3, 1))), 1)

    def test_latency_statistics_and_zero_duration(self):
        result = latency_summary([0.003, 0.001, 0.002])
        self.assertEqual(result['frames'], 3)
        self.assertEqual(result['median_ms'], 2)
        self.assertEqual(result['p95_ms'], 3)
        self.assertAlmostEqual(result['frames_per_second'], 500)
        self.assertIsNone(latency_summary([0])['frames_per_second'])

    def test_manifest_is_replaced_atomically(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            write_manifest(output, {'status': 'running'})
            write_manifest(output, {'status': 'completed'})
            self.assertEqual(json.loads((output / 'manifest.json').read_text()), {'status': 'completed'})
            self.assertFalse((output / 'manifest.tmp').exists())

    def test_prediction_failure_preserves_only_completed_rows(self):
        rgb = SimpleNamespace(shape=(50, 100, 3))
        detector = SimpleNamespace(predict=MagicMock(side_effect=[[], [], RuntimeError('model failed')]))
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            with self.assertRaisesRegex(RuntimeError, 'model failed'):
                process_frames([(0, 0, 0, rgb), (1, 40, 40, rgb)], detector, output, lambda: None, 1)
            rows = (output / 'detections.jsonl').read_text().splitlines()
            self.assertEqual(len(rows), 1)
            self.assertEqual(json.loads(rows[0])['frame_index'], 0)

    def test_argument_boundaries_and_cli_defaults(self):
        self.assertEqual(positive_int('1'), 1)
        self.assertEqual(confidence('0'), 0)
        self.assertEqual(confidence('1'), 1)
        with self.assertRaises(argparse.ArgumentTypeError):
            positive_int('0')
        for name, filename in [('yolo26n', 'yolo26n.pt'), ('yolo26s', 'yolo26s.pt'),
                               ('yolo26m', 'yolo26m.pt'), ('dfine-n', 'dfine_n_coco.pth')]:
            output = io.StringIO()
            with patch('benchmark.benchmark', return_value={'measurements': {'frames': 1}}) as runner:
                with redirect_stdout(output):
                    self.assertEqual(main(['video.mp4', '--model', name, '--output', 'run']), 0)
                self.assertEqual(runner.call_args.args[0].weights, Path('weights') / filename)
                self.assertEqual(runner.call_args.args[0].input_size, 640)
                self.assertEqual(json.loads(output.getvalue()), {'frames': 1})
        for error, code in [(RuntimeError('failure'), 1), (KeyboardInterrupt(), 130)]:
            with patch('benchmark.benchmark', side_effect=error), redirect_stderr(io.StringIO()):
                self.assertEqual(main(['v', '--model', 'yolo26n', '--output', 'run']), code)

    def test_complete_manifest_cpu_and_cuda_and_interrupted_run(self):
        for device, interruption in [('cpu', False), ('cuda:2', False), ('cpu', True)]:
            with self.subTest(device=device, interruption=interruption), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                video, weights = root / 'video.mp4', root / 'model.pt'
                video.write_bytes(b'video')
                weights.write_bytes(b'weights')
                args = SimpleNamespace(video=video, weights=weights, output=root / 'run', model='yolo26n',
                                       stride=1, max_frames=1, confidence=0.05, device=device, warmup=1, dfine_repo=None, input_size=640)
                args.input_size = 1280
                torch = MagicMock()
                torch.get_num_threads.return_value = 4
                torch.cuda.get_device_name.return_value = 'test GPU'
                torch.cuda.max_memory_allocated.return_value = 1024
                detector = SimpleNamespace(metadata={'runtime': 'test'}, predict=MagicMock(return_value=[]))
                if interruption:
                    detector.predict.side_effect = KeyboardInterrupt
                rgb = SimpleNamespace(shape=(50, 100, 3))
                with patch.dict('sys.modules', {'torch': torch}), patch('benchmark.load_detector', return_value=detector) as loader, \
                     patch('benchmark.video_frames', return_value=[(0, 0, 0, rgb)]), \
                     patch('benchmark.metadata.distributions', return_value=[]):
                    if interruption:
                        with self.assertRaises(KeyboardInterrupt):
                            benchmark(args)
                    else:
                        result = benchmark(args)
                        self.assertEqual(result['status'], 'completed')
                        self.assertEqual(result['inference']['input_size'], 1280)
                        loader.assert_called_once_with(args.model, weights, device, 0.05, None, input_size=1280)
                        self.assertEqual(result['measurements']['prediction']['frames'], 1)
                        self.assertEqual(result['environment']['torch_threads'], 4)
                        self.assertEqual(result['model']['sha256'], sha256_file(weights))
                        if device.startswith('cuda'):
                            torch.cuda.reset_peak_memory_stats.assert_called_once_with('cuda:2')
                            self.assertTrue(all(call.args == ('cuda:2',) for call in torch.cuda.synchronize.call_args_list))
                            self.assertEqual(result['measurements']['peak_cuda_allocated_bytes'], 1024)
                        else:
                            torch.cuda.synchronize.assert_not_called()
                saved = json.loads((args.output / 'manifest.json').read_text())
                self.assertEqual(saved['status'], 'failed' if interruption else 'completed')

    def test_cli_forwards_explicit_size_and_weights(self):
        with patch('benchmark.benchmark', return_value={'measurements': {}}) as runner:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(['video.mp4', '--model', 'yolo26s', '--weights', 'custom.pt',
                                       '--input-size', '1280', '--output', 'run']), 0)
            self.assertEqual(runner.call_args.args[0].input_size, 1280)
            self.assertEqual(runner.call_args.args[0].weights, Path('custom.pt'))

    def test_cli_accepts_yolo_1920(self):
        with patch('benchmark.benchmark', return_value={'measurements': {}}) as runner:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(['video.mp4', '--model', 'yolo26n', '--input-size', '1920',
                                       '--output', 'run']), 0)
            self.assertEqual(runner.call_args.args[0].input_size, 1920)

    def test_cli_rejects_unsupported_sizes_before_starting_run(self):
        for size in ('0', '-640', '641', '960', '1280.0', '1920.0', '1921', '2560.0', '2561', 'not-a-size'):
            with self.subTest(size=size), patch('benchmark.benchmark') as runner:
                with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                    main(['v', '--model', 'yolo26n', '--output', 'run', '--input-size', size])
                self.assertEqual(error.exception.code, 2)
                runner.assert_not_called()

    def test_cli_accepts_large_model_at_full_source_width(self):
        with patch('benchmark.benchmark', return_value={'measurements': {}}) as runner:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(['video.mp4', '--model', 'yolo26l', '--input-size', '2560',
                                       '--output', 'run']), 0)
            args = runner.call_args.args[0]
            self.assertEqual(args.model, 'yolo26l')
            self.assertEqual(args.input_size, 2560)
            self.assertEqual(args.weights, Path('weights/yolo26l.pt'))

    def test_missing_inputs_and_unavailable_cuda(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = SimpleNamespace(video=root / 'video', weights=root / 'weights', output=root / 'run',
                                   model='yolo26n', stride=1, max_frames=1, confidence=0.05,
                                   device='cuda', warmup=1, dfine_repo=None, input_size=640)
            with self.assertRaisesRegex(ValueError, 'Video does not exist'):
                benchmark(args)
            args.video.touch()
            with self.assertRaisesRegex(ValueError, 'Checkpoint does not exist'):
                benchmark(args)
            self.assertFalse(args.output.exists())
            args.weights.touch()
            torch = MagicMock()
            torch.cuda.is_available.return_value = False
            with patch.dict('sys.modules', {'torch': torch}), patch('benchmark.metadata.distributions', return_value=[]):
                with self.assertRaisesRegex(ValueError, 'CUDA was requested but is unavailable'):
                    benchmark(args)
            self.assertEqual(json.loads((args.output / 'manifest.json').read_text())['status'], 'failed')


if __name__ == '__main__':
    unittest.main()
