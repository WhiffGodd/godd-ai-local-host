// godd.ai — Klap-style Frontend Engine
// Real YT preview + Server-side FFmpeg download + Hinglish streamer subtitles

const RENDER_BACKEND = 'https://godd-ai.onrender.com';

// ─── State ───────────────────────────────────────────────────────────────────
let currentVideoData = null;
let currentClips     = [];
let activeClip       = null;
let activeVideoId    = '';

let ytPlayer        = null;
let ytPlayerCreated = false;
let facecamPlayer = null;
let facecamClip = null;
let facecamReady = false;
let nextFacecamSync = 0;

let isPlaying   = false;
let currentTime = 0;
let clipDur     = 30;
let animId      = null;
let lastTs      = 0;

let currentStyle  = 'beast';
let currentLayout = 'split';

// ─── YouTube IFrame API callback ──────────────────────────────────────────────
window.onYouTubeIframeAPIReady = function () {
  if (activeClip) loadYTPlayer(activeVideoId, activeClip.start, activeClip.end);
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
  // A deployed site always uses its own backend, including custom domains.
  if (window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
    return window.location.origin;
  }
  const custom = localStorage.getItem('godd_backend');
  return custom && custom.trim() ? custom.trim().replace(/\/$/, '') : window.location.origin;
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
  activeClip = null;
  destroyFacecamPlayer();
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
        if (data.success && Array.isArray(data.clips) && data.clips.length === 0) {
          document.getElementById('processingSection').style.display = 'none';
          document.getElementById('heroSection').style.display = 'block';
          showErrModal(data.transcript_available === false
            ? 'Captions are unavailable for this video. Try a video with captions so the app can find where an answer ends.'
            : 'No complete speech passage was found within the 3-minute clip limit. Try another video or a source with clearer captions.');
          return;
        }
        if (data.success && Array.isArray(data.clips) && data.clips.length > 0) {
          setProcStatus('Done! Loading Klap studio…');
          displayStudio(data.video, data.clips);
          showToast(data.clips.some(c => c.has_real_captions === false)
            ? 'Transcript unavailable: these are suggested time ranges. Review and adjust their endings.'
            : '✅ Clips selected using speech boundaries. Review the ending before export.');
          return;
        }
      }
    } catch (e) {
      console.warn(`[Analysis] ${ep} failed:`, e.message);
    }
  }

  document.getElementById('processingSection').style.display = 'none';
  document.getElementById('heroSection').style.display = 'block';
  showErrModal('Could not analyze the video. Check your backend connection and try again.');
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

  activeClip = null;
  setLayout(video.recommended_layout || 'split');

  // Start with the styled caption preset; source captions remain selectable.
  setStyle(currentStyle);

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
  if (trimS) trimS.value = clip.start;
  const trimE = document.getElementById('trimEnd');
  if (trimE) trimE.value = clip.end;
  const durLbl = document.getElementById('trimDurLabel');
  if (durLbl) durLbl.textContent = `${Math.round(clipDur)}s`;
  const tBox = document.getElementById('transcriptBox');
  if (tBox) tBox.textContent = clip.full_text || '';

  // Load YouTube player
  loadYTPlayer(activeVideoId, clip.start, clip.end);
  updateLayoutPreview();

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
  if (ytPlayerCreated && ytPlayer && typeof ytPlayer.cueVideoById === 'function') {
    try {
      ytPlayer.cueVideoById({
        videoId: videoId,
        startSeconds: startSec,
        endSeconds: endSec
      });
      return;
    } catch (e) {
      console.warn('[YT] cueVideoById fallback:', e);
    }
  }

  // Create YouTube player via API if available
  if (window.YT && window.YT.Player) {
    if (ytPlayer && !ytPlayerCreated) return;
    try {
      fallback.style.display = 'none';
      fallback.removeAttribute('src');
      ytDiv.style.display = '';
      ytPlayer = new YT.Player('ytPlayerDiv', {
        videoId: videoId,
        playerVars: {
          start: Math.floor(startSec),
          end: Math.ceil(endSec),
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
            if (!activeClip) return;
            e.target.cueVideoById({videoId: activeVideoId, startSeconds: activeClip.start, endSeconds: activeClip.end});
            if (isPlaying) e.target.playVideo();
            updateLayoutPreview();
          },
          onStateChange: (e) => {
            if (!activeClip) return;
            if (e.data === YT.PlayerState.PLAYING) {
              isPlaying = true;
              updatePlayIcon(true);
              syncFacecam(true);
              if (!animId) animLoop();
            } else if (e.data === YT.PlayerState.PAUSED) {
              isPlaying = false;
              updatePlayIcon(false);
              pauseFacecam();
            } else if (e.data === YT.PlayerState.BUFFERING) {
              pauseFacecam();
            } else if (e.data === YT.PlayerState.ENDED) {
              isPlaying = false;
              updatePlayIcon(false);
              pauseFacecam();
              if (activeClip) {
                try {
                  ytPlayer.seekTo(activeClip.start, true);
                  seekFacecam(activeClip.start);
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
    fallback.src = `https://www.youtube.com/embed/${videoId}?start=${Math.floor(startSec)}&end=${Math.ceil(endSec)}&autoplay=0&controls=1&rel=0&playsinline=1`;
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
  syncFacecam(true);
  if (!animId) animLoop();
}

function pausePlayer() {
  isPlaying = false;
  pauseFacecam();
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
function animLoop(ts) {
  if (!isPlaying) { animId = null; return; }
  if (!ts) ts = performance.now();
  if (ytPlayerCreated && ytPlayer.getPlayerState() === YT.PlayerState.BUFFERING) {
    lastTs = ts;
    animId = requestAnimationFrame(animLoop);
    return;
  }
  syncFacecam();
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
  seekFacecam(activeClip.start + currentTime);
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
      const cEndWithHold = cEndRaw;
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
      cards[i].end = Math.min(cards[i].end, nextStart);
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

  // Suggestions made without a transcript are not spoken words. Never show
  // invented hook text as if it were a caption from the video.
  if (activeClip.has_real_captions === false && !activeClip.subtitles_edited) {
    box.innerHTML = '';
    box.dataset.lastHtml = '';
    return;
  }

  // 2. If "Source Video Subtitles" selected and video contains real subtitles, USE THEM DIRECTLY!
  if (currentStyle === 'source' && activeClip.video_subtitles && activeClip.video_subtitles.length > 0) {
    const vSubs = activeClip.video_subtitles;
    const curAbs = activeClip.start + curOffset;
    const activeLine = vSubs.find(s => curAbs >= s.start && curAbs < s.end);
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

  const targetTime = activeClip.start + curOffset;

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

  if (!activeCard) {
    box.innerHTML = '';
    box.dataset.lastHtml = '';
    return;
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
  document.querySelectorAll('.style-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.s === name);
    b.setAttribute('aria-pressed', String(b.dataset.s === name));
  });
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
  updateLayoutPreview();
}

function updateLayoutPreview() {
  const container = document.getElementById('ytContainer');
  const clip = activeClip;
  const region = clip?.facecamPreview?.region;
  if (currentLayout === 'split' && ytPlayerCreated && region) {
    loadFacecamPlayer(clip, region);
  } else {
    destroyFacecamPlayer();
  }
  container.className = `yt-container layout-${facecamPlayer ? 'split' : currentLayout === 'split' ? 'blur' : currentLayout}`;
  if (currentLayout === 'split' && clip && !clip.facecamPreview) {
    const url = currentVideoData?.url || (activeVideoId && `https://www.youtube.com/watch?v=${activeVideoId}`);
    if (!url) return;
    const preview = clip.facecamPreview = {};
    fetch(`${getBackend()}/api/facecam`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({url, start: clip.start, duration: clip.end - clip.start})
    }).then(res => res.ok ? res.json() : null).then(data => {
      preview.region = data?.facecam;
      if (activeClip === clip && clip.facecamPreview === preview) updateLayoutPreview();
    }).catch(() => {});
  }
}

function loadFacecamPlayer(clip, region) {
  if (facecamClip === clip) return;
  destroyFacecamPlayer();
  const feed = document.getElementById('camPreviewFeed');
  feed.style.setProperty('--cam-width', region.w);
  feed.style.setProperty('--cam-height', region.h);
  feed.style.setProperty('--cam-aspect', region.aspect || 16 / 9);
  feed.style.setProperty('--cam-center-x', region.x + region.w / 2);
  feed.style.setProperty('--cam-center-y', region.y + region.h / 2);
  const mount = document.createElement('div');
  feed.appendChild(mount);
  facecamClip = clip;
  facecamPlayer = new YT.Player(mount, {
    videoId: activeVideoId,
    playerVars: {controls: 0, disablekb: 1, playsinline: 1, rel: 0, start: Math.floor(clip.start)},
    events: {
      onReady: ({target}) => {
        if (target !== facecamPlayer) return;
        target.mute();
        target.getIframe().tabIndex = -1;
        facecamReady = true;
        if (isPlaying) syncFacecam(true);
        else seekFacecam(clip.start + currentTime);
      },
      onError: ({target}) => {
        if (target !== facecamPlayer) return;
        clip.facecamPreview.region = null;
        updateLayoutPreview();
      }
    }
  });
}

function destroyFacecamPlayer() {
  const player = facecamPlayer;
  facecamPlayer = null;
  facecamClip = null;
  facecamReady = false;
  nextFacecamSync = 0;
  if (player) player.destroy();
}

function pauseFacecam() {
  if (facecamReady) facecamPlayer.pauseVideo();
}

function seekFacecam(seconds) {
  if (!facecamReady) return;
  facecamPlayer.seekTo(seconds, true);
  if (!isPlaying) pauseFacecam();
  nextFacecamSync = performance.now() + 750;
}

function syncFacecam(force = false) {
  if (!facecamReady || !isPlaying || ytPlayer.getPlayerState() !== YT.PlayerState.PLAYING) return;
  const now = performance.now();
  if (!force && now < nextFacecamSync) return;
  nextFacecamSync = now + 750;
  const state = facecamPlayer.getPlayerState();
  if (state === YT.PlayerState.BUFFERING) return;
  const seconds = ytPlayer.getCurrentTime();
  if (Math.abs(seconds - facecamPlayer.getCurrentTime()) > 0.45) facecamPlayer.seekTo(seconds, true);
  if (state !== YT.PlayerState.PLAYING) facecamPlayer.playVideo();
}

function applyTrim() {
  if (!activeClip) return;
  const s = parseFloat(document.getElementById('trimStart').value) || 0;
  const e = parseFloat(document.getElementById('trimEnd').value)   || s + 30;
  if (e <= s) return;
  activeClip.start = s;
  activeClip.end   = e;
  delete activeClip.facecamPreview;
  updateLayoutPreview();
  activeClip.duration_sec = e - s;
  activeClip.duration = fmtSec(e - s);
  clipDur = e - s;
  const lbl = document.getElementById('trimDurLabel');
  if (lbl) lbl.textContent = `${Math.round(clipDur)}s`;
  currentTime = 0;
  updateScrubber();
  loadYTPlayer(activeVideoId, s, e);
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
  activeClip.subtitles_edited = true;
  activeClip.video_subtitles = [];
  activeClip.subtitles = genWordSubs(activeClip.start, activeClip.end, text);
  cachedClipKey = null;
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

  const exportingClip = activeClip;
  const startSec = activeClip.start;
  const durSec   = activeClip.end - activeClip.start;
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
    setDlProgress(`🎬 Preparing captions and encoding 1080p "${clipTitle}"…`, pct, directDlUrl);
  }, 1800);

  // 3. Request video stream
  let renderTimer;
  try {
    const ctrl = new AbortController();
    renderTimer = setTimeout(() => ctrl.abort(), 1800000); // Background jobs can take longer on free hosting

    let res = await fetch(`${backend}/api/exports`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: videoUrl,
        start: startSec,
        duration: durSec,
        layout: currentLayout || 'split',
        title: clipTitle,
        subtitle_style: currentStyle || 'source',
        subtitles: (activeClip.has_real_captions || activeClip.subtitles_edited) ? (activeClip.subtitles || []) : [],
        video_subtitles: activeClip.video_subtitles || [],
        caption_source: activeClip.subtitles_edited ? 'provided' : 'auto',
        upload_id: currentVideoData.upload_id || undefined,
        stream: true
      }),
      signal: ctrl.signal
    });

    if (res.status === 202) {
      const job = await res.json();
      const started = Date.now();
      while (true) {
        if (Date.now() - started > 1800000) throw new Error('Export timed out');
        const status = await fetch(`${backend}/api/exports/${job.id}`, {signal: ctrl.signal}).then(r => r.json());
        if (status.state === 'failed') {
          hideDlProgress();
          showErrModal(status.error || 'The export failed. Please try again.');
          if (status.code === 'YOUTUBE_ACCESS_BLOCKED') offerSourceUpload();
          return;
        }
        if (status.state === 'complete') {
          res = await fetch(`${backend}/api/exports/${job.id}/download`, {signal: ctrl.signal});
          break;
        }
        if (status.state === 'queued') setDlProgress('Your clip is queued. It will start shortly…', 20, directDlUrl);
        await new Promise(resolve => setTimeout(resolve, 2500));
      }
    }
    clearTimeout(renderTimer);
    clearInterval(ticker);

    if (res.ok) {
      setDlProgress('💾 Saving your 9:16 MP4…', 95, directDlUrl);
      const blob = await res.blob();
      const captionsUrl = res.headers.get('X-Captions-URL');
      if (captionsUrl) {
        try {
          const captions = await fetch(`${backend}${captionsUrl}`).then(r => r.json());
          exportingClip.subtitles = captions.words.map(w => ({...w, start: w.start + startSec, end: w.end + startSec}));
          exportingClip.video_subtitles = [];
          exportingClip.has_real_captions = true;
          exportingClip.captions_measured = true;
          if (activeClip === exportingClip) {
            cachedClipKey = null;
            renderSubtitles(currentTime);
          }
        } catch (error) { console.warn('Could not load measured caption preview:', error); }
      }
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

    if (!res.ok) {
      const error = await res.json().catch(() => ({}));
      hideDlProgress();
      showErrModal(error.error || 'Clip rendering failed. Please try again.');
      return;
    }

    hideDlProgress();
    showErrModal('The server returned an empty clip. Please try again.');
  } catch (err) {
    hideDlProgress();
    showErrModal(err.name === 'AbortError'
      ? 'Rendering took too long. Please try a shorter clip.'
      : 'Could not download the clip. Check the backend connection and try again.');
  } finally {
    clearTimeout(renderTimer);
    clearInterval(ticker);
  }
}

function offerSourceUpload() {
  let button = document.getElementById('sourceUploadButton');
  if (!button) {
    button = document.createElement('button');
    button.id = 'sourceUploadButton';
    button.className = 'btn-modal-primary';
    button.textContent = 'Upload original video and retry';
    button.style.marginTop = '12px';
    button.onclick = () => {
      const input = document.createElement('input');
      input.type = 'file';
      input.accept = 'video/mp4,video/webm,video/quicktime,video/x-matroska,.mkv';
      input.onchange = () => { if (input.files[0]) uploadOriginalVideo(input.files[0]); };
      input.click();
    };
    document.getElementById('errDetail').after(button);
  }
  button.hidden = false;
}

async function uploadOriginalVideo(file) {
  if (!currentVideoData || !activeClip) return;
  const video = currentVideoData;
  const selectedClip = activeClip;
  const backend = getBackend();
  if (file.size > 1024 * 1024 * 1024) {
    showErrModal('Choose the same original video in MP4, MOV, WebM or MKV format, smaller than 1 GB.');
    return;
  }
  closeErrModal();
  setDlProgress('Uploading your original video…', 0);
  try {
    const created = await fetch(`${backend}/api/source-uploads`, {
      method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({size:file.size})
    });
    const upload = await created.json();
    if (!created.ok) throw new Error(upload.error || 'Could not start upload.');
    for (let offset=0; offset<file.size; offset+=upload.chunk_size) {
      const end = Math.min(file.size,offset+upload.chunk_size);
      const chunk = file.slice(offset,end);
      let sent = false;
      for (let attempt=0; attempt<2 && !sent; attempt++) {
        try {
          const response = await fetch(`${backend}/api/source-uploads/${upload.id}?offset=${offset}`, {
            method:'PUT', headers:{'Content-Type':'application/octet-stream'}, body:chunk
          });
          if (!response.ok) throw new Error((await response.json()).error || 'Upload interrupted.');
          sent = true;
        } catch(error) { if (attempt===1) throw error; }
      }
      setDlProgress(`Uploading original video… ${Math.round(end/file.size*100)}%`,end/file.size*100);
    }
    video.upload_id = upload.id;
    hideDlProgress();
    if (currentVideoData===video && activeClip===selectedClip) await downloadClip();
    else showToast('Source uploaded. Select your clip and download when ready.');
  } catch(error) {
    hideDlProgress();
    showErrModal(error.message || 'Could not upload the source video. Please retry.');
    offerSourceUpload();
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
    if (directBtn) directBtn.hidden = !directUrl;
    if (directBtn && directUrl) {
      directBtn.href = '#';
      directBtn.textContent = 'Retry download';
      directBtn.onclick = event => {
        event.preventDefault();
        if (pct >= 90) downloadClip();
      };
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
  const sourceButton = document.getElementById('sourceUploadButton');
  if (sourceButton) sourceButton.hidden = true;
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
  if (activeClip && activeClip.has_real_captions === false && !activeClip.subtitles_edited) {
    showToast('Captions are unavailable until the source video is processed.');
    return;
  }
  if (!activeClip || !activeClip.subtitles) {
    showToast('No subtitles to export');
    return;
  }
  const source = activeClip.video_subtitles || [];
  const subs = source.length ? source : (activeClip.subtitles || []);
  const lines = [];
  const chunk = source.length ? 1 : 4;
  const duration = activeClip.end - activeClip.start;
  for (let i = 0; i < subs.length; i += chunk) {
    const g = subs.slice(i, i + chunk);
    const start = Math.max(0, g[0].start - activeClip.start);
    const end = Math.min(duration, g[g.length - 1].end - activeClip.start);
    if (end <= start) continue;
    lines.push(lines.length / 4 + 1,
      `${srtTime(start)} --> ${srtTime(end)}`,
      g.map(s => s.text || s.word).join(' '), '');
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
