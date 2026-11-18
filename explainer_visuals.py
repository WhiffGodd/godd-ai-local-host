"""Generate and animate illustrated shots for subjects outside the 3D library."""

from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
from math import cos, pi
import os
from pathlib import Path
import shutil
import subprocess

from PIL import Image, ImageOps


_ROOT = Path(__file__).resolve().parent / ".visual-engine"
_MODEL = "DreamShaper_8_pruned.safetensors"
_SETUP = "Custom topics need the local image model. See AI Video Studio setup in the README."
_STYLE = ("photorealistic editorial photograph, realistic proportions and materials, "
          "detailed surfaces, soft directional studio lighting, vertical composition, subject centered, "
          "one continuous image, clean lower third, no lettering")
_NEGATIVE = "toy, colored blocks, low poly, abstract shapes, icons, infographic, collage, captions, watermark, blurry"


class VisualUnavailable(RuntimeError):
    """A custom image generation error suitable for showing in the studio."""


@lru_cache(maxsize=8)
def _default_backend(executable):
    if os.name != "nt":
        return "cpu"
    try:
        result = subprocess.run([executable, "--list-devices"], capture_output=True, text=True, timeout=6,
                                check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        devices = [line.split("\t", 1) for line in result.stdout.splitlines()
                   if line.casefold().startswith("vulkan") and "\t" in line]
    except (OSError, subprocess.SubprocessError):
        return "cpu"
    if not devices:
        return "cpu"
    discrete = next((device for device, name in devices if "nvidia" in name.casefold()), None)
    diffusion = (discrete or devices[0][0]).lower()
    decoder = diffusion if discrete else "cpu"
    return f"diffusion={diffusion},te=cpu,vae={decoder}"


@dataclass(frozen=True)
class LocalVisualEngine:
    executable: str
    model: Path
    backend: str

    @classmethod
    def configured(cls):
        default = _ROOT / "runtime" / ("sd-cli.exe" if os.name == "nt" else "sd-cli")
        requested = os.environ.get("AI_VIDEO_IMAGE_CLI")
        executable = shutil.which(requested) if requested else (
            str(default) if default.is_file() else shutil.which("sd-cli"))
        default_model = _ROOT / _MODEL
        if not default_model.is_file():
            default_model = _ROOT / "DreamShaper8_LCM.safetensors"
        model = Path(os.environ.get("AI_VIDEO_IMAGE_MODEL", str(default_model))).expanduser()
        if not executable or not model.is_file():
            return None
        backend = os.environ.get("AI_VIDEO_IMAGE_BACKEND") or _default_backend(executable)
        return cls(executable, model.resolve(), backend)

    def generate(self, subject, scene, work, index):
        visual = scene.get("visual") or scene["caption"]
        prompt = f"{visual}. Main subject: {subject}. {_STYLE}"
        cutout = scene.get("cutout", False)
        if cutout:
            prompt = (f"{visual}. Photorealistic product photograph of one object only, entire object visible, "
                      "centered isolated object against a perfectly plain pure black background, "
                      "realistic materials, soft studio rim lighting, no text, no floor, no other objects.")
        shot = f"{subject}\n{visual}\n{index}"
        seed = int.from_bytes(sha256(shot.encode()).digest()[:4], "big") % (2**31 - 1)
        output = work / f"visual-{index}.png"
        lcm = "lcm" in self.model.name.casefold()
        command = [self.executable, "-m", str(self.model), "-p", prompt, "-n", _NEGATIVE,
                   "-W", "512" if cutout else "448", "-H", "512" if cutout else "768",
                   "--steps", "8" if lcm else "20", "--sampling-method", "lcm" if lcm else "euler_a",
                   "--cfg-scale", ("3" if cutout else "1.7") if lcm else "7",
                   "--seed", str(seed), "--backend", self.backend,
                   "--offload-to-cpu", "--vae-tiling", "-o", str(output)]
        if cutout:
            command[command.index("-n")+1] = (scene.get("avoid","")+
                ", several objects, duplicates, collection, set of objects, "+_NEGATIVE)
        try:
            with (work / "visual-engine.log").open("wb") as log:
                subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                               timeout=360 if self.backend == "cpu" else 180,
                               check=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            with Image.open(output) as picture:
                return picture.convert("RGB")
        except (OSError, subprocess.SubprocessError) as error:
            print(f"[AI Video] Image generation failed: {type(error).__name__}", flush=True)
            raise VisualUnavailable("The local image model could not render this shot. Free some GPU memory or check the image engine setup and try again.") from None


def visual_settings():
    ready = LocalVisualEngine.configured() is not None
    return {"custom_visuals": ready, "custom_visuals_setup": "" if ready else _SETUP}


class IllustratedShot:
    def __init__(self, picture, size, index, view):
        self.size = size
        self.image = ImageOps.fit(picture, size, Image.Resampling.LANCZOS)
        self.direction = -1 if index % 2 else 1
        self.detail = view == "detail"

    def frame(self, fraction, subtitle):
        progress = (1-cos(pi*fraction))/2
        width, height = self.size
        zoom = (1.12 if self.detail else 1.035) + .115*progress
        crop_w, crop_h = width/zoom, height/zoom
        x = (width-crop_w)*(.5 + .28*self.direction*(progress-.5))
        y = (height-crop_h)*(.47 + .18*(progress-.5))
        frame = self.image.transform(self.size, Image.Transform.EXTENT, (x,y,x+crop_w,y+crop_h), Image.Resampling.BICUBIC)
        if subtitle:
            layer, location = subtitle
            frame.paste(layer, location, layer)
        return frame
