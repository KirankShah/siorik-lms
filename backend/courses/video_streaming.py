"""
Authenticated video streaming for uploaded Element.video_file content.

A plain `<video src="...">` tag can't attach the Authorization header this
app's JWT auth normally requires (browsers don't let you set custom headers
on a native media element's request), so a signed, short-lived, per-user,
per-element token is embedded in the URL itself instead — the standard
pattern for authenticated media delivery behind an ordinary <video> tag
(the same idea as an S3/CloudFront pre-signed URL). This intentionally
replaces exposing Element.video_file's raw storage URL (permanently public,
unauthenticated, and directly downloadable) with a URL that expires, is
scoped to one element and one user, and is re-checked against that user's
current course visibility (and demo-lock status) on every request.
"""
import mimetypes
import re

from django.core import signing
from django.http import FileResponse, Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404

from accounts.models import User

from .models import Element
from .permissions import is_lesson_locked_for_demo_user, visible_courses_for_user

_TOKEN_SALT = 'courses.element.video-stream'
# Generous rather than tight — long enough that a learner mid-way through a
# long training video, or one who leaves a tab open on a break, never has
# playback fail out from under them. Still expires same-day if a URL leaks,
# unlike the permanent public link this replaces.
TOKEN_MAX_AGE_SECONDS = 4 * 60 * 60

_RANGE_RE = re.compile(r'^bytes=(\d*)-(\d*)$')


def build_video_stream_token(user_id, element_id):
    return signing.dumps({'user_id': user_id, 'element_id': element_id}, salt=_TOKEN_SALT)


def _verify_video_stream_token(token, element_id):
    """Returns the signed-in user_id, or None if the token is missing/expired/tampered/for a different element."""
    try:
        payload = signing.loads(token, salt=_TOKEN_SALT, max_age=TOKEN_MAX_AGE_SECONDS)
    except signing.BadSignature:
        return None
    if payload.get('element_id') != element_id:
        return None
    return payload.get('user_id')


class _BoundedStream:
    """Wraps a file handle already seek()'d to a range's start, capping reads at `length` bytes total."""

    def __init__(self, handle, length):
        self._handle = handle
        self._remaining = length

    def read(self, size=-1):
        if self._remaining <= 0:
            return b''
        size = self._remaining if size is None or size < 0 else min(size, self._remaining)
        chunk = self._handle.read(size)
        self._remaining -= len(chunk)
        return chunk

    def close(self):
        self._handle.close()


def stream_element_video(request, pk):
    """
    GET /api/elements/<pk>/video/?token=<signed token>

    Deliberately outside DRF's normal IsAuthenticated/JWT flow (see module
    docstring) — authorization here is entirely the token's job, re-checked
    live against the token's embedded user on every request rather than
    trusted for its full lifetime, so a deactivated account or a revoked
    course grant takes effect immediately rather than waiting for expiry.
    """
    element_id = int(pk)
    user_id = _verify_video_stream_token(request.GET.get('token', ''), element_id)
    if user_id is None:
        return HttpResponseForbidden('This video link is invalid or has expired.')

    try:
        user = User.objects.get(pk=user_id, is_active=True)
    except User.DoesNotExist:
        return HttpResponseForbidden('This video link is invalid or has expired.')

    element = get_object_or_404(
        Element.objects.filter(
            element_type=Element.ElementType.VIDEO_AUDIO,
            slide__lesson__module__course__in=visible_courses_for_user(user),
        ),
        pk=element_id,
    )
    if not element.video_file:
        raise Http404
    if is_lesson_locked_for_demo_user(user, element.slide.lesson):
        return HttpResponseForbidden('This content is not available in your demo access.')

    content_type = mimetypes.guess_type(element.video_file.name)[0] or 'application/octet-stream'
    file_size = element.video_file.size
    range_match = _RANGE_RE.match(request.META.get('HTTP_RANGE', ''))

    if range_match and (range_match.group(1) or range_match.group(2)):
        start_str, end_str = range_match.groups()
        start = int(start_str) if start_str else 0
        end = min(int(end_str), file_size - 1) if end_str else file_size - 1
        if start >= file_size or start > end:
            response = HttpResponse(status=416)
            response['Content-Range'] = f'bytes */{file_size}'
            return response

        handle = element.video_file.open('rb')
        handle.seek(start)
        length = end - start + 1
        response = FileResponse(_BoundedStream(handle, length), status=206, content_type=content_type)
        response['Content-Range'] = f'bytes {start}-{end}/{file_size}'
        response['Content-Length'] = str(length)
    else:
        response = FileResponse(element.video_file.open('rb'), content_type=content_type)
        response['Content-Length'] = str(file_size)

    response['Accept-Ranges'] = 'bytes'
    response['Content-Disposition'] = 'inline'
    # Each URL is single-user/single-element and expires — nothing here
    # should be cached by a shared/proxy cache.
    response['Cache-Control'] = 'private, max-age=0, no-store'
    return response
