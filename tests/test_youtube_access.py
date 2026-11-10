import os
import tempfile
import unittest
from unittest.mock import patch
from api.youtube_access import youtube_options, download_error_response


class YoutubeAccessTests(unittest.TestCase):
    def test_node_enabled_without_implicitly_reading_cookies(self):
        with patch.dict(os.environ, {}, clear=True), patch('api.youtube_access.shutil.which', return_value='node'):
            opts = youtube_options({'quiet': True})
        self.assertIn('node', opts['js_runtimes'])
        self.assertNotIn('cookiesfrombrowser', opts)
        self.assertNotIn('cookiefile', opts)

    def test_explicit_cookie_file_takes_precedence(self):
        with tempfile.NamedTemporaryFile() as f:
            with patch.dict(os.environ, {'YOUTUBE_COOKIE_FILE': f.name, 'YOUTUBE_COOKIE_BROWSER': 'chrome'}):
                opts = youtube_options()
        self.assertEqual(opts['cookiefile'], os.path.abspath(f.name))
        self.assertNotIn('cookiesfrombrowser', opts)

    def test_block_and_decryption_failures_are_actionable(self):
        self.assertEqual(download_error_response(Exception('Sign in to confirm you are not a bot'))[:2], (429, 'YOUTUBE_ACCESS_BLOCKED'))
        self.assertEqual(download_error_response(Exception('Failed to decrypt with DPAPI'))[:2], (403, 'YOUTUBE_BROWSER_COOKIES_UNAVAILABLE'))


class ExtractionCacheTests(unittest.TestCase):
    def setUp(self):
        from api import youtube_access as access
        access._INFO_CACHE.clear()
        access._INFO_FAILURES.clear()

    def tearDown(self):
        self.setUp()

    def test_share_link_and_watch_link_reuse_one_extraction(self):
        from unittest.mock import MagicMock
        from api.youtube_access import extract_youtube_info
        ydl = MagicMock()
        expected = {'id': 'example', 'formats': [{'url': 'media'}]}
        ydl.__enter__.return_value.extract_info.return_value = expected
        with patch('yt_dlp.YoutubeDL', return_value=ydl) as constructor:
            self.assertEqual(extract_youtube_info('https://youtu.be/example?si=share', {'extract_flat': True}), expected)
            self.assertEqual(extract_youtube_info('https://www.youtube.com/watch?v=example'), expected)
        constructor.assert_called_once()
        self.assertNotIn('extract_flat', constructor.call_args.args[0])

    def test_blocked_requests_are_not_repeated_immediately(self):
        from unittest.mock import MagicMock
        from api.youtube_access import extract_youtube_info
        ydl = MagicMock()
        ydl.__enter__.return_value.extract_info.side_effect = RuntimeError('HTTP Error 429: Too Many Requests')
        with patch('yt_dlp.YoutubeDL', return_value=ydl) as constructor:
            for _ in range(2):
                with self.assertRaisesRegex(RuntimeError, '429'):
                    extract_youtube_info('https://youtu.be/blocked')
        constructor.assert_called_once()


class ServerOwnershipTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt', 'Windows port ownership regression')
    def test_second_local_backend_cannot_bind_existing_port(self):
        from server import ThreadedHTTPServer, GoddAIRequestHandler
        with ThreadedHTTPServer(('127.0.0.1', 0), GoddAIRequestHandler) as first:
            with self.assertRaises(OSError):
                with ThreadedHTTPServer(first.server_address, GoddAIRequestHandler):
                    pass
