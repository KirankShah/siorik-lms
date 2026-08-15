from io import BytesIO

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile
from PIL import Image

# A small margin so the crop doesn't hug the character's silhouette so
# tightly it looks clipped at the edges.
CROP_PADDING_RATIO = 0.04


def crop_to_opaque_bounds(image_field):
    """
    Tightly crops a freshly-uploaded PNG down to its actual non-transparent
    content. AI-illustration-pack exports (this app's avatar source) are
    routinely delivered on a large, mostly-transparent square canvas with
    the character occupying a modest fraction of it — rendered at a fixed
    stage height without this, the character looks much smaller than
    intended relative to the scene (see Character.save()). No-op for SVG
    (no pixel alpha to inspect), an image with no meaningful transparent
    margin, or a file that isn't actually a fresh upload (re-saving an
    unchanged FieldFile loaded from storage isn't an UploadedFile).
    """
    if not isinstance(image_field.file, UploadedFile):
        return None
    if not image_field.name.lower().endswith('.png'):
        return None

    image_field.seek(0)
    image = Image.open(image_field).convert('RGBA')
    bbox = image.getchannel('A').getbbox()
    if bbox is None or bbox == (0, 0, image.width, image.height):
        return None

    left, top, right, bottom = bbox
    pad_x = round((right - left) * CROP_PADDING_RATIO)
    pad_y = round((bottom - top) * CROP_PADDING_RATIO)
    left = max(0, left - pad_x)
    top = max(0, top - pad_y)
    right = min(image.width, right + pad_x)
    bottom = min(image.height, bottom + pad_y)

    buffer = BytesIO()
    image.crop((left, top, right, bottom)).save(buffer, format='PNG')
    return ContentFile(buffer.getvalue())
