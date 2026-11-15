# SPDX-License-Identifier: MIT
"""Render lit 3D explainer shots to the same frames used by the studio export."""

from functools import lru_cache
from math import asin, cos, pi, sin, sqrt, tan, tau
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from cinematic_geometry import CHROME, ROPE, STEEL, SUBJECTS, mesh, scale, spin, translate, tube
from explainer_templates import VIEWS


WIDTH, HEIGHT, FPS = 720, 1280, 24

_VERTEX = """
#version 330
in vec3 point;
in vec3 normal;
uniform mat4 model, view, light;
out vec3 world, local, n;
out vec4 shadow;
void main() {
    vec4 p = model * vec4(point, 1.);
    world = p.xyz;
    local = point;
    n = transpose(inverse(mat3(model))) * normal;
    shadow = light * p;
    gl_Position = view * p;
}
"""

_FRAGMENT = """
#version 330
in vec3 world, local, n;
in vec4 shadow;
uniform vec3 eye, source;
uniform vec4 material;
uniform float highlight;
uniform float highlight_edge;
uniform sampler2D shadow_map;
out vec4 pixel;
vec4 surface_pixel(vec3 color) {
    float selected = highlight * step(highlight_edge, length(local.xy));
    float brightness = .64 + .36 * max(color.r, max(color.g,color.b));
    return vec4(mix(color, vec3(.12,.91,.98)*brightness, .62*selected), selected);
}
float hash(vec3 p) { return fract(sin(dot(p, vec3(127.1, 311.7, 74.7))) * 43758.5453); }
float noise(vec3 p) {
    vec3 i = floor(p), f = fract(p);
    f = f*f*(3.-2.*f);
    return mix(mix(mix(hash(i),hash(i+vec3(1,0,0)),f.x),
                   mix(hash(i+vec3(0,1,0)),hash(i+vec3(1,1,0)),f.x),f.y),
               mix(mix(hash(i+vec3(0,0,1)),hash(i+vec3(1,0,1)),f.x),
                   mix(hash(i+vec3(0,1,1)),hash(i+vec3(1,1,1)),f.x),f.y),f.z);
}
float occlusion(float bias) {
    vec3 p = shadow.xyz / shadow.w * .5 + .5;
    if (p.z > 1. || any(lessThan(p.xy,vec2(0))) || any(greaterThan(p.xy,vec2(1)))) return 1.;
    float visibility = 0.;
    for (int x=-2; x<=2; ++x) for (int y=-2; y<=2; ++y)
        visibility += step(p.z-bias, texture(shadow_map,p.xy + vec2(x,y)*.00135).r);
    return visibility / 25.;
}
void main() {
    vec3 N=normalize(n), V=normalize(eye-world), L=normalize(source-world);
    vec3 base=pow(material.rgb,vec3(2.2));
    float metal=material.a;
    float detail=noise(local*320.);
    if (metal > 1.5 && metal < 3.5) {
        vec3 p=normalize(local);
        float land=noise(p*3.0)*.58 + noise(p*8.5)*.29 + noise(p*25.)*.13;
        if (metal < 2.5) {
            base=mix(base,mix(vec3(.065,.13,.021),vec3(.38,.24,.095),smoothstep(.53,.69,land)),smoothstep(.49,.52,land));
            base=mix(base,vec3(.74,.84,.88),smoothstep(.84,.99,abs(p.y)+.045*noise(p*10.)));
            float cloud=noise(p*12.+vec3(7,3,8))*noise(p*4.)+.18*noise(p*51.);
            base=mix(base,vec3(.82,.92,1.),smoothstep(.30,.55,cloud)*.78);
        } else {
            base *= .45 + .90 * land + .22*noise(p*52.);
        }
        float day = max(dot(N,normalize(source)),0.);
        vec3 color = base*(.035+day*2.5) + pow(1.-max(dot(V,N),0.),4.) * vec3(.035,.105,.24) * day;
        pixel=surface_pixel(pow(color/(.72+color),vec3(.4545)));
        return;
    }
    float nl=max(dot(N,L),0.);
    float visible=occlusion(mix(.0028,.0007,nl));
    vec3 H=normalize(L+V);
    float spec=pow(max(dot(N,H),0.),mix(18.,53.,metal));
    float fresnel=pow(1.-max(dot(N,V),0.),4.);
    vec3 fill=normalize(vec3(4.,2.,-4.));
    vec3 R=reflect(-V,N);
    float softbox=pow(max(dot(R,normalize(vec3(-.3,.78,.62))),0.),7.);
    float strip=pow(max(dot(R,normalize(vec3(.86,.48,-.27))),0.),32.);
    vec3 reflection=mix(vec3(.19),base*1.3+vec3(.12),metal);
    float lathe=sin(length(local.xy)*622.+detail*1.6);
    float brushed=mix(1.,.91+.085*lathe+.087*detail,clamp(metal,0.,1.));
    vec3 color=base*(.13 + (detail-.5)*.08 + 1.55*nl*visible)*brushed;
    color+=reflection*(spec*visible*2.25 + metal*(softbox*1.4+strip*1.45))*brushed;
    color+=vec3(.17,.49,.92)*max(dot(N,fill),0.)*(.07+fresnel*.30);
    if (material.a == 4.) {
        float pool=exp(-dot(world.xz,world.xz)*.093);
        color=(vec3(.002,.004,.009)+vec3(.018,.035,.056)*pool*(.30+.70*visible))*(.9+detail*.20);
    }
    pixel=surface_pixel(pow(color/(.81+color),vec3(.4545)));
}
"""

_DEPTH_VERTEX = """
#version 330
in vec3 point;
uniform mat4 view, model;
void main() { gl_Position = view * model * vec4(point,1.); }
"""

_BACKGROUND = """
#version 330
out vec4 pixel;
uniform vec2 size;
uniform int space;
void main() {
    vec2 uv=gl_FragCoord.xy/size, p=uv-vec2(.45,.57);
    float glow=exp(-8.*(p.x*p.x+p.y*p.y));
    vec3 color=mix(vec3(.026,.038,.058),vec3(.145,.195,.235),glow);
    if (space==1) {
        vec2 cell=floor(gl_FragCoord.xy/4.);
        float star=fract(sin(dot(cell,vec2(12.9898,78.233)))*43758.5453);
        color*=.46;
        color+=step(.990,star)*(.27+.4*star)*exp(-22.*pow(length(fract(gl_FragCoord.xy/4.)-.5),2.));
    }
    pixel=vec4(color,0.);
}
"""


class RendererUnavailable(RuntimeError):
    """The host failed to start the headless 3D renderer."""


def _unit(vector):
    return vector / np.linalg.norm(vector)


def _look_at(eye, target):
    z = _unit(np.array(eye) - target)
    x = _unit(np.cross((0.,1.,0.),z))
    y = np.cross(z,x)
    matrix = np.eye(4)
    matrix[:3,:3] = (x,y,z)
    matrix[:3,3] = -matrix[:3,:3] @ eye
    return matrix


def _perspective(aspect, angle):
    f = 1 / tan(angle / 2)
    near, far = .055, 90.
    return np.array([[f/aspect,0,0,0],[0,f,0,0],
                     [0,0,(far+near)/(near-far),2*far*near/(near-far)],[0,0,-1,0]])


def _matrix(uniform, value):
    uniform.write(np.asarray(value.T,dtype="f4").tobytes())


@lru_cache(maxsize=12)
def _font(size):
    for name in ("arialbd.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def caption_layer(text, size, opening=False):
    width, height = size
    font_size = round(width * (.079 if opening else .053))
    layer = Image.new("RGBA", (width, round(height * .19)))
    draw = ImageDraw.Draw(layer)
    while True:
        font = _font(font_size)
        lines = [""]
        for word in text.split():
            line = f"{lines[-1]} {word}".strip()
            if lines[-1] and draw.textlength(line, font=font) > width * .81:
                lines.append(word)
            else:
                lines[-1] = line
        if len(lines) * font.size * 1.17 <= layer.height - 12 or font_size <= round(width * .038):
            break
        font_size -= 2
    for i, line in enumerate(lines):
        y = round(layer.height * .48 + (i - (len(lines)-1)/2) * font.size * 1.17)
        draw.text((width/2,y+2),line,font=font,anchor="mm",fill=(0,0,0,215),stroke_width=5)
        draw.text((width/2,y),line,font=font,anchor="mm",fill="#fff3d7" if opening else "white",
                  stroke_width=round(width*.0028),stroke_fill="#101217")
    return layer, (0, round(height * .64))


def _draw_callout(frame, mask, label):
    # The alpha channel marks only visible pixels of the selected 3D meshes.
    visible = np.asarray(mask)[::3, ::3] >= 192
    y, x = np.nonzero(visible)
    if not len(x):
        return
    # Anchor inside the visible part, including thin rings and clipped geometry.
    center_x = (x.min() + x.max()) / 2
    upper_y = y.min() + .27 * (y.max() - y.min())
    point = np.argmin((x - center_x)**2 + (y - upper_y)**2)
    anchor = (int(x[point])*3, int(y[point])*3)

    width, height = frame.size
    draw = ImageDraw.Draw(frame)
    font = _font(round(width * .051))
    left, top = round(width * .072), round(height * .135)
    pad = round(width * .021)
    right = left + round(draw.textlength(label, font=font)) + pad * 2
    bottom = top + font.size + pad
    wire = max(2, round(width * .0044))
    accent, shadow = "#69efff", "#071319"
    if anchor[1] < top:
        edge = (left+pad, top)
    else:
        edge = (left+pad, bottom)
    bend = (edge[0], round((edge[1] + anchor[1]) / 2))
    draw.line((edge, bend, anchor), fill=shadow, width=wire+3, joint="curve")
    draw.line((edge, bend, anchor), fill=accent, width=wire, joint="curve")
    x, y = anchor
    dot = wire * 2
    draw.ellipse((x-dot,y-dot,x+dot,y+dot), fill=accent, outline=shadow, width=wire)
    draw.rounded_rectangle((left,top,right,bottom),radius=pad,fill=shadow,outline=accent,width=wire)
    draw.text((left+pad,(top+bottom)//2),label,font=font,anchor="lm",fill="#e7fbff")


def _between_pivots(x, y, a):
    return translate(x,y,0) @ spin(a) @ translate(-x,-y,0)


def _chain(offset):
    rear, front = (-1.48,.03),(-.11,-.13)
    r, R = .192,.375
    vector = np.array(front) - rear
    distance = np.linalg.norm(vector)
    x = vector / distance
    y = np.array((-x[1],x[0]))
    lean = asin((R-r)/distance)
    top, bottom = -x*sin(lean)+y*cos(lean), -x*sin(lean)-y*cos(lean)
    top_a = np.arctan2(top[1],top[0])
    front_sweep, rear_sweep = pi+2*lean, pi-2*lean
    line = (distance**2-(R-r)**2)**.5
    length = 2*line+R*front_sweep+r*rear_sweep
    count = round(length/.057)
    for i in range(count):
        d = (i*length/count + offset) % length
        if d < line:
            p = rear + r*top + d/line*(vector+(R-r)*top)
            a = top_a-pi/2
        elif d < line+R*front_sweep:
            a = top_a-(d-line)/R
            p = front+R*np.array((cos(a),sin(a)))
            a -= pi/2
        elif d < 2*line+R*front_sweep:
            p = front+R*bottom-(d-line-R*front_sweep)/line*(vector+(R-r)*bottom)
            a = top_a-front_sweep-pi/2
        else:
            a = top_a-front_sweep-(d-2*line-R*front_sweep)/r
            p = rear+r*np.array((cos(a),sin(a)))
            a -= pi/2
        model = translate(*p,.26) @ spin(a)
        yield ("chain-link", CHROME if i%2 else STEEL, model @ scale(.061,.031,.071 if i%2 else .053), "chain")


class CinematicRenderer:
    def __init__(self, size=(WIDTH, HEIGHT)):
        try:
            import moderngl as gl
            backend = {"backend": "egl"} if sys.platform.startswith("linux") else {}
            self.ctx = gl.create_context(standalone=True, **backend)
        except (ImportError, OSError, RuntimeError) as error:
            raise RendererUnavailable("The 3D renderer could not start. Install the project requirements and use an OpenGL 3.3 driver or Mesa EGL.") from error
        self.size = size
        self.depth_flag = gl.DEPTH_TEST
        self.ctx.gc_mode = "context_gc"
        self.framebuffer = self.ctx.simple_framebuffer(size, 4)
        self.multisample = self.ctx.simple_framebuffer(size, 4, samples=min(4,self.ctx.max_samples))
        self.depth = self.ctx.depth_texture((1024,1024))
        self.depth.compare_func = ""
        self.shadow = self.ctx.framebuffer(depth_attachment=self.depth)
        self.shader = self.ctx.program(vertex_shader=_VERTEX, fragment_shader=_FRAGMENT)
        self.depth_shader = self.ctx.program(vertex_shader=_DEPTH_VERTEX, fragment_shader="#version 330\nvoid main() {}")
        self.background = self.ctx.program(vertex_shader="""#version 330
            void main() {
                vec2 p=vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
                gl_Position=vec4(p*2.-1.,0.,1.);
            }""", fragment_shader=_BACKGROUND)
        self.background["size"].value = size
        self.backdrop = self.ctx.vertex_array(self.background, [])
        self.meshes = {}

    def close(self):
        for buffer, color, depth in self.meshes.values():
            color.release()
            depth.release()
            buffer.release()
        for resource in (self.backdrop,self.background,self.shader,self.depth_shader,self.shadow,
                         self.depth,self.multisample,self.framebuffer):
            resource.release()
        self.ctx.gc()
        self.ctx.release()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _arrays(self, name):
        if name not in self.meshes:
            buffer = self.ctx.buffer(np.asarray(mesh(name),dtype="f4").tobytes())
            color = self.ctx.vertex_array(self.shader, [(buffer,"3f 3f","point","normal")])
            depth = self.ctx.vertex_array(self.depth_shader, [(buffer,"3f 12x","point")])
            self.meshes[name] = buffer, color, depth
        return self.meshes[name]

    def frame(self, shot, elapsed, part=None):
        objects, eye, focus = shot.at(elapsed, part)
        space = shot.subject == "moon"
        light = (-3.9,4.8,5.4) if not space else (-5.,1.7,2.0)
        light_view = _perspective(1.,1.05) @ _look_at(light,(0,0,0))
        self.ctx.enable(self.depth_flag)
        self.shadow.use()
        self.shadow.clear(depth=1.)
        if not space:
            _matrix(self.depth_shader["view"], light_view)
            for name, _, model, _ in objects:
                _matrix(self.depth_shader["model"], model)
                self._arrays(name)[2].render()
        self.multisample.use()
        self.multisample.clear()
        self.ctx.disable(self.depth_flag)
        self.background["space"].value = int(space)
        self.backdrop.render(vertices=3)
        self.ctx.enable(self.depth_flag)
        self.depth.use(0)
        self.shader["eye"].value = eye
        self.shader["source"].value = light
        _matrix(self.shader["light"], light_view)
        _matrix(self.shader["view"], _perspective(self.size[0]/self.size[1], .78) @ _look_at(eye,focus))
        if not space:
            floor = ("box", (.17,.22,.26,4.), translate(0,getattr(shot,"floor",-1.25),0) @ scale(60,.10,60), "")
            objects.append(floor)
        groups = part.groups if part else ()
        edge = part.mesh_edge if part else 0.
        self.shader["highlight_edge"].value = edge
        for name, material, model, group in objects:
            self.shader["material"].value = material
            self.shader["highlight"].value = float(group in groups and (not edge or name.startswith("gear")))
            _matrix(self.shader["model"], model)
            self._arrays(name)[1].render()
        self.ctx.copy_framebuffer(self.framebuffer,self.multisample)
        mode = "RGBA" if part else "RGB"
        pixels = self.framebuffer.read(components=len(mode))
        frame = Image.frombytes(mode,self.size,pixels,"raw",mode,0,-1)
        if part:
            mask = frame.getchannel("A")
            frame = frame.convert("RGB")
            _draw_callout(frame, mask, part.label)
        if shot.caption:
            layer, xy = shot.caption
            frame.paste(layer,xy,layer)
        return frame


class Shot:
    def __init__(self, subject, view, size, caption="", opening=False, offset=0, action_start=None):
        self.subject = subject
        self.geometry = SUBJECTS[subject]()
        self.view = view
        self.offset = offset
        self.action_start = offset if action_start is None else action_start
        self.caption = caption_layer(caption,size,opening) if caption else None

    def at(self, t, part=None):
        time = t + self.offset
        angle = time * 1.44
        track = sin(t*.57)
        objects = []
        if self.subject == "bicycle":
            drive = self.action_start * 1.44 if self.view == "coasting" else angle
            transforms = {"crank": _between_pivots(-.11,-.13,-drive), "cog": _between_pivots(-1.48,.03,-drive*.375/.192),
                          "rear-wheel": _between_pivots(-1.48,.03,-angle*.375/.192),
                          "front-wheel": _between_pivots(1.48,.03,-angle*.375/.192)}
            transforms.update(chainring=transforms["crank"], pedal=transforms["crank"],
                              **{"rear-hub": transforms["rear-wheel"]})
            objects.extend(_chain(drive*.375))
            shots = [((.08,.15,0),(3.85+track*.70,2.41,8.6-track*.35)),
                     ((-.11,-.14,.24),(1.12+.35*track,.85,2.55-track*.28)),
                     ((-1.13,-.05,.22),(-2.51+.37*track,.84,2.69-track*.30)),
                     ((-.73,-.07,.12),(-.74+track*.8,1.25,4.23-track*.23)),
                     ((-.98,.10,.05),(-2.17+.4*track,1.33,4.46-track*.3))]
        elif self.subject == "gears":
            transforms = {"drive":_between_pivots(-.90,.06,-angle*.53),
                          "idler":_between_pivots(.24,.06,angle*1.06+pi/12),
                          "output":_between_pivots(1.15,.06,-angle*.795)}
            shots = [((.03,-.22,0),(1.3+track,2.4,6.4-track*.48)),
                     ((-.22,.0,.05),(-1.4+track,.85,2.7-track*.24)),
                     ((.59,.05,.05),(1.55-track*.6,1.4,3.1)),
                     ((0,-.08,0),(-1.5+track,-.61,5.45-track*.3))]
        elif self.subject == "pulley":
            shift = .38*sin(time*1.25)
            transforms = {"wheel":_between_pivots(0,.9,-shift/.44),
                          "load":translate(0,shift,0), "handle":translate(0,-shift,0)}
            objects.extend(("cylinder",ROPE,tube((x,.9,0),(x,y,0),.023),"rope")
                           for x,y in ((-.44,-.47+shift),(.44,-.55-shift)))
            shots = [((0,.26,0),(1.18+track*.6,1.5,4.8-track*.36)),
                     ((0,.89,0),(-1.32+track*.52,1.64,2.58)),
                     ((-.21,-.43,.04),(.79+track*.55,.19,2.62)),
                     ((0,.33,0),(-1.87+track*.63,1.2,4.38-track*.19))]
        elif self.subject == "moon":
            phase = .22 + time*.16
            moon = (1.79*cos(phase),.22*sin(phase),1.79*sin(phase))
            rotation = np.array([[cos(time*.13),0,sin(time*.13),0],[0,1,0,0],
                                 [-sin(time*.13),0,cos(time*.13),0],[0,0,0,1]])
            transforms = {"earth":rotation,"moon":translate(*moon)}
            shots = [((0,-.14,0),(-2.12+track*.51,2.22,5.56)),
                     (moon,(moon[0]+1.39+track*.35,moon[1]+.47,moon[2]+2.47)),
                     ((0,-.13,0),(1.48-track*.52,1.28,5.4)),
                     ((0,-.13,0),(-.89+track*.56,2.37,5.72))]
        elif self.subject == "piston":
            crank_pin = (.33*cos(angle), -.52+.33*sin(angle), 0.)
            piston_pin = (0.,crank_pin[1]+sqrt(1.10**2-crank_pin[0]**2),0.)
            transforms = {"crank":_between_pivots(0,-.52,angle), "piston":translate(*piston_pin)}
            rod = tube(crank_pin,piston_pin,.089)
            objects.append(("cylinder",STEEL,rod,"rod"))
            objects.extend(("cylinder",CHROME,translate(*point)@scale(.13,.13,.33),"rod")
                           for point in (crank_pin,piston_pin))
            shots = [((0,.24,0),(1.45+.47*track,1.07,5.41-track*.31)),
                     ((0,.78,0),(.55+.46*track,1.63,2.79-track*.19)),
                     ((0,.36,0),(1.31+.40*track,.74,3.24-track*.18)),
                     ((0,-.43,0),(-1.48+.41*track,.24,2.85-track*.16))]
        elif self.subject == "turbine":
            rotor = _between_pivots(0,1.04,-angle*.69)
            transforms = dict.fromkeys(("shaft", "hub", "blades"), rotor)
            shots = [((0,.62,0),(1.45+track*.56,2.11,6.32-track*.33)),
                     ((0,1.06,.35),(1.21+track*.34,1.74,4.84-track*.24)),
                     ((0,1.03,.36),(1.62+track*.32,1.58,2.53-track*.17)),
                     ((0,.73,-.18),(-2.12+track*.41,2.01,-3.84-track*.27))]
        elif self.subject == "hydraulics":
            press = (1-cos(angle*.58))/2
            fluid = (.08,.55,.71,.31)
            transforms = {}
            # A tracer sweeps toward the lifting piston during the press and reverses on return.
            for index in range(7):
                progress = (index/7 + press*.76) % 1.
                x = -.68 + progress*1.21
                tracer = translate(x,-.714,.203) @ scale(.034,.018,.025)
                objects.append(("sphere",(.18,.85,.96,.08),tracer,"fluid"))
            for group,x,radius,y in (("input",-.78,.233,.31-.64*press),
                                     ("output",.64,.483,-.36+.64*(.233/.483)**2*press)):
                transforms[group] = translate(0,y,0)
                objects.append(("cylinder",fluid,tube((x,-.76,0),(x,y-.027,0),radius),"fluid"))
                objects.append(("cylinder",CHROME,tube((x,y-.026,0),(x,y+.031,0),radius),group))
            transforms["load"] = transforms["output"]
            shots = [((-.05,.06,0),(1.01+track*.61,1.54,5.35-track*.33)),
                     ((-.77,-.29,0),(-1.57+track*.39,1.21,2.71-track*.20)),
                     ((.62,-.10,0),(1.83+track*.38,1.37,3.01-track*.20)),
                     ((-.10,-.64,.07),(-.39+track*.35,.48,3.26-track*.21))]
        elif self.subject == "bearing":
            transforms = {"inner":_between_pivots(0,.16,angle), "cage":_between_pivots(0,.16,angle*.36)}
            transforms["balls"] = transforms["cage"]
            shots = [((0,.18,0),(1.80+track*.51,1.52,4.66-track*.29)),
                     ((0,.19,.14),(-1.42+track*.39,1.11,3.10-track*.21)),
                     ((.50,.51,.15),(1.68+track*.32,1.45,2.33-track*.20)),
                     ((0,.33,0),(-1.94+track*.43,1.21,3.75-track*.23))]
        elif self.subject == "disc_brake":
            braking = self.view in ("caliper-and-pads", "braking")
            brake_time = time - self.action_start
            clamp_time, stop_time = .8, 2.6
            slowing = min(max(brake_time - clamp_time, 0.), stop_time)
            free_spin = min(brake_time, clamp_time)
            rotor_angle = (3.6 * (self.action_start + free_spin + slowing * (1 - slowing / (2 * stop_time)))
                           if braking else 3.6 * time)
            squeeze = min(brake_time / clamp_time, 1.) * .064 if braking else 0.
            transforms = {"rotor":_between_pivots(-.1,.28,-rotor_angle),
                          "pad-1":translate(0,0,squeeze),"pad1":translate(0,0,-squeeze)}
            shots = [((.12,.34,0),(1.84+track*.53,1.48,5.39-track*.36)),
                     ((-.26,.41,.02),(-1.43+track*.42,1.03,3.27-track*.21)),
                     ((.88,.61,.01),(2.41+track*.36,1.36,2.68-track*.20)),
                     ((.48,.53,0),(.83+track*.32,1.89,3.40-track*.25))]
        elif self.subject == "freewheel":
            hub_angle = -.91*time
            driver_angle = -.91*self.action_start if self.view == "coasting" else hub_angle
            reveal = min(t/1.4,1.)
            reveal = reveal*reveal*(3-2*reveal)
            cover = translate(1.6*reveal, 3.1*reveal, .65*reveal) if self.view == "wide" and self.offset < .05 else translate(0, 5, 0)
            transforms = {"hub":spin(hub_angle),"ratchet":spin(hub_angle),"sprocket":spin(driver_angle),
                          "driver":spin(driver_angle),"cover":cover}
            slip = (abs(hub_angle-driver_angle)*28/tau) % 1.
            for i in range(3):
                a = i*tau/3
                kick = -.32*sin(pi*slip)**2 if self.view == "coasting" else 0.
                transforms[f"pawl{i}"] = spin(driver_angle) @ _between_pivots(.665*cos(a),.665*sin(a),kick)
            shots = [((0,.05,0),(1.01+track*.38,1.20,4.82-track*.28)),
                     ((0,.07,.12),(-1.14+track*.51,1.13,4.18-track*.16)),
                     ((.08,.01,.15),(.61+track*.35,.66,3.82-track*.16)),
                     ((.07,.01,.18),(.41+track*.38,.55,3.71-track*.17))]
        for name, material, model, group in self.geometry.parts:
            if self.subject == "freewheel" and group == "cover" and (self.view != "wide" or self.offset >= .05 or t >= 1.65):
                continue
            transform = transforms.get(group)
            objects.append((name, material, model if transform is None else transform @ model, group))
        view = self.view
        if part and view not in ("wide", "coasting", "braking", "engagement", "cutaway"):
            view = part.view
        focus, eye = shots[VIEWS[self.subject].index(view)]
        return objects, eye, np.asarray(focus)
