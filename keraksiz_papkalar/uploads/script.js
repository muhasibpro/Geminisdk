// MUHASIB Cinematic Commercial Video Animation System
// Canvas HTML5 60fps Dynamic Renderer

const canvas = document.getElementById('animCanvas');
const ctx = canvas.getContext('2d');

const subtitleText = document.getElementById('subtitleText');
const playPauseBtn = document.getElementById('playPauseBtn');
const restartBtn = document.getElementById('restartBtn');
const timeline = document.getElementById('timeline');
const currentTimeEl = document.getElementById('currentTime');
const durationEl = document.getElementById('duration');
const startOverlay = document.getElementById('startOverlay');
const bigPlayBtn = document.getElementById('bigPlayBtn');
const muhasibOverlay = document.getElementById('muhasibOverlay');
const toggleAudioBtn = document.getElementById('toggleAudioBtn');
const fullscreenBtn = document.getElementById('fullscreenBtn');
const sceneBtns = document.querySelectorAll('.scene-btn');

const DURATION = 18; // 18 seconds total video duration
let currentTime = 0;
let isPlaying = false;
let audioEnabled = true;
let animationFrameId = null;
let lastTimestamp = 0;

// Speech Synthesis & Sound Effects (Web Audio API)
const audioCtx = new (window.AudioContext || window.webkitAudioContext)();

function playSound(freq, duration, type = 'sine') {
    if (!audioEnabled || audioCtx.state === 'suspended') return;
    try {
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = type;
        osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
        gain.gain.setValueAtTime(0.1, audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + duration);
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.start();
        osc.stop(audioCtx.currentTime + duration);
    } catch(e){}
}

function speakText(text) {
    if (!audioEnabled || !('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'uz-UZ';
    utterance.rate = 1.0;
    utterance.pitch = 1.1;
    window.speechSynthesis.speak(utterance);
}

// Background images or procedural fallback canvas rendering
const bgSupermarket = new Image();
bgSupermarket.src = 'supermarket_background_1785524557834.jpg';

const bgCashier = new Image();
bgCashier.src = 'cashier_counter_bg_1785524570992.jpg';

// Character State & Vectors
const boy = {
    x: -100,
    y: 420,
    scale: 0.95,
    legAngle: 0,
    armAngle: 0,
    mouthOpen: 0,
    eyeState: 'normal', // normal, shocked, happy
    holdingItem: false
};

const cashier = {
    x: 950,
    y: 380,
    armAngle: 0,
    headTilt: 0,
    expression: 'thinking' // thinking, surprised
};

// Particles for Energy effect
let particles = [];
for (let i = 0; i < 30; i++) {
    particles.push({
        x: Math.random() * 1280,
        y: Math.random() * 720,
        radius: Math.random() * 4 + 1,
        speedY: Math.random() * 1.5 + 0.5,
        alpha: Math.random()
    });
}

// Main Render Loop
function render(timestamp) {
    if (!lastTimestamp) lastTimestamp = timestamp;
    const delta = (timestamp - lastTimestamp) / 1000;
    lastTimestamp = timestamp;

    if (isPlaying) {
        currentTime += delta;
        if (currentTime >= DURATION) {
            currentTime = DURATION;
            isPlaying = false;
            playPauseBtn.textContent = '▶';
        }
        timeline.value = (currentTime / DURATION) * 100;
    }

    updateTimeDisplay();
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Scene Router
    if (currentTime < 4.5) {
        renderScene1(currentTime);
    } else if (currentTime < 8.5) {
        renderScene2(currentTime - 4.5);
    } else if (currentTime < 13.0) {
        renderScene3(currentTime - 8.5);
    } else {
        renderScene4(currentTime - 13.0);
    }

    if (isPlaying) {
        animationFrameId = requestAnimationFrame(render);
    }
}

// -------------------------------------------------------------
// SCENE 1: BOY ENTERS THE STORE (0 - 4.5s)
// -------------------------------------------------------------
let scene1AudioTriggered = false;
function renderScene1(t) {
    if (t < 0.2) scene1AudioTriggered = false;
    if (t > 0.5 && !scene1AudioTriggered) {
        scene1AudioTriggered = true;
        subtitleText.textContent = "Do'konga quvnoq yosh yigit kirib keldi...";
        playSound(440, 0.2);
    }

    // Draw Background
    if (bgSupermarket.complete && bgSupermarket.naturalWidth !== 0) {
        ctx.drawImage(bgSupermarket, 0, 0, 1280, 720);
    } else {
        drawFallbackSupermarket();
    }

    // Overlay darkening vignette
    drawVignette();

    // Boy Entrance Motion (walk from x = -100 to x = 450)
    const progress = Math.min(t / 4.0, 1);
    boy.x = -100 + progress * 550;
    boy.y = 420;
    boy.legAngle = Math.sin(t * 10) * 0.4;
    boy.armAngle = -Math.sin(t * 10) * 0.4;
    boy.holdingItem = false;
    boy.eyeState = 'normal';

    drawBoy(boy.x, boy.y, boy.scale, boy.legAngle, boy.armAngle, boy.eyeState, false);

    // Floating store ambient sparkles
    drawAmbientParticles();
}

// -------------------------------------------------------------
// SCENE 2: PICKS UP ENERGY DRINK (4.5 - 8.5s)
// -------------------------------------------------------------
let scene2AudioTriggered = false;
function renderScene2(t) {
    if (t < 0.2) scene2AudioTriggered = false;
    if (t > 0.5 && !scene2AudioTriggered) {
        scene2AudioTriggered = true;
        subtitleText.textContent = "Javondan muzdek energetik ichimlikni tanladi...";
        playSound(880, 0.3, 'square');
    }

    // Camera Slightly Zoomed in on shelf
    ctx.save();
    ctx.translate(640, 360);
    ctx.scale(1.15, 1.15);
    ctx.translate(-640, -360);

    if (bgSupermarket.complete && bgSupermarket.naturalWidth !== 0) {
        ctx.drawImage(bgSupermarket, -50, -30, 1380, 780);
    } else {
        drawFallbackSupermarket();
    }

    boy.x = 480;
    boy.y = 410;
    
    // Hand reaching out to grab drink animation
    if (t < 2.0) {
        boy.armAngle = Math.min(t * 0.8, 1.1);
        boy.holdingItem = false;
        boy.legAngle = 0;
    } else {
        // Holding drink!
        boy.armAngle = 0.5;
        boy.holdingItem = true;
        boy.legAngle = Math.sin(t * 8) * 0.3;
        boy.x = 480 + (t - 2.0) * 120; // Walking towards right
    }

    drawBoy(boy.x, boy.y, 1.0, boy.legAngle, boy.armAngle, 'happy', boy.holdingItem);

    // Energy drink glow burst when grabbed
    if (t >= 1.8 && t <= 3.0) {
        drawEnergyGlowBurst(boy.x + 40, boy.y - 60);
    }

    ctx.restore();
}

// -------------------------------------------------------------
// SCENE 3: CASHIER COUNTER - SLOW / MANUAL CASHIER (8.5 - 13s)
// -------------------------------------------------------------
let scene3AudioTriggered = false;
function renderScene3(t) {
    if (t < 0.2) scene3AudioTriggered = false;
    if (t > 0.5 && !scene3AudioTriggered) {
        scene3AudioTriggered = true;
        subtitleText.textContent = "Kassachi sekin daftardan va kalkulyatordan narx qidirmoqda...";
        playSound(220, 0.4, 'sawtooth');
    }

    if (bgCashier.complete && bgCashier.naturalWidth !== 0) {
        ctx.drawImage(bgCashier, 0, 0, 1280, 720);
    } else {
        drawFallbackCashier();
    }

    drawVignette();

    // Boy standing at counter holding drink
    boy.x = 320;
    boy.y = 430;
    boy.legAngle = 0;
    boy.armAngle = 0.4;
    boy.holdingItem = true;

    // As time progresses, boy gets confused/impatient
    if (t < 2.5) {
        boy.eyeState = 'normal';
    } else {
        boy.eyeState = 'confused';
    }

    drawBoy(boy.x, boy.y, 1.05, boy.legAngle, boy.armAngle, boy.eyeState, true);

    // Cashier animation (typing slowly, scratching head)
    cashier.x = 880;
    cashier.y = 390;
    cashier.armAngle = Math.sin(t * 4) * 0.2;
    drawCashier(cashier.x, cashier.y, cashier.armAngle, t);

    // Speech bubble from cashier
    drawSpeechBubble(840, 200, "Xo'sh... Energetik... 15,000 so'm... daftarni ko'ray-chi...", 280, 90);

    // Question marks floating from cashier's head
    ctx.fillStyle = '#f59e0b';
    ctx.font = 'bold 36px Space Grotesk';
    ctx.fillText('❓', 880 + Math.sin(t * 3) * 10, 260 - (t * 15) % 40);
}

// -------------------------------------------------------------
// SCENE 4: SHOCKED BOY & "NEGA MUHASIB DASTURI YO'Q?!" (13 - 18s)
// -------------------------------------------------------------
let scene4VoiceTriggered = false;
function renderScene4(t) {
    if (t < 0.2) scene4VoiceTriggered = false;

    // Background Cashier with energetic zoom effect
    ctx.save();
    const zoom = 1 + Math.min(t * 0.08, 0.25);
    ctx.translate(640, 360);
    ctx.scale(zoom, zoom);
    ctx.translate(-640, -360);

    if (bgCashier.complete && bgCashier.naturalWidth !== 0) {
        ctx.drawImage(bgCashier, 0, 0, 1280, 720);
    } else {
        drawFallbackCashier();
    }

    // Boy is SHOCKED!
    boy.x = 350;
    boy.y = 430;
    boy.eyeState = 'shocked';
    boy.armAngle = 1.2; // Hands up in shock
    boy.mouthOpen = 1.0;

    drawBoy(boy.x, boy.y, 1.1, 0, boy.armAngle, 'shocked', true);

    // Dramatic Shock comic lines / flash around boy's head
    drawShockLines(boy.x + 20, boy.y - 120, t);

    // Big Speech Bubble: "VAY! NEGA SIZLARDA MUHASIB DASTURI YO'Q?!"
    drawSpeechBubble(boy.x + 60, 160, "VAY!! NEGA SIZLARDA\nMUHASIB DASTURI YO'Q?! 😱", 380, 120, '#ef4444');

    ctx.restore();

    // Trigger voice speech
    if (t > 0.3 && !scene4VoiceTriggered) {
        scene4VoiceTriggered = true;
        subtitleText.textContent = "Bola: \"Vay! Nega sizlarda MUHASIB dasturi yo'q?!\"";
        speakText("Vay! Nega sizlarda Muhasib dasturi yo'q?!");
        playSound(600, 0.6, 'sawtooth');
    }

    // Show Muhasib Overlay Banner at end (t > 2.0s)
    if (t > 2.2) {
        muhasibOverlay.classList.remove('hidden');
    } else {
        muhasibOverlay.classList.add('hidden');
    }
}

// -------------------------------------------------------------
// ANIMATED CHARACTER DRAWING (VECTOR SKELETAL SYSTEM)
// -------------------------------------------------------------
function drawBoy(x, y, scale, legAngle, armAngle, eyeState, holdingItem) {
    ctx.save();
    ctx.translate(x, y);
    ctx.scale(scale, scale);

    // Shadow on floor
    ctx.fillStyle = 'rgba(0,0,0,0.35)';
    ctx.beginPath();
    ctx.ellipse(20, 160, 45, 12, 0, 0, Math.PI * 2);
    ctx.fill();

    // Legs
    ctx.lineWidth = 14;
    ctx.lineCap = 'round';
    ctx.strokeStyle = '#1e293b'; // Dark blue jeans

    // Left leg
    ctx.beginPath();
    ctx.moveTo(10, 80);
    ctx.lineTo(10 + Math.sin(legAngle) * 30, 150);
    ctx.stroke();

    // Right leg
    ctx.beginPath();
    ctx.moveTo(30, 80);
    ctx.lineTo(30 - Math.sin(legAngle) * 30, 150);
    ctx.stroke();

    // Shoes (Red sneakers)
    ctx.fillStyle = '#ef4444';
    ctx.beginPath();
    ctx.arc(10 + Math.sin(legAngle) * 30 + 5, 155, 10, 0, Math.PI * 2);
    ctx.arc(30 - Math.sin(legAngle) * 30 + 5, 155, 10, 0, Math.PI * 2);
    ctx.fill();

    // Torso / Jacket (Stylish Cyan / Navy hoodie)
    const jacketGrad = ctx.createLinearGradient(0, 0, 40, 80);
    jacketGrad.addColorStop(0, '#0284c7');
    jacketGrad.addColorStop(1, '#0369a1');
    ctx.fillStyle = jacketGrad;
    ctx.beginPath();
    ctx.roundRect(0, 0, 45, 85, 12);
    ctx.fill();

    // T-shirt inner yellow accent
    ctx.fillStyle = '#f59e0b';
    ctx.fillRect(15, 5, 15, 30);

    // Arms
    ctx.strokeStyle = '#0284c7';
    ctx.lineWidth = 12;

    // Left Arm (back)
    ctx.beginPath();
    ctx.moveTo(8, 15);
    ctx.lineTo(-10 + Math.sin(armAngle) * 20, 50);
    ctx.stroke();

    // Right Arm (front)
    ctx.beginPath();
    ctx.moveTo(35, 15);
    if (eyeState === 'shocked') {
        ctx.lineTo(60, -30); // Raised in shock
    } else if (holdingItem) {
        ctx.lineTo(55, 25);
    } else {
        ctx.lineTo(45 + Math.sin(armAngle) * 25, 55);
    }
    ctx.stroke();

    // If holding Energetic Drink Can
    if (holdingItem) {
        drawEnergyCan(52, 10, 0.9);
    }

    // Head & Neck
    ctx.fillStyle = '#fbcfe8'; // Skin tone
    ctx.fillRect(16, -15, 12, 18);

    // Head
    ctx.beginPath();
    ctx.arc(22, -40, 26, 0, Math.PI * 2);
    ctx.fill();

    // Hair (Modern trendy brown hairstyle)
    ctx.fillStyle = '#451a03';
    ctx.beginPath();
    ctx.arc(22, -46, 28, Math.PI * 0.8, Math.PI * 2.2);
    ctx.fill();

    // Cool Hair Spikes
    ctx.beginPath();
    ctx.moveTo(10, -55);
    ctx.lineTo(20, -70);
    ctx.lineTo(30, -58);
    ctx.lineTo(40, -68);
    ctx.lineTo(45, -50);
    ctx.fill();

    // Eyes
    ctx.fillStyle = '#000';
    if (eyeState === 'shocked') {
        // Big shocked wide eyes
        ctx.fillStyle = '#fff';
        ctx.beginPath();
        ctx.arc(15, -42, 8, 0, Math.PI * 2);
        ctx.arc(32, -42, 8, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = '#000';
        ctx.beginPath();
        ctx.arc(15, -42, 3, 0, Math.PI * 2);
        ctx.arc(32, -42, 3, 0, Math.PI * 2);
        ctx.fill();

        // Shocked mouth O-shape
        ctx.fillStyle = '#ef4444';
        ctx.beginPath();
        ctx.arc(23, -28, 8, 0, Math.PI * 2);
        ctx.fill();
    } else if (eyeState === 'confused') {
        // One eyebrow raised
        ctx.fillRect(12, -45, 8, 3);
        ctx.fillRect(28, -48, 8, 3);
        ctx.beginPath();
        ctx.arc(15, -40, 4, 0, Math.PI * 2);
        ctx.arc(32, -40, 4, 0, Math.PI * 2);
        ctx.fill();

        // Wavy mouth
        ctx.strokeStyle = '#000';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(16, -28);
        ctx.lineTo(30, -30);
        ctx.stroke();
    } else { // Normal / Happy
        ctx.beginPath();
        ctx.arc(15, -42, 4, 0, Math.PI * 2);
        ctx.arc(30, -42, 4, 0, Math.PI * 2);
        ctx.fill();

        // Smile
        ctx.strokeStyle = '#000';
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        ctx.arc(22, -34, 7, 0.1, Math.PI - 0.1);
        ctx.stroke();
    }

    ctx.restore();
}

// -------------------------------------------------------------
// DRAW CASHIER CHARACTER
// -------------------------------------------------------------
function drawCashier(x, y, armAngle, t) {
    ctx.save();
    ctx.translate(x, y);

    // Cashier Body
    ctx.fillStyle = '#1e293b';
    ctx.beginPath();
    ctx.roundRect(-20, 0, 50, 90, 10);
    ctx.fill();

    // Apron / Uniform
    ctx.fillStyle = '#10b981';
    ctx.fillRect(-15, 20, 40, 70);

    // Head
    ctx.fillStyle = '#fde047'; // Skin tone
    ctx.beginPath();
    ctx.arc(5, -35, 24, 0, Math.PI * 2);
    ctx.fill();

    // Glasses
    ctx.strokeStyle = '#000';
    ctx.lineWidth = 2;
    ctx.strokeRect(-8, -42, 12, 10);
    ctx.strokeRect(8, -42, 12, 10);
    ctx.beginPath();
    ctx.moveTo(4, -37);
    ctx.lineTo(8, -37);
    ctx.stroke();

    // Eyes behind glasses
    ctx.fillStyle = '#000';
    ctx.fillRect(-3, -39, 3, 3);
    ctx.fillRect(13, -39, 3, 3);

    // Sweat drop (stressed cashier looking at price list)
    ctx.fillStyle = '#38bdf8';
    ctx.beginPath();
    ctx.arc(24, -45 + (t * 5) % 15, 3, 0, Math.PI * 2);
    ctx.fill();

    // Arm moving to type on old calculator
    ctx.strokeStyle = '#1e293b';
    ctx.lineWidth = 10;
    ctx.beginPath();
    ctx.moveTo(-15, 20);
    ctx.lineTo(-40 + Math.sin(armAngle * 5) * 15, 45);
    ctx.stroke();

    ctx.restore();
}

// -------------------------------------------------------------
// DRAW ENERGETIC CAN (Glowing Ultra Detailed)
// -------------------------------------------------------------
function drawEnergyCan(x, y, scale = 1) {
    ctx.save();
    ctx.translate(x, y);
    ctx.scale(scale, scale);

    // Can aura glow
    const grad = ctx.createRadialGradient(12, 20, 5, 12, 20, 25);
    grad.addColorStop(0, 'rgba(56, 189, 248, 0.8)');
    grad.addColorStop(1, 'rgba(56, 189, 248, 0)');
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(12, 20, 25, 0, Math.PI * 2);
    ctx.fill();

    // Metallic Can Body
    const canGrad = ctx.createLinearGradient(0, 0, 24, 0);
    canGrad.addColorStop(0, '#0284c7');
    canGrad.addColorStop(0.5, '#38bdf8');
    canGrad.addColorStop(1, '#0369a1');
    ctx.fillStyle = canGrad;
    ctx.beginPath();
    ctx.roundRect(0, 0, 24, 45, 4);
    ctx.fill();

    // Lightning bolt logo on can
    ctx.fillStyle = '#f59e0b';
    ctx.beginPath();
    ctx.moveTo(14, 8);
    ctx.lineTo(8, 22);
    ctx.lineTo(13, 22);
    ctx.lineTo(10, 36);
    ctx.lineTo(18, 20);
    ctx.lineTo(13, 20);
    ctx.closePath();
    ctx.fill();

    // Silver Top
    ctx.fillStyle = '#cbd5e1';
    ctx.fillRect(2, -3, 20, 4);

    ctx.restore();
}

// -------------------------------------------------------------
// UTILITY DRAWINGS: Speech Bubble, Shock Lines, Vignette, Fallbacks
// -------------------------------------------------------------
function drawSpeechBubble(x, y, text, width, height, borderColor = '#38bdf8') {
    ctx.save();
    ctx.fillStyle = 'rgba(15, 23, 42, 0.92)';
    ctx.strokeStyle = borderColor;
    ctx.lineWidth = 3;

    ctx.beginPath();
    ctx.roundRect(x, y, width, height, 16);
    ctx.fill();
    ctx.stroke();

    // Bubble Tail
    ctx.beginPath();
    ctx.moveTo(x + 30, y + height);
    ctx.lineTo(x + 15, y + height + 20);
    ctx.lineTo(x + 50, y + height);
    ctx.fillStyle = 'rgba(15, 23, 42, 0.92)';
    ctx.fill();
    ctx.stroke();

    // Text
    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 18px Outfit, sans-serif';
    ctx.textAlign = 'center';
    
    const lines = text.split('\n');
    lines.forEach((line, i) => {
        ctx.fillText(line, x + width / 2, y + 35 + i * 26);
    });

    ctx.restore();
}

function drawShockLines(cx, cy, t) {
    ctx.save();
    ctx.strokeStyle = '#ef4444';
    ctx.lineWidth = 4;
    for (let i = 0; i < 8; i++) {
        const angle = (i / 8) * Math.PI * 2 + t * 5;
        const r1 = 50;
        const r2 = 75 + Math.sin(t * 20 + i) * 10;
        ctx.beginPath();
        ctx.moveTo(cx + Math.cos(angle) * r1, cy + Math.sin(angle) * r1);
        ctx.lineTo(cx + Math.cos(angle) * r2, cy + Math.sin(angle) * r2);
        ctx.stroke();
    }
    ctx.restore();
}

function drawEnergyGlowBurst(cx, cy) {
    ctx.save();
    for (let i = 0; i < 12; i++) {
        const angle = (i / 12) * Math.PI * 2;
        ctx.fillStyle = i % 2 === 0 ? '#38bdf8' : '#f59e0b';
        ctx.beginPath();
        ctx.arc(cx + Math.cos(angle) * 45, cy + Math.sin(angle) * 45, 6, 0, Math.PI * 2);
        ctx.fill();
    }
    ctx.restore();
}

function drawVignette() {
    const vignette = ctx.createRadialGradient(640, 360, 400, 640, 360, 800);
    vignette.addColorStop(0, 'rgba(0,0,0,0)');
    vignette.addColorStop(1, 'rgba(0,0,0,0.6)');
    ctx.fillStyle = vignette;
    ctx.fillRect(0, 0, 1280, 720);
}

function drawAmbientParticles() {
    ctx.fillStyle = 'rgba(56, 189, 248, 0.4)';
    particles.forEach(p => {
        p.y -= p.speedY;
        if (p.y < 0) p.y = 720;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
        ctx.fill();
    });
}

function drawFallbackSupermarket() {
    ctx.fillStyle = '#1e293b';
    ctx.fillRect(0, 0, 1280, 720);
    // Shelves
    ctx.fillStyle = '#334155';
    ctx.fillRect(100, 150, 400, 400);
    ctx.fillRect(780, 150, 400, 400);
}

function drawFallbackCashier() {
    ctx.fillStyle = '#0f172a';
    ctx.fillRect(0, 0, 1280, 720);
    // Counter
    ctx.fillStyle = '#475569';
    ctx.fillRect(400, 480, 700, 240);
}

// -------------------------------------------------------------
// CONTROLS & TIMELINE EVENTS
// -------------------------------------------------------------
function togglePlay() {
    isPlaying = !isPlaying;
    if (isPlaying) {
        if (currentTime >= DURATION) currentTime = 0;
        playPauseBtn.textContent = '⏸';
        startOverlay.classList.add('fade-out');
        lastTimestamp = performance.now();
        requestAnimationFrame(render);
    } else {
        playPauseBtn.textContent = '▶';
    }
}

bigPlayBtn.addEventListener('click', () => {
    audioCtx.resume();
    togglePlay();
});

playPauseBtn.addEventListener('click', togglePlay);

restartBtn.addEventListener('click', () => {
    currentTime = 0;
    timeline.value = 0;
    if (!isPlaying) togglePlay();
});

timeline.addEventListener('input', (e) => {
    currentTime = (e.target.value / 100) * DURATION;
    updateTimeDisplay();
    if (!isPlaying) render(performance.now());
});

sceneBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        const time = parseFloat(btn.dataset.time);
        currentTime = time;
        timeline.value = (currentTime / DURATION) * 100;
        if (!isPlaying) togglePlay();
    });
});

toggleAudioBtn.addEventListener('click', () => {
    audioEnabled = !audioEnabled;
    toggleAudioBtn.innerHTML = audioEnabled ? '<span class="icon">🔊</span> Ovoz: ON' : '<span class="icon">🔇</span> Ovoz: OFF';
});

fullscreenBtn.addEventListener('click', () => {
    const container = document.getElementById('canvasContainer');
    if (!document.fullscreenElement) {
        container.requestFullscreen().catch(err => alert(err.message));
    } else {
        document.exitFullscreen();
    }
});

function updateTimeDisplay() {
    const mins = Math.floor(currentTime / 60).toString().padStart(2, '0');
    const secs = Math.floor(currentTime % 60).toString().padStart(2, '0');
    currentTimeEl.textContent = `${mins}:${secs}`;
}

// Initial draw preview frame
bgSupermarket.onload = () => {
    render(performance.now());
};
render(performance.now());
