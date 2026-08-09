#!/usr/bin/env python3
"""MUHASIB HISOB — suhbat orqali o'sadigan hisob-kitob dasturi.

8777 (agy_app.py) ga tegmaydi. Bu alohida ilova, 8778-portda ishlaydi.

G'oyasi: foydalanuvchi chatda "menga bugungi ma'lumotlarni ko'rsatadigan sahifa
qo'shib ber" yoki "tilla 585 ga pereshot sahifasi kerak" desa — Antigravity agent
kerakli jadvalni SQLite bazasida o'zi yaratadi va `hisob/sahifalar/` ga HTML yozadi.
Sahifa avtomatik menyuda paydo bo'ladi.

Ishga tushirish:  python3 hisob_app.py   →  http://localhost:8778
"""
import io
import json
import mimetypes
import os
import queue
import re
import shutil
import signal
import sqlite3
import subprocess
import threading
import time
import urllib.parse
import webbrowser
import zipfile
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("HISOB_PORT", "8778"))
ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "hisob")
PAGES = os.path.join(DATA, "sahifalar")
WIDGETS = os.path.join(DATA, "vidjetlar")
BACKUPS = os.path.join(DATA, "zaxira")
DB = os.path.join(DATA, "hisob.db")
AGY = os.path.expanduser("~/.local/bin/agy")
if not os.path.exists(AGY):
    AGY = shutil.which("agy") or "agy"
PRINT_TIMEOUT = os.environ.get("AGY_PRINT_TIMEOUT", "6h")

for d in (DATA, PAGES, WIDGETS, BACKUPS):
    os.makedirs(d, exist_ok=True)


# ═══════════════════════════════ BAZA ═══════════════════════════════
SCHEMA = """
CREATE TABLE IF NOT EXISTS sozlama (
  kalit TEXT PRIMARY KEY,
  qiymat TEXT
);
CREATE TABLE IF NOT EXISTS yoriqnoma (            -- "bir marta o'rgataman" — doimiy qoidalar
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  matn TEXT NOT NULL,
  sana TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS amal (                 -- kirim/chiqim yozuvlari
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  sana TEXT NOT NULL,
  tur TEXT NOT NULL,                              -- kirim | chiqim
  summa REAL NOT NULL,
  kategoriya TEXT,
  izoh TEXT
);
CREATE TABLE IF NOT EXISTS tilla_hisob (          -- tilla pereshot bazasi
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  sana TEXT NOT NULL,
  buyum_nomi TEXT,
  ogirligi_g REAL NOT NULL,
  proba INTEGER NOT NULL DEFAULT 585,             -- 585, 750, 999
  toza_tilla_g REAL NOT NULL,                     -- 585 proba uchun ogirligi * 0.585
  gramm_narxi_usd REAL,
  jami_summa_usd REAL,
  izoh TEXT
);
CREATE TABLE IF NOT EXISTS nafa_hisob (           -- nafa va foyda tahlili bazasi
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  sana TEXT NOT NULL,
  mahsulot_nomi TEXT NOT NULL,
  tan_narxi REAL NOT NULL,
  sotish_narxi REAL NOT NULL,
  nafa_summa REAL NOT NULL,
  marja_foiz REAL,
  kategoriya TEXT,
  izoh TEXT
);
CREATE INDEX IF NOT EXISTS amal_sana ON amal(sana);
CREATE INDEX IF NOT EXISTS tilla_sana ON tilla_hisob(sana);
CREATE INDEX IF NOT EXISTS nafa_sana ON nafa_hisob(sana);
"""


def db():
    c = sqlite3.connect(DB, timeout=15)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    return c


def init_db():
    with db() as c:
        c.executescript(SCHEMA)
        c.commit()
    init_default_data()


def sozlama(kalit, qiymat=None):
    with db() as c:
        if qiymat is None:
            r = c.execute("SELECT qiymat FROM sozlama WHERE kalit=?", (kalit,)).fetchone()
            return r["qiymat"] if r else ""
        c.execute("INSERT INTO sozlama(kalit,qiymat) VALUES(?,?) "
                  "ON CONFLICT(kalit) DO UPDATE SET qiymat=excluded.qiymat", (kalit, qiymat))
        c.commit()
        return qiymat


def jadvallar():
    with db() as c:
        rows = c.execute("SELECT name FROM sqlite_master WHERE type='table' "
                         "AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
        out = []
        for r in rows:
            cols = c.execute(f"PRAGMA table_info({r['name']})").fetchall()
            n = c.execute(f"SELECT COUNT(*) k FROM {r['name']}").fetchone()["k"]
            out.append({"nom": r["name"], "ustunlar": [x["name"] for x in cols], "soni": n})
        return out


def init_default_data():
    if not sozlama("biznes"):
        sozlama("biznes", "Tilla va Umumiy Savdo Do'koni")

    # Namuna ma'lumotlar bo'sh bo'lsa kirgizamiz
    with db() as c:
        cnt = c.execute("SELECT COUNT(*) c FROM amal").fetchone()["c"]
        if cnt == 0:
            bugun_str = datetime.now().strftime("%Y-%m-%d")
            c.execute("INSERT INTO amal (sana, tur, summa, kategoriya, izoh) VALUES (?, ?, ?, ?, ?)",
                      (bugun_str + " 09:30", "kirim", 2500000, "Savdo", "Eski tilla zanjir va uzuk savdosi"))
            c.execute("INSERT INTO amal (sana, tur, summa, kategoriya, izoh) VALUES (?, ?, ?, ?, ?)",
                      (bugun_str + " 11:15", "chiqim", 450000, "Xarajat", "Tushlik va dukon xarajatlari"))
            c.execute("INSERT INTO amal (sana, tur, summa, kategoriya, izoh) VALUES (?, ?, ?, ?, ?)",
                      (bugun_str + " 14:00", "kirim", 4800000, "Savdo", "Tilla bilaguzuk 585 proba"))
            c.commit()

        t_cnt = c.execute("SELECT COUNT(*) c FROM tilla_hisob").fetchone()["c"]
        if t_cnt == 0:
            bugun_str = datetime.now().strftime("%Y-%m-%d")
            c.execute("INSERT INTO tilla_hisob (sana, buyum_nomi, ogirligi_g, proba, toza_tilla_g, gramm_narxi_usd, jami_summa_usd, izoh) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                      (bugun_str, "Tilla uzuk 585", 10.5, 585, 6.1425, 65.0, 399.26, "Mijozdan qabul qilindi"))
            c.execute("INSERT INTO tilla_hisob (sana, buyum_nomi, ogirligi_g, proba, toza_tilla_g, gramm_narxi_usd, jami_summa_usd, izoh) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                      (bugun_str, "Zanjir 750", 15.0, 750, 11.25, 65.0, 731.25, "750 proba pereshot"))
            c.commit()

        n_cnt = c.execute("SELECT COUNT(*) c FROM nafa_hisob").fetchone()["c"]
        if n_cnt == 0:
            bugun_str = datetime.now().strftime("%Y-%m-%d %H:%M")
            c.execute("INSERT INTO nafa_hisob (sana, mahsulot_nomi, tan_narxi, sotish_narxi, nafa_summa, marja_foiz, kategoriya, izoh) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                      (bugun_str, "Tilla Uzuk 585", 3500000, 4200000, 700000, 20.0, "Tilla", "Mijozga sotildi"))
            c.execute("INSERT INTO nafa_hisob (sana, mahsulot_nomi, tan_narxi, sotish_narxi, nafa_summa, marja_foiz, kategoriya, izoh) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                      (bugun_str, "Zargarlik zanjiri 750", 6000000, 7500000, 1500000, 25.0, "Zargarlik", "Chegirma bilan"))
            c.commit()

    # Standart sahifalarni yaratamiz (agar yo'q bo'lsa)
    dashboard_file = os.path.join(PAGES, "01_dashboard.html")
    if not os.path.exists(dashboard_file):
        with open(dashboard_file, "w", encoding="utf-8") as f:
            f.write(r"""<h1>📊 Bosh Ekran (Dashboard)</h1>
<div class="karta" style="display:grid;grid-template-columns:repeat(auto-fit, minmax(200px, 1fr));gap:15px;background:linear-gradient(135deg, #1e293b, #0f172a);color:#fff">
  <div style="padding:10px">
    <div style="font-size:12px;color:#94a3b8">BUGUNGI KIRIM</div>
    <div id="stat-kirim" style="font-size:24px;font-weight:700;color:#4ade80">0 so'm</div>
  </div>
  <div style="padding:10px">
    <div style="font-size:12px;color:#94a3b8">BUGUNGI CHIQIM</div>
    <div id="stat-chiqim" style="font-size:24px;font-weight:700;color:#f87171">0 so'm</div>
  </div>
  <div style="padding:10px">
    <div style="font-size:12px;color:#94a3b8">SOF FOYDA (BUGUN)</div>
    <div id="stat-foyda" style="font-size:24px;font-weight:700;color:#38bdf8">0 so'm</div>
  </div>
</div>

<div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-bottom:15px">
  <div class="karta">
    <h3>⚡ Quick Kirim / Chiqim</h3>
    <form id="amalForm" onsubmit="qo_shAmal(event)" style="display:flex;flex-direction:column;gap:10px">
      <select id="tur" style="width:100%">
        <option value="kirim">🟢 Kirim</option>
        <option value="chiqim">🔴 Chiqim</option>
      </select>
      <input type="number" id="summa" placeholder="Summa (so'm)" required style="width:100%">
      <input type="text" id="kategoriya" placeholder="Kategoriya (masalan: Savdo, Xarajat)" style="width:100%">
      <input type="text" id="izoh" placeholder="Izoh..." style="width:100%">
      <button type="submit">+ Saqlash</button>
    </form>
  </div>

  <div class="karta">
    <h3>🧮 Tezkor Kalkulyator</h3>
    <input type="text" id="calcInput" placeholder="Masalan: 125000 * 3 + 45000" style="width:100%;font-size:18px;margin-bottom:10px" onkeyup="if(event.key==='Enter')hisoblaCalc()">
    <div style="display:flex;gap:10px">
      <button onclick="hisoblaCalc()" style="flex:1">Hisoblash</button>
      <button onclick="document.getElementById('calcInput').value=''" style="background:#64748b">C</button>
    </div>
    <div id="calcRes" style="margin-top:12px;font-size:22px;font-weight:bold;color:#1a73e8">Natija: 0</div>
  </div>
</div>

<div class="karta">
  <h3>📋 So'nggi Amallar</h3>
  <table>
    <thead>
      <tr><th>Sana</th><th>Tur</th><th>Kategoriya</th><th>Summa</th><th>Izoh</th></tr>
    </thead>
    <tbody id="amalJadval"></tbody>
  </table>
</div>

<script>
async function yukla(){
  const amallar = await sql("SELECT * FROM amal ORDER BY id DESC LIMIT 20");
  let k=0, ch=0;
  const todayStr = bugun();
  let html = '';
  for(let a of amallar){
    if(a.sana.startsWith(todayStr)){
      if(a.tur === 'kirim') k += a.summa; else ch += a.summa;
    }
    const color = a.tur === 'kirim' ? '#16a34a' : '#dc2626';
    const sign = a.tur === 'kirim' ? '+' : '-';
    html += `<tr>
      <td>${a.sana}</td>
      <td><b style="color:${color}">${a.tur.toUpperCase()}</b></td>
      <td>${a.kategoriya || '-'}</td>
      <td><b style="color:${color}">${sign} ${pul(a.summa)} so'm</b></td>
      <td>${a.izoh || ''}</td>
    </tr>`;
  }
  document.getElementById('stat-kirim').innerText = pul(k) + " so'm";
  document.getElementById('stat-chiqim').innerText = pul(ch) + " so'm";
  document.getElementById('stat-foyda').innerText = pul(k - ch) + " so'm";
  document.getElementById('amalJadval').innerHTML = html || '<tr><td colspan="5">Ma\'lumot yo\'q</td></tr>';
}

async function qo_shAmal(e){
  e.preventDefault();
  const t = document.getElementById('tur').value;
  const s = parseFloat(document.getElementById('summa').value);
  const k = document.getElementById('kategoriya').value;
  const i = document.getElementById('izoh').value;
  const now = bugun() + ' ' + new Date().toTimeString().split(' ')[0].substring(0,5);
  await exec("INSERT INTO amal(sana,tur,summa,kategoriya,izoh) VALUES(?,?,?,?,?)", [now, t, s, k, i]);
  document.getElementById('summa').value = '';
  document.getElementById('izoh').value = '';
  yukla();
}

function hisoblaCalc(){
  try{
    const val = document.getElementById('calcInput').value.replace(/[^0-9+\-*\/().\s]/g, '');
    const res = eval(val);
    document.getElementById('calcRes').innerText = "Natija: " + pul(res);
  }catch(e){
    document.getElementById('calcRes').innerText = "Xato formula";
  }
}

yukla();
</script>
""")

    tilla_file = os.path.join(PAGES, "02_tilla_585_pereshot.html")
    if not os.path.exists(tilla_file):
        with open(tilla_file, "w", encoding="utf-8") as f:
            f.write("""<h1>⚖️ Tilla Pereshot & Hisob-kitobi (585 / 750 / 999 Proba)</h1>
<div class="karta" style="background:#fef3c7;border-color:#fde68a;color:#78350f">
  💡 <b>Tilla pereshot formulasi:</b> Toza tilla (999 proba) = Og'irlik × (Proba / 1000). <br>
  Masalan: 10 gramm 585 proba tilla = 10 × 0.585 = 5.85 gramm toza (999) tilla bo'ladi.
</div>

<div class="karta">
  <h3>⚡ Yangi Tilla Buyum Pereshot Qilish va Saqlash</h3>
  <form id="tillaForm" onsubmit="saqlaTilla(event)" style="display:grid;grid-template-columns:repeat(auto-fit, minmax(180px, 1fr));gap:12px">
    <div>
      <label style="font-size:12px;font-weight:bold;color:#4b5563">Buyum nomi:</label>
      <input type="text" id="buyum_nomi" placeholder="Zanjir, Uzuk..." required style="width:100%">
    </div>
    <div>
      <label style="font-size:12px;font-weight:bold;color:#4b5563">Og'irligi (gramm):</label>
      <input type="number" step="0.01" id="ogirligi_g" placeholder="10.5" required oninput="hisoblaPereshot()" style="width:100%">
    </div>
    <div>
      <label style="font-size:12px;font-weight:bold;color:#4b5563">Proba:</label>
      <select id="proba" onchange="hisoblaPereshot()" style="width:100%">
        <option value="585">585 Proba (58.5%)</option>
        <option value="750">750 Proba (75.0%)</option>
        <option value="999">999 Proba (Toza 100%)</option>
        <option value="375">375 Proba (37.5%)</option>
        <option value="583">583 Proba (58.3%)</option>
      </select>
    </div>
    <div>
      <label style="font-size:12px;font-weight:bold;color:#4b5563">Gramm narxi (USD $):</label>
      <input type="number" step="0.1" id="gramm_narxi_usd" value="65.0" oninput="hisoblaPereshot()" style="width:100%">
    </div>
    <div>
      <label style="font-size:12px;font-weight:bold;color:#4b5563">Toza tilla (999g):</label>
      <input type="text" id="toza_tilla_g" readonly style="background:#f1f5f9;font-weight:bold;color:#b45309;width:100%">
    </div>
    <div>
      <label style="font-size:12px;font-weight:bold;color:#4b5563">Jami Qiymati ($):</label>
      <input type="text" id="jami_summa_usd" readonly style="background:#f1f5f9;font-weight:bold;color:#15803d;width:100%">
    </div>
    <div style="grid-column:1 / -1">
      <input type="text" id="tilla_izoh" placeholder="Izoh..." style="width:100%">
    </div>
    <div style="grid-column:1 / -1">
      <button type="submit" style="width:100%;background:#d97706;padding:12px;font-size:16px">+ Bazaga Saqlash</button>
    </div>
  </form>
</div>

<div class="karta">
  <h3>🏆 Saqlangan Tilla Pereshotlar Bazasi</h3>
  <table>
    <thead>
      <tr><th>Sana</th><th>Buyum</th><th>Og'irlik</th><th>Proba</th><th>Toza Tilla (999)</th><th>$ / Gram</th><th>Jami $</th><th>Izoh</th><th>O'chirish</th></tr>
    </thead>
    <tbody id="tillaJadval"></tbody>
  </table>
</div>

<script>
function hisoblaPereshot(){
  const g = parseFloat(document.getElementById('ogirligi_g').value) || 0;
  const p = parseInt(document.getElementById('proba').value) || 585;
  const px = parseFloat(document.getElementById('gramm_narxi_usd').value) || 0;

  const toza = g * (p / 1000.0);
  const jami = toza * px;

  document.getElementById('toza_tilla_g').value = toza.toFixed(3) + " g";
  document.getElementById('jami_summa_usd').value = "$ " + pul(jami);
}

async function yuklaTilla(){
  const rows = await sql("SELECT * FROM tilla_hisob ORDER BY id DESC");
  let html = '';
  let jamiOg = 0, jamiToza = 0, jamiUsd = 0;

  for(let r of rows){
    jamiOg += r.ogirligi_g;
    jamiToza += r.toza_tilla_g;
    jamiUsd += (r.jami_summa_usd || 0);
    html += `<tr>
      <td>${r.sana}</td>
      <td><b>${r.buyum_nomi}</b></td>
      <td>${r.ogirligi_g} g</td>
      <td><span style="background:#fef3c7;color:#92400e;padding:2px 8px;border-radius:6px;font-weight:bold">${r.proba}</span></td>
      <td><b style="color:#b45309">${r.toza_tilla_g.toFixed(3)} g</b></td>
      <td>$ ${r.gramm_narxi_usd || 0}</td>
      <td><b style="color:#15803d">$ ${pul(r.jami_summa_usd || 0)}</b></td>
      <td>${r.izoh || ''}</td>
      <td><button onclick="ochirTilla(${r.id})" style="background:#ef4444;padding:4px 8px;font-size:12px">❌</button></td>
    </tr>`;
  }

  html += `<tr style="background:#f8fafc;font-weight:bold">
    <td colspan="2">JAMI:</td>
    <td>${jamiOg.toFixed(2)} g</td>
    <td>-</td>
    <td><b style="color:#b45309">${jamiToza.toFixed(3)} g</b></td>
    <td>-</td>
    <td><b style="color:#15803d">$ ${pul(jamiUsd)}</b></td>
    <td colspan="2"></td>
  </tr>`;

  document.getElementById('tillaJadval').innerHTML = html;
}

async function saqlaTilla(e){
  e.preventDefault();
  const nom = document.getElementById('buyum_nomi').value;
  const og = parseFloat(document.getElementById('ogirligi_g').value) || 0;
  const pr = parseInt(document.getElementById('proba').value) || 585;
  const px = parseFloat(document.getElementById('gramm_narxi_usd').value) || 0;
  const toza = og * (pr / 1000.0);
  const jami = toza * px;
  const iz = document.getElementById('tilla_izoh').value;
  const s = bugun();

  await exec("INSERT INTO tilla_hisob(sana,buyum_nomi,ogirligi_g,proba,toza_tilla_g,gramm_narxi_usd,jami_summa_usd,izoh) VALUES(?,?,?,?,?,?,?,?)",
    [s, nom, og, pr, toza, px, jami, iz]);

  document.getElementById('buyum_nomi').value = '';
  document.getElementById('ogirligi_g').value = '';
  document.getElementById('tilla_izoh').value = '';
  yuklaTilla();
}

async function ochirTilla(id){
  if(confirm("Ushbu tilla yozuvini o'chirmoqchimisiz?")){
    await exec("DELETE FROM tilla_hisob WHERE id=?", [id]);
    yuklaTilla();
  }
}

yuklaTilla();
</script>
""")

    backup_file = os.path.join(PAGES, "03_zaxira_va_sozlama.html")
    if not os.path.exists(backup_file):
        with open(backup_file, "w", encoding="utf-8") as f:
            f.write("""<h1>💾 Zaxira Olish, Tiklash va Sozlamalar</h1>
<div class="karta">
  <h3>📦 Baza va Dastur Zaxirasi (Backup)</h3>
  <p>Hisob-kitoblaringiz va sahifalaringizni zaxira fayl (ZIP/JSON) ko'rinishida saqlang yoki qayta yuklang.</p>
  <div style="display:flex;gap:12px;flex-wrap:wrap;margin-top:15px">
    <button onclick="olZaxira()" style="background:#16a34a;padding:12px 20px;font-size:15px">📥 Zaxira Faylini Yuklab Olish (.zip)</button>
  </div>
</div>

<div class="karta">
  <h3>🔄 Zaxiradan Qayta Tiklash (Restore)</h3>
  <p>Avval olingan `.zip` yoki `.json` zaxira faylini tanlab bazani tiklang:</p>
  <form id="restoreForm" onsubmit="tiklaZaxira(event)" style="display:flex;gap:10px;align-items:center">
    <input type="file" id="backupFile" accept=".zip,.json" required style="flex:1">
    <button type="submit" style="background:#d97706;padding:10px 18px">♻️ Bazaga Tiklash</button>
  </form>
  <div id="restoreMsg" style="margin-top:10px;font-weight:bold"></div>
</div>

<div class="karta">
  <h3>🎓 Antigravity AI O'rgatilgan Qoidalar (Yo'riqnomalar)</h3>
  <p>Foydalanuvchi bir marta o'rgatgan va AI agent eslab qolgan qoidalar:</p>
  <div style="display:flex;gap:8px;margin-bottom:12px">
    <input type="text" id="newYoriq" placeholder="Yangi qoida yoki yo'riqnoma matni..." style="flex:1">
    <button onclick="qoshYoriq()">+ Qo'shish</button>
  </div>
  <div id="yoriqList"></div>
</div>

<script>
async function olZaxira(){
  const res = await fetch('/api/zaxira/olish', {method: 'POST'});
  const d = await res.json();
  if(d.ok && d.url){
    window.location.href = d.url;
  } else {
    alert("Zaxira olishda xato: " + (d.xato || 'Noma\'lum'));
  }
}

async function tiklaZaxira(e){
  e.preventDefault();
  const fileInput = document.getElementById('backupFile');
  if(!fileInput.files.length) return;
  const file = fileInput.files[0];
  const formData = new FormData();
  formData.append('file', file);

  document.getElementById('restoreMsg').innerText = "Yuklanmoqda...";
  try {
    const res = await fetch('/api/zaxira/tiklash', {
      method: 'POST',
      body: formData
    });
    const d = await res.json();
    if(d.ok){
      document.getElementById('restoreMsg').innerText = "✅ " + d.msg;
      setTimeout(()=> location.reload(), 1500);
    } else {
      document.getElementById('restoreMsg').innerText = "❌ Xato: " + d.xato;
    }
  } catch(err){
    document.getElementById('restoreMsg').innerText = "❌ Xato: " + err.message;
  }
}

async function yuklaYoriq(){
  const res = await fetch('/api/yoriqnoma');
  const list = await res.json();
  let html = '';
  if(!list.length){
    html = '<div style="color:#94a3b8">Hali hech qanday maxsus yo\'riqnoma o\'rgatilmadi.</div>';
  } else {
    list.forEach(y => {
      html += `<div style="display:flex;justify-content:space-between;align-items:center;padding:8px 12px;background:#f8fafc;border-radius:8px;margin-bottom:6px">
        <div>📌 <b>${y.matn}</b> <small style="color:#94a3b8">(${y.sana})</small></div>
        <button onclick="ochirYoriq(${y.id})" style="background:#ef4444;padding:3px 8px;font-size:12px">❌</button>
      </div>`;
    });
  }
  document.getElementById('yoriqList').innerHTML = html;
}

async function qoshYoriq(){
  const txt = document.getElementById('newYoriq').value.trim();
  if(!txt) return;
  await fetch('/api/yoriqnoma', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({matn: txt})
  });
  document.getElementById('newYoriq').value = '';
  yuklaYoriq();
}

async function ochirYoriq(id){
  if(confirm("Ushbu yo'riqnomani o'chirmoqchimisiz?")){
    await fetch('/api/yoriqnoma?id=' + id, {method: 'DELETE'});
    yuklaYoriq();
  }
}

yuklaYoriq();
</script>
""")


# ═══════════════════════════ AGENT (job) ════════════════════════════
JOBS, JOBS_LOCK, _N = {}, threading.Lock(), 0


def preamble():
    """Agentga har safar beriladigan kontekst — u nima qila olishini aniq bilsin."""
    with db() as c:
        ys = [r["matn"] for r in c.execute("SELECT matn FROM yoriqnoma ORDER BY id").fetchall()]
    biz = sozlama("biznes") or "(hali kiritilmagan)"
    tbl = "\n".join(f"  - {t['nom']}({', '.join(t['ustunlar'])}) — {t['soni']} qator"
                    for t in jadvallar())
    pgs = ", ".join(sorted(os.path.splitext(f)[0] for f in os.listdir(PAGES)
                           if f.endswith(".html"))) or "(yo'q)"
    rules = ("\nFoydalanuvchi o'rgatgan doimiy qoidalar:\n" +
             "\n".join(f"  {i+1}. {y}" for i, y in enumerate(ys))) if ys else ""
    return f"""Sen MUHASIB HISOB dasturining ichki yordamchisisan. Faqat shu hisob-kitob
tizimi ustida ishlaysan. Boshqa mavzu so'ralsa — hisobga aloqasi yo'qligini ayt.

Biznes turi: {biz}
SQLite baza: {DB}
Mavjud jadvallar:
{tbl or "  (yo'q)"}
Mavjud sahifalar: {pgs}{rules}

QANDAY ISHLAYSAN:
1. Ma'lumot saqlash kerak bo'lsa — `sqlite3 {DB} "CREATE TABLE ..."` bilan jadval yarat.
   Mavjud jadvalni o'chirma, faqat qo'sh. Ustun qo'shish: ALTER TABLE ... ADD COLUMN.
2. Yangi sahifa/imkoniyat so'ralsa — {PAGES}/<nom>.html fayl yoz.
   Fayl nomi menyuda ko'rinadi (masalan tilla_585.html → "tilla 585").
   Sahifa ichida `<h1>` birinchi qatorda sarlavha bo'lsin.
3. Bosh ekrandagi doim ko'rinib turadigan karta so'ralsa — {WIDGETS}/<nom>.html yoz.
4. Sahifa ma'lumotni shu funksiyalar orqali oladi (avtomatik ulanadi, import kerak emas):
      await sql("SELECT * FROM amal WHERE sana LIKE ?", [bugun()+'%'])   // o'qish, massiv qaytadi
      await exec("INSERT INTO amal(sana,tur,summa) VALUES(?,?,?)", [s,t,x])  // yozish
      pul(12345)            // "12 345" ko'rinishida formatlash
      bugun()               // "2026-08-01"
   Sahifada oddiy HTML+CSS+JS yoz. Tashqi kutubxona (CDN) ULAMA — internet yo'q deb hisobla.
5. Uslub: oq karta, yumaloq burchak (16px), ko'k urg'u #1a73e8, shrift system-ui.
   Sahifa `<style>` ichida o'z uslubini yozsin.

QOIDALAR:
- Bloklovchi buyruq ishlatma (server ochma, `python3 -m http.server` va h.k.).
- Ishni oxirigacha bajar: jadval + sahifa + sinov ma'lumot bilan tekshir.
- Javobni qisqa yoz: nima qildim, qayerda ko'rish mumkin.
- O'zbek tilida javob ber.
"""


def _tool_label(name, p):
    p = p or {}
    g = lambda *k: next((str(p[x]) for x in k if p.get(x)), "")
    if name == "run_command":
        cmd = g("CommandLine")[:120]
        if "sqlite3" in cmd:
            return "🗄  baza: " + cmd[:100]
        return "$ " + cmd
    if name == "write_to_file":
        t = g("TargetFile", "FilePath", "Path")
        return ("📄  sahifa: " + os.path.basename(t)) if PAGES in t else ("✍️  " + os.path.basename(t))
    if name in ("replace_file_content", "multi_replace_file_content"):
        return "✏️  " + os.path.basename(g("TargetFile", "FilePath", "Path"))
    if name in ("view_file", "read_url_content"):
        return "📖  " + os.path.basename(g("AbsolutePath", "TargetFile", "Path"))
    if name == "list_dir":
        return "📂  " + os.path.basename(g("DirectoryPath", "Path"))
    if name in ("find_by_name", "grep_search"):
        return "🔎  " + g("Query", "Pattern")
    return "🔧  " + name


def stream_agent(prompt, job):
    args = [AGY, "-p", preamble() + "\n\nFOYDALANUVCHI SO'ROVI:\n" + prompt,
            "--output-format", "stream-json", "--dangerously-skip-permissions",
            "--print-timeout", PRINT_TIMEOUT, "--add-dir", DATA, "--add-dir", ROOT]
    yield {"action": "🗄  baza: " + os.path.basename(DB)}
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, bufsize=1, cwd=DATA, start_new_session=True)
    job["proc"] = p
    q = queue.Queue()

    def pump():
        try:
            for ln in p.stdout:
                q.put(ln)
        except Exception:
            pass
        finally:
            q.put(None)

    threading.Thread(target=pump, daemon=True).start()
    out, err = "", ""
    while True:
        try:
            line = q.get(timeout=2.0)
        except queue.Empty:
            yield {"ping": True}
            continue
        if line is None:
            break
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except Exception:
            continue
        if ev.get("event") == "step_update":
            su = ev.get("step_update", {})
            if su.get("step_type") == "tool" and su.get("state") == "ACTIVE":
                yield {"action": _tool_label(su.get("tool_name", ""),
                                             (su.get("tool_info") or {}).get("parameters"))}
        elif ev.get("event") == "result":
            res = ev.get("result", {})
            err, out = res.get("error") or "", res.get("response") or ""
    p.wait()
    yield {"done": True, "error": err} if err else {"done": True, "text": out.strip() or "(bo'sh)"}


def start_job(prompt):
    global _N
    with JOBS_LOCK:
        _N += 1
        jid = "h%d_%d" % (int(time.time()), _N)
        job = {"id": jid, "prompt": prompt, "started": time.time(), "state": "running",
               "events": [], "cv": threading.Condition()}
        JOBS[jid] = job
        for k in [k for k, j in JOBS.items()
                  if j["state"] != "running" and time.time() - j.get("ended", 0) > 3600]:
            JOBS.pop(k, None)

    def work():
        try:
            for ev in stream_agent(prompt, job):
                if ev.get("ping"):
                    continue
                if ev.get("done") and job.get("stopping"):
                    ev = {"done": True, "text": "⏹ To'xtatildi."}
                with job["cv"]:
                    job["events"].append(ev)
                    job["cv"].notify_all()
        except Exception as e:
            with job["cv"]:
                job["events"].append({"done": True, "error": str(e)})
                job["cv"].notify_all()
        finally:
            with job["cv"]:
                if not any(e.get("done") for e in job["events"]):
                    job["events"].append({"done": True, "text": "⏹ To'xtatildi."})
                job["state"] = "stopped" if job.get("stopping") else "done"
                job["ended"] = time.time()
                job["cv"].notify_all()

    threading.Thread(target=work, daemon=True).start()
    return job


def stop_job(jid):
    with JOBS_LOCK:
        job = JOBS.get(jid)
    if not job or job["state"] != "running":
        return False
    job["stopping"] = True
    p = job.get("proc")
    if p and p.poll() is None:
        try:
            os.killpg(os.getpgid(p.pid), signal.SIGTERM)
        except Exception:
            try:
                p.terminate()
            except Exception:
                pass
    with job["cv"]:
        job["cv"].notify_all()
    return True


def follow_job(job, start=0):
    idx = max(0, int(start or 0))
    yield {"job": job["id"], "started": job["started"], "state": job["state"]}
    while True:
        with job["cv"]:
            if idx >= len(job["events"]):
                if job["state"] != "running":
                    break
                job["cv"].wait(timeout=2.0)
            evs = job["events"][idx:]
            idx += len(evs)
            running = job["state"] == "running"
        if evs:
            for ev in evs:
                yield ev
        elif running:
            yield {"ping": True}
        else:
            break


# ═══════════════════════════ SAHIFALAR ══════════════════════════════
PAGE_LIB = """<script>
async function sql(q, args){ const r = await fetch('/api/sql',{method:'POST',
  headers:{'Content-Type':'application/json'},body:JSON.stringify({sql:q,args:args||[]})});
  const d = await r.json(); if(d.xato) throw new Error(d.xato); return d.qatorlar; }
async function exec(q, args){ const r = await fetch('/api/exec',{method:'POST',
  headers:{'Content-Type':'application/json'},body:JSON.stringify({sql:q,args:args||[]})});
  const d = await r.json(); if(d.xato) throw new Error(d.xato); return d; }
function pul(n){ return (Math.round(Number(n)||0)).toLocaleString('ru-RU').replace(/,/g,' '); }
function bugun(){ const d=new Date(); return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0'); }
</script>
<style>
  :root{color-scheme:light}
  body{margin:0;padding:22px;font-family:system-ui,-apple-system,'Segoe UI',sans-serif;
       background:#f5f7fb;color:#1f2430}
  h1{font-size:22px;margin:0 0 16px;color:#0f172a}
  h3{margin-top:0;font-size:16px;color:#334155}
  .karta{background:#fff;border:1px solid #e4e9f2;border-radius:16px;padding:18px;margin-bottom:14px;
         box-shadow:0 2px 10px rgba(20,40,80,.04)}
  table{width:100%;border-collapse:collapse;font-size:14px}
  th,td{padding:10px 12px;text-align:left;border-bottom:1px solid #eef1f6}
  th{color:#6b7280;font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.4px;background:#f8fafc}
  button{background:#1a73e8;color:#fff;border:0;border-radius:10px;padding:9px 16px;
         font-size:14px;font-weight:600;cursor:pointer;font-family:inherit;transition:all 0.15s ease}
  button:hover{background:#1557b0;transform:translateY(-1px)}
  input,select,textarea{padding:9px 12px;border:1px solid #d8dfea;border-radius:10px;font-size:14px;
               font-family:inherit;background:#fff;box-sizing:border-box}
  input:focus,select:focus,textarea:focus{outline:none;border-color:#1a73e8;box-shadow:0 0 0 3px rgba(26,115,232,0.15)}
</style>
"""


def page_title(path):
    try:
        with open(path, encoding="utf-8") as f:
            head = f.read(4000)
        m = re.search(r"<h1[^>]*>(.*?)</h1>", head, re.S | re.I)
        if m:
            return re.sub(r"<[^>]+>", "", m.group(1)).strip()[:40]
    except Exception:
        pass
    return os.path.splitext(os.path.basename(path))[0].replace("_", " ")


def ro_yxat(folder):
    out = []
    if not os.path.exists(folder):
        return out
    for f in sorted(os.listdir(folder)):
        if f.endswith(".html"):
            out.append({"fayl": f, "nom": os.path.splitext(f)[0],
                        "sarlavha": page_title(os.path.join(folder, f))})
    return out


# ══════════════════════════ ZAXIRALASH (BACKUP) ═════════════════════
def yarat_zaxira():
    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    zname = f"hisob_zaxira_{now_str}.zip"
    zpath = os.path.join(BACKUPS, zname)

    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as zf:
        if os.path.exists(DB):
            zf.write(DB, arcname="hisob.db")
        for root, dirs, files in os.walk(DATA):
            if BACKUPS in root:
                continue
            for file in files:
                full_p = os.path.join(root, file)
                rel_p = os.path.relpath(full_p, DATA)
                if rel_p != "hisob.db":
                    zf.write(full_p, arcname=rel_p)

    return zname, f"/api/zaxira/download?f={urllib.parse.quote(zname)}"


def tikla_zaxira_data(file_bytes, filename=""):
    try:
        if filename.endswith(".json"):
            obj = json.loads(file_bytes.decode("utf-8"))
            if "jadvallar" in obj:
                with db() as c:
                    for tbl, rows in obj["jadvallar"].items():
                        if rows:
                            cols = list(rows[0].keys())
                            qmarks = ",".join(["?"] * len(cols))
                            col_str = ",".join(cols)
                            for r in rows:
                                vals = [r[k] for k in cols]
                                c.execute(f"INSERT OR REPLACE INTO {tbl} ({col_str}) VALUES ({qmarks})", vals)
                    c.commit()
                return True, "JSON ma'lumotlar bazaga muvaffaqiyatli tiklandi!"

        # Aks holda ZIP fayl deb ishlaymiz
        with zipfile.ZipFile(io.BytesIO(file_bytes), 'r') as zf:
            for item in zf.infolist():
                target_path = os.path.join(DATA, item.filename)
                if item.filename == "hisob.db":
                    # DB ni yopib almashtiramiz
                    db_bytes = zf.read(item.filename)
                    with open(DB, "wb") as fdb:
                        fdb.write(db_bytes)
                else:
                    zf.extract(item, DATA)
        return True, "Zaxira zip fayl muvaffaqiyatli tiklandi!"
    except Exception as e:
        return False, str(e)


# ════════════════════════ HTTP SERVER HANDLER ═══════════════════════
class Handler(BaseHTTPRequestHandler):

    def _json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, html_str, status=200):
        body = html_str.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        ln = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(ln) if ln > 0 else b""

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/":
            self._html(INDEX_HTML)
            return

        if path == "/api/sahifalar":
            res = {
                "biznes": sozlama("biznes"),
                "sahifalar": ro_yxat(PAGES),
                "vidjetlar": ro_yxat(WIDGETS),
                "jadvallar": jadvallar()
            }
            self._json(res)
            return

        if path == "/api/sahifa":
            fnom = (query.get("f") or [""])[0]
            if not fnom or ".." in fnom:
                self._json({"xato": "Noto'g'ri fayl"}, 400)
                return
            full_p = os.path.join(PAGES, fnom)
            if not os.path.exists(full_p):
                full_p = os.path.join(WIDGETS, fnom)
            if not os.path.exists(full_p):
                self._html("<h2>Sahifa topilmadi</h2>", 404)
                return
            with open(full_p, encoding="utf-8") as f:
                cnt = f.read()
            self._html(PAGE_LIB + "\n" + cnt)
            return

        if path == "/api/stream":
            jid = (query.get("jid") or [""])[0]
            with JOBS_LOCK:
                job = JOBS.get(jid)
            if not job:
                self.send_error(404, "Job topilmadi")
                return

            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()

            st = (query.get("start") or ["0"])[0]
            for ev in follow_job(job, start=int(st)):
                msg = f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
                try:
                    self.wfile.write(msg.encode("utf-8"))
                    self.wfile.flush()
                except Exception:
                    break
            return

        if path == "/api/yoriqnoma":
            with db() as c:
                rows = c.execute("SELECT * FROM yoriqnoma ORDER BY id DESC").fetchall()
                out = [dict(r) for r in rows]
            self._json(out)
            return

        if path == "/api/zaxira/download":
            fnom = (query.get("f") or [""])[0]
            if not fnom or ".." in fnom:
                self.send_error(400)
                return
            fpath = os.path.join(BACKUPS, fnom)
            if not os.path.exists(fpath):
                self.send_error(404)
                return
            with open(fpath, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", f'attachment; filename="{fnom}"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        self._html("<h2>Not Found</h2>", 404)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path

        if path == "/api/sql":
            try:
                body = json.loads(self._read_body().decode("utf-8"))
                sql_q = body.get("sql", "")
                args = body.get("args", [])
                with db() as c:
                    rows = c.execute(sql_q, args).fetchall()
                    out = [dict(r) for r in rows]
                self._json({"qatorlar": out})
            except Exception as e:
                self._json({"xato": str(e)}, 400)
            return

        if path == "/api/exec":
            try:
                body = json.loads(self._read_body().decode("utf-8"))
                sql_q = body.get("sql", "")
                args = body.get("args", [])
                with db() as c:
                    cur = c.execute(sql_q, args)
                    c.commit()
                    rowid = cur.lastrowid
                    count = cur.rowcount
                self._json({"ok": True, "rowid": rowid, "ta_tasirladi": count})
            except Exception as e:
                self._json({"xato": str(e)}, 400)
            return

        if path == "/api/prompt":
            try:
                body = json.loads(self._read_body().decode("utf-8"))
                prompt = body.get("prompt", "").strip()
                if not prompt:
                    self._json({"xato": "Prompt bo'sh"}, 400)
                    return
                job = start_job(prompt)
                self._json({"ok": True, "jid": job["id"]})
            except Exception as e:
                self._json({"xato": str(e)}, 500)
            return

        if path == "/api/stop":
            try:
                body = json.loads(self._read_body().decode("utf-8"))
                jid = body.get("jid", "")
                ok = stop_job(jid)
                self._json({"ok": ok})
            except Exception as e:
                self._json({"xato": str(e)}, 500)
            return

        if path == "/api/yoriqnoma":
            try:
                body = json.loads(self._read_body().decode("utf-8"))
                matn = body.get("matn", "").strip()
                if matn:
                    now = datetime.now().strftime("%Y-%m-%d %H:%M")
                    with db() as c:
                        c.execute("INSERT INTO yoriqnoma (matn, sana) VALUES (?, ?)", (matn, now))
                        c.commit()
                self._json({"ok": True})
            except Exception as e:
                self._json({"xato": str(e)}, 400)
            return

        if path == "/api/sozlama":
            try:
                body = json.loads(self._read_body().decode("utf-8"))
                biz = body.get("biznes", "").strip()
                if biz:
                    sozlama("biznes", biz)
                self._json({"ok": True})
            except Exception as e:
                self._json({"xato": str(e)}, 400)
            return

        if path == "/api/zaxira/olish":
            try:
                zname, zurl = yarat_zaxira()
                self._json({"ok": True, "fayl": zname, "url": zurl})
            except Exception as e:
                self._json({"xato": str(e)}, 500)
            return

        if path == "/api/zaxira/tiklash":
            try:
                ct = self.headers.get("Content-Type", "")
                raw_body = self._read_body()
                filename = ""
                file_bytes = b""

                if "multipart/form-data" in ct:
                    boundary = ct.split("boundary=")[-1].encode("utf-8")
                    parts = raw_body.split(b"--" + boundary)
                    for part in parts:
                        if b'filename="' in part:
                            header_part, content_part = part.split(b"\r\n\r\n", 1)
                            content_part = content_part.rsplit(b"\r\n", 1)[0]
                            m = re.search(rb'filename="([^"]+)"', header_part)
                            if m:
                                filename = m.group(1).decode("utf-8", errors="ignore")
                            file_bytes = content_part
                            break
                else:
                    file_bytes = raw_body

                ok, msg = tikla_zaxira_data(file_bytes, filename)
                if ok:
                    self._json({"ok": True, "msg": msg})
                else:
                    self._json({"xato": msg}, 400)
            except Exception as e:
                self._json({"xato": str(e)}, 500)
            return

        self._json({"xato": "Not Found"}, 404)

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/api/yoriqnoma":
            yid = (query.get("id") or [""])[0]
            if yid:
                with db() as c:
                    c.execute("DELETE FROM yoriqnoma WHERE id=?", (yid,))
                    c.commit()
            self._json({"ok": True})
            return

        self._json({"xato": "Not Found"}, 404)


# ════════════════════════ MAIN INDEX HTML (FRONTEND) ════════════════
INDEX_HTML = r"""<!DOCTYPE html>
<html lang="uz">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>MUHASIB HISOB — Antigravity Intelligent POS</title>
  <style>
    :root {
      --bg: #0f172a;
      --panel: #1e293b;
      --card: #334155;
      --text: #f8fafc;
      --muted: #94a3b8;
      --accent: #38bdf8;
      --accent-hover: #0284c7;
      --border: #334155;
      --sidebar-w: 270px;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    body { background: var(--bg); color: var(--text); height: 100vh; display: flex; overflow: hidden; }

    /* SIDEBAR */
    #sidebar {
      width: var(--sidebar-w);
      background: var(--panel);
      border-right: 1px solid var(--border);
      display: flex;
      flex-direction: column;
      flex-shrink: 0;
      z-index: 10;
    }
    .brand {
      padding: 18px 20px;
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .brand-logo {
      width: 38px; height: 38px;
      background: linear-gradient(135deg, #38bdf8, #818cf8);
      border-radius: 10px;
      display: flex; align-items: center; justify-content: center;
      font-size: 20px; font-weight: bold; color: #fff;
      box-shadow: 0 4px 12px rgba(56, 189, 248, 0.3);
    }
    .brand-info h2 { font-size: 15px; font-weight: 700; color: #fff; letter-spacing: 0.5px; }
    .brand-info small { font-size: 11px; color: var(--accent); font-weight: 600; }

    .nav-section { padding: 14px 12px 6px; font-size: 11px; text-transform: uppercase; color: var(--muted); letter-spacing: 0.8px; font-weight: 700; }
    .nav-menu { flex: 1; overflow-y: auto; padding: 0 10px 15px; }
    .nav-item {
      display: flex; align-items: center; gap: 10px;
      padding: 10px 14px; border-radius: 10px;
      color: #cbd5e1; text-decoration: none; font-size: 13.5px; font-weight: 500;
      margin-bottom: 4px; cursor: pointer; transition: all 0.15s ease;
    }
    .nav-item:hover { background: rgba(255,255,255,0.06); color: #fff; }
    .nav-item.active { background: var(--accent); color: #0f172a; font-weight: 700; }
    .nav-item .icon { font-size: 16px; }

    .sidebar-footer {
      padding: 14px 16px; border-top: 1px solid var(--border);
      background: rgba(0,0,0,0.15);
    }
    .agent-btn {
      width: 100%; padding: 10px;
      background: linear-gradient(135deg, #0284c7, #4f46e5);
      color: #fff; border: 0; border-radius: 10px;
      font-weight: 600; font-size: 13px; cursor: pointer;
      display: flex; align-items: center; justify-content: center; gap: 8px;
      box-shadow: 0 4px 12px rgba(2, 132, 199, 0.3);
      transition: all 0.2s ease;
    }
    .agent-btn:hover { transform: translateY(-1px); filter: brightness(1.1); }

    /* MAIN CONTENT */
    #main {
      flex: 1; display: flex; flex-direction: column; height: 100vh; overflow: hidden; background: #f5f7fb;
    }

    #header {
      height: 60px; background: #fff; border-bottom: 1px solid #e2e8f0;
      display: flex; align-items: center; justify-content: space-between;
      padding: 0 24px; color: #1e293b; flex-shrink: 0;
      box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    .header-title { font-size: 17px; font-weight: 700; color: #0f172a; display: flex; align-items: center; gap: 8px; }
    .header-stats { display: flex; gap: 18px; align-items: center; font-size: 13px; }
    .stat-badge {
      background: #f1f5f9; padding: 6px 12px; border-radius: 8px; border: 1px solid #e2e8f0;
      display: flex; align-items: center; gap: 6px; font-weight: 600; color: #334155;
    }

    #frame-container { flex: 1; position: relative; width: 100%; height: calc(100vh - 60px); }
    iframe { width: 100%; height: 100%; border: 0; background: #f5f7fb; }

    /* FLOATING AI CHAT DRAWER */
    #chat-drawer {
      position: fixed; right: 20px; bottom: 20px; width: 440px; height: 580px;
      background: #ffffff; color: #0f172a; border-radius: 20px;
      box-shadow: 0 20px 40px rgba(0,0,0,0.25), 0 0 0 1px rgba(0,0,0,0.08);
      display: flex; flex-direction: column; z-index: 100;
      transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
      transform: translateY(120%); opacity: 0; pointer-events: none;
    }
    #chat-drawer.open { transform: translateY(0); opacity: 1; pointer-events: all; }

    .chat-header {
      padding: 16px 20px; background: linear-gradient(135deg, #0f172a, #1e293b); color: #fff;
      border-top-left-radius: 20px; border-top-right-radius: 20px;
      display: flex; align-items: center; justify-content: space-between;
    }
    .chat-header h3 { font-size: 15px; font-weight: 700; display: flex; align-items: center; gap: 8px; margin: 0; color: #fff; }
    .chat-close { background: none; border: 0; color: #94a3b8; font-size: 20px; cursor: pointer; }
    .chat-close:hover { color: #fff; }

    .chat-body { flex: 1; padding: 16px; overflow-y: auto; display: flex; flex-direction: column; gap: 12px; background: #f8fafc; }
    .msg { max-width: 85%; padding: 12px 16px; border-radius: 14px; font-size: 13.5px; line-height: 1.45; word-wrap: break-word; }
    .msg.user { align-self: flex-end; background: #1a73e8; color: #fff; border-bottom-right-radius: 4px; }
    .msg.agent { align-self: flex-start; background: #fff; color: #1e293b; border: 1px solid #e2e8f0; border-bottom-left-radius: 4px; box-shadow: 0 2px 6px rgba(0,0,0,0.03); }
    .msg.agent .status-log { font-family: monospace; font-size: 12px; color: #0284c7; background: #e0f2fe; padding: 4px 8px; border-radius: 6px; margin-bottom: 6px; display: inline-block; }

    .chat-footer { padding: 14px; background: #fff; border-bottom-left-radius: 20px; border-bottom-right-radius: 20px; border-top: 1px solid #e2e8f0; display: flex; gap: 8px; }
    .chat-input { flex: 1; padding: 10px 14px; border: 1px solid #cbd5e1; border-radius: 12px; font-size: 13.5px; outline: none; }
    .chat-input:focus { border-color: #1a73e8; box-shadow: 0 0 0 3px rgba(26,115,232,0.15); }
    .send-btn { background: #1a73e8; color: #fff; border: 0; border-radius: 12px; padding: 0 16px; font-weight: 600; cursor: pointer; }
    .send-btn:hover { background: #1557b0; }

    /* QUICK CHAT TRIGGER BUTTON */
    #fab-chat {
      position: fixed; right: 24px; bottom: 24px;
      background: linear-gradient(135deg, #1a73e8, #4f46e5);
      color: #fff; padding: 14px 22px; border-radius: 50px;
      box-shadow: 0 10px 25px rgba(26, 115, 232, 0.4);
      display: flex; align-items: center; gap: 10px; font-weight: 600; font-size: 14px;
      cursor: pointer; z-index: 90; transition: all 0.2s ease; border: 0;
    }
    #fab-chat:hover { transform: scale(1.05); }

    /* LOADING SPINNER */
    .spinner {
      display: inline-block; width: 14px; height: 14px;
      border: 2px solid rgba(255,255,255,0.3); border-radius: 50%;
      border-top-color: #fff; animation: spin 0.8s linear infinite;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
  </style>
</head>
<body>

  <!-- SIDEBAR -->
  <div id="sidebar">
    <div class="brand">
      <div class="brand-logo">M</div>
      <div class="brand-info">
        <h2>MUHASIB HISOB</h2>
        <small id="biznesLabel">Tilla va Savdo POS</small>
      </div>
    </div>

    <div class="nav-section">Asosiy Menyular</div>
    <div class="nav-menu" id="menuList">
      <!-- Dinamik yuklanadi -->
    </div>

    <div class="sidebar-footer">
      <button class="agent-btn" onclick="toggleChat()">
        <span>✨ Antigravity Agent</span>
      </button>
    </div>
  </div>

  <!-- MAIN -->
  <div id="main">
    <div id="header">
      <div class="header-title" id="pageTitle">
        <span>📊 Bosh Ekran</span>
      </div>
      <div class="header-stats">
        <div class="stat-badge">📅 <span id="headerDate">--/--/----</span></div>
        <div class="stat-badge">⚡ Port: <b>8778</b></div>
        <button onclick="toggleChat()" style="background:#1a73e8;color:#fff;border:0;padding:7px 14px;border-radius:8px;font-weight:600;cursor:pointer">
          💬 Suhbat Oynasi
        </button>
      </div>
    </div>

    <div id="frame-container">
      <iframe id="pageFrame" src="/api/sahifa?f=01_dashboard.html"></iframe>
    </div>
  </div>

  <!-- FLOATING CHAT DRAWER -->
  <div id="chat-drawer">
    <div class="chat-header">
      <h3>✨ Antigravity AI Yordamchi</h3>
      <button class="chat-close" onclick="toggleChat()">✕</button>
    </div>
    <div class="chat-body" id="chatBody">
      <div class="msg agent">
        Assalomu alaykum! Men MUHASIB HISOB intellektual agentiman.<br><br>
        Men siz so'ragan har qanday hisob-kitob sahifasini, jadvalini yoki pereshot formasini SQLite bazasi bilan birga yaratib beraman.<br><br>
        <i>Masalan: "Menga bugungi tushumlarni ko'rsatadigan karta qo'shib ber" yoki "Tilla 585 ga pereshot sahifasini yozib ber".</i>
      </div>
    </div>
    <div class="chat-footer">
      <input type="text" id="promptInput" class="chat-input" placeholder="Nima hisob-kitob sahifasi yoki imkoniyat qo'shaylik?..." onkeyup="if(event.key==='Enter')yuborPrompt()">
      <button class="send-btn" id="sendBtn" onclick="yuborPrompt()">Yuborish</button>
    </div>
  </div>

  <!-- FAB BUTTON -->
  <button id="fab-chat" onclick="toggleChat()">
    <span>💬 Antigravity AI</span>
  </button>

  <script>
    document.getElementById('headerDate').innerText = new Date().toLocaleDateString('uz-UZ');

    let joriySahifa = '01_dashboard.html';

    async function yuklaMenyu() {
      try {
        const res = await fetch('/api/sahifalar');
        const data = await res.json();

        if (data.biznes) {
          document.getElementById('biznesLabel').innerText = data.biznes;
        }

        const menuEl = document.getElementById('menuList');
        let html = '';

        data.sahifalar.forEach(s => {
          const isActive = s.fayl === joriySahifa ? 'active' : '';
          let icon = '📄';
          if (s.fayl.includes('dashboard')) icon = '📊';
          else if (s.fayl.includes('tilla')) icon = '⚖️';
          else if (s.fayl.includes('zaxira')) icon = '💾';

          html += `<div class="nav-item ${isActive}" onclick="ochSahifa('${s.fayl}', '${s.sarlavha}')">
            <span class="icon">${icon}</span>
            <span>${s.sarlavha}</span>
          </div>`;
        });

        menuEl.innerHTML = html;
      } catch (e) {
        console.error("Menyu yuklashda xato:", e);
      }
    }

    function ochSahifa(fayl, sarlavha) {
      joriySahifa = fayl;
      document.getElementById('pageFrame').src = '/api/sahifa?f=' + encodeURIComponent(fayl);
      document.getElementById('pageTitle').innerHTML = `<span>${sarlavha}</span>`;
      yuklaMenyu();
    }

    function toggleChat() {
      const drawer = document.getElementById('chat-drawer');
      drawer.classList.toggle('open');
    }

    async function yuborPrompt() {
      const input = document.getElementById('promptInput');
      const text = input.value.trim();
      if (!text) return;

      input.value = '';
      const body = document.getElementById('chatBody');

      // User message
      const uMsg = document.createElement('div');
      uMsg.className = 'msg user';
      uMsg.innerText = text;
      body.appendChild(uMsg);

      // Agent placeholder
      const aMsg = document.createElement('div');
      aMsg.className = 'msg agent';
      aMsg.innerHTML = '<span class="status-log"><span class="spinner"></span> Ishlamoqda...</span><div class="agent-txt"></div>';
      body.appendChild(aMsg);
      body.scrollTop = body.scrollHeight;

      document.getElementById('sendBtn').disabled = true;

      try {
        const res = await fetch('/api/prompt', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({prompt: text})
        });
        const d = await res.json();
        if (!d.ok) throw new Error(d.xato || 'Xato yuz berdi');

        const es = new EventSource('/api/stream?jid=' + d.jid);
        const statusEl = aMsg.querySelector('.status-log');
        const txtEl = aMsg.querySelector('.agent-txt');

        es.onmessage = function(e) {
          const ev = JSON.parse(e.data);
          if (ev.action) {
            statusEl.innerHTML = '⚙️ ' + ev.action;
          }
          if (ev.done) {
            es.close();
            document.getElementById('sendBtn').disabled = false;
            if (ev.error) {
              statusEl.innerHTML = '❌ Xato';
              txtEl.innerText = ev.error;
            } else {
              statusEl.style.display = 'none';
              txtEl.innerText = ev.text || '✅ Topshiriq bajarildi!';
              // Refresh pages menu and current page frame
              yuklaMenyu();
              document.getElementById('pageFrame').contentWindow.location.reload();
            }
          }
          body.scrollTop = body.scrollHeight;
        };

        es.onerror = function() {
          es.close();
          document.getElementById('sendBtn').disabled = false;
          statusEl.style.display = 'none';
          txtEl.innerText = '✅ Topshiriq bajarildi va saqlandi!';
          yuklaMenyu();
          document.getElementById('pageFrame').contentWindow.location.reload();
        };

      } catch (err) {
        document.getElementById('sendBtn').disabled = false;
        aMsg.querySelector('.status-log').style.display = 'none';
        aMsg.querySelector('.agent-txt').innerText = '❌ Xato: ' + err.message;
      }
    }

    yuklaMenyu();
  </script>
</body>
</html>
"""


# ════════════════════════════ ISHGA TUSHIRISH ═══════════════════════
def main():
    init_db()
    ThreadingHTTPServer.allow_reuse_address = True
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"🚀 MUHASIB HISOB ishga tushdi: http://localhost:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n⏹ Server to'xtatildi.")
        server.server_close()


if __name__ == "__main__":
    main()
