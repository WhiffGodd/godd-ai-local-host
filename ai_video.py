"""Plan narrated motion graphics with a language model and render an MP4."""

import base64
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

from explainer_motion import FPS, HEIGHT, WIDTH, ScenePainter
from explainer_templates import TEMPLATES
from video_engine import FFMPEG_PATH


OLLAMA_MODEL = os.environ.get("AI_VIDEO_OLLAMA_MODEL", "qwen3:4b")
OLLAMA_URL = os.environ.get("AI_VIDEO_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
GEMINI_MODEL = os.environ.get("AI_VIDEO_GEMINI_MODEL", "gemini-3.1-flash-lite")
MAX_PROMPT = 1200
TARGET_SECONDS = 55
MIN_SECONDS = 50
MAX_SECONDS = 60
BICYCLE_PEDALS_PROMPT = "Explain how bicycle pedals turn the rear wheel through the crank, chain and rear cog."
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
DIAGRAMS = ("parts", "cutaway", "flow", "sequence", "cycle", "network", "orbit", "wave",
            "motion", "bars", "compare", "gears", "piston", "moon", "bicycle", "bicycle_drive")


class ExplainerError(RuntimeError):
    """A generation error suitable for displaying in the studio."""


def _object(**properties):
    return {"type": "object", "properties": properties, "required": list(properties)}


def _strings(minimum, maximum):
    return {"type": "array", "minItems": minimum, "maxItems": maximum, "items": {"type": "string"}}


_TEXT = {"type": "string"}
_SCHEMA = _object(title=_TEXT, hook=_TEXT, description=_TEXT, hashtags=_strings(2, 5), scenes={
    "type": "array", "minItems": 5, "maxItems": 6, "items": _object(
        heading=_TEXT, caption=_TEXT, narration=_TEXT, labels=_strings(2, 4),
        diagram={"type": "string", "enum": list(DIAGRAMS)},
    ),
})

_EXAMPLE = {
    "title": "How Bicycle Pedals Turn the Rear Wheel",
    "hook": "How does one pedal stroke turn the rear wheel?",
    "description": "Follow the motion from the pedals through the crank, chainring, chain, and rear cog to the rear wheel.",
    "hashtags": ["#Bicycle", "#Physics", "#Engineering"],
    "scenes": [
        {"heading": "Start at the pedal", "caption": "Your foot turns the crank.",
         "narration": "Press down on a pedal and watch the short arm it's attached to. That's the crank. Your foot pushes the end of that arm, and the arm turns around the axle in the middle.",
         "diagram": "bicycle", "labels": ["Pedal", "Crank"]},
        {"heading": "The chain starts moving", "caption": "The front chainring pulls the chain.",
         "narration": "The big toothed ring is attached to the crank, so they turn together. Its teeth catch the chain links one by one, and that pulls the upper run of the chain forward.",
         "diagram": "bicycle_drive", "labels": ["Chainring", "Chain"]},
        {"heading": "Power reaches the back", "caption": "The moving chain turns the rear cog.",
         "narration": "That same chain wraps around the smaller cog at the back. As the chain moves, it turns the cog. While you're pedaling, the cog drives the rear hub and the wheel turns with it.",
         "diagram": "bicycle_drive", "labels": ["Rear cog", "Rear hub"]},
        {"heading": "Why gear size matters", "caption": "A smaller rear cog turns more times per pedal revolution.",
         "narration": "A smaller rear cog needs less chain to go around once. So the same turn of the pedals spins it more times. That's why a higher gear can feel harder to push.",
         "diagram": "bicycle_drive", "labels": ["Chainring", "Rear cog"]},
        {"heading": "The whole motion", "caption": "Pedal, crank, chain, rear wheel.",
         "narration": "Next time you start from a stop, follow that first push. Your foot turns the crank, the crank pulls the chain, and the chain spins the rear wheel. That's how one pedal stroke gets you rolling.",
         "diagram": "bicycle", "labels": ["Pedals", "Rear wheel"]},
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
    template = payload.get("template")
    if not isinstance(template, str) or template not in TEMPLATES:
        raise ValueError("Choose a template from the library.")
    example = payload.get("example", False)
    if type(example) is not bool or (not example and len(prompt.strip()) < 8):
        raise ValueError("Describe the topic you want the video to explain.")
    voice = payload.get("voice", "expressive")
    if not isinstance(voice, str) or voice not in VOICE_STYLES:
        raise ValueError("Choose a narration style.")
    return {"prompt": prompt.strip(), "template": template, "example": example, "voice": voice}


def _validate_plan(plan):
    def text(value, limit):
        if not isinstance(value, str):
            raise ValueError("Expected text")
        value = " ".join(value.replace("<", "").replace(">", "").split())
        if not value:
            raise ValueError("Empty text")
        return value[:limit].strip()

    title = text(plan["title"], 95)
    hook = text(plan["hook"], 1000)
    if not 4 <= len(hook.split()) <= 11 or len(hook) > 82:
        raise ValueError("Expected a short opening hook")
    description = text(plan["description"], 900)
    hashtags = plan["hashtags"]
    if not isinstance(hashtags, list):
        raise ValueError("Expected hashtags")
    tags = list(dict.fromkeys(re.findall(r"#\w{2,35}", " ".join(text(tag, 40) for tag in hashtags[:5]))))
    if "#Shorts" not in tags:
        tags.append("#Shorts")
    scenes = plan["scenes"]
    if not isinstance(scenes, list) or not 5 <= len(scenes) <= 6:
        raise ValueError("Expected 5–6 scenes")
    clean = []
    for scene in scenes:
        diagram, labels = scene["diagram"], scene["labels"]
        if diagram not in DIAGRAMS or not isinstance(labels, list) or not 2 <= len(labels) <= 4:
            raise ValueError("Invalid diagram")
        narration = text(scene["narration"], 360)
        if len(narration.split()) < 5:
            raise ValueError("Missing narration")
        clean.append({"heading": text(scene["heading"], 44), "caption": text(scene["caption"], 96),
                      "narration": narration, "diagram": diagram,
                      "labels": [text(label, 18) for label in labels]})
    opening = {**clean[0], "heading": hook, "narration": hook, "opening": True}
    return title, f"{description}\n\n{' '.join(tags)}", [opening, *clean]


def plan_video(prompt, template, voice_style="expressive", target_words=150):
    delivery = {
        "expressive": "Sound like a friend explaining something cool. Use contractions, everyday words, and short sentences that feel natural aloud.",
        "energetic": "Sound like an excited friend showing a quick discovery. Use short, lively sentences and skip hype and filler.",
        "documentary": "Use a measured, clear delivery with concrete imagery.",
    }[voice_style]
    instructions = (
        "Plan a factually accurate educational vertical video in English. Return only the requested JSON. "
        "Write a 4 to 10 word hook, maximum 80 characters. Open immediately with a specific puzzle, "
        "surprising truth or relatable 'what if' that the video actually answers. Use no greeting, "
        "intro filler, clickbait or invented claim. The hook is spoken and shown before the scenes. "
        "Use 5 to 6 consecutive scenes. Pick up directly from the hook without repeating it, "
        "explain cause and effect, and end with the payoff and a complete answer. "
        f"Write about {target_words} spoken words in total, including the hook, for a {TARGET_SECONDS}-second video. "
        f"Write roughly {round((target_words - 8) / 5)} words of narration in each of five scenes. "
        "Use two or three complete sentences per scene and develop the answer with a concrete example or useful detail. "
        f"{delivery} "
        "Write the narration as one spoken story that happens to span several visuals. Let each scene pick up "
        "the thought from the previous one. Vary sentence length. Avoid repeated setup phrases, spoken headings "
        "and canned lines like 'Let's dive in' or 'Here's the kicker'. "
        "Headings and diagram labels must be short. Caption is one short sentence summarizing the narration. "
        "Choose diagrams to illustrate the actual concept. parts/cutaway show components; flow/sequence show steps; "
        "cycle shows recurrence; network shows relationships; orbit shows rotation; wave shows a signal; "
        "motion shows movement; bars/compare show contrasts. Use gears for meshing gears, piston for a crank "
        "driving a piston, moon for lunar phases, bicycle for a full side view of a bicycle, and bicycle_drive "
        "for a close-up of pedals driving a chain and rear cog. For bicycle drivetrain explanations start with "
        "bicycle and use bicycle_drive while explaining the moving parts. For moon, label Sun, Earth and Moon in "
        "that order. Treat shapes as schematic and avoid invented measurements. "
        "Follow provider safety rules. Do not give actionable instructions for harming people, "
        "building weapons, engineering dangerous pathogens, or exploiting computer systems. "
        f"Selected visual style: {template.name}. Use {template.diagram} when it fits, and vary other scenes."
    )
    key = os.environ.get("AI_VIDEO_GEMINI_API_KEY")
    try:
        if key:
            endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
            response = requests.post(endpoint, headers={"x-goog-api-key": key}, json={
                "systemInstruction": {"parts": [{"text": instructions}]},
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json", "responseJsonSchema": _SCHEMA,
                                     "maxOutputTokens": 3000},
            }, timeout=(5, 90))
            response.raise_for_status()
            result = "".join(part.get("text", "") for part in response.json()["candidates"][0]["content"]["parts"]
                             if not part.get("thought"))
        else:
            response = requests.post(f"{OLLAMA_URL}/api/chat", json={
                "model": OLLAMA_MODEL, "stream": False, "think": False, "format": _SCHEMA, "keep_alive": "1m",
                "options": {"temperature": 0.3, "num_predict": 2400, "num_ctx": 4096},
                "messages": [{"role": "system", "content": instructions}, {"role": "user", "content": prompt}],
            }, timeout=(4, 180))
            response.raise_for_status()
            result = response.json()["message"]["content"]
        title, description, scenes = _validate_plan(json.loads(result))
        # Keep the full bicycle visible at the hook and introduce the close-up
        # even when the model chooses an abstract scene for a drivetrain prompt.
        topic = f"{prompt} {title}"
        if re.search(r"\b(?:bicycles?|bikes?|cycles?)\b", topic, re.I) and re.search(
            r"\b(?:pedal\w*|drivetrain|chain\w*|sprockets?|crank\w*)\b", topic, re.I
        ):
            hook = "How does one pedal stroke turn the rear wheel?"
            scenes[0].update(diagram="bicycle", heading=hook, narration=hook)
            scenes[1].update(diagram="bicycle")
            if not any(scene["diagram"] == "bicycle_drive" for scene in scenes[2:]):
                detail = next((scene for scene in scenes[2:]
                               if re.search(r"\b(?:chain\w*|sprockets?|cogs?)\b", scene["narration"], re.I)),
                              scenes[2])
                detail.update(diagram="bicycle_drive")
        return title, description, scenes
    except requests.HTTPError as error:
        status = error.response.status_code
        if status == 429:
            raise ExplainerError("The AI provider reached its usage limit. Try again later.") from None
        if not key and status == 404:
            raise ExplainerError(f"Install the AI model first with ollama pull {OLLAMA_MODEL}.") from None
        raise ExplainerError("The AI provider could not generate a storyboard. Check its setup or try again.") from None
    except requests.RequestException:
        raise ExplainerError("Could not reach the AI model. Check that the configured provider is running.") from None
    except (ValueError, KeyError, TypeError, IndexError):
        raise ExplainerError("The AI returned an incomplete storyboard. Try a shorter, more specific prompt.") from None


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


def _continuous_narration(scenes, style, output):
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
        offset = 0
        for phrase in phrases[:-1]:
            offset += len(phrase) + separator_length
            boundaries.append(round(timings[offset].start * FPS))
        boundaries.append(math.ceil((len(samples) / rate + 0.25) * FPS))
        counts = [end - start for start, end in zip(boundaries, boundaries[1:])]
        if min(counts) < 1:
            raise ValueError("Invalid narration timing")

        pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2").tobytes()
        tail = round(boundaries[-1] * rate / FPS) - len(samples)
        with wave.open(str(output), "wb") as audio:
            audio.setparams((1, 2, rate, 0, "NONE", "not compressed"))
            audio.writeframes(pcm + bytes(tail * 2))
        return counts
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


def render_explainer(payload):
    template = TEMPLATES[payload["template"]]
    style = payload.get("voice", "expressive")
    example = payload["example"] or payload.get("prompt", "").strip().casefold() == BICYCLE_PEDALS_PROMPT.casefold()
    target_words = {"expressive": 160, "energetic": 175, "documentary": 150}[style]
    title, description, scenes = (_validate_plan(_EXAMPLE) if example else
                                  plan_video(payload["prompt"], template, style, target_words))
    with tempfile.TemporaryDirectory(prefix="godd_explainer_") as directory:
        work = Path(directory)
        audio_path = work / "narration.wav"
        for attempt in range(3):
            frame_counts = _continuous_narration(scenes, style, audio_path)
            if frame_counts is None:
                frame_counts = _scene_narration(scenes, style, work, audio_path)
            duration = sum(frame_counts) / FPS
            if 44 <= duration <= 67 or example or attempt == 2:
                break
            spoken_words = sum(len(scene["narration"].split()) for scene in scenes)
            estimated = round(spoken_words * TARGET_SECONDS / duration)
            if duration < 44:
                estimated = max(target_words + 25, estimated + 15)
            else:
                estimated = min(target_words - 20, estimated)
            target_words = min(230, max(90, estimated))
            title, description, scenes = plan_video(payload["prompt"], template, style, target_words)
        frame_counts, tempo = _fit_runtime(frame_counts)
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
            with (work / "ffmpeg.log").open("wb") as log:
                with subprocess.Popen(command, stdin=subprocess.PIPE, stderr=log) as encoder:
                    try:
                        for index, (scene, count) in enumerate(zip(scenes, frame_counts)):
                            painter = ScenePainter(template, scene, index, len(scenes))
                            for frame in range(count):
                                encoder.stdin.write(painter.frame(frame / count).tobytes())
                        encoder.stdin.close()
                        if encoder.wait(timeout=25):
                            raise ExplainerError("The animation could not be encoded. Try generating again.")
                    finally:
                        if encoder.poll() is None:
                            encoder.kill()
            return output, {"title": title, "description": description}
        except BaseException as error:
            Path(output).unlink(missing_ok=True)
            if isinstance(error, (OSError, subprocess.SubprocessError)):
                raise ExplainerError("The animation could not be encoded. Try generating again.") from None
            raise


def _fit_runtime(frame_counts):
    total = sum(frame_counts)
    if MIN_SECONDS * FPS <= total <= MAX_SECONDS * FPS:
        return frame_counts, 1.0
    # Use the closest limit so the voice changes speed only as much as needed.
    target = (MIN_SECONDS if total < MIN_SECONDS * FPS else MAX_SECONDS) * FPS
    tempo = total / target
    if not 0.76 <= tempo <= 1.25:
        raise ExplainerError("The narration missed 50–60 seconds. Generate again with a prompt that gives enough detail for a one-minute explanation.")
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
