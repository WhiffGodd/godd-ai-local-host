"""Plan narrated 3D explainers with a language model and render an MP4."""

import base64
from contextlib import nullcontext
from difflib import SequenceMatcher
from functools import lru_cache
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
from urllib.parse import urlsplit
import wave

import requests
import numpy as np

from cinematic_render import FPS, HEIGHT, WIDTH, CinematicRenderer, RendererUnavailable, Shot, caption_layer
from explainer_parts import part_mentions
from explainer_templates import GENERATED_TEMPLATE, MECHANISM_TEMPLATE, MOTION_TEMPLATE, TEMPLATES, VIEWS, matching_subjects
from explainer_visuals import IllustratedShot, LocalVisualEngine, VisualUnavailable, visual_settings
from mechanism_animation import PLAN_INSTRUCTIONS, mechanism_schema, parse_mechanism_rows
from motion_graphics import (
    MotionReel, STORYBOARD_INSTRUCTIONS, extract_cutout, motion_objects_schema, motion_plan_from_scenes,
)
from explainer_photos import find_photo
from bearing_mechanism import spacing_storyboard
from mechanism_3d import Mechanism3D, Mechanism3DShot
from narration_budget import compact_sentences, word_count
from sliding_latch import latch_mechanism, latch_storyboard, matches_latch
from procedural_scene import CURATED_STAGES, StageShot, stage_parts
from video_engine import FFMPEG_PATH


OLLAMA_MODEL = os.environ.get("AI_VIDEO_OLLAMA_MODEL", "qwen3:4b")
OLLAMA_URL = os.environ.get("AI_VIDEO_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MECHANISM_MODEL = "qwen3.5:9b"
GEMINI_MODEL = os.environ.get("AI_VIDEO_GEMINI_MODEL", "gemini-3.1-flash-lite")
MAX_PROMPT = 1200
TARGET_SECONDS = 55
MIN_SECONDS = 50
DEFAULT_MAX_SECONDS = 60
MAX_SECONDS = 120
VOICE_STYLES = {
    "expressive": ("en_US-amy-medium", 0.91, 0.96, 0.97),
    "energetic": ("en_US-amy-medium", 0.84, 0.91, 0.87),
    "documentary": ("en_US-lessac-medium", 0.97, 1.06, 1.02),
}
KOKORO_STYLES = {
    "expressive": ("af_heart", 0.99, 0.19),
    "energetic": ("af_bella", 1.10, 0.15),
    "documentary": ("am_michael", 0.96, 0.25),
}


class ExplainerError(RuntimeError):
    """A generation error suitable for displaying in the studio."""


def _object(**properties):
    return {"type": "object", "properties": properties, "required": list(properties)}


def _strings(minimum, maximum):
    return {"type": "array", "minItems": minimum, "maxItems": maximum, "items": {"type": "string"}}


_TEXT = {"type": "string"}
_SCHEMA = _object(title=_TEXT, hook=_TEXT, hook_view=_TEXT, description=_TEXT, hashtags=_strings(2, 5), scenes={
    "type": "array", "minItems": 5, "maxItems": 6, "items": _object(
        heading=_TEXT, caption=_TEXT, narration=_TEXT, view=_TEXT,
    ),
})

_EXAMPLE = {
    "title": "How Bicycle Pedals Turn the Rear Wheel",
    "hook": "How does one pedal stroke turn the rear wheel?",
    "hook_view": "wide",
    "description": "Follow the motion from the pedals through the crank, chainring, chain, and rear cog to the rear wheel.",
    "hashtags": ["#Bicycle", "#Physics", "#Engineering"],
    "scenes": [
        {"heading": "Start at the pedal", "caption": "Your foot turns the crank.",
         "narration": "Press down on a pedal and watch the short arm it's attached to. That's the crank. Your foot pushes the end of that arm, and the arm turns around the axle in the middle.",
         "view": "pedal-crank"},
        {"heading": "The chain starts moving", "caption": "The front chainring pulls the chain.",
         "narration": "The big toothed ring is attached to the crank, so they turn together. Its teeth catch the chain links one by one, and that pulls the upper run of the chain forward.",
         "view": "chain-drive"},
        {"heading": "Power reaches the back", "caption": "The moving chain turns the rear cog.",
         "narration": "That same chain wraps around the smaller cog at the back. As the chain moves, it turns the cog. While you're pedaling, the cog drives the rear hub and the wheel turns with it.",
         "view": "rear-hub"},
        {"heading": "Why gear size matters", "caption": "A smaller rear cog turns more times per pedal revolution.",
         "narration": "A smaller rear cog needs less chain to go around once. So the same turn of the pedals spins it more times. That's why a higher gear can feel harder to push.",
         "view": "chain-drive"},
        {"heading": "The whole motion", "caption": "Pedal, crank, chain, rear wheel.",
         "narration": "Next time you start from a stop, follow that first push. Your foot turns the crank, the crank pulls the chain, and the chain spins the rear wheel. That's how one pedal stroke gets you rolling.",
         "view": "wide"},
    ],
}

_LONG_EXAMPLE_SCENES = [
    {"heading": "Why a longer crank helps", "caption": "A longer lever gives your foot more turning force.",
     "narration": "Think of pushing a door near its hinge, then pushing it near the handle. The same push turns it more easily at the handle. A crank works on that same principle. The pedal is out at the end of the lever, away from the axle.",
     "view": "pedal-crank"},
    {"heading": "What happens when you coast?", "caption": "A freewheel lets the rear wheel turn without moving the pedals.",
     "narration": "On most bicycles, you can stop moving your feet while the bike keeps rolling. The freewheel lets the hub turn faster than the cog, so the rear wheel doesn't drag the chain around. Start pedaling again and the freewheel engages, sending power back to the wheel.",
     "view": "coasting"},
]

_TOASTER_PLAN = {
    "title": "What Makes a Toaster Pop?",
    "hook": "What actually makes your toast jump?",
    "hook_view": "wide",
    "description": "Watch bread drop into a cutaway toaster, then follow the carriage, heating wires, latch and spring through one complete cycle.",
    "hashtags": ["#Toaster", "#HowItWorks", "#Engineering"],
    "scenes": [
        {"view": "loading", "heading": "Load the slices", "caption": "Two slices slide onto the carriage.",
         "narration": "Drop two slices into the slots. They land on a metal carriage inside. That carriage is the movable rack that holds the bread upright and brings it back up when the cycle ends."},
        {"view": "latch", "heading": "Press the lever", "caption": "The latch holds the carriage down against the spring.",
         "narration": "Pressing the lever lowers the carriage and compresses the return spring. A latch holds the carriage down, so the spring stays squeezed even after you take your hand away."},
        {"view": "heating", "heading": "Heat the bread", "caption": "The wires heat up and radiate energy onto the bread.",
         "narration": "Now watch the heating wires on either side of the bread. Electric current makes the wires hot enough to glow. They radiate heat onto both faces of each slice."},
        {"view": "browning", "heading": "Brown the surface", "caption": "The bread dries and browns at the surface.",
         "narration": "As the surface dries and heats up, sugars react with amino acids in the bread. That is the Maillard reaction, which gives toast its brown color and roasted flavor."},
        {"view": "release", "heading": "Release the latch", "caption": "The heater switches off and the latch lets go.",
         "narration": "At the end of the cycle, the control cuts power to the heating wires and releases the latch. The spring is still compressed, but nothing holds the carriage down anymore."},
        {"view": "pop-up", "heading": "Lift the toast", "caption": "The return spring drives the carriage upward.",
         "narration": "The return spring expands and pushes the carriage back up. The toast rises with it and stops where you can reach it. The wires do the browning. The spring does the popping."},
    ],
}


def _ollama_models(timeout=2):
    try:
        response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=timeout)
        response.raise_for_status()
        models = response.json()["models"]
        return {item["name"] for item in models} if isinstance(models, list) else None
    except (requests.RequestException, ValueError, TypeError, KeyError):
        return None


def start_local_ollama():
    """Start the Windows Ollama server if the configured local endpoint is down."""
    if os.name != "nt" or os.environ.get("RENDER") or os.environ.get("AI_VIDEO_GEMINI_API_KEY"):
        return
    try:
        url = urlsplit(OLLAMA_URL)
        port = url.port
    except ValueError:
        return
    if (url.scheme != "http" or url.hostname not in ("localhost", "127.0.0.1", "::1")
            or url.username is not None or url.path or url.query or url.fragment or not port):
        return
    if _ollama_models(timeout=1) is not None:
        return
    executable = shutil.which("ollama")
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not executable and local_app_data:
        installed = Path(local_app_data) / "Programs" / "Ollama" / "ollama.exe"
        if installed.is_file():
            executable = str(installed)
    if not executable:
        print("[Ollama] Ollama is not installed. Install it to enable AI Video Studio prompts.")
        return

    try:
        log_path = Path(tempfile.gettempdir()) / "godd-ai-ollama.log"
        with log_path.open("ab") as log:
            process = subprocess.Popen(
                [executable, "serve"], env={**os.environ, "OLLAMA_HOST": url.netloc},
                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
            )
    except OSError as error:
        print(f"[Ollama] Could not start: {error}")
        return
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        if _ollama_models(timeout=1) is not None:
            print(f"[Ollama] Ready at {OLLAMA_URL}")
            return
        if process.poll() is not None:
            break
        time.sleep(0.25)
    print(f"[Ollama] Still unavailable at {OLLAMA_URL}. See {log_path} for startup details.")


def generation_settings():
    visuals = visual_settings()
    if os.environ.get("AI_VIDEO_GEMINI_API_KEY"):
        return {**visuals, "available": True, "provider": "Gemini"}
    installed = _ollama_models()
    if installed is not None and (OLLAMA_MODEL in installed or OLLAMA_MODEL + ":latest" in installed):
        return {**visuals, "available": True, "provider": "Ollama"}
    return {**visuals, "available": False, "setup": f"Start Ollama and run ollama pull {OLLAMA_MODEL} to enable custom prompts."}


def validate_generation(payload):
    prompt = payload.get("prompt", "")
    if not isinstance(prompt, str) or len(prompt) > MAX_PROMPT:
        raise ValueError(f"Keep the prompt under {MAX_PROMPT} characters.")
    template = payload.get("template", "auto")
    if not isinstance(template, str) or (template not in ("auto", GENERATED_TEMPLATE.id, MECHANISM_TEMPLATE.id)
                                         and template not in TEMPLATES):
        raise ValueError("Choose a template from the library.")
    example = payload.get("example", False)
    if type(example) is not bool or (not example and not prompt.strip()):
        raise ValueError("Describe the topic you want the video to explain.")
    if example and prompt.strip():
        raise ValueError("Generate the video from your prompt or run the bicycle demo with an empty prompt.")
    voice = payload.get("voice", "expressive")
    if not isinstance(voice, str) or voice not in VOICE_STYLES:
        raise ValueError("Choose a narration style.")
    max_seconds = payload.get("max_seconds", DEFAULT_MAX_SECONDS)
    if type(max_seconds) is not int or max_seconds not in (DEFAULT_MAX_SECONDS,90,MAX_SECONDS):
        raise ValueError("Choose a 60-, 90-, or 120-second maximum.")
    visual_style = payload.get("visual_style", "auto")
    if visual_style not in ("auto", "motion"):
        raise ValueError("Choose Reel motion or 3D cutaway.")
    return {"prompt": prompt.strip(), "template": template, "example": example, "voice": voice,
            "max_seconds": max_seconds, "visual_style": visual_style}


_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_COMMON_WORDS = frozenset("a an the to of you your that this what why how it does do is are can when with in and then".split())


def _distinct_opening(hook, narration):
    def words(sentence):
        return re.findall(r"[\w']+", sentence.casefold().replace("’", "'"))

    hook_words = [(line, words(line)) for line in _SENTENCE_END.split(hook)]
    lines = _SENTENCE_END.split(narration)
    for index, line in enumerate(lines):
        tokens = words(line)
        content = set(tokens) - _COMMON_WORDS
        repeated = False
        for hook_line, original in hook_words:
            original_content = set(original) - _COMMON_WORDS
            # A question can share vocabulary with the actual answer.
            same_delivery = line.endswith("?") == hook_line.endswith("?")
            similarity = SequenceMatcher(None, original, tokens, autojunk=False).ratio()
            shared = len(content & original_content)
            repeated = (tokens == original or (same_delivery and shared >= 3 and
                        (similarity >= .83 or shared / len(content | original_content) >= .78)))
            if repeated:
                break
        if not repeated and not (hook.endswith("?") and line.endswith("?")):
            return " ".join(lines[index:])
    return ""


def _validate_plan(plan, subject, max_scenes=6):
    def text(value, limit):
        if not isinstance(value, str):
            raise ValueError("Expected text")
        value = " ".join(value.replace("<", "").replace(">", "").split())
        if not value:
            raise ValueError("Empty text")
        return value[:limit].strip()

    title = text(plan["title"], 95)
    hook_lines = _SENTENCE_END.split(text(plan["hook"], 1000))
    hook = next((line for line in hook_lines if 4 <= len(line.split()) <= 25 and len(line) <= 160), "")
    if not hook:
        raise ValueError("Expected an opening hook under 160 characters")
    description = text(plan["description"], 900)
    hashtags = plan["hashtags"]
    if not isinstance(hashtags, list):
        raise ValueError("Expected hashtags")
    tags = list(dict.fromkeys(re.findall(r"#\w{2,35}", " ".join(text(tag, 40) for tag in hashtags[:5]))))
    if "#Shorts" not in tags:
        tags.append("#Shorts")
    scenes = plan["scenes"]
    if not isinstance(scenes, list) or not 5 <= len(scenes) <= max_scenes:
        raise ValueError("Unexpected scene count")
    clean = []
    for scene in scenes:
        view = scene["view"]
        if view not in VIEWS[subject]:
            raise ValueError("The view does not belong to the selected 3D subject")
        if len(scene["narration"])>2000:
            raise ValueError("A narration scene is too long")
        narration = text(scene["narration"], 2000)
        if len(narration.split()) < 5:
            raise ValueError("Missing narration")
        caption = text(scene["caption"], 96)
        if not clean:
            distinct = _distinct_opening(hook, narration)
            if not distinct:
                continue
            if distinct != narration or not _distinct_opening(hook, caption):
                caption = _SENTENCE_END.split(distinct, maxsplit=1)[0][:96].rstrip()
            narration = distinct
        heading = text(scene["heading"],44)
        if re.fullmatch(r"(?:first|second|third|fourth|fifth|sixth|seventh|eighth|step\s*\d+)[.!:]?",heading,re.I):
            heading = " ".join(caption.split()[:6]).rstrip(".")
        shot = {"heading": heading, "caption": caption, "narration": narration, "view": view}
        if subject == GENERATED_TEMPLATE.diagram:
            shot["visual"] = text(scene.get("visual") or caption, 225)
        if subject == MOTION_TEMPLATE.diagram:
            shot["objects"] = scene["objects"]
        clean.append(shot)
    if not clean:
        raise ValueError("The storyboard repeats the hook without explaining it")
    seen_phrases = set()
    for shot in clean[:-1]:
        words = re.findall(r"[a-z]+",shot["narration"].casefold())
        phrases = {tuple(words[index:index+8]) for index in range(len(words)-7)}
        if phrases and len(phrases & seen_phrases)/len(phrases)>.20:
            raise ValueError("The narration repeats whole explanations. Give each scene one new fact and reserve the recap for the last scene.")
        seen_phrases.update(phrases)
    if subject == "bearing":
        script = " ".join(shot["narration"] for shot in clean)
        if re.search(r"(?:cage|retainer)[^.!?]{0,90}(?:slower|faster|more slowly|more quickly)[^.!?]{0,25}than (?:the )?(?:steel )?balls\b",script,re.I):
            raise ValueError("The cage travels at the same orbital speed as the ball centres, and more slowly than the inner ring. Correct the cage-speed explanation.")
    hook_view = plan["hook_view"]
    if hook_view not in VIEWS[subject]:
        raise ValueError("The opening view does not belong to the selected 3D subject")
    opening = {"heading": hook, "narration": hook, "view": hook_view, "opening": True}
    if subject == GENERATED_TEMPLATE.diagram:
        opening["visual_subject"] = text(plan.get("visual_subject") or title, 130)
        opening["visual"] = text(plan.get("hook_visual") or clean[0]["visual"], 225)
    if subject == MOTION_TEMPLATE.diagram:
        opening["objects"] = plan["hook_objects"]
        motion_plan_from_scenes([opening,*clean])
    return title, f"{description}\n\n{' '.join(tags)}", [opening, *clean]


def _request_storyboard(prompt, instructions, schema, key, long_video, single_match, mechanism_model=None):
    if key:
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
        response = requests.post(endpoint, headers={"x-goog-api-key": key}, json={
            "systemInstruction": {"parts": [{"text": instructions}]},
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "responseJsonSchema": schema,
                                 "maxOutputTokens": 6000 if "hook_objects" in schema["properties"] else 3000},
        }, timeout=(5, 90))
        response.raise_for_status()
        result = "".join(part.get("text", "") for part in response.json()["candidates"][0]["content"]["parts"]
                         if not part.get("thought"))
    else:
        motion_story = "hook_objects" in schema["properties"]
        layout = all(name in schema["properties"] for name in ("parts","actions"))
        request_body = {
            "model": mechanism_model or OLLAMA_MODEL, "stream": layout, "think": False, "format": schema,
            "keep_alive": 0 if mechanism_model or any(name in schema["properties"] for name in
                                  ("visual_subject","assets","hook_objects")) else "5m",
            "options": {"temperature": 0.15 if layout else 0.3,
                        "num_predict": 1800 if layout else 4800 if motion_story else 3200 if long_video else 2400,
                        "num_ctx": 4096 if layout else 8192 if motion_story else 6144 if long_video or not single_match else 4096},
            "messages": [{"role": "system", "content": instructions}, {"role": "user", "content": prompt}],
        }
        started = time.monotonic()
        def send():
            return requests.post(f"{OLLAMA_URL}/api/chat",json=request_body,
                                 timeout=(4,90 if layout else 300),**({"stream":True} if layout else {}))
        try:
            response = send()
        except requests.ConnectTimeout:
            raise
        except requests.ConnectionError:
            start_local_ollama()
            response = send()
        if layout:
            chunks = []
            complete = False
            try:
                response.raise_for_status()
                for line in response.iter_lines():
                    if time.monotonic()-started>180:
                        raise requests.ReadTimeout("Animation planning exceeded its time budget")
                    if not line:
                        continue
                    event = json.loads(line)
                    if event.get("error"):
                        raise requests.HTTPError("The local model stopped while generating the layout",response=response)
                    chunks.append(event.get("message",{}).get("content",""))
                    if event.get("done"):
                        if event.get("done_reason")=="length":
                            raise ValueError("The part layout exceeded the response budget; use more compact rows")
                        complete = True
                        break
                if not complete:
                    raise requests.ConnectionError("The layout stream ended before completion")
                result = "".join(chunks)
            finally:
                response.close()
        else:
            response.raise_for_status()
            result = response.json()["message"]["content"]
    return result


def plan_video(prompt, template, voice_style="expressive", target_words=150, max_seconds=DEFAULT_MAX_SECONDS):
    long_video = max_seconds > DEFAULT_MAX_SECONDS
    target_seconds = TARGET_SECONDS + max_seconds - DEFAULT_MAX_SECONDS
    max_scenes = 8 if long_video else 6
    properties = {**_SCHEMA["properties"],
                  "scenes": {**_SCHEMA["properties"]["scenes"], "maxItems": max_scenes}}
    candidates = matching_subjects(prompt)
    choices = ([template] if template in (GENERATED_TEMPLATE, MECHANISM_TEMPLATE, MOTION_TEMPLATE) or template in candidates
               else candidates or [MECHANISM_TEMPLATE])
    toaster = TEMPLATES["pop-up-toaster"]
    if matches_latch(prompt) and choices in ([TEMPLATES["spring-loaded-latch"]],[MECHANISM_TEMPLATE]):
        template = TEMPLATES["spring-loaded-latch"]
        return template, *_validate_plan(latch_storyboard(),template.diagram,max_scenes)
    if choices == [toaster]:
        # The script and the cutaway need the same ordered steps for one continuous cycle.
        return toaster, *_validate_plan(_TOASTER_PLAN, toaster.diagram)
    if choices == [TEMPLATES["ball-bearing"]]:
        reviewed = spacing_storyboard(prompt,long_video)
        if reviewed:
            return choices[0], *_validate_plan(reviewed,"bearing",max_scenes)
    single_match = len(choices) == 1
    choices_by_id = {item.id:item for item in choices}
    ids = list(choices_by_id)
    views = list(dict.fromkeys(view for item in choices for view in VIEWS[item.diagram]))
    view_schema = {"type": "string", "enum": views}
    key = os.environ.get("AI_VIDEO_GEMINI_API_KEY")
    words_per_scene = round((target_words - 8) / (7 if long_video else 5))
    narration_schema = {**_TEXT, "description": f"About {words_per_scene} spoken words with concrete detail."}
    if not key:
        narration_schema.update(minLength=max(35,round(words_per_scene*2.7)),
                                maxLength=min(360,max(100,round(words_per_scene*6))))
    scene_properties = properties["scenes"]["items"]["properties"]
    custom = choices == [GENERATED_TEMPLATE]
    mechanism = choices == [MECHANISM_TEMPLATE]
    visual_mode = ("AI illustrations" if custom else "an animated 3D cutaway" if mechanism else
                   "motion graphics" if choices == [MOTION_TEMPLATE] else "3D animation")
    if custom:
        properties.update(visual_subject=_TEXT, hook_visual=_TEXT)
        scene_properties = {**scene_properties, "visual": _TEXT}
    if choices == [MOTION_TEMPLATE]:
        properties["hook_objects"] = motion_objects_schema()
        scene_properties = {**scene_properties,"objects":motion_objects_schema()}
    properties["scenes"]["items"] = _object(**{**scene_properties, "view": view_schema, "narration": narration_schema})
    properties["hook_view"] = view_schema
    schema = _object(template={"type": "string", "enum": ids}, **properties)
    coverage = " | ".join(f"{item.id} ({item.coverage}): {', '.join(VIEWS[item.diagram])}" for item in choices)
    visual_style = (
        ("A separate image model illustrates each shot. In visual_subject give a short, consistent physical "
         "description of the exact object or setting, including characteristic features, color and materials. "
         "In hook_visual and each visual field, describe what is visible in a single camera shot using concrete nouns. "
         "Specify the real part, its appearance and surroundings. Vary wide views and close-ups. Avoid diagrams, "
         "typography, abstract blocks and impossible cross-sections. Show only what that narration beat describes. "
         if custom else
         "Use the selected subject and only its available camera views. ") +
        "Set hook_view to the shot that makes the opening question visible. "
        "For each scene, set view to the exact part or action being narrated. Show how the details requested "
        "by the user work, in the order they asked for. Use the wide view when it establishes the whole object. "
        f"Subjects and their views: {coverage}"
    )
    if single_match and choices[0].diagram == "freewheel":
        visual_style += (" Establish with a wide shot, use cutaway to expose the pawls and ratchet ring, then "
                         "use engagement while describing how pedaling locks them together. Use coasting when "
                         "describing the pawls clicking past the teeth while the sprocket stands still.")
    if single_match and choices[0].diagram == "bearing":
        visual_style += (" Start and finish with wide views of the assembled working bearing. "
            "Use exploded once to introduce the separate components, explicitly saying they are separated for inspection. "
            "Use cage while explaining ball spacing, rolling-balls to show individual ball spin and travel, "
            "and cutaway to expose contact with the grooved races. The outer race is fixed, "
            "the inner race turns with the shaft, and the cage travels more slowly with the ball centres. "
            "Orange witness marks make each ball's own spin visible; they are illustrative markings. "
            "Show at least three different explanatory views. Keep the explanation focused on the user's question.")
        visual_style += (" PHYSICAL FACTS: The cage and ball CENTRES travel together at the SAME orbital speed. "
            "Each ball ALSO spins about its own centre. Do not compare cage speed to 'the balls' without distinguishing spin from orbital travel. "
            "The cage maintains gaps; the grooved races guide and carry load. It is not a straight line of balls. "
            "Give each scene one NEW explanatory fact. Avoid repeating the inner-ring, outer-ring and cage facts in every scene. "
            "Answer the opening question directly in the first explanatory sentence. Do not say 'that is the question', "
            "'watch this animation' or 'here is the secret'.")
    delivery = {
        "expressive": "Sound like a friend explaining something cool. Use contractions, everyday words, and short sentences that feel natural aloud.",
        "energetic": "Sound like an excited friend showing a quick discovery. Use short, lively sentences and skip hype and filler.",
        "documentary": "Use a measured, clear delivery with concrete imagery.",
    }[voice_style]
    instructions = (
        "Plan a factually accurate educational vertical video in English. Return only the requested JSON. "
        "Write a short, natural YouTube title that names the subject and gives viewers a reason to watch. "
        "Keep the title, narration and description faithful to the prompt and the mechanism. "
        "Use established causes for physical mechanisms. Keep the description focused on the topic. "
        f"If you mention the visuals, call them {visual_mode}. "
        "Write a single, standalone hook sentence of 4 to 10 words, maximum 80 characters. "
        "Start with one concrete surprise or a short curiosity question. Name a visible outcome and leave its cause open. "
        "Avoid claims about what the viewer has seen, extra setup sentences, and a second question. "
        "The hook is spoken and shown by itself before the scenes. "
        f"Use {'5 to 8' if long_video else '5 to 6'} consecutive scenes. Start scene one with the first new fact or visible action that answers the hook. "
        "Move directly to the first physical action or cause. Say the names of the physical parts as you explain what they do. "
        "Keep the question and setup out of the explanation. "
        "Explain cause and effect, then end with the payoff and a complete answer. "
        f"Write about {target_words} spoken words, including the hook, for a {target_seconds}-second video. "
        "The selected length is a maximum. A shorter complete explanation is valid. Do not add filler to reach the time limit. "
        f"Aim for {words_per_scene} spoken words per scene. Develop each beat with a visible cause-and-effect "
        "detail or a concrete example that directly answers the prompt. Finish every sentence. "
        f"{delivery} "
        "Write the narration as one spoken story that happens to span several visuals. Let each scene pick up "
        "the thought from the previous one. Vary sentence length. Avoid repeated setup phrases, spoken headings "
        "and canned lines like 'Let's dive in' or 'Here's the kicker'. "
        "Use the requested subject, question, level of detail and emphasis. If the prompt asks why something "
        "happens, answer that question directly in the title, hook and narration. Do not substitute a generic overview. "
        "Headings must name the part or change in two to six concrete words. Avoid headings like First or Second. "
        "Each caption is one short sentence summarizing the corresponding narration. "
        "Follow provider safety rules. Do not give actionable instructions for harming people, "
        "building weapons, engineering dangerous pathogens, or exploiting computer systems. "
        f"Vary the scenes to follow the narration. {visual_style}"
    )
    if mechanism:
        instructions += (" Explain one full cycle or complete cause-and-effect sequence in order. "
                         "Use concrete names of the parts that move, carry material or transfer energy, "
                         "and describe what triggers each change. "
                         "Describe each step in a way a cutaway side view can show. Avoid repeated steps.")
    if choices == [MOTION_TEMPLATE]:
        instructions += STORYBOARD_INSTRUCTIONS
    try:
        storyboard_model = None
        if not key and choices[0] in TEMPLATES.values():
            preferred = os.environ.get("AI_VIDEO_OLLAMA_STORYBOARD_MODEL",OLLAMA_MECHANISM_MODEL)
            if preferred in (_ollama_models() or ()):
                storyboard_model = preferred
        for attempt in range(2):
            try:
                result = _request_storyboard(prompt, instructions, schema, key, long_video, single_match,
                                             mechanism_model=storyboard_model)
                plan = json.loads(result)
                selected_template = choices_by_id[plan["template"]]
                if selected_template == toaster:
                    plan = _TOASTER_PLAN
                title, description, scenes = _validate_plan(plan, selected_template.diagram, max_scenes)
                return selected_template, title, description, scenes
            except (ValueError, KeyError, TypeError, IndexError) as error:
                if attempt:
                    raise
                instructions += (f" Previous validation failed: {error}. Rewrite the storyboard to correct this."
                                 " Return a complete storyboard using the specified fields and supplied view IDs."
                                 " Use one standalone hook sentence followed by at least five explanatory scenes.")
    except requests.HTTPError as error:
        status = error.response.status_code
        if status == 429:
            raise ExplainerError("The AI provider reached its usage limit. Try again later.") from None
        if not key and status == 404:
            raise ExplainerError(f"Install the AI model first with ollama pull {OLLAMA_MODEL}.") from None
        if not key and status >= 500:
            print(f"[Ollama] Storyboard request returned HTTP {status}.")
            raise ExplainerError("Ollama is reachable, but its model could not finish. Try again with the 1-minute option.") from None
        raise ExplainerError("The AI provider could not generate a storyboard. Check its setup or try again.") from None
    except requests.ReadTimeout:
        provider = "Gemini" if key else "Ollama"
        raise ExplainerError(f"{provider} took too long to write the storyboard. Try the 1-minute option.") from None
    except requests.RequestException:
        message = ("Could not reach Gemini. Check your internet connection and provider settings." if key else
                   f"Could not connect to Ollama. Open Ollama and check that {OLLAMA_MODEL} is installed, then try again.")
        raise ExplainerError(message) from None
    except (ValueError, KeyError, TypeError, IndexError):
        raise ExplainerError("The AI returned an incomplete storyboard. Try a shorter, more specific prompt.") from None


def _plan_mechanism(prompt, scenes, report_progress=None):
    if matches_latch(prompt):
        return latch_mechanism(len(scenes))
    key = os.environ.get("AI_VIDEO_GEMINI_API_KEY")
    mechanism_model = None
    if not key:
        installed = _ollama_models() or ()
        preferred = os.environ.get("AI_VIDEO_OLLAMA_MECHANISM_MODEL", OLLAMA_MODEL)
        mechanism_model = preferred if preferred in installed else OLLAMA_MODEL
    script = "\n".join(f"{index}. {scene['narration']}" for index, scene in enumerate(scenes) if index)
    brief = f"Topic: {prompt}\nNarration beats:\n{script}"
    schema = mechanism_schema(len(scenes))
    instructions = PLAN_INSTRUCTIONS
    try:
        for attempt in range(2):
            try:
                if attempt and report_progress:
                    report_progress("mechanism_retry")
                candidate = mechanism_model
                if attempt and not key:
                    alternate = OLLAMA_MODEL if candidate!=OLLAMA_MODEL else OLLAMA_MECHANISM_MODEL
                    if alternate in installed:
                        candidate = alternate
                raw = _request_storyboard(brief, instructions, schema, key, False, True, candidate)
                return parse_mechanism_rows(json.loads(raw), len(scenes))
            except requests.RequestException as error:
                status = getattr(getattr(error,"response",None),"status_code",None)
                print(f"[AI layout] Attempt {attempt+1}: {type(error).__name__}, HTTP {status}",flush=True)
                if attempt:
                    raise
                instructions += " Use a compact layout and only the necessary functional parts. Return the requested JSON only."
            except (ValueError, KeyError, TypeError, AttributeError, IndexError) as error:
                if attempt:
                    raise
                if isinstance(error, ValueError) and not isinstance(error, json.JSONDecodeError):
                    instructions += f" Fix this validation issue from the previous answer: {error}."
                instructions += (" Use simple geometry and exact part names in every action. "
                                 "Check that the geometry and motion fit the board and cover at least three distinct beats.")
    except requests.RequestException:
        raise ExplainerError("The local AI did not complete the part layout after two attempts. Check the AI connection and retry.") from None
    except (ValueError, KeyError, TypeError, AttributeError, IndexError):
        raise ExplainerError("The AI could not lay out a working mechanism. Try naming the parts or focusing on one cycle.") from None


@lru_cache(maxsize=1)
def _neural_voice(model):
    from piper import PiperVoice
    return PiperVoice.load(model)


def _voice_dir():
    default_dir = (Path(os.environ["LOCALAPPDATA"]) / "GoddAI" / "voices" if os.environ.get("LOCALAPPDATA")
                   else Path.home() / ".local" / "share" / "godd-ai" / "voices")
    return Path(os.environ.get("AI_VIDEO_VOICE_DIR", str(default_dir)))


@lru_cache(maxsize=1)
def _kokoro(model, voices):
    from kokoro_onnx import Kokoro
    from onnxruntime import InferenceSession, SessionOptions

    options = SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    session = InferenceSession(str(model), options, providers=["CPUExecutionProvider"])
    return Kokoro.from_session(session, str(voices))


def _estimated_cue_ratios(narration, mentions):
    words = len(narration.split())
    return [(len(narration[:position].split()) / words, part) for position, part in mentions]


def _subtitle_phrases(text):
    words = list(re.finditer(r"\S+", text))
    spans = []
    start = 0
    for index, word in enumerate(words):
        count = index - start + 1
        boundary = word.group().rstrip('”"').endswith((".", "!", "?", ",", ";", ":"))
        if count >= 6 or (count >= 3 and boundary) or index == len(words)-1:
            spans.append((words[start].start(), word.end()))
            start = index + 1
    if len(spans) > 1 and len(text[spans[-1][0]:].split()) == 1:
        spans[-2:] = [(spans[-2][0], spans[-1][1])]
    return [(start, text[start:end]) for start, end in spans]


def _continuous_narration(scenes, style, output, mentions):
    voice_dir = _voice_dir()
    model = voice_dir / "timed-kokoro-v1.0.onnx"
    voices = voice_dir / "timed-voices-v1.0.bin"
    if not model.is_file() or not voices.is_file():
        return None

    try:
        engine = _kokoro(model, voices)
        voice, speed, pause = KOKORO_STYLES[style]

        def phonemize(text):
            return engine.tokenizer.known(" ".join(engine.tokenizer.phonemize(text, lang="en-us").split()))

        separator = len(engine.tokenizer.known(" "))
        offset = 0
        phrases = []
        scene_chunks = []
        for scene in scenes:
            chunks = []
            split = _subtitle_phrases(scene["narration"])
            for index, (position, caption) in enumerate(split):
                voiced = caption
                if index == len(split)-1 and voiced[-1] not in ".!?":
                    voiced += "."
                phonemes = phonemize(voiced)
                if not phonemes:
                    raise ValueError("Missing pronunciation")
                chunks.append((position, caption, phonemes, offset))
                phrases.append(phonemes)
                offset += len(phonemes) + separator
            scene_chunks.append(chunks)

        transcript = " ".join(phrases)
        samples, rate, timings = engine.create_timed(
            transcript, voice, speed=speed, is_phonemes=True,
            continuous=True, sentence_pause=pause, clause_pause=0.07,
        )
        if len(timings) != len(engine.tokenizer.known(transcript)) or not len(samples):
            raise ValueError("Missing narration timings")

        # Visual cuts share the same continuous take and subtitle timeline.
        boundaries = [0, *(round(timings[chunks[0][3]].start * FPS) for chunks in scene_chunks[1:])]
        boundaries.append(math.ceil((len(samples) / rate + 0.25) * FPS))
        counts = [end - start for start, end in zip(boundaries, boundaries[1:])]
        if min(counts) < 1:
            raise ValueError("Invalid narration timing")

        cue_ratios, captions = [], []
        for scene, row, chunks, boundary, count in zip(scenes, mentions, scene_chunks, boundaries, counts):
            def ratio(seconds):
                return max(0., min(1., (seconds * FPS - boundary) / count))

            block = []
            for _, caption, phonemes, start in chunks:
                spoken = phonemes.rstrip(" .,!?:;…")
                last = start + max(0, len(spoken)-1)
                block.append((ratio(timings[start].start), ratio(timings[last].end), caption))
            captions.append(block)

            narration = scene["narration"]
            cues = []
            for (position, part), (estimate, _) in zip(row, _estimated_cue_ratios(narration, row)):
                chunk_position, _, phonemes, start = next(chunk for chunk in reversed(chunks) if chunk[0] <= position)
                prefix = narration[chunk_position:position].rstrip()
                if not prefix:
                    estimate = ratio(timings[start].start)
                else:
                    known = phonemize(prefix)
                    index = len(known) + separator
                    if phonemes.startswith(known) and index < len(phonemes):
                        estimate = ratio(timings[start+index].start)
                cues.append((estimate, part))
            cue_ratios.append(cues)

        pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2").tobytes()
        tail = round(boundaries[-1] * rate / FPS) - len(samples)
        with wave.open(str(output), "wb") as audio:
            audio.setparams((1, 2, rate, 0, "NONE", "not compressed"))
            audio.writeframes(pcm + bytes(tail * 2))
        return counts, cue_ratios, captions
    except (ImportError, OSError, ValueError, RuntimeError, KeyError, IndexError, wave.Error) as error:
        raise ExplainerError("Could not generate continuous narration. Check the Kokoro voice files or try again.") from error


def _voice_for_render(voice_name):
    voice_dir = _voice_dir()
    for name in dict.fromkeys((voice_name, "en_US-lessac-medium")):
        model = voice_dir / f"{name}.onnx"
        try:
            if model.is_file():
                return _neural_voice(str(model))
        except (ImportError, OSError, ValueError, RuntimeError):
            continue
    return None


def _speak(text, script, target, pace, opening, voice):
    if voice is not None:
        from piper import SynthesisConfig
        try:
            config = SynthesisConfig(length_scale=pace, noise_scale=0.62,
                                     noise_w_scale=0.92 if opening else 0.8)
            with wave.open(str(target), "wb") as audio:
                voice.synthesize_wav(text, audio, syn_config=config)
            with wave.open(str(target), "rb") as audio:
                if audio.getnframes():
                    return audio.getparams(), audio.readframes(audio.getnframes())
        except (OSError, EOFError, ValueError, wave.Error, RuntimeError):
            raise ExplainerError("The neural voice could not render this line. Try generating again.") from None
        raise ExplainerError("The neural voice returned empty audio. Try generating again.")

    script.write_text(text, encoding="utf-8")
    if os.name == "nt":
        # Pass paths as data. The narration never becomes PowerShell source.
        command = (
            "Add-Type -AssemblyName System.Speech; "
            "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            "$s.Rate=[int]$env:GODD_SPEECH_RATE; "
            "$s.SetOutputToWaveFile($env:GODD_SPEECH_WAV); "
            "$s.Speak([IO.File]::ReadAllText($env:GODD_SPEECH_TEXT)); $s.Dispose()"
        )
        encoded = base64.b64encode(command.encode("utf-16-le")).decode("ascii")
        args = ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded]
        env = {**os.environ, "GODD_SPEECH_WAV": str(target), "GODD_SPEECH_TEXT": str(script),
               "GODD_SPEECH_RATE": str(round((1 - pace) * 13))}
    else:
        engine = shutil.which("espeak-ng") or shutil.which("espeak")
        if not engine:
            raise ExplainerError("Install eSpeak NG on this server to generate narration.")
        args = [engine, "-v", "en-us", "-s", str(round(163 / pace)), "-p", "57" if opening else "49",
                "-f", str(script), "-w", str(target)]
        env = None
    try:
        subprocess.run(args, env=env, capture_output=True, check=True, timeout=35)
        with wave.open(str(target), "rb") as audio:
            return audio.getparams(), audio.readframes(audio.getnframes())
    except (OSError, EOFError, wave.Error, subprocess.SubprocessError):
        raise ExplainerError("Could not create the voiceover. Check the server's speech engine.") from None


def _part_schedule(cues, count, view):
    minimum = round(FPS * 1.3)
    scheduled = []
    for ratio, part in sorted(cues, key=lambda cue: cue[0]):
        frame = min(round(ratio * count), max(0, count - minimum))
        if not scheduled:
            scheduled.append((0 if frame < FPS else frame, part))
            continue
        last_frame, previous = scheduled[-1]
        if part == previous:
            continue
        if frame - last_frame >= minimum:
            scheduled.append((frame, part))
        elif part.view == view and previous.view != view:
            scheduled[-1] = (last_frame, part)
    return scheduled


def _subtitle_schedule(captions, count):
    for start, end, text in captions:
        first = min(count-1, max(0, round(start*count)))
        last = min(count, max(first+1, math.ceil(end*count)))
        yield first, last, text


def _shorten_narration(scenes, budget, subject):
    """Fit the spoken script without dropping scenes, changing shots or cutting audio."""
    def checked(rows):
        if len(rows)!=len(scenes) or word_count(rows)>budget:
            raise ValueError("The revised narration exceeds its word budget")
        plan = {"title":"Complete explanation","description":"Complete explanation.","hashtags":["#Shorts"],
                "hook":rows[0]["narration"],"hook_view":rows[0]["view"],"scenes":rows[1:]}
        if subject == MOTION_TEMPLATE.diagram:
            plan["hook_objects"] = rows[0]["objects"]
        if subject == GENERATED_TEMPLATE.diagram:
            plan["visual_subject"] = rows[0]["visual_subject"]
            plan["hook_visual"] = rows[0]["visual"]
        validated = _validate_plan(plan,subject,8)[2]
        if len(validated)!=len(scenes):
            raise ValueError("Keep every explanation step")
        # Keep all original geometry/scene data. Only narration and its short
        # caption change, then speech timing is regenerated for the new take.
        return [{**original,"narration":row["narration"],**({"caption":row["caption"]} if "caption" in row else {})}
                for original,row in zip(scenes,validated)]

    compact = compact_sentences(scenes,budget)
    if compact:
        try:
            return checked(compact)
        except (ValueError,KeyError,TypeError):
            pass
    body = scenes[1:]
    per_scene = max(5,(budget-len(scenes[0]["narration"].split()))//len(body))
    schema = _object(narrations={"type":"array","minItems":len(body),"maxItems":len(body),
        "items":{"type":"string","minLength":15,"maxLength":max(45,min(280,per_scene*5))}})
    instructions = ("Shorten an existing educational voiceover. Return only the requested JSON. "
        f"Return exactly {len(body)} narration strings in the original order, each at most {per_scene} words. "
        "Use one or two COMPLETE short sentences per scene. Preserve the physical cause, action and result of every step. "
        "Keep the part names, numbers, negations and scientific meaning. Do not invent facts or reverse relationships. "
        "Remove setup, filler and repetition. The final scene must finish the explanation. Do not repeat the opening hook. "
        "Keep the explanation non-actionable for harmful topics and follow provider safety rules.")
    brief = json.dumps({"opening_hook":scenes[0]["narration"],
        "steps":[{"heading":scene["heading"],"narration":scene["narration"]} for scene in body]})
    key = os.environ.get("AI_VIDEO_GEMINI_API_KEY")
    for attempt in range(2):
        try:
            raw = _request_storyboard(brief,instructions,schema,key,False,True,mechanism_model=OLLAMA_MODEL)
            lines = json.loads(raw)["narrations"]
            if len(lines)!=len(body) or any(not isinstance(line,str) or not re.search(r'[.!?]["\u201d\u2019]?$',line.strip()) for line in lines):
                raise ValueError("Use complete sentences and retain every scene")
            revised = [dict(scenes[0]),*[{**scene,"narration":line.strip()} for scene,line in zip(body,lines)]]
            return checked(revised)
        except (ValueError,KeyError,TypeError,requests.RequestException) as error:
            instructions += f" Previous revision failed: {type(error).__name__}. Keep within the word limits and finish every sentence."
    raise ExplainerError("The AI could not shorten the narration. Check the AI connection and retry.")


def render_explainer(payload, report_progress=None):
    def report(stage, percent=None):
        if report_progress:
            report_progress(stage, percent)

    template = {GENERATED_TEMPLATE.id: GENERATED_TEMPLATE, MECHANISM_TEMPLATE.id: MECHANISM_TEMPLATE}.get(
        payload["template"], TEMPLATES.get(payload["template"]))
    style = payload.get("voice", "expressive")
    max_seconds = payload.get("max_seconds", DEFAULT_MAX_SECONDS)
    long_video = max_seconds > DEFAULT_MAX_SECONDS
    target_seconds = TARGET_SECONDS + max_seconds - DEFAULT_MAX_SECONDS
    minimum = MIN_SECONDS if not long_video else 75
    report("storyboard")
    example = payload["example"]
    # A known mechanism must retain its actual moving model, including requests
    # from browsers that saved the old photo-motion default.
    reel_motion = (payload.get("visual_style") == "motion" and not example and template is None
                   and not matching_subjects(payload["prompt"]))
    if reel_motion:
        template = MOTION_TEMPLATE
    target_words = round({"expressive": 160, "energetic": 175, "documentary": 150}[style] * target_seconds / TARGET_SECONDS)
    if example:
        template = TEMPLATES["bicycle-drivetrain"]
        plan = _EXAMPLE
        if long_video:
            original = plan["scenes"]
            plan = {**plan, "scenes": [*original[:1], _LONG_EXAMPLE_SCENES[0], *original[1:-1],
                                       _LONG_EXAMPLE_SCENES[1], original[-1]]}
        title, description, scenes = _validate_plan(plan, template.diagram, 8 if long_video else 6)
    else:
        template, title, description, scenes = plan_video(payload["prompt"], template, style, target_words, max_seconds)
    custom = template == GENERATED_TEMPLATE
    animated = template.diagram == MECHANISM_TEMPLATE.diagram
    reviewed_bearing = template.diagram == "bearing" and bool(spacing_storyboard(payload["prompt"],long_video))
    image_engine = LocalVisualEngine.configured() if custom or reel_motion else None
    if (custom or reel_motion) and image_engine is None:
        raise ExplainerError(visual_settings()["custom_visuals_setup"])
    stage = CURATED_STAGES.get(template.diagram)
    custom_parts = stage_parts(stage) if stage else ()
    scene_source = "motion" if reel_motion else "illustrated" if custom else "cutaway" if animated else "library"
    with tempfile.TemporaryDirectory(prefix="godd_explainer_") as directory:
        work = Path(directory)
        audio_path = work / "narration.wav"
        if word_count(scenes)>target_words:
            report("revising")
            scenes = _shorten_narration(scenes,target_words,template.diagram)
        for attempt in range(4):
            report("narration")
            mentions = [part_mentions(template.diagram, scene["narration"], custom_parts) for scene in scenes]
            timing = _continuous_narration(scenes, style, audio_path, mentions)
            if timing is None:
                frame_counts, caption_ratios = _scene_narration(scenes, style, work, audio_path)
                cue_ratios = [_estimated_cue_ratios(scene["narration"], cues) for scene, cues in zip(scenes, mentions)]
            else:
                frame_counts, cue_ratios, caption_ratios = timing
            duration = sum(frame_counts) / FPS
            if duration<=max_seconds*1.12 and (long_video or duration>=minimum*.88 or example
                                             or reviewed_bearing or template.diagram=="toaster"):
                break
            if attempt==3:
                _fit_runtime(frame_counts,max_seconds)
                break
            if duration>max_seconds*1.12:
                # Use the measured voice rate rather than asking the model to
                # guess another full storyboard's length. Keep the same shots.
                budget = min(word_count(scenes)-1,round(word_count(scenes)*(max_seconds-4)/duration))
                budget = max(len(scenes[0]["narration"].split())+8*(len(scenes)-1),budget)
                report("revising")
                scenes = _shorten_narration(scenes,budget,template.diagram)
                continue
            spoken_words = sum(len(scene["narration"].split()) for scene in scenes)
            estimated = round(spoken_words * target_seconds / duration)
            if duration < minimum * .88:
                estimated = max(target_words + 25, estimated + 15)
            else:
                estimated = min(target_words - 20, estimated)
            target_words = min(340 if long_video else 230, max(90, estimated))
            report("revising")
            try:
                _, title, description, scenes = plan_video(payload["prompt"], template, style, target_words, max_seconds)
                if word_count(scenes)>target_words:
                    scenes = _shorten_narration(scenes,target_words,template.diagram)
            except ExplainerError:
                # The current take is already complete. Keep it if it can be
                # exported within the requested limit without truncating speech.
                _fit_runtime(frame_counts, max_seconds)
                break
        # A shorter complete explanation is valid when the user selects a 90-second maximum.
        frame_counts, tempo = _fit_runtime(frame_counts, max_seconds)
        total_frames = sum(frame_counts)
        audio_filter = "highpass=f=75,alimiter=limit=0.89:latency=1"
        if tempo != 1.0:
            seconds = sum(frame_counts) / FPS
            audio_filter = f"atempo={tempo:.8f},apad,atrim=duration={seconds:.6f},{audio_filter}"

        pictures = []
        mechanism = None
        mechanism_model = None
        motion_reel = None
        if reel_motion:
            report("motion")
            motion_plan = motion_plan_from_scenes(scenes)
            cutouts = {}
            photo_credits = []
            for index,asset in enumerate(motion_plan[0]):
                report("visuals",round(index*100/len(motion_plan[0])))
                if asset.kind != "object":
                    continue
                sourced = find_photo(asset.query or asset.name)
                credits_length = sum(len(credit) for credit in dict.fromkeys(photo_credits))
                if sourced and len(description)+credits_length+len(sourced[1])+100 < 4900:
                    cutouts[asset.name] = sourced[0]
                    photo_credits.append(sourced[1])
                    continue
                for attempt in range(2):
                    try:
                        picture = image_engine.generate(asset.name,{"visual":asset.description,"cutout":True,"avoid":asset.avoid},
                                                        work,index+attempt*1000)
                        cutouts[asset.name] = extract_cutout(picture)
                        break
                    except VisualUnavailable as error:
                        if attempt:
                            raise ExplainerError(str(error)) from None
            motion_reel = MotionReel(motion_plan,cutouts,scenes,(WIDTH,HEIGHT))
            if photo_credits:
                description += "\n\nPhoto credits\n"+"\n\n".join(dict.fromkeys(photo_credits))
        if animated:
            report("mechanism")
            mechanism = _plan_mechanism(payload["prompt"], scenes,report)
            try:
                mechanism_model = Mechanism3D(mechanism)
            except ValueError as error:
                raise ExplainerError(f"The AI's part shapes could not form a working 3D cutaway: {error}") from None
            parts = tuple(component.part for component in mechanism[0])
            # The model uses the script's part names. Highlight the part in the active action.
            cue_ratios = [_estimated_cue_ratios(scene["narration"],
                          part_mentions(template.diagram, scene["narration"], parts)) for scene in scenes]
        if custom:
            for index, scene in enumerate(scenes):
                report("visuals", index*100//len(scenes))
                try:
                    picture = image_engine.generate(scenes[0]["visual_subject"], scene, work, index)
                except VisualUnavailable as error:
                    raise ExplainerError(str(error)) from None
                pictures.append(picture)

        fd, output = tempfile.mkstemp(prefix="godd_ai_video_", suffix=".mp4")
        os.close(fd)
        command = [FFMPEG_PATH, "-y", "-v", "error", "-f", "rawvideo", "-pixel_format", "rgb24",
                   "-video_size", f"{WIDTH}x{HEIGHT}", "-framerate", str(FPS), "-i", "-",
                   "-i", str(audio_path), "-c:v", "libx264", "-threads", "2", "-preset", "veryfast",
                   "-crf", "21", "-pix_fmt", "yuv420p", "-af", audio_filter,
                   "-c:a", "aac", "-b:a", "96k",
                   "-movflags", "+faststart", output]
        try:
            report("rendering", 0)
            render_context = nullcontext() if custom or reel_motion else CinematicRenderer()
            with render_context as renderer, (work / "ffmpeg.log").open("wb") as log:
                if mechanism_model:
                    mechanism_model.upload(renderer)
                with subprocess.Popen(command, stdin=subprocess.PIPE, stderr=log) as encoder:
                    try:
                        rendered_frames = 0
                        last_percent = 0
                        previous_view = None
                        for beat, (scene, count, cues, captions) in enumerate(zip(scenes, frame_counts, cue_ratios, caption_ratios)):
                            view = scene["view"]
                            transition_from = previous_view
                            if view != previous_view:
                                action_start = rendered_frames / FPS
                                previous_view = view
                            opening = scene.get("opening", False)
                            offset = rendered_frames / FPS
                            if reel_motion:
                                shot = None
                            elif custom:
                                shot = IllustratedShot(pictures[beat], (WIDTH, HEIGHT), beat, view)
                            elif animated:
                                shot = Mechanism3DShot(mechanism_model,(WIDTH,HEIGHT),beat,view,count/FPS,offset)
                            elif stage:
                                shot = StageShot(stage, view, None, offset, beat=beat, duration=count/FPS)
                            else:
                                shot = Shot(template.diagram, view, renderer.size, offset=offset,
                                            action_start=action_start, duration=count/FPS,previous_view=transition_from)
                            if renderer is not None and shot is not None:
                                shot.camera_from = getattr(renderer,"last_camera",None)
                            schedule = iter(_part_schedule(cues, count, view))
                            pending = next(schedule, None)
                            focused_part = None
                            subtitles = iter(_subtitle_schedule(captions,count))
                            next_subtitle = next(subtitles,None)
                            subtitle, subtitle_end = None, 0
                            for frame in range(count):
                                if pending and pending[0] == frame:
                                    focused_part = pending[1]
                                    pending = next(schedule, None)
                                while next_subtitle and next_subtitle[0] <= frame:
                                    _, subtitle_end, text = next_subtitle
                                    subtitle = caption_layer(text,(WIDTH, HEIGHT),opening)
                                    next_subtitle = next(subtitles,None)
                                visible_subtitle = subtitle if frame < subtitle_end else None
                                fraction = frame/max(1, count-1)
                                if reel_motion:
                                    picture = motion_reel.frame(beat,fraction,visible_subtitle)
                                elif custom:
                                    picture = shot.frame(fraction, visible_subtitle)
                                else:
                                    picture = renderer.frame(shot, frame/FPS, focused_part, visible_subtitle)
                                encoder.stdin.write(picture.tobytes())
                                rendered_frames += 1
                                percent = rendered_frames * 100 // total_frames
                                if percent >= last_percent + 5 and percent < 100:
                                    report("rendering", percent)
                                    last_percent = percent
                        encoder.stdin.close()
                        report("finalizing")
                        if encoder.wait(timeout=25):
                            raise ExplainerError("The animation could not be encoded. Try generating again.")
                    finally:
                        if encoder.poll() is None:
                            encoder.kill()
            return output, {"title": title, "description": description, "template": template.name,
                            "duration": total_frames / FPS, "scene_source": scene_source,
                            "views": [scene["view"] for scene in scenes]}
        except BaseException as error:
            Path(output).unlink(missing_ok=True)
            if isinstance(error, RendererUnavailable):
                raise ExplainerError(str(error)) from None
            if isinstance(error, (OSError, subprocess.SubprocessError)):
                raise ExplainerError("The animation could not be encoded. Try generating again.") from None
            raise


def _fit_runtime(frame_counts, max_seconds=DEFAULT_MAX_SECONDS):
    total = sum(frame_counts)
    min_seconds = MIN_SECONDS if max_seconds == DEFAULT_MAX_SECONDS else 0
    if min_seconds * FPS <= total <= max_seconds * FPS:
        return frame_counts, 1.0
    # Use the closest limit so the voice changes speed only as much as needed.
    target = (min_seconds if total < min_seconds * FPS else max_seconds) * FPS
    tempo = total / target
    if not 0.76 <= tempo <= 1.25:
        raise ExplainerError(f"The narration could not fit the {max_seconds}-second length. Try a more focused prompt.")
    boundaries = [0]
    elapsed = 0
    for count in frame_counts:
        elapsed += count
        boundaries.append(round(elapsed * target / total))
    return [end - start for start, end in zip(boundaries, boundaries[1:])], tempo


def _speech_samples(params, samples):
    if params.sampwidth == 2 and samples:
        pcm = np.abs(np.frombuffer(samples,dtype="<i2").astype(np.int32))
        voiced = np.flatnonzero(pcm >= max(40,pcm.max()*.02))
        if len(voiced):
            margin = round(params.framerate*.027)
            first = max(0, int(voiced[0])//params.nchannels-margin)
            last = min(params.nframes, int(voiced[-1])//params.nchannels+margin+1)
            return first, last
    return 0, params.nframes


def _scene_narration(scenes, style, work, audio_path):
    voice_name, hook_pace, scene_pace, payoff_pace = VOICE_STYLES[style]
    voice = _voice_for_render(voice_name)
    frame_counts, captions = [], []
    with wave.open(str(audio_path), "wb") as audio:
        for index, scene in enumerate(scenes):
            opening = scene.get("opening", False)
            pace = hook_pace if opening else payoff_pace if index == len(scenes) - 1 else scene_pace
            total = 0
            chunks = _subtitle_phrases(scene["narration"])
            ranges = []
            for phrase_index, (_, text) in enumerate(chunks):
                params, samples = _speak(text, work / "line.txt", work / "line.wav", pace,
                                         opening and phrase_index == 0, voice)
                if not index and not phrase_index:
                    audio.setparams(params)
                if (params.nchannels, params.sampwidth, params.framerate) != (
                        audio.getnchannels(), audio.getsampwidth(), audio.getframerate()):
                    raise ExplainerError("Voiceover scenes used different audio formats.")
                width = params.sampwidth*params.nchannels
                first, last = _speech_samples(params,samples)
                ranges.append((total,total+last-first,text))
                # Keep natural sentence pauses while joining short subtitle phrases.
                if phrase_index == len(chunks)-1:
                    pause = .16 if opening else .32
                else:
                    pause = .19 if text.endswith((".", "?", "!")) else .055
                gap = round(params.framerate*pause)
                audio.writeframes(samples[first*width:last*width] + bytes(gap*width))
                total += last-first+gap
            frames = math.ceil(total*FPS/params.framerate)
            length = round(frames*params.framerate/FPS)
            audio.writeframes(bytes((length-total)*width))
            frame_counts.append(frames)
            captions.append([(first/length,last/length,text) for first,last,text in ranges])
    return frame_counts, captions
