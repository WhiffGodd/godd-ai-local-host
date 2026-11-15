"""Plan narrated 3D explainers with a language model and render an MP4."""

import base64
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
from explainer_templates import GENERATED_TEMPLATE, TEMPLATES, VIEWS, matching_subjects
from procedural_scene import COLORS, CURATED_STAGES, DIRECTIONS, MAX_OBJECTS, MOTIONS, POSES, RELATIONS, SHAPES, StageShot, read_actions, read_stage, stage_parts, storyboard_stage
from video_engine import FFMPEG_PATH


OLLAMA_MODEL = os.environ.get("AI_VIDEO_OLLAMA_MODEL", "qwen3:4b")
OLLAMA_URL = os.environ.get("AI_VIDEO_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
GEMINI_MODEL = os.environ.get("AI_VIDEO_GEMINI_MODEL", "gemini-3.1-flash-lite")
MAX_PROMPT = 1200
TARGET_SECONDS = 55
MIN_SECONDS = 50
DEFAULT_MAX_SECONDS = 60
MAX_SECONDS = 90
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
    if os.environ.get("AI_VIDEO_GEMINI_API_KEY"):
        return {"available": True, "provider": "Gemini"}
    installed = _ollama_models()
    if installed is not None and (OLLAMA_MODEL in installed or OLLAMA_MODEL + ":latest" in installed):
        return {"available": True, "provider": "Ollama"}
    return {"available": False, "setup": f"Start Ollama and run ollama pull {OLLAMA_MODEL} to enable custom prompts."}


def validate_generation(payload):
    prompt = payload.get("prompt", "")
    if not isinstance(prompt, str) or len(prompt) > MAX_PROMPT:
        raise ValueError(f"Keep the prompt under {MAX_PROMPT} characters.")
    template = payload.get("template", "auto")
    if not isinstance(template, str) or (template not in ("auto", GENERATED_TEMPLATE.id) and template not in TEMPLATES):
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
    if type(max_seconds) is not int or max_seconds not in (DEFAULT_MAX_SECONDS, MAX_SECONDS):
        raise ValueError("Choose a 60- or 90-second maximum.")
    return {"prompt": prompt.strip(), "template": template, "example": example, "voice": voice,
            "max_seconds": max_seconds}


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
        narration = text(scene["narration"], 360)
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
        clean.append({"heading": text(scene["heading"], 44), "caption": caption, "narration": narration, "view": view})
    if not clean:
        raise ValueError("The storyboard repeats the hook without explaining it")
    hook_view = plan["hook_view"]
    if hook_view not in VIEWS[subject]:
        raise ValueError("The opening view does not belong to the selected 3D subject")
    opening = {"heading": hook, "narration": hook, "view": hook_view, "opening": True}
    return title, f"{description}\n\n{' '.join(tags)}", [opening, *clean]


def _request_storyboard(prompt, instructions, schema, key, long_video, single_match):
    if key:
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
        response = requests.post(endpoint, headers={"x-goog-api-key": key}, json={
            "systemInstruction": {"parts": [{"text": instructions}]},
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "responseJsonSchema": schema,
                                 "maxOutputTokens": 3000},
        }, timeout=(5, 90))
        response.raise_for_status()
        result = "".join(part.get("text", "") for part in response.json()["candidates"][0]["content"]["parts"]
                         if not part.get("thought"))
    else:
        request_body = {
            "model": OLLAMA_MODEL, "stream": False, "think": False, "format": schema, "keep_alive": "5m",
            "options": {"temperature": 0.3, "num_predict": 3200 if long_video else 2400,
                        "num_ctx": 6144 if long_video or not single_match else 4096},
            "messages": [{"role": "system", "content": instructions}, {"role": "user", "content": prompt}],
        }
        try:
            response = requests.post(f"{OLLAMA_URL}/api/chat", json=request_body, timeout=(4, 300))
        except requests.ConnectTimeout:
            raise
        except requests.ConnectionError:
            start_local_ollama()
            response = requests.post(f"{OLLAMA_URL}/api/chat", json=request_body, timeout=(4, 300))
        response.raise_for_status()
        result = response.json()["message"]["content"]
    return result


def plan_video(prompt, template, voice_style="expressive", target_words=150, max_seconds=DEFAULT_MAX_SECONDS):
    long_video = max_seconds == MAX_SECONDS
    target_seconds = TARGET_SECONDS + max_seconds - DEFAULT_MAX_SECONDS
    max_scenes = 8 if long_video else 6
    properties = {**_SCHEMA["properties"],
                  "scenes": {**_SCHEMA["properties"]["scenes"], "maxItems": max_scenes}}
    candidates = matching_subjects(prompt)
    choices = [template] if template == GENERATED_TEMPLATE or template in candidates else candidates or [GENERATED_TEMPLATE]
    single_match = len(choices) == 1
    choices_by_id = {item.id:item for item in choices}
    ids = list(choices_by_id)
    views = list(dict.fromkeys(view for item in choices for view in VIEWS[item.diagram]))
    view_schema = {"type": "string", "enum": views}
    key = os.environ.get("AI_VIDEO_GEMINI_API_KEY")
    words_per_scene = round((target_words - 8) / (7 if long_video else 5))
    narration_schema = {**_TEXT, "description": f"About {words_per_scene} spoken words with concrete detail."}
    if not key:
        narration_schema.update(minLength=min(260, round(words_per_scene * 5.3)), maxLength=360)
    scene_properties = properties["scenes"]["items"]["properties"]
    properties["scenes"]["items"] = _object(**{**scene_properties, "view": view_schema, "narration": narration_schema})
    properties["hook_view"] = view_schema
    schema = _object(template={"type": "string", "enum": ids}, **properties)
    coverage = " | ".join(f"{item.id} ({item.coverage}): {', '.join(VIEWS[item.diagram])}" for item in choices)
    visual_style = (
        ("A separate step will build new 3D objects for this topic. Treat the views as camera directions: use "
         "wide for the whole scene, detail for a named object, and overhead for objects seen from above. "
         if choices == [GENERATED_TEMPLATE] else
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
    delivery = {
        "expressive": "Sound like a friend explaining something cool. Use contractions, everyday words, and short sentences that feel natural aloud.",
        "energetic": "Sound like an excited friend showing a quick discovery. Use short, lively sentences and skip hype and filler.",
        "documentary": "Use a measured, clear delivery with concrete imagery.",
    }[voice_style]
    instructions = (
        "Plan a factually accurate educational vertical video in English. Return only the requested JSON. "
        "Write a short, natural YouTube title that names the subject and gives viewers a reason to watch. "
        "Keep the title, narration and description faithful to the prompt and the mechanism. "
        "Use established causes for physical mechanisms. Keep the description focused on the topic and call the visuals 3D animation when describing them. "
        "Write a single, standalone hook sentence of 4 to 10 words, maximum 80 characters. "
        "Start with one concrete surprise or a short curiosity question. Name a visible outcome and leave its cause open. "
        "Avoid claims about what the viewer has seen, extra setup sentences, and a second question. "
        "The hook is spoken and shown by itself before the scenes. "
        f"Use {'7 to 8' if long_video else '5 to 6'} consecutive scenes. Start scene one with the first new fact or visible action that answers the hook. "
        "Move directly to the first physical action or cause. Say the names of the physical parts as you explain what they do. "
        "Keep the question and setup out of the explanation. "
        "Explain cause and effect, then end with the payoff and a complete answer. "
        f"Write about {target_words} spoken words, including the hook, for a {target_seconds}-second video. "
        f"Aim for {words_per_scene} spoken words per scene. Develop each beat with a visible cause-and-effect "
        "detail or a concrete example that directly answers the prompt. Finish every sentence. "
        f"{delivery} "
        "Write the narration as one spoken story that happens to span several visuals. Let each scene pick up "
        "the thought from the previous one. Vary sentence length. Avoid repeated setup phrases, spoken headings "
        "and canned lines like 'Let's dive in' or 'Here's the kicker'. "
        "Use the requested subject, question, level of detail and emphasis. If the prompt asks why something "
        "happens, answer that question directly in the title, hook and narration. Do not substitute a generic overview. "
        "Headings must be short. Each caption is one short sentence summarizing the corresponding narration. "
        "Follow provider safety rules. Do not give actionable instructions for harming people, "
        "building weapons, engineering dangerous pathogens, or exploiting computer systems. "
        f"Vary the scenes to follow the narration. {visual_style}"
    )
    try:
        for attempt in range(2):
            try:
                result = _request_storyboard(prompt, instructions, schema, key, long_video, single_match)
                plan = json.loads(result)
                selected_template = choices_by_id[plan["template"]]
                title, description, scenes = _validate_plan(plan, selected_template.diagram, max_scenes)
                return selected_template, title, description, scenes
            except (ValueError, KeyError, TypeError, IndexError):
                if attempt:
                    raise
                instructions += (" Return a complete storyboard using the specified fields and supplied view IDs."
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


def _plan_stage(prompt, scenes):
    def options(values):
        return {"type":"string", "enum":list(values)}

    def vector(low, high):
        return {"type":"array", "minItems":3, "maxItems":3,
                "items":{"type":"number", "minimum":low, "maximum":high}}

    schema = _object(objects={"type":"array", "minItems":2, "maxItems":MAX_OBJECTS, "items":_object(
        label=_TEXT, shape=options(SHAPES), color=options(COLORS), pose=options(POSES), motion=options(MOTIONS),
        position=vector(-2.5, 2.5), size=vector(.035, 2.65), relation=options(RELATIONS), anchor=_TEXT,
    )}, actions={"type":"array", "minItems":0, "maxItems":24, "items":_object(
        beat={"type":"integer", "minimum":0, "maximum":len(scenes)-1}, part=_TEXT,
        direction=options(DIRECTIONS), distance={"type":"number", "minimum":0, "maximum":1.8},
        turn={"type":"number", "minimum":-720, "maximum":720},
        start={"type":"number", "minimum":0, "maximum":1}, end={"type":"number", "minimum":0, "maximum":1},
    )})
    instructions = (
        "Build one coherent miniature 3D stage for this educational video. Return JSON objects only. "
        "Choose 4 to 9 recognizable parts or props that make the requested cause and effect visible. "
        "Compose the topic itself with meshes. A named, animated schematic is appropriate for an abstract topic. "
        "Use the exact names of important parts spoken in the narration as short labels. Give each object a distinct label. "
        "Coordinates are [x, y, z]: right, up, toward the camera. Keep most objects between x=-1.4 and 1.4, "
        "y=-0.8 and 1.4. Size is [x, y, z] before pose. For a cylinder the third size is its length; "
        "upright points that length up, across points right, and front points toward the camera. "
        "Use small thicknesses for lines and legs. Let small shapes form detailed objects. Use waves for periodic motion. "
        "Join pieces that belong together. For a piece stacked on or attached to another piece, use on-top, in-front, "
        "on-left, or on-right as its relation and the other object's exact label as anchor. Independent pieces use free and an empty anchor. "
        "Place internal parts in front of or beside the housing so they are visible in a cutaway. "
        "Arrange an opening wide view and leave room around the main objects. Color moving parts distinctly. "
        "The beats are numbered from zero. Use actions to CHOREOGRAPH each mechanism across the beats. "
        "Name the exact part and beat, then give its direction and distance from its current location, degrees of rotation around its center, "
        "and fractions start/end within the beat. For example within the same beat the input moves from 0.1 to 0.4, "
        "then the driven part moves from 0.4 to 0.85. Move covers away to reveal interiors; show contact then response. "
        "Actions persist into later beats. Attached children automatically follow their parent. Use still for keyed parts. "
        "Keep fixed parts still; for a static topic show the described change when appropriate, such as tilting one stack to demonstrate balance. "
        "Use only the given meshes and parameters. Return no code, paths, external assets, or actionable harmful details."
    )
    context = json.dumps({"topic":prompt, "beats":[{"beat":i, "narration":scene["narration"]}
                         for i, scene in enumerate(scenes)]}, ensure_ascii=False)
    key = os.environ.get("AI_VIDEO_GEMINI_API_KEY")
    try:
        result = _request_storyboard(context, instructions, schema, key, False, True)
        data = json.loads(result)
        stage = read_stage(data)
        return stage, "procedural", read_actions(data, stage, scenes)
    except (requests.RequestException, ValueError, TypeError, KeyError, IndexError):
        return storyboard_stage(scenes), "schematic", ()


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


def _continuous_narration(scenes, style, output, mentions):
    voice_dir = _voice_dir()
    model = voice_dir / "timed-kokoro-v1.0.onnx"
    voices = voice_dir / "timed-voices-v1.0.bin"
    if not model.is_file() or not voices.is_file():
        return None

    try:
        engine = _kokoro(model, voices)
        voice, speed, pause = KOKORO_STYLES[style]
        phrases = []
        for scene in scenes:
            text = scene["narration"].rstrip()
            if text[-1] not in ".!?":
                text += "."
            phonemes = engine.tokenizer.phonemize(text, lang="en-us")
            phrases.append(engine.tokenizer.known(" ".join(phonemes.split())))

        transcript = " ".join(phrases)
        samples, rate, timings = engine.create_timed(
            transcript, voice, speed=speed, is_phonemes=True,
            continuous=True, sentence_pause=pause, clause_pause=0.07,
        )
        if not all(phrases) or len(timings) != len(engine.tokenizer.known(transcript)) or not len(samples):
            raise ValueError("Missing narration timings")

        # Cut visuals at the next line's first phoneme. The audio stays in one take.
        separator_length = len(engine.tokenizer.known(" "))
        boundaries = [0]
        starts = [0]
        for phrase in phrases[:-1]:
            starts.append(starts[-1] + len(phrase) + separator_length)
            boundaries.append(round(timings[starts[-1]].start * FPS))
        boundaries.append(math.ceil((len(samples) / rate + 0.25) * FPS))
        counts = [end - start for start, end in zip(boundaries, boundaries[1:])]
        if min(counts) < 1:
            raise ValueError("Invalid narration timing")

        cue_ratios = []
        for scene, row, phrase, start, boundary, count in zip(scenes, mentions, phrases, starts, boundaries, counts):
            narration = scene["narration"]
            cues = []
            for (position, part), (estimate, _) in zip(row, _estimated_cue_ratios(narration, row)):
                prefix = narration[:position].rstrip()
                if not prefix:
                    cues.append((0., part))
                    continue
                phonemes = engine.tokenizer.phonemize(prefix, lang="en-us")
                known = engine.tokenizer.known(" ".join(phonemes.split()))
                index = len(known) + separator_length
                if phrase.startswith(known) and index < len(phrase):
                    frames = timings[start + index].start * FPS - boundary
                    estimate = max(0., min(1., frames / count))
                cues.append((estimate, part))
            cue_ratios.append(cues)

        pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2").tobytes()
        tail = round(boundaries[-1] * rate / FPS) - len(samples)
        with wave.open(str(output), "wb") as audio:
            audio.setparams((1, 2, rate, 0, "NONE", "not compressed"))
            audio.writeframes(pcm + bytes(tail * 2))
        return counts, cue_ratios
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


def render_explainer(payload, report_progress=None):
    def report(stage, percent=None):
        if report_progress:
            report_progress(stage, percent)

    template = GENERATED_TEMPLATE if payload["template"] == GENERATED_TEMPLATE.id else TEMPLATES.get(payload["template"])
    style = payload.get("voice", "expressive")
    max_seconds = payload.get("max_seconds", DEFAULT_MAX_SECONDS)
    long_video = max_seconds == MAX_SECONDS
    target_seconds = TARGET_SECONDS + max_seconds - DEFAULT_MAX_SECONDS
    minimum = MIN_SECONDS if not long_video else 75
    report("storyboard")
    example = payload["example"]
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
    stage, scene_source = CURATED_STAGES.get(template.diagram), "library"
    actions = ()
    if template == GENERATED_TEMPLATE:
        report("scene")
        stage, scene_source, actions = _plan_stage(payload["prompt"], scenes)
    custom_parts = stage_parts(stage) if stage else ()
    with tempfile.TemporaryDirectory(prefix="godd_explainer_") as directory:
        work = Path(directory)
        audio_path = work / "narration.wav"
        for attempt in range(3):
            report("narration")
            mentions = [part_mentions(template.diagram, scene["narration"], custom_parts) for scene in scenes]
            if scene_source == "schematic":
                mentions = [row or [(0, custom_parts[min(max(0,index-1),len(custom_parts)-1)])]
                            for index, row in enumerate(mentions)]
            timing = _continuous_narration(scenes, style, audio_path, mentions)
            if timing is None:
                frame_counts = _scene_narration(scenes, style, work, audio_path)
                cue_ratios = [_estimated_cue_ratios(scene["narration"], cues) for scene, cues in zip(scenes, mentions)]
            else:
                frame_counts, cue_ratios = timing
            duration = sum(frame_counts) / FPS
            if (minimum * .88 <= duration <= max_seconds * 1.12 or example or attempt == 2
                    or (long_video and attempt == 1 and duration <= max_seconds)):
                break
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
                if scene_source == "schematic":
                    stage = storyboard_stage(scenes)
                    custom_parts = stage_parts(stage)
                elif actions:
                    report("scene")
                    stage, scene_source, actions = _plan_stage(payload["prompt"], scenes)
                    custom_parts = stage_parts(stage)
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
            with CinematicRenderer() as renderer, (work / "ffmpeg.log").open("wb") as log:
                with subprocess.Popen(command, stdin=subprocess.PIPE, stderr=log) as encoder:
                    try:
                        rendered_frames = 0
                        last_percent = 0
                        previous_view = None
                        for beat, (scene, count, cues) in enumerate(zip(scenes, frame_counts, cue_ratios)):
                            view = scene["view"]
                            if view != previous_view:
                                action_start = rendered_frames / FPS
                                previous_view = view
                            opening = scene.get("opening", False)
                            caption = scene["heading"] if opening else scene["caption"]
                            offset = rendered_frames / FPS
                            if stage:
                                shot = StageShot(stage, view, caption_layer(caption,renderer.size,opening), offset,
                                                 actions=actions, beat=beat, duration=count/FPS)
                            else:
                                shot = Shot(template.diagram, view, renderer.size, caption, opening,
                                            offset=offset, action_start=action_start)
                            schedule = iter(_part_schedule(cues, count, view))
                            pending = next(schedule, None)
                            focused_part = None
                            for frame in range(count):
                                if pending and pending[0] == frame:
                                    focused_part = pending[1]
                                    pending = next(schedule, None)
                                encoder.stdin.write(renderer.frame(shot, frame/FPS, focused_part).tobytes())
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


def _scene_narration(scenes, style, work, audio_path):
    voice_name, hook_pace, scene_pace, payoff_pace = VOICE_STYLES[style]
    voice = _voice_for_render(voice_name)
    frame_counts = []
    with wave.open(str(audio_path), "wb") as audio:
        for index, scene in enumerate(scenes):
            opening = scene.get("opening", False)
            pace = hook_pace if opening else payoff_pace if index == len(scenes) - 1 else scene_pace
            params, samples = _speak(scene["narration"], work / "line.txt", work / "line.wav", pace, opening, voice)
            if not frame_counts:
                audio.setparams(params)
            if (params.nchannels, params.sampwidth, params.framerate) != (
                    audio.getnchannels(), audio.getsampwidth(), audio.getframerate()):
                raise ExplainerError("Voiceover scenes used different audio formats.")
            pause = 0.16 if opening else 0.32
            frames = math.ceil((params.nframes / params.framerate + pause) * FPS)
            padding = round(frames * params.framerate / FPS) - params.nframes
            audio.writeframes(samples + bytes(padding * params.sampwidth * params.nchannels))
            frame_counts.append(frames)
    return frame_counts
