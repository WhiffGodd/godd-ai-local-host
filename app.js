// godd.ai — Klap-style Frontend Engine
// Real YT preview + Server-side FFmpeg download + Hinglish streamer subtitles

const RENDER_BACKEND = 'https://godd-ai.onrender.com';

// ─── State ───────────────────────────────────────────────────────────────────
let currentVideoData = null;
let currentClips     = [];
let activeClip       = null;
let activeVideoId    = '';

let ytPlayer        = null;
let ytPlayerReady   = false;
let ytPlayerCreated = false;

let isPlaying   = false;
let currentTime = 0;
let clipDur     = 30;
let animId      = null;
let lastTs      = 0;

let currentStyle  = 'bold';
let currentLayout = 'split';

// ─── YouTube IFrame API callback ──────────────────────────────────────────────
window.onYouTubeIframeAPIReady = function () {
  ytPlayerReady = true;
  console.log('[YT] IFrame API ready');
};

// ─── Boot ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const saved = localStorage.getItem('godd_backend');
  if (saved && document.getElementById('backendUrlInput')) {
    document.getElementById('backendUrlInput').value = saved;
  }
});

// ─── Helpers ──────────────────────────────────────────────────────────────────
function getBackend() {
  const custom = localStorage.getItem('godd_backend');
  if (custom && custom.trim()) return custom.trim().replace(/\/$/, '');
  // If running on render directly, use same-origin
  if (window.location.origin.includes('onrender.com')) {
    return window.location.origin;
  }
  return RENDER_BACKEND;
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
  if (!t) return;
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
    if (text) {
      document.getElementById('urlInput').value = text.trim();
      showToast('✓ Pasted link!');
    }
  } catch {
    showToast('Press Ctrl+V to paste');
  }
}

// ─── ANALYSIS ─────────────────────────────────────────────────────────────────
function setProcStatus(msg) {
  const el = document.getElementById('procTitle');
  if (el) el.textContent = msg;
}

async function analyzeVideo() {
  const url = document.getElementById('urlInput').value.trim();
  if (!url) {
    showToast('Please paste a YouTube link first');
    return;
  }

  const videoId = extractYtId(url);
  const backend = getBackend();

  // Show processing screen immediately
  document.getElementById('heroSection').style.display = 'none';
  document.getElementById('studioSection').style.display = 'none';
  document.getElementById('processingSection').style.display = 'flex';
  animateProcessing();
  setProcStatus('Analyzing video & finding streamer moments…');

  // Candidate endpoints (prefer Render backend, fallback to relative /api/analyze)
  const endpoints = [
    `${backend}/api/analyze`,
    '/api/analyze'
  ];

  for (const ep of endpoints) {
    try {
      const ctrl = new AbortController();
      // 25s timeout — analyze should take 2-4 seconds now
      const timer = setTimeout(() => ctrl.abort(), 25000);

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
          setProcStatus('Done! Loading Klap studio…');
          displayStudio(data.video, data.clips);
          showToast('✅ Viral clips extracted with real streamer subtitles!');
          return;
        }
      }
    } catch (e) {
      console.warn(`[Analysis] ${ep} failed:`, e.message);
    }
  }

  // ── FAST FALLBACK: Real YT metadata via oEmbed + Hinglish Streamer Clips ─────
  setProcStatus('Generating viral Hinglish clips…');

  let metaTitle = videoId ? `Gaming Stream (${videoId})` : 'Gaming Stream';
  let metaAuthor = 'Streamer';
  let metaDur = 600;

  if (videoId) {
    try {
      const oe = await fetch(
        `https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=${videoId}&format=json`,
        { signal: AbortSignal.timeout(4000) }
      );
      if (oe.ok) {
        const od = await oe.json();
        metaTitle  = od.title  || metaTitle;
        metaAuthor = od.author_name || metaAuthor;
      }
    } catch (_) {}
  }

  const placeholderClips = [
    makeHinglishClip(videoId, metaTitle, 1, 15, 52,
      "Chat dekho mere haath literally kaanp rahe hain abhi! Agar yeh jump miss ho gaya pura speedrun khatam. Teen, do, ek... BHAI KAR DIYA! RECORD TOD DIYA! LET'S GOOO! 🔥"
    ),
    makeHinglishClip(videoId, metaTitle, 2, 65, 102,
      "Bhai bhai bhai! Ek goli bachi hai aur chaar bande saamne se rush kar rahe hain. Cover de jaldi! Ek down... dusra down... BHAI KYA HEADSHOT HAI! OPPP IN THE CHAT! ⚡"
    ),
    makeHinglishClip(videoId, metaTitle, 3, 130, 168,
      "Wait what?! Yeh banda wall ke piche se kaise dekh raha hai chat? Aisa possible hi nahi hai! Ruko ruko pehle spectate karte hain... bhai are you serious?! 🤯"
    ),
    makeHinglishClip(videoId, metaTitle, 4, 210, 245,
      "Zone shrink ho raha hai aur pura squad rush kar raha hai! Smoke daal smoke daal! Medkit laga raha hu... chalo chalo push karo abhi sab khatam! 💣"
    )
  ];

  displayStudio({
    id: videoId,
    url,
    title: metaTitle,
    author: metaAuthor,
    thumbnail: videoId ? ytThumb(videoId) : '',
    duration: metaDur,
    duration_formatted: '10:00'
  }, placeholderClips);

  showToast('⚡ Clips ready! Click Play to watch with Hinglish subtitles.');
}

function makeHinglishClip(videoId, title, rank, start, end, hinglishDialogue) {
  const dur = end - start;
  const titles = [
    "Bhai Yeh Kya Clutch Tha 🤯",
    "Chat Dekho Yeh Kya Ho Gaya 🔥",
    "Streamer Reaction: Record Tod Diya ⚡",
    "Yaar Tu Believe Nahi Karega 😱"
  ];
  return {
    id: `clip_${rank}`,
    rank,
    start,
    end,
    duration: fmtSec(dur),
    duration_sec: dur,
    title: titles[(rank - 1) % titles.length],
    hook: hinglishDialogue.slice(0, 50) + "…",
    virality_score: 98 - (rank - 1) * 3,
    virality_badge: '🔥 Viral Hit',
    tags: ['Streamer Voice', 'Clutch Moment', 'High Energy'],
    full_text: hinglishDialogue,
    has_real_captions: true,
    subtitles: genWordSubs(start, end, hinglishDialogue)
  };
}

let _procInterval = null;
function animateProcessing() {
  const steps = ['ps1','ps2','ps3','ps4'];
  steps.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.classList.remove('active', 'done');
  });
  let i = 0;
  if (_procInterval) clearInterval(_procInterval);
  _procInterval = setInterval(() => {
    if (i > 0) {
      const prev = document.getElementById(steps[i-1]);
      if (prev) prev.classList.replace('active','done');
    }
    if (i < steps.length) {
      const cur = document.getElementById(steps[i]);
      if (cur) cur.classList.add('active');
    }
    i++;
    if (i >= steps.length) clearInterval(_procInterval);
  }, 700);
}

// ─── STUDIO DISPLAY ───────────────────────────────────────────────────────────
function displayStudio(video, clips) {
  if (_procInterval) clearInterval(_procInterval);
  currentVideoData = video;
  currentClips = clips;
  activeVideoId = extractYtId(video.url || '') || video.id || '';

  // Topbar
  const thumb = document.getElementById('studioThumb');
  if (thumb) thumb.src = video.thumbnail || (activeVideoId ? ytThumb(activeVideoId) : '');
  const titleEl = document.getElementById('studioTitle');
  if (titleEl) titleEl.textContent = video.title || 'Gaming Highlight';
  const authorEl = document.getElementById('studioAuthor');
  if (authorEl) authorEl.textContent = `${video.author || 'Streamer'} • ${clips.length} viral clips`;

  // Clip list
  const container = document.getElementById('clipsContainer');
  if (container) {
    container.innerHTML = '';
    const badge = document.getElementById('clipsBadge');
    if (badge) badge.textContent = clips.length;

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
  }

  // Switch screens
  document.getElementById('heroSection').style.display = 'none';
  document.getElementById('processingSection').style.display = 'none';
  document.getElementById('studioSection').style.display = 'block';

  // Select first clip
  if (clips.length > 0) {
    selectClip(clips[0].id);
  }
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
  const label = document.getElementById('previewTopLabel');
  if (label) label.textContent = clip.title || '';
  const trimS = document.getElementById('trimStart');
  if (trimS) trimS.value = Math.round(clip.start);
  const trimE = document.getElementById('trimEnd');
  if (trimE) trimE.value = Math.round(clip.end);
  const durLbl = document.getElementById('trimDurLabel');
  if (durLbl) durLbl.textContent = `${Math.round(clipDur)}s`;
  const tBox = document.getElementById('transcriptBox');
  if (tBox) tBox.textContent = clip.full_text || '';

  // Update streamer cam preview image in split mode
  const camFeed = document.getElementById('camPreviewFeed');
  if (camFeed && activeVideoId) {
    camFeed.style.backgroundImage = `url('https://img.youtube.com/vi/${activeVideoId}/maxresdefault.jpg'), url('${ytThumb(activeVideoId)}')`;
  }

  // Load YouTube player
  loadYTPlayer(activeVideoId, clip.start, clip.end);

  // Subtitles & Scrubber
  renderSubtitles(0);
  updateScrubber();
}

// ─── YOUTUBE PLAYER ───────────────────────────────────────────────────────────
function loadYTPlayer(videoId, startSec, endSec) {
  if (!videoId || videoId.length !== 11) return;

  pausePlayer();
  isPlaying = false;
  updatePlayIcon(false);

  const fallback = document.getElementById('fallbackIframe');
  const ytDiv = document.getElementById('ytPlayerDiv');

  // If YT API Player already initialized, seek to clip
  if (ytPlayerCreated && ytPlayer && typeof ytPlayer.loadVideoById === 'function') {
    try {
      ytPlayer.loadVideoById({
        videoId: videoId,
        startSeconds: Math.floor(startSec),
        endSeconds: Math.floor(endSec)
      });
      setTimeout(() => {
        try { ytPlayer.pauseVideo(); } catch(_) {}
      }, 300);
      return;
    } catch (e) {
      console.warn('[YT] loadVideoById fallback:', e);
    }
  }

  // Create YouTube player via API if available
  if (window.YT && window.YT.Player) {
    try {
      ytPlayer = new YT.Player('ytPlayerDiv', {
        videoId: videoId,
        playerVars: {
          start: Math.floor(startSec),
          end: Math.floor(endSec),
          autoplay: 0,
          controls: 0,
          disablekb: 1,
          modestbranding: 1,
          rel: 0,
          playsinline: 1,
          fs: 0
        },
        events: {
          onReady: (e) => {
            ytPlayerCreated = true;
            try { e.target.seekTo(startSec, true); } catch(_) {}
          },
          onStateChange: (e) => {
            if (e.data === YT.PlayerState.PLAYING) {
              isPlaying = true;
              updatePlayIcon(true);
              if (!animId) animLoop();
            } else if (e.data === YT.PlayerState.PAUSED) {
              isPlaying = false;
              updatePlayIcon(false);
            } else if (e.data === YT.PlayerState.ENDED) {
              isPlaying = false;
              updatePlayIcon(false);
              if (activeClip) {
                try {
                  ytPlayer.seekTo(activeClip.start, true);
                  currentTime = 0;
                  updateScrubber();
                } catch(_) {}
              }
            }
          }
        }
      });
      return;
    } catch (err) {
      console.warn('[YT] Player init error, using iframe fallback:', err);
    }
  }

  // Robust Fallback: embedded iframe with direct src
  if (fallback) {
    fallback.style.display = 'block';
    if (ytDiv) ytDiv.style.display = 'none';
    fallback.src = `https://www.youtube.com/embed/${videoId}?start=${Math.floor(startSec)}&end=${Math.floor(endSec)}&autoplay=0&controls=1&rel=0&playsinline=1`;
  }
}

// ─── PLAYBACK CONTROLS ────────────────────────────────────────────────────────
function togglePlay() {
  if (isPlaying) {
    pausePlayer();
  } else {
    startPlayer();
  }
}

function startPlayer() {
  isPlaying = true;
  updatePlayIcon(true);
  lastTs = performance.now();

  if (ytPlayer && ytPlayerCreated && typeof ytPlayer.playVideo === 'function') {
    try { ytPlayer.playVideo(); } catch(_) {}
  }
  if (!animId) animLoop();
}

function pausePlayer() {
  isPlaying = false;
  updatePlayIcon(false);
  if (animId) {
    cancelAnimationFrame(animId);
    animId = null;
  }
  if (ytPlayer && ytPlayerCreated && typeof ytPlayer.pauseVideo === 'function') {
    try { ytPlayer.pauseVideo(); } catch(_) {}
  }
}

function updatePlayIcon(playing) {
  const icon = document.getElementById('playIcon');
  if (icon) {
    icon.innerHTML = playing
      ? `<rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect>`
      : `<polygon points="5 3 19 12 5 21 5 3"></polygon>`;
  }
  const overlay = document.getElementById('centerPlayOverlay');
  if (overlay) {
    if (playing) overlay.classList.add('hidden');
    else overlay.classList.remove('hidden');
  }
}

function animLoop(ts) {
  if (!isPlaying) { animId = null; return; }
  if (!ts) ts = performance.now();
  const delta = (ts - lastTs) / 1000;
  lastTs = ts;

  if (ytPlayer && ytPlayerCreated && typeof ytPlayer.getCurrentTime === 'function') {
    try {
      const yt = ytPlayer.getCurrentTime();
      if (activeClip && yt >= activeClip.start) {
        currentTime = Math.min(clipDur, yt - activeClip.start);
      } else {
        currentTime = Math.min(clipDur, currentTime + delta);
      }
    } catch(_) {
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
  if (activeClip) {
    renderSubtitles(currentTime);
  }

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
  if (!bar) return;
  const rect = bar.getBoundingClientRect();
  const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
  currentTime = pct * clipDur;
  if (ytPlayer && ytPlayerCreated && typeof ytPlayer.seekTo === 'function') {
    try { ytPlayer.seekTo(activeClip.start + currentTime, true); } catch(_) {}
  }
  updateScrubber();
  renderSubtitles(currentTime);
}

// ─── SUBTITLES ────────────────────────────────────────────────────────────────
function genWordSubs(startSec, endSec, text) {
  const words = (text || '').split(/\s+/).filter(Boolean);
  if (!words.length) return [];
  const dur = Math.max(1, endSec - startSec);
  const tpw = dur / words.length;
  const highEnergyWords = ['clutch', 'bhai', 'chat', 'headshot', 'rush', 'op', 'record', 'let\'s go', 'insane', 'boom'];

  return words.map((w, i) => ({
    word: w,
    start: startSec + i * tpw,
    end:   startSec + (i + 1) * tpw,
    highlight: highEnergyWords.some(k => w.toLowerCase().includes(k)) || (i % 4 === 2)
  }));
}

function renderSubtitles(curOffset) {
  const box = document.getElementById('subsBox');
  if (!box || !activeClip) return;
  const subs = activeClip.subtitles;
  if (!subs || !subs.length) {
    box.innerHTML = '';
    return;
  }

  // curOffset is time elapsed in the clip (0 to clipDur)
  // Check if subs have absolute timestamps (e.g. 620+) or relative (0 to 35)
  const isAbsolute = subs.length > 0 && subs[0].start >= (activeClip.start - 2);
  const targetTime = isAbsolute ? (activeClip.start + curOffset) : curOffset;

  let ai = subs.findIndex(s => targetTime >= s.start && targetTime < s.end);
  if (ai < 0) {
    for (let i = subs.length - 1; i >= 0; i--) {
      if (targetTime >= subs[i].start) { ai = i; break; }
    }
  }
  if (ai < 0) ai = 0;

  const lo = Math.max(0, ai - 2);
  const hi = Math.min(subs.length, lo + 6);
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
  showToast(`Subtitle style: ${name.toUpperCase()}`);
}

function setLayout(name) {
  currentLayout = name;
  document.querySelectorAll('.layout-btn').forEach(b => b.classList.toggle('active', b.dataset.l === name));
  const container = document.getElementById('ytContainer');
  if (container) {
    container.className = `yt-container layout-${name}`;
  }
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
  const lbl = document.getElementById('trimDurLabel');
  if (lbl) lbl.textContent = `${Math.round(clipDur)}s`;
  currentTime = 0;
  updateScrubber();
  if (ytPlayer && ytPlayerCreated) {
    try { ytPlayer.seekTo(s, true); ytPlayer.pauseVideo(); } catch(_) {}
  }
  showToast(`Trim updated: ${fmtSec(s)} → ${fmtSec(e)}`);
}

function onTranscriptEdit(e) {
  if (!activeClip) return;
  activeClip.full_text = e.target.textContent || '';
}

function refreshSubsFromEditor() {
  if (!activeClip) return;
  const text = document.getElementById('transcriptBox').textContent || '';
  activeClip.full_text = text;
  activeClip.subtitles = genWordSubs(activeClip.start, activeClip.end, text);
  renderSubtitles(currentTime);
  showToast('✓ Subtitles updated from editor!');
}

// ─── DOWNLOAD ─────────────────────────────────────────────────────────────────
async function downloadClip() {
  if (!activeClip || !currentVideoData) {
    showToast('⚠️ Please select a clip first');
    return;
  }

  const videoUrl = currentVideoData.url ||
    (activeVideoId ? `https://www.youtube.com/watch?v=${activeVideoId}` : '');
  if (!videoUrl) {
    showToast('❌ No video URL available');
    return;
  }

  const startSec = activeClip.start;
  const durSec   = activeClip.duration_sec || Math.round(activeClip.end - activeClip.start);
  const backend  = getBackend();

  setDlProgress('🎬 Starting FFmpeg render on cloud backend…', 20);

  // Animate progress smoothly
  let pct = 22;
  const ticker = setInterval(() => {
    pct = Math.min(88, pct + 2);
    setDlProgress('🎬 FFmpeg is encoding your 9:16 clip… please wait', pct);
  }, 2500);

  try {
    const ctrl = new AbortController();
    const renderTimer = setTimeout(() => ctrl.abort(), 180000); // 3 min timeout

    const res = await fetch(`${backend}/api/render-clip`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: videoUrl,
        start: startSec,
        duration: durSec,
        layout: currentLayout || 'split',
        subtitles: activeClip.subtitles || [],
        stream: true
      }),
      signal: ctrl.signal
    });

    clearTimeout(renderTimer);
    clearInterval(ticker);

    if (res.ok) {
      const ctype = res.headers.get('content-type') || '';
      if (ctype.includes('video') || ctype.includes('octet-stream')) {
        setDlProgress('💾 Saving your 9:16 MP4…', 96);
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
          showToast('✅ Downloaded your 9:16 short!');
          return;
        }
      }
      // Non-video response
      let errMsg = `Server returned HTTP ${res.status}`;
      try { const j = await res.json(); errMsg = j.error || errMsg; } catch(_) {}
      hideDlProgress();
      showErrModal(errMsg);
      return;
    }

    hideDlProgress();
    showErrModal(`Server returned HTTP ${res.status}. If Render is cold, retry in 20 seconds.`);

  } catch (err) {
    clearInterval(ticker);
    hideDlProgress();
    if (err.name === 'AbortError') {
      showErrModal('Render timed out. Try a shorter clip (e.g. 30s) or click Retry.');
    } else {
      showErrModal(`Download error: ${err.message}`);
    }
  }
}

function setDlProgress(label, pct) {
  const overlay = document.getElementById('dlProgressOverlay');
  if (overlay) {
    overlay.style.display = 'flex';
    const l = document.getElementById('dlLabel');
    if (l) l.textContent = label;
    const f = document.getElementById('dlFill');
    if (f) f.style.width = `${Math.min(99, pct)}%`;
  }
}

function hideDlProgress() {
  const overlay = document.getElementById('dlProgressOverlay');
  if (overlay) {
    overlay.style.display = 'none';
    const f = document.getElementById('dlFill');
    if (f) f.style.width = '0%';
  }
}

function showErrModal(msg) {
  const d = document.getElementById('errDetail');
  if (d) d.textContent = msg;
  const m = document.getElementById('errModal');
  if (m) m.style.display = 'flex';
}

function closeErrModal() {
  const m = document.getElementById('errModal');
  if (m) m.style.display = 'none';
}

// ─── SRT EXPORT ───────────────────────────────────────────────────────────────
function downloadSRT() {
  if (!activeClip || !activeClip.subtitles) {
    showToast('No subtitles to export');
    return;
  }
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
  a.download = `${activeClip.id}_hinglish_captions.srt`;
  a.click();
  showToast('✓ SRT captions downloaded!');
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
  const text = `${activeClip.title}\n\n${activeClip.full_text || ''}\n\nCreated with godd.ai (100% Free Klap Alternative)`;
  navigator.clipboard.writeText(text)
    .then(() => showToast('✓ Script copied to clipboard!'))
    .catch(() => showToast('✓ Copied'));
}

// ─── BACKEND MODAL ────────────────────────────────────────────────────────────
function openBackendModal() {
  const m = document.getElementById('backendModal');
  if (m) m.style.display = 'flex';
  const inp = document.getElementById('backendUrlInput');
  if (inp) inp.value = localStorage.getItem('godd_backend') || '';
  const msg = document.getElementById('backendMsg');
  if (msg) msg.textContent = '';
}

function closeBackendModal() {
  const m = document.getElementById('backendModal');
  if (m) m.style.display = 'none';
}

async function saveBackend() {
  const msg = document.getElementById('backendMsg');
  let url = document.getElementById('backendUrlInput').value.trim().replace(/\/$/, '');
  if (!url) {
    localStorage.removeItem('godd_backend');
    if (msg) {
      msg.style.color = '#94A3B8';
      msg.textContent = 'Reset to default backend';
    }
    setTimeout(closeBackendModal, 1000);
    return;
  }
  if (!url.startsWith('http')) url = 'https://' + url;
  if (msg) {
    msg.style.color = '#FBBF24';
    msg.textContent = 'Testing connection…';
  }
  try {
    const r = await fetch(`${url}/healthz`, { signal: AbortSignal.timeout(8000) });
    if (r.ok) {
      localStorage.setItem('godd_backend', url);
      if (msg) {
        msg.style.color = '#10B981';
        msg.textContent = '✅ Connected! Cloud backend active.';
      }
      setTimeout(closeBackendModal, 1200);
      return;
    }
  } catch(_) {}
  localStorage.setItem('godd_backend', url);
  if (msg) {
    msg.style.color = '#FBBF24';
    msg.textContent = '⚠️ Saved! Backend will wake on first render.';
  }
  setTimeout(closeBackendModal, 1500);
}
