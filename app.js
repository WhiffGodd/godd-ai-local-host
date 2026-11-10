// godd.ai — Klap-style Frontend Engine
// Real YT preview + Server-side FFmpeg download + Whisper subtitles

const RENDER_BACKEND = 'https://godd-ai.onrender.com';

// ─── State ───────────────────────────────────────────────────────────────────
let currentVideoData = null;
let currentClips     = [];
let activeClip       = null;
let activeVideoId    = '';

let ytPlayer        = null;
let ytPlayerReady   = false;
let ytPlayerCreated = false;

let isPlaying  = false;
let currentTime = 0;
let clipDur    = 30;
let animId     = null;
let lastTs     = 0;

let currentStyle  = 'bold';
let currentLayout = 'crop';

// ─── YouTube IFrame API callback ──────────────────────────────────────────────
window.onYouTubeIframeAPIReady = function () {
  ytPlayerReady = true;
  console.log('[YT] IFrame API ready');
};

// ─── Boot ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Load saved backend URL
  const saved = localStorage.getItem('godd_backend');
  if (saved) document.getElementById('backendUrlInput').value = saved;
});

// ─── Helpers ──────────────────────────────────────────────────────────────────
function getBackend() {
  return (localStorage.getItem('godd_backend') || RENDER_BACKEND).replace(/\/$/, '');
}

function extractYtId(url) {
  if (!url) return '';
  const patterns = [
    /(?:v=|\/v\/|embed\/|shorts\/|live\/)([0-9A-Za-z_-]{11})/,
    /youtu\.be\/([0-9A-Za-z_-]{11})/,
    /^([0-9A-Za-z_-]{11})$/
  ];
  for (const p of patterns) {
    const m = url.match(p);
    if (m) return m[1];
  }
  return '';
}

function ytThumb(videoId) {
  return `https://img.youtube.com/vi/${videoId}/mqdefault.jpg`;
}

function fmtSec(s) {
  s = Math.max(0, Math.floor(s || 0));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2600);
}

function goHome() {
  pausePlayer();
  document.getElementById('heroSection').style.display = '';
  document.getElementById('processingSection').style.display = 'none';
  document.getElementById('studioSection').style.display = 'none';
}

function loadDemo() {
  document.getElementById('urlInput').value = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ';
  analyzeVideo();
}

async function pasteClip() {
  try {
    const text = await navigator.clipboard.readText();
    if (text) { document.getElementById('urlInput').value = text.trim(); showToast('✓ Pasted!'); }
  } catch { showToast('Press Ctrl+V to paste'); }
}

// ─── ANALYSIS ─────────────────────────────────────────────────────────────────
async function analyzeVideo() {
  const url = document.getElementById('urlInput').value.trim();
  if (!url) { showToast('Please paste a YouTube link first'); return; }

  const videoId = extractYtId(url);

  // Show processing screen
  document.getElementById('heroSection').style.display = 'none';
  document.getElementById('studioSection').style.display = 'none';
  document.getElementById('processingSection').style.display = '';
  animateProcessing();

  const endpoints = [`${getBackend()}/api/analyze`, '/api/analyze'];

  for (const ep of endpoints) {
    try {
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), 120000);
      const res = await fetch(ep, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
        signal: ctrl.signal
      });
      clearTimeout(timer);
      if (res.ok) {
        const data = await res.json();
        if (data.success && Array.isArray(data.clips) && data.clips.length > 0) {
          displayStudio(data.video, data.clips);
          return;
        }
      }
    } catch (e) {
      console.warn(`[Analysis] ${ep} failed:`, e.message);
    }
  }

  // Fallback: generate placeholder clips
  const title = videoId ? `YouTube Video (${videoId})` : 'Video';
  const dur = 600;
  const fakeClips = [
    makeClip(videoId, title, 1, 15, 55),
    makeClip(videoId, title, 2, 70, 108),
    makeClip(videoId, title, 3, 130, 168),
  ];
  displayStudio({
    id: videoId, url, title, author: 'Creator',
    thumbnail: videoId ? ytThumb(videoId) : '',
    duration: dur, duration_formatted: '10:00'
  }, fakeClips);
  showToast('ℹ️ Backend offline — showing placeholder clips. Edit subtitles manually.');
}

function makeClip(videoId, title, rank, start, end) {
  const dur = end - start;
  return {
    id: `clip_${rank}`, rank, start, end,
    duration: fmtSec(dur), duration_sec: dur,
    title: `${title} — Moment #${rank} 🔥`,
    hook: 'Click to edit this subtitle text…',
    virality_score: 95 - rank * 2,
    virality_badge: '🔥 Viral Hit',
    tags: ['Highlight'],
    full_text: 'Yaar, kya clutch tha yeh moment! Chat dekho — literally kaanp raha hoon. Aisa pehle kabhi nahi hua. Click here to edit these subtitles.',
    has_real_captions: false,
    subtitles: genWordSubs(start, end, 'Yaar kya clutch tha yeh moment Chat dekho literally kaanp raha hoon click to edit subtitles')
  };
}

let _procInterval = null;
function animateProcessing() {
  const steps = ['ps1','ps2','ps3','ps4'];
  steps.forEach(id => {
    const el = document.getElementById(id);
    el.classList.remove('active', 'done');
  });
  let i = 0;
  if (_procInterval) clearInterval(_procInterval);
  _procInterval = setInterval(() => {
    if (i > 0) document.getElementById(steps[i-1])?.classList.replace('active','done');
    if (i < steps.length) document.getElementById(steps[i])?.classList.add('active');
    i++;
    if (i >= steps.length) clearInterval(_procInterval);
  }, 900);
}

// ─── STUDIO DISPLAY ───────────────────────────────────────────────────────────
function displayStudio(video, clips) {
  if (_procInterval) clearInterval(_procInterval);
  currentVideoData = video;
  currentClips = clips;
  activeVideoId = extractYtId(video.url || '') || video.id || '';

  // Topbar
  const thumb = document.getElementById('studioThumb');
  thumb.src = video.thumbnail || (activeVideoId ? ytThumb(activeVideoId) : '');
  document.getElementById('studioTitle').textContent  = video.title || 'Video';
  document.getElementById('studioAuthor').textContent = video.author || 'Creator';
  document.getElementById('studioClipCount').textContent = `${clips.length} clips`;

  // Clip cards
  const container = document.getElementById('clipsContainer');
  container.innerHTML = '';
  document.getElementById('clipsBadge').textContent = clips.length;

  clips.forEach((clip, idx) => {
    const thumbUrl = activeVideoId ? ytThumb(activeVideoId) : '';
    const card = document.createElement('div');
    card.className = 'clip-card' + (idx === 0 ? ' selected' : '');
    card.id = `card_${clip.id}`;
    card.onclick = () => selectClip(clip.id);
    card.innerHTML = `
      <div class="clip-thumb-wrap">
        ${thumbUrl ? `<img src="${thumbUrl}" alt="" loading="lazy">` : ''}
        <span class="clip-score-pill">🔥 ${clip.virality_score}</span>
        <span class="clip-dur-pill">⏱ ${clip.duration}</span>
      </div>
      <div class="clip-info">
        <div class="clip-info-title">${clip.title}</div>
        <div class="clip-info-tags">${(clip.tags||[]).map(t=>`<span class="clip-tag">${t}</span>`).join('')}</div>
      </div>`;
    container.appendChild(card);
  });

  // Show studio
  document.getElementById('heroSection').style.display = 'none';
  document.getElementById('processingSection').style.display = 'none';
  document.getElementById('studioSection').style.display = '';

  // Select first clip
  selectClip(clips[0].id);
}

// ─── SELECT CLIP ──────────────────────────────────────────────────────────────
function selectClip(clipId) {
  const clip = currentClips.find(c => c.id === clipId);
  if (!clip) return;
  activeClip = clip;
  clipDur = Math.max(1, clip.end - clip.start);
  currentTime = 0;

  // Highlight card
  document.querySelectorAll('.clip-card').forEach(c => c.classList.remove('selected'));
  const selCard = document.getElementById(`card_${clipId}`);
  if (selCard) selCard.classList.add('selected');

  // Update controls
  document.getElementById('previewTopLabel').textContent = clip.title || '';
  document.getElementById('trimStart').value = Math.round(clip.start);
  document.getElementById('trimEnd').value   = Math.round(clip.end);
  document.getElementById('trimDurLabel').textContent = `${Math.round(clipDur)}s`;
  document.getElementById('transcriptBox').textContent = clip.full_text || '';

  // Load YouTube player
  loadYTPlayer(activeVideoId, clip.start, clip.end);

  // Update subtitles immediately
  renderSubtitles(clip.start);
  updateScrubber();
}

// ─── YOUTUBE PLAYER ───────────────────────────────────────────────────────────
function loadYTPlayer(videoId, startSec, endSec) {
  if (!videoId || videoId.length !== 11) return;

  pausePlayer();
  isPlaying = false;
  updatePlayIcon(false);

  if (ytPlayerCreated && ytPlayer && typeof ytPlayer.loadVideoById === 'function') {
    // Reuse existing player — load new clip
    try {
      ytPlayer.loadVideoById({
        videoId: videoId,
        startSeconds: Math.floor(startSec),
        endSeconds: Math.floor(endSec)
      });
      setTimeout(() => { try { ytPlayer.pauseVideo(); } catch(e){} }, 400);
    } catch(e) { console.warn('[YT] loadVideoById error:', e); }
    return;
  }

  // Create player for first time
  const tryCreate = () => {
    if (!window.YT || !window.YT.Player) {
      setTimeout(tryCreate, 300);
      return;
    }
    ytPlayer = new YT.Player('ytPlayerDiv', {
      videoId: videoId,
      playerVars: {
        start:          Math.floor(startSec),
        end:            Math.floor(endSec),
        autoplay:       0,
        controls:       0,
        disablekb:      1,
        modestbranding: 1,
        rel:            0,
        playsinline:    1,
        fs:             0,
        iv_load_policy: 3
      },
      events: {
        onReady: (e) => {
          ytPlayerCreated = true;
          e.target.seekTo(startSec, true);
          setTimeout(() => { try { e.target.pauseVideo(); } catch(_){} }, 300);
        },
        onStateChange: (e) => {
          if (e.data === YT.PlayerState.PLAYING) {
            isPlaying = true; updatePlayIcon(true);
            if (!animId) animLoop();
          } else if (e.data === YT.PlayerState.PAUSED || e.data === YT.PlayerState.ENDED) {
            isPlaying = false; updatePlayIcon(false);
            if (e.data === YT.PlayerState.ENDED && activeClip) {
              // Loop clip
              setTimeout(() => {
                try { ytPlayer.seekTo(activeClip.start, true); ytPlayer.pauseVideo(); } catch(_){}
                currentTime = 0; updateScrubber();
              }, 300);
            }
          }
        }
      }
    });
  };
  tryCreate();
}

// ─── PLAYBACK CONTROLS ────────────────────────────────────────────────────────
function togglePlay() {
  if (isPlaying) pausePlayer();
  else startPlayer();
}

function startPlayer() {
  isPlaying = true;
  updatePlayIcon(true);
  lastTs = performance.now();
  if (ytPlayer && ytPlayerCreated && typeof ytPlayer.playVideo === 'function') {
    try { ytPlayer.playVideo(); } catch(e){}
  }
  if (!animId) animLoop();
}

function pausePlayer() {
  isPlaying = false;
  updatePlayIcon(false);
  if (animId) { cancelAnimationFrame(animId); animId = null; }
  if (ytPlayer && ytPlayerCreated && typeof ytPlayer.pauseVideo === 'function') {
    try { ytPlayer.pauseVideo(); } catch(e){}
  }
}

function updatePlayIcon(playing) {
  const icon = document.getElementById('playIcon');
  if (!icon) return;
  icon.innerHTML = playing
    ? `<rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect>`
    : `<polygon points="5 3 19 12 5 21 5 3"></polygon>`;
}

function animLoop(ts) {
  if (!isPlaying) { animId = null; return; }
  if (!ts) ts = performance.now();
  const delta = (ts - lastTs) / 1000;
  lastTs = ts;

  // Sync with YT player if available
  if (ytPlayer && ytPlayerCreated && typeof ytPlayer.getCurrentTime === 'function') {
    try {
      const yt = ytPlayer.getCurrentTime();
      if (activeClip && yt >= activeClip.start) {
        currentTime = Math.min(clipDur, yt - activeClip.start);
      } else {
        currentTime = Math.min(clipDur, currentTime + delta);
      }
    } catch(e) {
      currentTime = Math.min(clipDur, currentTime + delta);
    }
  } else {
    currentTime = Math.min(clipDur, currentTime + delta);
  }

  if (currentTime >= clipDur) {
    currentTime = clipDur;
    pausePlayer();
    return;
  }

  updateScrubber();
  if (activeClip) renderSubtitles(activeClip.start + currentTime);

  animId = requestAnimationFrame(animLoop);
}

function updateScrubber() {
  if (!activeClip) return;
  const pct = clipDur > 0 ? (currentTime / clipDur) * 100 : 0;
  const fill = document.getElementById('scrubFill');
  if (fill) fill.style.width = `${Math.min(100, pct)}%`;
  const lbl = document.getElementById('ctrlTime');
  if (lbl) lbl.textContent = `${fmtSec(currentTime)} / ${fmtSec(clipDur)}`;
}

function scrubSeek(e) {
  if (!activeClip) return;
  const bar = document.getElementById('scrubber');
  const rect = bar.getBoundingClientRect();
  const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
  currentTime = pct * clipDur;
  if (ytPlayer && ytPlayerCreated && typeof ytPlayer.seekTo === 'function') {
    try { ytPlayer.seekTo(activeClip.start + currentTime, true); } catch(e){}
  }
  updateScrubber();
  renderSubtitles(activeClip.start + currentTime);
}

// ─── SUBTITLES ────────────────────────────────────────────────────────────────
function genWordSubs(startSec, endSec, text) {
  const words = (text || '').split(/\s+/).filter(Boolean);
  if (!words.length) return [];
  const dur = Math.max(1, endSec - startSec);
  const tpw = dur / words.length;
  return words.map((w, i) => ({
    word: w,
    start: startSec + i * tpw,
    end:   startSec + (i + 1) * tpw,
    highlight: i % 5 === 2
  }));
}

function renderSubtitles(absTime) {
  const box = document.getElementById('subsBox');
  if (!box || !activeClip) return;
  const subs = activeClip.subtitles;
  if (!subs || !subs.length) { box.innerHTML = ''; return; }

  // Find active word index
  let ai = subs.findIndex(s => absTime >= s.start && absTime < s.end);
  if (ai < 0) {
    for (let i = subs.length - 1; i >= 0; i--) {
      if (absTime >= subs[i].start) { ai = i; break; }
    }
  }
  if (ai < 0) ai = 0;

  // Show window of 5 words centred on active
  const lo = Math.max(0, ai - 1);
  const hi = Math.min(subs.length, lo + 5);
  const visible = subs.slice(lo, hi);

  box.innerHTML = visible.map((s, idx) => {
    const isActive = (lo + idx) === ai;
    const isHl     = s.highlight && !isActive;
    return `<span class="sw${isActive ? ' active' : ''}${isHl ? ' hl' : ''}">${escHtml(s.word)}</span>`;
  }).join(' ');
}

function escHtml(s) {
  return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function setStyle(name) {
  currentStyle = name;
  document.querySelectorAll('.style-btn').forEach(b => b.classList.toggle('active', b.dataset.s === name));
  const box = document.getElementById('subsBox');
  if (box) box.className = `subs-box s-${name}`;
}

function setLayout(name) {
  currentLayout = name;
  document.querySelectorAll('.layout-btn').forEach(b => b.classList.toggle('active', b.dataset.l === name));
  showToast(`Layout: ${name.toUpperCase()}`);
}

function applyTrim() {
  if (!activeClip) return;
  const s = parseFloat(document.getElementById('trimStart').value) || 0;
  const e = parseFloat(document.getElementById('trimEnd').value)   || s + 30;
  if (e <= s) return;
  activeClip.start = s;
  activeClip.end   = e;
  clipDur = e - s;
  document.getElementById('trimDurLabel').textContent = `${Math.round(clipDur)}s`;
  currentTime = 0;
  updateScrubber();
  if (ytPlayer && ytPlayerCreated) {
    try { ytPlayer.seekTo(s, true); ytPlayer.pauseVideo(); } catch(_){}
  }
  showToast(`Trim: ${fmtSec(s)} → ${fmtSec(e)}`);
}

function onTranscriptEdit(e) {
  if (!activeClip) return;
  const text = e.target.textContent || '';
  activeClip.full_text = text;
  // Don't regen subs live — user clicks refresh button
}

function refreshSubsFromEditor() {
  if (!activeClip) return;
  const text = document.getElementById('transcriptBox').textContent || '';
  activeClip.full_text = text;
  activeClip.subtitles = genWordSubs(activeClip.start, activeClip.end, text);
  renderSubtitles(activeClip.start + currentTime);
  showToast('✓ Subtitles updated!');
}

// ─── DOWNLOAD (THE CRITICAL FUNCTION) ────────────────────────────────────────
async function downloadClip() {
  if (!activeClip || !currentVideoData) {
    showToast('⚠️ Please select a clip first');
    return;
  }

  const videoUrl = currentVideoData.url ||
    (activeVideoId ? `https://www.youtube.com/watch?v=${activeVideoId}` : '');
  if (!videoUrl) { showToast('❌ No video URL available'); return; }

  const startSec = activeClip.start;
  const durSec   = activeClip.duration_sec || Math.round(activeClip.end - activeClip.start);
  const backend  = getBackend();

  // ── STEP 1: Wake the Render server ─────────────────────────────────────────
  setDlProgress('⏳ Waking up server… (Render free tier sleeps after idle)', 8);

  let serverAwake = false;
  try {
    const ctrl = new AbortController();
    const wakeTimer = setTimeout(() => ctrl.abort(), 70000); // 70s to wake
    const r = await fetch(`${backend}/healthz`, { signal: ctrl.signal });
    clearTimeout(wakeTimer);
    if (r.ok) serverAwake = true;
  } catch (e) {
    console.warn('[Wake] healthz failed:', e.message);
  }

  if (!serverAwake) {
    setDlProgress('⏳ Server still waking — waiting 15 more seconds…', 18);
    await sleep(15000);
  }

  // ── STEP 2: Request FFmpeg render ───────────────────────────────────────────
  setDlProgress('🎬 Server ready! Sending clip to FFmpeg…', 32);

  // Animate progress ticking while we wait
  let pct = 34;
  const ticker = setInterval(() => {
    pct = Math.min(89, pct + 1.2);
    setDlProgress('🎬 FFmpeg is encoding your 9:16 clip… please wait', pct);
  }, 3500);

  try {
    const ctrl2 = new AbortController();
    const renderTimer = setTimeout(() => ctrl2.abort(), 190000); // 190s timeout

    const res = await fetch(`${backend}/api/render-clip`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: videoUrl,
        start: startSec,
        duration: durSec,
        layout: currentLayout,
        stream: true
      }),
      signal: ctrl2.signal
    });

    clearTimeout(renderTimer);
    clearInterval(ticker);

    if (res.ok) {
      const ctype = res.headers.get('content-type') || '';
      if (ctype.includes('video') || ctype.includes('octet-stream')) {
        setDlProgress('💾 Saving MP4 to your device…', 94);
        const blob = await res.blob();
        if (blob.size > 5000) {
          const a = document.createElement('a');
          a.href = URL.createObjectURL(blob);
          const name = (activeClip.title || activeClip.id || 'clip')
            .replace(/[^a-z0-9]/gi, '_').toLowerCase();
          a.download = `godd_ai_${name}.mp4`;
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          setTimeout(() => URL.revokeObjectURL(a.href), 10000);
          hideDlProgress();
          showToast('✅ Your 9:16 clip is downloaded!');
          return;
        }
        // Empty blob
        clearInterval(ticker);
        hideDlProgress();
        showErrModal('Server returned an empty video file. Please retry.');
        return;
      }
      // Non-video response — parse error message
      clearInterval(ticker);
      let errMsg = `Server error (HTTP ${res.status})`;
      try { const j = await res.json(); errMsg = j.error || errMsg; } catch(_){}
      hideDlProgress();
      showErrModal(errMsg);
      return;
    }

    clearInterval(ticker);
    hideDlProgress();
    showErrModal(`Server returned HTTP ${res.status}. Try again in 30 seconds.`);

  } catch (err) {
    clearInterval(ticker);
    hideDlProgress();
    if (err.name === 'AbortError') {
      showErrModal('Render timed out (190s). The clip may be too long. Try a shorter segment or retry.');
    } else {
      showErrModal(`Download failed: ${err.message}`);
    }
  }
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// Progress overlay helpers
function setDlProgress(label, pct) {
  const overlay = document.getElementById('dlProgressOverlay');
  overlay.style.display = 'flex';
  document.getElementById('dlLabel').textContent = label;
  document.getElementById('dlFill').style.width  = `${Math.min(99, pct)}%`;
}
function hideDlProgress() {
  document.getElementById('dlProgressOverlay').style.display = 'none';
  document.getElementById('dlFill').style.width = '0%';
}

// Error modal
function showErrModal(msg) {
  document.getElementById('errDetail').textContent = msg;
  document.getElementById('errModal').style.display = 'flex';
}
function closeErrModal() {
  document.getElementById('errModal').style.display = 'none';
}

// ─── SRT EXPORT ───────────────────────────────────────────────────────────────
function downloadSRT() {
  if (!activeClip || !activeClip.subtitles) { showToast('No subtitles to export'); return; }
  const subs = activeClip.subtitles;
  const lines = [];
  const chunk = 4;
  for (let i = 0; i < subs.length; i += chunk) {
    const g = subs.slice(i, i + chunk);
    lines.push(
      Math.floor(i/chunk) + 1,
      `${srtTime(g[0].start)} --> ${srtTime(g[g.length-1].end)}`,
      g.map(s => s.word).join(' '),
      ''
    );
  }
  const blob = new Blob([lines.join('\n')], { type: 'text/plain;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `${activeClip.id}_captions.srt`;
  a.click();
  showToast('✓ SRT downloaded!');
}

function srtTime(s) {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const ss = Math.floor(s % 60);
  const ms = Math.floor((s - Math.floor(s)) * 1000);
  return `${pad(h)}:${pad(m)}:${pad(ss)},${pad(ms, 3)}`;
}
function pad(n, len = 2) { return String(n).padStart(len, '0'); }

// ─── COPY SCRIPT ──────────────────────────────────────────────────────────────
function copyScript() {
  if (!activeClip) return;
  const text = `${activeClip.title}\n\n${activeClip.full_text || ''}\n\nMade with godd.ai (Free)`;
  navigator.clipboard.writeText(text)
    .then(() => showToast('✓ Script copied!'))
    .catch(() => showToast('✓ Copied'));
}

// ─── BACKEND MODAL ────────────────────────────────────────────────────────────
function openBackendModal() {
  document.getElementById('backendModal').style.display = 'flex';
  document.getElementById('backendUrlInput').value = localStorage.getItem('godd_backend') || '';
  document.getElementById('backendMsg').textContent = '';
}
function closeBackendModal() {
  document.getElementById('backendModal').style.display = 'none';
}
async function saveBackend() {
  const msg = document.getElementById('backendMsg');
  let url = document.getElementById('backendUrlInput').value.trim().replace(/\/$/, '');
  if (!url) {
    localStorage.removeItem('godd_backend');
    msg.style.color = '#94A3B8';
    msg.textContent = 'Reset to default backend';
    setTimeout(closeBackendModal, 1200);
    return;
  }
  if (!url.startsWith('http')) url = 'https://' + url;
  msg.style.color = '#FBBF24';
  msg.textContent = 'Testing connection…';
  try {
    const r = await fetch(`${url}/healthz`, { signal: AbortSignal.timeout(10000) });
    if (r.ok) {
      localStorage.setItem('godd_backend', url);
      msg.style.color = '#10B981';
      msg.textContent = '✅ Connected! Backend saved.';
      setTimeout(closeBackendModal, 1200);
      return;
    }
  } catch(_) {}
  localStorage.setItem('godd_backend', url);
  msg.style.color = '#FBBF24';
  msg.textContent = '⚠️ Saved (server may be sleeping — it will wake on use)';
  setTimeout(closeBackendModal, 2000);
}
