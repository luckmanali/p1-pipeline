"""Fixed 1080p full-frame and overlapping ball-crop experiment; no enhancement."""

from evaluate import _boxes, box_iou


ANALYSIS_SIZE = (1920, 1080)
CROP_BOXES = tuple((x, y, x + 960, y + 640) for y in (0, 440) for x in (0, 480, 960))
MERGE_IOU = 0.5
SPATIAL_MODES = ('native', 'full-1080p', 'ball-crops-1080p')


def resize_1080p(rgb):
    """Use the same RGB resize in both arms; reject stretching and upscaling."""
    import av
    import numpy as np

    if not isinstance(rgb, np.ndarray) or rgb.dtype != np.uint8 or rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ValueError('1080p analysis requires an RGB uint8 array')
    height, width = rgb.shape[:2]
    if width < 1920 or height < 1080 or width * 9 != height * 16:
        raise ValueError('1080p experiment requires 16:9 source pixels at least 1920x1080')
    if (width, height) == ANALYSIS_SIZE:
        return rgb
    return av.VideoFrame.from_ndarray(rgb, format='rgb24').reformat(
        width=1920, height=1080, format='rgb24', interpolation='BILINEAR',
    ).to_ndarray(format='rgb24')


def map_crop_balls(detections, crop):
    """Map crop-normalized boxes to whole-frame normalized source coordinates."""
    if (len(crop) != 4 or any(type(v) is not int for v in crop)
            or not 0 <= crop[0] < crop[2] <= 1920 or not 0 <= crop[1] < crop[3] <= 1080):
        raise ValueError('Crop must have positive integer bounds inside the 1080p image')
    _boxes(detections, 'Crop output', predictions=True)
    x, y, right, bottom = crop
    return [dict(item, bbox=[(x + item['bbox'][0] * (right-x)) / 1920,
                            (y + item['bbox'][1] * (bottom-y)) / 1080,
                            (x + item['bbox'][2] * (right-x)) / 1920,
                            (y + item['bbox'][3] * (bottom-y)) / 1080])
            for item in detections if item['class'] == 'football']


def merge_balls(detections):
    """Identical ball-only NMS in both arms; preserve full-frame person boxes."""
    _boxes(detections, 'Merge input', predictions=True)
    balls = []
    for item in sorted((d for d in detections if d['class'] == 'football'),
                       key=lambda d: d['confidence'], reverse=True):
        if not any(box_iou(item['bbox'], kept['bbox']) >= MERGE_IOU for kept in balls):
            balls.append(item)
    return [d for d in detections if d['class'] == 'player'] + balls


class SpatialDetector:
    def __init__(self, detector, mode):
        if mode not in SPATIAL_MODES[1:]:
            raise ValueError('SpatialDetector requires full-1080p or ball-crops-1080p')
        self.detector = detector
        self.crops = CROP_BOXES if mode == 'ball-crops-1080p' else ()
        self.metadata = dict(detector.metadata, spatial_processing={
            'mode': mode, 'analysis_size': list(ANALYSIS_SIZE),
            'resize': 'PyAV RGB24 BILINEAR; 16:9 sources >=1920x1080; no upscaling',
            'crop_boxes_xyxy': [list(box) for box in self.crops],
            'detector_calls_per_frame': 1 + len(self.crops),
            'merge': 'Ball-only confidence-ordered NMS; IoU >= threshold suppressed; stable ties',
            'merge_iou': MERGE_IOU, 'person_predictions': 'Full-frame only',
            'coordinates': 'Original-source normalized xyxy; original row dimensions/timestamps retained',
        })

    def predict(self, rgb):
        image = resize_1080p(rgb)
        candidates = list(self.detector.predict(image))
        for crop in self.crops:
            x, y, right, bottom = crop
            candidates.extend(map_crop_balls(self.detector.predict(image[y:bottom, x:right].copy()), crop))
        return merge_balls(candidates)
