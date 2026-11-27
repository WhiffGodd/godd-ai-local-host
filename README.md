# ⚡ godd ai

> Turn long videos into viral TikToks, Reels & Shorts with AI — **100% Free Forever**.  
> The free, open alternative to **Klap.app** and **Opus Clip**.

---

## ✨ Features

- **🎯 AI Virality Engine**: Analyzes transcripts and audio dynamics to detect the highest-retention moments (curiosity hooks in the first 3 seconds, emotional spikes, punchlines, and high-energy laughter).
- **📱 Smart 9:16 Auto-Reframing**: Converts standard horizontal 16:9 YouTube videos and live streams into flawless vertical shorts (Supports *Smart Center Crop*, *Podcast Background Blur*, and *Letterbox Fit*).
- **🔥 Dynamic Animated Karaoke Subtitles**:
  - **Hormozi Style**: Bold yellow/green words with thick black stroke.
  - **MrBeast Style**: High-energy cyan and orange text with animated rotation.
  - **Cyber Glow**: Futuristic neon green aura.
  - **Minimal Clean**: Crisp white text in translucent capsules.
  - Auto-generated contextual emojis (`💰`, `🤯`, `🔥`, `🚀`, `💡`).
- **📱 Smartphone Studio Preview**: Interactive 9:16 mobile mockup with real-time word-by-word karaoke synchronization, scrubber, and video playback.
- **⚡ Dual Export Modes**:
  - **Client-Side Instant Export**: Direct in-browser recording via WebCodecs/Canvas to WebM/MP4 with zero server waiting queues.
  - **Server-Side FFmpeg Render**: Native 1080x1920 60fps MP4 encoding powered by `imageio-ffmpeg`.
- **📄 SRT Subtitle & Script Export**: Download `.srt` subtitle tracks or copy the full hook and script in one click.
- **🚫 100% Free & No Watermarks**: No credit cards, no subscriptions, and no branding watermarks.

---

## Run locally

Install Git, Python 3.11 or 3.12, and Node.js 22 or later. Clone the local
edition, then install the Python dependencies in a virtual environment.

```sh
git clone https://github.com/WhiffGodd/godd-ai-local-host.git
cd godd-ai-local-host
python -m venv .venv
```

Use `python3 -m venv .venv` if your system uses the `python3` command.

On Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe server.py
```

On macOS and Linux:

```sh
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python server.py
```

Open [http://localhost:8080](http://localhost:8080), paste a YouTube link, and
select a clip to preview and download. CPU rendering works. The first export
with automatic subtitles downloads the speech model.

---

## 🛠️ Tech Stack

- **Backend**: Python 3.12, multi-threaded HTTP server, `yt-dlp`, `youtube-transcript-api`, `imageio-ffmpeg`.
- **Frontend**: Vanilla JavaScript (ES6+), HTML5 Canvas 2D engine, MediaRecorder API, CSS3 Glassmorphism with Plus Jakarta Sans & Space Grotesk fonts.


## Clip subtitles and audio

Clip Studio checks YouTube captions first. When they are missing, it transcribes
the audio to find complete spoken passages. Analysis runs in the background with
a progress display and can be reconnected with **Check scan status**.

Use **Automatic** to scan an ordinary recording. For recordings longer than
30 minutes without captions, it scans six four-minute sections across the full
timeline. **Choose a time range** scans a specific section, including hours into
a long stream. **Recent live footage** saves up to the selected length from the
available live replay. If a stream provides too little replay, it records the
next three minutes. Stream access, replay availability, and clear speech are
required. Live clip times refer to the saved window, which remains available for
preview, thumbnails, download, and YouTube upload for about an hour.

Hindi captions are automatically shown in English letters in the preview,
downloaded SRT files, and rendered clips. The original speech and caption
timing stay the same.

Install dependencies with `python -m pip install -r requirements.txt`, then run
`python server.py`. FFmpeg must support the `subtitles` filter (the Docker image
and bundled imageio-ffmpeg build do). On Linux, install a font covering the spoken
language; the Docker image includes Latin and Devanagari fonts.

Exports burn in available source captions. If none are supplied, faster-whisper
transcribes the selected export audio with automatic language detection and word
timestamps. Its first use downloads the `small` multilingual model and may take longer; set
`WHISPER_MODEL=tiny` for lower memory use. Missing recognition dependencies or
subtitle rendering errors are reported instead of silently exporting without
requested captions. Select subtitles **Off** to disable captions.

Each MP4 contains one selected audio stream, preferring a rendition marked
original over a dubbed track. Audio and video seek to the same clip start; audio
resampling corrects timestamp drift. Captions and SRT exports use clip-relative
timing without an automatic lead. This prevents extra-track duplication; voices
or echoes already mixed into a single source track require separate audio
restoration. Existing lip-sync errors in the source are not automatically inferred.


## Complete answer boundaries

Clip selection looks for up to five standalone excerpts between 60 and 90
seconds. When none fit, a clearly bounded exchange can run up to 2 minutes.
The selector uses transcript and chapter cues to find endings, so preview
the result before exporting. Manual trims apply to previews and exports.


## YouTube download access

Install `yt-dlp[default]` from requirements and Node.js 22+ (Node 24 is bundled
in the Docker image). The app enables Node and the matching EJS package for
YouTube extraction. A YouTube rate limit or sign-in block is reported before
rendering; subtitle changes cannot resolve it.

For a local authenticated session, explicitly set `YOUTUBE_COOKIE_BROWSER=chrome`
before launching the server. Chrome's Windows encryption can prevent yt-dlp
from reading its cookies. Alternatively, set `YOUTUBE_COOKIE_FILE` to the absolute
path of a YouTube-only Netscape cookies file kept on your computer. Do not share
that file, paste it into chat, or commit it. Cookie files take precedence over
browser extraction. Authentication may still be rate limited by YouTube.


### Local server and request reuse

Only one local server may own the listening port on Windows. Stop the existing
server before restarting after backend changes; `/healthz` reports the active
backend version and caption renderer. This prevents a new frontend from calling
an older renderer that is still running in memory.

YouTube extraction results are shared for five minutes between metadata,
transcript, and export requests, including equivalent `youtu.be` and watch URLs.
After a YouTube access block, the app pauses equivalent extraction attempts for
one minute instead of immediately repeating them through every fallback.


## Speech-matched export captions

Automatic exports now render the selected video/audio clip first, recognize its
actual local audio, then burn styled captions while copying that audio unchanged.
This gives recognition and output the same zero-based clock. Estimated preview
words and translated source tracks are not used as automatic export captions.
The default recognition model is multilingual `small`; `WHISPER_LANGUAGE` may
optionally force a spoken language, otherwise detection is automatic. Recognition
uses transcription, not translation. Larger models take longer on CPU.

The downloaded clip's measured words are returned to the site preview and SRT
export. Original timed words retain their real endpoints; preview phrases no
longer persist through artificial hold intervals. Speech recognition can still
make mistakes, especially with overlapping speakers, accents, and mixed languages.


## Public Render deployment (free demo)

The `render.yaml` Blueprint deploys the Docker service on Render Free. It serves
the site and API from the same public domain. Deploy from the `main` branch of
`https://github.com/WhiffGodd/godd-ai` using Render's Docker runtime and health
check `/healthz`. The deployed health version is `1.3.0`.

The free profile uses multilingual Whisper `base`, one CPU thread and one export
at a time. This uses less memory than the local `small` model, with a tradeoff in
recognition accuracy. Exports run as bounded background jobs; the browser polls
status instead of holding a render request open. Temporary results expire after
30 minutes and are lost on restart. The speech model and Node runtime are bundled
in the image. Local videos, browser cookies and `.env` files are excluded.

Render Free sleeps on idle, has limited memory/CPU, and is suitable for a public
demo rather than dependable production rendering. YouTube can also block cloud
hosting IPs. A successful web deployment does not guarantee access to every
YouTube video. Personal browser cookies are never included in deployment.

To publish: connect Render, select the existing `godd-ai` service and deploy the
latest `main` commit, or create a Blueprint from the repository. Keep the Free
instance selected. Share the service's assigned HTTPS URL after `/healthz` shows
version `1.3.0` and a browser export has been verified.


### YouTube playback verification on Render

The image includes bgutil-ytdlp-pot-provider 2.0.2 and its matching Node script,
as recommended in yt-dlp's PO Token Guide. It runs on demand during extraction,
then exits before encoding and speech recognition. Mobile-web, Safari and
embedded playback clients are configured, and FFmpeg preserves the selected
stream's HTTP playback headers. No personal account cookies are bundled.

Playback verification can improve access but cannot guarantee access from a
blocked datacenter IP or to a video requiring sign-in. Treat a download as
verified only after the affected video's export succeeds on the deployed host.


### Blocked-video upload alternative

When YouTube blocks an export, the error dialog offers **Upload original video
and retry**. Choose the same original video (up to 1 GB). Uploads use 4 MB chunks
and stream to temporary storage; the visitor does not need a local backend.
The selected start/end, layout and subtitle style stay the same. Rendering reads
that uploaded source directly and recognizes its clip audio without contacting
YouTube. Uploads are identified by random tokens, expire after one hour, and
are lost if the free service restarts. Only use videos you are allowed to upload.
This is an alternative source path, not a claim that YouTube's IP block is removed.

## AI Mechanism Videos

Open **AI Mechanism Videos** from the main navigation. Describe what to explain and click
**Generate video**. The default **Working mechanisms** mode selects a matching 3D model.
Clicking a library card selects that model and opens its preview in one step.
The site uses working 3D models and animated 3D cutaways throughout. Custom
cutaways use solid part profiles with bevelled edges, tubes and helical springs,
rendered with the same lighting, materials and shadows as the scene library.
Part names and subtle surface highlights identify the narration's subject without
pointer lines. Camera changes ease between scenes and do not jump when a new
part is named within the same shot.
Known mechanism prompts keep their working model even if a browser saved the old
photo-motion setting. The ball bearing has grooved races, a pocketed cage,
individually spinning balls, rotating witness marks, and cutaway and exploded
inspection views. Its outer race stays fixed while the inner race drives rolling
motion. Camera and inspection transitions preserve the running mechanism's time.
Prompts about bearing-ball spacing use a reviewed sequence tied to these parts,
including the distinction between ball spin, ball-centre travel, and cage motion.
Questions about other bearing topics retain the AI storyboard workflow.
The Spring-Loaded Sliding Latch also has a reviewed five-part layout and a
complete retract-and-return sequence. Its narration and geometry do not require
AI planning. The bolt, handle, and spring endpoint remain connected throughout.
Other custom layouts try the smaller configured local model first, then a
bounded alternative attempt. Layout responses stream with a separate planning
time budget, independently of the maximum video length.
When `qwen3.5:9b` is already installed, modeled topics use it for storyboard
writing and release it before rendering. Otherwise they use the configured
`AI_VIDEO_OLLAMA_MODEL`. Set `AI_VIDEO_OLLAMA_STORYBOARD_MODEL` to choose another
installed storyboard model. Narration validation rejects repeated explanations
and a known ambiguity between bearing-ball spin and the cage's orbital motion.

The legacy photo API mode finds photographic objects or creates images locally,
then animates them independently over colored backgrounds with changing headlines,
smooth entrances and exits, and timed subtitles. It reuses the same objects across
steps so their appearance stays consistent. AI video exports run at 30 frames per second.
This style uses layered photographic assets. Check generated object details and
the explanation before publishing. The local image engine is required. Its first
use also downloads the small U2NetP foreground model from the
[rembg project](https://github.com/danielgatis/rembg) into `.visual-engine`.
Photographs are selected from Wikimedia Commons using public-domain, CC0 or
attribution-only license metadata. Source and license credits, including the
background-removal and animation changes, are added to the video's description.
Heat, airflow, light, force and electricity use animated overlays.

Choose **Working mechanisms** to use modeled mechanisms.
The AI picks a matching 3D subject and chooses the shot for
each part of your explanation. For topics outside the library, the AI plans a
cutaway with labeled parts and moves them through each stage of the explanation.
The generated 3D cutaway is an AI-designed illustration, so check the arrangement and motion before
publishing an educational video. Click a library card to select and preview its model.
Image workflows remain available to legacy API clients. The studio's normal
generation flow uses animated geometry. The Pop-up Toaster scene follows a full cycle in 3D, including loading,
heating, latch release, and the spring pushing the toast back up. The library
also includes other mechanisms, lunar phases,
prism refraction, sound and octaves, and the water cycle. Mechanism scenes can
expose internal parts in cutaway. The studio
creates a short English script, opens with a spoken and on-screen hook, and
renders a narrated 720 × 1280 MP4 with a 25-, 60-, 90-, or 120-second maximum. Follow the
preparation stages and watch the finished video in the preview. Pick Friendly,
Energetic, or Documentary to change the delivery. Generated videos are temporary,
so download a copy before closing the studio.

Prompts can contain up to 12,000 characters. Describe the parts, their connections,
the order of events and which parts stay fixed. The planner receives the entire
prompt with a context budget that grows for longer instructions. Layouts use
typed part and action objects, with validation and a bounded retry.

The **Electric circuit** example selects the 25-second option and a reviewed
battery–switch–bulb model. The contacts physically close before current appears;
opening them stops the current and lets the filament cool. Blue markers represent
electron drift from negative to positive through the external circuit. Orange
markers represent conventional current in the opposite direction. Marker size and
speed are exaggerated for visibility; the model is qualitative rather than a
circuit solver. This distinction follows [OpenStax's explanation of electrical
current](https://openstax.org/books/university-physics-volume-2/pages/9-1-electrical-current).
Other electrical prompts can use native copper wire, battery, bulb, LED, resistor,
capacitor, coil, terminal, switch, relay and motor geometry. Persistent current
actions, filament glow and rotor motion are available to the planner. AI-planned
connections and behavior still need review in the preview before publishing.
Electrical components use manufactured 3D models: a cylindrical battery with
polarity marks and metal contacts, an electrolytic capacitor with a marked sleeve,
scored vent, rubber bung and radial leads, a banded axial resistor, glass bulb and
threaded base, LED lens, wound coil and motor internals. Detail views open the
battery/capacitor case to reveal the internal layers. Wires have smooth insulation,
exposed copper strands and connector ends; their endpoints remain at the planned
terminals. The same models are used in library previews and exported videos.
The **Relay** example also has a reviewed continuous model: its control coil
attracts a pivoted armature, the attached spring follows it, and separate load
contacts close before the lamp receives current. Solid-state, latching, normally
closed and other relay variants use the general planner instead.

Use the **Biology** filter for three reviewed scenes: **A Pill's Journey**,
**Swallowing and Peristalsis**, and **Lung Gas Exchange**. The pill scene follows a
typical immediate-release oral dose through swallowing, disintegration and
dissolution, intestinal absorption, portal blood and liver processing, an
illustrative protein-binding target, and clearance. Capsule prompts use a capsule
model and matching narration. Solid pills never pass into blood. The process is
generalized; named medicines and modified-release products use the general
planner rather than being presented as this same example. No dose, treatment
recommendation or real-time pharmacokinetic prediction is supplied.

Reusable 3D anatomy includes a head and oral cavity, esophagus, stomach and
digestive tubes, intestinal villi, liver, kidneys, ureters and bladder, heart,
lungs and alveoli, blood vessels and biconcave red blood cells, cell membranes,
receptors and neurons. Reviewed scenes animate peristaltic contraction, breakup
and particle transport, circulation and opposing gas transfer. Anatomy, particle
sizes and time are schematic. Other biological prompts use AI-planned assemblies
and should be reviewed before publication.

Science references: [NIH medicine journey](https://www.nigms.nih.gov/biobeat/2023/09/what-happens-to-medicine-in-your-body),
[NIDDK digestion](https://www.niddk.nih.gov/health-information/digestive-diseases/digestive-system-how-it-works),
and [NHLBI lung function](https://www.nhlbi.nih.gov/health/lungs).

### Ten example prompts

Choose **1 minute** and **Auto-select from prompt**. Videos use vertical 9:16.
Biology prompts 1–3 and electrical prompts 1–2 use the reviewed scenes.
The remaining prompts use reusable components and AI-planned animation; preview
their geometry, motion and explanation before publishing.

#### Biology

1. **A pill’s journey.** Show the journey of a typical immediate-release tablet: swallowing, esophageal peristalsis, breakup and dissolution, absorption through the small intestine, portal blood and liver processing, circulation to tissue, illustrative protein binding and clearance. Keep the anatomy connected. Show dissolved medicine entering blood, and explain that medicines and formulations differ.

2. **How swallowing works.** Explain esophageal peristalsis using one food bolus. Show muscle contracting behind it and relaxing ahead. Move the contraction along the esophagus with the food, then show the lower esophageal sphincter opening for entry into the stomach and closing afterward. Keep the food and active muscle wave visible.

3. **How oxygen enters blood.** Explain gas exchange in lung alveoli. Begin with breathing lungs, then show thin-walled air sacs, surrounding capillaries and moving red blood cells. Animate oxygen moving from air into blood and carbon dioxide moving the opposite way. Explain hemoglobin’s role in oxygen transport and show carbon dioxide leaving during exhalation.

4. **How a cell receives a signal.** Show an illustrative signaling molecule approaching a receptor in a cell membrane. Include a lipid bilayer, the receptor and the cell interior. Let the molecule bind to a matching pocket, then show a signal passing into the cell. Label this as a simplified example; avoid naming a medicine or claiming a treatment effect.

5. **How a nerve signal travels.** Explain a signal traveling along one neuron. Show dendrites, the cell body, an axon and its terminal. Use a traveling glow to represent local membrane-voltage changes along the axon. Explain that the glow is a teaching marker rather than a particle moving through a wire. Keep the neuron fixed while the signal progresses.

#### Electrical systems

1. **How a switch lights a bulb.** Show a battery, switch and filament bulb connected by insulated copper wires. Begin with the switch open and no current. Close the contacts, show current and a warming filament, then open the switch and let the bulb cool. Distinguish blue electron drift from orange conventional current moving in the opposite direction.

2. **How a relay controls a separate circuit.** Explain a low-voltage DC relay with separate control and lamp circuits. Energize the copper coil, magnetize the iron core, pull the pivoted armature, stretch its return spring and close the normally open load contacts. Then switch off and show the complete return. Keep the circuits electrically isolated and stop current when contacts open.

3. **How an electromagnet picks up metal.** Show a battery and switch connected to a copper coil around an iron core. Place a steel paperclip below it. Close the switch, animate coil current and illustrative magnetic-field lines, and lift the paperclip toward the core. Open the switch and let it fall. Keep the coil fixed; no circuit current flows through the paperclip.

4. **How a capacitor charges.** Show a battery charging an electrolytic capacitor through a resistor and switch. Use a detailed capacitor can, polarity stripe, radial leads and insulated wires. Close the switch, show a brief charging current that gradually decreases, and reveal charge separation in a cutaway. Never show electrons crossing the dielectric. Explain stored electric-field energy.

5. **Why a resistor warms up.** Show a low-voltage battery, switch, banded resistor and connected copper wires. Close the switch, animate current and gradually warm the resistor’s appearance. Explain electrical energy transferring into thermal energy. Open the switch, stop current and show cooling. Keep the resistor’s shape unchanged and avoid flames, melting or invented temperatures.

Narration is budgeted before recording. If a take runs long, the studio uses
its measured speaking rate to shorten complete sentences while preserving every
scene and the ending, then regenerates the voice and subtitle timings. The
90-second setting accepts a shorter complete explanation without expanding it
to fill the maximum. Only modest final tempo adjustments are used.
The reusable 3D scene modules and renderer are available under the [MIT license](LICENSE-3D).

For Reel motion and AI illustrations, extract a recent [stable-diffusion.cpp release](https://github.com/leejet/stable-diffusion.cpp/releases)
into `.visual-engine/runtime`, with `sd-cli.exe` or `sd-cli` directly in that
folder. Put [DreamShaper_8_pruned.safetensors](https://huggingface.co/Lykon/DreamShaper/blob/main/DreamShaper_8_pruned.safetensors)
in `.visual-engine`. These files are local to the installation. To use different
locations, set `AI_VIDEO_IMAGE_CLI` and `AI_VIDEO_IMAGE_MODEL`. The Windows
Vulkan build detects compatible GPUs. Set `AI_VIDEO_IMAGE_BACKEND=cpu` to use
the CPU or to run the CLI's CPU build. The hosted studio needs its own runtime
and model files for Reel motion and AI illustrations.
The older `DreamShaper8_LCM.safetensors` file is also supported. The standard
model is preferred when both are installed, with more sampling steps for object detail.

- **Local setup**: Install [Ollama](https://ollama.com/download) and run
  `ollama pull qwen3:4b` once. On Windows, starting Godd AI with `start.bat`,
  `run_gpu.bat`, or `python server.py` starts Ollama when needed and connects
  to `http://127.0.0.1:11434`. On macOS and Linux, start Ollama before Godd AI.
  Install `qwen3.5:9b` with `ollama pull qwen3.5:9b` for a larger diagram
  planner. The studio tries the smaller model first and can retry with it. Set
  `AI_VIDEO_OLLAMA_MECHANISM_MODEL` to select a different installed model.
  Install the packages in `requirements.txt`. The renderer requires OpenGL 3.3
  or newer. On headless Linux, install Mesa EGL and its DRI drivers.
  For continuous narration, download `kokoro-v1.0.onnx` and `voices-v1.0.bin`
  from [Kokoro ONNX model files v1.1](https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.1).
  Save them as `timed-kokoro-v1.0.onnx` and `timed-voices-v1.0.bin` in
  `%LOCALAPPDATA%\GoddAI\voices` on Windows or `~/.local/share/godd-ai/voices` on Linux.
  Set `AI_VIDEO_VOICE_DIR` to use a different directory. If Kokoro's files are
  absent, the studio uses installed Piper voices, Windows speech, or eSpeak NG.
- **Hosted setup**: Set `AI_VIDEO_GEMINI_API_KEY` in the server environment to
  use Gemini for the storyboard. The default is `gemini-3.1-flash-lite`.
  Keep this key server-side. Prompts go to Gemini when this option is enabled.
  The Docker image includes Mesa EGL and the narration engine. The static Vercel version
  needs the Python rendering server for this feature.
- **Publishing**: Preview the video, review its suggested title, description
  and hashtags, then use **Upload to YouTube**. Connect a channel separately in
  each studio. The same Google OAuth client and callback can handle both sign-ins.
  Disconnecting from either studio removes that studio's session. Uploads default to Private.

## Upload clips to YouTube

1. In [Google Cloud Console](https://console.cloud.google.com/), enable the
   **YouTube Data API v3**. Set up the OAuth consent screen and create a **Web
   application** OAuth client. If the app is in Testing, add the Google account
   that owns the YouTube channel as a test user.
2. Add the exact callback URL under **Authorized redirect URIs**. For the local
   app use `http://localhost:8080/api/youtube/callback`. For Render use
   `https://YOUR-RENDER-HOST/api/youtube/callback`.
3. Set these environment variables where the server runs. Keep the client
   secret in the server environment. The app does not read it from the browser.

   | Variable | Value |
   | --- | --- |
   | `YOUTUBE_OAUTH_CLIENT_ID` | Web application's client ID |
   | `YOUTUBE_OAUTH_CLIENT_SECRET` | Web application's client secret |
   | `YOUTUBE_OAUTH_REDIRECT_URI` | The exact callback URL from step 2 |

   For local PowerShell, set each variable with `$env:NAME = 'value'` before
   running `python server.py`. On Render, set the variables in the service's
   Environment settings and redeploy. Open the studio at the same origin as the
   callback. For example, a localhost callback requires using `localhost`.

4. Analyze a video and choose a clip. In **Upload to YouTube**, click
   **Connect YouTube** and select the destination channel on Google's sign-in
   page. The studio reopens the selected clip after sign-in.
   Set the audience and visibility, then click **Upload to YouTube**. The app
   renders the current clip and returns a link to it in YouTube Studio. The
   YouTube title matches the MP4 filename without the extension. Editing the
   title in the studio updates both.

Each clip has a suggested description with relevant hashtags and a thumbnail
from the source video. Edit the description, enter another timestamp in seconds
to preview a different frame, or download the JPG. The studio sends your
description with the video and applies the thumbnail after YouTube processing
finishes if the channel is eligible.

Uploads default to Private. The app asks for permission to identify the chosen
channel and upload videos. Credentials stay in server memory, and connections
expire after 24 hours. Each browser connects its own channel, and a server
restart requires reconnecting. **Disconnect** removes the session and requests revocation from
Google. Access can also be revoked from
[Google Account connections](https://myaccount.google.com/connections).

For public sign-in, configure a production web client with your site's HTTPS
callback and complete Google's [OAuth verification](https://developers.google.com/identity/protocols/oauth2/production-readiness/sensitive-scope-verification).
Set the credentials on that server once. Visitors connect through Google with
their own accounts. A project in Testing allows only its listed test users.

### Custom mechanism planning

Custom prompts use a shared two-stage planner: validated component geometry,
then motion and state changes referencing those exact components. Each stage
gets one bounded repair attempt with the specific validation error. Movement
repairs retain the valid geometry. A single meaningful continuing motion is
accepted; zero-motion placeholders and incomplete responses are rejected.

The local planner uses `AI_VIDEO_OLLAMA_MODEL` (default `qwen3:4b`) and does not
silently switch to a larger model after an error. To select a stronger installed
model explicitly, set `AI_VIDEO_OLLAMA_MECHANISM_MODEL`; storyboard selection
can be configured separately with `AI_VIDEO_OLLAMA_STORYBOARD_MODEL`.

Generated electrical circuits name component terminals in their wire links.
Wire endpoints snap to those terminals, incomplete source paths get a geometry
repair, and open switches suppress flow on their disconnected branch. Only a
verified single-source series loop shares current states across its wires;
branch currents are never inferred. Capacitor charge and switch blade movement
are separate states. The renderer integrates current for continuous particle
motion across narration cuts.

These checks validate supported geometry, animation and basic connectivity.
They are qualitative illustrations, not a general physics or medical simulator;
review unfamiliar mechanisms and scientific narration before publishing.
