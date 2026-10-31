"""Generated-video integration tests: no footage, weights, network or GPU needed."""

from pathlib import Path
import tempfile
import unittest

import av
import numpy as np

from benchmark import video_frames


class VideoTests(unittest.TestCase):
    def test_real_h264_decoder_samples_rgb_frames_with_presentation_times(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'generated.mp4'
            with av.open(str(path), 'w') as output:
                stream = output.add_stream('libx264', rate=10)
                stream.width, stream.height = 64, 48
                stream.pix_fmt = 'yuv420p'
                for index in range(5):
                    pixels = np.zeros((48, 64, 3), dtype=np.uint8)
                    pixels[:, :, 0] = 200
                    pixels[:, :, 1] = index * 20
                    for packet in stream.encode(av.VideoFrame.from_ndarray(pixels, format='rgb24')):
                        output.mux(packet)
                for packet in stream.encode():
                    output.mux(packet)
            rows = list(video_frames(path, 2, 2))
        self.assertEqual([row[0] for row in rows], [0, 2])
        self.assertAlmostEqual(rows[0][1], 0)
        self.assertAlmostEqual(rows[1][1], 200)
        self.assertEqual(rows[0][3].shape, (48, 64, 3))
        self.assertEqual(rows[0][3].dtype, np.uint8)
        self.assertGreater(int(rows[0][3][0, 0, 0]), 190)
        self.assertLess(int(rows[0][3][0, 0, 2]), 10)

    def test_corrupt_video_fails_clearly(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'broken.mp4'
            path.write_bytes(b'not a video')
            with self.assertRaises(av.error.InvalidDataError):
                list(video_frames(path, 1))


if __name__ == '__main__':
    unittest.main()
