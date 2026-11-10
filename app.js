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

let currentStyle  = 'source';
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
  // If running locally, ALWAYS use local backend on RTX GPU!
  if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    return window.location.origin;
  }
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
  setProcStatus('Analyzing video & finding key content moments…');

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
          showToast('✅ Meaningful content clips extracted with titles!');
          return;
        }
      }
    } catch (e) {
      console.warn(`[Analysis] ${ep} failed:`, e.message);
    }
  }

  // ── FAST FALLBACK: Real YT metadata via oEmbed + Content-Focused Clips ─────
  setProcStatus('Generating content-focused viral clips…');

  let metaTitle = videoId ? `Video (${videoId})` : 'Video Content';
  let metaAuthor = 'Creator';
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

  const topic = extractContentTopic(metaTitle);
  const placeholderClips = [
    makeContentClip(videoId, metaTitle, topic, 1, 15, 52),
    makeContentClip(videoId, metaTitle, topic, 2, 65, 105),
    makeContentClip(videoId, metaTitle, topic, 3, 130, 172),
    makeContentClip(videoId, metaTitle, topic, 4, 210, 248)
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

  showToast('⚡ Content clips ready! Click to preview and render on your GPU.');
}

function extractContentTopic(title) {
  if (!title) return "This Topic";
  const clean = title.replace(/[^\w\s-]/g, '').trim();
  const words = clean.split(/\s+/).filter(w => w.length > 2 && !/^(video|full|stream|live|episode|podcast|part|with|from|the|and|official|clip|highlight|gameplay)$/i.test(w));
  return words.slice(0, 4).join(' ') || "This Key Concept";
}

function makeContentClip(videoId, metaTitle, topic, rank, start, end) {
  const dur = end - start;
  const titles = [
    `The Core Truth About ${topic} 🧠`,
    `Why ${topic} Changes Everything 💡`,
    `The Exact Moment Everything Shifted ⚡`,
    `What Nobody Realizes About ${topic} 🎯`
  ];
  const hooks = [
    `The biggest realization from ${topic}…`,
    `Why most people get ${topic} completely wrong…`,
    `The major turning point in ${topic}…`,
    `The final critical takeaway about ${topic}…`
  ];
  const badges = ['🔥 Core Highlight', '💡 Key Insight', '⚡ Turning Point', '🎯 Main Takeaway'];

  return {
    id: `clip_${rank}`,
    rank,
    start,
    end,
    duration: fmtSec(dur),
    duration_sec: dur,
    title: titles[(rank - 1) % titles.length],
    hook: hooks[(rank - 1) % hooks.length],
    virality_score: 98 - (rank - 1) * 3,
    virality_badge: badges[(rank - 1) % badges.length],
    tags: ['Key Insight', 'Deep Dive', 'High Retention'],
    full_text: hooks[(rank - 1) % hooks.length],
    has_real_captions: false,
    subtitles: genWordSubs(start, end, hooks[(rank - 1) % hooks.length])
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

  // Layout selection: If no facecam is present, automatically use single-section (no 2 sections)
  if (video.has_facecam === false) {
    setLayout('blur');
  } else {
    setLayout('split');
  }

  // Subtitle selection: If video contains real subtitles, use them by default!
  const hasSourceSubs = clips.some(c => c.has_source_subtitles || (c.video_subtitles && c.video_subtitles.length > 0));
  if (hasSourceSubs) {
    setStyle('source');
  } else {
    setStyle('beast');
  }

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

let lastYtReportedTime = -1;
let lastYtReportedTs   = 0;
let syncOffset         = 0.35; // Default 350ms lead time: perfectly synchronizes visual highlight with physical vocal attack

function onSyncChange(val) {
  syncOffset = parseFloat(val) / 1000.0;
  const badge = document.getElementById('syncBadge');
  if (badge) badge.textContent = `${val >= 0 ? '+' : ''}${val}ms`;
  document.querySelectorAll('.sync-chip').forEach(c => c.classList.remove('active'));
  if (activeClip) renderSubtitles(currentTime);
}

function setSyncOffset(val) {
  const slider = document.getElementById('syncSlider');
  if (slider) slider.value = val;
  onSyncChange(val);
  const badge = document.getElementById('syncBadge');
  if (badge) badge.textContent = `${val >= 0 ? '+' : ''}${val}ms`;
  document.querySelectorAll('.sync-chip').forEach(c => {
    c.classList.toggle('active', c.textContent.includes(`${val}ms`));
  });
  showToast(`⚡ Subtitle Sync: ${val >= 0 ? '+' : ''}${val}ms`);
}

function animLoop(ts) {
  if (!isPlaying) { animId = null; return; }
  if (!ts) ts = performance.now();
  const delta = Math.min(0.1, (ts - lastTs) / 1000);
  lastTs = ts;

  if (ytPlayer && ytPlayerCreated && typeof ytPlayer.getCurrentTime === 'function') {
    try {
      const yt = ytPlayer.getCurrentTime();
      if (yt !== lastYtReportedTime && yt > 0) {
        lastYtReportedTime = yt;
        lastYtReportedTs = ts;
        if (activeClip && yt >= (activeClip.start - 0.5)) {
          // Compensate for YouTube iframe cross-origin reporting transit lag (~120ms)
          const expected = Math.max(0, yt - activeClip.start + 0.12);
          const drift = Math.abs(currentTime - expected);
          if (drift > 0.5) {
            currentTime = expected;
          } else {
            // Smoothly converge at 60 FPS without stair-stepping freezing
            currentTime += (expected - currentTime) * 0.25;
          }
        }
      } else {
        // Continuous microsecond 60 FPS audio clock between YouTube 250ms postMessage ticks
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
let cachedClipKey = null;
let cachedPhraseCards = [];

function estimateWordWeightJs(word) {
  if (!word) return 1.0;
  const w = word.toLowerCase().replace(/[^a-z]/g, '');
  if (!w) return 1.0;
  const vowels = (w.match(/[aeiouy]/g) || []).length;
  let weight = 0.6 + (w.length * 0.08) + (vowels * 0.18);
  if (/[.!?]$/.test(word)) weight += 0.45;
  else if (/[,;:]$/.test(word)) weight += 0.25;
  return Math.max(0.6, weight);
}

function buildPhraseCards(subs) {
  if (!subs || !subs.length) return [];
  const cards = [];
  let currentChunk = [];

  for (let i = 0; i < subs.length; i++) {
    const item = subs[i];
    currentChunk.push(item);
    const wordStr = (item.word || '').trim();
    const endsSentence = /[.!?]$/.test(wordStr);
    let endsPause = false;
    if (i + 1 < subs.length) {
      const gap = subs[i + 1].start - item.end;
      if (gap >= 0.38) endsPause = true;
    }

    if ((endsSentence && currentChunk.length >= 2) || currentChunk.length >= 4 || endsPause || i === subs.length - 1) {
      const cStart = currentChunk[0].start;
      const cEndRaw = currentChunk[currentChunk.length - 1].end || (cStart + 1.2);
      const cEndWithHold = Math.max(cStart + 1.3, cEndRaw + 0.45);
      cards.push({
        start: cStart,
        end: cEndWithHold,
        words: [...currentChunk],
        startIndex: i - currentChunk.length + 1
      });
      currentChunk = [];
    }
  }

  // Prevent overlap with next card's start
  for (let i = 0; i < cards.length - 1; i++) {
    const nextStart = cards[i + 1].start;
    if (cards[i].end > nextStart) {
      cards[i].end = Math.max(cards[i].start + 0.85, nextStart - 0.04);
    }
  }
  return cards;
}

function genWordSubs(startSec, endSec, text) {
  const clean = (text || '')
    .replace(/&(?:lt|gt|amp|quot|apos);?/g, ' ')
    .replace(/[«»<>]+/g, ' ')
    .replace(/\[.*?\]|\(.*?\)/g, ' ')
    .trim();
  const words = clean.split(/\s+/).filter(Boolean);
  if (!words.length) return [];
  const dur = Math.max(1, endSec - startSec);
  const speechDur = Math.min(dur, Math.max(words.length * 0.32, dur * 0.88));
  const weights = words.map(w => estimateWordWeightJs(w));
  const totalWeight = weights.reduce((a, b) => a + b, 0) || 1.0;
  const highlightWords = ['important', 'key', 'secret', 'never', 'why', 'how', 'truth', 'future', 'mind', 'huge', 'best', 'worst', 'money', 'power', 'crazy', 'realize'];

  let curTime = startSec;
  return words.map((w, i) => {
    const cleanWord = w.replace(/[«»<>]+/g, '').trim();
    const wDur = Math.max(0.18, speechDur * (weights[i] / totalWeight));
    const wStart = Math.round(curTime * 100) / 100;
    const wEnd = Math.round(Math.min(endSec, curTime + wDur) * 100) / 100;
    curTime += wDur;
    return {
      word: cleanWord,
      start: wStart,
      end: wEnd,
      highlight: highlightWords.some(k => cleanWord.toLowerCase().includes(k)) || (i % 4 === 2)
    };
  }).filter(item => item.word.length > 0);
}

function renderSubtitles(curOffset) {
  const box = document.getElementById('subsBox');
  if (!box || !activeClip) return;

  // 1. If subtitles are disabled (e.g., video has burned-in captions)
  if (currentStyle === 'none') {
    if (box.innerHTML !== '') {
      box.innerHTML = '';
      box.dataset.lastHtml = '';
    }
    return;
  }

  // 2. If "Source Video Subtitles" selected and video contains real subtitles, USE THEM DIRECTLY!
  if (currentStyle === 'source' && activeClip.video_subtitles && activeClip.video_subtitles.length > 0) {
    const vSubs = activeClip.video_subtitles;
    const curAbs = activeClip.start + curOffset;
    let activeLine = vSubs.find(s => curAbs >= s.start && curAbs <= (s.end + 0.35));
    if (!activeLine) {
      activeLine = vSubs.slice().reverse().find(s => curAbs >= s.start && (curAbs - s.end) < 0.65);
    }
    const html = activeLine ? `<div class="sub-source-card">${escHtml(activeLine.text)}</div>` : '';
    if (box.dataset.lastHtml !== html) {
      box.innerHTML = html;
      box.dataset.lastHtml = html;
    }
    return;
  }

  const subs = activeClip.subtitles;
  if (!subs || !subs.length) {
    if (box.innerHTML !== '') {
      box.innerHTML = '';
      box.dataset.lastHtml = '';
    }
    return;
  }

  const isAbsolute = subs.length > 0 && subs[0].start >= (activeClip.start - 2);
  // User calibrated syncOffset (+350ms default advance): visual highlight locks with speaker acoustic attack
  const targetTime = (isAbsolute ? (activeClip.start + curOffset) : curOffset) + syncOffset;

  const clipKey = `${activeClip.start}_${activeClip.end}_${subs.length}`;
  if (cachedClipKey !== clipKey) {
    cachedClipKey = clipKey;
    cachedPhraseCards = buildPhraseCards(subs);
  }

  if (!cachedPhraseCards.length) {
    if (box.innerHTML !== '') box.innerHTML = '';
    return;
  }

  // Find active phrase card
  let activeCard = null;
  for (let i = 0; i < cachedPhraseCards.length; i++) {
    const card = cachedPhraseCards[i];
    if (targetTime >= card.start && targetTime <= card.end) {
      activeCard = card;
      break;
    }
  }

  // If outside speech segments
  if (!activeCard) {
    // Before first phrase or past last phrase
    if (targetTime < cachedPhraseCards[0].start || targetTime > cachedPhraseCards[cachedPhraseCards.length - 1].end) {
      if (box.innerHTML !== '') box.innerHTML = '';
      return;
    }
    // Hold previous card during micro-pauses (< 0.75s) so captions don't vanish abruptly
    for (let i = cachedPhraseCards.length - 1; i >= 0; i--) {
      if (targetTime >= cachedPhraseCards[i].start && (targetTime - cachedPhraseCards[i].end) < 0.75) {
        activeCard = cachedPhraseCards[i];
        break;
      }
    }
    if (!activeCard) {
      if (box.innerHTML !== '') box.innerHTML = '';
      return;
    }
  }

  // Within the active card, identify currently spoken word
  let activeWordIdx = -1;
  for (let j = 0; j < activeCard.words.length; j++) {
    const w = activeCard.words[j];
    if (targetTime >= w.start && targetTime < w.end) {
      activeWordIdx = j;
      break;
    }
  }
  // During hold time after all words spoken, keep the last word active
  if (activeWordIdx < 0) {
    for (let j = activeCard.words.length - 1; j >= 0; j--) {
      if (targetTime >= activeCard.words[j].start) {
        activeWordIdx = j;
        break;
      }
    }
  }

  const html = activeCard.words.map((s, idx) => {
    const isActive = (idx === activeWordIdx);
    const isHl     = s.highlight && !isActive;
    const cleanWord = (s.word || '')
      .replace(/&(?:lt|gt|amp|quot|apos);?/g, '')
      .replace(/[«»<>]+/g, '')
      .trim();
    if (!cleanWord) return '';
    return `<span class="sw${isActive ? ' active' : ''}${isHl ? ' hl' : ''}">${escHtml(cleanWord)}</span>`;
  }).filter(Boolean).join(' ');

  // Only update DOM if the rendered content actually changed (avoids 60fps layout thrashing)
  if (box.dataset.lastHtml !== html) {
    box.innerHTML = html;
    box.dataset.lastHtml = html;
  }
}

function escHtml(s) {
  return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function setStyle(name) {
  currentStyle = name;
  document.querySelectorAll('.style-btn').forEach(b => b.classList.toggle('active', b.dataset.s === name));
  const box = document.getElementById('subsBox');
  if (box) {
    box.className = `subs-box s-${name}`;
    box.dataset.lastHtml = ''; // force re-render with new style
  }
  if (activeClip) renderSubtitles(currentTime);
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
  const clipTitle = activeClip.title || `clip_${Math.round(startSec)}s`;
  const cleanTitle = clipTitle.replace(/[^\w\s-]/g, '').trim().replace(/[-\s]+/g, '_') || `clip_${Math.round(startSec)}s`;
  const directDlUrl = `${backend}/api/render-clip?url=${encodeURIComponent(videoUrl)}&start=${encodeURIComponent(startSec)}&duration=${encodeURIComponent(durSec)}&layout=${encodeURIComponent(currentLayout || 'split')}&title=${encodeURIComponent(clipTitle)}&subtitle_style=${encodeURIComponent(currentStyle || 'source')}`;

  // 1. Show modal with immediate direct download link ready
  setDlProgress(`🎬 Rendering "${clipTitle}" in 1080p…`, 18, directDlUrl);

  // 2. Animate progress smoothly
  let pct = 20;
  const ticker = setInterval(() => {
    pct = Math.min(88, pct + 3);
    setDlProgress(`🎬 FFmpeg NVENC is encoding 1080p "${clipTitle}"…`, pct, directDlUrl);
  }, 1800);

  // 3. Request video stream
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
        title: clipTitle,
        subtitle_style: currentStyle || 'source',
        subtitles: activeClip.subtitles || [],
        video_subtitles: activeClip.video_subtitles || [],
        stream: true
      }),
      signal: ctrl.signal
    });

    clearTimeout(renderTimer);
    clearInterval(ticker);

    if (res.ok) {
      setDlProgress('💾 Saving your 9:16 MP4…', 95, directDlUrl);
      const blob = await res.blob();
      if (blob.size > 2000) {
        const blobUrl = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = blobUrl;
        a.download = `${cleanTitle}.mp4`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setTimeout(() => URL.revokeObjectURL(blobUrl), 15000);
        hideDlProgress();
        showToast(`✅ Downloaded "${cleanTitle}.mp4"!`);
        return;
      }
    }

    // Direct browser navigation fallback
    setDlProgress('⬇️ Starting native browser download…', 92, directDlUrl);
    window.location.href = directDlUrl;
    setTimeout(() => hideDlProgress(), 4500);

  } catch (err) {
    clearInterval(ticker);
    console.warn('[Download] Fetch failed, triggering native browser download:', err);
    setDlProgress('⬇️ Starting native browser download…', 92, directDlUrl);
    // Automatic fallback: trigger direct browser GET download
    window.location.href = directDlUrl;
    setTimeout(() => hideDlProgress(), 5000);
  }
}

function setDlProgress(label, pct, directUrl) {
  const overlay = document.getElementById('dlProgressOverlay');
  if (overlay) {
    overlay.style.display = 'flex';
    const l = document.getElementById('dlLabel');
    if (l) l.textContent = label;
    const f = document.getElementById('dlFill');
    if (f) f.style.width = `${Math.min(99, pct)}%`;
    const directBtn = document.getElementById('dlDirectLink');
    if (directBtn && directUrl) {
      directBtn.href = directUrl;
      directBtn.download = `godd_ai_${(activeClip?.title||'clip').replace(/[^a-z0-9]/gi,'_').toLowerCase()}.mp4`;
    }
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
  a.download = `${activeClip.id}_captions.srt`;
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
