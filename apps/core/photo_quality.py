"""
Is a face photo clear enough to identify the member at the gate? Checks size, light and
sharpness with Pillow (no extra libraries). The browser runs the same checks before upload
(website LiveCamera.jsx); this is the authority.
"""
from PIL import Image, ImageFilter, ImageOps, ImageStat, UnidentifiedImageError

MIN_SIDE = 240            # px — anything smaller can't be matched reliably
DARK, BRIGHT = 45, 225    # mean grey level (0–255)
FLAT = 18                 # grey std-dev: lower = covered lens / blank wall
BLUR_MIN = 90             # Laplacian variance at 480 px: sharp photos score 150+, blurred < 80

LAPLACIAN = ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], scale=1, offset=128)


def photo_problem(file):
    """A sentence telling the person what to fix, or None when the photo is fine."""
    try:
        file.seek(0)
        img = Image.open(file)
        img.load()
    except (UnidentifiedImageError, OSError, ValueError):
        return 'This file isn’t a photo we can read. Take the photo again with the camera.'
    finally:
        try:
            file.seek(0)
        except (AttributeError, OSError):
            pass
    img = ImageOps.exif_transpose(img)
    if min(img.size) < MIN_SIDE:
        return 'The photo is too small. Move closer to the camera and take it again.'
    grey = img.convert('L')
    grey.thumbnail((480, 480))
    stat = ImageStat.Stat(grey)
    mean, spread = stat.mean[0], stat.stddev[0]
    if mean < DARK:
        return 'The photo is too dark. Face a light or window and take it again.'
    if mean > BRIGHT:
        return 'The photo is too bright. Move away from direct light and take it again.'
    if spread < FLAT:
        return 'We can’t see a face in this photo. Make sure the camera isn’t covered and your face fills the frame.'
    if ImageStat.Stat(grey.filter(LAPLACIAN)).var[0] < BLUR_MIN:
        return 'The photo is blurry. Hold still, keep your face in focus and take it again.'
    return None
