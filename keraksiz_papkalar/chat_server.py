#!/usr/bin/env python3
"""Gemini web-chat — bitta faylli, streaming interfeys.

Ishga tushirish:
    source ~/agv/bin/activate
    export GEMINI_API_KEY="sizning_kalitingiz"
    python chat_server.py

So'ng brauzerda: http://localhost:8765
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    from google import genai
    from google.genai import types
except Exception as e:  # pragma: no cover
    sys.exit(f"google-genai topilmadi ({e}). venv'ni yoqing: source ~/agv/bin/activate")

PORT = int(os.environ.get("PORT", "8765"))
API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

FALLBACK = "gemini-flash-latest"

MODELS = [
    {"id": "gemini-flash-latest",    "label": "gemini-flash-latest — bepul ✅"},
    {"id": "gemini-3-flash-preview", "label": "gemini-3-flash-preview — bepul ✅"},
    {"id": "gemini-3-pro-preview",   "label": "gemini-3-pro-preview — pulli reja 💳"},
    {"id": "gemini-pro-latest",      "label": "gemini-pro-latest — pulli reja 💳"},
]

client = genai.Client(api_key=API_KEY) if API_KEY else None

PAGE = r"""<!doctype html>
<html lang="uz">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MUHASIB Antigravity Chat</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Google+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');
  
  :root {
    --bg: #0b0f19;
    --panel: rgba(22, 27, 34, 0.78);
    --panel-solid: #161b22;
    --border: rgba(255, 255, 255, 0.12);
    --border-hover: rgba(66, 133, 244, 0.4);
    --text: #e6edf3;
    --ink: #ffffff;
    --muted: #8b949e;
    --user: #1f6feb;
    --accent: #238636;
    --code: #090d14;
    --card-shadow: 0 12px 32px rgba(0,0,0,0.35);
    --glass-blur: blur(16px);
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: "Google Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: var(--bg); color: var(--text); height: 100dvh; display: flex; flex-direction: column; overflow: hidden;
  }
  #agCanvas { position: fixed; inset: 0; pointer-events: none; z-index: 0; width: 100%; height: 100%; }
  #antigravity-bg {
    position: fixed; inset: 0; pointer-events: none; z-index: 0; display: flex; flex-direction: column;
    align-items: center; justify-content: center; opacity: 0.14; user-select: none; transition: transform 0.2s ease-out;
  }
  .ag-line {
    font-family: 'Google Sans', sans-serif; font-weight: 800; letter-spacing: 8px; text-transform: uppercase;
    display: flex; gap: 6px; line-height: 1.05; filter: drop-shadow(0 0 25px rgba(66,133,244,0.4));
  }
  .ag-line.word-1 { font-size: clamp(3.2rem, 9vw, 7.5rem); animation: agFloat1 7s ease-in-out infinite alternate; }
  .ag-line.word-2 { font-size: clamp(1.8rem, 5vw, 4.2rem); letter-spacing: 14px; margin-top: 8px; animation: agFloat2 8s ease-in-out infinite alternate; }
  .ag-line span { display: inline-block; transition: transform 0.3s ease; }
  .ag-line span:hover { transform: translateY(-18px) scale(1.25); }
  .c-blue { color: #4285f4; } .c-red { color: #ea4335; } .c-yellow { color: #fbbc05; } .c-green { color: #34a853; }
  @keyframes agFloat1 { 0% { transform: translateY(0) rotate(0deg); } 100% { transform: translateY(-14px) rotate(1deg); } }
  @keyframes agFloat2 { 0% { transform: translateY(0) rotate(0deg); } 100% { transform: translateY(14px) rotate(-1deg); } }

  body.zero-g-active .ag-line span { animation: zeroGFloat 4s ease-in-out infinite alternate !important; }
  @keyframes zeroGFloat { 0% { transform: translateY(-35px) rotate(-15deg); } 100% { transform: translateY(25px) rotate(20deg); } }

  header {
    position: relative; z-index: 10; margin: 12px 20px 6px 20px; padding: 10px 20px;
    border: 1px solid var(--border); border-radius: 20px;
    background: var(--panel); backdrop-filter: var(--glass-blur); -webkit-backdrop-filter: var(--glass-blur);
    display: flex; align-items: center; gap: 12px; flex-wrap: wrap; box-shadow: 0 4px 20px rgba(0,0,0,0.06);
    transition: border-color 0.25s, box-shadow 0.25s;
  }
  header:hover { border-color: var(--border-hover); box-shadow: 0 6px 28px rgba(0,0,0,0.09); }
  header h1 { font-size: 18px; margin: 0; font-weight: 700; color: var(--ink); display: flex; align-items: center; gap: 10px; }
  .dot { width: 10px; height: 10px; border-radius: 50%; background: #34a853; box-shadow: 0 0 10px #34a853; }
  header .spacer { flex: 1; }
  select, button {
    background: var(--user); color: #fff; border: 1px solid var(--border); border-radius: 22px;
    padding: 8px 18px; font-size: 13.5px; cursor: pointer; font-weight: 600; font-family: inherit; transition: all 0.2s;
  }
  select:hover, button:hover { opacity: 0.92; transform: translateY(-2px); }
  button.ghost, select { background: var(--bg); color: var(--text); border: 1px solid var(--border); }
  
  .zerog-btn {
    background: linear-gradient(135deg, rgba(161,66,244,0.2), rgba(66,133,244,0.2)) !important;
    border: 1px solid rgba(161,66,244,0.4) !important; color: #a142f4 !important;
  }
  .zerog-btn.active {
    background: linear-gradient(135deg, #a142f4, #4285f4) !important; color: #fff !important;
    box-shadow: 0 0 20px rgba(161,66,244,0.5) !important;
  }

  #chat { position: relative; z-index: 1; flex: 1; overflow-y: auto; padding: 24px 16px; scroll-behavior: smooth; }
  .wrap { max-width: 880px; width: 100%; margin: 0 auto; display: flex; flex-direction: column; gap: 18px; }
  .msg { display: flex; gap: 14px; align-items: flex-start; animation: msgSlide 0.3s ease-out; }
  @keyframes msgSlide { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); } }
  .msg .av {
    width: 34px; height: 34px; border-radius: 50%; flex: 0 0 34px; display: grid; place-items: center;
    font-size: 14px; font-weight: 700; color: #fff; box-shadow: 0 4px 12px rgba(0,0,0,0.2);
  }
  .msg.user .av { background: linear-gradient(135deg, #1f6feb, #4285f4); }
  .msg.model .av { background: conic-gradient(from 0.25turn, #4285f4, #ea4335, #fbbc05, #34a853, #4285f4); }
  .bubble {
    background: var(--panel); border: 1px solid var(--border); border-radius: 20px;
    padding: 14px 20px; line-height: 1.65; word-wrap: break-word; overflow-x: auto; min-width: 0;
    backdrop-filter: var(--glass-blur); box-shadow: var(--card-shadow); font-size: 15px;
  }
  .bubble pre { background: var(--code); border: 1px solid var(--border); border-radius: 10px; padding: 12px; overflow-x: auto; font-family: 'JetBrains Mono', monospace; font-size: 13px; }
  .bubble code { background: var(--code); padding: 2px 6px; border-radius: 6px; font-family: 'JetBrains Mono', monospace; font-size: 13px; }
  .bubble pre code { background: none; padding: 0; }
  .cursor::after { content: "▋"; color: #4285f4; animation: blink 1s steps(1) infinite; }
  @keyframes blink { 50% { opacity: 0; } }

  footer {
    position: relative; z-index: 10; border-top: none !important; background: transparent !important;
    backdrop-filter: none !important; -webkit-backdrop-filter: none !important; padding: 14px 20px; box-shadow: none !important;
  }
  /* Antigravity Input Card CSS */
  .ag-workspace-selector { display: flex; align-items: center; justify-content: center; gap: 8px; margin-bottom: 12px; font-size: 14.5px; color: var(--muted); font-weight: 500; }
  .ag-ws-btn { background: transparent; color: var(--text); border: none; padding: 3px 8px; font-size: 14.5px; font-weight: 600; cursor: pointer; display: inline-flex; align-items: center; gap: 6px; border-radius: 8px; }
  .ag-ws-btn:hover { background: rgba(255,255,255,0.08); }
  .ag-input-card {
    position: relative; max-width: 720px; margin: 0 auto; background: var(--panel); border-radius: 20px; padding: 16px 18px 12px 18px;
    box-shadow: -15px -10px 40px rgba(66, 133, 244, 0.2), 0px -15px 35px rgba(161, 66, 244, 0.16), 20px 10px 40px rgba(234, 67, 53, 0.16), 0px 20px 35px rgba(251, 188, 5, 0.16), -15px 20px 35px rgba(52, 168, 83, 0.16);
    border: 1.5px solid transparent; background-clip: padding-box; transition: box-shadow 0.3s ease;
  }
  .ag-input-card::before {
    content: ''; position: absolute; inset: -1.5px; border-radius: 21.5px; padding: 1.5px;
    background: linear-gradient(135deg, #4285f4 0%, #a142f4 25%, #ea4335 50%, #fbbc05 75%, #34a853 100%);
    -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0); -webkit-mask-composite: xor; mask-composite: exclude; pointer-events: none; opacity: 0.85;
  }
  .ag-input-card:focus-within::before { opacity: 1; }
  #input { width: 100%; resize: none; background: transparent; color: var(--text); border: none; outline: none; font-size: 15.5px; font-family: inherit; line-height: 1.5; min-height: 48px; max-height: 160px; padding: 0 4px 10px 4px; }
  #input::placeholder { color: var(--muted); opacity: 0.7; font-size: 15.5px; }
  .ag-input-footer-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: 4px; }
  .ag-input-left-tools { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
  .ag-tool-btn { background: transparent; color: var(--text); border: 1px solid var(--border); border-radius: 999px; padding: 5px 12px; font-size: 13px; font-weight: 500; cursor: pointer; display: inline-flex; align-items: center; gap: 4px; }
  .ag-tool-btn:hover { background: rgba(255,255,255,0.08); }
  .ag-plus-btn { width: 28px; height: 28px; padding: 0; display: grid; place-items: center; font-size: 18px; border-radius: 50%; border: none; color: var(--muted); }
  .ag-plus-btn:hover { color: var(--text); background: rgba(255,255,255,0.08); }
  .ag-model-select-wrap { position: relative; display: inline-flex; align-items: center; }
  .ag-model-select-wrap .ag-model-chevron { position: absolute; left: 10px; font-size: 11px; color: var(--muted); pointer-events: none; }
  .ag-model-select { appearance: none; -webkit-appearance: none; background: transparent !important; color: var(--text) !important; border: 1px solid var(--border) !important; border-radius: 999px; padding: 5px 12px 5px 22px; font-size: 13px; font-weight: 500; font-family: inherit; cursor: pointer; outline: none; }
  .ag-send-circle-btn { width: 34px; height: 34px; border-radius: 50%; background: #0084ff; color: #ffffff; border: none; display: grid; place-items: center; cursor: pointer; flex-shrink: 0; box-shadow: 0 2px 8px rgba(0, 132, 255, 0.35); transition: transform 0.2s, background 0.2s; }
  .ag-send-circle-btn:hover { background: #0073e6; transform: scale(1.06); }
  .hint { color: var(--muted); font-size: 12px; text-align: center; margin-top: 8px; }
</style>
</head>
<body>
<canvas id="agCanvas"></canvas>
<div id="antigravity-bg" style="display:none;"></div>
<header>
  <h1><span class="dot"></span> MUHASIB Antigravity Chat</h1>
  <span class="spacer"></span>
  <button id="zeroGBtn" class="ghost zerog-btn" title="Zero-G Physics">🌌 Zero-G Physics</button>
  <button id="clear" class="ghost">Tozalash</button>
</header>
<div id="chat"><div class="wrap" id="wrap"></div></div>
<footer>
  <div id="imgPreviewBar" class="img-preview-bar hidden">
    <img id="imgPreview" src="" alt="preview">
    <button id="removeImg" class="remove-btn" title="O'chirish">✕</button>
    <span style="font-size:12px;color:var(--muted)">Rasm biriktirildi</span>
  </div>

  <div class="ag-workspace-selector">
    <span class="ag-ws-label">Start new conversation in</span>
    <button type="button" class="ag-ws-btn">
      <span class="ag-ws-chevron">˅</span>
      <span>Folder</span>
    </button>
  </div>

  <div class="ag-input-card">
    <textarea id="input" rows="2" placeholder="Ask anything, @ for context"></textarea>
    <div class="ag-input-footer-row">
      <div class="ag-input-left-tools">
        <input type="file" id="fileInput" accept="image/*" style="display:none">
        <button id="attachBtn" class="ag-tool-btn ag-plus-btn" title="Rasm biriktirish">+</button>
        <button class="ag-tool-btn" type="button">
          <span>˅ Planning</span>
        </button>
        <div class="ag-model-select-wrap">
          <span class="ag-model-chevron">˅</span>
          <select id="model" class="ag-model-select" title="Gemini modelini tanlang"></select>
        </div>
      </div>
      <button id="send" class="ag-send-circle-btn" title="Yuborish">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <line x1="5" y1="12" x2="19" y2="12"></line>
          <polyline points="12 5 19 12 12 19"></polyline>
        </svg>
      </button>
    </div>
  </div>
  <div class="hint" id="hint"></div>
</footer>
<script>
// Canvas Anti-Gravity Particles Engine
(function() {
  const canvas = document.getElementById('agCanvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let width, height, particles = [];
  let mouse = { x: -1000, y: -1000, active: false };
  let zeroGActive = false;
  const colors = ['#4285f4', '#ea4335', '#fbbc05', '#34a853', '#a142f4'];

  function resize() { width = canvas.width = window.innerWidth; height = canvas.height = window.innerHeight; }
  window.addEventListener('resize', resize); resize();

  class Particle {
    constructor() { this.reset(); }
    reset() {
      this.x = Math.random() * width; this.y = Math.random() * height;
      this.vx = (Math.random() - 0.5) * 0.8; this.vy = (Math.random() - 0.5) * 0.8;
      this.radius = Math.random() * 3 + 2; this.color = colors[Math.floor(Math.random() * colors.length)];
      this.alpha = Math.random() * 0.5 + 0.3; this.pulse = Math.random() * Math.PI * 2;
    }
    update() {
      this.pulse += 0.03;
      if (zeroGActive) { this.vx += (Math.random() - 0.5) * 0.2; this.vy += (Math.random() - 0.5) * 0.2; }
      this.x += this.vx; this.y += this.vy;
      if (mouse.active) {
        const dx = this.x - mouse.x, dy = this.y - mouse.y, dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 180 && dist > 0) {
          const push = ((180 - dist) / 180) * (zeroGActive ? 4 : 2);
          this.vx += (dx / dist) * push * 0.1; this.vy += (dy / dist) * push * 0.1;
        }
      }
      this.vx *= 0.98; this.vy *= 0.98;
      if (this.x < 0 || this.x > width) this.vx *= -1;
      if (this.y < 0 || this.y > height) this.vy *= -1;
    }
    draw() {
      ctx.save(); ctx.globalAlpha = this.alpha + Math.sin(this.pulse) * 0.15;
      ctx.fillStyle = this.color; ctx.shadowBlur = 10; ctx.shadowColor = this.color;
      ctx.beginPath(); ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2); ctx.fill(); ctx.restore();
    }
  }

  for (let i = 0; i < 60; i++) particles.push(new Particle());
  window.addEventListener('mousemove', e => { mouse.x = e.clientX; mouse.y = e.clientY; mouse.active = true; });
  window.addEventListener('mouseleave', () => mouse.active = false);

  const zeroGBtn = document.getElementById('zeroGBtn');
  if (zeroGBtn) {
    zeroGBtn.addEventListener('click', () => {
      zeroGActive = !zeroGActive;
      document.body.classList.toggle('zero-g-active', zeroGActive);
      zeroGBtn.classList.toggle('active', zeroGActive);
      if (zeroGActive) particles.forEach(p => { p.vx = (Math.random() - 0.5) * 8; p.vy = (Math.random() - 0.5) * 8; });
    });
  }

  function animate() {
    ctx.clearRect(0, 0, width, height);
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const dx = particles[i].x - particles[j].x, dy = particles[i].y - particles[j].y, dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 120) {
          ctx.save(); ctx.globalAlpha = (1 - dist / 120) * 0.15; ctx.strokeStyle = particles[i].color; ctx.lineWidth = 0.8;
          ctx.beginPath(); ctx.moveTo(particles[i].x, particles[i].y); ctx.lineTo(particles[j].x, particles[j].y); ctx.stroke(); ctx.restore();
        }
      }
    }
    particles.forEach(p => { p.update(); p.draw(); });
    requestAnimationFrame(animate);
  }
  animate();
})();

const MODELS = __MODELS__;
const wrap = document.getElementById('wrap');
const input = document.getElementById('input');
const send = document.getElementById('send');
const modelSel = document.getElementById('model');
const hint = document.getElementById('hint');

const attachBtn = document.getElementById('attachBtn');
const fileInput = document.getElementById('fileInput');
const imgPreviewBar = document.getElementById('imgPreviewBar');
const imgPreview = document.getElementById('imgPreview');
const removeImg = document.getElementById('removeImg');

let currentImage = null; // { mime_type, data, src }
let history = [];   // [{role, text, image}]
let busy = false;

MODELS.forEach(m => { const o=document.createElement('option'); o.value=m.id; o.textContent=m.label; modelSel.appendChild(o); });

attachBtn.onclick = () => fileInput.click();
fileInput.onchange = e => {
  if(e.target.files && e.target.files[0]) processFile(e.target.files[0]);
};
removeImg.onclick = clearAttachedImage;

function clearAttachedImage(){
  currentImage = null;
  imgPreview.src = '';
  imgPreviewBar.classList.add('hidden');
  fileInput.value = '';
}

function processFile(file){
  if(!file.type.startsWith('image/')) return;
  const r = new FileReader();
  r.onload = ev => {
    const src = ev.target.result;
    const parts = src.split(',');
    const mimeMatch = parts[0].match(/:(.*?);/);
    const mime_type = mimeMatch ? mimeMatch[1] : file.type;
    const data = parts[1];
    currentImage = { mime_type, data, src };
    imgPreview.src = src;
    imgPreviewBar.classList.remove('hidden');
  };
  r.readAsDataURL(file);
}

// Paste support (Ctrl+V / Cmd+V)
window.addEventListener('paste', e => {
  const items = (e.clipboardData || e.originalEvent?.clipboardData)?.items || [];
  for (const item of items) {
    if (item.kind === 'file' && item.type.startsWith('image/')) {
      const file = item.getAsFile();
      if (file) processFile(file);
    }
  }
});

// Drag and drop support
const dropFooter = document.querySelector('footer');
dropFooter.addEventListener('dragover', e => { e.preventDefault(); });
dropFooter.addEventListener('drop', e => {
  e.preventDefault();
  if (e.dataTransfer?.files?.[0]) {
    processFile(e.dataTransfer.files[0]);
  }
});

function esc(s){ return (s||'').replace(/[&<>]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }
function render(md){
  let h = esc(md);
  h = h.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, function(_, alt, src){
    let url = src.trim();
    if(url.startsWith('file://')) url = url.slice(7);
    if(url.startsWith('/') || url.startsWith('http://') || url.startsWith('https://') || url.startsWith('data:')){
      if(url.startsWith('/')) {
        url = '/api/file?path=' + encodeURIComponent(url);
      }
    }
    return `<img src="${url}" class="chat-img" alt="${alt}">`;
  });
  h = h.replace(/```([\s\S]*?)```/g, (_,c)=>'<pre><code>'+c.replace(/^\n/,'')+'</code></pre>');
  h = h.replace(/`([^`\n]+)`/g, '<code>$1</code>');
  h = h.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  return h;
}
function addMsg(role, text, imgData){
  const m = document.createElement('div'); m.className = 'msg '+role;
  const av = document.createElement('div'); av.className='av'; av.textContent = role==='user'?'S':'✦';
  const b = document.createElement('div'); b.className='bubble';
  let html = '';
  if(imgData && imgData.src){
    html += '<img src="'+esc(imgData.src)+'" class="chat-img" alt="image"><br>';
  }
  html += render(text||'');
  b.innerHTML = html;
  m.appendChild(av); m.appendChild(b); wrap.appendChild(m);
  document.getElementById('chat').scrollTop = 1e9;
  return b;
}
function autoscroll(){ document.getElementById('chat').scrollTop = 1e9; }

async function submit(){
  const text = input.value.trim();
  if((!text && !currentImage) || busy) return;
  busy = true; send.disabled = true; hint.textContent='';
  const imgToSend = currentImage;
  clearAttachedImage();
  input.value=''; input.style.height='auto';
  
  addMsg('user', text, imgToSend);
  history.push({
    role: 'user',
    text: text,
    image: imgToSend ? { mime_type: imgToSend.mime_type, data: imgToSend.data } : null
  });
  
  const bubble = addMsg('model', ''); bubble.classList.add('cursor');
  let acc = '';
  try {
    const res = await fetch('/api/chat', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({model: modelSel.value, messages: history})
    });
    if(!res.ok){ throw new Error('HTTP '+res.status+': '+await res.text()); }
    const reader = res.body.getReader();
    const dec = new TextDecoder(); let buf='';
    while(true){
      const {value, done} = await reader.read(); if(done) break;
      buf += dec.decode(value, {stream:true});
      let idx;
      while((idx = buf.indexOf('\n\n')) >= 0){
        const chunk = buf.slice(0, idx); buf = buf.slice(idx+2);
        for(const line of chunk.split('\n')){
          if(!line.startsWith('data:')) continue;
          const payload = JSON.parse(line.slice(5).trim());
          if(payload.error){ acc += '\n⚠️ '+payload.error; }
          else if(payload.text){ acc += payload.text; }
          bubble.innerHTML = render(acc); autoscroll();
        }
      }
    }
    history.push({role:'model', text: acc});
  } catch(e){
    bubble.innerHTML = render(acc + '\n\n⚠️ Xatolik: '+e.message);
  } finally {
    bubble.classList.remove('cursor');
    busy=false; send.disabled=false; input.focus();
  }
}
send.onclick = submit;
input.addEventListener('keydown', e=>{ if(e.key==='Enter' && !e.shiftKey){ e.preventDefault(); submit(); }});
input.addEventListener('input', ()=>{ input.style.height='auto'; input.style.height=Math.min(input.scrollHeight,180)+'px'; });
document.getElementById('clear').onclick = ()=>{ history=[]; wrap.innerHTML=''; clearAttachedImage(); input.focus(); };
input.focus();
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # tinch log
        pass

    def _send(self, code, ctype, body=b""):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            html = PAGE.replace("__MODELS__", json.dumps(MODELS))
            self._send(200, "text/html; charset=utf-8", html.encode("utf-8"))
        elif self.path.startswith("/api/file"):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            p = q.get("path", [""])[0]
            p = os.path.abspath(os.path.expanduser(p))
            if p and os.path.exists(p) and os.path.isfile(p):
                mime = "image/jpeg"
                ext = os.path.splitext(p)[1].lower()
                if ext == ".png": mime = "image/png"
                elif ext == ".webp": mime = "image/webp"
                elif ext == ".gif": mime = "image/gif"
                elif ext == ".svg": mime = "image/svg+xml"
                try:
                    with open(p, "rb") as f:
                        data = f.read()
                    self.send_response(200)
                    self.send_header("Content-Type", mime)
                    self.send_header("Content-Length", str(len(data)))
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(data)
                    return
                except Exception:
                    pass
            self._send(404, "text/plain; charset=utf-8", b"not found")
        else:
            self._send(404, "text/plain; charset=utf-8", b"not found")

    def do_POST(self):
        if self.path != "/api/chat":
            self._send(404, "text/plain", b"not found")
            return
        if client is None:
            self._send(500, "text/plain; charset=utf-8",
                       "GEMINI_API_KEY o'rnatilmagan".encode("utf-8"))
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(length) or b"{}")
            model = data.get("model") or MODELS[0]["id"]
            msgs = data.get("messages") or []
            contents = []
            for m in msgs:
                role = "user" if m.get("role") == "user" else "model"
                parts = []
                img = m.get("image")
                if img and isinstance(img, dict) and img.get("data"):
                    parts.append({
                        "inline_data": {
                            "mime_type": img.get("mime_type", "image/png"),
                            "data": img.get("data")
                        }
                    })
                if m.get("text"):
                    parts.append({"text": m.get("text")})
                if parts:
                    contents.append({"role": role, "parts": parts})
        except Exception as e:
            self._send(400, "text/plain; charset=utf-8", f"bad request: {e}".encode())
            return

        # SSE streaming
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        def sse(obj):
            self.wfile.write(b"data: " + json.dumps(obj).encode("utf-8") + b"\n\n")
            self.wfile.flush()

        def friendly(err):
            m = str(err)
            if "RESOURCE_EXHAUSTED" in m or "429" in m or "quota" in m.lower():
                return "Kvota tugagan: bu model bepul rejada mavjud emas (limit = 0). Pulli reja yoqing yoki bepul modelni tanlang."
            if "NOT_FOUND" in m or "no longer available" in m:
                return "Bu model bu kalit uchun mavjud emas. Boshqa modelni tanlang."
            if "PERMISSION_DENIED" in m or "API key" in m or "401" in m or "403" in m:
                return "Kalit qabul qilinmadi (GEMINI_API_KEY ni tekshiring)."
            return f"{type(err).__name__}: {m[:200]}"

        def stream_model(name):
            emitted = 0
            for chunk in client.models.generate_content_stream(model=name, contents=contents):
                t = getattr(chunk, "text", None)
                if t:
                    emitted += len(t)
                    sse({"text": t})
            return emitted

        try:
            stream_model(model)
        except Exception as e:
            recoverable = any(k in str(e) for k in ("RESOURCE_EXHAUSTED", "429", "NOT_FOUND", "no longer available")) \
                or "quota" in str(e).lower()
            if recoverable and model != FALLBACK:
                sse({"text": f"ℹ️ «{model}» ishlamadi ({friendly(e)}) — «{FALLBACK}» bilan javob beraman:\n\n"})
                try:
                    stream_model(FALLBACK)
                except Exception as e2:
                    sse({"error": friendly(e2)})
            else:
                sse({"error": friendly(e)})
        try:
            self.wfile.write(b"event: done\ndata: {}\n\n")
            self.wfile.flush()
        except Exception:
            pass


def main():
    if not API_KEY:
        print("⚠️  GEMINI_API_KEY o'rnatilmagan. Ishga tushishdan oldin:")
        print('    export GEMINI_API_KEY="sizning_kalitingiz"')
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"✅ Gemini Chat: http://localhost:{PORT}  (to'xtatish: Ctrl+C)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nto'xtatildi.")


if __name__ == "__main__":
    main()
