# SPDX-License-Identifier: MIT
"""Render lit 3D explainer shots to the same frames used by the studio export."""

from functools import lru_cache
from math import asin, ceil, cos, pi, sin, sqrt, tan, tau
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from cinematic_geometry import CHROME, ROPE, STEEL, SUBJECTS, TOASTER_SLOTS, mesh, scale, spin, translate, tube
from explainer_templates import VIEWS


WIDTH, HEIGHT, FPS = 720, 1280, 30

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
uniform bool machined;
uniform bool rolling_mark;
uniform sampler2D shadow_map;
out vec4 pixel;
vec4 surface_pixel(vec3 color) {
    float selected = highlight * step(highlight_edge, length(local.xy));
    float brightness = .64 + .36 * max(color.r, max(color.g,color.b));
    return vec4(mix(color, vec3(.12,.91,.98)*brightness, .25*selected), selected);
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
vec3 finish_normal(vec3 normal, float height) {
    vec3 dx = dFdx(world), dy = dFdy(world);
    vec3 x = cross(dy, normal), y = cross(normal, dx);
    float determinant = dot(dx, x);
    return normalize(max(abs(determinant),1.e-9)*normal
                     - sign(determinant)*(dFdx(height)*x+dFdy(height)*y));
}
vec3 display_color(vec3 c) {
    c *= 1.28;
    vec3 mapped = clamp((c*(2.51*c+.03))/(c*(2.43*c+.59)+.14),0.,1.);
    return pow(mapped,vec3(1./2.2));
}
float occlusion(float bias) {
    vec3 p = shadow.xyz / shadow.w * .5 + .5;
    if (p.z > 1. || any(lessThan(p.xy,vec2(0))) || any(greaterThan(p.xy,vec2(1)))) return 1.;
    float visibility = 0.;
    float blocker = texture(shadow_map,p.xy).r;
    float radius = mix(.00085,.0030,smoothstep(.0009,.013,p.z-blocker));
    for (int x=-2; x<=2; ++x) for (int y=-2; y<=2; ++y)
        visibility += step(p.z-bias, texture(shadow_map,p.xy + vec2(x,y)*radius).r);
    return visibility / 25.;
}
void main() {
    vec3 N=normalize(n), V=normalize(eye-world), L=normalize(source-world);
    vec3 base=pow(material.rgb,vec3(2.2));
    float metal=material.a;
    if (rolling_mark) {
        float width=max(fwidth(local.x),.008);
        float stripe=1.-smoothstep(.075-width,.075+width,abs(local.x));
        float dot=1.-smoothstep(.13,.15,length(local.xy-vec2(.43,.32)));
        base=mix(base,pow(vec3(.95,.50,.10),vec3(2.2)),max(stripe,dot)*.94);
    }
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
    if (material.a == 4.) {
        float pool=exp(-dot(world.xz,world.xz)*.062);
        float lit=occlusion(.0011);
        float stone=noise(world*15.)*.62 + noise(world*55.)*.38;
        vec3 color=(vec3(.006,.009,.017)+vec3(.018,.027,.044)*pool*(.23+.77*lit))*(.86+stone*.28);
        pixel=surface_pixel(display_color(color));
        return;
    }
    if (metal == 7.) {
        pixel=surface_pixel(display_color(base));
        return;
    }
    if (metal == 8.) {
        float rim=pow(1.-abs(dot(N,V)),2.5);
        pixel=vec4(display_color(base*(.18+rim)),.055+.28*rim);
        return;
    }
    if (metal == 9.) {
        float wrap=clamp(dot(N,L)*.55+.45,0.,1.);
        float rim=pow(1.-abs(dot(N,V)),2.);
        vec3 tissue=base*(.40+1.8*wrap)+vec3(.10,.025,.018)*pow(max(dot(-N,L),0.),2.);
        pixel=vec4(display_color(tissue),.24+.36*rim);
        return;
    }
    if (metal == 5. || metal == 6.) {
        float pores=noise(local*91.);
        float mottling=noise(local*12.)*.60 + noise(local*36.)*.40;
        base *= (.64+.6*mottling) * mix(.53,1.,smoothstep(.18,.44,pores));
        metal = 0.;
    }
    float usable = 1.-smoothstep(.010,.036,length(fwidth(local)));
    float grain = noise(local*(metal>.55 ? vec3(28,28,94) : vec3(38)));
    float stride = length(local.xy)*174.;
    float tooling = machined ? sin(stride+.42*grain)*(1.-smoothstep(1.1,3.,fwidth(stride))) : 0.;
    float patina=noise(local*5.)*.64 + noise(local*21.)*.36;
    float finish = usable*(.0008*grain+.00016*tooling);
    N=finish_normal(N,finish);
    base*=.85+.20*patina+.045*tooling;
    float roughness=clamp(mix(.59,.29,metal)+.15*(patina-.5)+.035*tooling,.23,.75);
    float alpha=roughness*roughness, a2=alpha*alpha;
    vec3 H=normalize(V+L);
    float nv=max(dot(N,V),.002), nl=max(dot(N,L),.001), nh=max(dot(N,H),0.);
    float visible=occlusion(mix(.0019,.00055,nl));
    float denom=nh*nh*(a2-1.)+1.;
    float D=a2/(3.141593*denom*denom);
    float k=pow(roughness+1.,2.)/8.;
    float G=(nv/(nv*(1.-k)+k))*(nl/(nl*(1.-k)+k));
    vec3 f0=mix(vec3(.041),max(base,vec3(.052)),metal);
    vec3 F=f0+(1.-f0)*pow(1.-clamp(dot(H,V),0.,1.),5.);
    vec3 diffuse=(1.-F)*(1.-metal)*base/3.141593;
    vec3 color=(diffuse+F*D*G/(4.*nv*nl))*nl*visible*vec3(3.5,3.12,2.72);

    vec3 R=reflect(-V,N);
    float top=max(dot(R,normalize(vec3(-.45,.82,.36))),0.);
    float card=max(dot(R,normalize(vec3(.89,.30,.34))),0.);
    float rim=max(dot(R,normalize(vec3(.15,.53,-.86))),0.);
    vec3 environment=vec3(.035,.053,.086)+vec3(.86,.72,.56)*pow(top,mix(24.,4.,roughness))
                    +vec3(.25,.51,.82)*pow(card,mix(58.,13.,roughness))
                    +vec3(.52,.72,.96)*pow(rim,mix(43.,9.,roughness));
    vec3 reflection=f0+(max(vec3(1.-roughness),f0)-f0)*pow(1.-nv,5.);
    color+=environment*reflection*(.60+.40*visible);
    vec3 fill=normalize(vec3(3.8,1.3,-2.1));
    color+=base*(vec3(.15,.19,.25)+vec3(.14,.22,.36)*max(dot(N,fill),0.))*(1.-.62*metal);
    pixel=surface_pixel(display_color(color));
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
    vec3 color=mix(vec3(.030,.044,.067),vec3(.174,.213,.268),glow);
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


@lru_cache(maxsize=96)
def _part_badge(label, size):
    width, height = size
    font = _font(round(width * .051))
    pad = round(width * .021)
    dot = round(width * .012)
    max_label_width = width*.82 - 3*pad - 2*dot
    while font.getlength(label) > max_label_width and font.size > 10:
        font = _font(font.size-1)
    layer = Image.new("RGBA", (ceil(font.getlength(label)) + 3*pad + 2*dot, font.size + pad))
    draw = ImageDraw.Draw(layer)
    accent, shadow = "#69efff", "#071319"
    draw.rounded_rectangle((0,0,layer.width-1,layer.height-1),radius=pad,
                           fill=shadow,outline=accent,width=max(1,round(width*.003)))
    middle = layer.height // 2
    draw.ellipse((pad,middle-dot,pad+2*dot,middle+dot),fill=accent)
    draw.text((2*pad+2*dot,middle),label,font=font,anchor="lm",fill="#e7fbff")
    return layer, (round(width*.072),round(height*.135))


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
            self.register_mesh(name,mesh(name))
        return self.meshes[name]

    def register_mesh(self, name, vertices):
        if name in self.meshes:
            return
        buffer = self.ctx.buffer(np.asarray(vertices,dtype="f4").tobytes())
        color = self.ctx.vertex_array(self.shader, [(buffer,"3f 3f","point","normal")])
        depth = self.ctx.vertex_array(self.depth_shader, [(buffer,"3f 12x","point")])
        self.meshes[name] = buffer, color, depth

    def frame(self, shot, elapsed, part=None, subtitle=None):
        objects, eye, focus = shot.at(elapsed, part)
        previous_camera = getattr(shot,"camera_from",None)
        if previous_camera is not None and elapsed<.8:
            amount = min(1.,max(0.,elapsed/.8))
            amount = amount**3*(10+amount*(-15+6*amount))
            old_eye,old_focus = previous_camera
            eye = np.asarray(old_eye)+(np.asarray(eye)-old_eye)*amount
            focus = np.asarray(old_focus)+(np.asarray(focus)-old_focus)*amount
        self.last_camera = (np.asarray(eye).copy(),np.asarray(focus).copy())
        if hasattr(shot,'camera'):
            # Labels must project through the same camera as the rendered
            # anatomy, including the eased transition between closeups.
            shot.camera=self.last_camera
        space = shot.subject == "moon"
        light = (-3.9,4.8,5.4) if not space else (-5.,1.7,2.0)
        light_view = _perspective(1.,1.05) @ _look_at(light,(0,0,0))
        self.ctx.enable(self.depth_flag)
        self.shadow.use()
        self.shadow.clear(depth=1.)
        if not space:
            _matrix(self.depth_shader["view"], light_view)
            for name, material, model, _ in objects:
                if material[3] in (8.,9.):
                    continue
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
        # Glass is composited after opaque internals, with depth writes off.
        import moderngl
        objects.sort(key=lambda obj: obj[1][3] in (8.,9.))
        transparent = False
        for name, material, model, group in objects:
            if material[3] in (8.,9.) and not transparent:
                transparent = True
                self.ctx.enable(moderngl.BLEND)
                self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
                self.multisample.depth_mask = False
            self.shader["material"].value = material
            self.shader["machined"].value = name.startswith(("gear", "ratchet", "drilled", "recessed")) or name in ("ring", "cylinder", "bolt")
            self.shader["rolling_mark"].value = name == "bearing-ball"
            self.shader["highlight"].value = float(group in groups and (not edge or name.startswith("gear")))
            _matrix(self.shader["model"], model)
            self._arrays(name)[1].render()
        if transparent:
            self.multisample.depth_mask = True
            self.ctx.disable(moderngl.BLEND)
        self.ctx.copy_framebuffer(self.framebuffer,self.multisample)
        pixels = self.framebuffer.read(components=3)
        frame = Image.frombytes("RGB",self.size,pixels,"raw","RGB",0,-1)
        if part:
            layer, xy = _part_badge(part.label,self.size)
            frame.paste(layer,xy,layer)
        if hasattr(shot,"overlay"):
            shot.overlay(frame,elapsed)
        if shot.subject == "bearing":
            label = ("PARTS SEPARATED FOR INSPECTION" if shot.view == "exploded" else
                     "WORKING CUTAWAY" if shot.view in ("cutaway","cage","rolling-balls") else "WORKING BALL BEARING")
            draw = ImageDraw.Draw(frame)
            draw.text((self.size[0]*.07,self.size[1]*.075),label,font=_font(round(self.size[0]*.030)),fill="#a9c1d0")
        caption = subtitle or shot.caption
        if caption:
            layer, xy = caption
            frame.paste(layer,xy,layer)
        return frame


class Shot:
    def __init__(self, subject, view, size, caption="", opening=False, offset=0, action_start=None, duration=3., previous_view=None):
        self.subject = subject
        self.geometry = SUBJECTS[subject]()
        self.view = view
        self.offset = offset
        self.action_start = offset if action_start is None else action_start
        self.duration = duration
        self.previous_view = previous_view
        self.caption = caption_layer(caption,size,opening) if caption else None
        if subject == "toaster":
            self.floor = -.955

    def at(self, t, part=None):
        if self.subject == "toaster":
            return _toaster_shot(self.geometry.parts, self.view, t / max(self.duration, .01))
        if self.subject == "bearing":
            from bearing_mechanism import bearing_shot
            return bearing_shot(self.geometry.parts,self.view,t+self.offset,
                                t/max(self.duration,.01),part,self.previous_view,t)
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
        focus, eye = shots[VIEWS[self.subject].index(view)]
        return objects, eye, np.asarray(focus)


def _ease(progress, start, end):
    fraction = min(1., max(0., (progress-start)/(end-start)))
    return fraction*fraction*(3.-2.*fraction)


def _toaster_shot(parts, view, progress):
    # The shot boundaries share the same mechanism state so cuts preserve the action.
    lowered = _ease(progress, .12, .57) if view == "latch" else float(view in ("heating","browning","release","pop-up"))
    rise = _ease(progress, .18, .36) if view == "pop-up" else 0.
    if view == "pop-up":
        rise += .085*sin(3*pi*_ease(progress,.36,.57))*(1.-_ease(progress,.36,.57))
    engaged = (_ease(progress, .51, .70) if view == "latch" else
               1.-_ease(progress,.26,.57) if view == "release" else float(view in ("heating","browning")))
    heat = (_ease(progress,.04,.46) if view == "heating" else
            1.-_ease(progress,.24,.48) if view == "release" else float(view == "browning"))
    toasted = _ease(progress,.10,.89) if view == "browning" else float(view in ("release","pop-up"))
    carriage = .29 - .74*(lowered-rise)
    cutaway = view in ("latch", "heating", "browning", "release")
    roll = .88*(1.-engaged)
    pivot = (1.09,-.37,.55)
    transforms = {"carriage":translate(0,carriage,0), "lever":translate(0,carriage,0),
                  "latch":translate(*pivot) @ spin(roll) @ translate(-.103,0,0)}
    if view == "pop-up":
        transforms["cover"] = translate(-3.55*(1.-_ease(progress,.58,.95)),0,0)
    objects = []
    for name, material, model, group in parts:
        if group == "cover" and cutaway:
            continue
        transform = transforms.get(group)
        objects.append((name, material, model if transform is None else transform @ model, group))
    spring = translate(.91,(carriage-.565)/2,.56) @ scale(1,carriage+.565,1)
    objects.append(("toaster-spring",(.57,.42,.19,.76),spring,"spring"))

    glow = heat*(.965 + .035*sin(9*progress))
    wire = (.18+2.05*glow,.105+.52*glow,.075-.015*glow,7.) if glow > 0 else (.19,.16,.16,.55)
    for z in (-.545,0,.545):
        objects.append(("toaster-wire", wire, translate(0,.017,z), "heater"))
    crumb = (.94-.30*toasted,.82-.39*toasted,.60-.33*toasted,5.)
    crust = (.62-.18*toasted,.34-.14*toasted,.15-.07*toasted,6.)
    if view != "wide":
        for index, z in enumerate(TOASTER_SLOTS):
            delay = 1.-_ease(progress,.13*index+.10,.13*index+.66) if view == "loading" else 0.
            bread = translate(0,carriage+.492+.95*delay,z) @ scale(1.39,.89,.153)
            objects.extend((("bread-crumb",crumb,bread,"bread"),("bread-crust",crust,bread,"bread")))

    targets = {
        "wide": ((0,.04,0),(2.15,2.15,5.90)),
        "loading": ((0,.53,0),(1.98,2.90,5.95)),
        "latch": ((.38,-.06,.18),(1.32,1.52,4.63)),
        "heating": ((0,.07,.08),(-.81,1.24,4.47)),
        "browning": ((0,.13,.10),(-1.04,1.51,4.06)),
        "release": ((.43,-.09,.33),(1.15,1.39,4.54)),
        "pop-up": ((0,.22,0),(1.84,2.09,5.88)),
    }
    focus, eye = targets[view]
    return objects, (eye[0]+.33*(progress-.5),eye[1],eye[2]), np.asarray(focus)
