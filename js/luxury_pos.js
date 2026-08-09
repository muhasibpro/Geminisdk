/* LUXURY RETAIL / MUHASIB POS - Master Application Logic */

const PRODUCTS = [
  { id: 'j1', name: 'DIAMOND ECLIPSE RING', category: 'JEWELRY', price: 12500, specs: 'Solitaire Cushion Diamond, Platinum', img: 'images/diamond_eclipse_ring_1785603522622.jpg' },
  { id: 'j2', name: 'ROYAL EMERALD CUT RING', category: 'JEWELRY', price: 15800, specs: '3.8 Carat Emerald Cut, 18K Gold', img: 'images/diamond_eclipse_ring_1785603522622.jpg' },
  { id: 'j3', name: 'SAPPHIRE NIGHT SOLITAIRE', category: 'JEWELRY', price: 19500, specs: '4.2 Carat Ceylon Sapphire, Platinum', img: 'images/diamond_eclipse_ring_1785603522622.jpg' },
  { id: 'w1', name: 'ORION CHRONOGRAPH WATCH', category: 'WATCHES', price: 12500, specs: 'Rose Gold Skeleton Dial, Sapphire', img: 'images/orion_watch_1785603534746.jpg' },
  { id: 'w2', name: 'NEBULA TOURBILLON', category: 'WATCHES', price: 28900, specs: 'Titanium Case, Automatic Movement', img: 'images/orion_watch_1785603534746.jpg' },
  { id: 'l1', name: 'ROYAL ITALIAN HANDBAG', category: 'LEATHER GOODS', price: 8900, specs: 'Calfskin Leather, 24K Gold Clasp', img: 'images/leather_handbag_1785603570147.jpg' },
  { id: 'l2', name: 'CYBER LEATHER BRIEFCASE', category: 'LEATHER GOODS', price: 6400, specs: 'Biometric Lock, Carbon Texture', img: 'images/leather_handbag_1785603570147.jpg' },
  { id: 'p1', name: 'AURORA ELIXIR PARFUM', category: 'PERFUME', price: 4800, specs: 'Crystal Decanter, Amber & Oud 100ml', img: 'images/luxury_perfume_1785603558636.jpg' },
  { id: 'p2', name: 'EMERALD NIGHT EXTRACT', category: 'PERFUME', price: 3200, specs: 'Pure Bergamot & Iris Absolute', img: 'images/luxury_perfume_1785603558636.jpg' },
  { id: 'a1', name: 'CYBER NANOFIBER BLAZER', category: 'APPAREL', price: 6200, specs: 'Climate Adaptive Nanofiber Silk', img: 'images/flyer_hero.jpg' },
  { id: 'c1', name: 'SOLARIS GOLD MEDALLION', category: 'COLLECTIBLES', price: 15000, specs: '24K Pure Gold Minted Artifact', img: 'images/flyer_secondary.jpg' }
];

const CATEGORIES = ['JEWELRY', 'WATCHES', 'LEATHER GOODS', 'PERFUME', 'APPAREL', 'COLLECTIBLES'];

let state = {
  activeCategory: 'JEWELRY',
  cart: [
    { ...PRODUCTS[0], qty: 1 }
  ],
  numpadValue: '',
  totalRevenue: 45678,
  salesVolume: 124
};

// Web Audio API Synthesizer for High-Tech Sound FX
class SoundFX {
  constructor() {
    this.ctx = null;
  }
  init() {
    if (!this.ctx) {
      this.ctx = new (window.AudioContext || window.webkitAudioContext)();
    }
  }
  playBeep(freq = 800, duration = 0.08, type = 'sine') {
    try {
      this.init();
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.type = type;
      osc.frequency.setValueAtTime(freq, this.ctx.currentTime);
      gain.gain.setValueAtTime(0.15, this.ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, this.ctx.currentTime + duration);
      osc.connect(gain);
      gain.connect(this.ctx.destination);
      osc.start();
      osc.stop(this.ctx.currentTime + duration);
    } catch(e){}
  }
  playChime() {
    try {
      this.init();
      [523.25, 659.25, 783.99, 1046.50].forEach((freq, idx) => {
        setTimeout(() => this.playBeep(freq, 0.15, 'triangle'), idx * 60);
      });
    } catch(e){}
  }
  playCheckout() {
    try {
      this.init();
      [440, 554.37, 659.25, 880, 1108.73].forEach((freq, idx) => {
        setTimeout(() => this.playBeep(freq, 0.25, 'sine'), idx * 80);
      });
    } catch(e){}
  }
}

const sound = new SoundFX();

// DOM Content Loaded
document.addEventListener('DOMContentLoaded', () => {
  initClock();
  renderWheel();
  renderProducts();
  renderNumpad();
  initSalesChart();
  updateCartDisplay();
});

// Real-time HUD Clock
function initClock() {
  const clockEl = document.getElementById('timeDisplay');
  function update() {
    const now = new Date();
    const hrs = String(now.getHours()).padStart(2, '0');
    const mins = String(now.getMinutes()).padStart(2, '0');
    const secs = String(now.getSeconds()).padStart(2, '0');
    if (clockEl) clockEl.innerText = `${hrs}:${mins}:${secs}`;
  }
  update();
  setInterval(update, 1000);
}

// Render SVG Radial Wheel
function renderWheel() {
  const svg = document.getElementById('svgWheel');
  if (!svg) return;

  const cx = 215, cy = 215, outerR = 210, innerR = 110;
  const numSlices = CATEGORIES.length;
  const sliceAngle = 360 / numSlices;

  let html = `
    <defs>
      <linearGradient id="goldGradient" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#ffb703" stop-opacity="0.95" />
        <stop offset="100%" stop-color="#f77f00" stop-opacity="0.95" />
      </linearGradient>
    </defs>
  `;

  CATEGORIES.forEach((cat, idx) => {
    const startDeg = idx * sliceAngle - 90;
    const endDeg = (idx + 1) * sliceAngle - 90;

    const startRad = (startDeg * Math.PI) / 180;
    const endRad = (endDeg * Math.PI) / 180;

    const x1 = cx + outerR * Math.cos(startRad);
    const y1 = cy + outerR * Math.sin(startRad);
    const x2 = cx + outerR * Math.cos(endRad);
    const y2 = cy + outerR * Math.sin(endRad);

    const x3 = cx + innerR * Math.cos(endRad);
    const y3 = cy + innerR * Math.sin(endRad);
    const x4 = cx + innerR * Math.cos(startRad);
    const y4 = cy + innerR * Math.sin(startRad);

    const d = `M ${x1} ${y1} A ${outerR} ${outerR} 0 0 1 ${x2} ${y2} L ${x3} ${y3} A ${innerR} ${innerR} 0 0 0 ${x4} ${y4} Z`;

    const midRad = (startRad + endRad) / 2;
    const textR = (outerR + innerR) / 2;
    const tx = cx + textR * Math.cos(midRad);
    const ty = cy + textR * Math.sin(midRad);
    
    let textAngle = (midRad * 180) / Math.PI + 90;
    // Keep text upright
    if (textAngle > 90 && textAngle < 270) {
      textAngle += 180;
    }

    const isActive = cat === state.activeCategory;

    html += `
      <g>
        <path class="wheel-slice ${isActive ? 'active' : ''}" d="${d}" data-category="${cat}" onclick="selectCategory('${cat}', ${idx})" />
        <text class="wheel-text" x="${tx}" y="${ty}" transform="rotate(${textAngle}, ${tx}, ${ty})">${cat}</text>
      </g>
    `;
  });

  svg.innerHTML = html;
}

function selectCategory(cat, index) {
  sound.playBeep(900, 0.08);
  state.activeCategory = cat;

  // Highlight active category & update catalog
  document.getElementById('hubCategoryTitle').innerText = cat;
  renderWheel();
  renderProducts();
}

// Render Products Grid
function renderProducts() {
  const container = document.getElementById('productsContainer');
  if (!container) return;

  const filtered = PRODUCTS.filter(p => p.category === state.activeCategory);

  container.innerHTML = filtered.map(p => `
    <div class="product-card" onclick="addToCart('${p.id}')">
      <img src="${p.img}" class="product-thumb" alt="${p.name}">
      <div class="product-info">
        <div class="product-name">${p.name}</div>
        <div class="product-specs">${p.specs}</div>
        <div class="product-price-row">
          <div class="product-price">$${p.price.toLocaleString()}</div>
          <button class="add-btn">+</button>
        </div>
      </div>
    </div>
  `).join('');
}

// Add Item to Cart
function addToCart(productId) {
  sound.playChime();
  const prod = PRODUCTS.find(p => p.id === productId);
  if (!prod) return;

  const existing = state.cart.find(item => item.id === productId);
  if (existing) {
    existing.qty++;
  } else {
    state.cart.push({ ...prod, qty: 1 });
  }

  updateCartDisplay();
}

function updateCartDisplay() {
  const total = state.cart.reduce((sum, item) => sum + item.price * item.qty, 0);
  const checkoutBtnVal = document.getElementById('checkoutTotalDisplay');
  const hubVal = document.getElementById('hubValueDisplay');
  const numpadDisplay = document.getElementById('numpadDisplay');

  if (checkoutBtnVal) checkoutBtnVal.innerText = `$${total.toLocaleString()}`;
  if (hubVal) hubVal.innerText = `$${total.toLocaleString()}`;
  if (numpadDisplay && !state.numpadValue) {
    numpadDisplay.innerText = `$${total.toLocaleString()}`;
  }
}

// Transaction Input Numpad
function renderNumpad() {
  const display = document.getElementById('numpadDisplay');
  const buttons = document.querySelectorAll('.num-btn[data-val]');

  buttons.forEach(btn => {
    btn.addEventListener('click', () => {
      sound.playBeep(1200, 0.05);
      const val = btn.getAttribute('data-val');

      if (val === 'C') {
        state.numpadValue = '';
      } else if (val === 'DEL') {
        state.numpadValue = state.numpadValue.slice(0, -1);
      } else {
        state.numpadValue += val;
      }

      if (display) {
        display.innerText = state.numpadValue || `$${state.cart.reduce((sum, i) => sum + i.price * i.qty, 0).toLocaleString()}`;
      }
    });
  });
}

// Live Bezier Sales Chart Canvas
function initSalesChart() {
  const canvas = document.getElementById('salesChart');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  const width = (canvas.width = canvas.parentElement.clientWidth);
  const height = (canvas.height = canvas.parentElement.clientHeight);

  const points1 = [20, 45, 30, 70, 50, 85, 40, 65, 80, 95];
  const points2 = [10, 30, 25, 45, 35, 60, 55, 40, 70, 80];

  function drawLine(points, strokeColor, fillColor) {
    ctx.beginPath();
    const step = width / (points.length - 1);

    ctx.moveTo(0, height - points[0]);
    for (let i = 0; i < points.length - 1; i++) {
      const x1 = i * step;
      const y1 = height - points[i];
      const x2 = (i + 1) * step;
      const y2 = height - points[i + 1];
      const cx = (x1 + x2) / 2;
      ctx.bezierCurveTo(cx, y1, cx, y2, x2, y2);
    }

    ctx.strokeStyle = strokeColor;
    ctx.lineWidth = 3;
    ctx.stroke();

    ctx.lineTo(width, height);
    ctx.lineTo(0, height);
    ctx.closePath();
    ctx.fillStyle = fillColor;
    ctx.fill();
  }

  ctx.clearRect(0, 0, width, height);

  const grad1 = ctx.createLinearGradient(0, 0, 0, height);
  grad1.addColorStop(0, 'rgba(0, 230, 118, 0.35)');
  grad1.addColorStop(1, 'rgba(0, 230, 118, 0.0)');

  const grad2 = ctx.createLinearGradient(0, 0, 0, height);
  grad2.addColorStop(0, 'rgba(255, 183, 3, 0.3)');
  grad2.addColorStop(1, 'rgba(255, 183, 3, 0.0)');

  drawLine(points1, '#00e676', grad1);
  drawLine(points2, '#ffb703', grad2);
}

// AI Assistant Response Logic
function askAIAssistant() {
  const input = document.getElementById('aiInput');
  const subtitle = document.getElementById('aiSubtitle');
  if (!input || !input.value.trim()) return;

  sound.playBeep(1000, 0.1);
  const q = input.value.trim();
  input.value = '';

  if (subtitle) {
    subtitle.innerText = 'AI Thinking...';
  }

  setTimeout(() => {
    let response = "AI Insight: Peak sales velocity detected in Jewelry. Recommended bundle: Orion Watch + Diamond Ring for +18% margin.";
    if (q.toLowerCase().includes('discount') || q.toLowerCase().includes('vip')) {
      response = "AI VIP Protocol: Applied 10% Loyalty discount ($1,250 reduction). VIP Customer Verified.";
    } else if (q.toLowerCase().includes('best') || q.toLowerCase().includes('popular')) {
      response = "AI Analytics: Diamond Eclipse Ring is #1 top seller with 45 units sold today.";
    }
    if (subtitle) {
      subtitle.innerText = response;
    }
    sound.playChime();
  }, 600);
}

// Checkout Modal Workflow
function openCheckoutModal() {
  sound.playCheckout();
  const modal = document.getElementById('checkoutModal');
  const itemsContainer = document.getElementById('modalOrderItems');
  const totalVal = document.getElementById('modalTotalVal');

  const total = state.cart.reduce((sum, i) => sum + i.price * i.qty, 0);

  if (itemsContainer) {
    itemsContainer.innerHTML = state.cart.map(item => `
      <div class="order-item-row">
        <span>${item.qty}x ${item.name}</span>
        <span style="color: var(--color-gold-bright)">$${(item.price * item.qty).toLocaleString()}</span>
      </div>
    `).join('');
  }

  if (totalVal) {
    totalVal.innerText = `$${total.toLocaleString()}`;
  }

  if (modal) modal.classList.add('active');
}

function closeCheckoutModal() {
  const modal = document.getElementById('checkoutModal');
  if (modal) modal.classList.remove('active');
}

function confirmPayment() {
  sound.playCheckout();
  alert('✨ TRANSACTION SUCCESSFUL!\nReceipt printed & Cloud Ledger updated.');
  state.cart = [];
  state.totalRevenue += 12500;
  state.salesVolume += 1;

  document.getElementById('revenueDisplay').innerText = `$${state.totalRevenue.toLocaleString()}`;
  document.getElementById('salesVolumeDisplay').innerText = state.salesVolume;

  updateCartDisplay();
  closeCheckoutModal();
}
