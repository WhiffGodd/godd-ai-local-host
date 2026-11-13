"""Draw the trusted diagram primitives used in generated videos."""

from functools import lru_cache
from math import acos, atan2, cos, hypot, pi, sin, sqrt
from pathlib import Path
from random import Random
import os
import textwrap

from PIL import Image, ImageDraw, ImageFont


WIDTH, HEIGHT, FPS = 720, 1280, 24


def _rgb(color):
    return tuple(bytes.fromhex(color))


def _mix(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


@lru_cache(maxsize=24)
def _font(size, bold=False):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    windows = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / ("arialbd.ttf" if bold else "arial.ttf")
    for candidate in (windows, name):
        try:
            return ImageFont.truetype(str(candidate), size)
        except OSError:
            pass
    return ImageFont.load_default(size=size)


def _lines(draw, text, font, width):
    lines = []
    line = ""
    for word in text.split():
        pieces = [word] if draw.textlength(word, font=font) <= width else textwrap.wrap(word, 10)
        for part in pieces:
            proposal = f"{line} {part}".strip()
            if line and draw.textlength(proposal, font=font) > width:
                lines.append(line)
                line = part
            else:
                line = proposal
    return lines + ([line] if line else [])


class ScenePainter:
    def __init__(self, template, scene, index, total):
        self.scene = scene
        self.opening = scene.get("opening", False)
        self.index = index
        self.total = total
        self.bg, self.ink, self.a, self.b = map(_rgb, (
            template.background, template.ink, template.accent, template.secondary,
        ))
        self.line = _mix(self.bg, self.ink, 0.20)
        self.panel = _mix(self.bg, self.ink, 0.07)
        self.diagram = getattr(self, "_" + scene["diagram"])
        self.labels = scene["labels"]
        self.full_frame = scene["diagram"] in ("bicycle", "bicycle_drive", "piston", "gears", "moon")
        if self.full_frame:
            self._prepare_full_frame()
            return
        self.base = Image.new("RGB", (WIDTH, HEIGHT), self.bg)
        draw = ImageDraw.Draw(self.base)
        for y in range(HEIGHT):
            glow = (1 - abs(y - 560) / HEIGHT) ** 5
            draw.line((0, y, WIDTH, y), fill=_mix(self.bg, self.b, glow * 0.14))
        if template.surface == "grid":
            grid = _mix(self.bg, self.ink, 0.11)
            for x in range(0, WIDTH, 32):
                draw.line((x, 0, x, HEIGHT), fill=grid)
            for y in range(0, HEIGHT, 32):
                draw.line((0, y, WIDTH, y), fill=grid)
        elif template.surface == "stars":
            rng = Random(24)
            for _ in range(125):
                x, y = rng.randrange(WIDTH), rng.randrange(HEIGHT)
                draw.circle((x, y), rng.choice((1, 1, 2)), fill=_mix(self.bg, self.ink, rng.uniform(.18, .48)))
        elif template.surface == "paper":
            for y in range(15, HEIGHT, 36):
                draw.line((0, y, WIDTH, y), fill=_mix(self.bg, self.ink, 0.09))
        elif template.surface == "cards":
            draw.rounded_rectangle((61, 377, 675, 887), radius=36, fill=_mix(self.bg, self.b, .28))
        radius = 36 if template.surface in ("glass", "cards") else 18
        if self.opening:
            draw.rounded_rectangle((43, 356, 663, 770), radius=radius, fill=self.panel, outline=self.line, width=2)
            for size in (66, 59, 52, 45):
                font = _font(size, True)
                lines = _lines(draw, scene["heading"], font, 570)
                if len(lines) <= 3:
                    break
            spacing = size + 9
            for row, line in enumerate(lines):
                draw.text((353, 965 + (row - (len(lines) - 1) / 2) * spacing), line,
                          anchor="mm", fill=self.ink, font=font)
            return
        draw.rounded_rectangle((43, 356, 663, 870), radius=radius, fill=self.panel, outline=self.line, width=2)
        draw.text((54, 84), template.name.upper(), fill=self.a, font=_font(19, True))
        draw.text((661, 84), f"{index + 1:02} / {total:02}", anchor="ra", fill=self.ink, font=_font(19))
        draw.line((54, 126, 661, 126), fill=self.line, width=2)
        for size in (62, 54, 46):
            heading_font = _font(size, True)
            heading = _lines(draw, scene["heading"], heading_font, 608)
            if len(heading) <= 3:
                break
        for row, line in enumerate(heading[:3]):
            draw.text((53, 154 + row * (size + 4)), line, fill=self.ink, font=heading_font)
        draw.rounded_rectangle((43, 927, 663, 1116), radius=24, fill=self.panel, outline=self.line, width=2)
        caption_font = _font(30, True)
        for row, line in enumerate(_lines(draw, scene["caption"], caption_font, 532)[:4]):
            draw.text((74, 957 + row * 36), line, fill=self.ink, font=caption_font)

    def frame(self, t):
        if self.full_frame:
            return self._full_frame(t)
        image = self.base.copy()
        draw = ImageDraw.Draw(image)
        self.diagram(draw, t)
        if self.opening:
            draw.rounded_rectangle((103, 1135, 603, 1141), radius=3, fill=self.line)
            draw.rounded_rectangle((103, 1135, 103 + 500 * t, 1141), radius=3, fill=self.a)
            return image
        rows = (len(self.labels) + 1) // 2
        for i, label in enumerate(self.labels):
            x, y = 74 + (i % 2) * 288, 807 + (i // 2) * 28 + (2 - rows) * 12
            fill = self.a if i % 2 == 0 else self.b
            draw.circle((x + 10, y + 10), 10, fill=fill)
            draw.text((x + 10, y + 10), str(i + 1), anchor="mm", fill=self.bg, font=_font(12, True))
            draw.text((x + 28, y), label, fill=self.ink, font=_font(18, True))
        for i in range(self.total):
            x = 54 + i * (608 / self.total)
            end = x + 608 / self.total - 7
            draw.rounded_rectangle((x, 1181, end, 1187), radius=3, fill=self.line)
            progress = min(1, max(0, self.index + t - i))
            if progress:
                draw.rounded_rectangle((x, 1181, x + (end - x) * progress, 1187), radius=3, fill=self.a)
        return image

    def _prepare_full_frame(self):
        self.base = Image.new("RGB", (WIDTH, HEIGHT), self.bg)
        draw = ImageDraw.Draw(self.base)
        for y in range(HEIGHT):
            light = max(0, 1 - abs(y - 550) / 750)
            draw.line((0, y, WIDTH, y), fill=_mix(self.bg, self.b, .22 + .36 * light))
        self.panel = _mix(self.bg, self.b, .35)
        self.line = _mix(self.bg, self.ink, .33)
        text = self.scene["heading"] if self.opening else self.scene["caption"]
        for size in (54, 48, 42) if self.opening else (42, 37, 32):
            self.full_font = _font(size, True)
            self.full_lines = _lines(draw, text, self.full_font, 560)
            if len(self.full_lines) <= 3:
                break

    def _full_frame(self, t):
        image = self.base.copy()
        # Existing mechanism coordinates sit between y=420 and y=740.
        # The viewport moves independently of the captions.
        stage = Image.new("RGBA", (WIDTH, 800))
        self.diagram(ImageDraw.Draw(stage), t)
        art = stage.crop((0, 345, WIDTH, 800))
        detail = self.scene["diagram"] == "bicycle_drive"
        zoom = (1.14 if detail else 1.07) + .13 * t
        art = art.resize((round(art.width * zoom), round(art.height * zoom)), Image.Resampling.BILINEAR)
        pan = round(15 * sin(t * pi)) if detail else 0
        image.paste(art, ((WIDTH - art.width) // 2 + pan, 560 - art.height // 2), art)
        draw = ImageDraw.Draw(image)
        spacing = self.full_font.size + 10
        for i, line in enumerate(self.full_lines):
            y = 987 + (i - (len(self.full_lines) - 1) / 2) * spacing
            draw.text((WIDTH // 2, y), line, anchor="mm", font=self.full_font, fill="white",
                      stroke_width=3, stroke_fill="#111827")
        return image

    def _badge(self, draw, x, y, index, size=29):
        fill = self.a if index % 2 == 0 else self.b
        draw.circle((x, y), size, fill=fill)
        ink = (17, 19, 24) if sum(fill) > 365 else (255, 255, 255)
        draw.text((x, y), str(index + 1), anchor="mm", fill=ink, font=_font(23, True))

    def _bicycle(self, draw, t):
        rear, front, crank = (184, 623), (523, 623), (325, 638)
        angle = t * 8 * pi
        frame = _mix(self.b, self.ink, .30)
        tire = (31, 34, 42) if self.full_frame else _mix(self.bg, self.ink, .78)
        metal = _mix(self.panel, self.ink, .78)
        draw.line((76, 737, 628, 737), fill=self.line, width=3)
        for x, y in (rear, front):
            draw.circle((x, y), 111, outline=tire, width=11)
            draw.circle((x, y), 108, outline=_mix(tire, metal, .35), width=2)
            draw.circle((x, y), 99, outline=metal, width=3)
            for i in range(16):
                spoke = angle * 36 / 20 + i * pi / 8
                draw.line((x, y, x + 97 * cos(spoke), y + 97 * sin(spoke)), fill=metal, width=2)
            draw.circle((x, y), 8, fill=metal)

        seat, head_top, head_bottom = (284, 473), (446, 470), (460, 517)
        for start, end in ((rear, seat), (seat, crank), (crank, rear), (seat, head_top),
                           (head_top, head_bottom), (head_bottom, crank), (head_bottom, front)):
            draw.line((*start, *end), fill=frame, width=14)
            draw.line((start[0], start[1] - 3, end[0], end[1] - 3), fill=_mix(frame, self.ink, .40), width=3)
        for joint in (rear, seat, crank, head_top, head_bottom, front):
            draw.circle(joint, 7, fill=frame)
        draw.line((284, 473, 275, 439), fill=metal, width=9)
        draw.rounded_rectangle((249, 426, 304, 440), radius=7, fill=tire)
        draw.line((446, 470, 436, 429, 480, 429), fill=metal, width=9, joint="curve")
        draw.arc((469, 420, 504, 472), 270, 435, fill=tire, width=10)
        self._bike_drive(draw, rear, crank, angle, 1)

    def _bicycle_drive(self, draw, t):
        rear, crank = (172, 591), (478, 614)
        draw.line((172, 591, 347, 424, 478, 614, 172, 591), fill=_mix(self.panel, self.b, .48),
                  width=18, joint="curve")
        angle = t * 8 * pi
        self._bike_drive(draw, rear, crank, angle, 1.8)
        pedal = (crank[0] + 100.8 * cos(angle), crank[1] + 100.8 * sin(angle))
        for i, (name, x, y, line_end) in enumerate((
            ("Pedal", 552, 483, pedal),
            ("Chain", 324, 476, (324, 534)),
            ("Rear cog", 160, 714, (172, 637)),
        )):
            color = self.a if i % 2 == 0 else self.b
            draw.line((x, y + (15 if i < 2 else -16), *line_end), fill=color, width=2)
            draw.text((x, y), name, anchor="mm", fill=self.ink, font=_font(21, True))

    def _bike_drive(self, draw, rear, crank, angle, scale):
        rear_radius, front_radius = 20 * scale, 36 * scale
        dx, dy = crank[0] - rear[0], crank[1] - rear[1]
        axis = atan2(dy, dx)
        tangent = acos((rear_radius - front_radius) / hypot(dx, dy))

        def point(center, radius, theta):
            return center[0] + radius * cos(theta), center[1] + radius * sin(theta)

        top, bottom = axis - tangent, axis + tangent
        chain = []
        for center, radius, start, end in ((crank, front_radius, top, bottom),
                                            (rear, rear_radius, bottom, top + 2 * pi)):
            chain.extend(point(center, radius, start + (end - start) * i / 24) for i in range(25))
        chain.append(chain[0])
        draw.line(chain, fill=self.ink, width=round(4 * scale), joint="curve")
        for center, radius, teeth, turn in (
            (rear, rear_radius, 10, angle * front_radius / rear_radius),
            (crank, front_radius, 18, angle),
        ):
            draw.circle(center, radius - 5 * scale, outline=self.b, width=round(3 * scale))
            for i in range(teeth):
                theta = turn + i * 2 * pi / teeth
                draw.line((*point(center, radius - 9 * scale, theta), *point(center, radius - 2 * scale, theta)),
                          fill=self.b, width=round(3 * scale))
            draw.circle(center, 5 * scale, fill=self.ink)

        # Both sprockets turn clockwise in this drive-side view, so the top run travels to the right.
        spacing = 12 * scale
        distance = 0
        next_link = (angle * front_radius) % spacing
        for a, b in zip(chain, chain[1:]):
            length = hypot(b[0] - a[0], b[1] - a[1])
            while next_link < distance + length:
                fraction = (next_link - distance) / length
                draw.circle((a[0] + (b[0] - a[0]) * fraction, a[1] + (b[1] - a[1]) * fraction),
                            2.6 * scale, fill=self.a)
                next_link += spacing
            distance += length

        for offset, color in ((pi, self.b), (0, self.a)):
            x, y = point(crank, 56 * scale, angle + offset)
            draw.line((*crank, x, y), fill=color, width=round(7 * scale))
            draw.rounded_rectangle((x - 15 * scale, y - 4 * scale, x + 15 * scale, y + 4 * scale),
                                   radius=4 * scale, fill=color)

    def _parts(self, draw, t):
        count = len(self.labels)
        draw.line((109, 610, 595, 610), fill=self.line, width=3)
        for i in range(count):
            x = 360 + (i - (count - 1) / 2) * (78 + 58 * sin(pi * min(t * 1.2, 1)))
            y = 587 + 31 * sin(t * 2 * pi + i)
            color = self.a if i % 2 == 0 else self.b
            draw.polygon([(x, y - 55), (x + 51, y - 26), (x + 51, y + 29), (x, y + 58),
                          (x - 51, y + 29), (x - 51, y - 26)], fill=_mix(self.panel, color, .29), outline=color, width=3)
            draw.line((x - 51, y - 26, x, y + 1, x + 51, y - 26), fill=color, width=2)
            draw.line((x, y + 1, x, y + 58), fill=color, width=2)
            self._badge(draw, x, y - 84, i, 18)

    def _cutaway(self, draw, t):
        for i in reversed(range(len(self.labels))):
            y = 494 + i * (48 + 13 * sin(t * pi))
            x = 356 + 16 * sin(t * 2 * pi + i)
            color = self.a if i % 2 == 0 else self.b
            draw.polygon([(x - 145, y), (x, y - 54), (x + 145, y), (x, y + 54)], fill=_mix(self.panel, color, .35),
                         outline=color, width=3)
            draw.line((x - 145, y, x - 145, y + 21, x, y + 77, x + 145, y + 21, x + 145, y), fill=color, width=3)
            self._badge(draw, 539, y + 11, i, 17)

    def _flow(self, draw, t):
        count = len(self.labels)
        positions = [136 + 442 * i / (count - 1) for i in range(count)]
        draw.line((positions[0], 590, positions[-1], 590), fill=self.line, width=5)
        marker = positions[0] + (positions[-1] - positions[0]) * t
        draw.line((positions[0], 590, marker, 590), fill=self.a, width=5)
        for i, x in enumerate(positions):
            self._badge(draw, x, 590, i, 25)
        draw.circle((marker, 654), 8, fill=self.ink)
        draw.line((marker, 626, marker, 654), fill=self.line, width=2)

    def _sequence(self, draw, t):
        for i in range(len(self.labels)):
            x, y = 157 + i * 65, 450 + i * 72
            progress = min(1, max(0, t * 2.2 - i * .22))
            draw.rounded_rectangle((x, y, x + 240, y + 54), radius=11, outline=self.line, width=2)
            if progress:
                draw.rounded_rectangle((x, y, x + 240 * progress, y + 54), radius=11,
                                       fill=_mix(self.panel, self.a if i % 2 == 0 else self.b, .38))
            self._badge(draw, x + 30, y + 27, i, 16)

    def _cycle(self, draw, t):
        draw.ellipse((206, 446, 508, 748), outline=self.line, width=5)
        angle = 2 * pi * t - pi / 2
        draw.arc((206, 446, 508, 748), -90, 360 * t - 90, fill=self.a, width=5)
        for i in range(len(self.labels)):
            step = 2 * pi * i / len(self.labels) - pi / 2
            self._badge(draw, 357 + 151 * cos(step), 597 + 151 * sin(step), i, 23)
        draw.circle((357 + 122 * cos(angle), 597 + 122 * sin(angle)), 10, fill=self.ink)

    def _network(self, draw, t):
        draw.circle((353, 591), 44, fill=_mix(self.panel, self.b, .42), outline=self.b, width=3)
        for i in range(len(self.labels)):
            angle = i * 2 * pi / len(self.labels) + pi / 4
            x, y = 353 + 183 * cos(angle), 591 + 160 * sin(angle)
            draw.line((353, 591, x, y), fill=self.line, width=4)
            progress = (t * 1.5 + i / len(self.labels)) % 1
            draw.circle((353 + (x - 353) * progress, 591 + (y - 591) * progress), 7, fill=self.a)
            self._badge(draw, x, y, i, 23)
        draw.circle((353, 591), 24, fill=self.b)

    def _orbit(self, draw, t):
        draw.circle((356, 594), 34, fill=self.b)
        for i in range(len(self.labels)):
            radius = 70 + 36 * i
            angle = (t * (1.25 - i * .16) + i * .19) * 2 * pi
            draw.ellipse((356 - radius, 594 - .68 * radius, 356 + radius, 594 + .68 * radius),
                         outline=self.line, width=2)
            self._badge(draw, 356 + radius * cos(angle), 594 + .68 * radius * sin(angle), i, 17)

    def _moon(self, draw, t):
        earth_x, earth_y, orbit = 410, 585, 118
        draw.ellipse((earth_x - orbit, earth_y - orbit, earth_x + orbit, earth_y + orbit),
                     outline=self.line, width=3)
        sun = (252, 194, 105)
        for y in (515, 585, 655):
            draw.line((179, y, 280, y), fill=_mix(self.panel, sun, .64), width=3)
            draw.polygon(((280, y), (267, y - 6), (267, y + 6)), fill=sun)
        draw.circle((135, 585), 36, fill=sun)
        draw.circle((earth_x, earth_y), 28, fill=self.b)
        angle = 2 * pi * t + pi
        mx, my = earth_x + orbit * cos(angle), earth_y + orbit * sin(angle)
        bounds = (mx - 16, my - 16, mx + 16, my + 16)
        draw.ellipse(bounds, fill=self.line, outline=self.ink, width=1)
        draw.pieslice(bounds, 90, 270, fill=self.ink)
        self._badge(draw, 135, 650, 0, 16)
        self._badge(draw, earth_x, earth_y + 56, 1, 16)
        self._badge(draw, mx, my - 35, 2, 16)

    def _gears(self, draw, t):
        for i, (x, radius, teeth) in enumerate(((254, 97, 16), (435, 79, 13))):
            turn = 2 * pi * t * (1 if i == 0 else -16 / 13) + i * pi / teeth
            points = []
            for tooth in range(teeth):
                for offset, size in ((0, .88), (.19, 1), (.53, 1), (.72, .88)):
                    angle = turn + 2 * pi * (tooth + offset) / teeth
                    points.append((x + radius * size * cos(angle), 596 + radius * size * sin(angle)))
            color = self.a if i == 0 else self.b
            draw.polygon(points, fill=_mix(self.panel, color, .5), outline=color, width=3)
            draw.circle((x, 596), radius * .44, outline=color, width=3)
            self._badge(draw, x, 596, i, 22)

    def _piston(self, draw, t):
        x, y = 358, 673
        radius = 49
        angle = 2 * pi * t
        pin_x, pin_y = x + radius * sin(angle), y - radius * cos(angle)
        slider_y = pin_y - sqrt(136 ** 2 - (pin_x - x) ** 2)
        draw.rounded_rectangle((276, 422, 440, 596), radius=18, outline=self.line, width=4)
        draw.circle((x, y), 69, outline=self.b, width=4)
        draw.line((x, y, pin_x, pin_y), fill=self.b, width=13)
        draw.line((pin_x, pin_y, x, slider_y), fill=self.ink, width=12)
        draw.rounded_rectangle((288, slider_y - 19, 428, slider_y + 18), radius=9, fill=self.a)
        self._badge(draw, x, slider_y, 0, 17)
        self._badge(draw, pin_x, pin_y, 1, 15)

    def _wave(self, draw, t):
        draw.line((93, 590, 620, 590), fill=self.line, width=2)
        for i, color in enumerate((self.a, self.b)):
            points = [(x, 590 + (89 - 31 * i) * sin((x - 94) / 62 - t * 2 * pi + i * 1.25))
                      for x in range(94, 620, 4)]
            draw.line(points, fill=color, width=4)
            draw.circle(points[int(t * (len(points) - 1))], 9, fill=color)

    def _motion(self, draw, t):
        for i in range(len(self.labels)):
            y = 465 + i * 84
            draw.rounded_rectangle((105, y - 5, 605, y + 5), radius=5, fill=self.line)
            progress = (.5 - .5 * cos((t + i * .14) * 2 * pi))
            self._badge(draw, 123 + 466 * progress, y, i, 22)

    def _bars(self, draw, t):
        # Relative shapes are illustrative. Never infer quantities from model text.
        count = len(self.labels)
        draw.line((109, 727, 601, 727), fill=self.line, width=2)
        for i in range(count):
            x = 143 + i * 440 / count
            h = 35 + 151 * min(1, t * 2.3) * (.52 + i * .13)
            color = self.a if i % 2 == 0 else self.b
            draw.rounded_rectangle((x, 721 - h, x + 65, 721), radius=10, fill=_mix(self.panel, color, .75))
            self._badge(draw, x + 32, 690 - h, i, 17)

    def _compare(self, draw, t):
        for i in range(len(self.labels)):
            x, y = 108 + (i % 2) * 259, 458 + (i // 2) * 147
            color = self.a if i % 2 == 0 else self.b
            mix = .11 + .23 * sin(pi * min(t + i * .12, 1))
            draw.rounded_rectangle((x, y, x + 232, y + 119), radius=18, outline=color, width=2,
                                   fill=_mix(self.panel, color, mix))
            self._badge(draw, x + 116, y + 60, i, 24)
