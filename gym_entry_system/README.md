# Gym entry gate (face check)

Standalone "gate controller" for the entrance laptop. Given a member's Iqama
number it fetches their registration photo from the backend, takes a live
photo with the webcam, compares the faces with OpenCV (YuNet detection +
SFace recognition) and shows **ACCESS GRANTED - OK** (green) or
**ACCESS DENIED** (red). Every attempt is logged via the face-verify endpoint;
a match also records the check-in.

## Setup (Command Prompt)

```bat
cd C:\Users\Hamna\Desktop\smart-gym-backend\gym_entry_system
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
notepad .env
```

Fill in `GATE_STAFF_EMAIL` / `GATE_STAFF_PASSWORD` with a staff account
(`is_staff`, or role `admin`/`manager`). The two face models (~39 MB) download
on the first run into `models\` and are verified by SHA-256.

## Run

```bat
venv\Scripts\python.exe gate_check.py --iqama 2999888777
```

A camera window opens: look at the camera and press **SPACE** (only enabled
with exactly one face in view), **ESC** to cancel. The result shows full-screen
for 5 seconds (any key closes it) and in the terminal.

| Option | Use |
|---|---|
| `--iqama N` | Member to check (prompted if omitted) |
| `--no-record` | Don't save the face check / check-in (dry run) |
| `--image FILE` | Testing: use an image file instead of the webcam |
| `--threshold X` | Override `MATCH_THRESHOLD` for this run |

Exit code: `0` granted, `1` denied, `2` error (config, network, camera).

## Why it can deny

- No member / registration not yet approved
- Membership not valid (expired, frozen, inactive)
- Already checked in today with no check-out
- No usable face in the registered photo
- Live face doesn't match (similarity below `MATCH_THRESHOLD`)

## Notes

- **Local storage:** with `R2_*` unset the backend keeps photos in
  `media\`, served only when it runs with `DEBUG=True`. Point
  `API_BASE_URL` at that local backend.
- **Not anti-spoofing:** this checks *who* is in front of the camera, not that
  they're live — a good printed photo or a screen could pass. Keep staff
  oversight at the gate.
- **Threshold:** 0.363 is OpenCV's recommended SFace cosine threshold. Watch
  real-world scores (printed on every run) before tightening it.
