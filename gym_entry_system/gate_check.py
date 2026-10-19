"""
Smart Gym - gate controller (face check at the entrance).

    python gate_check.py --iqama 2999888777

1. Logs in to the backend as a staff account (API_BASE_URL, GATE_STAFF_* in .env).
2. Looks the member up by Iqama; denies if not found, not approved, or membership not valid.
3. Downloads the photo captured at registration.
4. Opens the webcam; press SPACE to capture (ESC to cancel).
5. Compares faces with OpenCV YuNet (detection) + SFace (recognition).
6. Shows a full-screen green "ACCESS GRANTED - OK" or red "ACCESS DENIED",
   records the face check, and on a match records the check-in.

Exit codes: 0 = granted, 1 = denied, 2 = error (config / network / camera).
"""
import argparse
import hashlib
import os
import sys
import time
import urllib.request
from pathlib import Path

import cv2
import numpy as np
import requests
from colorama import Fore, Style, just_fix_windows_console
from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
MODELS_DIR = HERE / 'models'

# Official OpenCV Zoo models. Pinned by SHA-256 so a tampered/corrupt download is rejected.
MODELS = {
    'detector': (
        'face_detection_yunet_2023mar.onnx',
        'https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx',
    ),
    'recognizer': (
        'face_recognition_sface_2021dec.onnx',
        'https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx',
    ),
}
MODEL_SHA256 = {
    'face_detection_yunet_2023mar.onnx': '8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4',
    'face_recognition_sface_2021dec.onnx': '0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79',
}

DEFAULT_THRESHOLD = 0.363   # OpenCV's recommended SFace cosine threshold
MIN_FACE_SCORE = 0.8        # YuNet detection confidence
HTTP_TIMEOUT = 15

GREEN = (60, 200, 60)
RED = (40, 40, 220)
WHITE = (255, 255, 255)


class GateError(Exception):
    """Configuration / network / camera problem - not a decision about the member."""


class Denied(Exception):
    """A decision: the member may not enter. The message is the reason."""


# ============================================================
# CONFIG
# ============================================================
def load_config():
    load_dotenv(HERE / '.env')
    cfg = {
        'api': os.getenv('API_BASE_URL', 'http://localhost:8000/api').rstrip('/'),
        'email': os.getenv('GATE_STAFF_EMAIL', ''),
        'password': os.getenv('GATE_STAFF_PASSWORD', ''),
        'threshold': float(os.getenv('MATCH_THRESHOLD', DEFAULT_THRESHOLD)),
        'camera': int(os.getenv('CAMERA_INDEX', '0')),
        'facility': os.getenv('GATE_FACILITY', 'Main Entrance'),
    }
    if not cfg['email'] or not cfg['password']:
        raise GateError('Set GATE_STAFF_EMAIL and GATE_STAFF_PASSWORD in gym_entry_system/.env')
    return cfg


# ============================================================
# MODELS
# ============================================================
def ensure_models():
    MODELS_DIR.mkdir(exist_ok=True)
    paths = {}
    for key, (filename, url) in MODELS.items():
        path = MODELS_DIR / filename
        if not path.exists():
            print(f'Downloading {filename} (first run only)...')
            tmp = path.with_suffix('.part')
            try:
                urllib.request.urlretrieve(url, tmp)
            except OSError as exc:
                raise GateError(f'Could not download {filename}: {exc}') from exc
            tmp.replace(path)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != MODEL_SHA256[filename]:
            path.unlink()
            raise GateError(f'{filename} failed its integrity check (got {digest}). Deleted - run again to re-download.')
        paths[key] = str(path)
    return paths


class FaceEngine:
    def __init__(self, paths):
        # OpenCV 5 logs a harmless "Targets are not supported by the new graph engine" warning.
        cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
        self.detector = cv2.FaceDetectorYN.create(paths['detector'], '', (320, 320), MIN_FACE_SCORE)
        self.recognizer = cv2.FaceRecognizerSF.create(paths['recognizer'], '')

    def detect(self, img):
        """Return YuNet face rows (largest first), or an empty list."""
        h, w = img.shape[:2]
        self.detector.setInputSize((w, h))
        _, faces = self.detector.detect(img)
        if faces is None:
            return []
        return sorted(faces, key=lambda f: f[2] * f[3], reverse=True)

    def embed(self, img, face):
        aligned = self.recognizer.alignCrop(img, face)
        return self.recognizer.feature(aligned)

    def similarity(self, feat_a, feat_b):
        return float(self.recognizer.match(feat_a, feat_b, cv2.FaceRecognizerSF_FR_COSINE))


# ============================================================
# BACKEND
# ============================================================
class Backend:
    def __init__(self, cfg):
        self.api = cfg['api']
        self.http = requests.Session()
        self.http.headers['User-Agent'] = 'SmartGym-Gate/1.0'
        self._login(cfg['email'], cfg['password'])

    def _call(self, method, path, **kw):
        try:
            return self.http.request(method, f'{self.api}{path}', timeout=HTTP_TIMEOUT, **kw)
        except requests.RequestException as exc:
            raise GateError(f'Backend unreachable at {self.api}: {exc}') from exc

    def _login(self, email, password):
        r = self._call('POST', '/auth/login/', json={'email': email, 'password': password})
        if r.status_code != 200:
            raise GateError(f'Staff login failed (HTTP {r.status_code}) - check GATE_STAFF_EMAIL / GATE_STAFF_PASSWORD.')
        self.http.headers['Authorization'] = f"Bearer {r.json()['access']}"

    def lookup(self, iqama):
        r = self._call('GET', '/admin/registrations-api/members/lookup/', params={'iqama': iqama})
        if r.status_code == 403:
            raise GateError('This staff account is not allowed to look up members (needs admin/manager role).')
        if r.status_code == 404:
            reason = r.json().get('reason')
            if reason == 'registration_pending':
                raise Denied('Registration not approved yet.')
            raise Denied('No member with this Iqama number.')
        if r.status_code != 200:
            raise GateError(f'Lookup failed (HTTP {r.status_code}).')
        return r.json()

    def download_photo(self, url):
        # Plain GET without our auth header - the URL may be a signed storage link.
        try:
            r = requests.get(url, timeout=HTTP_TIMEOUT)
        except requests.RequestException as exc:
            raise GateError(f'Could not download the registered photo: {exc}') from exc
        if r.status_code != 200:
            raise GateError(f'Registered photo unavailable (HTTP {r.status_code}). '
                            'With local storage the backend must run with DEBUG=True to serve /media/.')
        img = cv2.imdecode(np.frombuffer(r.content, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise GateError('Registered photo could not be decoded.')
        return img

    def record_face_check(self, member_id, matched, score, threshold):
        """Saves a FaceCheck (audit trail, incl. denials). Returns its id, or None if not saved."""
        r = self._call('POST', f'/admin/registrations-api/members/{member_id}/face-verify/',
                       json={'match': matched, 'confidence': round(score, 4),
                             'threshold': threshold, 'source': 'gate'})
        if r.status_code != 201:
            print(f'{Fore.YELLOW}Warning: face check not recorded (HTTP {r.status_code}).{Style.RESET_ALL}')
            return None
        return r.json().get('face_check_id')

    def check_in(self, member_id, facility, face_check_id=None):
        body = {'facility': facility, 'face_verified': True}
        if face_check_id is not None:
            body['face_check_id'] = face_check_id
        r = self._call('POST', f'/admin/registrations-api/members/{member_id}/check-in/', json=body)
        if r.status_code != 201:
            raise GateError(f"Face matched but check-in failed: {r.json().get('detail', r.status_code)}")
        return r.json()


# ============================================================
# CAMERA
# ============================================================
def capture_live(engine, camera_index):
    """Live preview with a face box; SPACE captures (only with exactly one face), ESC cancels."""
    cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW if sys.platform == 'win32' else cv2.CAP_ANY)
    if not cap.isOpened():
        raise GateError(f'Could not open camera {camera_index} (in use by another app, or set CAMERA_INDEX).')
    window = 'Smart Gym Gate - SPACE: capture   ESC: cancel'
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    hint = ''
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                raise GateError('Camera stopped delivering frames.')
            faces = engine.detect(frame)
            view = cv2.flip(frame, 1)   # mirrored preview feels natural; the capture stays unmirrored
            w = frame.shape[1]
            for f in faces:
                x, y, fw, fh = map(int, f[:4])
                colour = GREEN if len(faces) == 1 else RED
                cv2.rectangle(view, (w - x - fw, y), (w - x, y + fh), colour, 2)
            status = hint or ('Face detected - press SPACE' if len(faces) == 1
                              else 'One person at a time' if faces else 'Look at the camera')
            cv2.putText(view, status, (16, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.9, WHITE, 2, cv2.LINE_AA)
            cv2.imshow(window, view)

            key = cv2.waitKey(1) & 0xFF
            if key == 27:
                raise Denied('Cancelled by operator.')
            if key == 32:
                if len(faces) == 1:
                    return frame, faces[0]
                hint = 'Need exactly one face in view'
            if cv2.getWindowProperty(window, cv2.WND_PROP_VISIBLE) < 1:
                raise Denied('Camera window closed.')
    finally:
        cap.release()
        cv2.destroyWindow(window)


# ============================================================
# OUTPUT
# ============================================================
def banner(granted, lines):
    colour = Fore.GREEN if granted else Fore.RED
    title = 'ACCESS GRANTED - OK' if granted else 'ACCESS DENIED'
    bar = '#' * 44   # ASCII on purpose: cp1252 consoles/redirects can't encode block glyphs
    print(f'\n{colour}{Style.BRIGHT}{bar}\n##{title:^40}##\n{bar}{Style.RESET_ALL}')
    for line in lines:
        print(f'  {line}')
    print()


def show_result(granted, lines, seconds=5):
    img = np.full((480, 900, 3), GREEN if granted else RED, np.uint8)
    title = 'ACCESS GRANTED - OK' if granted else 'ACCESS DENIED'
    (tw, _), _ = cv2.getTextSize(title, cv2.FONT_HERSHEY_DUPLEX, 2.2, 5)
    cv2.putText(img, title, ((900 - tw) // 2, 200), cv2.FONT_HERSHEY_DUPLEX, 2.2, WHITE, 5, cv2.LINE_AA)
    for i, line in enumerate(lines[:4]):
        cv2.putText(img, line, (40, 290 + i * 42), cv2.FONT_HERSHEY_SIMPLEX, 0.9, WHITE, 2, cv2.LINE_AA)
    window = 'Smart Gym Gate'
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(window, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    cv2.imshow(window, img)
    cv2.waitKey(seconds * 1000)   # any key dismisses early
    cv2.destroyAllWindows()


# ============================================================
# MAIN
# ============================================================
def run(args):
    cfg = load_config()
    threshold = args.threshold if args.threshold is not None else cfg['threshold']
    engine = FaceEngine(ensure_models())
    backend = Backend(cfg)

    data = backend.lookup(args.iqama)
    member = data['member']
    name = member.get('full_name') or member.get('email')
    membership = data.get('membership') or {}

    if not data.get('is_valid'):
        raise Denied(f"{name}: membership not valid (status {membership.get('status')}, "
                     f"{membership.get('days_remaining', 0)} days remaining).")
    if data.get('active_check_in'):
        raise Denied(f'{name} is already checked in (no check-out recorded).')
    if not data.get('registration_photo_url'):
        raise Denied(f'{name} has no registered photo - verify manually at the desk.')

    reg_img = backend.download_photo(data['registration_photo_url'])
    reg_faces = engine.detect(reg_img)
    if not reg_faces:
        raise Denied(f'No face found in {name}\'s registered photo - verify manually at the desk.')
    reg_feat = engine.embed(reg_img, reg_faces[0])

    if args.image:
        live_img = cv2.imread(args.image)
        if live_img is None:
            raise GateError(f'Could not read {args.image}')
        live_faces = engine.detect(live_img)
        if len(live_faces) != 1:
            raise Denied(f'Test image must contain exactly one face (found {len(live_faces)}).')
        live_face = live_faces[0]
    else:
        print('Camera open - look at the camera and press SPACE.')
        live_img, live_face = capture_live(engine, cfg['camera'])

    score = engine.similarity(reg_feat, engine.embed(live_img, live_face))
    matched = score >= threshold
    detail = f'similarity {score:.3f} (threshold {threshold:.3f})'

    face_check_id = None
    if not args.no_record:
        face_check_id = backend.record_face_check(member['id'], matched, score, threshold)

    if not matched:
        raise Denied(f'Face does not match {name} - {detail}.')

    lines = [f'Welcome, {name}', detail,
             f"{(membership.get('plan') or {}).get('display_name', '')} | "
             f"{membership.get('days_remaining', '?')} days remaining".strip(' |')]
    if args.no_record:
        lines.append('(--no-record: check-in NOT saved)')
    else:
        ci = backend.check_in(member['id'], cfg['facility'], face_check_id)
        lines.append(f"Checked in at {cfg['facility']} (#{ci.get('id')})")
    return lines


def main():
    just_fix_windows_console()
    # Never crash on output: member names may be Arabic and Windows consoles may be cp1252.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(errors='replace')
    parser = argparse.ArgumentParser(description='Smart Gym entrance face check.')
    parser.add_argument('--iqama', help='Member Iqama number (10 digits, starts with 2)')
    parser.add_argument('--image', help='TESTING: compare against this image file instead of the webcam')
    parser.add_argument('--no-record', action='store_true', help='Do not save the face check / check-in')
    parser.add_argument('--threshold', type=float, help=f'Override MATCH_THRESHOLD (default {DEFAULT_THRESHOLD})')
    args = parser.parse_args()

    if not args.iqama:
        args.iqama = input('Iqama number: ').strip()
    if not (len(args.iqama) == 10 and args.iqama.isdigit() and args.iqama.startswith('2')):
        banner(False, ['Invalid Iqama number (10 digits, starts with 2).'])
        return 1

    started = time.monotonic()
    try:
        lines = run(args)
    except Denied as exc:
        banner(False, [str(exc)])
        show_result(False, [str(exc)])
        return 1
    except GateError as exc:
        print(f'{Fore.YELLOW}{Style.BRIGHT}GATE ERROR:{Style.RESET_ALL} {exc}')
        return 2

    lines.append(f'({time.monotonic() - started:.1f}s)')
    banner(True, lines)
    show_result(True, lines)
    return 0


if __name__ == '__main__':
    sys.exit(main())
