"""Styled ASS captions with explicit 1080p sizing and spoken-word emphasis."""
import re

PRESETS = {
    "source": dict(font="Arial", size=48, accent="FFFFFF", outline=2, shadow=1),
    "clean": dict(font="Arial", size=48, accent="FFFFFF", outline=2, shadow=1),
    "beast": dict(font="Arial Black", size=56, accent="56DEFF", outline=4, shadow=3, upper=True),
    "hormozi": dict(font="Arial Black", size=54, accent="64F2BE", outline=4, shadow=2, upper=True),
    "cyber": dict(font="Consolas", size=54, accent="F9E867", outline=3, shadow=4),
    "fire": dict(font="Arial Black", size=54, accent="6594FF", outline=4, shadow=3, upper=True),
    "cinematic": dict(font="Georgia", size=56, accent="B8DCEE", outline=2, shadow=2, italic=True),
    "rose": dict(font="Georgia", size=54, accent="D4A8F9", outline=3, shadow=2, italic=True),
    "box": dict(font="Arial Black", size=52, accent="17140B", outline=12, shadow=0, box=True),
}


def _timestamp(seconds):
    ticks = max(0, round(seconds * 100))
    sec, centi = divmod(ticks, 100)
    minutes, sec = divmod(sec, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02d}:{sec:02d}.{centi:02d}"


def _seconds(value):
    h, m, s = value.replace(',', '.').split(':')
    return int(h) * 3600 + int(m) * 60 + float(s)


def _escape(text):
    # Transcript content cannot introduce ASS drawing or override commands.
    return text.replace('\\', '＼').replace('{', '｛').replace('}', '｝').replace('\n', r'\N')


def generate_ass(srt, preset='beast', words=None, clip_start=0):
    style = PRESETS.get(preset, PRESETS['beast'])
    primary = '17140B' if style.get('box') else 'FFFFFF'
    border = '56DEFF' if style.get('box') else '14100C'
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,{style['font']},{style['size']},&H00{primary},&H00{style['accent']},&H00{border},&H90000000,-1,{ -1 if style.get('italic') else 0},0,0,100,100,0,0,{3 if style.get('box') else 1},{style['outline']},{style['shadow']},2,80,80,220,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    for block in re.split(r'\n\s*\n', srt.strip()):
        lines = block.splitlines()
        if len(lines) < 3 or ' --> ' not in lines[1]:
            continue
        begin, finish = map(_seconds, lines[1].split(' --> '))
        text = ' '.join(lines[2:])
        tokens = text.split()
        # Decorative layers use ASS vector paths, not a screenshot of text.
        # Their explicit pixel coordinates keep preview/export sizes predictable.
        width = min(920, max(220, len(text) * style['size'] * 0.57 + 64))
        height = 92 if width < 920 else 154
        x, y = (1080 - width) / 2, 1920 - 210 - height
        def decoration(drawing, color, outline_color, outline=1.5, alpha='28', dx=0, dy=0):
            tags = (f"{{\\an7\\pos({x+dx:.1f},{y+dy:.1f})\\p1\\bord{outline}\\shad0"
                    f"\\1c&H{color}&\\3c&H{outline_color}&\\1a&H{alpha}&\\3a&H30&}}")
            events.append(f"Dialogue: 0,{_timestamp(begin)},{_timestamp(finish)},Caption,,0,0,0,,{tags}{drawing}{{\\p0}}")
        if preset in ('cyber', 'rose'):
            radius = 8 if preset == 'cyber' else 18
            r, w, h = radius, width, height
            path = (f"m {r} 0 l {w-r} 0 b {w} 0 {w} 0 {w} {r} l {w} {h-r} "
                    f"b {w} {h} {w} {h} {w-r} {h} l {r} {h} b 0 {h} 0 {h} 0 {h-r} "
                    f"l 0 {r} b 0 0 0 0 {r} 0")
            if preset == 'rose':
                decoration(path, 'D4A8F9', 'D4A8F9', 0, 'A0', 6, 7)
            decoration(path, '281C0B' if preset == 'cyber' else '2F1739',
                       style['accent'], 2)
        elif preset == 'cinematic':
            decoration(f'm 0 0 l {width} 0', 'B8DCEE', 'B8DCEE', 1, '00')
            decoration(f'm 0 {height} l {width} {height}', 'B8DCEE', 'B8DCEE', 1, '00')
        timed = [w for w in (words or []) if float(w.get('end', 0)) - clip_start > begin
                 and float(w.get('start', 0)) - clip_start < finish]
        # Apply word emphasis only when actual words match this phrase exactly.
        matching = ([str(w.get('word', '')).strip().casefold() for w in timed] ==
                    [t.casefold() for t in tokens])
        emphasis = matching and preset not in ('source', 'clean', 'cinematic')
        boundaries = {begin, finish}
        if emphasis:
            for word in timed:
                boundaries.add(max(begin, min(finish, float(word['start']) - clip_start)))
                boundaries.add(max(begin, min(finish, float(word['end']) - clip_start)))
        times = sorted(boundaries)
        for a, b in zip(times, times[1:]):
            if round(b * 100) <= round(a * 100):
                continue
            spans = []
            for index, token in enumerate(tokens):
                token = _escape(token.upper() if style.get('upper') else token)
                active = emphasis and float(timed[index]['start']) - clip_start <= (a+b)/2 < float(timed[index]['end']) - clip_start
                if active:
                    tags = r'{\u1}' if style.get('box') else '{\\c&H' + style['accent'] + r'&\fscx106\fscy106}'
                    token = tags + token + r'{\rCaption}'
                spans.append(token)
            rendered = ' '.join(spans)
            # A short fade only on static cues; word events stay continuous.
            if not emphasis:
                rendered = r'{\fad(70,70)}' + rendered
            events.append(f"Dialogue: 1,{_timestamp(a)},{_timestamp(b)},Caption,,0,0,0,,{rendered}")
    return header + '\n'.join(events) + '\n'
