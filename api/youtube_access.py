"""Shared YouTube setup. Browser credentials are used only by explicit configuration."""
import os
import shutil
import time
import threading
import urllib.parse


def original_caption_formats(info, preferred_languages):
    """Use the original audio language before considering translated tracks."""
    manual = info.get("subtitles") or {}
    automatic = info.get("automatic_captions") or {}
    originals = [lang for lang, formats in automatic.items() if lang.endswith("-orig") and formats]
    if originals:
        # A dubbed track can also be marked "-orig" within its own language.
        # Prefer the video's declared original language over guesses from its title.
        language = info.get("language")
        candidates = [language] if isinstance(language, str) and language else []
        if candidates:
            candidates.append(language.split("-")[0])
        lang = next((code + "-orig" for code in (*candidates, *preferred_languages) if code + "-orig" in originals),
                    originals[0])
        return manual.get(lang.removesuffix("-orig")) or automatic[lang]
    for lang in preferred_languages:
        formats = manual.get(lang) or automatic.get(lang)
        if formats:
            return formats
    return next(iter((manual or automatic).values()), [])

_INFO_CACHE = {}
_INFO_FAILURES = {}
_INFO_LOCK = threading.Lock()


def youtube_options(options=None):
    result = {'noplaylist': True, 'socket_timeout': 20, 'retries': 1, 'extractor_retries': 1}
    if shutil.which('node'):
        result['js_runtimes'] = {'node': {'path': shutil.which('node')}}
    elif shutil.which('deno'):
        result['js_runtimes'] = {'deno': {'path': shutil.which('deno')}}
    cookie_file = os.environ.get('YOUTUBE_COOKIE_FILE', '').strip()
    browser = os.environ.get('YOUTUBE_COOKIE_BROWSER', '').strip().lower()
    if cookie_file:
        cookie_file = os.path.abspath(os.path.expanduser(cookie_file))
        if not os.path.isfile(cookie_file):
            raise RuntimeError('The configured YouTube cookie file does not exist.')
        result['cookiefile'] = cookie_file
    elif browser:
        if browser not in ('chrome', 'edge', 'firefox', 'brave'):
            raise RuntimeError('Unsupported configured YouTube cookie browser.')
        result['cookiesfrombrowser'] = (browser,)
    result.update(options or {})
    home = os.environ.get('YOUTUBE_PO_PROVIDER_HOME', '').strip()
    if home and os.path.isfile(os.path.join(home, 'build', 'generate_once.js')):
        # Provider is invoked only for extraction, so it does not compete with
        # FFmpeg or speech recognition for memory on the free host.
        args = dict(result.get('extractor_args') or {})
        args['youtubepot-bgutilscript'] = {'server_home': [home]}
        youtube_args = dict(args.get('youtube') or {})
        youtube_args['player_client'] = ['mweb', 'web_safari', 'web_embedded']
        args['youtube'] = youtube_args
        result['extractor_args'] = args
    return result


def download_error_response(error):
    text = str(error).lower()
    if 'dpapi' in text or 'could not copy chrome cookie database' in text or 'decrypt' in text:
        return 403, 'YOUTUBE_BROWSER_COOKIES_UNAVAILABLE', (
            'Chrome cookies could not be read on this computer. The video has not been downloaded. '
            'Use a YouTube-only Netscape cookies file via YOUTUBE_COOKIE_FILE, or retry when YouTube allows anonymous access.')
    if any(term in text for term in ('confirm you', 'not a bot', 'sign in', '429', 'too many requests')):
        return 429, 'YOUTUBE_ACCESS_BLOCKED', (
            'YouTube blocked access to this video before rendering could start. '
            'Choose Upload original video and retry to render the same clip from a video you provide. '
            'This avoids the blocked YouTube fetch and still generates subtitles on the server.')
    return 500, 'CLIP_RENDER_FAILED', str(error)


def extract_youtube_info(url, options=None):
    """Reuse one full extraction across metadata, captions, and clip exports.

    Cache for five minutes, well below normal signed URL expiry. Keep original
    YouTube IDs as keys so share links and watch links share the same entry.
    """
    import yt_dlp
    parsed = urllib.parse.urlparse(url)
    video_id = urllib.parse.parse_qs(parsed.query).get('v', [None])[0]
    if parsed.hostname in ('youtu.be', 'www.youtu.be'):
        video_id = parsed.path.strip('/').split('/')[0]
    key = (video_id or url, os.environ.get('YOUTUBE_COOKIE_FILE', ''),
           os.environ.get('YOUTUBE_COOKIE_BROWSER', ''))
    with _INFO_LOCK:
        now = time.monotonic()
        failed = _INFO_FAILURES.get(key)
        if failed and now - failed[0] < 60:
            raise RuntimeError(failed[1])
        cached = _INFO_CACHE.get(key)
        lifetime = 15 if cached and cached[1].get("is_live") else 300
        if cached and now - cached[0] < lifetime:
            return cached[1]
        opts = dict(options or {})
        # A complete cached response can serve every caller without another
        # watch-page/player request. Do not cache flattened placeholder data.
        opts.pop('extract_flat', None)
        opts.setdefault('format', 'bestvideo[height<=1080]+bestaudio/best')
        try:
            with yt_dlp.YoutubeDL(youtube_options(opts)) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as error:
            if download_error_response(error)[1] == 'YOUTUBE_ACCESS_BLOCKED':
                _INFO_FAILURES[key] = (time.monotonic(), str(error))
            raise
        _INFO_FAILURES.pop(key, None)
        _INFO_CACHE[key] = (time.monotonic(), info)
        for old_key in list(_INFO_CACHE):
            if time.monotonic() - _INFO_CACHE[old_key][0] >= 300:
                del _INFO_CACHE[old_key]
        return info
