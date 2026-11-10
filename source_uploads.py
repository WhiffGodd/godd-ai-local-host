"""Bounded, chunked source uploads for videos a visitor provides directly."""
import os
import secrets
import tempfile
import threading
import time

MAX_FILE_BYTES = 1024 * 1024 * 1024
MAX_CHUNK_BYTES = 4 * 1024 * 1024


class SourceUploads:
    def __init__(self, directory=None, quota=MAX_FILE_BYTES * 2):
        self.directory = directory or os.path.join(tempfile.gettempdir(), 'godd_ai_sources')
        os.makedirs(self.directory, exist_ok=True)
        self.quota = quota
        self.entries = {}
        self.lock = threading.Lock()

    def _prune(self):
        now = time.monotonic()
        for token, entry in list(self.entries.items()):
            if now-entry['updated'] > 3600:
                try:
                    os.remove(entry['path'])
                except OSError:
                    continue
                del self.entries[token]

    def create(self, size):
        if isinstance(size, bool) or not isinstance(size, int) or not 1 <= size <= MAX_FILE_BYTES:
            raise ValueError('Choose a video smaller than 1 GB.')
        with self.lock:
            self._prune()
            if len(self.entries) >= 8 or sum(e['size'] for e in self.entries.values()) + size > self.quota:
                raise ValueError('Upload storage is busy. Please try again later.')
            token = secrets.token_urlsafe(24)
            path = os.path.join(self.directory, token+'.source')
            with open(path, 'xb'):
                pass
            self.entries[token] = {'path':path,'size':size,'received':0,'updated':time.monotonic()}
            return token

    def append(self, token, offset, stream, length):
        with self.lock:
            self._prune()
            entry = self.entries.get(token)
            if not entry:
                raise ValueError('Upload expired. Please choose the video again.')
            if not 1 <= length <= MAX_CHUNK_BYTES or offset < 0 or offset + length > entry['size']:
                raise ValueError('Upload chunk is out of order or too large.')
            if offset != entry['received']:
                if offset + length != entry['received']:
                    raise ValueError('Upload chunk is out of order.')
                # A response can be lost after a successful write. A repeated
                # identical chunk is acknowledged without duplicating bytes.
                remaining = length
                with open(entry['path'], 'rb') as existing:
                    existing.seek(offset)
                    while remaining:
                        data = stream.read(min(65536, remaining))
                        if not data or existing.read(len(data)) != data:
                            raise ValueError('Retried upload chunk did not match.')
                        remaining -= len(data)
                return entry['received']
            remaining = length
            # Restore the acknowledged offset if a disconnected request left a
            # partial chunk, so retrying cannot corrupt or duplicate the file.
            with open(entry['path'], 'r+b') as f:
                f.seek(offset)
                f.truncate()
                try:
                    while remaining:
                        chunk = stream.read(min(65536,remaining))
                        if not chunk:
                            raise ValueError('Upload interrupted. Please retry.')
                        f.write(chunk)
                        remaining -= len(chunk)
                except Exception:
                    f.seek(offset)
                    f.truncate()
                    raise
            entry['received'] += length
            entry['updated'] = time.monotonic()
            return entry['received']

    def completed_path(self, token):
        with self.lock:
            self._prune()
            entry = self.entries.get(token)
            if not entry or entry['received'] != entry['size']:
                raise ValueError('The source video has not finished uploading.')
            entry['updated'] = time.monotonic()
            return entry['path']


def validate_uploaded_video(path):
    import av
    try:
        with av.open(path, options={'protocol_whitelist':'file,pipe'}) as container:
            formats = set(container.format.name.split(','))
            if not formats.intersection({'mov','mp4','matroska','webm'}):
                raise ValueError('Choose an MP4, MOV, WebM or MKV video file.')
            if not container.streams.video or not container.streams.audio:
                raise ValueError('The uploaded video must contain video and audio.')
    except ValueError:
        raise
    except Exception as error:
        raise ValueError('The uploaded file could not be read as a video. Choose an MP4, MOV, WebM or MKV file.') from error
    return path
