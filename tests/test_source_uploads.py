import io
import json
import os
import tempfile
import unittest
from unittest.mock import patch
from source_uploads import SourceUploads, MAX_CHUNK_BYTES


class SourceUploadTests(unittest.TestCase):
    def test_complete_file_requires_all_ordered_chunks(self):
        with tempfile.TemporaryDirectory() as directory:
            uploads=SourceUploads(directory)
            token=uploads.create(6)
            with self.assertRaises(ValueError): uploads.completed_path(token)
            uploads.append(token,0,io.BytesIO(b'abc'),3)
            self.assertEqual(uploads.append(token,0,io.BytesIO(b'abc'),3),3)
            with self.assertRaises(ValueError): uploads.append(token,1,io.BytesIO(b'abc'),3)
            uploads.append(token,3,io.BytesIO(b'def'),3)
            with open(uploads.completed_path(token),'rb') as f: self.assertEqual(f.read(),b'abcdef')

    def test_interrupted_chunk_is_rolled_back(self):
        with tempfile.TemporaryDirectory() as directory:
            uploads=SourceUploads(directory)
            token=uploads.create(6)
            with self.assertRaises(ValueError): uploads.append(token,0,io.BytesIO(b'ab'),3)
            self.assertEqual(uploads.entries[token]['received'],0)
            uploads.append(token,0,io.BytesIO(b'abcdef'),6)
            with open(uploads.completed_path(token),'rb') as f: self.assertEqual(f.read(),b'abcdef')

    def test_quota_and_expired_tokens_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            uploads=SourceUploads(directory,quota=6)
            token=uploads.create(6)
            with self.assertRaises(ValueError): uploads.create(1)
            with self.assertRaises(ValueError): uploads.append('unknown',0,io.BytesIO(b'a'),1)

    def test_non_video_upload_is_rejected_before_rendering(self):
        from source_uploads import validate_uploaded_video
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'not a video')
            path=f.name
        try:
            with self.assertRaises(ValueError): validate_uploaded_video(path)
        finally:
            os.remove(path)
