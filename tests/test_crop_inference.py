import argparse
from contextlib import redirect_stderr, redirect_stdout
import copy
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

import numpy as np

from benchmark import benchmark, main, process_frames
from crop_inference import CROP_BOXES, SpatialDetector, map_crop_balls, merge_balls, resize_1080p


def ball(box, score=.8, label='football'):
    return {'class': label, 'confidence': score, 'bbox': box}


class SpatialTests(unittest.TestCase):
    def test_native_1080_pixels_unchanged_and_higher_source_resized_in_rgb(self):
        original = np.zeros((1080, 1920, 3), dtype=np.uint8)
        self.assertIs(resize_1080p(original), original)
        large = np.empty((1440, 2560, 3), dtype=np.uint8)
        large[:] = [231, 53, 17]
        result = resize_1080p(large)
        self.assertEqual(result.shape, (1080, 1920, 3))
        np.testing.assert_array_equal(result, np.broadcast_to([231, 53, 17], result.shape))
        np.testing.assert_array_equal(large[0, 0], [231, 53, 17])

    def test_rejects_bad_pixels_geometry_and_upscaling(self):
        for value in (None, np.zeros((1080, 1920, 3)), np.zeros((1080,1920), dtype=np.uint8),
                      np.zeros((1080,1920,4), dtype=np.uint8), np.zeros((720,1280,3), dtype=np.uint8),
                      np.zeros((1440,1920,3), dtype=np.uint8), np.zeros((0,0,3), dtype=np.uint8)):
            with self.subTest(shape=getattr(value, 'shape', None)), self.assertRaises(ValueError):
                resize_1080p(value)

    def test_grid_covers_image_and_seam_objects_have_an_unclipped_view(self):
        covered = np.zeros((1080, 1920), dtype=np.uint8)
        for x,y,right,bottom in CROP_BOXES:
            covered[y:bottom,x:right] += 1
        self.assertTrue(covered.all())
        self.assertGreater(int(covered.max()), 1)
        for box in ((950,430,970,450), (470,630,490,650), (1900,1060,1920,1080), (0,0,20,20)):
            self.assertTrue(any(x<=box[0]<box[2]<=r and y<=box[1]<box[3]<=b for x,y,r,b in CROP_BOXES))

    def test_coordinate_mapping_boundaries_and_partial_crop_positions(self):
        items = [ball([0,0,1,1]), ball([.25,.5,.5,.75], .7), ball([0,0,1,1], .9, 'player')]
        saved = copy.deepcopy(items)
        actual = map_crop_balls(items, (960,440,1920,1080))
        self.assertEqual(len(actual), 2)
        np.testing.assert_allclose(actual[0]['bbox'], [.5,440/1080,1,1])
        np.testing.assert_allclose(actual[1]['bbox'], [1200/1920,760/1080,1440/1920,920/1080])
        self.assertEqual(actual[1]['confidence'], .7)
        self.assertEqual(items, saved)

    def test_invalid_crop_bounds_fail(self):
        for crop in ((0,0,0,1),(-1,0,960,640),(0,0,1921,1080),(0,0,1920,1081),
                     (0,0,1), (0,0,1,2,3), (False,0,960,640),(0.,0,960,640)):
            with self.subTest(crop=crop), self.assertRaises(ValueError):
                map_crop_balls([], crop)

    def test_malformed_detector_output_is_not_silently_merged(self):
        invalid = [ball([0,0,0,1]), ball([0,0,1,1], float('nan')), ball([0,0,1,1], 1.1),
                   ball([0,0,1,1], .8, 'unknown'), ball([0,0,2,1]), ball([0,0,1]),
                   ball([0,0,float('nan'),1])]
        for item in invalid:
            for fn in (merge_balls, lambda items: map_crop_balls(items, CROP_BOXES[0])):
                with self.subTest(item=item), self.assertRaises(ValueError):
                    fn([item])

    def test_nms_keeps_best_duplicate_and_distinct_balls_without_mutating_people(self):
        items = [ball([.1,.1,.2,.2],.3), ball([.1,.1,.2,.2],.9), ball([.6,.6,.7,.7],.6),
                 ball([.1,.1,.2,.2],.1,'player'), ball([.1,.1,.2,.2],.8,'player')]
        before = copy.deepcopy(items)
        result = merge_balls(items)
        self.assertEqual(result, [items[3],items[4],items[1],items[2]])
        self.assertEqual(items, before)
        self.assertEqual(merge_balls([]), [])

    def test_nms_exact_iou_boundary_and_stable_confidence_ties(self):
        first = ball([0,0,.5,.5])
        half = ball([0,0,.25,.5])
        below = ball([0,0,.249,.5])
        self.assertEqual(merge_balls([first,half]), [first])
        self.assertEqual(merge_balls([half,first]), [half])
        self.assertEqual(merge_balls([first,below]), [first,below])

    def test_crop_views_use_same_resized_pixels_and_preserve_only_full_frame_people(self):
        rgb = np.zeros((1440,2560,3), dtype=np.uint8)
        rgb[:,:,0] = np.arange(2560, dtype=np.uint16)[None,:] % 256
        rgb[:,:,1] = np.arange(1440, dtype=np.uint16)[:,None] % 256
        expected = resize_1080p(rgb)
        full_person = ball([.1,.1,.2,.4], .9, 'player')
        full_ball = ball([.6,.5,.61,.52], .7)
        calls = []
        def predict(view):
            n = len(calls)
            calls.append(view.copy())
            if n == 0:
                return [full_person, full_ball]
            if n == 2:
                # Second crop starts at (480, 0); this duplicates the full-frame ball.
                return [ball([(1152-480)/960,540/640,(1171.2-480)/960,561.6/640],.9),
                        ball([0,0,1,1],.99,'player')]
            return []
        model = SimpleNamespace(metadata={'runtime':'fake'}, predict=predict)
        wrapper = SpatialDetector(model, 'ball-crops-1080p')
        result = wrapper.predict(rgb)
        self.assertEqual(len(calls), 7)
        np.testing.assert_array_equal(calls[0], expected)
        for actual, (x,y,r,b) in zip(calls[1:], CROP_BOXES):
            np.testing.assert_array_equal(actual, expected[y:b,x:r])
        self.assertEqual(result[0], full_person)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[1]['confidence'], .9)
        np.testing.assert_allclose(result[1]['bbox'], full_ball['bbox'])
        self.assertNotIn('spatial_processing', model.metadata)
        self.assertEqual(wrapper.metadata['spatial_processing']['detector_calls_per_frame'], 7)

    def test_full_frame_control_uses_same_merge_with_one_call(self):
        item = ball([.1,.1,.2,.2])
        model = SimpleNamespace(metadata={}, predict=MagicMock(return_value=[item,item]))
        wrapper = SpatialDetector(model, 'full-1080p')
        self.assertEqual(wrapper.predict(np.zeros((1080,1920,3),dtype=np.uint8)), [item])
        model.predict.assert_called_once()
        self.assertEqual(wrapper.metadata['spatial_processing']['detector_calls_per_frame'], 1)
        self.assertEqual(wrapper.metadata['spatial_processing']['crop_boxes_xyxy'], [])

    def test_invalid_mode_fails_before_using_model(self):
        for mode in ('native', '', 'tiles', None):
            with self.assertRaises(ValueError):
                SpatialDetector(None, mode)

    def test_crop_failure_propagates_without_saving_partial_frame(self):
        model = SimpleNamespace(metadata={}, predict=MagicMock(side_effect=[[],[],RuntimeError('tile failed')]))
        wrapper = SpatialDetector(model, 'ball-crops-1080p')
        rgb = np.zeros((1080,1920,3),dtype=np.uint8)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, 'tile failed'):
                process_frames([(0,0,0,rgb)], wrapper, Path(directory), lambda:None, 0)
            self.assertEqual((Path(directory)/'detections.jsonl').read_text(), '')

    def test_saved_rows_keep_source_geometry_and_timestamps_after_resize(self):
        item = ball([.25,.25,.5,.5])
        model = SimpleNamespace(metadata={}, predict=lambda rgb:[item])
        wrapper = SpatialDetector(model, 'full-1080p')
        rgb = np.zeros((1440,2560,3),dtype=np.uint8)
        with tempfile.TemporaryDirectory() as directory:
            result = process_frames([(10500,420000,421000,rgb)], wrapper, Path(directory), lambda:None, 2)
            row = json.loads((Path(directory)/'detections.jsonl').read_text())
        self.assertEqual((row['width'],row['height']), (2560,1440))
        self.assertEqual((row['frame_index'],row['timestamp_ms'],row['source_time_ms']), (10500,420000,421000))
        self.assertEqual(row['detections'], [item])
        self.assertEqual(result['prediction']['frames'], 1)


class SpatialCliTests(unittest.TestCase):
    def test_cli_default_and_explicit_modes(self):
        for mode in ('native','full-1080p','ball-crops-1080p'):
            with patch('benchmark.benchmark', return_value={'measurements':{}}) as run, redirect_stdout(io.StringIO()):
                args = ['video','--model','yolo26l','--output','run']
                if mode != 'native': args += ['--spatial-mode',mode]
                self.assertEqual(main(args), 0)
                self.assertEqual(run.call_args.args[0].spatial_mode, mode)
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(['video','--model','yolo26l','--output','run','--spatial-mode','bad'])

    def test_complete_and_failed_spatial_manifests(self):
        for invalid_geometry in (False,True):
            with self.subTest(invalid_geometry=invalid_geometry), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root/'video').touch(); (root/'weights').touch()
                args = argparse.Namespace(video=root/'video', weights=root/'weights', output=root/'run', model='yolo26l',
                    stride=300,max_frames=1,confidence=.05,device='cpu',warmup=1,dfine_repo=None,input_size=1280,
                    spatial_mode='ball-crops-1080p')
                model = SimpleNamespace(metadata={'runtime':'fake'}, predict=MagicMock(return_value=[]))
                rgb = np.zeros((720,1280,3) if invalid_geometry else (1080,1920,3),dtype=np.uint8)
                torch = SimpleNamespace(get_num_threads=lambda: 4)
                with patch.dict('sys.modules',{'torch':torch}), patch('benchmark.load_detector',return_value=model), \
                     patch('benchmark.video_frames',return_value=[(0,0,0,rgb)]), \
                     patch('benchmark.metadata.distributions',return_value=[]), patch('benchmark.repo_state',return_value={}):
                    if invalid_geometry:
                        with self.assertRaises(ValueError): benchmark(args)
                    else:
                        benchmark(args)
                        self.assertEqual(model.predict.call_count, 14)  # seven warmup and seven measured views
                manifest = json.loads((args.output/'manifest.json').read_text())
                self.assertEqual(manifest['status'], 'failed' if invalid_geometry else 'completed')
                self.assertEqual(manifest['inference']['spatial_mode'], 'ball-crops-1080p')
                self.assertEqual(manifest['model']['spatial_processing']['merge_iou'], .5)
                self.assertEqual(manifest['model']['spatial_processing']['analysis_size'], [1920,1080])
                args.spatial_mode = 'invalid'
                with self.assertRaisesRegex(ValueError, 'Unsupported spatial mode'): benchmark(args)


if __name__ == '__main__':
    unittest.main()
