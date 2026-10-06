"""Short-lived, resumable uploads for large admin-authored lesson videos."""

import json
import os
import shutil
import time
import uuid
from pathlib import Path, PurePosixPath

from django.conf import settings
from django.core import signing
from django.core.files import File
from django.core.files.storage import default_storage
from django.core.signing import BadSignature, SignatureExpired

from .validators import MAX_LESSON_FILE_SIZE_BYTES


VIDEO_UPLOAD_CHUNK_SIZE_BYTES = 8 * 1024 * 1024
VIDEO_UPLOAD_MAX_AGE_SECONDS = 24 * 60 * 60
VIDEO_REFERENCE_MAX_AGE_SECONDS = 2 * 60 * 60
VIDEO_UPLOAD_EXTENSIONS = {'.mp4', '.mov', '.webm', '.m4v'}
_UPLOAD_SALT = 'courses.video-upload-session'
_REFERENCE_SALT = 'courses.video-upload-reference'


class VideoUploadError(Exception):
    pass


def _upload_root():
    root = Path(settings.MEDIA_ROOT) / '.video_uploads'
    root.mkdir(parents=True, exist_ok=True)
    return root


def _remove_expired_sessions(root):
    cutoff = time.time() - VIDEO_UPLOAD_MAX_AGE_SECONDS
    for child in root.iterdir():
        try:
            if child.is_dir() and child.stat().st_mtime < cutoff:
                shutil.rmtree(child, ignore_errors=True)
        except OSError:
            continue


def _session(token, user_id):
    try:
        payload = signing.loads(token, salt=_UPLOAD_SALT, max_age=VIDEO_UPLOAD_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired) as exc:
        raise VideoUploadError('This upload session is invalid or has expired.') from exc
    if payload.get('user_id') != user_id:
        raise VideoUploadError('This upload session belongs to another user.')
    upload_id = payload.get('upload_id', '')
    if not isinstance(upload_id, str) or len(upload_id) != 32:
        raise VideoUploadError('This upload session is invalid.')
    session_dir = _upload_root() / upload_id
    metadata_path = session_dir / 'metadata.json'
    try:
        metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise VideoUploadError('This upload session could not be found.') from exc
    return session_dir, metadata


def start_video_upload(*, user_id, filename, size, content_type=''):
    filename = Path(str(filename or '')).name
    extension = PurePosixPath(filename).suffix.lower()
    if extension not in VIDEO_UPLOAD_EXTENSIONS:
        raise VideoUploadError('Upload an MP4, MOV, WEBM, or M4V video file.')
    try:
        size = int(size)
    except (TypeError, ValueError) as exc:
        raise VideoUploadError('A valid video file size is required.') from exc
    if size <= 0 or size > MAX_LESSON_FILE_SIZE_BYTES:
        raise VideoUploadError(
            f'Video size must be between 1 byte and {MAX_LESSON_FILE_SIZE_BYTES // (1024 * 1024)}MB.'
        )
    if content_type and not str(content_type).lower().startswith('video/'):
        raise VideoUploadError('The selected file is not recognized as a video.')

    upload_id = uuid.uuid4().hex
    upload_root = _upload_root()
    _remove_expired_sessions(upload_root)
    session_dir = upload_root / upload_id
    session_dir.mkdir()
    chunk_count = (size + VIDEO_UPLOAD_CHUNK_SIZE_BYTES - 1) // VIDEO_UPLOAD_CHUNK_SIZE_BYTES
    metadata = {
        'filename': filename,
        'extension': extension,
        'size': size,
        'content_type': content_type or '',
        'chunk_count': chunk_count,
    }
    (session_dir / 'metadata.json').write_text(json.dumps(metadata), encoding='utf-8')
    token = signing.dumps({'upload_id': upload_id, 'user_id': user_id}, salt=_UPLOAD_SALT, compress=True)
    return {'upload_id': token, 'chunk_size': VIDEO_UPLOAD_CHUNK_SIZE_BYTES, 'chunk_count': chunk_count}


def save_video_chunk(*, token, user_id, index, upload):
    session_dir, metadata = _session(token, user_id)
    try:
        index = int(index)
    except (TypeError, ValueError) as exc:
        raise VideoUploadError('A valid chunk index is required.') from exc
    if index < 0 or index >= metadata['chunk_count']:
        raise VideoUploadError('Chunk index is outside this upload session.')
    expected_size = min(
        VIDEO_UPLOAD_CHUNK_SIZE_BYTES,
        metadata['size'] - (index * VIDEO_UPLOAD_CHUNK_SIZE_BYTES),
    )
    if upload.size != expected_size:
        raise VideoUploadError(f'Chunk {index + 1} has an unexpected size.')

    final_path = session_dir / f'{index:06d}.part'
    temporary_path = session_dir / f'{index:06d}.{uuid.uuid4().hex}.tmp'
    with temporary_path.open('wb') as destination:
        for block in upload.chunks():
            destination.write(block)
    os.replace(temporary_path, final_path)
    return {'received': index, 'size': upload.size}


def complete_video_upload(*, token, user_id):
    session_dir, metadata = _session(token, user_id)
    chunk_paths = [session_dir / f'{index:06d}.part' for index in range(metadata['chunk_count'])]
    if any(not path.is_file() for path in chunk_paths):
        raise VideoUploadError('One or more video chunks are missing. Please retry the upload.')
    if sum(path.stat().st_size for path in chunk_paths) != metadata['size']:
        raise VideoUploadError('The uploaded video size does not match the selected file.')

    stored_name = f'element_videos/{uuid.uuid4().hex}{metadata["extension"]}'
    assembled_path = session_dir / 'assembled.tmp'
    with assembled_path.open('wb') as destination:
        for chunk_path in chunk_paths:
            with chunk_path.open('rb') as source:
                shutil.copyfileobj(source, destination, length=1024 * 1024)

    try:
        final_path = Path(default_storage.path(stored_name))
    except NotImplementedError:
        with assembled_path.open('rb') as source:
            stored_name = default_storage.save(stored_name, File(source))
    else:
        final_path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(assembled_path, final_path)

    shutil.rmtree(session_dir, ignore_errors=True)
    reference = signing.dumps(
        {'path': stored_name, 'user_id': user_id, 'size': metadata['size']},
        salt=_REFERENCE_SALT,
        compress=True,
    )
    return {'video_upload_token': reference, 'name': metadata['filename'], 'size': metadata['size']}


def resolve_video_upload_reference(token, user_id):
    try:
        payload = signing.loads(token, salt=_REFERENCE_SALT, max_age=VIDEO_REFERENCE_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired) as exc:
        raise VideoUploadError('This completed video upload is invalid or has expired.') from exc
    if payload.get('user_id') != user_id:
        raise VideoUploadError('This completed video upload belongs to another user.')
    stored_name = payload.get('path', '')
    if not isinstance(stored_name, str) or not stored_name.startswith('element_videos/'):
        raise VideoUploadError('This completed video upload is invalid.')
    if not default_storage.exists(stored_name):
        raise VideoUploadError('The uploaded video file could not be found.')
    return stored_name
