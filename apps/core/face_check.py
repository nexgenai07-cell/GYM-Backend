"""
Is there exactly one usable face in a registration photo? Uses the same OpenCV YuNet detector
and confidence as the entrance gate (gym_entry_system/gate_check.py), so a photo that passes
here gives the gate a face to compare against.
"""
import hashlib
import logging
import math
from pathlib import Path

logger = logging.getLogger(__name__)

MODEL = Path(__file__).resolve().parent / 'face_models' / 'face_detection_yunet_2023mar.onnx'
MODEL_SHA256 = '8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4'

MIN_FACE_SCORE = 0.8      # YuNet confidence — same as the gate
MIN_FACE_PX = 110         # face box width; SFace aligns faces to 112 px, smaller loses detail
OTHER_FACE_SHARE = 0.25   # a second face at least a quarter the size of the main one counts
EDGE_PX = 4               # a face box touching the border is cut off
TURNED = 0.35             # nose offset from the eyes' midpoint, as a share of the eye distance
TILTED_DEG = 25           # eye line angle
FACE_DARK, FACE_BRIGHT = 55, 235
FACE_BLUR_MIN = 60        # Laplacian variance of the face at 160 px wide

MESSAGES = {
    'no_face': 'We can’t find a face in this photo. Look straight at the camera with your whole face in view and take it again.',
    'many_faces': 'More than one face is in the photo. Make sure only you are in front of the camera.',
    'face_small': 'Your face is too far from the camera. Move closer so your face fills the oval.',
    'face_cut': 'Part of your face is outside the photo. Keep your whole face inside the oval.',
    'face_turned': 'Your head is turned. Look straight at the camera and take it again.',
    'face_tilted': 'Your head is tilted. Keep your head straight and take it again.',
    'face_dark': 'Your face is too dark (the light is behind you). Face a light or a window and take it again.',
    'face_bright': 'Your face is too bright. Move away from direct light and take it again.',
    'face_blurry': 'Your face is blurry. Hold still and take it again.',
    'unavailable': 'We can’t check photos right now. Please try again in a few minutes.',
}

_detector = None


class FaceCheckUnavailable(Exception):
    """OpenCV or the model is missing — the photo can't be checked (never treated as a pass)."""


def _get_detector():
    global _detector
    if _detector is None:
        try:
            import cv2
        except ImportError as exc:
            raise FaceCheckUnavailable('opencv-python-headless is not installed') from exc
        data = MODEL.read_bytes() if MODEL.exists() else b''
        if hashlib.sha256(data).hexdigest() != MODEL_SHA256:
            raise FaceCheckUnavailable(f'{MODEL.name} is missing or corrupt')
        # OpenCV 5 logs a harmless "Targets are not supported by the new graph engine" warning.
        cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
        _detector = cv2.FaceDetectorYN.create(str(MODEL), '', (320, 320), MIN_FACE_SCORE)
    return _detector


def find_faces(img):
    """YuNet rows for an RGB Pillow image, largest first. Raises FaceCheckUnavailable."""
    import cv2
    import numpy as np
    detector = _get_detector()
    bgr = cv2.cvtColor(np.asarray(img.convert('RGB')), cv2.COLOR_RGB2BGR)
    h, w = bgr.shape[:2]
    detector.setInputSize((w, h))
    _, faces = detector.detect(bgr)
    if faces is None:
        return [], bgr
    return sorted(faces, key=lambda f: f[2] * f[3], reverse=True), bgr


def face_problem(img):
    """
    (code, message) for what's wrong with the face in a Pillow image (already upright), or None.
    Returns ('unavailable', …) when the check can't run, so callers refuse rather than pass.
    """
    try:
        faces, bgr = find_faces(img)
    except (FaceCheckUnavailable, ImportError):
        logger.exception('Face check unavailable')
        return 'unavailable', MESSAGES['unavailable']
    import cv2
    if not faces:
        return 'no_face', MESSAGES['no_face']
    main = faces[0]
    x, y, fw, fh = (float(v) for v in main[:4])
    if any(f[2] * f[3] >= OTHER_FACE_SHARE * fw * fh for f in faces[1:]):
        return 'many_faces', MESSAGES['many_faces']
    if fw < MIN_FACE_PX:
        return 'face_small', MESSAGES['face_small']
    h, w = bgr.shape[:2]
    if x < EDGE_PX or y < EDGE_PX or x + fw > w - EDGE_PX or y + fh > h - EDGE_PX:
        return 'face_cut', MESSAGES['face_cut']

    # landmarks: right eye, left eye, nose tip, right & left mouth corners
    rex, rey, lex, ley, nx = (float(v) for v in main[4:9])
    eye_dist = math.hypot(lex - rex, ley - rey)
    if eye_dist < 1 or abs(nx - (rex + lex) / 2) / eye_dist > TURNED:
        return 'face_turned', MESSAGES['face_turned']
    angle = abs(math.degrees(math.atan2(ley - rey, lex - rex)))
    if min(angle, 180 - angle) > TILTED_DEG:
        return 'face_tilted', MESSAGES['face_tilted']

    crop = cv2.cvtColor(bgr[int(y):int(y + fh), int(x):int(x + fw)], cv2.COLOR_BGR2GRAY)
    crop = cv2.resize(crop, (160, max(1, round(160 * fh / fw))), interpolation=cv2.INTER_AREA)
    mean = float(crop.mean())
    if mean < FACE_DARK:
        return 'face_dark', MESSAGES['face_dark']
    if mean > FACE_BRIGHT:
        return 'face_bright', MESSAGES['face_bright']
    if float(cv2.Laplacian(crop, cv2.CV_64F).var()) < FACE_BLUR_MIN:
        return 'face_blurry', MESSAGES['face_blurry']
    return None
