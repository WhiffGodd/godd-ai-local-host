# SPDX-License-Identifier: MIT
"""Modeled subjects and motion for the AI studio's cinematic shots."""

from math import cos, pi, sin, tau

import numpy as np


STEEL = (.37, .45, .51, .78)
CHROME = (.58, .66, .70, .92)
GOLD = (.84, .34, .085, .72)
RED = (.52, .033, .026, .55)
RUBBER = (.062, .071, .077, .02)
ROPE = (.65, .39, .17, .05)


def translate(x, y, z):
    matrix = np.eye(4)
    matrix[:3, 3] = (x, y, z)
    return matrix


def scale(x, y, z):
    return np.diag([x, y, z, 1.])


def spin(angle):
    c, s = cos(angle), sin(angle)
    return np.array([[c, -s, 0., 0.], [s, c, 0., 0.], [0., 0., 1., 0.], [0., 0., 0., 1.]])


def tube(start, end, radius):
    start, end = np.array(start), np.array(end)
    direction = end - start
    length = np.linalg.norm(direction)
    z = direction / length
    reference = (0., 1., 0.) if abs(z[1]) < .95 else (1., 0., 0.)
    x = np.cross(reference, z)
    x /= np.linalg.norm(x)
    matrix = translate(*((start + end) / 2))
    matrix[:3, :3] = np.column_stack((radius * x, radius * np.cross(z, x), length * z))
    return matrix


def _surface(point, rings, sides):
    grid = [[point(i / rings, j / sides) for j in range(sides + 1)] for i in range(rings + 1)]
    return [vertex for i in range(rings) for j in range(sides)
            for vertex in (grid[i][j], grid[i + 1][j], grid[i + 1][j + 1],
                           grid[i][j], grid[i + 1][j + 1], grid[i][j + 1])]


def mesh(name):
    if name in ("bread-crumb", "bread-crust"):
        outline = [(-.40,-.50), (.40,-.50), (.46,-.44), (.46,.19), (.50,.23)]
        outline += [(.50*cos(pi*i/20), .23+.27*sin(pi*i/20)) for i in range(1,21)]
        outline += [(-.46,.19),(-.46,-.44)]
        vertices = []
        for a, b in zip(outline, outline[1:] + outline[:1]):
            for z in (-.5, .5):
                if name == "bread-crumb":
                    face = [(0.,0.), (.915*a[0],.915*a[1]), (.915*b[0],.915*b[1])]
                else:
                    inner_a = (.915*a[0],.915*a[1])
                    inner_b = (.915*b[0],.915*b[1])
                    face = [a,b,inner_b,a,inner_b,inner_a]
                vertices.extend((*p,z,0.,0.,2*z) for p in face)
            if name == "bread-crust":
                outward = np.array((b[1]-a[1], a[0]-b[0]))
                outward /= np.linalg.norm(outward)
                vertices.extend((*point,z,*outward,0.) for point, z in (
                    (a,-.5),(b,-.5),(b,.5),(a,-.5),(b,.5),(a,.5)))
        return vertices
    if name == "toaster-spring":
        def spring(u, v):
            a, b = tau*7*u, tau*v
            r = .106 + .017*cos(b)
            return (r*cos(a), u-.5+.017*sin(b), r*sin(a), cos(a)*cos(b), sin(b), sin(a)*cos(b))
        return _surface(spring, 112, 9)
    if name == "toaster-wire":
        wire = np.asarray(mesh("cylinder"))
        path = [(-.75,.52,0)]
        for i in range(6):
            y = .52-.19*i
            x = .75 if i % 2 == 0 else -.75
            path.append((x,y,0))
            if i < 5:
                path.extend(((x*1.038,y-.035,0),(x*1.038,y-.155,0),(x,y-.19,0)))
        segments = []
        for a, b in zip(path, path[1:]):
            model = tube(a,b,.014)
            direction = model[:3,:3]
            points = wire[:,:3] @ direction.T + model[:3,3]
            normals = wire[:,3:] @ np.linalg.inv(direction)
            segments.append(np.column_stack((points,normals)))
        return np.concatenate(segments)
    if name == "drilled-rotor":
        vertices = []
        holes = 18
        for i in range(holes):
            angle = tau * (i+.5)/holes
            center = np.array((.86*cos(angle), .86*sin(angle)))

            def perimeter(u):
                edge = min(int(u*4),3)
                p = u*4-edge
                left, right = angle-pi/holes, angle+pi/holes
                a, radius = ((left+(right-left)*p,1.),(right,1.-.28*p),
                             (right-(right-left)*p,.72),(left,.72+.28*p))[edge]
                return np.array((radius*cos(a),radius*sin(a)))

            def section(u, v, side):
                outer = perimeter(u)
                radial = outer-center
                radial /= np.linalg.norm(radial)
                inner = center+.043*radial
                x,y = inner+(outer-inner)*v
                return (x,y,side*.5,0.,0.,side)

            def bore(u, v, side):
                radial=perimeter(u)-center
                radial /= np.linalg.norm(radial)
                x,y=center+(.034+.009*v)*radial
                return (x,y,side*(.24+.26*v),-radial[0],-radial[1],side*.38)

            def wall(u, v, radius, normal):
                a = tau*(i+u)/holes
                x,y=cos(a),sin(a)
                return (radius*x,radius*y,v-.5,normal*x,normal*y,0.)

            def tunnel(u, v):
                radial=perimeter(u)-center
                radial /= np.linalg.norm(radial)
                x,y=center+.034*radial
                return (x,y,.48*v-.24,-radial[0],-radial[1],0.)

            for side in (-1., 1.):
                vertices.extend(_surface(lambda u,v:section(u,v,side),32,1))
                vertices.extend(_surface(lambda u,v:bore(u,v,side),32,1))
            vertices.extend(_surface(tunnel,32,1))
            vertices.extend(_surface(lambda u,v:wall(u,v,1.,1.),8,1))
            vertices.extend(_surface(lambda u,v:wall(u,v,.72,-1.),8,1))
        return vertices
    if name == "ratchet":
        # Internal saw teeth leave the pawls visible through the front of the ring.
        def edge(u):
            phase = round(u*112) % 4
            return (.79,.795,.887,.89)[phase]
        def face(u, v, z):
            a, r = tau*u, edge(u)*(1-v)+v
            return (r*cos(a),r*sin(a),z,0.,0.,2*z)
        def wall(u, v, inner):
            a, r = tau*u, edge(u) if inner else 1.
            return (r*cos(a),r*sin(a),v-.5,(-1 if inner else 1)*cos(a),(-1 if inner else 1)*sin(a),0.)
        return (_surface(lambda u,v:face(u,v,.5),112,1) + _surface(lambda u,v:face(u,v,-.5),112,1)
                + _surface(lambda u,v:wall(u,v,True),112,1) + _surface(lambda u,v:wall(u,v,False),112,1))
    if name in ("wave", "wave-double"):
        cycles = 1 if name == "wave" else 2
        def wave(u, v):
            phase, angle = tau*cycles*u, tau*v
            dx, dy = 2., .52*tau*cycles*cos(phase)
            length = (dx*dx + dy*dy)**.5
            nx, ny, nz = -dy*cos(angle)/length, dx*cos(angle)/length, sin(angle)
            return (2*u-1+.044*nx, .52*sin(phase)+.044*ny, .044*nz, nx, ny, nz)
        return _surface(wave, 132, 12)
    if name == "cone":
        def side(u, v):
            angle = v*tau
            return ((1-u)*cos(angle),(1-u)*sin(angle),u-.5,cos(angle),sin(angle),1.)
        def cap(u, v):
            angle = v*tau
            return (u*cos(angle),u*sin(angle),-.5,0.,0.,-1.)
        return _surface(side, 1, 48) + _surface(cap, 1, 48)
    if name == "prism":
        corners = ((-.57,-.44),(.57,-.44),(0,.57))
        vertices = [(*point,z,0.,0.,z*2) for z in (-.5,.5) for point in corners]
        for left, right in zip(corners, (*corners[1:],corners[0])):
            dx, dy = right[0]-left[0], right[1]-left[1]
            for point, z in ((left,-.5),(right,-.5),(right,.5),(left,-.5),(right,.5),(left,.5)):
                vertices.append((*point,z,dy,-dx,0.))
        return vertices
    if name == "sphere":
        def sphere(u, v):
            point = (sin(pi*u)*cos(tau*v), cos(pi*u), sin(pi*u)*sin(tau*v))
            return (*point, *point)
        return _surface(sphere, 42, 64)
    if name == "chain-link":
        cylinder = np.array(mesh("bolt"))
        plates = np.array(mesh("box"))
        pieces = []
        for z in (-.38, .38):
            piece = plates.copy()
            piece[:, :3] *= (1., .91, .21)
            piece[:, 2] += z
            pieces.append(piece)
        for x in (-.30, .30):
            piece = cylinder.copy()
            piece[:, :3] *= (.17, .38, .99)
            piece[:, 0] += x
            pieces.append(piece)
        return np.concatenate(pieces)
    if name in ("box", "beveled-box"):
        faces = []
        for axis in range(3):
            for sign in (-1, 1):
                normal = np.eye(3)[axis] * sign
                u, v = np.eye(3)[(axis+1)%3], np.eye(3)[(axis+2)%3]
                if name == "box":
                    faces.extend((*((normal + u*a + v*b) / 2), *normal)
                                 for a, b in ((-1,-1),(1,-1),(1,1),(-1,-1),(1,1),(-1,1)))
                else:
                    def beveled(a, b):
                        point = normal*.5 + u*(a-.5) + v*(b-.5)
                        core = np.clip(point, -.462, .462)
                        rounded = point - core
                        rounded /= np.linalg.norm(rounded)
                        return (*(core + .038*rounded), *rounded)
                    faces.extend(_surface(beveled, 24, 24))
        return faces
    if name in ("tire", "rim", "groove", "rope-loop"):
        minor = {"tire": .072, "rim": .040, "groove": .12, "rope-loop": .053}[name]

        def torus(u, v):
            cu, su, cv, sv = cos(tau*u), sin(tau*u), cos(tau*v), sin(tau*v)
            return ((1+minor*cv)*cu, (1+minor*cv)*su, minor*sv, cv*cu, cv*su, sv)
        return _surface(torus, 96, 16)

    if name == "shell":
        vertices = []
        for radius, normal in ((1., 1.), (.86, -1.)):
            def wall(u, v):
                angle = pi * (u + .5)
                x, y = cos(angle), sin(angle)
                return (x*radius, y*radius, v-.5, x*normal, y*normal, 0.)
            vertices.extend(_surface(wall, 44, 1))
        for depth in (-.5, .5):
            def lip(u, v):
                angle = pi * (u + .5)
                r = .86 + .14 * v
                return (r*cos(angle), r*sin(angle), depth, 0., 0., depth*2)
            vertices.extend(_surface(lip, 44, 1))
        for angle in (.5*pi, 1.5*pi):
            def edge(u, v):
                r = .86 + .14*u
                return (r*cos(angle), r*sin(angle), v-.5, sin(angle), -cos(angle), 0.)
            vertices.extend(_surface(edge, 1, 1))
        return vertices

    if name == "turbine-blade":
        def blade(u, v):
            angle = tau*v
            width = (.14 + .14*sin(pi*u)) * (1-u)**.68 + .018
            pitch = .47 - u*.58
            x, z = cos(angle)*width, sin(angle)*width*.28
            return (x*cos(pitch)-z*sin(pitch)-.19*u*u, .12+1.15*u,
                    x*sin(pitch)+z*cos(pitch), cos(angle), .07, sin(angle))
        return _surface(blade, 32, 18)

    teeth = int(name.removeprefix("gear")) if name.startswith("gear") else 0
    hexagonal = name in ("bolt", "recessed-bolt")
    inner = .25 if teeth else {"ring": .72, "recessed-bolt": .46}.get(name,0.)
    sides = teeth * 4 if teeth else (6 if hexagonal else 48)
    # The layered profile forms the bore, flat faces and beveled edges.
    profile = [(inner, -.5, (0,-1)), (.84 if teeth else .90,-.5,(0,-1)),
               (1.,-.37,(.85,-.53)), (1.,.37,(.85,.53)),
               (.84 if teeth else .90,.5,(0,1)), (inner,.5,(0,1)),
               (inner,.5,(-1,0)), (inner,-.5,(-1,0))]

    def ring(i, j):
        radius, z, (nr, nz) = profile[i]
        if teeth and i in (2, 3) and j % 4 in (0, 3):
            radius = .86
        c, s = cos(tau*j/sides), sin(tau*j/sides)
        return (radius*c, radius*s, z, nr*c, nr*s, nz)

    return [ring(i + di, j + dj) for i in range(len(profile)-1) for j in range(sides)
            for di, dj in ((0,0),(1,0),(1,1),(0,0),(1,1),(0,1))]


class Subject:
    def __init__(self):
        self.parts = []

    def add(self, mesh_name, material, model, group=""):
        self.parts.append((mesh_name, material, model, group))

    def place(self, mesh_name, material, point, dimensions, group="", angle=0):
        self.add(mesh_name, material, translate(*point) @ spin(angle) @ scale(*dimensions), group)

    def pipe(self, start, end, radius, material, group=""):
        self.add("cylinder", material, tube(start, end, radius), group)


def bicycle():
    s = Subject()
    rear, front = (-1.48, .03, 0), (1.48, .03, 0)
    crank, seat, head = (-.11, -.13, 0), (-.59, 1.16, 0), (.89, 1.16, 0)
    fork = (1.04, .77, 0)
    for hub, group in ((rear, "rear-wheel"), (front, "front-wheel")):
        s.place("tire", RUBBER, hub, (.83,.83,1.02), group)
        s.place("rim", STEEL, hub, (.77,.77,.89), group)
        s.place("cylinder", CHROME, hub, (.12,.12,.31), "rear-hub" if group == "rear-wheel" else group)
        for i in range(24):
            a, b = tau*i/24, tau*i/24 + (-1)**i*.17
            s.pipe((hub[0] + .12*cos(b), hub[1] + .12*sin(b), (-1)**i*.11),
                   (hub[0] + .77*cos(a), hub[1] + .77*sin(a), 0), .008, CHROME, group)
    for a, b, radius in ((crank, seat,.056),(seat,head,.046),(head,crank,.070),(head,fork,.068)):
        s.pipe(a,b,radius,RED)
    for side in (-1, 1):
        for a, b, radius in ((rear,crank,.036),(rear,seat,.029),(front,fork,.046)):
            s.pipe((a[0],a[1],side*.100), (b[0],b[1],side*.050),radius,RED)
    s.pipe(seat,(-.68,1.45,0),.028,CHROME)
    s.place("sphere", RUBBER, (-.70,1.47,0), (.32,.052,.15), angle=-.12)
    s.pipe(head,(.82,1.45,0),.037,STEEL)
    s.pipe((.82,1.45,0),(1.11,1.51,0),.031,STEEL)
    s.pipe((1.11,1.51,-.32),(1.11,1.51,.32),.031,CHROME)
    for side in (-1, 1):
        s.pipe((1.11,1.51,side*.32),(1.15,1.47,side*.40),.039,RUBBER)
    for x,y,r,name in ((*crank[:2],.375,"chainring"),(*rear[:2],.192,"cog")):
        s.place("gear32" if name == "chainring" else "gear16", GOLD, (x,y,.26), (r,r,.057), name)
        s.place("cylinder", STEEL, (x,y,.26), (r*.29,r*.29,.10), "rear-hub" if name == "cog" else "crank")
    for side in (-1,1):
        z = side*.31
        s.pipe((crank[0],crank[1],z),(crank[0]+side*.40,crank[1],z),.046,CHROME,"crank")
        s.place("box", RUBBER, (crank[0]+side*.40,crank[1],side*.39), (.15,.075,.20), "pedal")
    return s


def gear_train():
    s = Subject()
    s.place("beveled-box", (.16,.19,.21,.42), (0,0,-.52), (3.55,1.9,.14))
    for y in (-.82, .82):
        s.place("beveled-box", STEEL, (0,y,-.43), (3.45,.13,.085))
    for x,y,r,teeth,group in ((-.90,.06,.77,24,"drive"),(.24,.06,.41,12,"idler"),(1.15,.06,.55,16,"output")):
        material = GOLD if group == "drive" else CHROME
        s.place(f"gear{teeth}", material, (x,y,0), (r,r,.19), group)
        s.place("cylinder", STEEL, (x,y,-.12), (r*.245,r*.245,.84))
        s.place("bolt", CHROME, (x,y,.28), (r*.18,r*.18,.12))
        for a in range(5):
            t = tau*a/5
            s.place("bolt", STEEL, (x+r*.55*cos(t),y+r*.55*sin(t),.115), (.048,.048,.065), group)
            s.place("cylinder", CHROME, (x+r*.27*cos(t),y+r*.27*sin(t),.107), (.024,.024,.034), group)
    for x in (-1.6,1.6):
        for y in (-.77,.77):
            s.place("bolt",CHROME,(x,y,-.38),(.09,.09,.12))
    return s


def pulley():
    s = Subject()
    s.place("beveled-box", STEEL, (0,1.68,-.25), (2.8,.16,.48))
    s.pipe((0,1.68,-.24),(0,.91,-.24),.066,STEEL)
    for z in (-.15,.15):
        s.place("cylinder",CHROME,(0,.9,z),(.48,.48,.066),"wheel")
    s.place("gear16",STEEL,(0,.9,0),(.40,.40,.25),"wheel")
    s.place("cylinder",GOLD,(0,.9,.22),(.11,.11,.18))
    for i in range(5):
        a = tau*i/5
        s.place("cylinder",STEEL,(.30*cos(a),.90+.30*sin(a),.19),(.049,.049,.06),"wheel")
    s.place("beveled-box",GOLD,(-.44,-.80,.02),(.56,.48,.45),"load")
    for dx in (-.20,.20):
        s.place("box",STEEL,(-.44+dx,-.80,.02),(.045,.49,.47),"load")
    s.place("groove",CHROME,(-.44,-.52,0),(.075,.075,.075),"load")
    s.place("cylinder",RED,(.44,-.55,0),(.083,.083,.27),"handle",pi/2)
    for i in range(16):
        a, b = pi*i/16, pi*(i+1)/16
        s.pipe((.44*cos(a),.9+.44*sin(a),0),(.44*cos(b),.9+.44*sin(b),0),.023,ROPE,"rope")
    return s


def moon():
    s = Subject()
    s.place("sphere", (.09,.30,.59,2.), (0,0,0), (.82,.82,.82), "earth")
    s.place("sphere", (.50,.47,.44,3.), (0,0,0), (.24,.24,.24), "moon")
    return s


def piston():
    s = Subject()
    s.place("beveled-box", (.13,.18,.23,.48), (0,-.99,-.13), (1.88,.18,1.26))
    s.add("shell", STEEL, tube((0,.25,0),(0,1.41,0),.61), "cylinder")
    for y in (.37,.52,.67,.82,.97,1.12,1.27):
        s.add("shell", STEEL, tube((0,y-.025,0),(0,y+.025,0),.66), "cylinder")
    for x in (-.69,.69):
        s.pipe((x,-.92,-.43),(x,1.45,-.43),.042,CHROME)
        s.place("bolt", CHROME, (x,1.45,-.43), (.10,.10,.072))
    s.place("cylinder", STEEL, (0,-.52,0), (.125,.125,1.2), "crank")
    for z in (-.25,.25):
        s.place("cylinder", CHROME, (0,-.52,z), (.42,.42,.14), "crank")
        s.place("bolt", GOLD, (.33,-.52,z), (.13,.13,.19), "crank")
    s.pipe((0,-.13,0),(0,.26,0),.49,GOLD,"piston")
    for y in (.09,.145,.20):
        s.pipe((0,y-.012,0),(0,y+.012,0),.507,CHROME,"piston")
    s.place("cylinder", STEEL, (0,0,0), (.15,.15,.95), "piston")
    return s


def turbine():
    s = Subject()
    white = (.73,.79,.80,.28)
    s.place("beveled-box", STEEL, (0,-1.11,-.14), (1.50,.16,1.30))
    s.pipe((0,-1.02,-.14),(0,.85,-.14),.16,white,"tower")
    for y in (-.92,-.69,.66):
        s.pipe((0,y-.024,-.14),(0,y+.024,-.14),.181,STEEL)
    s.place("beveled-box", white, (0,1.03,-.36), (.51,.38,.91), "nacelle")
    s.place("beveled-box", (.16,.33,.33,.48), (0,1.06,.015), (.35,.28,.05), "nacelle")
    s.place("cylinder", STEEL, (0,1.04,.20), (.073,.073,.72), "shaft")
    s.place("sphere", white, (0,1.04,.58), (.17,.17,.22), "hub")
    for index in range(3):
        a = tau*index/3
        s.place("turbine-blade", white, (0,1.04,.50), (1,1,1), "blades", angle=a)
        s.place("bolt", GOLD, (-.14*sin(a),1.04+.14*cos(a),.63), (.026,.026,.046), "hub")
    return s


def hydraulic_lift():
    s = Subject()
    s.place("beveled-box", STEEL, (0,-1.08,-.05), (2.68,.20,1.35))
    for x, radius, height in ((-.78,.28,1.04),(.64,.57,.87)):
        s.add("shell", STEEL, tube((x,-.86,0),(x,-.86+height,0),radius))
        s.pipe((x,-.88,0),(x,-.76,0),radius*1.11,CHROME)
        for z in (-.41,.41):
            s.place("bolt", CHROME, (x,-.96,z), (.095,.095,.09))
    s.pipe((-.78,-.73,.10),(.64,-.73,.10),.09,(.10,.55,.67,.25),"fluid")
    for x in (-.51,.13):
        s.pipe((x-.045,-.73,.10),(x+.045,-.73,.10),.119,CHROME)
    s.pipe((-.78,0,0),(-.78,.45,0),.072,CHROME,"input")
    s.place("beveled-box", GOLD, (-.78,.46,0), (.47,.11,.23), "input")
    s.pipe((.64,0,0),(.64,.46,0),.15,CHROME,"output")
    s.place("beveled-box", STEEL, (.64,.47,0), (1.19,.13,.95), "output")
    s.place("beveled-box", GOLD, (.64,.74,0), (.70,.43,.64), "load")
    return s


def bearing():
    s = Subject()
    s.place("beveled-box", STEEL, (0,-.93,-.30), (2.45,.21,1.20))
    for z in (-.16,.10):
        s.place("ring", STEEL, (0,.16,z), (1.04,1.04,.082), "outer")
        s.place("ring", CHROME, (0,.16,z+.034), (.52,.52,.087), "inner")
    s.place("ring", GOLD, (0,.16,-.08), (.79,.79,.065), "cage")
    for index in range(9):
        angle = tau*index/9
        x, y = .65*cos(angle), .16+.65*sin(angle)
        s.place("sphere", CHROME, (x,y,.07), (.143,.143,.143), "balls")
        s.place("bolt", GOLD, (.43*cos(angle),.16+.43*sin(angle),.177), (.033,.033,.055), "inner")
        s.place("bolt", STEEL, (.93*cos(angle),.16+.93*sin(angle),.164), (.053,.053,.056))
    return s


def disc_brake():
    s = Subject()
    s.place("beveled-box", STEEL, (0,-.95,-.21), (2.44,.24,1.51))
    for z in (-.055,.055):
        s.place("drilled-rotor", CHROME, (-.1,.28,z), (1.01,1.01,.059), "rotor")
    s.place("cylinder", STEEL, (-.1,.28,0), (.32,.32,.24), "rotor")
    for index in range(8):
        a = tau*index/8
        center = (-.1+.54*cos(a),.28+.54*sin(a),0)
        s.place("beveled-box", STEEL, center, (.46,.14,.11), "rotor", angle=a+.22)
        s.place("recessed-bolt", STEEL, (-.1+.23*cos(a),.28+.23*sin(a),.15), (.050,.050,.10), "rotor")
        s.place("beveled-box", STEEL, (-.1+.875*cos(a),.28+.875*sin(a),0.), (.21,.048,.071), "rotor", angle=a+.26)
    s.place("beveled-box", RED, (1.03,.60,0), (.36,.76,.71), "caliper")
    s.place("beveled-box", RED, (.79,.60,-.30), (.63,.73,.20), "caliper")
    # The near half of the caliper is cut away to expose the moving pad.
    for y in (.31,.89):
        s.place("beveled-box", RED, (.79,y,.30), (.63,.12,.20), "caliper")
    for sign in (-1,1):
        s.place("beveled-box", GOLD, (.76,.60,sign*.193), (.42,.57,.091), f"pad{sign}")
        s.place("bolt", CHROME, (.88,.79,sign*.418), (.075,.075,.08))
    s.pipe((1.12,.95,0),(1.35,1.20,-.21),.046,RUBBER)
    return s


def freewheel():
    s = Subject()
    blue = (.11,.35,.61,.78)
    s.place("beveled-box", (.15,.20,.27,.45), (0,-1.05,-.23), (2.75,.25,1.40))
    s.place("cylinder", CHROME, (0,0,0), (.15,.15,1.65), "axle")
    s.place("gear32", blue, (0,0,-.43), (1.09,1.09,.15), "sprocket")
    s.place("ring", STEEL, (0,0,-.26), (1.04,1.04,.20), "hub")
    s.place("ratchet", CHROME, (0,0,.11), (1.03,1.03,.25), "ratchet")
    s.place("rim", blue, (0,0,.21), (1.06,1.06,.60), "hub")
    s.place("cylinder", blue, (0,0,.05), (.69,.69,.22), "driver")
    s.place("ring", STEEL, (0,0,.18), (.54,.54,.11), "driver")
    s.place("ring", CHROME, (0,0,.245), (.375,.375,.058), "driver")
    s.place("ring", (.11,.13,.16,.4), (0,0,.27), (.263,.263,.047), "driver")
    s.place("ring", blue, (0,0,.45), (1.05,1.05,.10), "cover")
    s.place("cylinder", blue, (0,0,.45), (.81,.81,.10), "cover")
    for i in range(12):
        a = tau*i/12
        s.place("recessed-bolt", STEEL, (.96*cos(a),.96*sin(a),.254), (.046,.046,.079), "hub")
        s.place("beveled-box", blue, (1.057*cos(a),1.057*sin(a),-.033), (.10,.060,.26), "hub", a)
    for i in range(3):
        a = tau*i/3
        s.place("beveled-box", GOLD, (.768*cos(a),.768*sin(a),.23), (.245,.13,.13), f"pawl{i}", a+.24)
        s.place("recessed-bolt", CHROME, (.665*cos(a),.665*sin(a),.31), (.059,.059,.096), "driver")
    return s


TOASTER_STEEL = (.66,.70,.74,.86)
TOASTER_SLOTS = (-.32,.32)


def toaster():
    s = Subject()
    metal = TOASTER_STEEL
    mica = (.34,.25,.22,.16)
    s.place("beveled-box", RUBBER, (0,-.78,0), (2.55,.26,1.57))
    s.place("beveled-box", metal, (0,-.59,0), (2.48,.12,1.48))
    for x in (-1.20,1.20):
        s.place("beveled-box", metal, (x,.025,0), (.16,1.25,1.50))
        s.place("beveled-box", CHROME, (x,.65,0), (.24,.13,1.53))
    for z, width in ((-.64,.26),(0,.29),(.64,.26)):
        s.place("beveled-box", metal, (0,.65,z), (2.35,.13,width))
    for z in TOASTER_SLOTS:
        for side in (-1,1):
            s.place("beveled-box", CHROME, (0,.676,z+side*.185), (2.02,.073,.044))
            s.place("beveled-box", STEEL, (side*.94,.65,z), (.11,.12,.34))
        s.place("beveled-box", CHROME, (0,0,z), (1.57,.086,.31), "carriage")
        for x in (-.72,.72):
            s.place("beveled-box", STEEL, (x,.10,z), (.047,.22,.26), "carriage")
    s.place("beveled-box", metal, (0,.025,-.737), (2.37,1.25,.14))
    s.place("beveled-box", metal, (0,.025,.737), (2.37,1.25,.14), "cover")
    s.place("beveled-box", RUBBER, (.967,.10,.822), (.11,.89,.034), "cover")
    s.place("beveled-box", CHROME, (.967,0,.63), (.11,.084,.41), "lever")
    s.place("beveled-box", RUBBER, (.967,0,.885), (.27,.125,.23), "lever")
    s.place("cylinder", RUBBER, (-.92,-.38,.815), (.15,.15,.087), "cover")
    s.place("cylinder", CHROME, (-.92,-.38,.876), (.113,.113,.08), "cover")
    s.place("beveled-box", RUBBER, (-.92,-.32,.922), (.027,.056,.021), "cover")
    for z in (-.545,0):
        s.place("beveled-box", mica, (0,.02,z-.018), (1.71,1.15,.039))
    # The guide rod and spring run vertically next to the carriage.
    s.pipe((.91,-.61,.56),(.91,.53,.56),.043,STEEL,"guide")
    s.add("ring", CHROME, tube((.91,-.04,.56),(.91,.04,.56),.094), "carriage")
    s.place("beveled-box", GOLD, (0,0,0), (.25,.084,.14), "latch")
    s.place("cylinder", STEEL, (1.09,-.37,.55), (.058,.058,.20))
    return s


SUBJECTS = {
    "bicycle": bicycle, "gears": gear_train, "pulley": pulley, "moon": moon,
    "piston": piston, "turbine": turbine, "hydraulics": hydraulic_lift,
    "bearing": bearing, "disc_brake": disc_brake, "freewheel": freewheel, "toaster": toaster,
}
