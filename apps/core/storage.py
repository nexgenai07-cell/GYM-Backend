"""
Cloudinary storage for user uploads (registration photos, avatars).

Built on Cloudinary's official SDK rather than the unmaintained
django-cloudinary-storage package. Files are uploaded as delivery type
"authenticated" by default: they can't be fetched by a public URL, only via
signed URLs generated here — registration photos are faces used for gate access.

Stored names look like Django's ("registrations/2026/10/live-photo_k3j9x2.jpg");
the Cloudinary public_id is "<CLOUDINARY_FOLDER>/<name without extension>".
"""
import secrets
from pathlib import PurePosixPath

import cloudinary
import cloudinary.uploader
import cloudinary.utils
from django.conf import settings
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible


@deconstructible
class CloudinaryMediaStorage(Storage):
    resource_type = 'image'   # only ImageFields use this storage

    def __init__(self, folder=None, delivery_type=None):
        self.folder = (folder if folder is not None else settings.CLOUDINARY_FOLDER).strip('/')
        self.delivery_type = delivery_type or settings.CLOUDINARY_DELIVERY_TYPE
        cloudinary.config(
            cloud_name=settings.CLOUDINARY_CLOUD_NAME,
            api_key=settings.CLOUDINARY_API_KEY,
            api_secret=settings.CLOUDINARY_API_SECRET,
            secure=True,
        )

    # ---------- naming ----------
    @staticmethod
    def _clean(name):
        # Django builds upload paths with os.path, so on Windows they arrive as
        # "registrations\2026\10\x.jpg"; Cloudinary public_ids use "/".
        return name.replace('\\', '/')

    def _public_id(self, name):
        stem = str(PurePosixPath(self._clean(name)).with_suffix(''))
        return f'{self.folder}/{stem}' if self.folder else stem

    @staticmethod
    def _format(name):
        return PurePosixPath(name).suffix.lstrip('.').lower() or None

    def get_available_name(self, name, max_length=None):
        """Always add a random suffix instead of asking Cloudinary whether the
        name is taken (that check uses the rate-limited Admin API)."""
        path = PurePosixPath(self._clean(name))
        candidate = str(path.with_name(f'{path.stem}_{secrets.token_hex(4)}{path.suffix}'))
        if max_length and len(candidate) > max_length:
            excess = len(candidate) - max_length
            candidate = str(path.with_name(f'{path.stem[:-excess]}_{secrets.token_hex(4)}{path.suffix}'))
        return candidate

    def exists(self, name):
        return False   # names are made unique in get_available_name

    # ---------- Storage API ----------
    def _save(self, name, content):
        name = self._clean(name)
        if hasattr(content, 'seek'):
            content.seek(0)
        cloudinary.uploader.upload(
            content,
            public_id=self._public_id(name),
            resource_type=self.resource_type,
            type=self.delivery_type,
            overwrite=False,
            unique_filename=False,
            use_filename=False,
        )
        return name

    def delete(self, name):
        if name:
            cloudinary.uploader.destroy(
                self._public_id(name),
                resource_type=self.resource_type,
                type=self.delivery_type,
                invalidate=True,
            )

    def url(self, name):
        url, _ = cloudinary.utils.cloudinary_url(
            self._public_id(name),
            resource_type=self.resource_type,
            type=self.delivery_type,
            format=self._format(name),
            sign_url=self.delivery_type != 'upload',
            secure=True,
        )
        return url
