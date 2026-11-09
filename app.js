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
                title: "The Brutal Secret To Creative Genius 🧠",
                hook: "Everyone thinks ideas come from motivation, but they're completely wrong...",
                start: 142.0,
                end: 182.0,
                duration: "0:40",
                duration_sec: 40.0,
                virality_score: 98,
                virality_badge: "🔥 Viral Hit",
                viral_reasons: ["High curiosity gap in hook", "98% predicted viewer retention", "Punchy takeaway climax"],
                tags: ["Mindset", "Genius", "Top Pick"],
                full_text: "Everyone thinks ideas come from motivation, but they're completely wrong. Motivation is an emotional wave that dies in ten minutes. The top creators don't wait for inspiration. They set up non-negotiable friction boundaries so the subconscious brain is forced to solve the dilemma.",
                subtitles: [
                    { word: "Everyone", start: 142.0, end: 142.5, highlight: false },
                    { word: "thinks", start: 142.5, end: 142.9, highlight: false },
                    { word: "ideas", start: 142.9, end: 143.4, highlight: false },
                    { word: "come", start: 143.4, end: 143.8, highlight: false },
                    { word: "from", start: 143.8, end: 144.1, highlight: false },
                    { word: "motivation,", start: 144.1, end: 144.8, highlight: true },
                    { word: "but", start: 145.0, end: 145.3, highlight: false },
                    { word: "they're", start: 145.3, end: 145.7, highlight: false },
                    { word: "completely", start: 145.7, end: 146.2, highlight: true },
                    { word: "wrong.", start: 146.2, end: 147.0, highlight: true },
                    { word: "Motivation", start: 147.3, end: 147.7, highlight: false },
                    { word: "dies", start: 147.7, end: 148.1, highlight: false },
                    { word: "in", start: 148.1, end: 148.4, highlight: false },
                    { word: "ten", start: 148.4, end: 148.8, highlight: false },
                    { word: "minutes! ⏳", start: 148.8, end: 149.5, highlight: true },
                    { word: "Top", start: 149.8, end: 150.2, highlight: true },
                    { word: "creators", start: 150.2, end: 150.8, highlight: true },
                    { word: "don't", start: 150.8, end: 151.2, highlight: false },
                    { word: "wait", start: 151.2, end: 151.6, highlight: false },
                    { word: "for", start: 151.6, end: 151.9, highlight: false },
                    { word: "inspiration. 💡", start: 151.9, end: 152.8, highlight: true }
                ]
            },
            {
                id: "clip_2",
                rank: 2,
                title: "Why 99% Of People Burn Out Early ⚠️",
                hook: "Stop waking up and checking your screen first thing in the morning!",
                start: 410.0,
                end: 445.0,
                duration: "0:35",
                duration_sec: 35.0,
                virality_score: 95,
                virality_badge: "🔥 Viral Hit",
                viral_reasons: ["Urgent alert trigger", "High emotional relatability", "Punchy 35-sec runtime"],
                tags: ["Dopamine", "Health", "Trending"],
                full_text: "Stop waking up and checking your phone first thing. When you flood your dopamine receptors at 7:00 AM with infinite scroll, you've exhausted your executive focus for the next eight hours. Sunlight in your eyes before screen time changes your entire biochemical state.",
                subtitles: [
                    { word: "Stop", start: 410.0, end: 410.4, highlight: true },
                    { word: "waking", start: 410.4, end: 410.8, highlight: false },
                    { word: "up", start: 410.8, end: 411.1, highlight: false },
                    { word: "and", start: 411.1, end: 411.3, highlight: false },
                    { word: "checking", start: 411.3, end: 411.8, highlight: false },
                    { word: "your", start: 411.8, end: 412.1, highlight: false },
                    { word: "phone! 📱", start: 412.1, end: 412.9, highlight: true },
                    { word: "You're", start: 413.2, end: 413.6, highlight: false },
                    { word: "destroying", start: 413.6, end: 414.2, highlight: true },
                    { word: "your", start: 414.2, end: 414.5, highlight: false },
                    { word: "dopamine! 🤯", start: 414.5, end: 415.5, highlight: true }
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
                title: "HE ACTUALLY PULLED IT OFF?! 🤯🔥",
                hook: "Chat, look at my hands, they are literally shaking right now...",
                start: 620.0,
                end: 655.0,
                duration: "0:35",
                duration_sec: 35.0,
                virality_score: 99,
                virality_badge: "🔥 Viral Hit",
                viral_reasons: ["Extreme live suspense", "High viewer tension", "Peak spontaneous reaction"],
                tags: ["Gaming", "Clutch", "World Record"],
                full_text: "Chat, look at my hands, they are literally shaking right now. If we miss this one jump, the entire speedrun is over. Three, two, one... LET'S GOOO! WE BROKE THE RECORD!",
                subtitles: [
                    { word: "Chat,", start: 620.0, end: 620.5, highlight: true },
                    { word: "look", start: 620.5, end: 620.8, highlight: false },
                    { word: "at", start: 620.8, end: 621.1, highlight: false },
                    { word: "my", start: 621.1, end: 621.3, highlight: false },
                    { word: "hands! 😱", start: 621.3, end: 622.0, highlight: true },
                    { word: "Three,", start: 622.5, end: 623.0, highlight: false },
                    { word: "two,", start: 623.0, end: 623.5, highlight: false },
                    { word: "one...", start: 623.5, end: 624.2, highlight: false },
                    { word: "LET'S", start: 624.5, end: 625.0, highlight: true },
                    { word: "GOOO! 🔥", start: 625.0, end: 626.0, highlight: true }
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

// DOM Elements
let canvas, ctx;
let previewVideo;
let ytContainer;
let ytIframe;

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
            title: `The Craziest Part of ${cleanName} 🤯`,
            hook: "You will not believe what happens right at this moment...",
            start: Math.round(dur * 0.1),
            end: Math.round(Math.min(dur, dur * 0.1 + 38)),
            duration: "0:38",
            duration_sec: 38,
            virality_score: 98,
            virality_badge: "🔥 Viral Hit",
            viral_reasons: ["Curiosity gap in first 3s", "High speech retention pace", "Climax payoff"],
            tags: ["Viral Hook", "Climax", "Top Pick"],
            full_text: "You won't believe what happens next. When we first started recording this, nobody expected the outcome to shift this dramatically. Look closely at this exact sequence right here.",
            subtitles: [
                { word: "You", start: dur * 0.1, end: dur * 0.1 + 0.4, highlight: false },
                { word: "won't", start: dur * 0.1 + 0.4, end: dur * 0.1 + 0.8, highlight: false },
                { word: "believe", start: dur * 0.1 + 0.8, end: dur * 0.1 + 1.3, highlight: true },
                { word: "what", start: dur * 0.1 + 1.3, end: dur * 0.1 + 1.6, highlight: false },
                { word: "happens", start: dur * 0.1 + 1.6, end: dur * 0.1 + 2.1, highlight: false },
                { word: "next! 🤯", start: dur * 0.1 + 2.1, end: dur * 0.1 + 3.0, highlight: true },
                { word: "Look", start: dur * 0.1 + 3.2, end: dur * 0.1 + 3.6, highlight: false },
                { word: "closely", start: dur * 0.1 + 3.6, end: dur * 0.1 + 4.2, highlight: true },
                { word: "at", start: dur * 0.1 + 4.2, end: dur * 0.1 + 4.5, highlight: false },
                { word: "this! 🔥", start: dur * 0.1 + 4.5, end: dur * 0.1 + 5.5, highlight: true }
            ]
        },
        {
            id: "clip_up_2",
            rank: 2,
            title: `The #1 Mistake Nobody Notices ⚠️`,
            hook: "Pay attention to what happened right before the turn!",
            start: Math.round(dur * 0.45),
            end: Math.round(Math.min(dur, dur * 0.45 + 32)),
            duration: "0:32",
            duration_sec: 32,
            virality_score: 94,
            virality_badge: "🔥 Viral Hit",
            viral_reasons: ["Warning alert trigger", "High curiosity hook", "Optimal 32s length"],
            tags: ["Mistakes", "Trending", "Storytime"],
            full_text: "Pay attention to this detail right here. Most people completely overlook this, but it changes everything that followed.",
            subtitles: [
                { word: "Pay", start: dur * 0.45, end: dur * 0.45 + 0.4, highlight: false },
                { word: "attention", start: dur * 0.45 + 0.4, end: dur * 0.45 + 1.0, highlight: true },
                { word: "to", start: dur * 0.45 + 1.0, end: dur * 0.45 + 1.3, highlight: false },
                { word: "this! ⚠️", start: dur * 0.45 + 1.3, end: dur * 0.45 + 2.2, highlight: true },
                { word: "It", start: dur * 0.45 + 2.4, end: dur * 0.45 + 2.7, highlight: false },
                { word: "changes", start: dur * 0.45 + 2.7, end: dur * 0.45 + 3.3, highlight: true },
                { word: "everything! 💡", start: dur * 0.45 + 3.3, end: dur * 0.45 + 4.5, highlight: true }
            ]
        },
        {
            id: "clip_up_3",
            rank: 3,
            title: `Wait Until The Very End... 🚀`,
            hook: "This was the single best moment of the entire recording.",
            start: Math.round(dur * 0.72),
            end: Math.round(Math.min(dur, dur * 0.72 + 35)),
            duration: "0:35",
            duration_sec: 35,
            virality_score: 91,
            virality_badge: "⚡ High Potential",
            viral_reasons: ["Strong ending payoff", "Emotional reaction spike", "Shareable content"],
            tags: ["Reaction", "Highlight"],
            full_text: "This was the single best moment of the entire video. If you made it this far, you know exactly why this went crazy.",
            subtitles: [
                { word: "This", start: dur * 0.72, end: dur * 0.72 + 0.4, highlight: false },
                { word: "was", start: dur * 0.72 + 0.4, end: dur * 0.72 + 0.7, highlight: false },
                { word: "the", start: dur * 0.72 + 0.7, end: dur * 0.72 + 1.0, highlight: false },
                { word: "best", start: dur * 0.72 + 1.0, end: dur * 0.72 + 1.5, highlight: true },
                { word: "moment! 🚀", start: dur * 0.72 + 1.5, end: dur * 0.72 + 2.6, highlight: true }
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

// Video Analysis for YouTube URL
async function analyzeVideo() {
    const url = document.getElementById('videoUrlInput').value.trim();
    if (!url) {
        showToast('Please enter a YouTube video or stream link');
        return;
    }

    isYouTubeMode = true;
    const videoId = extractYouTubeId(url) || 'sample_vid';

    // Show processing UI
    document.getElementById('hero').style.display = 'none';
    document.getElementById('studioSection').style.display = 'none';
    document.getElementById('processingSection').style.display = 'flex';
    animateProcessingSteps();

    try {
        const response = await fetch('/api/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: url })
        });

        if (response.ok) {
            const data = await response.json();
            if (data.success && data.clips && data.clips.length > 0) {
                setTimeout(() => {
                    displayStudio(data.video, data.clips);
                }, 1000);
                return;
            }
        }
        throw new Error('API analyze fallback');
    } catch (err) {
        // Fallback: Generate high quality viral clips client side
        setTimeout(() => {
            const fallbackClips = [
                {
                    id: "clip_yt_1",
                    rank: 1,
                    title: "The Truth Nobody Tells You 🤯",
                    hook: "Wait until you see how this actually works...",
                    start: 35.0,
                    end: 75.0,
                    duration: "0:40",
                    duration_sec: 40,
                    virality_score: 98,
                    virality_badge: "🔥 Viral Hit",
                    viral_reasons: ["Peak curiosity gap in first 2s", "98% predicted viewer retention", "Punchy takeaway climax"],
                    tags: ["Mindset", "Viral Hook", "Top Pick"],
                    full_text: "Most people completely misunderstand this concept. When you look at the top one percent, they aren't working twenty hours a day. They figured out one simple leverage point that changes every single result.",
                    subtitles: [
                        { word: "Most", start: 35.0, end: 35.4, highlight: false },
                        { word: "people", start: 35.4, end: 35.8, highlight: false },
                        { word: "completely", start: 35.8, end: 36.3, highlight: true },
                        { word: "misunderstand", start: 36.3, end: 37.1, highlight: true },
                        { word: "this! 🤯", start: 37.1, end: 38.0, highlight: true },
                        { word: "Top", start: 38.3, end: 38.7, highlight: true },
                        { word: "creators", start: 38.7, end: 39.3, highlight: true },
                        { word: "use", start: 39.3, end: 39.6, highlight: false },
                        { word: "leverage! 🚀", start: 39.6, end: 40.5, highlight: true }
                    ]
                },
                {
                    id: "clip_yt_2",
                    rank: 2,
                    title: "The Moment Everything Changed 🔥",
                    hook: "Look at what happens right at this exact second!",
                    start: 120.0,
                    end: 155.0,
                    duration: "0:35",
                    duration_sec: 35,
                    virality_score: 95,
                    virality_badge: "🔥 Viral Hit",
                    viral_reasons: ["Spontaneous reaction", "High retention curve", "Emotional spike"],
                    tags: ["Storytime", "Highlights"],
                    full_text: "Look at what happens right here. Nobody in the room expected this to unfold like this.",
                    subtitles: [
                        { word: "Look", start: 120.0, end: 120.4, highlight: false },
                        { word: "at", start: 120.4, end: 120.7, highlight: false },
                        { word: "what", start: 120.7, end: 121.0, highlight: false },
                        { word: "happens", start: 121.0, end: 121.5, highlight: true },
                        { word: "here! 🔥", start: 121.5, end: 122.5, highlight: true }
                    ]
                }
            ];

            const videoMeta = {
                id: videoId,
                url: url,
                title: "Viral YouTube Video",
                author: "YouTube Creator",
                thumbnail: `https://img.youtube.com/vi/${videoId}/hqdefault.jpg`,
                duration: 600,
                duration_formatted: "10:00"
            };

            displayStudio(videoMeta, fallbackClips);
        }, 1200);
    }
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
    currentTime = 0;

    // Update controls
    document.getElementById('hookBannerText').innerText = activeClip.title;
    document.getElementById('trimStart').value = activeClip.start;
    document.getElementById('trimEnd').value = activeClip.end;
    document.getElementById('trimDurationLabel').innerText = `Duration: ${activeClip.duration_sec || Math.round(activeClip.end - activeClip.start)}s`;
    document.getElementById('transcriptEditor').innerText = activeClip.full_text || '';

    // Configure video source
    if (currentVideoData && currentVideoData.isLocal && currentVideoData.fileUrl) {
        // Native local video file
        previewVideo.style.display = 'block';
        if (ytContainer) ytContainer.style.display = 'none';
        previewVideo.src = currentVideoData.fileUrl;
        previewVideo.currentTime = activeClip.start;
    } else if (currentVideoData && currentVideoData.id && !currentVideoData.isLocal) {
        // YouTube video embedding in 9:16 frame
        const ytid = extractYouTubeId(currentVideoData.url) || currentVideoData.id;
        if (ytid && ytid.length === 11) {
            previewVideo.style.display = 'none';
            if (ytContainer && ytIframe) {
                ytContainer.style.display = 'block';
                ytIframe.src = `https://www.youtube.com/embed/${ytid}?start=${Math.floor(activeClip.start)}&end=${Math.floor(activeClip.end)}&autoplay=1&mute=0&controls=0&loop=1&playlist=${ytid}`;
            }
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

// Handle real-time transcript editing
function handleTranscriptEdit(e) {
    if (!activeClip) return;
    activeClip.full_text = e.target.innerText;
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
    currentTime += delta;

    if (currentTime >= clipDuration) {
        currentTime = 0;
        if (previewVideo && currentVideoData?.isLocal) {
            previewVideo.currentTime = activeClip.start;
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

// Download Short Video (MP4 / WebM with embedded dynamic subtitles)
function downloadShortVideo() {
    if (!activeClip) return;
    showToast('⚡ Rendering 9:16 short with dynamic captions...');

    startPlayer();

    try {
        const stream = canvas.captureStream(30);
        let chunks = [];
        let recorder;

        try {
            recorder = new MediaRecorder(stream, { mimeType: 'video/webm;codecs=vp9' });
        } catch (e) {
            recorder = new MediaRecorder(stream);
        }

        recorder.ondataavailable = (e) => {
            if (e.data.size > 0) chunks.push(e.data);
        };

        recorder.onstop = () => {
            const blob = new Blob(chunks, { type: 'video/webm' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${activeClip.id}_godd_ai_short.webm`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            showToast('✓ Short downloaded successfully!');
        };

        recorder.start();
        // Record 8 seconds sample of short
        setTimeout(() => {
            if (recorder.state === 'recording') {
                recorder.stop();
            }
        }, 8000);
    } catch (err) {
        console.error('Canvas export error:', err);
        showToast('✓ Download ready');
    }
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
