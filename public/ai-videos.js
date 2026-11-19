"use strict";

const $ = id => document.getElementById(id);
const storeKey = "godd_ai_video_studio";
const promptScene = {id: "generated", name: "AI illustrations"};
const page = {
  templates: [], selected: null, preview: null, provider: null,
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
    generation: page.generation, upload: page.upload, sceneOverride: page.selected?.id,
    prompt: $("prompt").value, voice: $("voice").value, maxSeconds: $("maxSeconds").value,
    visualStyle: $("visualStyle").value,
    styleVersion: 3,
    draft: $("video").hidden ? null :
      Object.fromEntries(["title", "description", "visibility", "audience"].map(id => [id, $(id).value])),
  }));
}

function readSaved() {
  try { return JSON.parse(sessionStorage.getItem(storeKey)) || {}; }
  catch (_) { return {}; }
}

function showScenePreview(template) {
  const preview = $("stylePreview");
  preview.hidden = !template;
  if (template) {
    if (preview.getAttribute("src") === template.preview) return;
    preview.poster = template.poster;
    preview.src = template.preview;
    preview.setAttribute("aria-label", template.name + " animation preview");
  } else {
    preview.pause();
    preview.removeAttribute("src");
    preview.load();
  }
}

function updateTemplateSelection() {
  const template = page.selected;
  $("autoTemplate").setAttribute("aria-pressed", String(!template));
  $("buildScene").setAttribute("aria-pressed", String(template === promptScene));
  $("useScene").setAttribute("aria-pressed", String(!!template && template === page.preview));
  message("sceneSelection", template ? template.name + " is selected for generation." : "");
}

function chooseTemplate(template) {
  page.selected = template;
  if (template) $("visualStyle").value = "auto";
  updateTemplateSelection();
  updateVisualMode(page.provider || {});
  generationControls();
  save();
}

function previewScene(template) {
  page.preview = template;
  const useScene = $("useScene");
  useScene.hidden = !template;
  useScene.textContent = template ? "Use " + template.name : "Use previewed scene";
  useScene.setAttribute("aria-pressed", String(!!template && template === page.selected));
  showScenePreview(template);
  if ($("video").hidden) $("selectedStyle").textContent = template ? template.name + " · Scene preview" : "";
  for (const button of $("templateGrid").querySelectorAll("button")) {
    button.setAttribute("aria-pressed", String(button.dataset.template === template?.id));
  }
}

function drawLibrary() {
  $("templateGrid").replaceChildren(...page.templates.map(template => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "template";
    button.dataset.template = template.id;
    button.setAttribute("aria-pressed", String(template.id === page.preview?.id));
    button.title = template.coverage;
    const image = document.createElement("img");
    image.alt = "";
    image.src = template.poster;
    const name = document.createElement("span");
    name.textContent = template.name;
    button.append(image, name);
    button.addEventListener("click", () => {
      chooseTemplate(template);
      previewScene(template);
    });
    return button;
  }));
}

function generationControls() {
  const imagesRequired = $("visualStyle").value === "motion" || page.selected === promptScene;
  $("generate").disabled = page.generating || page.uploading || !page.provider?.available ||
    (imagesRequired && page.provider?.custom_visuals === false);
  $("generate").textContent = page.generating ? "Generating…" : "Generate video";
}

async function checkModel() {
  $("checkModel").disabled = true;
  message("generationStatus", "Checking the AI connection…");
  try {
    page.provider = await request("/api/ai-videos/templates");
    updateVisualMode(page.provider);
    message("generationStatus", page.provider.available ? page.provider.provider + " is ready." : page.provider.setup);
    $("checkModel").hidden = page.provider.available;
  } catch (error) {
    message("generationStatus", error.message, true);
  } finally {
    $("checkModel").disabled = false;
    generationControls();
  }
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
  previewScene(null);
  const seconds = Math.round(job.metadata.duration);
  const runtime = Number.isFinite(seconds) ? Math.floor(seconds / 60) + ":" + String(seconds % 60).padStart(2, "0") : "";
  const visualStyle = job.metadata.scene_source === "schematic" ? "3D schematic" : job.metadata.template;
  $("selectedStyle").textContent = [visualStyle, runtime].filter(Boolean).join(" · ");
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
    motion: "Planning the moving objects and scene transitions…",
    mechanism: "Designing moving parts and mapping the steps…",
    visuals: "Preparing objects and visual effects…",
    revising: "Fitting the complete narration to your time limit…",
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
    if (error.finished && /Ollama|Gemini/.test(error.message)) $("checkModel").hidden = false;
    $("checkGeneration").hidden = !page.generation;
    message("generationStatus", page.generation ? error.message + " Use Check video status to reconnect." : error.message, true);
    message("previewStatus", page.generation ? "Waiting for a status update." : "No video is available to preview.");
  } finally {
    $("generationProgress").hidden = true;
    page.generating = false;
    generationControls();
  }
}

async function generate() {
  if (page.generating || page.uploading || !page.templates.length) return;
  $("checkGeneration").hidden = true;
  page.generating = true;
  generationControls();
  message("generationStatus", "Starting your video…");
  try {
    const job = await request("/api/ai-videos", {
      prompt: $("prompt").value.trim(), template: page.selected?.id || "auto", voice: $("voice").value,
      visual_style: $("visualStyle").value,
      max_seconds: Number($("maxSeconds").value),
    });
    page.generation = job.id;
    $("video").pause();
    $("video").hidden = true;
    $("previewLink").hidden = true;
    showGenerationProgress(job);
    previewScene(null);
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
    const data = await request("/api/youtube/ai-videos/status");
    page.youtubeEnabled = data.enabled;
    page.channel = data.channel;
    message("connectionStatus", data.channel ? "AI Studio channel · " + data.channel.title :
      data.enabled ? "Choose a YouTube channel for AI Studio." : "YouTube sign-in is unavailable at this address.");
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
      const job = await request("/api/youtube/ai-videos/uploads/" + encodeURIComponent(page.upload));
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

$("generator").addEventListener("submit", event => { event.preventDefault(); generate(); });
$("checkGeneration").addEventListener("click", () => watchGeneration());
$("checkModel").addEventListener("click", checkModel);
$("title").addEventListener("input", save);
$("video").addEventListener("error", () => {
  if (!$("video").hidden) message("previewStatus", "The preview could not load. Try Download MP4 or refresh the studio.", true);
});
$("autoTemplate").addEventListener("click", () => {
  $("visualStyle").value = "auto";
  chooseTemplate(null);
});
$("buildScene").addEventListener("click", () => chooseTemplate(promptScene));
$("visualStyle").addEventListener("change", () => {
  if ($("visualStyle").value === "motion") chooseTemplate(null);
  updateVisualMode(page.provider || {});
  generationControls();
  save();
});
$("useScene").addEventListener("click", () => chooseTemplate(page.preview));
for (const button of document.querySelectorAll("[data-topic]")) {
  button.addEventListener("click", () => {
    $("prompt").value = button.dataset.topic;
    $("prompt").focus();
    $("visualStyle").value = "auto";
    chooseTemplate(null);
  });
}
$("generator").addEventListener("input", save);
$("publishForm").addEventListener("input", save);

$("connect").addEventListener("click", async () => {
  $("connect").disabled = true;
  try {
    save();
    const {url} = await request("/api/youtube/ai-videos/connect", {});
    window.location.assign(url);
  } catch (error) {
    message("connectionStatus", error.message, true);
    $("connect").disabled = false;
  }
});

$("disconnect").addEventListener("click", async () => {
  $("disconnect").disabled = true;
  try {
    await request("/api/youtube/ai-videos/disconnect", {});
    page.upload = null;
    message("publishStatus", "");
    save();
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
    try { job = await request("/api/youtube/ai-videos/uploads", payload); }
    catch (error) {
      if (error.status) throw error;
      job = await request("/api/youtube/ai-videos/uploads", payload);
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

function updateVisualMode(settings) {
  $("visualMode").textContent = "Matching topics use working 3D models. Other topics use AI-planned 3D cutaways. Select a scene to use and preview it.";
  $("buildScene").disabled = settings.custom_visuals === false;
  $("buildScene").title = settings.custom_visuals_setup || "";
}

async function initialize() {
  const saved = readSaved();
  $("prompt").value = saved.prompt || "";
  $("visualStyle").value = "auto";
  if (["60", "90"].includes(saved.maxSeconds)) $("maxSeconds").value = saved.maxSeconds;
  if (Array.from($("voice").options).some(option => option.value === saved.voice)) $("voice").value = saved.voice;
  page.generation = saved.generation;
  page.upload = saved.upload;
  const url = new URL(location.href);
  const requestedVideo = url.searchParams.get("video");
  if (requestedVideo && /^[A-Za-z0-9_-]{20,80}$/.test(requestedVideo)) {
    page.generation = requestedVideo;
    page.upload = null;
    saved.draft = null;
    url.searchParams.delete("video");
    history.replaceState(null, "", url);
  }
  if (url.searchParams.has("youtube")) {
    url.searchParams.delete("youtube");
    history.replaceState(null, "", url);
  }
  const connection = refreshConnection();
  try {
    const data = await request("/api/ai-videos/templates");
    page.templates = data.templates;
    page.provider = data;
    updateVisualMode(data);
    drawLibrary();
    page.selected = page.templates.find(template => template.id === saved.sceneOverride) || null;
    updateTemplateSelection();
    previewScene(page.selected === promptScene ? null : page.selected);
    message("generationStatus", data.setup || "");
    $("checkModel").hidden = data.available;
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
