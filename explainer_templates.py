"""Original motion templates for the AI video studio."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Template:
    id: str
    name: str
    category: str
    diagram: str
    surface: str
    background: str
    ink: str
    accent: str
    secondary: str


# The diagram is the default for scene planning. Surface and palette control
# the composition independently so a style can use a diagram suited to a topic.
_STYLES = """
Mechanisms|Blueprint Lab|parts|grid|101f3c|e0f2ff|63ccff|4185ef
Mechanisms|Glass Workshop|parts|glass|102829|ddfff4|5bf4c4|117b7d
Mechanisms|Technical Draft|flow|paper|ece9d7|232e2a|19655a|b37b49
Mechanisms|Industrial Cutaway|cutaway|grid|161c21|f3f4e8|ffb44d|7f9aaa
Mechanisms|Assembly Cards|sequence|cards|202338|eef0ff|ff9b8c|987bf4
Mechanisms|Machine Room|cycle|glass|201b19|fff0db|ff8452|d0ac69
Mechanisms|Mechanical Motion|motion|grid|161d27|e2efff|a4de5e|558ae2
Mechanisms|Precision Layers|cutaway|glass|221b35|f1e9ff|c29aff|7297f7
Mechanisms|Engineering Notes|parts|paper|f4ecdc|2b261e|994c2e|355e84
Mechanisms|Signal Path|flow|grid|0b222b|dffaff|58e5ff|6b8ffa
Mechanisms|System Overview|network|cards|13152a|f1edff|a6acff|51d6bf
Science|Orbit Theater|orbit|stars|0f1230|e9edff|a48bff|6de6ff
Science|Field Lines|wave|grid|0e2130|eefaff|6ee7b7|4ca4ff
Science|Molecular Glow|network|stars|122b25|e8fff1|b6fb77|3ac9ae
Science|Particle Studio|motion|stars|241532|fceeff|ff89c5|9baaff
Science|Wave Bench|wave|glass|102330|e7f8ff|67daff|c79af5
Science|Earth Layers|cutaway|paper|eee5ce|30281b|9c5031|687c36
Science|Nature Cycle|cycle|paper|edf0d7|243626|4e7447|9b671e
Science|Gravity Grid|orbit|grid|19263d|e1ecff|f6d77c|65cfee
Science|Micro World|parts|glass|10252c|e7fff8|5eead4|5ea6fa
Science|Light Spectrum|wave|stars|231c42|f3efff|ffa8ea|8eabff
Science|Energy Transfer|flow|grid|201728|fff2fe|ffc471|f780ab
Data|Chart Room|bars|grid|141c2b|eaf3ff|8fb3ff|66e5c1
Data|Market Pulse|wave|grid|141c1a|e6fff1|a7f576|e8bb63
Data|Number Stack|bars|cards|241d35|f6ebff|bd9aff|fdad79
Data|Data Blocks|compare|paper|eeeaf7|252045|5445b8|9f487c
Data|Timeline Rail|sequence|grid|13243b|e7f6ff|80edfa|fa9da2
Data|Proportion Lab|compare|glass|2a1733|fff0fa|ffa1cf|ae9cff
Data|Metrics Panel|bars|cards|101f36|edf5ff|6ef0f1|7995ff
Data|Scale Lineup|bars|paper|f5efd9|3a2c21|a05021|5f733a
Data|Formula Desk|wave|paper|e6ecf8|243454|375ba8|875786
Data|Connection Map|network|glass|14202b|ebfff9|7be4ba|7b9df2
Illustrated|Pencil Classroom|parts|paper|f6edd9|272929|65419c|9c5f31
Illustrated|Marker Room|flow|paper|f2f1e9|272f32|176c8b|b65c42
Illustrated|Paper Stacks|sequence|cards|472e48|fff1e7|ffbaaa|dbc4ff
Illustrated|Color Blocks|compare|cards|282046|fff1f9|ffa8db|f8d572
Illustrated|Comic Science|motion|cards|212657|eff3ff|ffe26b|ff8589
Illustrated|Botanical Notebook|cycle|paper|eef0df|273520|527842|a16648
Illustrated|Field Guide|cutaway|paper|eee5c9|352c22|92652b|3b766b
Illustrated|Ink & Lilac|network|paper|ede6f3|32233f|7950a7|b35a75
Illustrated|Story Panels|sequence|cards|2f2440|fff3e4|fbc687|b49bf4
Illustrated|Atlas Sketch|network|paper|e7ecdb|31392c|487753|a36738
Retro|Terminal Signal|flow|grid|0a1c15|e4ffe7|84f192|488977
Retro|Arcade Physics|motion|grid|221642|f7edff|ff8ed5|70dbff
Retro|CRT Dashboard|bars|grid|0f2024|e8fff8|70eac7|f2c66f
Retro|Synth Horizon|wave|stars|26143a|ffebff|fb7deb|879aff
Retro|Space Console|orbit|stars|141c36|e7f7ff|ffad70|6be4ff
Retro|Analog Meter|bars|paper|f0e3cf|3d2a23|a6512a|557f7b
Retro|Neon Circuit|network|grid|19122e|fbefff|ed8bff|5effda
Retro|VHS Lessons|compare|cards|242444|f3edff|ff919a|9eacff
Retro|Console Manual|sequence|paper|e4e5f0|29284b|6654ad|a64a65
Retro|Night Frequency|wave|stars|11192d|edf7ff|70cfff|ff9a71
Shorts|Quick Breakdown|parts|cards|171933|f4efff|bfa7ff|75e4f2
Shorts|Myth Check|compare|cards|2e1833|fff0fc|ffa0c0|b6a0ff
Shorts|This vs That|compare|glass|15283a|eff7ff|63e5dd|ffad8d
Shorts|Steps in Motion|sequence|cards|29233e|fff3fe|f7ac8f|bcb2ff
Shorts|Question Timer|cycle|grid|182634|f1f8ff|f8d773|7bcfe7
Shorts|Fact Stack|bars|cards|182832|ecfffc|8ae7ce|a3a9ff
Shorts|Focus Mode|motion|glass|1e2036|f5efff|c4acff|ffb27c
Shorts|Big Reveal|cutaway|stars|291b2b|fff2e9|ffb982|c68cf6
Shorts|Fast Timeline|sequence|grid|1c192e|f2efff|f7aaf5|70d9e3
Shorts|Visual Summary|network|paper|ece8fa|312b4d|6950ab|348174
"""

TEMPLATES = {}
for row in _STYLES.strip().splitlines():
    category, name, *style = row.split("|")
    slug = name.lower().replace(" & ", " ").replace(" ", "-")
    TEMPLATES[slug] = Template(slug, name, category, *style)


def template_catalog():
    return [asdict(template) for template in TEMPLATES.values()]
