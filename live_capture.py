"""Freeze a bounded, available HLS window before analyzing or exporting a live stream."""

from contextlib import contextmanager
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import math
import os
import re
import subprocess
import tempfile
import threading
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

from video_engine import FFMPEG_PATH, stream_http_input_args


class ReplayTooShort(ValueError):
    pass


def _media_url(base, value):
    url = urljoin(base, value)
    if urlsplit(url).scheme not in ("http", "https"):
        raise ValueError("The live playlist contains an unsupported media address.")
    return url


def freeze_hls(text, base, seconds, until=None):
    """Keep complete segments from the DVR tail with original sequence and key state."""
    if not text.startswith("#EXTM3U"):
        raise ValueError("The live stream did not return an HLS playlist.")
    segments, pending, headers = [], [], []
    key = init = None
    sequence = discontinuities = 0
    duration = clock = None
    byte_ends = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXT-X-STREAM-INF"):
            raise ValueError("The live stream needs a media playlist.")
        if line.startswith("#EXT-X-MEDIA-SEQUENCE:"):
            sequence = int(line.split(":",1)[1])
        elif line.startswith("#EXT-X-DISCONTINUITY-SEQUENCE:"):
            discontinuities = int(line.split(":",1)[1])
        elif line.startswith(("#EXT-X-KEY:", "#EXT-X-MAP:")):
            line = re.sub(r'URI="([^"]+)"', lambda match: 'URI="'+_media_url(base,match[1])+'"', line)
            if line.startswith("#EXT-X-KEY"):
                key = line
            else:
                init = line
        elif line.startswith("#EXTINF:"):
            duration = float(line.split(":",1)[1].split(",")[0])
            if not math.isfinite(duration) or duration <= 0:
                raise ValueError("The live playlist contains an invalid segment duration.")
            pending.append(line)
        elif not line.startswith("#"):
            if duration is not None:
                address = _media_url(base,line)
                for index,tag in enumerate(pending):
                    if tag.startswith("#EXT-X-BYTERANGE:"):
                        length,_,offset = tag.split(":",1)[1].partition("@")
                        first = int(offset) if offset else byte_ends.get(address,0)
                        pending[index] = f"#EXT-X-BYTERANGE:{length}@{first}"
                        byte_ends[address] = first+int(length)
                segments.append((duration, [*pending,address], key, init, discontinuities,clock))
                if clock is not None:
                    clock += duration
                duration, pending = None, []
        elif line.startswith("#EXT-X-DISCONTINUITY"):
            discontinuities += 1
            pending.append(line)
        elif line.startswith("#EXT-X-PROGRAM-DATE-TIME:"):
            clock = datetime.fromisoformat(line.split(":",1)[1].replace("Z","+00:00")).timestamp()
            pending.append(line)
        elif line.startswith("#EXT-X-BYTERANGE:"):
            pending.append(line)
        elif line.startswith(("#EXT-X-TARGETDURATION:", "#EXT-X-VERSION:", "#EXT-X-INDEPENDENT-SEGMENTS")):
            headers.append(line)
    if not segments:
        raise ValueError("This stream has no complete DVR segments yet. Try again after it has run longer.")
    stop = len(segments)
    if until is not None:
        while stop and segments[stop-1][5] is not None and segments[stop-1][5] >= until:
            stop -= 1
    total, start = 0., stop
    while start and total < seconds:
        start -= 1
        total += segments[start][0]
    if total < 75:
        raise ReplayTooShort("This stream exposes less than 75 seconds of replay.")
    leading_discontinuity = int("#EXT-X-DISCONTINUITY" in segments[start][1])
    output = ["#EXTM3U", *headers, f"#EXT-X-MEDIA-SEQUENCE:{sequence+start}",
              f"#EXT-X-DISCONTINUITY-SEQUENCE:{segments[start][4]-leading_discontinuity}", "#EXT-X-PLAYLIST-TYPE:VOD"]
    previous_key = previous_init = None
    for _, lines, key, init, _, clock in segments[start:stop]:
        if key and key != previous_key:
            output.append(key)
            previous_key = key
        if init and init != previous_init:
            output.append(init)
            previous_init = init
        if clock is not None and not any(line.startswith("#EXT-X-PROGRAM-DATE-TIME:") for line in lines):
            output.append("#EXT-X-PROGRAM-DATE-TIME:"+datetime.fromtimestamp(clock).astimezone().isoformat())
        output.extend(lines)
    output.append("#EXT-X-ENDLIST")
    return "\n".join(output)+"\n", total


def playlist_times(text):
    clock = first = None
    for line in text.splitlines():
        if line.startswith("#EXT-X-PROGRAM-DATE-TIME:"):
            clock = datetime.fromisoformat(line.split(":",1)[1].replace("Z","+00:00")).timestamp()
            if first is None:
                first = clock
        elif line.startswith("#EXTINF:") and clock is not None:
            clock += float(line.split(":",1)[1].split(",")[0])
    return (first,clock) if first is not None else None


@contextmanager
def _playlist_server(playlists):
    if not playlists:
        yield None
        return
    manifests = {f"/window-{index}.m3u8": text.encode("utf-8") for index,(text,_) in enumerate(playlists)}
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            content = manifests.get(self.path)
            if content is None:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type","application/vnd.apple.mpegurl")
            self.send_header("Content-Length",str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, *_):
            pass

    with ThreadingHTTPServer(("127.0.0.1",0),Handler) as server:
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            yield f"http://127.0.0.1:{server.server_port}"
        finally:
            server.shutdown()


def capture_live_window(info, seconds, report):
    formats = info.get("formats") or []
    playable = [item for item in formats if item.get("url") and item.get("vcodec") not in (None,"none","")
                and "m3u8" in item.get("protocol","") and (item.get("height") or 0) <= 1080]
    if not playable:
        raise ValueError("This live stream has no accessible replay playlist. Enable DVR on the stream or retry after it ends.")
    stream = max(playable, key=lambda item: ((item.get("height") or 0) <= 720, item.get("height") or 0))
    streams = [stream]
    if stream.get("acodec") == "none":
        audios = [item for item in formats if item.get("url") and item.get("vcodec") == "none"
                  and "m3u8" in item.get("protocol","") and item.get("acodec") != "none"]
        if not audios:
            raise ValueError("This live stream has no accessible audio track.")
        streams.append(max(audios,key=lambda item: (item.get("abr") or item.get("tbr") or 0,str(item.get("format_id","")))))
    report("Reading the live replay window", None)
    playlists = []
    for rendition in streams:
        request = Request(rendition["url"],headers=rendition.get("http_headers") or info.get("http_headers") or {})
        with urlopen(request,timeout=25) as response:
            text = response.read(8*1024*1024).decode("utf-8-sig")
            playlists.append((text,response.url))
    bounds = [playlist_times(text) for text,_ in playlists]
    if len(streams)>1 and not all(bounds):
        raise ValueError("The live audio and video playlists have no shared clock for synchronization.")
    until = min(bound[1] for bound in bounds if bound) if any(bounds) else None
    try:
        frozen = [freeze_hls(text,base,seconds,until) for text,base in playlists]
        duration = min(length for _,length in frozen)
    except ReplayTooShort:
        frozen,duration = None,min(seconds,180)
    fd, output = tempfile.mkstemp(prefix="godd_live_",suffix=".mp4")
    os.close(fd)
    try:
        with _playlist_server(frozen) as relay:
            command = [FFMPEG_PATH,"-y","-v","error"]
            if frozen:
                report("Saving the available live replay window", None)
            else:
                report("Recording the next 3 minutes of live footage", None)
            selected_bounds = [playlist_times(text) for text,_ in frozen] if frozen else []
            start = max(bound[0] for bound in selected_bounds if bound) if any(selected_bounds) else None
            for index,rendition in enumerate(streams):
                options = ["-rw_timeout","20000000",*stream_http_input_args(info,rendition["url"])]
                if frozen:
                    options += ["-protocol_whitelist","http,https,tcp,tls,crypto"]
                    if start is not None:
                        options += ["-ss",str(max(0,start-selected_bounds[index][0]))]
                    source = f"{relay}/window-{index}.m3u8"
                else:
                    options += ["-live_start_index","-1"]
                    source = rendition["url"]
                command.extend([*options,"-i",source])
            if start is not None:
                duration = min(duration,until-start)
            command += ["-t",str(duration),"-map","0:v:0","-map",f"{len(streams)-1}:a:0",
                        "-c","copy","-avoid_negative_ts","make_zero","-movflags","+faststart",output]
            try:
                subprocess.run(command,capture_output=True,check=True,timeout=max(180,duration*2))
            except subprocess.CalledProcessError as error:
                detail = error.stderr.decode(errors="replace").lower()
                if "403" in detail or "401" in detail:
                    raise ValueError("YouTube denied access to the live media. Retry the stream or check the configured YouTube login.") from None
                raise ValueError("Could not save the live replay. Retry to refresh the stream addresses.") from None
            except subprocess.TimeoutExpired:
                raise ValueError("The live replay download stalled. Retry the stream.") from None
        import av
        with av.open(output) as container:
            measured = container.duration / av.time_base if container.duration else 0
            if measured < 60 or not container.streams.video or not container.streams.audio:
                raise ValueError("The live replay window did not contain enough playable video and speech.")
        return output, measured
    except Exception:
        os.remove(output)
        raise
