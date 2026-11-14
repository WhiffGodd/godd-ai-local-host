"use strict";

const $ = id => document.getElementById(id);
const storeKey = "godd_ai_video_studio";
const page = {
  templates: [], category: "All", limit: 12, selected: null, provider: null,
  generation: null, upload: null, channel: null, generating: false, uploading: false,
};

async function request(path, body) {
  const response = await fetch(path, {
    ...(body === undefined ? {} : {
      method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body),
    }),
    signal: AbortSignal.timeout(15000),
  });
  const data = await response.json().catch(() => null);
  if (!response.ok || !data || typeof data !== "object") {
    throw Object.assign(new Error(data?.error || "Could not reach the studio. Try again."), {status: response.status});
  }
  return data;
}

function message(id, text, error = false) {
  const element = $(id);
  element.textContent = text;
  element.dataset.error = String(error);
}

function save() {
  sessionStorage.setItem(storeKey, JSON.stringify({
    generation: page.generation, upload: page.upload, template: page.selected?.id || "auto",
    prompt: $("prompt").value, voice: $("voice").value, maxSeconds: $("maxSeconds").value,
    draft: $("video").hidden ? null :
      Object.fromEntries(["title", "description", "visibility", "audience"].map(id => [id, $(id).value])),
  }));
}

function readSaved() {
  try { return JSON.parse(sessionStorage.getItem(storeKey)) || {}; }
  catch (_) { return {}; }
}

function paint(canvas, template, t, cover = false) {
  const ctx = canvas.getContext("2d");
  const {width, height} = canvas;
  const {accent, secondary, background, ink, surface, diagram} = template;
  const a = "#" + accent, b = "#" + secondary;
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#" + background;
  ctx.fillRect(0, 0, width, height);
  ctx.save();
  const scale = cover ? width / 360 : width / 230;
  ctx.translate(width / 2, height * (cover ? .49 : .53));
  ctx.scale(scale, scale);
  const gradient = ctx.createRadialGradient(0, 0, 4, 0, 0, 145);
  gradient.addColorStop(0, a + "35");
  gradient.addColorStop(1, a + "00");
  ctx.fillStyle = gradient;
  ctx.fillRect(-150, -150, 300, 300);
  ctx.lineWidth = 1;
  ctx.strokeStyle = a + "30";
  if (surface === "grid" || surface === "paper") {
    for (let i = -180; i <= 180; i += 18) {
      ctx.beginPath();
      ctx.moveTo(-180, i);
      ctx.lineTo(180, i);
      if (surface === "grid") {
        ctx.moveTo(i, -180);
        ctx.lineTo(i, 180);
      }
      ctx.stroke();
    }
  } else if (surface === "stars") {
    for (let i = 0; i < 40; i++) {
      ctx.fillStyle = i % 3 ? a + "68" : b;
      ctx.fillRect((i * 73) % 300 - 150, (i * 67) % 230 - 115, 1.5, 1.5);
    }
  } else {
    ctx.beginPath();
    ctx.roundRect(-100, -70, 200, 140, surface === "glass" ? 24 : 9);
    ctx.fillStyle = b + "26";
    ctx.fill();
    ctx.stroke();
  }
  const disc = (x, y, radius, color) => {
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.fill();
  };
  const beat = t * Math.PI * 2;
  ctx.lineWidth = 2;
  ctx.strokeStyle = a;
  if (["presenter", "walking", "handoff"].includes(diagram)) {
    if (diagram === "presenter") {
      ctx.fillStyle = b + "50";
      ctx.fillRect(0, -36, 75, 62);
      for (let row = 0; row < 3; row++) ctx.fillRect(10, -22 + row * 16, 42 + row * 5, 3);
    }
    const people = diagram === "handoff" ? [[-42, 1, a], [42, -1, b]] :
      [[diagram === "walking" ? 34 * Math.sin(beat) : -44, 1, a]];
    for (const [x, facing, color] of people) {
      const step = diagram === "walking" ? Math.sin(beat * 2) * 13 : 0;
      ctx.strokeStyle = color;
      ctx.lineWidth = 8;
      ctx.lineCap = "round";
      ctx.beginPath();
      ctx.moveTo(x - 8, 12);
      ctx.lineTo(x - 12 - step, 37);
      ctx.moveTo(x + 8, 12);
      ctx.lineTo(x + 12 + step, 37);
      ctx.moveTo(x, -9);
      ctx.lineTo(x + facing * 33, -8 + 9 * Math.sin(beat));
      ctx.stroke();
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.roundRect(x - 14, -20, 28, 37, 8);
      ctx.fill();
      disc(x, -33, 11, "#efbc93");
    }
  } else if (["orbit", "cycle", "network"].includes(diagram)) {
    disc(0, 0, 15, b);
    for (let i = 0; i < 3; i++) {
      const radius = 32 + i * 20;
      const angle = beat * (1 - i * .2) + i * 2.2;
      ctx.beginPath();
      ctx.ellipse(0, 0, radius, radius * .7, 0, 0, Math.PI * 2);
      ctx.strokeStyle = a + "8a";
      ctx.stroke();
      disc(radius * Math.cos(angle), radius * .7 * Math.sin(angle), 7 - i, a);
    }
  } else if (["flow", "motion", "sequence"].includes(diagram)) {
    for (let i = 0; i < 3; i++) {
      const y = (i - 1) * 29;
      ctx.beginPath();
      ctx.moveTo(-72, y);
      ctx.lineTo(72, y);
      ctx.strokeStyle = a + "65";
      ctx.stroke();
      disc(61 * Math.sin(beat + i * 1.6), y, 8, i % 2 ? b : a);
    }
  } else if (diagram === "wave") {
    for (let row = 0; row < 2; row++) {
      ctx.strokeStyle = row ? a : b;
      ctx.beginPath();
      for (let x = -90; x < 91; x += 3) {
        const y = Math.sin(x / 19 + beat + row * 1.1) * (row ? 25 : 38);
        if (x === -90) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }
  } else if (diagram === "bars" || diagram === "compare") {
    for (let i = 0; i < 4; i++) {
      const h = 26 + i * 13 + 8 * Math.sin(beat + i);
      ctx.fillStyle = i % 2 ? b : a;
      ctx.beginPath();
      ctx.roundRect(-70 + i * 38, 41 - h, 25, h, 4);
      ctx.fill();
    }
  } else {
    for (let i = 0; i < 3; i++) {
      const y = 28 - i * 25 + 8 * Math.sin(beat + i);
      ctx.fillStyle = i % 2 ? b + "99" : a + "99";
      ctx.strokeStyle = i % 2 ? b : a;
      ctx.beginPath();
      ctx.moveTo(-73, y);
      ctx.lineTo(0, y - 25);
      ctx.lineTo(73, y);
      ctx.lineTo(0, y + 25);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
    }
  }
  ctx.restore();
  if (cover) {
    ctx.fillStyle = a;
    ctx.font = "600 15px DM Sans, sans-serif";
    ctx.fillText(template.category.toUpperCase(), 26, 51);
    ctx.fillStyle = "#" + ink;
    ctx.font = "700 30px Space Grotesk, sans-serif";
    ctx.fillText(template.name, 26, height - 78, width - 52);
    ctx.fillStyle = a + "90";
    ctx.fillRect(26, height - 46, 49 + 50 * (.5 + .5 * Math.sin(beat)), 3);
  }
}

const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
function animate(now) {
  if (page.selected && !$("stylePreview").hidden) {
    paint($("stylePreview"), page.selected, reducedMotion.matches ? .18 : (now % 4300) / 4300, true);
  }
  requestAnimationFrame(animate);
}
requestAnimationFrame(animate);

function chooseTemplate(template) {
  page.selected = template;
  $("autoTemplate").setAttribute("aria-pressed", String(!template));
  if ($("video").hidden) {
    $("selectedStyle").textContent = template ? template.name + " · Template preview" : "Template will be chosen from your prompt";
    $("stylePreview").hidden = !template;
  }
  for (const button of $("templateGrid").querySelectorAll("button")) {
    button.setAttribute("aria-pressed", String(button.dataset.template === template?.id));
  }
  save();
}

function drawLibrary() {
  const matches = page.templates.filter(template => page.category === "All" || template.category === page.category);
  $("templateCount").textContent = matches.length + " templates";
  for (const button of $("categories").querySelectorAll("button")) {
    button.setAttribute("aria-pressed", String(button.textContent === page.category));
  }
  $("templateGrid").replaceChildren(...matches.slice(0, page.limit).map(template => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "template";
    button.dataset.template = template.id;
    button.setAttribute("aria-pressed", String(template.id === page.selected?.id));
    const image = document.createElement("canvas");
    image.width = 230;
    image.height = 126;
    image.setAttribute("aria-hidden", "true");
    paint(image, template, .18);
    const name = document.createElement("span");
    name.textContent = template.name;
    button.append(image, name);
    button.addEventListener("click", () => chooseTemplate(template));
    return button;
  }));
  $("moreTemplates").hidden = page.limit >= matches.length;
}

function generationControls() {
  $("generate").disabled = page.generating || page.uploading || !page.provider?.available;
  $("sample").disabled = page.generating || page.uploading || !page.templates.length;
  $("generate").textContent = page.generating ? "Generating…" : "Generate video";
}

function youtubeControls() {
  $("connect").hidden = !page.youtubeEnabled || !!page.channel;
  $("disconnect").hidden = !page.channel;
  $("disconnect").disabled = page.uploading;
  $("publishForm").hidden = !page.channel && !page.upload;
  $("upload").disabled = page.uploading;
  $("upload").formNoValidate = !!page.upload;
  $("upload").textContent = page.upload ? "Check upload status" : "Upload to YouTube";
  generationControls();
}

function showVideo(job, draft = null) {
  const source = "/api/ai-videos/" + encodeURIComponent(job.id) + "/video";
  $("video").src = source;
  $("video").hidden = false;
  $("stylePreview").hidden = true;
  const seconds = Math.round(job.metadata.duration);
  const runtime = Number.isFinite(seconds) ? Math.floor(seconds / 60) + ":" + String(seconds % 60).padStart(2, "0") : "";
  $("selectedStyle").textContent = [job.metadata.template, runtime].filter(Boolean).join(" · ");
  $("downloadVideo").href = source + "?download=1";
  $("previewLink").hidden = false;
  $("exportTools").hidden = false;
  document.querySelector(".workbench").dataset.generated = "true";
  $("title").value = job.metadata.title;
  $("description").value = job.metadata.description;
  if (draft) {
    for (const [id, value] of Object.entries(draft)) if (["title", "description", "visibility", "audience"].includes(id)) $(id).value = value;
  }
  save();
}

const delay = ms => new Promise(resolve => setTimeout(resolve, ms));

function showGenerationProgress(job) {
  const stage = job.progress?.stage;
  const percent = job.progress?.percent;
  const labels = {
    storyboard: "Writing the storyboard…",
    revising: "Adjusting the script to fit your chosen length…",
    narration: "Generating the voice-over…",
    rendering: "Rendering the animation…",
    finalizing: "Finishing the MP4…",
  };
  const text = job.state === "queued" ? "Your video is queued…" : labels[stage] || "Preparing your video…";
  const bar = $("generationProgress");
  bar.hidden = false;
  if (Number.isFinite(percent)) bar.value = percent;
  else bar.removeAttribute("value");
  message("generationStatus", Number.isFinite(percent) ? text + " " + percent + "%" : text);
  message("previewStatus", "The finished video will appear here.");
}

async function watchGeneration(draft) {
  $("checkGeneration").hidden = true;
  page.generating = true;
  generationControls();
  try {
    const end = Date.now() + 20 * 60 * 1000;
    while (Date.now() < end) {
      const job = await request("/api/ai-videos/" + encodeURIComponent(page.generation));
      if (job.state === "failed") throw Object.assign(new Error(job.error), {finished: true});
      if (job.state === "complete") {
        showVideo(job, draft);
        message("generationStatus", "Your video is ready.");
        message("previewStatus", "");
        return;
      }
      showGenerationProgress(job);
      await delay(2000);
    }
    throw new Error("The video is taking longer than expected.");
  } catch (error) {
    if (error.finished || error.status === 404) {
      page.generation = null;
      save();
    }
    $("checkGeneration").hidden = !page.generation;
    message("generationStatus", page.generation ? error.message + " Use Check video status to reconnect." : error.message, true);
    message("previewStatus", page.generation ? "Waiting for a status update." : "No video is available to preview.");
  } finally {
    $("generationProgress").hidden = true;
    page.generating = false;
    generationControls();
  }
}

async function generate(example) {
  if (page.generating || page.uploading || !page.templates.length) return;
  $("checkGeneration").hidden = true;
  page.generating = true;
  generationControls();
  message("generationStatus", "Starting your video…");
  try {
    const job = await request("/api/ai-videos", {
      prompt: $("prompt").value.trim(), template: page.selected?.id || "auto", voice: $("voice").value, example,
      max_seconds: Number($("maxSeconds").value),
    });
    page.generation = job.id;
    $("video").pause();
    $("video").hidden = true;
    $("previewLink").hidden = true;
    showGenerationProgress(job);
    $("stylePreview").hidden = !page.selected;
    $("selectedStyle").textContent = page.selected ? page.selected.name + " · Template preview" : "Auto-selecting a template";
    $("exportTools").hidden = true;
    message("publishStatus", "");
    delete document.querySelector(".workbench").dataset.generated;
    save();
    await watchGeneration();
  } catch (error) {
    $("checkGeneration").hidden = !page.generation || !$("video").hidden;
    message("generationStatus", error.message, true);
  } finally {
    page.generating = false;
    generationControls();
  }
}

async function refreshConnection() {
  try {
    const data = await request("/api/youtube/status");
    page.youtubeEnabled = data.enabled;
    page.channel = data.channel;
    message("connectionStatus", data.channel ? "Connected to " + data.channel.title :
      data.enabled ? "Connect your channel to publish this video." : "YouTube sign-in is unavailable at this address.");
  } catch (error) {
    message("connectionStatus", error.message, true);
  }
  youtubeControls();
}

async function watchUpload() {
  page.uploading = true;
  youtubeControls();
  try {
    const end = Date.now() + 360000;
    while (Date.now() < end) {
      const job = await request("/api/youtube/uploads/" + encodeURIComponent(page.upload));
      if (job.state === "failed") throw Object.assign(new Error(job.error), {finished: true});
      if (job.state === "complete") {
        const link = document.createElement("a");
        link.href = "https://studio.youtube.com/video/" + encodeURIComponent(job.video_id) + "/edit";
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = "Open in YouTube Studio";
        message("publishStatus", "Uploaded" + (job.privacy ? " (" + job.privacy + ")" : "") + ". " +
          (job.thumbnail_warning ? job.thumbnail_warning + " " : ""));
        $("publishStatus").append(link);
        page.upload = null;
        save();
        return;
      }
      message("publishStatus", job.state === "thumbnail_processing" ? "Video uploaded. Applying the thumbnail…" :
        job.state === "uploading" ? "Uploading to YouTube…" : "Preparing the video for YouTube…");
      await delay(2500);
    }
    throw new Error("YouTube is still working. Use Check upload status to continue.");
  } catch (error) {
    if (error.finished || error.status === 404) {
      page.upload = null;
      save();
    }
    message("publishStatus", error.message, true);
  } finally {
    page.uploading = false;
    youtubeControls();
  }
}

$("generator").addEventListener("submit", event => { event.preventDefault(); generate(false); });
$("sample").addEventListener("click", () => generate(true));
$("checkGeneration").addEventListener("click", () => watchGeneration());
$("video").addEventListener("error", () => {
  if (!$("video").hidden) message("previewStatus", "The preview could not load. Try Download MP4 or refresh the studio.", true);
});
$("autoTemplate").addEventListener("click", () => chooseTemplate(null));
$("moreTemplates").addEventListener("click", () => { page.limit += 12; drawLibrary(); });
for (const button of document.querySelectorAll("[data-topic]")) {
  button.addEventListener("click", () => { $("prompt").value = button.dataset.topic; $("prompt").focus(); save(); });
}
$("generator").addEventListener("input", save);
$("publishForm").addEventListener("input", save);

$("connect").addEventListener("click", async () => {
  $("connect").disabled = true;
  try {
    save();
    const {url} = await request("/api/youtube/connect", {studio: "ai-videos"});
    window.location.assign(url);
  } catch (error) {
    message("connectionStatus", error.message, true);
    $("connect").disabled = false;
  }
});

$("disconnect").addEventListener("click", async () => {
  $("disconnect").disabled = true;
  try {
    await request("/api/youtube/disconnect", {});
    await refreshConnection();
  } catch (error) {
    message("connectionStatus", error.message, true);
    youtubeControls();
  }
});

$("publishForm").addEventListener("submit", async event => {
  event.preventDefault();
  if (page.uploading) return;
  if (page.upload) return watchUpload();
  if (!page.channel || !page.generation || $("video").hidden) return;
  page.uploading = true;
  youtubeControls();
  const payload = {
    request_id: crypto.randomUUID(), channel_id: page.channel.id, generated_video_id: page.generation,
    title: $("title").value, description: $("description").value,
    privacy: $("visibility").value, made_for_kids: $("audience").value === "yes",
  };
  try {
    let job;
    try { job = await request("/api/youtube/uploads", payload); }
    catch (error) {
      if (error.status) throw error;
      job = await request("/api/youtube/uploads", payload);
    }
    page.upload = job.id;
    save();
    await watchUpload();
  } catch (error) {
    message("publishStatus", error.status ? error.message : "Could not confirm the upload. Check YouTube Studio before retrying.", true);
    if ([401, 409].includes(error.status)) await refreshConnection();
  } finally {
    page.uploading = false;
    youtubeControls();
  }
});

async function initialize() {
  const saved = readSaved();
  $("prompt").value = saved.prompt || "";
  if (["60", "90"].includes(saved.maxSeconds)) $("maxSeconds").value = saved.maxSeconds;
  if (Array.from($("voice").options).some(option => option.value === saved.voice)) $("voice").value = saved.voice;
  page.generation = saved.generation;
  page.upload = saved.upload;
  const url = new URL(location.href);
  if (url.searchParams.has("youtube")) {
    url.searchParams.delete("youtube");
    history.replaceState(null, "", url);
  }
  const connection = refreshConnection();
  try {
    const data = await request("/api/ai-videos/templates");
    page.templates = data.templates;
    page.provider = data;
    page.selected = page.templates.find(template => template.id === saved.template) || null;
    for (const category of ["All", ...new Set(page.templates.map(template => template.category))]) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = category;
      button.addEventListener("click", () => { page.category = category; page.limit = 12; drawLibrary(); });
      $("categories").append(button);
    }
    drawLibrary();
    $("autoTemplate").setAttribute("aria-pressed", String(!page.selected));
    $("stylePreview").hidden = !page.selected;
    $("selectedStyle").textContent = page.selected ? page.selected.name + " · Template preview" : "Template will be chosen from your prompt";
    message("generationStatus", data.setup || "");
    generationControls();
    if (page.generation) {
      await watchGeneration(saved.draft);
      await connection;
      if (page.upload && !$("video").hidden) watchUpload();
    }
  } catch (error) {
    message("generationStatus", "The template library could not load. Refresh the studio to retry.", true);
  }
}

initialize();
