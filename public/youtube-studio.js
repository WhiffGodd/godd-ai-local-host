// YouTube authorization and publishing stay on the same origin as the studio.
const youtubeUI = {
  status: document.getElementById('youtubeStatus'),
  connect: document.getElementById('youtubeConnect'),
  setup: document.getElementById('youtubeSetup'),
  disconnect: document.getElementById('youtubeDisconnect'),
  form: document.getElementById('youtubeForm'),
  title: document.getElementById('youtubeTitle'),
  description: document.getElementById('youtubeDescription'),
  thumbnail: document.getElementById('clipThumbnail'),
  thumbnailTime: document.getElementById('thumbnailTime'),
  thumbnailStatus: document.getElementById('thumbnailStatus'),
  downloadThumbnail: document.getElementById('downloadThumbnail'),
  privacy: document.getElementById('youtubePrivacy'),
  audience: document.getElementById('youtubeAudience'),
  upload: document.getElementById('youtubeUpload'),
  result: document.getElementById('youtubeResult')
};
const youtubeJobKey = 'godd_youtube_upload_job';
const youtubeDraftKey = 'godd_youtube_connect_draft';
let youtubeChannel;
let youtubeConfigured = true;
let youtubeBusy = false;
let youtubeJob = sessionStorage.getItem(youtubeJobKey);
const clipThumbnails = new WeakMap();
let thumbnailRequest;
let thumbnailObjectUrl;

async function youtubeRequest(path, body) {
  const options = body === undefined ? {} : {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body)
  };
  const response = await fetch('/api/youtube/' + path, {
    ...options, signal: AbortSignal.timeout(20000)
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw Object.assign(new Error(data.error || 'Could not reach YouTube uploads.'), {status: response.status});
  return data;
}

function youtubeControls() {
  youtubeUI.connect.hidden = !!youtubeChannel || !youtubeConfigured;
  youtubeUI.setup.hidden = youtubeConfigured;
  youtubeUI.disconnect.hidden = !youtubeChannel;
  youtubeUI.disconnect.disabled = youtubeBusy;
  youtubeUI.form.hidden = !youtubeChannel;
  youtubeUI.upload.disabled = youtubeBusy;
  youtubeUI.upload.textContent = youtubeJob && !youtubeBusy ? 'Check upload status' : 'Upload to YouTube';
}

async function refreshYoutubeConnection() {
  if (getBackend() !== window.location.origin) {
    youtubeUI.status.textContent = 'Open the studio on the rendering server to connect YouTube.';
    youtubeUI.connect.disabled = true;
    return;
  }
  try {
    const state = await youtubeRequest('status');
    youtubeChannel = state.channel;
    youtubeConfigured = state.enabled === true;
    youtubeUI.connect.disabled = !youtubeConfigured;
    youtubeUI.status.textContent = youtubeChannel ? `Connected to ${youtubeChannel.title}` :
      youtubeConfigured ? 'Connect your channel to upload this clip.' :
        'This server needs Google OAuth credentials before you can connect a YouTube channel.';
    youtubeControls();
    if (youtubeChannel && youtubeJob && !youtubeBusy) await monitorYoutubeUpload();
  } catch (_) {
    youtubeUI.status.textContent = 'Could not check the YouTube connection. Refresh the studio to retry.';
    youtubeUI.connect.disabled = true;
  }
}

function clipExportTitle(clip) {
  const title = (clip?.exportTitle ?? clip?.title ?? '')
    .replace(/[^\w\s-]/g, '').trim().replace(/[-\s]+/g, '_').slice(0, 100);
  if (!title || /^(?:con|prn|aux|nul|com[0-9]|lpt[0-9])$/i.test(title)) {
    return `clip_${Math.round(clip?.start || 0)}s`;
  }
  return title;
}

function updateYoutubeClip(clip) {
  youtubeUI.title.value = clipExportTitle(clip);
  youtubeUI.description.value = clip.exportDescription ?? clip.description ??
    `${clip.title || 'Video highlight'}\n\n#Shorts`;
  if (!youtubeBusy && !youtubeJob) youtubeUI.result.replaceChildren();
  youtubeUI.thumbnailTime.value = clip.thumbnail_time ?? Math.round(clip.start * 100) / 100;
  updateThumbnail(clip, youtubeUI.thumbnailTime.valueAsNumber);
}

function showThumbnail(image) {
  if (thumbnailObjectUrl) URL.revokeObjectURL(thumbnailObjectUrl);
  thumbnailObjectUrl = image ? URL.createObjectURL(image) : null;
  const preview = youtubeUI.thumbnail;
  const youtubeThumbnail = activeVideoId ? ytThumb(activeVideoId) : '';
  const sources = [...new Set([currentVideoData?.thumbnail, youtubeThumbnail].filter(Boolean))];
  const src = thumbnailObjectUrl || sources.shift();
  preview.hidden = !src;
  preview.alt = image ? 'Selected clip thumbnail' : 'Original video thumbnail';
  youtubeUI.downloadThumbnail.hidden = !image;
  if (image) {
    youtubeUI.downloadThumbnail.href = thumbnailObjectUrl;
  } else {
    youtubeUI.downloadThumbnail.removeAttribute('href');
  }
  preview.onerror = () => {
    if (image) {
      clipThumbnails.delete(activeClip);
      showThumbnail();
      youtubeUI.thumbnailStatus.textContent = 'Could not display the captured frame. Preview it again to retry.';
      return;
    }
    const fallback = sources.shift();
    if (fallback) preview.src = fallback;
    else preview.hidden = true;
  };
  if (src) preview.src = src;
  else preview.removeAttribute('src');
}

async function updateThumbnail(clip, timestamp) {
  thumbnailRequest?.abort();
  const cached = clipThumbnails.get(clip);
  const hasFrame = cached?.timestamp === timestamp && cached?.image;
  showThumbnail(hasFrame);
  if (!Number.isFinite(timestamp) || timestamp < 0) {
    youtubeUI.thumbnailStatus.textContent = 'Enter a valid time in the original video.';
    return;
  }
  if (hasFrame) {
    youtubeUI.thumbnailStatus.textContent = '';
    return;
  }
  const controller = new AbortController();
  thumbnailRequest = controller;
  youtubeUI.thumbnailStatus.textContent = 'Capturing the selected frame…';
  try {
    const response = await fetch(`${getBackend()}/api/thumbnail`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        url: currentVideoData?.url || `https://www.youtube.com/watch?v=${activeVideoId}`,
        timestamp,
        upload_id: currentVideoData?.upload_id
      }),
      signal: AbortSignal.any([controller.signal, AbortSignal.timeout(45000)])
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.error || 'Could not load this thumbnail.');
    }
    const image = await response.blob();
    if (image.type !== 'image/jpeg' || !image.size) {
      throw new Error('The server did not return a thumbnail. Try previewing the frame again.');
    }
    if (activeClip !== clip || controller.signal.aborted) return;
    clip.thumbnail_time = timestamp;
    clipThumbnails.set(clip, {timestamp, image});
    showThumbnail(image);
    youtubeUI.thumbnailStatus.textContent = '';
  } catch (error) {
    if (activeClip !== clip || controller.signal.aborted) return;
    youtubeUI.thumbnailStatus.textContent = error.name === 'TimeoutError' ?
      'Thumbnail capture took too long. Try previewing the frame again.' : error.message;
  }
}

youtubeUI.description.addEventListener('input', () => {
  if (activeClip) activeClip.exportDescription = youtubeUI.description.value;
});

document.getElementById('copyDescription').addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText(youtubeUI.description.value);
    showToast('Description and hashtags copied.');
  } catch (_) {
    youtubeUI.description.select();
    showToast('The description is selected. Press Ctrl+C to copy.');
  }
});

document.getElementById('previewThumbnail').addEventListener('click', () => {
  if (activeClip) updateThumbnail(activeClip, youtubeUI.thumbnailTime.valueAsNumber);
});

youtubeUI.downloadThumbnail.addEventListener('click', () => {
  youtubeUI.downloadThumbnail.download = `${clipExportTitle(activeClip)}_thumbnail.jpg`;
});

youtubeUI.title.addEventListener('input', () => {
  if (activeClip) activeClip.exportTitle = youtubeUI.title.value;
});

youtubeUI.title.addEventListener('blur', () => {
  if (activeClip) youtubeUI.title.value = clipExportTitle(activeClip);
});

youtubeUI.connect.addEventListener('click', async () => {
  youtubeUI.connect.disabled = true;
  try {
    sessionStorage.setItem(youtubeDraftKey, JSON.stringify({
      video: currentVideoData, clips: currentClips, clipId: activeClip?.id,
      layout: currentLayout, style: currentStyle,
      description: youtubeUI.description.value, privacy: youtubeUI.privacy.value,
      audience: youtubeUI.audience.value
    }));
    const {url} = await youtubeRequest('connect', {});
    window.location.assign(url);
  } catch (error) {
    sessionStorage.removeItem(youtubeDraftKey);
    youtubeUI.status.textContent = error.message;
    youtubeUI.connect.disabled = false;
  }
});

function restoreYoutubeDraft() {
  const url = new URL(window.location.href);
  if (!['connected', 'retry'].includes(url.searchParams.get('youtube'))) return;
  url.searchParams.delete('youtube');
  window.history.replaceState(null, '', url);
  const saved = sessionStorage.getItem(youtubeDraftKey);
  sessionStorage.removeItem(youtubeDraftKey);
  if (!saved) return;
  let draft;
  try {
    draft = JSON.parse(saved);
  } catch (_) {
    return;
  }
  if (!draft?.video || !Array.isArray(draft.clips) || !draft.clips.length) return;
  displayStudio(draft.video, draft.clips);
  if (draft.clipId !== activeClip?.id) selectClip(draft.clipId);
  setLayout(draft.layout);
  setStyle(draft.style);
  youtubeUI.description.value = draft.description;
  youtubeUI.privacy.value = draft.privacy;
  youtubeUI.audience.value = draft.audience;
}

youtubeUI.disconnect.addEventListener('click', async () => {
  try {
    await youtubeRequest('disconnect', {});
    clearYoutubeJob();
    youtubeUI.result.replaceChildren();
    await refreshYoutubeConnection();
  } catch (error) {
    youtubeUI.result.textContent = error.message;
  }
});

function clearYoutubeJob() {
  youtubeJob = null;
  sessionStorage.removeItem(youtubeJobKey);
}

function showUploadedVideo(status, message) {
  const link = document.createElement('a');
  link.href = `https://studio.youtube.com/video/${encodeURIComponent(status.video_id)}/edit`;
  link.target = '_blank';
  link.rel = 'noopener noreferrer';
  link.textContent = 'Open in YouTube Studio';
  const visibility = ['private', 'unlisted', 'public'].includes(status.privacy) ? ` (${status.privacy})` : '';
  youtubeUI.result.replaceChildren(`Uploaded${visibility}. ${message} `, link);
}

async function monitorYoutubeUpload(retrySource) {
  youtubeBusy = true;
  youtubeControls();
  const started = Date.now();
  let interrupted = 0;
  try {
    while (youtubeJob && Date.now() - started < 1800000) {
      let status;
      try {
        status = await youtubeRequest('uploads/' + encodeURIComponent(youtubeJob));
        interrupted = 0;
      } catch (error) {
        if (error.status === 404) {
          clearYoutubeJob();
          youtubeUI.result.textContent = 'The upload status expired. Check YouTube Studio before retrying.';
          return;
        }
        if (++interrupted >= 3) throw error;
        await new Promise(resolve => setTimeout(resolve, 3000));
        continue;
      }
      if (status.state === 'complete') {
        clearYoutubeJob();
        showUploadedVideo(status, status.thumbnail_applied ? 'Thumbnail applied.' :
          status.thumbnail_warning || 'YouTube may still be processing the clip.');
        return;
      }
      if (status.state === 'failed') {
        clearYoutubeJob();
        youtubeUI.result.textContent = status.error || 'The YouTube upload failed.';
        if (status.code === 'YOUTUBE_ACCESS_BLOCKED' && retrySource && typeof offerSourceUpload === 'function') {
          showErrModal(status.error);
          offerSourceUpload(retrySource);
        }
        return;
      }
      if (status.state === 'thumbnail_processing') {
        showUploadedVideo(status, 'Waiting for YouTube to process the clip before applying the thumbnail.');
      } else {
        youtubeUI.result.textContent = {
          queued: 'Upload queued.',
          rendering: 'Rendering your clip with the selected captions and layout…',
          uploading: 'Sending the clip to YouTube…'
        }[status.state] || 'Preparing upload…';
      }
      await new Promise(resolve => setTimeout(resolve, 2500));
    }
    youtubeUI.result.textContent = 'The job is taking longer than expected. Check its status before trying another upload.';
  } catch (_) {
    youtubeUI.result.textContent = 'Could not check the upload. Use Check upload status to resume.';
  } finally {
    youtubeBusy = false;
    youtubeControls();
  }
}

async function startYoutubeUpload() {
  if (youtubeBusy || !youtubeChannel) return;
  if (youtubeJob) return monitorYoutubeUpload();
  if (!activeClip || !currentVideoData || !youtubeUI.form.reportValidity()) return;
  const clip = activeClip;
  const video = currentVideoData;
  const timestamp = youtubeUI.thumbnailTime.valueAsNumber;
  if (!Number.isFinite(timestamp) || timestamp < 0) {
    youtubeUI.thumbnailStatus.textContent = 'Enter a valid time in the original video.';
    youtubeUI.thumbnailTime.focus();
    return;
  }
  const title = clipExportTitle(clip);
  youtubeUI.title.value = title;
  const payload = {
    request_id: crypto.randomUUID(),
    channel_id: youtubeChannel.id,
    url: video.url || `https://www.youtube.com/watch?v=${activeVideoId}`,
    start: clip.start,
    duration: clip.end - clip.start,
    layout: currentLayout || 'split',
    subtitle_style: currentStyle || 'source',
    subtitles: (clip.has_real_captions || clip.subtitles_edited) ? (clip.subtitles || []) : [],
    video_subtitles: clip.video_subtitles || [],
    caption_source: clip.subtitles_edited ? 'provided' : 'auto',
    upload_id: video.upload_id || undefined,
    title,
    description: youtubeUI.description.value,
    thumbnail_time: timestamp,
    privacy: youtubeUI.privacy.value,
    made_for_kids: youtubeUI.audience.value === 'yes'
  };
  youtubeBusy = true;
  youtubeControls();
  youtubeUI.result.textContent = 'Starting your upload…';
  try {
    let job;
    try {
      job = await youtubeRequest('uploads', payload);
    } catch (error) {
      if (error.status) throw error;
      // Reuse the same request ID if the server queued the job but the response was lost.
      job = await youtubeRequest('uploads', payload);
    }
    youtubeJob = job.id;
    sessionStorage.setItem(youtubeJobKey, youtubeJob);
    await monitorYoutubeUpload(() => {
      youtubeUI.result.textContent = 'Source ready. Select Upload to YouTube to retry.';
    });
  } catch (error) {
    youtubeUI.result.textContent = error.status ? error.message : 'Could not confirm the upload request. Check YouTube Studio before retrying.';
    if ([401, 409].includes(error.status)) await refreshYoutubeConnection();
  } finally {
    youtubeBusy = false;
    youtubeControls();
  }
}

youtubeUI.form.addEventListener('submit', event => {
  event.preventDefault();
  startYoutubeUpload();
});
youtubeUI.upload.addEventListener('click', event => {
  if (!youtubeJob) return;
  event.preventDefault();
  startYoutubeUpload();
});
restoreYoutubeDraft();
refreshYoutubeConnection();
