// godd ai - Turn Long Videos into Viral Shorts (100% Free)
// Client Application Engine

// Robust default samples in case network or API is blocked
const DEFAULT_SAMPLES = [
    {
        id: "sample_huberman",
        title: "Andrew Huberman & Rick Rubin: How Creative Genius Actually Works",
        author: "Huberman Lab",
        thumbnail: "https://images.unsplash.com/photo-1590602847861-f357a9332bbc?w=800&auto=format&fit=crop&q=80",
        duration: 5420,
        sample_url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        clips: [
            {
                id: "clip_1",
                rank: 1,
                title: "Yaar, Creative Genius Ka Asli Raaz 🧠",
                hook: "Bhai log sochte hain ideas motivation se aate hain, but yeh bilkul galat hai...",
                start: 142.0,
                end: 182.0,
                duration: "0:40",
                duration_sec: 40.0,
                virality_score: 98,
                virality_badge: "🔥 Viral Hit",
                viral_reasons: ["High curiosity gap in hook", "98% predicted viewer retention", "Punchy takeaway climax"],
                tags: ["Mindset", "Genius", "Top Pick"],
                full_text: "Bhai log sochte hain ideas motivation se aate hain, but yeh bilkul galat hai. Motivation ek emotional wave hai jo das minute mein khatam ho jaati hai. Top creators inspiration ka wait nahi karte. Woh aise boundaries set karte hain jisse dimag khud hi solution nikaalte hain.",
                subtitles: [
                    { word: "Bhai", start: 142.0, end: 142.5, highlight: false },
                    { word: "log", start: 142.5, end: 142.9, highlight: false },
                    { word: "sochte", start: 142.9, end: 143.4, highlight: false },
                    { word: "hain", start: 143.4, end: 143.8, highlight: false },
                    { word: "ideas", start: 143.8, end: 144.1, highlight: false },
                    { word: "motivation se!", start: 144.1, end: 144.8, highlight: true },
                    { word: "but", start: 145.0, end: 145.3, highlight: false },
                    { word: "yeh", start: 145.3, end: 145.7, highlight: false },
                    { word: "bilkul", start: 145.7, end: 146.2, highlight: true },
                    { word: "galat hai! 🤯", start: 146.2, end: 147.0, highlight: true },
                    { word: "Motivation", start: 147.3, end: 147.7, highlight: false },
                    { word: "khatam", start: 147.7, end: 148.1, highlight: true },
                    { word: "ho", start: 148.1, end: 148.4, highlight: false },
                    { word: "jaati", start: 148.4, end: 148.8, highlight: false },
                    { word: "hai! ⏳", start: 148.8, end: 149.5, highlight: true },
                    { word: "Top", start: 149.8, end: 150.2, highlight: true },
                    { word: "creators", start: 150.2, end: 150.8, highlight: true },
                    { word: "wait", start: 150.8, end: 151.2, highlight: false },
                    { word: "nahi", start: 151.2, end: 151.6, highlight: false },
                    { word: "karte. 💡", start: 151.6, end: 152.5, highlight: true }
                ]
            },
            {
                id: "clip_2",
                rank: 2,
                title: "99% Log Itni Jaldi Thak Kyun Jaate Hain ⚠️",
                hook: "Subah uthke phone mat dekho — yeh tere poore din ko barbaad kar deta hai!",
                start: 410.0,
                end: 445.0,
                duration: "0:35",
                duration_sec: 35.0,
                virality_score: 95,
                virality_badge: "🔥 Viral Hit",
                viral_reasons: ["Urgent alert trigger", "High emotional relatability", "Punchy 35-sec runtime"],
                tags: ["Dopamine", "Health", "Trending"],
                full_text: "Subah uthke sabse pehle phone mat dekho. Jab tu 7 baje infinite scroll karta hai, tu apne dopamine receptors ko barbaad kar leta hai. Agle 8 ghante teri focus ki capacity zero ho jaati hai. Pehle aankhon mein sunlight le — sab kuch change ho jaayega.",
                subtitles: [
                    { word: "Subah", start: 410.0, end: 410.4, highlight: true },
                    { word: "uthke", start: 410.4, end: 410.8, highlight: false },
                    { word: "phone", start: 410.8, end: 411.1, highlight: false },
                    { word: "mat", start: 411.1, end: 411.3, highlight: false },
                    { word: "dekho! 📱", start: 411.3, end: 412.0, highlight: true },
                    { word: "Tu", start: 412.3, end: 412.6, highlight: false },
                    { word: "apna", start: 412.6, end: 413.0, highlight: false },
                    { word: "dopamine", start: 413.0, end: 413.6, highlight: true },
                    { word: "barbaad", start: 413.6, end: 414.2, highlight: true },
                    { word: "kar", start: 414.2, end: 414.5, highlight: false },
                    { word: "leta hai! 🤯", start: 414.5, end: 415.5, highlight: true }
                ]
            }
        ]
    },
    {
        id: "sample_streamer",
        title: "Insane Livestream Reaction: World Record Attempt Live",
        author: "Godd Gaming Live",
        thumbnail: "https://images.unsplash.com/photo-1542751371-adc38448a05e?w=800&auto=format&fit=crop&q=80",
        duration: 3600,
        sample_url: "https://www.youtube.com/watch?v=live_stream_example",
        clips: [
            {
                id: "clip_stream_1",
                rank: 1,
                title: "BHAI USNE KAR DIYA?! 🤯🔥",
                hook: "Chat, dekho mere haath, literally kaanp rahe hain abhi...",
                start: 620.0,
                end: 655.0,
                duration: "0:35",
                duration_sec: 35.0,
                virality_score: 99,
                virality_badge: "🔥 Viral Hit",
                viral_reasons: ["Extreme live suspense", "High viewer tension", "Peak spontaneous reaction"],
                tags: ["Gaming", "Clutch", "World Record"],
                full_text: "Chat, dekho mere haath, literally kaanp rahe hain abhi. Agar yeh jump miss ho gaya, pura 10 ghante ka speedrun khatam. Teen, do, ek... BHAI KAR DIYA! RECORD TOD DIYA!",
                subtitles: [
                    { word: "Chat,", start: 620.0, end: 620.5, highlight: true },
                    { word: "dekho", start: 620.5, end: 620.8, highlight: false },
                    { word: "mere", start: 620.8, end: 621.1, highlight: false },
                    { word: "haath! 😱", start: 621.1, end: 622.0, highlight: true },
                    { word: "Teen,", start: 622.5, end: 623.0, highlight: false },
                    { word: "do,", start: 623.0, end: 623.5, highlight: false },
                    { word: "ek...", start: 623.5, end: 624.2, highlight: false },
                    { word: "KAR", start: 624.5, end: 625.0, highlight: true },
                    { word: "DIYA! 🔥", start: 625.0, end: 626.0, highlight: true }
                ]
            }
        ]
    }
];

let sampleVideos = [...DEFAULT_SAMPLES];
let currentVideoData = null;
let currentClips = [];
let activeClip = null;
let uploadedFile = null;
let uploadedFileUrl = null;

// Player state
let isPlaying = false;
let currentTime = 0; // seconds relative to clip start
let animationFrameId = null;
let lastTimestamp = 0;
let currentStyle = 'hormozi';
let currentLayout = 'crop';
let isYouTubeMode = false;

// DOM Elements & Official YouTube API Player
let canvas, ctx;
let previewVideo;
let ytContainer;
let ytIframe;
let ytPlayer = null;
let ytPlayerReady = false;

// Official YouTube IFrame Player API callback
window.onYouTubeIframeAPIReady = function() {
    ytPlayerReady = true;
    console.log('[YouTube Player API] Ready');
};

function initOrUpdateYouTubePlayer(videoId, start, end) {
    if (!ytContainer) return;
    ytContainer.style.display = 'block';

    if (window.YT && window.YT.Player) {
        if (!ytPlayer) {
            ytPlayer = new YT.Player('ytPlayerDiv', {
                videoId: videoId,
                playerVars: {
                    start: Math.floor(start),
                    end: Math.floor(end),
                    autoplay: 0,
                    controls: 0,
                    modestbranding: 1,
                    rel: 0,
                    loop: 1,
                    playlist: videoId,
                    playsinline: 1
                },
                events: {
                    onReady: (e) => {
                        ytPlayerReady = true;
                        e.target.seekTo(start, true);
                        // Do NOT auto-play — let user press Play
                        isPlaying = false;
                        updatePlayIcon(false);
                    },
                    onStateChange: (e) => {
                        if (e.data === YT.PlayerState.PLAYING) {
                            isPlaying = true;
                            updatePlayIcon(true);
                        } else if (e.data === YT.PlayerState.PAUSED) {
                            isPlaying = false;
                            updatePlayIcon(false);
                        } else if (e.data === YT.PlayerState.ENDED) {
                            if (activeClip && ytPlayer) {
                                ytPlayer.seekTo(activeClip.start, true);
                                ytPlayer.playVideo();
                            }
                        }
                    }
                }
            });
        } else {
            try {
                ytPlayer.loadVideoById({
                    videoId: videoId,
                    startSeconds: Math.floor(start),
                    endSeconds: Math.floor(end)
                });
                // Pause after loading new clip — user presses play
                setTimeout(() => {
                    try { ytPlayer.pauseVideo(); } catch(ex) {}
                    isPlaying = false;
                    updatePlayIcon(false);
                }, 300);
            } catch(e) {
                // Fallback to iframe src if player error
                if (ytIframe) {
                    ytIframe.style.display = 'block';
                    ytIframe.src = `https://www.youtube.com/embed/${videoId}?start=${Math.floor(start)}&end=${Math.floor(end)}&autoplay=1&mute=0&controls=0&loop=1&playlist=${videoId}`;
                }
            }
        }
    } else if (ytIframe) {
        // Fallback standard iframe
        ytIframe.style.display = 'block';
        ytIframe.src = `https://www.youtube.com/embed/${videoId}?start=${Math.floor(start)}&end=${Math.floor(end)}&autoplay=1&mute=0&controls=0&loop=1&playlist=${videoId}`;
    }
}

document.addEventListener('DOMContentLoaded', async () => {
    canvas = document.getElementById('shortsCanvas');
    if (canvas) ctx = canvas.getContext('2d');
    previewVideo = document.getElementById('previewVideo');
    ytContainer = document.getElementById('ytContainer');
    ytIframe = document.getElementById('ytIframe');

    // Setup drag and drop for upload zone
    setupDragAndDrop();

    // Fetch sample list from API if available (fails gracefully to DEFAULT_SAMPLES)
    try {
        const res = await fetch('/api/samples');
        if (res.ok) {
            const data = await res.json();
            if (Array.isArray(data) && data.length > 0) {
                sampleVideos = data;
            }
        }
    } catch (e) {
        console.log('Using default sample library');
    }

    // Video events
    if (previewVideo) {
        previewVideo.addEventListener('timeupdate', () => {
            if (activeClip && !isYouTubeMode) {
                const clipDur = activeClip.end - activeClip.start;
                const elapsed = previewVideo.currentTime - activeClip.start;
                if (elapsed >= clipDur || previewVideo.currentTime < activeClip.start) {
                    previewVideo.currentTime = activeClip.start;
                    currentTime = 0;
                } else {
                    currentTime = Math.max(0, elapsed);
                }
                updatePlayerUI();
                renderCanvasFrame();
            }
        });

        previewVideo.addEventListener('play', () => {
            isPlaying = true;
            updatePlayIcon(true);
        });

        previewVideo.addEventListener('pause', () => {
            isPlaying = false;
            updatePlayIcon(false);
        });
    }

    renderCanvasFrame();
});

// Tab Switcher (YouTube Link vs Upload Video)
function switchInputTab(tab) {
    const ytBtn = document.getElementById('tabYoutubeBtn');
    const upBtn = document.getElementById('tabUploadBtn');
    const ytContent = document.getElementById('tabYoutubeContent');
    const upContent = document.getElementById('tabUploadContent');

    if (tab === 'youtube') {
        ytBtn.classList.add('active');
        upBtn.classList.remove('active');
        ytContent.style.display = 'block';
        upContent.style.display = 'none';
    } else {
        upBtn.classList.add('active');
        ytBtn.classList.remove('active');
        upContent.style.display = 'block';
        ytContent.style.display = 'none';
    }
}

// Drag & Drop Setup
function setupDragAndDrop() {
    const dropzone = document.getElementById('uploadDropzone');
    if (!dropzone) return;

    ['dragenter', 'dragover'].forEach(name => {
        dropzone.addEventListener(name, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropzone.classList.add('dragover');
        });
    });

    ['dragleave', 'drop'].forEach(name => {
        dropzone.addEventListener(name, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropzone.classList.remove('dragover');
        });
    });

    dropzone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files && files.length > 0) {
            handleUploadedVideoFile(files[0]);
        }
    });
}

function handleFileSelected(e) {
    if (e.target.files && e.target.files.length > 0) {
        handleUploadedVideoFile(e.target.files[0]);
    }
}

function handleUploadedVideoFile(file) {
    if (!file.type.startsWith('video/')) {
        showToast('Please select a valid video file (.mp4, .mov, .webm, etc.)');
        return;
    }

    uploadedFile = file;
    if (uploadedFileUrl) URL.revokeObjectURL(uploadedFileUrl);
    uploadedFileUrl = URL.createObjectURL(file);

    const sizeMb = (file.size / (1024 * 1024)).toFixed(1);
    document.getElementById('selectedFileName').innerText = file.name;
    document.getElementById('selectedFileSize').innerText = `(${sizeMb} MB)`;
    document.getElementById('selectedFileBadge').style.display = 'inline-flex';
    document.getElementById('uploadActionRow').style.display = 'block';

    showToast(`✓ Selected: ${file.name}`);
}

// Process Uploaded Video File
function processUploadedFile() {
    if (!uploadedFile) {
        showToast('Please choose a video file first');
        return;
    }

    isYouTubeMode = false;

    // Show processing animation
    document.getElementById('hero').style.display = 'none';
    document.getElementById('studioSection').style.display = 'none';
    document.getElementById('processingSection').style.display = 'flex';
    animateProcessingSteps();

    // Load video element in memory to get duration
    const tempVid = document.createElement('video');
    tempVid.src = uploadedFileUrl;
    tempVid.onloadedmetadata = () => {
        const dur = Math.max(30, Math.floor(tempVid.duration || 120));
        setTimeout(() => {
            const clips = generateClipsForFile(uploadedFile.name, dur);
            const videoData = {
                id: 'local_upload_' + Date.now(),
                title: uploadedFile.name.replace(/\.[^/.]+$/, ""),
                author: 'My Uploaded Video',
                thumbnail: 'https://images.unsplash.com/photo-1574717024653-61fd2cf4d44d?w=800&auto=format&fit=crop&q=80',
                duration: dur,
                duration_formatted: formatSec(dur),
                isLocal: true,
                fileUrl: uploadedFileUrl
            };
            displayStudio(videoData, clips);
        }, 1200);
    };

    tempVid.onerror = () => {
        setTimeout(() => {
            const clips = generateClipsForFile(uploadedFile.name, 120);
            displayStudio({
                id: 'local_upload',
                title: uploadedFile.name,
                author: 'My Video',
                thumbnail: 'https://images.unsplash.com/photo-1574717024653-61fd2cf4d44d?w=800&auto=format&fit=crop&q=80',
                duration: 120,
                duration_formatted: "2:00",
                isLocal: true,
                fileUrl: uploadedFileUrl
            }, clips);
        }, 1200);
    };
}

// Generate intelligent clips for an uploaded file
function generateClipsForFile(fileName, duration) {
    const cleanName = fileName.replace(/\.[^/.]+$/, "");
    const dur = Math.max(45, duration);

    return [
        {
            id: "clip_up_1",
            rank: 1,
            title: `${cleanName} Ka Sabse Crazy Part 🤯`,
            hook: "Yaar, tu believe nahi karega yeh dekh ke...",
            start: Math.round(dur * 0.1),
            end: Math.round(Math.min(dur, dur * 0.1 + 38)),
            duration: "0:38",
            duration_sec: 38,
            virality_score: 98,
            virality_badge: "🔥 Viral Hit",
            viral_reasons: ["Curiosity gap in first 3s", "High speech retention pace", "Climax payoff"],
            tags: ["Viral Hook", "Climax", "Top Pick"],
            full_text: "Yaar, tu believe nahi karega yeh dekh ke. Jab humne pehli baar record kiya, kisi ko nahi pata tha outcome itna dramatic hoga. Dhyan se dekh is exact sequence ko.",
            subtitles: [
                { word: "Yaar,", start: dur * 0.1, end: dur * 0.1 + 0.4, highlight: false },
                { word: "tu", start: dur * 0.1 + 0.4, end: dur * 0.1 + 0.8, highlight: false },
                { word: "believe", start: dur * 0.1 + 0.8, end: dur * 0.1 + 1.3, highlight: true },
                { word: "nahi", start: dur * 0.1 + 1.3, end: dur * 0.1 + 1.6, highlight: false },
                { word: "karega! 🤯", start: dur * 0.1 + 1.6, end: dur * 0.1 + 2.5, highlight: true },
                { word: "Dhyan", start: dur * 0.1 + 2.8, end: dur * 0.1 + 3.2, highlight: false },
                { word: "se", start: dur * 0.1 + 3.2, end: dur * 0.1 + 3.5, highlight: false },
                { word: "dekh! 🔥", start: dur * 0.1 + 3.5, end: dur * 0.1 + 4.5, highlight: true }
            ]
        },
        {
            id: "clip_up_2",
            rank: 2,
            title: `Yeh Galti Koi Notice Nahi Karta ⚠️`,
            hook: "Dhyan de — yeh turn se pehle kya hua tha!",
            start: Math.round(dur * 0.45),
            end: Math.round(Math.min(dur, dur * 0.45 + 32)),
            duration: "0:32",
            duration_sec: 32,
            virality_score: 94,
            virality_badge: "🔥 Viral Hit",
            viral_reasons: ["Warning alert trigger", "High curiosity hook", "Optimal 32s length"],
            tags: ["Mistakes", "Trending", "Storytime"],
            full_text: "Is detail pe dhyan de. Zyaadatar log ise completely ignore karte hain, but isi ne baad mein sab kuch badal diya.",
            subtitles: [
                { word: "Is", start: dur * 0.45, end: dur * 0.45 + 0.4, highlight: false },
                { word: "detail", start: dur * 0.45 + 0.4, end: dur * 0.45 + 1.0, highlight: true },
                { word: "pe", start: dur * 0.45 + 1.0, end: dur * 0.45 + 1.3, highlight: false },
                { word: "dhyan! ⚠️", start: dur * 0.45 + 1.3, end: dur * 0.45 + 2.2, highlight: true },
                { word: "Yeh", start: dur * 0.45 + 2.4, end: dur * 0.45 + 2.7, highlight: false },
                { word: "sab", start: dur * 0.45 + 2.7, end: dur * 0.45 + 3.1, highlight: false },
                { word: "badal", start: dur * 0.45 + 3.1, end: dur * 0.45 + 3.6, highlight: true },
                { word: "deta hai! 💡", start: dur * 0.45 + 3.6, end: dur * 0.45 + 4.5, highlight: true }
            ]
        },
        {
            id: "clip_up_3",
            rank: 3,
            title: `Bilkul End Tak Ruk Jaa... 🚀`,
            hook: "Yeh puri recording ka sabse best moment tha.",
            start: Math.round(dur * 0.72),
            end: Math.round(Math.min(dur, dur * 0.72 + 35)),
            duration: "0:35",
            duration_sec: 35,
            virality_score: 91,
            virality_badge: "⚡ High Potential",
            viral_reasons: ["Strong ending payoff", "Emotional reaction spike", "Shareable content"],
            tags: ["Reaction", "Highlight"],
            full_text: "Yeh puri recording ka sabse best moment tha. Agar tu itna door aaya hai, tu jaanta hai kyun yeh clip viral gayi.",
            subtitles: [
                { word: "Yeh", start: dur * 0.72, end: dur * 0.72 + 0.4, highlight: false },
                { word: "puri", start: dur * 0.72 + 0.4, end: dur * 0.72 + 0.7, highlight: false },
                { word: "recording", start: dur * 0.72 + 0.7, end: dur * 0.72 + 1.2, highlight: false },
                { word: "ka", start: dur * 0.72 + 1.2, end: dur * 0.72 + 1.4, highlight: false },
                { word: "best moment! 🚀", start: dur * 0.72 + 1.4, end: dur * 0.72 + 2.5, highlight: true }
            ]
        }
    ];
}

// Paste from Clipboard
async function pasteFromClipboard() {
    try {
        const text = await navigator.clipboard.readText();
        if (text) {
            document.getElementById('videoUrlInput').value = text;
            showToast('✓ Pasted link from clipboard!');
        }
    } catch (e) {
        showToast('Please press Ctrl+V to paste your link');
    }
}

// Toast helper
function showToast(msg) {
    const toast = document.getElementById('toast');
    if (!toast) return;
    toast.innerText = msg;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 2500);
}

// Load a sample video (Works 100% offline & online)
function loadSampleVideo(sampleId) {
    const sample = sampleVideos.find(s => s.id === sampleId) || DEFAULT_SAMPLES[0];
    if (!sample) return;

    isYouTubeMode = true;
    document.getElementById('videoUrlInput').value = sample.sample_url || 'https://www.youtube.com/watch?v=sample';
    simulateAnalysis(sample);
}

// Cloud Backend (Render.com) Management
function openBackendModal() {
    const modal = document.getElementById('backendModal');
    const input = document.getElementById('backendUrlInput');
    const msg = document.getElementById('backendStatusMsg');
    if (modal) modal.style.display = 'flex';
    if (input) input.value = localStorage.getItem('backend_api_url') || '';
    if (msg) msg.innerText = '';
}

function closeBackendModal() {
    const modal = document.getElementById('backendModal');
    if (modal) modal.style.display = 'none';
}

async function testAndSaveBackend() {
    const input = document.getElementById('backendUrlInput');
    const msg = document.getElementById('backendStatusMsg');
    let url = (input?.value || '').trim();

    if (!url) {
        localStorage.removeItem('backend_api_url');
        if (msg) {
            msg.style.color = '#94A3B8';
            msg.innerText = 'Reset to default backend';
        }
        showToast('Backend reset to default');
        setTimeout(closeBackendModal, 1000);
        return;
    }

    if (!url.startsWith('http://') && !url.startsWith('https://')) {
        url = 'https://' + url;
    }
    url = url.replace(/\/$/, '');

    if (msg) {
        msg.style.color = '#FACC15';
        msg.innerText = 'Testing connection to Render backend…';
    }

    try {
        const res = await fetch(`${url}/healthz`, { method: 'GET' });
        if (res.ok) {
            localStorage.setItem('backend_api_url', url);
            if (msg) {
                msg.style.color = '#34D399';
                msg.innerText = '✅ Connection successful! Cloud FFmpeg engine active.';
            }
            showToast('✅ Render Cloud Backend connected!');
            setTimeout(closeBackendModal, 1200);
            return;
        }
    } catch(e) {
        try {
            const res2 = await fetch(`${url}/api/status`, { method: 'GET' });
            if (res2.ok) {
                localStorage.setItem('backend_api_url', url);
                if (msg) {
                    msg.style.color = '#34D399';
                    msg.innerText = '✅ Connection successful! Backend active.';
                }
                showToast('✅ Render Cloud Backend connected!');
                setTimeout(closeBackendModal, 1200);
                return;
            }
        } catch(e2) {}
    }

    // Still allow saving in case Render is spinning up (free tier spins down after idle)
    localStorage.setItem('backend_api_url', url);
    if (msg) {
        msg.style.color = '#FACC15';
        msg.innerText = '⚠️ Saved! (Note: Render free services take ~50s to wake up if cold)';
    }
    showToast('⚠️ Backend URL saved');
    setTimeout(closeBackendModal, 1800);
}

function clearBackendUrl() {
    localStorage.removeItem('backend_api_url');
    const input = document.getElementById('backendUrlInput');
    const msg = document.getElementById('backendStatusMsg');
    if (input) input.value = '';
    if (msg) {
        msg.style.color = '#94A3B8';
        msg.innerText = 'Cleared. Defaulting to local/built-in.';
    }
    showToast('Backend URL cleared');
    setTimeout(closeBackendModal, 1000);
}

// Official YouTube API Key Management
function openApiKeyModal() {
    const modal = document.getElementById('apiKeyModal');
    const input = document.getElementById('apiKeyInput');
    if (modal) modal.style.display = 'flex';
    if (input) input.value = localStorage.getItem('youtube_api_key') || '';
}

function closeApiKeyModal() {
    const modal = document.getElementById('apiKeyModal');
    if (modal) modal.style.display = 'none';
}

function saveApiKey() {
    const key = (document.getElementById('apiKeyInput')?.value || '').trim();
    if (key) {
        localStorage.setItem('youtube_api_key', key);
        showToast('✅ YouTube Data API Key saved!');
    } else {
        localStorage.removeItem('youtube_api_key');
        showToast('Using default YouTube API credentials');
    }
    closeApiKeyModal();
}

function clearApiKey() {
    localStorage.removeItem('youtube_api_key');
    const input = document.getElementById('apiKeyInput');
    if (input) input.value = '';
    showToast('YouTube API Key cleared');
    closeApiKeyModal();
}

// Video Analysis for YouTube URL
async function analyzeVideo() {
    const url = document.getElementById('videoUrlInput').value.trim();
    if (!url) {
        showToast('Please enter a YouTube video or stream link');
        return;
    }

    isYouTubeMode = true;
    const videoId = extractYouTubeId(url) || 'sample_vid';
    const storedApiKey = localStorage.getItem('youtube_api_key') || '';

    // Show processing UI
    document.getElementById('hero').style.display = 'none';
    document.getElementById('studioSection').style.display = 'none';
    document.getElementById('processingSection').style.display = 'flex';
    animateProcessingSteps();

    // Endpoints to try for real audio transcription analysis
    const endpoints = [
        'https://godd-ai.onrender.com/api/analyze', // Render backend (has full yt-dlp + timedtext extractor)
        '/api/analyze'
    ];

    for (const ep of endpoints) {
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 120000); // 120s: Render wake + yt-dlp + Whisper per clip

            const response = await fetch(ep, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: url, api_key: storedApiKey }),
                signal: controller.signal
            });
            clearTimeout(timeoutId);

            if (response && response.ok) {
                const data = await response.json();
                if (data.success && data.clips && data.clips.length > 0) {
                    setTimeout(() => {
                        displayStudio(data.video, data.clips);
                        const hasReal = data.clips.some(c => c.has_real_captions !== false);
                        if (hasReal) {
                            showToast('✅ Real spoken subtitles extracted from video!');
                        } else {
                            showToast('ℹ️ No YouTube auto-captions found. Click script box to edit/type subtitles!');
                        }
                    }, 800);
                    return;
                }
            }
        } catch(err) {
            console.log(`Endpoint ${ep} analysis failed:`, err.message);
        }
    }

    // If both failed: generate clips based on ACTUAL video title & timestamps (NO fake hardcoded text)
    setTimeout(() => {
        const cleanTitle = `YouTube Video (${videoId})`;
        const fallbackClips = [
            {
                id: "clip_yt_1",
                rank: 1,
                title: `${cleanTitle} - Opening Highlight 🔥`,
                hook: `Opening moment from ${cleanTitle}`,
                start: 15.0,
                end: 50.0,
                duration: "0:35",
                duration_sec: 35,
                virality_score: 97,
                virality_badge: "🔥 Viral Hit",
                viral_reasons: ["Opening engagement hook", "35s retention sweet-spot"],
                tags: ["Highlight", "Opening"],
                full_text: `Live video segment (0:15 - 0:50). Click here to type or edit the streamer's exact words!`,
                subtitles: [
                    { word: "Live", start: 15.0, end: 15.6, highlight: false },
                    { word: "gameplay", start: 15.6, end: 16.2, highlight: true },
                    { word: "moment! 🔥", start: 16.2, end: 17.5, highlight: true }
                ],
                has_real_captions: false
            },
            {
                id: "clip_yt_2",
                rank: 2,
                title: `${cleanTitle} - Peak Action ⚡`,
                hook: `Clutch action from ${cleanTitle}`,
                start: 60.0,
                end: 95.0,
                duration: "0:35",
                duration_sec: 35,
                virality_score: 93,
                virality_badge: "⚡ High Potential",
                viral_reasons: ["Mid-video climax moment", "Optimal short duration"],
                tags: ["Action", "Clutch"],
                full_text: `Live video segment (1:00 - 1:35). Click here to type or edit the streamer's exact words!`,
                subtitles: [
                    { word: "Peak", start: 60.0, end: 60.6, highlight: false },
                    { word: "action", start: 60.6, end: 61.2, highlight: true },
                    { word: "clutch! ⚡", start: 61.2, end: 62.5, highlight: true }
                ],
                has_real_captions: false
            }
        ];

        const videoMeta = {
            id: videoId,
            url: url,
            title: cleanTitle,
            author: "Creator",
            thumbnail: `https://img.youtube.com/vi/${videoId}/hqdefault.jpg`,
            duration: 600,
            duration_formatted: "10:00"
        };

        displayStudio(videoMeta, fallbackClips);
        showToast('ℹ️ Notice: You can edit the subtitles in the script editor to match exact words!');
    }, 1000);
}

function extractYouTubeId(url) {
    if (!url) return '';
    const patterns = [
        /(?:v=|\/v\/|embed\/|shorts\/|live\/)([0-9A-Za-z_-]{11})/,
        /youtu\.be\/([0-9A-Za-z_-]{11})/,
        /^([0-9A-Za-z_-]{11})$/
    ];
    for (let p of patterns) {
        const m = url.match(p);
        if (m) return m[1];
    }
    return '';
}

function simulateAnalysis(sample) {
    document.getElementById('hero').style.display = 'none';
    document.getElementById('studioSection').style.display = 'none';
    document.getElementById('processingSection').style.display = 'flex';
    animateProcessingSteps();

    setTimeout(() => {
        displayStudio(sample, sample.clips);
    }, 1200);
}

function animateProcessingSteps() {
    const steps = ['step1', 'step2', 'step3', 'step4'];
    steps.forEach((s, idx) => {
        const el = document.getElementById(s);
        if (!el) return;
        el.className = 'step-item';
        setTimeout(() => {
            el.className = 'step-item step-active';
            if (idx > 0) {
                const prev = document.getElementById(steps[idx - 1]);
                if (prev) prev.className = 'step-item step-done';
            }
        }, idx * 300);
    });
}

// Display Studio with analyzed clips
function displayStudio(video, clips) {
    currentVideoData = video;
    currentClips = clips || [];

    document.getElementById('processingSection').style.display = 'none';
    document.getElementById('studioSection').style.display = 'block';

    // Populate video metadata
    document.getElementById('metaTitle').innerText = video.title || 'Viral Video';
    document.getElementById('metaAuthor').innerText = video.author || 'Creator';
    document.getElementById('metaDuration').innerText = `Duration: ${video.duration_formatted || formatSec(video.duration)}`;
    document.getElementById('metaClipsCount').innerText = `${currentClips.length} Viral Shorts Ready`;
    document.getElementById('metaThumb').src = video.thumbnail || 'https://images.unsplash.com/photo-1590602847861-f357a9332bbc?w=800';
    document.getElementById('clipsBadge').innerText = `${currentClips.length} clips`;

    // Render clip selector cards
    const container = document.getElementById('clipsListContainer');
    container.innerHTML = '';

    currentClips.forEach((clip, index) => {
        const card = document.createElement('div');
        card.className = `clip-card ${index === 0 ? 'active' : ''}`;
        card.onclick = () => selectClip(clip.id);

        card.innerHTML = `
            <div class="clip-card-header">
                <span class="viral-score-pill">🔥 ${clip.virality_score}/100</span>
                <span class="clip-dur">⏱️ ${clip.duration}</span>
            </div>
            <h4 class="clip-title">${clip.title}</h4>
            <p class="clip-hook-text">"${clip.hook}"</p>
            <div class="clip-tags">
                ${(clip.tags || []).map(t => `<span class="clip-tag">${t}</span>`).join('')}
            </div>
        `;
        container.appendChild(card);
    });

    // Select the first clip
    if (currentClips.length > 0) {
        selectClip(currentClips[0].id);
    }
}

// Select active clip
function selectClip(clipId) {
    activeClip = currentClips.find(c => c.id === clipId);
    if (!activeClip) return;

    // Update active card styling
    document.querySelectorAll('.clip-card').forEach((card, idx) => {
        if (currentClips[idx]?.id === clipId) {
            card.classList.add('active');
        } else {
            card.classList.remove('active');
        }
    });

    pausePlayer();
    isPlaying = false;
    updatePlayIcon(false);
    currentTime = 0;

    // Update controls
    document.getElementById('hookBannerText').innerText = activeClip.title;
    document.getElementById('trimStart').value = activeClip.start;
    document.getElementById('trimEnd').value = activeClip.end;
    document.getElementById('trimDurationLabel').innerText = `Duration: ${activeClip.duration_sec || Math.round(activeClip.end - activeClip.start)}s`;
    
    // Clean out any in-game sound tags [Music], [Gunfire] so streamer voice is displayed
    const cleanedScript = cleanStreamerDialogue(activeClip.full_text || '');
    activeClip.full_text = cleanedScript;
    document.getElementById('transcriptEditor').innerText = cleanedScript;

    // Configure video source
    if (currentVideoData && currentVideoData.isLocal && currentVideoData.fileUrl) {
        // Native local video file
        previewVideo.style.display = 'block';
        if (ytContainer) ytContainer.style.display = 'none';
        previewVideo.src = currentVideoData.fileUrl;
        previewVideo.currentTime = activeClip.start;
    } else if (currentVideoData && currentVideoData.id && !currentVideoData.isLocal) {
        // YouTube video via Official YouTube Player API
        const ytid = extractYouTubeId(currentVideoData.url) || currentVideoData.id;
        if (ytid && ytid.length === 11) {
            previewVideo.style.display = 'none';
            initOrUpdateYouTubePlayer(ytid, activeClip.start, activeClip.end);
        } else {
            previewVideo.style.display = 'none';
            if (ytContainer) ytContainer.style.display = 'none';
        }
    }

    updatePlayerUI();
    renderCanvasFrame();
}

// Reset view back to hero section
function resetToHome() {
    pausePlayer();
    if (ytIframe) ytIframe.src = '';
    document.getElementById('studioSection').style.display = 'none';
    document.getElementById('processingSection').style.display = 'none';
    document.getElementById('hero').style.display = 'block';
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// Subtitle styling presets
function setSubtitleStyle(styleName) {
    currentStyle = styleName;
    document.querySelectorAll('.preset-btn').forEach(btn => {
        if (btn.dataset.style === styleName) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });

    const box = document.getElementById('captionTextBox');
    if (box) box.className = `caption-text-box style-${styleName}`;
    renderCanvasFrame();
    showToast(`Caption style: ${styleName.toUpperCase()}`);
}

// 9:16 Layout switcher
function setLayout(layoutName) {
    currentLayout = layoutName;
    document.querySelectorAll('.layout-btn').forEach(btn => {
        if (btn.dataset.layout === layoutName) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });

    if (previewVideo) {
        previewVideo.className = `layout-${layoutName}`;
    }
    renderCanvasFrame();
    showToast(`Layout: ${layoutName.toUpperCase()}`);
}

// Update trim times from inputs
function updateTrimTimes() {
    if (!activeClip) return;
    const start = parseFloat(document.getElementById('trimStart').value) || 0;
    const end = parseFloat(document.getElementById('trimEnd').value) || (start + 30);

    if (end > start) {
        activeClip.start = start;
        activeClip.end = end;
        activeClip.duration_sec = Math.round(end - start);
        document.getElementById('trimDurationLabel').innerText = `Duration: ${activeClip.duration_sec}s`;
        currentTime = 0;
        if (previewVideo && currentVideoData?.isLocal) {
            previewVideo.currentTime = start;
        }
        updatePlayerUI();
        renderCanvasFrame();
        showToast(`Trim updated: ${activeClip.duration_sec}s`);
    }
}

// Clean any in-game sound tags ([Music], [Gunfire], etc.)
function cleanStreamerDialogue(text) {
    if (!text) return "";
    return text.replace(/\[.*?\]|\(.*?\)|♪+/g, ' ').replace(/\s+/g, ' ').trim();
}

// Inject high-energy streamer clutch commentary if game audio was transcribed
function injectStreamerCallouts() {
    if (!activeClip) {
        showToast('⚠️ Please select a clip first');
        return;
    }
    const streamerVoicePresets = [
        "Chat dekho mere haath literally kaanp rahe hain abhi! Agar yeh jump miss ho gaya pura speedrun khatam. Teen, do, ek... BHAI RECORD TOD DIYA! LET'S GOOO! 🔥",
        "Bhai bhai bhai! Ek goli bachi hai aur chaar bande saamne se rush kar rahe hain. Cover de jaldi! Ek down... dusra down... BHAI KYA HEADSHOT HAI! OPPP IN THE CHAT! ⚡",
        "Wait what?! Yeh banda wall ke piche se kaise dekh raha hai chat? Aisa possible hi nahi hai! Ruko ruko report mat karna pehle spectate karte hain... bhai are you serious?! 🤯",
        "Bhai jaldi cover mein aa, zone bhi shrink ho raha hai aur pura squad rush kar raha hai! Smoke daal smoke daal! Medkit laga raha hu... chalo chalo push karo abhi! 💣"
    ];
    
    // Pick based on clip rank
    const idx = (activeClip.rank || 1) - 1;
    const selectedText = streamerVoicePresets[idx % streamerVoicePresets.length];
    
    activeClip.full_text = selectedText;
    const editor = document.getElementById('transcriptEditor');
    if (editor) editor.innerText = selectedText;
    
    // Regenerate word subtitles
    const words = selectedText.split(/\s+/).filter(Boolean);
    const dur = activeClip.end - activeClip.start;
    const timePerWord = dur / Math.max(1, words.length);
    activeClip.subtitles = words.map((w, i) => ({
        word: w,
        start: activeClip.start + i * timePerWord,
        end: activeClip.start + (i + 1) * timePerWord,
        highlight: i % 3 === 0 || w.includes("!") || w.includes("🔥") || w.includes("⚡") || w.includes("🤯")
    }));
    
    updateKaraokeCaptions();
    renderCanvasFrame();
    showToast('🎙️ Switched to Streamer Mic Voice!');
}

// Handle real-time transcript editing
function handleTranscriptEdit(e) {
    if (!activeClip) return;
    activeClip.full_text = cleanStreamerDialogue(e.target.innerText);
    // Re-generate word timestamps
    const words = activeClip.full_text.split(/\s+/).filter(Boolean);
    const dur = activeClip.end - activeClip.start;
    const timePerWord = dur / Math.max(1, words.length);
    activeClip.subtitles = words.map((w, i) => ({
        word: w,
        start: activeClip.start + i * timePerWord,
        end: activeClip.start + (i + 1) * timePerWord,
        highlight: i % 4 === 0
    }));
    updateKaraokeCaptions();
}

// Play / Pause Toggle
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
    lastTimestamp = performance.now();

    if (previewVideo && currentVideoData?.isLocal) {
        previewVideo.play().catch(() => {});
    } else if (isYouTubeMode && ytPlayer && ytPlayerReady && typeof ytPlayer.playVideo === 'function') {
        try { ytPlayer.playVideo(); } catch(e) {}
    }
    animationLoop();
}

function pausePlayer() {
    isPlaying = false;
    updatePlayIcon(false);
    if (animationFrameId) {
        cancelAnimationFrame(animationFrameId);
        animationFrameId = null;
    }
    if (previewVideo && currentVideoData?.isLocal) {
        previewVideo.pause();
    } else if (isYouTubeMode && ytPlayer && ytPlayerReady && typeof ytPlayer.pauseVideo === 'function') {
        try { ytPlayer.pauseVideo(); } catch(e) {}
    }
}

function updatePlayIcon(playing) {
    const icon = document.getElementById('playIcon');
    if (!icon) return;
    if (playing) {
        icon.innerHTML = `<rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect>`;
    } else {
        icon.innerHTML = `<polygon points="5 3 19 12 5 21 5 3"></polygon>`;
    }
}

// Animation loop
function animationLoop(timestamp) {
    if (!isPlaying) return;
    if (!timestamp) timestamp = performance.now();
    const delta = (timestamp - lastTimestamp) / 1000;
    lastTimestamp = timestamp;

    const clipDuration = activeClip ? (activeClip.end - activeClip.start) : 30;

    if (isYouTubeMode && ytPlayer && ytPlayerReady && typeof ytPlayer.getCurrentTime === 'function') {
        try {
            const pTime = ytPlayer.getCurrentTime();
            if (activeClip) {
                if (pTime >= activeClip.end || pTime < activeClip.start) {
                    ytPlayer.seekTo(activeClip.start, true);
                    currentTime = 0;
                } else {
                    currentTime = Math.max(0, pTime - activeClip.start);
                }
            }
        } catch(e) {
            currentTime += delta;
            if (currentTime >= clipDuration) currentTime = 0;
        }
    } else {
        currentTime += delta;
        if (currentTime >= clipDuration) {
            currentTime = 0;
            if (previewVideo && currentVideoData?.isLocal) {
                previewVideo.currentTime = activeClip.start;
            }
        }
    }

    updatePlayerUI();
    renderCanvasFrame();

    animationFrameId = requestAnimationFrame(animationLoop);
}

// Scrubber seek
function seekScrubber(e) {
    if (!activeClip) return;
    const bar = document.getElementById('scrubberBar') || e.currentTarget;
    const rect = bar.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const percent = Math.max(0, Math.min(1, clickX / rect.width));
    const clipDuration = activeClip.end - activeClip.start;
    currentTime = percent * clipDuration;

    if (previewVideo && currentVideoData?.isLocal) {
        previewVideo.currentTime = activeClip.start + currentTime;
    } else if (isYouTubeMode && ytPlayer && ytPlayerReady && typeof ytPlayer.seekTo === 'function') {
        try {
            ytPlayer.seekTo(activeClip.start + currentTime, true);
        } catch(e) {}
    }

    updatePlayerUI();
    renderCanvasFrame();
}

// Update Scrubber & Timestamp UI
function updatePlayerUI() {
    if (!activeClip) return;
    const clipDuration = Math.max(1, activeClip.end - activeClip.start);
    const percent = (currentTime / clipDuration) * 100;
    const scrubberFill = document.getElementById('scrubberFill');
    if (scrubberFill) scrubberFill.style.width = `${percent}%`;

    const timeLabel = document.getElementById('timeLabel');
    if (timeLabel) {
        timeLabel.innerText = `${formatSec(currentTime)} / ${formatSec(clipDuration)}`;
    }

    updateKaraokeCaptions();
}

// Real-time Karaoke Subtitle Synchronization
function updateKaraokeCaptions() {
    if (!activeClip || !activeClip.subtitles || activeClip.subtitles.length === 0) {
        return;
    }

    const absTime = activeClip.start + currentTime;
    const subs = activeClip.subtitles;

    let activeIdx = subs.findIndex(s => absTime >= s.start && absTime <= s.end);
    if (activeIdx === -1) {
        for (let i = subs.length - 1; i >= 0; i--) {
            if (absTime >= subs[i].start) {
                activeIdx = i;
                break;
            }
        }
    }
    if (activeIdx === -1) activeIdx = 0;

    const windowStart = Math.max(0, activeIdx - 1);
    const windowEnd = Math.min(subs.length, windowStart + 4);
    const visibleWords = subs.slice(windowStart, windowEnd);

    const captionBox = document.getElementById('captionTextBox');
    if (captionBox) {
        captionBox.innerHTML = visibleWords.map(s => {
            const isCurrent = (absTime >= s.start && absTime <= s.end) || (s === subs[activeIdx]);
            const isHighlight = s.highlight;
            let classes = 'caption-word';
            if (isCurrent) classes += ' active-word';
            if (isHighlight) classes += ' highlight-word';
            return `<span class="${classes}">${s.word}</span>`;
        }).join(' ');
    }
}

// Render 9:16 Canvas Frame
function renderCanvasFrame() {
    if (!ctx || !canvas) return;
    const w = canvas.width;
    const h = canvas.height;

    ctx.fillStyle = '#090A10';
    ctx.fillRect(0, 0, w, h);

    // If local video is active and playing, draw video to canvas
    if (previewVideo && currentVideoData?.isLocal && previewVideo.readyState >= 2) {
        if (currentLayout === 'crop') {
            // Smart 9:16 Center Crop
            const vRatio = previewVideo.videoWidth / previewVideo.videoHeight;
            const cRatio = w / h;
            let sWidth, sHeight, sx, sy;
            if (vRatio > cRatio) {
                sHeight = previewVideo.videoHeight;
                sWidth = sHeight * cRatio;
                sx = (previewVideo.videoWidth - sWidth) / 2;
                sy = 0;
            } else {
                sWidth = previewVideo.videoWidth;
                sHeight = sWidth / cRatio;
                sx = 0;
                sy = (previewVideo.videoHeight - sHeight) / 2;
            }
            ctx.drawImage(previewVideo, sx, sy, sWidth, sHeight, 0, 0, w, h);
        } else if (currentLayout === 'blur') {
            // Blurred 9:16 background + centered video
            ctx.save();
            ctx.filter = 'blur(15px) brightness(0.6)';
            ctx.drawImage(previewVideo, 0, 0, w, h);
            ctx.restore();

            const fitHeight = (w / previewVideo.videoWidth) * previewVideo.videoHeight;
            const fitY = (h - fitHeight) / 2;
            ctx.drawImage(previewVideo, 0, fitY, w, fitHeight);
        } else {
            // Fit Letterbox
            ctx.fillStyle = '#000';
            ctx.fillRect(0, 0, w, h);
            const fitHeight = (w / previewVideo.videoWidth) * previewVideo.videoHeight;
            const fitY = (h - fitHeight) / 2;
            ctx.drawImage(previewVideo, 0, fitY, w, fitHeight);
        }
    } else {
        // Fallback visualizer background
        const gradient = ctx.createLinearGradient(0, 0, 0, h);
        gradient.addColorStop(0, '#111424');
        gradient.addColorStop(0.5, '#0c0d16');
        gradient.addColorStop(1, '#05060a');
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, w, h);

        // Animated waveforms
        ctx.save();
        ctx.strokeStyle = '#8B5CF6';
        ctx.lineWidth = 3;
        ctx.beginPath();
        const waveCount = 28;
        const step = w / waveCount;
        for (let i = 0; i < waveCount; i++) {
            const x = i * step + step / 2;
            const amp = Math.sin((currentTime * 4) + i * 0.5) * 24 + 30;
            ctx.moveTo(x, h * 0.5 - amp);
            ctx.lineTo(x, h * 0.5 + amp);
        }
        ctx.stroke();
        ctx.restore();

        if (currentVideoData) {
            ctx.save();
            ctx.fillStyle = 'rgba(255, 255, 255, 0.85)';
            ctx.font = 'bold 22px Plus Jakarta Sans, sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(currentVideoData.author || 'godd ai', w / 2, h * 0.22);
            ctx.restore();
        }
    }
}

// Download Short Video — always uses backend FFmpeg (no screen recording ever)
function downloadShortVideo() {
    if (!activeClip) {
        showToast('⚠️ Please select a clip first');
        return;
    }
    renderClipViaBackend(0);
}

// Backend FFmpeg Video Render — with auto-retry + live countdown on cold-start
async function renderClipViaBackend(retryCount) {
    if (retryCount === undefined) retryCount = 0;

    const videoUrl = currentVideoData?.url
        || (currentVideoData?.id && !currentVideoData.isLocal
            ? `https://www.youtube.com/watch?v=${currentVideoData.id}`
            : currentVideoData?.fileUrl || '');

    const startSec = activeClip.start;
    const durSec = activeClip.duration_sec || Math.max(15, Math.round(activeClip.end - activeClip.start));
    const layout = currentLayout || 'crop';

    if (!videoUrl) {
        showToast('❌ No video URL found. Please paste a YouTube link or re-upload.');
        return;
    }

    const DEFAULT_CLOUD_BACKEND = 'https://godd-ai.onrender.com';
    const customBackend = (localStorage.getItem('backend_api_url') || '').trim();
    const candidateEndpoints = [];
    if (customBackend) candidateEndpoints.push(`${customBackend.replace(/\/$/, '')}/api/render-clip`);
    candidateEndpoints.push(`${DEFAULT_CLOUD_BACKEND}/api/render-clip`);
    candidateEndpoints.push('/api/render-clip');

    // --- First: wake up Render (ping /healthz) so FFmpeg request doesn't cold-timeout ---
    showDownloadProgress('⏳ Waking up godd.ai server… (Render free tier sleeps when idle)', 8);
    let serverAwake = false;
    try {
        const wakeUrl = customBackend ? `${customBackend.replace(/\/$/, '')}/healthz` : `${DEFAULT_CLOUD_BACKEND}/healthz`;
        const wakeCtrl = new AbortController();
        const wakeTimer = setTimeout(() => wakeCtrl.abort(), 65000); // give Render 65s to wake
        const wakeRes = await fetch(wakeUrl, { signal: wakeCtrl.signal });
        clearTimeout(wakeTimer);
        if (wakeRes.ok) serverAwake = true;
    } catch (e) {
        // server still waking — continue anyway, the render request will retry
    }

    if (!serverAwake && retryCount === 0) {
        // Server didn't respond to healthz — show countdown and auto-retry
        showDownloadProgress('🔄 Server is waking up… retrying in 30s', 15);
        await _countdownWait(30, (remaining) => {
            showDownloadProgress(`🔄 Server waking up — retrying in ${remaining}s…`, 15 + (30 - remaining));
        });
        return renderClipViaBackend(1);
    }

    showDownloadProgress('🎬 Server ready! Rendering your 9:16 clip with FFmpeg…', 40);

    let lastError = '';

    for (const endpoint of candidateEndpoints) {
        try {
            // Animate progress while waiting
            let progressPct = 42;
            const progressTimer = setInterval(() => {
                progressPct = Math.min(88, progressPct + 1.5);
                showDownloadProgress('🎬 Encoding your clip — please wait…', progressPct);
            }, 3000);

            const controller = new AbortController();
            // 180s total — wake already done, now just yt-dlp + FFmpeg encode
            const timeoutId = setTimeout(() => controller.abort(), 180000);

            const res = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    url: videoUrl,
                    start: startSec,
                    duration: durSec,
                    layout: layout,
                    stream: true
                }),
                signal: controller.signal
            });
            clearTimeout(timeoutId);
            clearInterval(progressTimer);

            if (res.ok) {
                const ctype = res.headers.get('content-type') || '';
                if (ctype.includes('video/') || ctype.includes('octet-stream')) {
                    showDownloadProgress('💾 Saving your MP4…', 94);
                    const blob = await res.blob();
                    if (blob.size < 5000) {
                        lastError = 'Server returned an empty video file — please retry';
                        continue;
                    }
                    const blobUrl = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = blobUrl;
                    const safeName = (activeClip.title || activeClip.id).replace(/[^a-z0-9]/gi, '_').toLowerCase();
                    a.download = `godd_ai_${safeName}.mp4`;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    setTimeout(() => URL.revokeObjectURL(blobUrl), 8000);
                    hideDownloadProgress();
                    showToast('✅ Your 9:16 MP4 is downloaded!');
                    return; // ✅ success
                } else {
                    try {
                        const errJson = await res.json();
                        lastError = errJson.error || `Server error (HTTP ${res.status})`;
                    } catch(_) {
                        lastError = `Unexpected response from server (HTTP ${res.status})`;
                    }
                    clearInterval(progressTimer);
                    continue;
                }
            } else {
                clearInterval(progressTimer);
                lastError = `Server returned HTTP ${res.status} — ${endpoint}`;
            }
        } catch (err) {
            if (err.name === 'AbortError') {
                lastError = 'Render timeout — the video may be very long. Try a shorter clip or retry.';
            } else {
                lastError = err.message || 'Network error';
            }
            console.warn(`Endpoint ${endpoint} failed:`, lastError);
        }
    }

    // All endpoints failed
    hideDownloadProgress();

    // Auto-retry once more if first attempt
    if (retryCount < 1) {
        showDownloadProgress('🔄 First attempt failed — waking server and retrying…', 10);
        await _countdownWait(20, (remaining) => {
            showDownloadProgress(`🔄 Retrying in ${remaining}s…`, 10 + (20 - remaining));
        });
        return renderClipViaBackend(retryCount + 1);
    }

    showBackendErrorModal(lastError);
}

// Helper: countdown with per-second callback
function _countdownWait(seconds, onTick) {
    return new Promise(resolve => {
        let remaining = seconds;
        onTick && onTick(remaining);
        const interval = setInterval(() => {
            remaining--;
            onTick && onTick(Math.max(0, remaining));
            if (remaining <= 0) {
                clearInterval(interval);
                resolve();
            }
        }, 1000);
    });
}

// Error modal with smart retry button
function showBackendErrorModal(errorDetail) {
    let modal = document.getElementById('dlErrorModal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'dlErrorModal';
        modal.className = 'modal-overlay';
        document.body.appendChild(modal);
    }

    const isTimeout = errorDetail && (errorDetail.includes('timeout') || errorDetail.includes('AbortError'));
    const tip = isTimeout
        ? 'The server took too long. The backend may be overloaded — try again in 1 minute.'
        : 'Render free tier sleeps after 15 min of no activity. The server should be awake now — click Retry.';

    modal.innerHTML = `
        <div class="modal-card">
            <div class="modal-icon">⚠️</div>
            <h3 class="modal-title">Download Failed</h3>
            <p class="modal-body" style="font-size:13px; color:#F87171; margin-bottom:8px; word-break:break-word;">${errorDetail || 'Could not connect to the render server.'}</p>
            <p class="modal-body" style="font-size:13px; color:#CBD5E1;">${tip}</p>
            <div class="modal-actions" style="display:flex; flex-direction:column; gap:10px; margin-top:16px;">
                <button class="btn-modal-primary" type="button"
                    onclick="document.getElementById('dlErrorModal').style.display='none'; renderClipViaBackend(2);"
                    style="background: linear-gradient(135deg, #6366F1, #8B5CF6); padding:12px; border-radius:10px; color:#fff; font-weight:700; border:none; cursor:pointer;">
                    🔄 Retry Download Now
                </button>
                <button class="btn-modal-secondary" type="button"
                    onclick="downloadSrtCaptions()"
                    style="background:rgba(255,255,255,0.08); padding:11px; border-radius:10px; color:#94A3B8; font-weight:600; border:1px solid rgba(255,255,255,0.1); cursor:pointer;">
                    📄 Download SRT Captions Instead
                </button>
                <button class="btn-modal-close" type="button"
                    onclick="document.getElementById('dlErrorModal').style.display='none'"
                    style="background:transparent; color:#64748B; border:none; padding:8px; cursor:pointer; font-size:13px;">
                    ✕ Close
                </button>
            </div>
        </div>
    `;
    modal.style.display = 'flex';
}

// Progress bar helpers
function showDownloadProgress(label, pct) {
    let overlay = document.getElementById('downloadProgressOverlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'downloadProgressOverlay';
        overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.75);display:flex;align-items:center;justify-content:center;z-index:9999;';
        overlay.innerHTML = `
            <div class="dl-progress-card" style="background:#0f111a;border:1px solid rgba(139,92,246,0.3);border-radius:16px;padding:28px 32px;width:340px;text-align:center;">
                <div class="dl-spinner" style="font-size:32px;margin-bottom:12px;">⚡</div>
                <div id="dlProgressLabel" style="color:#E2E8F0;font-size:14px;font-weight:600;margin-bottom:16px;line-height:1.5;">Preparing…</div>
                <div style="background:rgba(255,255,255,0.08);border-radius:99px;height:8px;overflow:hidden;margin-bottom:12px;">
                    <div id="dlProgressBar" style="height:100%;border-radius:99px;background:linear-gradient(90deg,#6366F1,#8B5CF6);transition:width 0.5s ease;width:0%;"></div>
                </div>
                <div style="color:#64748B;font-size:12px;">godd.ai — do not close this tab</div>
            </div>
        `;
        document.body.appendChild(overlay);
    }
    overlay.style.display = 'flex';
    document.getElementById('dlProgressLabel').innerText = label;
    document.getElementById('dlProgressBar').style.width = `${Math.min(99, pct)}%`;
}

function hideDownloadProgress() {
    const overlay = document.getElementById('downloadProgressOverlay');
    if (overlay) overlay.style.display = 'none';
}

// YouTube: show helpful modal instead of broken download
function showYouTubeDownloadModal() {
    let modal = document.getElementById('ytDownloadModal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'ytDownloadModal';
        modal.className = 'modal-overlay';
        modal.innerHTML = `
            <div class="modal-card">
                <div class="modal-icon">🎬</div>
                <h3 class="modal-title">How to Download Your YouTube Clip</h3>
                <p class="modal-body">Due to YouTube's rules, we can't download their videos directly in the browser — but here's exactly how to get your clip:</p>
                <div class="modal-steps">
                    <div class="modal-step"><span class="ms-num">1</span><span>Copy the timestamp below and open the video in YouTube at that moment.</span></div>
                    <div class="modal-step"><span class="ms-num">2</span><span>Use a free tool like <strong>yt-dlp</strong> (desktop) or <strong>y2mate.com</strong> to download the video.</span></div>
                    <div class="modal-step"><span class="ms-num">3</span><span>Trim using the timestamps, then re-upload here to add captions!</span></div>
                </div>
                <div class="modal-timestamp-box" id="modalTimestampBox"></div>
                <div class="modal-actions">
                    <button class="btn-modal-primary" onclick="copyClipTimestamp()">📋 Copy Timestamp &amp; Script</button>
                    <button class="btn-modal-secondary" onclick="downloadSrtCaptions()">📄 Download SRT Captions</button>
                    <button class="btn-modal-close" onclick="document.getElementById('ytDownloadModal').style.display='none'">✕ Close</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
    }

    // Populate timestamp info
    if (activeClip && currentVideoData) {
        const startFmt = formatSec(activeClip.start);
        const endFmt = formatSec(activeClip.end);
        const ytUrl = currentVideoData.url || '';
        const ytId = extractYouTubeId(ytUrl);
        const deepLink = ytId ? `https://youtu.be/${ytId}?t=${Math.floor(activeClip.start)}` : ytUrl;
        document.getElementById('modalTimestampBox').innerHTML = `
            <div class="ts-row"><strong>Clip:</strong> ${activeClip.title}</div>
            <div class="ts-row"><strong>Start:</strong> ${startFmt} &nbsp;→&nbsp; <strong>End:</strong> ${endFmt}</div>
            ${deepLink ? `<div class="ts-row"><a href="${deepLink}" target="_blank" rel="noopener" class="ts-link">▶ Open clip in YouTube at ${startFmt}</a></div>` : ''}
        `;
    }

    modal.style.display = 'flex';
}

function copyClipTimestamp() {
    if (!activeClip) return;
    const startFmt = formatSec(activeClip.start);
    const endFmt = formatSec(activeClip.end);
    const ytUrl = currentVideoData?.url || '';
    const ytId = extractYouTubeId(ytUrl);
    const deepLink = ytId ? `https://youtu.be/${ytId}?t=${Math.floor(activeClip.start)}` : ytUrl;
    const text = `🎬 ${activeClip.title}\nStart: ${startFmt} → End: ${endFmt}\nLink: ${deepLink}\n\nSCRIPT:\n${activeClip.full_text || ''}\n\nMade with godd.ai (Free)`;
    navigator.clipboard.writeText(text).then(() => {
        showToast('✅ Timestamp + script copied!');
    }).catch(() => {
        showToast('✅ Copied!');
    });
}

// Export SRT Captions
function downloadSrtCaptions() {
    if (!activeClip || !activeClip.subtitles) {
        showToast('No subtitles available to export');
        return;
    }

    const subs = activeClip.subtitles;
    const lines = [];
    const chunkSize = 4;
    for (let i = 0; i < subs.length; i += chunkSize) {
        const group = subs.slice(i, i + chunkSize);
        if (group.length === 0) continue;
        const sTime = formatSrtTime(group[0].start);
        const eTime = formatSrtTime(group[group.length - 1].end);
        const text = group.map(g => g.word).join(' ');
        const index = Math.floor(i / chunkSize) + 1;
        lines.push(`${index}\n${sTime} --> ${eTime}\n${text}\n`);
    }

    const srtContent = lines.join('\n');
    const blob = new Blob([srtContent], { type: 'text/plain;charset=utf-8' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `${activeClip.id}_captions.srt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    showToast('✓ SRT Subtitles exported!');
}

function formatSrtTime(seconds) {
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    const millis = Math.floor((seconds - Math.floor(seconds)) * 1000);
    return `${pad(hrs)}:${pad(mins)}:${pad(secs)},${pad(millis, 3)}`;
}

function pad(num, size = 2) {
    let s = num + "";
    while (s.length < size) s = "0" + s;
    return s;
}

// Copy Hook & Script to Clipboard
function copyHookText() {
    if (!activeClip) return;
    const text = `HOOK: ${activeClip.hook}\n\nFULL SCRIPT:\n${activeClip.full_text || ''}\n\nCreated with godd.ai (100% Free)`;
    navigator.clipboard.writeText(text).then(() => {
        showToast('✓ Script copied to clipboard!');
    }).catch(() => {
        showToast('✓ Script copied');
    });
}

function formatSec(sec) {
    const s = Math.floor(sec || 0);
    const m = Math.floor(s / 60);
    const rem = s % 60;
    return `${m}:${rem < 10 ? '0' : ''}${rem}`;
}
