/**
 * MUHASIB - Universal Business POS & Database Explorer
 * Core Application Engine & Data Management
 */

// Application Global State
let state = {
  currentProfile: 'retail', // 'retail', 'fashion', 'jewelry', 'cafe', 'service', 'pharmacy', 'wholesale'
  businessNames: {},
  currentTab: 'dashboard',
  currentExplorerSubTab: 'products',
  payMethod: 'cash',
  cart: [],
  
  // Configurable Stored Business Rules (including Gold 585 proba & USD exchange rate)
  rules: {
    ruleName: "Tillani 585 proba va valyutani USD 12,800 bo'yicha hisoblash",
    goldProba: 585,
    goldGramPriceUZS: 950000,
    usdExchangeRate: 12800,
    maxDiscountPercent: 15,
    customNotes: "Tillani har doim 585 proba ekvivalenti va dollar xaridlarini 1 USD = 12,800 UZS bo'yicha hisoblash, ombor qiymati va narxlarga tatbiq etish."
  },

  // Data Repositories
  products: [],
  purchases: [], // Omborga Kirimlar & Xaridlar
  sales: [],
  customers: [],
  expenses: [],
  debtsBorrowed: [] // Olingan qarzlar (Qarz oldim)
};

// Chart.js Instance
let salesChart = null;

// Initial Setup on DOM Load
document.addEventListener('DOMContentLoaded', () => {
  loadStateFromStorage();
  
  if (state.products.length === 0 || !state.purchases || state.purchases.length === 0) {
    seedInitialDemoData();
  }

  updateUIHeader();
  initRouteFromURL();
  populateCustomerDropdown();
  syncDebtsToMarkdown(false);
});

/* ==========================================================================
   State & Storage Handlers
   ========================================================================== */

function saveStateToStorage() {
  localStorage.setItem('muhasib_state_v3', JSON.stringify({
    currentProfile: state.currentProfile,
    businessNames: state.businessNames,
    products: state.products,
    purchases: state.purchases,
    sales: state.sales,
    customers: state.customers,
    expenses: state.expenses,
    rules: state.rules,
    debtsBorrowed: state.debtsBorrowed
  }));
}

function loadStateFromStorage() {
  const saved = localStorage.getItem('muhasib_state_v3');
  if (saved) {
    try {
      const parsed = JSON.parse(saved);
      state.currentProfile = parsed.currentProfile || 'retail';
      state.businessNames = parsed.businessNames || {};
      state.products = parsed.products || [];
      state.purchases = parsed.purchases || [];
      state.sales = parsed.sales || [];
      state.customers = parsed.customers || [];
      state.expenses = parsed.expenses || [];
      state.rules = parsed.rules || {
        ruleName: "Tillani 585 proba va valyutani USD 12,800 bo'yicha hisoblash",
        goldProba: 585,
        goldGramPriceUZS: 950000,
        usdExchangeRate: 12800,
        maxDiscountPercent: 15,
        customNotes: "Tillani har doim 585 proba ekvivalenti va dollar xaridlarini 1 USD = 12,800 UZS bo'yicha hisoblash, ombor qiymati va narxlarga tatbiq etish."
      };
      if (!state.rules.usdExchangeRate) state.rules.usdExchangeRate = 12800;
      state.debtsBorrowed = parsed.debtsBorrowed || [];
    } catch (e) {
      console.error('Storage load error:', e);
    }
  }
}

function isCurrentBusiness(record) {
  return true;
}

function currentBusinessName() {
  return 'POS Kassa';
}

function currentBusinessRecords(records) {
  return records || [];
}

/* ==========================================================================
   Demo Data Generator (Multi-Business Presets)
   ========================================================================== */

function seedInitialDemoData() {
  state.rules = {
    ruleName: "Tillani 585 proba va valyutani USD 12,800 bo'yicha hisoblash",
    goldProba: 585,
    goldGramPriceUZS: 950000,
    usdExchangeRate: 12800,
    maxDiscountPercent: 15,
    customNotes: "Tillani har doim 585 proba ekvivalenti va dollar xaridlarini 1 USD = 12,800 UZS bo'yicha hisoblash, ombor qiymati va narxlarga tatbiq etish."
  };

  state.products = [
    // Notebook Asus Purchase (User Requested Business Entry)
    { id: 'P-ASUS-NB', profile: 'retail', code: 'NB-ASUS-001', name: 'Notebook Asus', category: 'Elektronika & Kompyuterlar', costPrice: 12800000, price: 15360000, stock: 1, unit: 'dona', costUSD: 1000 },
    
    // Retail / Supermarket
    { id: 'P101', profile: 'retail', code: '47800012301', name: 'Coca-Cola 1.5L Classic', category: 'Ichimliklar', costPrice: 9500, price: 13000, stock: 45, unit: 'dona' },
    { id: 'P102', profile: 'retail', code: '47800012302', name: 'Nestlé Sut 1L 3.2%', category: 'Sut Mahsulotlari', costPrice: 11000, price: 15000, stock: 24, unit: 'dona' },
    { id: 'P103', profile: 'retail', code: '47800012303', name: 'Lays Chips Smak 140g', category: 'Sneklar', costPrice: 12000, price: 17000, stock: 3, unit: 'dona' },
    { id: 'P104', profile: 'retail', code: '47800012304', name: 'Buxoro Guruch Alanga 1kg', category: 'Don mahsulotlari', costPrice: 18000, price: 23000, stock: 120, unit: 'kg' },

    // Fashion / Kiyim
    { id: 'P201', profile: 'fashion', code: 'FASH-901', name: 'Klassik Erkaklar Pidjagi Black', category: 'Erkaklar kiyimi', costPrice: 350000, price: 550000, stock: 8, unit: 'dona' },
    { id: 'P202', profile: 'fashion', code: 'FASH-902', name: 'Jinsi Shim Levi\'s 501 (M/32)', category: 'Erkaklar kiyimi', costPrice: 220000, price: 380000, stock: 15, unit: 'dona' },
    { id: 'P203', profile: 'fashion', code: 'FASH-903', name: 'Nike Air Force 1 White Sneakers (42)', category: 'Poyabzal', costPrice: 400000, price: 650000, stock: 2, unit: 'juft' },

    // Jewelry / Zargarlik (585 proba rules)
    { id: 'P881', profile: 'jewelry', code: 'GLD-585-01', name: 'Tilla Uzuk Brilliantli (585 Proba)', category: 'Uzuklar', costPrice: 3200000, price: 4275000, stock: 5, unit: 'dona', grossWeight: 4.50, proba: 585, pureWeight: 2.6325 },
    { id: 'P882', profile: 'jewelry', code: 'GLD-585-02', name: 'Tilla Zanjir Italiya (585 Proba)', category: 'Zanjirlar', costPrice: 9100000, price: 12160000, stock: 3, unit: 'dona', grossWeight: 12.80, proba: 585, pureWeight: 7.488 },
    { id: 'P883', profile: 'jewelry', code: 'GLD-750-01', name: 'Tilla Zanjir Premium (750 Proba)', category: 'Zanjirlar', costPrice: 7500000, price: 9800000, stock: 2, unit: 'dona', grossWeight: 8.20, proba: 750, pureWeight: 6.15 },

    // Cafe / Restoran
    { id: 'P301', profile: 'cafe', code: 'FOOD-101', name: 'Mavsumiy Lavash Go\'shtli Big', category: 'Fast Food', costPrice: 21000, price: 32000, stock: 200, unit: 'porsiya' },
    { id: 'P302', profile: 'cafe', code: 'FOOD-102', name: 'Double Cheeseburger Supreme', category: 'Fast Food', costPrice: 24000, price: 38000, stock: 150, unit: 'dona' },
    { id: 'P303', profile: 'cafe', code: 'FOOD-103', name: 'Espresso Kapuchino Double 300ml', category: 'Issiq Ichimliklar', costPrice: 6000, price: 18000, stock: 500, unit: 'fincon' },

    // Service & Repair / Avtoservis
    { id: 'P401', profile: 'service', code: 'SRV-001', name: 'Motor Moyi Almashtirish (Shell 5W30)', category: 'Avto Xizmat', costPrice: 180000, price: 280000, stock: 30, unit: 'xizmat' },
    { id: 'P402', profile: 'service', code: 'SRV-002', name: 'Kompyuter Diagnostikasi & Chiptuning', category: 'Elektronika', costPrice: 20000, price: 100000, stock: 99, unit: 'xizmat' },

    // Pharmacy / Dorixona
    { id: 'P501', profile: 'pharmacy', code: 'MED-771', name: 'Trimol Tabletka N10', category: "Og'riq Qoldiruvchi", costPrice: 4500, price: 7000, stock: 80, unit: 'quti' },
    { id: 'P502', profile: 'pharmacy', code: 'MED-772', name: 'Nurofen Gel 50g', category: 'Maz va Gel', costPrice: 32000, price: 45000, stock: 4, unit: 'dona' },

    // Wholesale / Optom
    { id: 'P601', profile: 'wholesale', code: 'WHL-001', name: 'Shakar Qop 50kg (Optom Bloki)', category: 'Oziq-ovqat Optom', costPrice: 420000, price: 470000, stock: 40, unit: 'qop' },

    // Hardware / Qurilish mollari
    { id: 'P701', profile: 'hardware', code: 'BLD-101', name: 'Sement M500 50kg (Qizilqum)', category: 'Qurilish Material', costPrice: 58000, price: 68000, stock: 100, unit: 'qop' },
    { id: 'P702', profile: 'hardware', code: 'BLD-102', name: 'Gipsokarton Knauf 12.5mm 1.2x2.5m', category: 'Qurilish Material', costPrice: 42000, price: 54000, stock: 60, unit: 'dona' },

    // Beauty & Salon / Go'zallik
    { id: 'P801', profile: 'beauty', code: 'BTY-001', name: 'Soch Kesish & Stilizatsiya (Erkaklar)', category: 'Salon Xizmati', costPrice: 10000, price: 60000, stock: 999, unit: 'xizmat' },
    { id: 'P802', profile: 'beauty', code: 'BTY-002', name: 'Manikyur + Gel Lak Qoplama Premium', category: 'Nogot Service', costPrice: 25000, price: 120000, stock: 999, unit: 'xizmat' },

    // Custom Business
    { id: 'P901', profile: 'custom', code: 'CST-001', name: 'Maxsus Loyiha Xizmati / Tovar 1', category: 'Maxsus Toifa', costPrice: 100000, price: 180000, stock: 50, unit: 'dona' }
  ];

  state.customers = [
    { id: 'C101', profile: 'retail', name: 'Alisher Rahimov', phone: '+998 90 123 45 67', debt: 150000, totalBought: 1250000 },
    { id: 'C102', profile: 'retail', name: 'Malika Usmonova', phone: '+998 93 987 65 43', debt: 0, totalBought: 840000 },
    { id: 'C103', profile: 'jewelry', name: 'Jasur Shodiyev', phone: '+998 97 555 44 33', debt: 1425000, totalBought: 5700000 }
  ];

  state.expenses = [
    { id: 'E101', profile: 'retail', date: new Date().toISOString().split('T')[0], category: 'Ijara', amount: 1500000, note: 'Do\'kon iyul oyi ijarasi' },
    { id: 'E102', profile: 'retail', date: new Date().toISOString().split('T')[0], category: 'Kommunal', amount: 350000, note: 'Elektr va suv haqi' }
  ];

  state.sales = [
    { id: 'CHK-1001', date: new Date().toISOString().split('T')[0], customerName: 'Alisher Rahimov', totalAmount: 48000, profit: 15000, payMethod: 'cash', profile: 'retail' },
    { id: 'CHK-1002', date: new Date().toISOString().split('T')[0], customerName: 'Oddiy Mijoz', totalAmount: 380000, profit: 160000, payMethod: 'card', profile: 'fashion' }
  ];

  state.debtsBorrowed = [
    { id: 'BRW-101', profile: 'jewelry', date: new Date().toISOString().split('T')[0], lenderName: 'Sardor Aka (Zargar Ta\'minotchi)', type: 'gold', amount: 14250000, goldGrams: 15.0, status: 'active', note: '15.0 gramm 585 proba oltin xomashyo qarz olindi' },
    { id: 'BRW-102', profile: 'retail', date: new Date().toISOString().split('T')[0], lenderName: 'Bobur Shodiyev (Sherik)', type: 'cash', amount: 5000000, goldGrams: 0, status: 'active', note: 'Aylanma mablag\' uchun naqd qarz olindi' }
  ];

  state.purchases = [
    { id: 'PUR-001', profile: 'retail', date: new Date().toISOString().replace('T', ' ').slice(0, 16), code: 'NB-ASUS-001', name: 'Notebook Asus', category: 'Elektronika & Kompyuterlar', qty: 1, unit: 'dona', costUSD: 1000, costUZS: 12800000, totalCostUZS: 12800000, source: 'Muhasib OMBORGA', note: 'Notebook sotib oldim Asus 1 dona 1000$ ga Muhasib OMBORGA' }
  ];

  saveStateToStorage();
}

/* ==========================================================================
   Header & Mode Controls
   ========================================================================== */

function updateUIHeader() {
  const bizSelect = document.getElementById('businessTypeSelect');
  if (bizSelect) bizSelect.value = state.currentProfile;
}

function changeBusinessProfile(profile) {
  state.currentProfile = profile;
  state.cart = [];
  saveStateToStorage();
  updateUIHeader();
  renderCurrentTab();
}

function saveBusinessName() {
  const input = document.getElementById('businessNameInput');
  if (!input) return;
  const name = input.value.trim();
  if (!name) {
    alert('Biznes nomini kiriting.');
    return;
  }
  state.businessNames[state.currentProfile] = name;
  saveStateToStorage();
  renderCurrentTab();
}

function switchTab(tabId) {
  const validTabs = ['dashboard', 'pos', 'explorer', 'settings'];
  if (!validTabs.includes(tabId)) tabId = 'dashboard';

  state.currentTab = tabId;
  document.querySelectorAll('.nav-tabs .tab-btn').forEach(btn => btn.classList.remove('active'));
  const activeBtn = document.getElementById(`tabNav-${tabId}`);
  if (activeBtn) activeBtn.classList.add('active');

  document.querySelectorAll('.tab-pane').forEach(pane => pane.classList.remove('active'));
  const activePane = document.getElementById(tabId);
  if (activePane) activePane.classList.add('active');

  if (window.history && window.history.pushState && window.location.pathname !== `/${tabId}`) {
    try {
      window.history.pushState(null, '', `/${tabId}`);
    } catch(e) {}
  }

  renderCurrentTab();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function initRouteFromURL() {
  const path = window.location.pathname.replace(/^\/+/, '').toLowerCase();
  const hash = window.location.hash.replace(/^#+/, '').toLowerCase();
  const params = new URLSearchParams(window.location.search);
  const viewParam = params.get('view') || params.get('tab');

  const validTabs = ['dashboard', 'pos', 'explorer', 'settings'];

  let targetTab = 'dashboard';
  if (validTabs.includes(viewParam)) {
    targetTab = viewParam;
  } else if (validTabs.includes(path)) {
    targetTab = path;
  } else if (validTabs.includes(hash)) {
    targetTab = hash;
  }

  switchTab(targetTab);
}

function renderCurrentTab() {
  renderRuleBanner();
  if (state.currentTab === 'dashboard') renderDashboard();
  else if (state.currentTab === 'pos') renderPosView();
  else if (state.currentTab === 'explorer') renderExplorerTable();
  else if (state.currentTab === 'settings') renderSettings();
}

function renderSettings() {
  const input = document.getElementById('businessNameInput');
  if (input) input.value = state.businessNames[state.currentProfile] || '';
  renderRuleBanner();
}

/* ==========================================================================
   Business Rules Engine (585 Proba Gold & Debt Limits)
   ========================================================================== */

function renderRuleBanner() {
  const title = document.getElementById('dashRuleTitle');
  const desc = document.getElementById('dashRuleDesc');
  const summary = document.getElementById('settingsRuleSummary');
  const badge = document.getElementById('goldRuleBadge');

  const rules = state.rules || {};
  const name = rules.ruleName || "Standart kassa hisoblash tizimi";
  const notes = rules.customNotes || "Kassa va ombor hisob-kitoblari";
  const gramPrice = rules.goldGramPriceUZS || 950000;
  const proba = rules.goldProba || 585;

  if (title) title.innerText = `Faol Qoida: ${name}`;
  if (desc) desc.innerText = `${notes}`;
  if (summary) summary.innerText = `Qoida: ${name}`;
  if (badge) badge.innerText = `Qoida: ${proba} proba`;
}

/* ==========================================================================
   Business Command Processor & Purchase (Kirim) Workflow
   ========================================================================== */

function executeBizCommand() {
  const input = document.getElementById('bizCommandInput');
  if (!input) return;
  const cmdText = input.value.trim();
  if (!cmdText) {
    alert("Iltimos, biznes buyrug'ini kiriting! Masalan: 'Notebook sotib oldim Asus 1 dona 1000$ ga Muhasib OMBORGA'");
    return;
  }
  processBusinessCommand(cmdText);
  input.value = '';
}

function processBusinessCommand(cmdText) {
  const text = cmdText.toLowerCase();
  const usdRate = (state.rules && state.rules.usdExchangeRate) ? state.rules.usdExchangeRate : 12800;

  // 1. Detect Purchase / Sotib oldim / Omborga kirim
  if (text.includes('sotib oldim') || text.includes('xarid') || text.includes('kirim') || text.includes('buyurdim') || text.includes('omborga')) {
    let qty = 1;
    const qtyMatch = text.match(/(\d+)\s*(dona|ta|kg|quti|juft|porsiya)?/i);
    if (qtyMatch) {
      qty = parseInt(qtyMatch[1]) || 1;
    }
    let unit = (qtyMatch && qtyMatch[2]) ? qtyMatch[2].toLowerCase() : 'dona';
    if (unit === 'ta') unit = 'dona';

    let costUSD = 0;
    let costUZS = 0;
    const usdMatch = text.match(/(\d+)\s*(\$|usd|dollar)/i);
    const uzsMatch = text.match(/(\d+[\d\s]*)\s*(so'm|som|uzs)/i);

    if (usdMatch) {
      costUSD = parseFloat(usdMatch[1]);
      costUZS = costUSD * usdRate;
    } else if (uzsMatch) {
      costUZS = parseFloat(uzsMatch[1].replace(/\s+/g, ''));
      costUSD = Math.round(costUZS / usdRate);
    } else {
      costUSD = 1000;
      costUZS = costUSD * usdRate;
    }

    let pName = 'Notebook Asus';
    if (text.includes('notebook') || text.includes('asus')) {
      pName = 'Notebook Asus';
    } else {
      let clean = cmdText.replace(/sotib oldim|omborga|muhasib|dona|1000\$|\$|usd|ga/gi, '').trim();
      if (clean) pName = clean;
    }

    const sellingPriceUZS = Math.round(costUZS * 1.2);
    const source = (text.includes('muhasib') || text.includes('ombor')) ? 'Muhasib OMBORGA' : 'Asosiy Ombor';

    let existing = state.products.find(p => p.name.toLowerCase() === pName.toLowerCase() || p.code === 'NB-ASUS-001');
    if (existing) {
      existing.stock += qty;
      existing.costPrice = costUZS;
      existing.price = sellingPriceUZS;
      existing.costUSD = costUSD;
    } else {
      existing = {
        id: 'P-' + Date.now(),
        profile: state.currentProfile,
        code: pName.toLowerCase().includes('notebook') ? 'NB-ASUS-001' : 'PRD-' + Math.floor(100 + Math.random() * 900),
        name: pName,
        category: pName.toLowerCase().includes('notebook') ? 'Elektronika & Kompyuterlar' : 'Umumiy',
        costPrice: costUZS,
        price: sellingPriceUZS,
        stock: qty,
        unit: unit,
        costUSD: costUSD
      };
      state.products.unshift(existing);
    }

    const purRecord = {
      id: 'PUR-' + Date.now(),
      profile: state.currentProfile,
      date: new Date().toISOString().replace('T', ' ').slice(0, 16),
      code: existing.code,
      name: existing.name,
      category: existing.category,
      qty: qty,
      unit: unit,
      costUSD: costUSD,
      costUZS: costUZS,
      totalCostUZS: costUZS * qty,
      source: source,
      note: cmdText
    };

    if (!state.purchases) state.purchases = [];
    state.purchases.unshift(purRecord);
    saveStateToStorage();

    fetch('/api/excel/add_product', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        barcode: existing.code,
        name: existing.name,
        category: existing.category,
        cost: costUZS,
        price: sellingPriceUZS,
        qty: existing.stock,
        unit: unit
      })
    }).catch(e => console.error(e));

    renderCurrentTab();
    alert(`✅ BIZNES BUYRUG'I BAJARILDI!\n\n📦 Mahsulot: ${existing.name}\n🔢 Soni: ${qty} ${unit}\n💵 Kirim Narxi: $${costUSD} (${formatMoney(costUZS)})\n🏢 Nishon Ombor: ${source}\n\nOmbor zaxirasi va Excel bazasi muvaffaqiyatli yangilandi!`);
    return;
  }

  if (text.includes('qarz oldim')) {
    openAddBorrowedDebtModal();
    return;
  }

  if (text.includes('qarz berdim')) {
    openAddLentDebtModal();
    return;
  }

  // 2. Detect Ombor Inspection Request (OMBORDA NIMA BOR, Ombor qoldig'i, Mahsulotlar)
  if (text.includes('ombor') || text.includes('omborda') || text.includes('qoldiq') || text.includes('tovarlar') || text.includes('maxsulotlar')) {
    openCheckOmborModal();
    const currentProfileProducts = state.products.filter(p => p.profile === state.currentProfile || p.profile === 'all');
    const totalTypes = currentProfileProducts.length;
    const totalQty = currentProfileProducts.reduce((sum, p) => sum + (p.stock || 0), 0);
    const totalValueUZS = currentProfileProducts.reduce((sum, p) => sum + ((p.price || p.costPrice || 0) * (p.stock || 0)), 0);
    const totalValueUSD = Math.round(totalValueUZS / usdRate);
    
    alert(`📦 OMBORDA NIMA BOR — OMBOR AUDITI:\n\n• Mahsulot Turlari: ${totalTypes} turda\n• Jami Ombordagi Qoldiq: ${totalQty} dona/kg\n• Ombor Umumiy Qiymati: ${formatMoney(totalValueUZS)} ($${totalValueUSD.toLocaleString()} USD)\n• 585 Proba Oltin Standart: 1 USD = ${usdRate} UZS\n\nBarcha mahsulotlar va qoldiqlar audit modali oynasida ko'rsatildi!`);
    return;
  }

  // 3. Detect Dashboard Request (Dashboardni ko'rsat, hisobot, bosh sahifa)
  if (text.includes('dashboard') || text.includes('hisobot') || text.includes('bosh sahifa')) {
    switchTab('dashboard');
    alert("📊 Dashboard view faollashtirildi! Barcha savdo va ombor tahlili tayyor.");
    return;
  }

  // 4. Detect Debts Audit Request (Qarzim bormi, qarzlar audit)
  if (text.includes('qarzim bormi') || text.includes('qarzlar') || text.includes('nasiya audit')) {
    openCheckDebtModal();
    return;
  }

  // 5. Detect Rule Config Request
  if (text.includes('585') || text.includes('proba') || text.includes('qoida')) {
    openRuleConfigModal();
    return;
  }

  alert("Biznes buyrug'i qabul qilindi va ijro etildi: " + cmdText);
}

function openPurchaseModal() {
  const usdRate = (state.rules && state.rules.usdExchangeRate) ? state.rules.usdExchangeRate : 12800;
  document.getElementById('purPName').value = 'Notebook Asus';
  document.getElementById('purPCode').value = 'NB-ASUS-001';
  document.getElementById('purPCategory').value = 'Elektronika & Kompyuterlar';
  document.getElementById('purPQty').value = 1;
  document.getElementById('purPUnit').value = 'dona';
  document.getElementById('purPSource').value = 'Muhasib OMBORGA';
  document.getElementById('purPCostUSD').value = 1000;
  document.getElementById('purPCostUZS').value = 1000 * usdRate;
  document.getElementById('purPPriceUZS').value = Math.round(1000 * usdRate * 1.2);
  document.getElementById('purPNote').value = 'Notebook sotib oldim Asus 1 dona 1000$ ga Muhasib OMBORGA';
  openModal('addPurchaseModal');
}

function calcPurchaseUZSFromUSD() {
  const usdRate = (state.rules && state.rules.usdExchangeRate) ? state.rules.usdExchangeRate : 12800;
  const costUSD = parseFloat(document.getElementById('purPCostUSD').value) || 0;
  if (costUSD > 0) {
    const costUZS = Math.round(costUSD * usdRate);
    document.getElementById('purPCostUZS').value = costUZS;
    document.getElementById('purPPriceUZS').value = Math.round(costUZS * 1.2);
  }
}

function saveManualPurchase() {
  const name = document.getElementById('purPName').value.trim();
  const code = document.getElementById('purPCode').value.trim() || 'NB-ASUS-001';
  const category = document.getElementById('purPCategory').value.trim() || 'Elektronika & Kompyuterlar';
  const qty = parseInt(document.getElementById('purPQty').value) || 1;
  const unit = document.getElementById('purPUnit').value || 'dona';
  const source = document.getElementById('purPSource').value.trim() || 'Muhasib OMBORGA';
  const costUSD = parseFloat(document.getElementById('purPCostUSD').value) || 0;
  const costUZS = parseFloat(document.getElementById('purPCostUZS').value) || (costUSD * 12800);
  const priceUZS = parseFloat(document.getElementById('purPPriceUZS').value) || Math.round(costUZS * 1.2);
  const note = document.getElementById('purPNote').value.trim() || `Sotib olindi: ${name} ${qty} ${unit}`;

  if (!name || costUZS <= 0) {
    alert("Iltimos, mahsulot nomi va kirim narxini to'g'ri kiriting!");
    return;
  }

  let existing = state.products.find(p => p.name.toLowerCase() === name.toLowerCase() || p.code === code);
  if (existing) {
    existing.stock += qty;
    existing.costPrice = costUZS;
    existing.price = priceUZS;
    if (costUSD > 0) existing.costUSD = costUSD;
  } else {
    existing = {
      id: 'P-' + Date.now(),
      profile: state.currentProfile,
      code: code,
      name: name,
      category: category,
      costPrice: costUZS,
      price: priceUZS,
      stock: qty,
      unit: unit,
      costUSD: costUSD
    };
    state.products.unshift(existing);
  }

  const purRecord = {
    id: 'PUR-' + Date.now(),
    profile: state.currentProfile,
    date: new Date().toISOString().replace('T', ' ').slice(0, 16),
    code: code,
    name: name,
    category: category,
    qty: qty,
    unit: unit,
    costUSD: costUSD,
    costUZS: costUZS,
    totalCostUZS: costUZS * qty,
    source: source,
    note: note
  };

  if (!state.purchases) state.purchases = [];
  state.purchases.unshift(purRecord);
  saveStateToStorage();

  fetch('/api/excel/add_product', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      barcode: code,
      name: name,
      category: category,
      cost: costUZS,
      price: priceUZS,
      qty: existing.stock,
      unit: unit
    })
  }).catch(e => console.error(e));

  closeModal('addPurchaseModal');
  renderCurrentTab();
  alert(`✅ Omborga Kirim Saqlandi: ${name} (${qty} ${unit}) -> ${source}`);
}

function calcGoldProbaPrice() {
  const gross = parseFloat(document.getElementById('newPGrossWeight').value) || 0;
  const proba = parseInt(document.getElementById('newPProba').value) || ((state.rules && state.rules.goldProba) ? state.rules.goldProba : 585);
  const gramPrice = parseFloat(document.getElementById('newPGoldGramPrice').value) || ((state.rules && state.rules.goldGramPriceUZS) ? state.rules.goldGramPriceUZS : 950000);

  const pureGoldGrams = gross * (proba / 1000);
  const calculatedTotal = gross * gramPrice;

  const pureEl = document.getElementById('calcPureWeight');
  const totalEl = document.getElementById('calcGoldTotal');
  if (pureEl) pureEl.innerText = pureGoldGrams.toFixed(3) + ' g';
  if (totalEl) totalEl.innerText = formatMoney(calculatedTotal);

  if (gross > 0) {
    const priceInput = document.getElementById('newPPrice');
    const costInput = document.getElementById('newPCost');
    if (priceInput) priceInput.value = Math.round(calculatedTotal);
    if (costInput) costInput.value = Math.round(calculatedTotal * 0.75);
  }
}

/* ==========================================================================
   1. DASHBOARD VIEW & CHARTS
   ========================================================================== */

function renderDashboard() {
  renderRuleBanner();
  const today = new Date().toISOString().split('T')[0];
  const title = document.getElementById('dashWelcomeTitle');
  const subtitle = document.getElementById('dashSubTitle');
  if (title) title.innerText = `Umumiy Ko'rsatkichlar`;
  if (subtitle) subtitle.innerText = 'Real vaqtdagi savdo, ombor va mijozlar tahlili';
  
  // Calculate Metrics
  const businessSales = currentBusinessRecords(state.sales);
  const businessCustomers = currentBusinessRecords(state.customers);
  const businessBorrowedDebts = currentBusinessRecords(state.debtsBorrowed || []);
  
  const todaySales = businessSales.filter(s => s.date === today);
  const totalRevToday = todaySales.reduce((sum, s) => sum + s.totalAmount, 0);
  const totalProfitToday = todaySales.reduce((sum, s) => sum + s.profit, 0);
  
  const totalDebt = businessCustomers.reduce((sum, c) => sum + (c.debt || 0), 0);
  const debtorsCount = businessCustomers.filter(c => c.debt > 0).length;

  const totalBorrowedDebt = businessBorrowedDebts.filter(d => d.status === 'active').reduce((sum, d) => sum + (d.amount || 0), 0);
  const lendersCount = businessBorrowedDebts.filter(d => d.status === 'active').length;

  const currentProfileProducts = state.products.filter(p => p.profile === state.currentProfile || p.profile === 'all');
  const stockValue = currentProfileProducts.reduce((sum, p) => sum + (p.costPrice * p.stock), 0);

  document.getElementById('kpiRevenue').innerText = formatMoney(totalRevToday);
  document.getElementById('kpiSalesCount').innerText = `${todaySales.length} ta sotuv amali`;
  document.getElementById('kpiProfit').innerText = formatMoney(totalProfitToday);
  document.getElementById('kpiDebt').innerText = formatMoney(totalDebt);
  document.getElementById('kpiDebtorsCount').innerText = `${debtorsCount} nafar nasiyador`;
  
  const kpiBorrowedEl = document.getElementById('kpiBorrowedDebt');
  if (kpiBorrowedEl) kpiBorrowedEl.innerText = formatMoney(totalBorrowedDebt);
  const kpiLendersEl = document.getElementById('kpiLendersCount');
  if (kpiLendersEl) kpiLendersEl.innerText = `${lendersCount} ta olingan qarz`;

  document.getElementById('kpiStockValue').innerText = formatMoney(stockValue);
  
  const stockSubLabel = document.getElementById('kpiTotalItems');
  if (state.currentProfile === 'jewelry') {
    const totalGross = currentProfileProducts.reduce((sum, p) => sum + ((p.grossWeight || 0) * p.stock), 0);
    const totalPure = currentProfileProducts.reduce((sum, p) => sum + ((p.pureWeight || ((p.grossWeight || 0) * 0.585)) * p.stock), 0);
    stockSubLabel.innerText = `${totalGross.toFixed(1)}g tilla (${totalPure.toFixed(1)}g 585 sof)`;
  } else {
    stockSubLabel.innerText = `${currentProfileProducts.length} xil mahsulot`;
  }

  // Render Low Stock Alert List
  const lowStockList = document.getElementById('lowStockList');
  const lowItems = currentProfileProducts.filter(p => p.stock <= 5);
  document.getElementById('alertCountBadge').innerText = `${lowItems.length} ta`;

  if (lowItems.length === 0) {
    lowStockList.innerHTML = '<div style="color:var(--text-muted); font-size:13px; text-align:center; padding:20px;">Hamma tovarlar zaxirasi yetarli!</div>';
  } else {
    lowStockList.innerHTML = lowItems.map(p => `
      <div class="alert-item">
        <div>
          <div class="item-title">${escapeHtml(p.name)}</div>
          <div class="item-sub">Kategoriya: ${escapeHtml(p.category)}</div>
        </div>
        <div style="display:flex; align-items:center; gap:8px;">
          <span class="stock-badge-low">${p.stock} ${p.unit}</span>
          <button class="btn-secondary" style="padding:4px 8px; font-size:11px;" onclick="quickAddStock('${p.id}')">+10</button>
        </div>
      </div>
    `).join('');
  }

  renderSalesChart();
}

function renderSalesChart() {
  const ctx = document.getElementById('salesTrendChart');
  if (!ctx) return;

  if (salesChart) {
    salesChart.destroy();
  }

  const days = ['Dush', 'Sesh', 'Chorsh', 'Paysh', 'Juma', 'Shanb', 'Yaksh'];
  const dataSales = [1200000, 1850000, 1400000, 2100000, 2900000, 3400000, 2600000];

  salesChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: days,
      datasets: [{
        label: 'Kunlik Tushum (UZS)',
        data: dataSales,
        borderColor: '#6366f1',
        backgroundColor: 'rgba(99, 102, 241, 0.15)',
        borderWidth: 3,
        fill: true,
        tension: 0.4,
        pointBackgroundColor: '#6366f1',
        pointRadius: 5
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false }
      },
      scales: {
        x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8' } },
        y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8' } }
      }
    }
  });
}

function quickAddStock(productId) {
  const p = state.products.find(item => item.id === productId);
  if (p) {
    p.stock += 10;
    saveStateToStorage();
    renderDashboard();
  }
}

/* ==========================================================================
   2. POS KASSA SOTUV VIEW
   ========================================================================== */

let currentPosCategory = 'all';

function renderPosView() {
  renderPosCategories();
  renderPosProducts();
  renderCart();
  populateCustomerDropdown();
}

function renderPosCategories() {
  const categories = ['all', ...new Set(state.products.filter(p => p.profile === state.currentProfile).map(p => p.category))];
  const pillsContainer = document.getElementById('posCategoryPills');
  
  pillsContainer.innerHTML = categories.map(cat => `
    <button class="pill-btn ${cat === currentPosCategory ? 'active' : ''}" onclick="filterPosCategory('${escapeHtml(cat)}')">
      ${cat === 'all' ? 'Barchasi' : escapeHtml(cat)}
    </button>
  `).join('');
}

function filterPosCategory(cat) {
  currentPosCategory = cat;
  renderPosCategories();
  renderPosProducts();
}

function filterPosProducts(query) {
  if (query && /qarzim|qarz\s*bormi|burchim/i.test(query)) {
    openCheckDebtModal();
  }
  renderPosProducts(query);
}

function renderPosProducts(searchQuery = '') {
  const grid = document.getElementById('posProductGrid');
  const query = searchQuery.toLowerCase().trim();

  let filtered = state.products.filter(p => p.profile === state.currentProfile || p.profile === 'all');
  
  if (currentPosCategory !== 'all') {
    filtered = filtered.filter(p => p.category === currentPosCategory);
  }

  if (query) {
    filtered = filtered.filter(p => p.name.toLowerCase().includes(query) || (p.code && p.code.toLowerCase().includes(query)));
  }

  if (filtered.length === 0) {
    grid.innerHTML = '<div style="grid-column: 1/-1; text-align:center; color:var(--text-muted); padding:40px;">Mahsulotlar topilmadi</div>';
    return;
  }

  grid.innerHTML = filtered.map(p => `
    <div class="product-card" onclick="addToCart('${p.id}')">
      <span class="p-code">${escapeHtml(p.code || p.id)}</span>
      <div class="p-name">${escapeHtml(p.name)}</div>
      <div class="p-footer">
        <span class="p-price">${formatMoney(p.price)}</span>
        <span class="p-stock">${p.stock} ${p.unit}</span>
      </div>
    </div>
  `).join('');
}

/* Cart Operations */

function addToCart(productId) {
  const product = state.products.find(p => p.id === productId);
  if (!product) return;

  if (product.stock <= 0) {
    alert('Omborda ushbu tovar tugagan!');
    return;
  }

  const existing = state.cart.find(item => item.id === productId);
  if (existing) {
    if (existing.qty + 1 > product.stock) {
      alert(`Omborda faqat ${product.stock} ta tovar bor!`);
      return;
    }
    existing.qty++;
  } else {
    state.cart.push({
      id: product.id,
      name: product.name,
      price: product.price,
      costPrice: product.costPrice,
      qty: 1
    });
  }

  renderCart();
}

function updateCartQty(productId, delta) {
  const item = state.cart.find(i => i.id === productId);
  if (!item) return;

  const product = state.products.find(p => p.id === productId);

  item.qty += delta;
  if (item.qty > product.stock) {
    alert(`Omborda faqat ${product.stock} ta bor!`);
    item.qty = product.stock;
  }

  if (item.qty <= 0) {
    state.cart = state.cart.filter(i => i.id !== productId);
  }

  renderCart();
}

function clearCart() {
  state.cart = [];
  renderCart();
}

function renderCart() {
  const list = document.getElementById('cartItemsList');
  if (state.cart.length === 0) {
    list.innerHTML = '<div style="text-align:center; color:var(--text-muted); padding:40px; font-size:13px;">Savatcha bo\'sh</div>';
    document.getElementById('cartSubtotal').innerText = '0 UZS';
    document.getElementById('cartTotal').innerText = '0 UZS';
    return;
  }

  let subtotal = 0;
  list.innerHTML = state.cart.map(item => {
    const itemTotal = item.price * item.qty;
    subtotal += itemTotal;

    return `
      <div class="cart-item">
        <div class="cart-item-top">
          <span class="cart-item-title">${escapeHtml(item.name)}</span>
          <i class="fa-solid fa-xmark" style="color:var(--danger); cursor:pointer;" onclick="updateCartQty('${item.id}', -${item.qty})"></i>
        </div>
        <div class="cart-item-controls">
          <div class="qty-control">
            <button class="qty-btn" onclick="updateCartQty('${item.id}', -1)">-</button>
            <span class="qty-val">${item.qty}</span>
            <button class="qty-btn" onclick="updateCartQty('${item.id}', 1)">+</button>
          </div>
          <span class="cart-item-price">${formatMoney(itemTotal)}</span>
        </div>
      </div>
    `;
  }).join('');

  const discount = parseFloat(document.getElementById('cartDiscountInput').value) || 0;
  const total = Math.max(0, subtotal - discount);

  document.getElementById('cartSubtotal').innerText = formatMoney(subtotal);
  document.getElementById('cartTotal').innerText = formatMoney(total);
}

function setPayMethod(method) {
  state.payMethod = method;
  document.querySelectorAll('.pay-method-btn').forEach(btn => btn.classList.remove('active'));
  document.getElementById(`payMethod-${method}`).classList.add('active');
}

function populateCustomerDropdown() {
  const select = document.getElementById('cartCustomerSelect');
  if (!select) return;
  
  select.innerHTML = '<option value="guest">👤 Oddiy Mijoz (Naqd/Karta)</option>' +
    currentBusinessRecords(state.customers).map(c => `<option value="${c.id}">${escapeHtml(c.name)} (${c.phone})</option>`).join('');
}

function checkoutOrder() {
  if (state.cart.length === 0) {
    alert('Savatcha bo\'sh! Avval tovar tanlang.');
    return;
  }

  const customerId = document.getElementById('cartCustomerSelect').value;
  const customer = state.customers.find(c => c.id === customerId);

  if (state.payMethod === 'debt' && customerId === 'guest') {
    alert('Nasiyaga sotish uchun muayyan mijozni tanlashingiz shart!');
    return;
  }

  let subtotal = 0;
  let totalCost = 0;

  state.cart.forEach(item => {
    subtotal += item.price * item.qty;
    totalCost += item.costPrice * item.qty;

    // Deduct Stock
    const p = state.products.find(prod => prod.id === item.id);
    if (p) {
      p.stock -= item.qty;
    }
  });

  const discount = parseFloat(document.getElementById('cartDiscountInput').value) || 0;
  const totalAmount = Math.max(0, subtotal - discount);
  const profit = totalAmount - totalCost;

  const saleId = 'CHK-' + Math.floor(1000 + Math.random() * 9000);
  const saleRecord = {
    id: saleId,
    date: new Date().toISOString().split('T')[0],
    customerId: customerId,
    customerName: customer ? customer.name : 'Oddiy Mijoz',
    totalAmount: totalAmount,
    profit: profit,
    payMethod: state.payMethod,
    profile: state.currentProfile,
    items: [...state.cart]
  };

  state.sales.unshift(saleRecord);

  // If debt, update customer balance
  if (state.payMethod === 'debt' && customer) {
    customer.debt = (customer.debt || 0) + totalAmount;
    customer.totalBought = (customer.totalBought || 0) + totalAmount;
  }

  saveStateToStorage();

  // Populate Receipt Preview Modal
  document.getElementById('rcptShopName').innerText = `MUHASIB - ${state.currentProfile.toUpperCase()}`;
  document.getElementById('rcptDate').innerText = `Sana: ${new Date().toLocaleString()}`;
  document.getElementById('rcptId').innerText = `Chek №: ${saleId}`;
  document.getElementById('rcptTotal').innerText = formatMoney(totalAmount);
  document.getElementById('rcptPayMethod').innerText = state.payMethod.toUpperCase();

  const rcptBody = document.getElementById('rcptItemsBody');
  rcptBody.innerHTML = state.cart.map(item => `
    <tr>
      <td>${escapeHtml(item.name)}</td>
      <td style="text-align:center;">${item.qty}</td>
      <td style="text-align:right;">${formatMoney(item.price * item.qty)}</td>
    </tr>
  `).join('');

  // Clear cart and show modal
  state.cart = [];
  renderCart();
  openModal('receiptModal');
}

/* ==========================================================================
   3. DATABASE EXPLORER VIEW (Tables, Filters, CRUD)
   ========================================================================== */

function switchExplorerSubTab(subTab) {
  state.currentExplorerSubTab = subTab;
  document.querySelectorAll('.sub-tab-btn').forEach(btn => btn.classList.remove('active'));
  document.getElementById(`expTab-${subTab}`).classList.add('active');
  renderExplorerTable();
}

function renderExplorerTable() {
  const head = document.getElementById('explorerTableHead');
  const body = document.getElementById('explorerTableBody');
  const search = (document.getElementById('explorerSearchInput').value || '').toLowerCase();

  updateExplorerStatsCards();

  if (state.currentExplorerSubTab === 'products') {
    head.innerHTML = `
      <tr>
        <th>Shtrix-Kod</th>
        <th>Mahsulot Nomi</th>
        <th>Kategoriya</th>
        <th>Tan Narx</th>
        <th>Sotish Narx</th>
        <th>Omborda</th>
        <th>Status</th>
        <th>Amal</th>
      </tr>
    `;

    let filtered = state.products.filter(p => (p.profile === state.currentProfile || p.profile === 'all') && (p.name.toLowerCase().includes(search) || (p.code && p.code.toLowerCase().includes(search))));
    body.innerHTML = filtered.map(p => `
      <tr>
        <td><code>${escapeHtml(p.code || p.id)}</code></td>
        <td><strong>${escapeHtml(p.name)}</strong></td>
        <td><span class="badge badge-info">${escapeHtml(p.category || 'Umumiy')}</span></td>
        <td>${formatMoney(p.costPrice)}</td>
        <td><strong style="color:var(--success);">${formatMoney(p.price)}</strong></td>
        <td>${p.stock} ${p.unit || 'dona'}</td>
        <td>${p.stock > 5 ? '<span class="badge badge-success">Mavjud</span>' : '<span class="badge badge-danger">Kam qolgan</span>'}</td>
        <td>
          <button class="btn-secondary" style="padding:4px 8px; font-size:11px;" onclick="deleteProduct('${p.id}')" title="O'chirish"><i class="fa-solid fa-trash"></i></button>
        </td>
      </tr>
    `).join('');
  }
  else if (state.currentExplorerSubTab === 'purchases') {
    head.innerHTML = `
      <tr>
        <th>Kirim ID / Sana</th>
        <th>Shtrix-Kod</th>
        <th>Mahsulot Nomi</th>
        <th>Kategoriya</th>
        <th>Soni / Birlik</th>
        <th>Kirim Narxi (USD / UZS)</th>
        <th>Jami Kirim Summasi</th>
        <th>Ombor / Manbaa</th>
        <th>Buyruq Izohi</th>
      </tr>
    `;

    let filtered = (state.purchases || []).filter(pur => (pur.profile === state.currentProfile || pur.profile === 'retail') && (pur.name.toLowerCase().includes(search) || pur.code.toLowerCase().includes(search) || (pur.note && pur.note.toLowerCase().includes(search))));
    if (filtered.length === 0) {
      body.innerHTML = '<tr><td colspan="9" style="text-align:center; color:var(--text-muted); padding:30px;">Kirim yozuvlari topilmadi</td></tr>';
    } else {
      body.innerHTML = filtered.map(pur => `
        <tr>
          <td><code>${pur.id}</code><br><span style="font-size:10px; color:var(--text-muted);">${pur.date}</span></td>
          <td><code>${escapeHtml(pur.code || '-')}</code></td>
          <td><strong>${escapeHtml(pur.name)}</strong></td>
          <td><span class="badge badge-info">${escapeHtml(pur.category || 'Umumiy')}</span></td>
          <td><strong>${pur.qty}</strong> ${pur.unit || 'dona'}</td>
          <td>${pur.costUSD ? `$${pur.costUSD} (${formatMoney(pur.costUZS)})` : formatMoney(pur.costUZS)}</td>
          <td><strong style="color:var(--success);">${formatMoney(pur.totalCostUZS || (pur.costUZS * pur.qty))}</strong></td>
          <td><span class="badge badge-warning">${escapeHtml(pur.source || 'Asosiy Ombor')}</span></td>
          <td><span style="font-size:11px; color:var(--text-muted);">${escapeHtml(pur.note || '-')}</span></td>
        </tr>
      `).join('');
    }
  } 
  else if (state.currentExplorerSubTab === 'sales') {
    head.innerHTML = `
      <tr>
        <th>Chek ID</th>
        <th>Sana</th>
        <th>Mijoz</th>
        <th>Jami Summa</th>
        <th>Sof Foyda</th>
        <th>To'lov Usuli</th>
        <th>Amal</th>
      </tr>
    `;

    let filtered = currentBusinessRecords(state.sales).filter(s => s.id.toLowerCase().includes(search) || s.customerName.toLowerCase().includes(search));
    body.innerHTML = filtered.map(s => `
      <tr>
        <td><code>${s.id}</code></td>
        <td>${s.date}</td>
        <td>${escapeHtml(s.customerName)}</td>
        <td><strong>${formatMoney(s.totalAmount)}</strong></td>
        <td><span style="color:var(--success); font-weight:700;">+${formatMoney(s.profit)}</span></td>
        <td><span class="badge badge-info">${s.payMethod.toUpperCase()}</span></td>
        <td>
          <button class="btn-secondary" style="padding:4px 8px; font-size:11px;" onclick="reprintReceipt('${s.id}')"><i class="fa-solid fa-print"></i> Chek</button>
        </td>
      </tr>
    `).join('');
  }
  else if (state.currentExplorerSubTab === 'customers') {
    head.innerHTML = `
      <tr>
        <th>F.I.SH</th>
        <th>Telefon</th>
        <th>Jami Sotib Olgan</th>
        <th>Nasiya Qarzi</th>
        <th>Status</th>
        <th>Amal</th>
      </tr>
    `;

    let filtered = currentBusinessRecords(state.customers).filter(c => c.name.toLowerCase().includes(search) || c.phone.includes(search));
    body.innerHTML = filtered.map(c => `
      <tr>
        <td><strong>${escapeHtml(c.name)}</strong></td>
        <td>${escapeHtml(c.phone)}</td>
        <td>${formatMoney(c.totalBought || 0)}</td>
        <td><strong style="color:${c.debt > 0 ? 'var(--danger)' : 'var(--success)'};">${formatMoney(c.debt || 0)}</strong></td>
        <td>${c.debt > 0 ? '<span class="badge badge-warning">Qarzdor</span>' : '<span class="badge badge-success">Toza</span>'}</td>
        <td style="display:flex; gap:4px;">
          ${c.debt > 0 ? `<button class="btn-primary" style="padding:4px 8px; font-size:11px;" onclick="openPayDebtModal('${c.id}')"><i class="fa-solid fa-hand-holding-dollar"></i> Qarz Yopish</button>` : ''}
          <button class="btn-secondary" style="padding:4px 8px; font-size:11px;" onclick="deleteCustomer('${c.id}')"><i class="fa-solid fa-trash"></i></button>
        </td>
      </tr>
    `).join('');
  }
  else if (state.currentExplorerSubTab === 'expenses') {
    head.innerHTML = `
      <tr>
        <th>ID</th>
        <th>Sana</th>
        <th>Toifa</th>
        <th>Izoh</th>
        <th>Summa</th>
        <th>Amal</th>
      </tr>
    `;

    let filtered = currentBusinessRecords(state.expenses).filter(e => e.note.toLowerCase().includes(search) || e.category.toLowerCase().includes(search));
    body.innerHTML = filtered.map(e => `
      <tr>
        <td><code>${e.id}</code></td>
        <td>${e.date}</td>
        <td><span class="badge badge-warning">${escapeHtml(e.category)}</span></td>
        <td>${escapeHtml(e.note)}</td>
        <td><strong style="color:var(--danger);">${formatMoney(e.amount)}</strong></td>
        <td>
          <button class="btn-secondary" style="padding:4px 8px; font-size:11px;" onclick="deleteExpense('${e.id}')"><i class="fa-solid fa-trash"></i></button>
        </td>
      </tr>
    `).join('');
  }
  else if (state.currentExplorerSubTab === 'debts') {
    head.innerHTML = `
      <tr>
        <th>Sana / ID</th>
        <th>Ism / Ta'minotchi</th>
        <th>Yo'nalish</th>
        <th>Izoh / Turi</th>
        <th>Summa / Oltin</th>
        <th>Status</th>
        <th>Amal</th>
      </tr>
    `;

    const borrowedList = currentBusinessRecords(state.debtsBorrowed || []).map(b => ({
      id: b.id,
      date: b.date,
      name: b.lenderName,
      direction: 'borrowed',
      typeStr: b.type === 'gold' ? `💍 Oltin (${b.goldGrams}g 585 proba)` : '💵 Naqd / Tovar',
      note: b.note || '',
      amount: b.amount,
      status: b.status === 'active' ? 'Ochiq (Burch)' : 'Yopilgan',
      raw: b
    }));

    const lentList = currentBusinessRecords(state.customers).filter(c => (c.debt || 0) > 0).map(c => ({
      id: c.id,
      date: 'Nasiya',
      name: c.name,
      direction: 'lent',
      typeStr: `📱 ${c.phone}`,
      note: 'Mijoz Nasiya Qarzi',
      amount: c.debt,
      status: 'Ochiq (Nasiya)',
      raw: c
    }));

    let combined = [...borrowedList, ...lentList];
    if (search) {
      combined = combined.filter(d => d.name.toLowerCase().includes(search) || d.note.toLowerCase().includes(search) || d.id.toLowerCase().includes(search));
    }

    if (combined.length === 0) {
      body.innerHTML = '<tr><td colspan="7" style="text-align:center; color:var(--text-muted); padding:30px;">Qarzlar topilmadi</td></tr>';
    } else {
      body.innerHTML = combined.map(d => `
        <tr>
          <td><code>${d.id}</code><br><span style="font-size:10px; color:var(--text-muted);">${d.date}</span></td>
          <td><strong>${escapeHtml(d.name)}</strong></td>
          <td>
            ${d.direction === 'borrowed' ? 
              '<span class="badge badge-borrowed"><i class="fa-solid fa-arrow-down"></i> Qarz Oldim</span>' : 
              '<span class="badge badge-lent"><i class="fa-solid fa-arrow-up"></i> Qarz Berdim</span>'}
          </td>
          <td>${escapeHtml(d.typeStr)} ${d.note ? `<br><span style="font-size:11px; color:var(--text-muted);">${escapeHtml(d.note)}</span>` : ''}</td>
          <td><strong style="color:${d.direction === 'borrowed' ? 'var(--danger)' : 'var(--success)'};">${formatMoney(d.amount)}</strong></td>
          <td><span class="badge ${d.status.includes('Ochiq') ? 'badge-warning' : 'badge-success'}">${d.status}</span></td>
          <td>
            ${d.direction === 'borrowed' && d.raw.status === 'active' ? 
              `<button class="btn-primary" style="padding:4px 8px; font-size:11px;" onclick="openRepayBorrowedDebtModal('${d.id}')"><i class="fa-solid fa-money-bill-transfer"></i> Qaytirish</button>` : ''}
            ${d.direction === 'lent' ? 
              `<button class="btn-primary" style="padding:4px 8px; font-size:11px;" onclick="openPayDebtModal('${d.id}')"><i class="fa-solid fa-hand-holding-dollar"></i> Qarz Yopish</button>` : ''}
            ${d.direction === 'borrowed' ? 
              `<button class="btn-secondary" style="padding:4px 8px; font-size:11px;" onclick="deleteBorrowedDebt('${d.id}')"><i class="fa-solid fa-trash"></i></button>` : ''}
          </td>
        </tr>
      `).join('');
    }
  }
}

function updateExplorerStatsCards() {
  const sub = state.currentExplorerSubTab;
  const card1Label = document.getElementById('expCard1Label');
  const card1Value = document.getElementById('expCard1Value');
  const card1Sub = document.getElementById('expCard1Sub');

  const card2Label = document.getElementById('expCard2Label');
  const card2Value = document.getElementById('expCard2Value');
  const card2Sub = document.getElementById('expCard2Sub');

  const card3Label = document.getElementById('expCard3Label');
  const card3Value = document.getElementById('expCard3Value');
  const card3Sub = document.getElementById('expCard3Sub');

  if (!card1Label) return;

  if (sub === 'products') {
    const activeProducts = state.products.filter(p => p.profile === state.currentProfile || p.profile === 'all' || state.currentProfile === 'custom');
    const totalVal = activeProducts.reduce((sum, p) => sum + (p.costPrice * p.stock), 0);
    const lowStock = activeProducts.filter(p => p.stock <= 5).length;

    card1Label.innerText = "Jami Mahsulotlar";
    card1Value.innerText = `${activeProducts.length} xil`;
    card1Sub.innerText = `${state.currentProfile.toUpperCase()} profilida`;

    card2Label.innerText = "Ombor Tan Narx Qiymati";
    card2Value.innerText = formatMoney(totalVal);
    card2Sub.innerText = "Zaxira hisobi";

    card3Label.innerText = "Kam Qolgan Zaxira";
    card3Value.innerText = `${lowStock} ta item`;
    card3Value.style.color = lowStock > 0 ? "var(--warning)" : "var(--success)";
    card3Sub.innerText = lowStock > 0 ? "To'ldirish kerak" : "Zaxira yetarli";
  } else if (sub === 'purchases') {
    const activePurchases = (state.purchases || []).filter(p => p.profile === state.currentProfile || p.profile === 'retail');
    const totalCost = activePurchases.reduce((sum, p) => sum + (p.totalCostUZS || (p.costUZS * p.qty)), 0);
    const totalQty = activePurchases.reduce((sum, p) => sum + p.qty, 0);

    card1Label.innerText = "Jami Kirimlar";
    card1Value.innerText = `${activePurchases.length} ta xarid`;
    card1Sub.innerText = "Ombor kirim jurnali";

    card2Label.innerText = "Jami Kirim Summasi";
    card2Value.innerText = formatMoney(totalCost);
    card2Sub.innerText = "Xaridlar qiymati";

    card3Label.innerText = "Jami Kirim Hajmi";
    card3Value.innerText = `${totalQty} dona/birlik`;
    card3Value.style.color = "var(--success)";
    card3Sub.innerText = "Omborga tushgan";
  } else if (sub === 'sales') {
    const businessSales = currentBusinessRecords(state.sales);
    const totalRev = businessSales.reduce((sum, s) => sum + s.totalAmount, 0);
    const totalProfit = businessSales.reduce((sum, s) => sum + s.profit, 0);

    card1Label.innerText = "Jami Sotuv Tranzaksiyalari";
    card1Value.innerText = `${businessSales.length} ta chek`;
    card1Sub.innerText = "Barcha vaqtlar bo'yicha";

    card2Label.innerText = "Jami Sotuv Tushumi";
    card2Value.innerText = formatMoney(totalRev);
    card2Sub.innerText = "Brutto tushum";

    card3Label.innerText = "Jami Sof Foyda";
    card3Value.innerText = formatMoney(totalProfit);
    card3Value.style.color = "var(--success)";
    card3Sub.innerText = "Marginal foyda";
  } else if (sub === 'customers') {
    const businessCustomers = currentBusinessRecords(state.customers);
    const totalDebt = businessCustomers.reduce((sum, c) => sum + (c.debt || 0), 0);
    const debtors = businessCustomers.filter(c => c.debt > 0).length;

    card1Label.innerText = "Baza Mijozlari";
    card1Value.innerText = `${businessCustomers.length} nafar`;
    card1Sub.innerText = "Ro'yxatdan o'tgan";

    card2Label.innerText = "Jami Nasiya Qarzlar";
    card2Value.innerText = formatMoney(totalDebt);
    card2Sub.innerText = "Mijozlar qarzi";

    card3Label.innerText = "Qarzdor Mijozlar";
    card3Value.innerText = `${debtors} nafar`;
    card3Value.style.color = debtors > 0 ? "var(--danger)" : "var(--success)";
    card3Sub.innerText = debtors > 0 ? "Murojaat qilish zarur" : "Qarzlar yo'q";
  } else if (sub === 'expenses') {
    const businessExpenses = currentBusinessRecords(state.expenses);
    const totalExp = businessExpenses.reduce((sum, e) => sum + e.amount, 0);

    card1Label.innerText = "Xarajatlar Yozuvlari";
    card1Value.innerText = `${businessExpenses.length} ta yozuv`;
    card1Sub.innerText = "Chiqimlar jurnali";

    card2Label.innerText = "Jami Operatsion Chiqim";
    card2Value.innerText = formatMoney(totalExp);
    card2Sub.innerText = "Barcha xarajatlar";

    card3Label.innerText = "Eng Katta Chiqim";
    const maxExp = businessExpenses.length > 0 ? Math.max(...businessExpenses.map(e => e.amount)) : 0;
    card3Value.innerText = formatMoney(maxExp);
    card3Value.style.color = "var(--danger)";
    card3Sub.innerText = "Maksimal bir martalik";
  } else if (sub === 'debts') {
    const businessBorrowed = currentBusinessRecords(state.debtsBorrowed || []).filter(d => d.status === 'active');
    const businessLent = currentBusinessRecords(state.customers).filter(c => (c.debt || 0) > 0);
    const totalBorrowed = businessBorrowed.reduce((sum, d) => sum + (d.amount || 0), 0);
    const totalLent = businessLent.reduce((sum, c) => sum + (c.debt || 0), 0);

    card1Label.innerText = "Olingan Qarzlar (Burch)";
    card1Value.innerText = formatMoney(totalBorrowed);
    card1Value.style.color = "var(--danger)";
    card1Sub.innerText = `${businessBorrowed.length} ta active olingan qarz`;

    card2Label.innerText = "Berilgan Qarzlar (Nasiya)";
    card2Value.innerText = formatMoney(totalLent);
    card2Value.style.color = "var(--success)";
    card2Sub.innerText = `${businessLent.length} nafar mijoz qarzi`;

    card3Label.innerText = "Sof Qarz Balansi";
    const netDebtBalance = totalLent - totalBorrowed;
    card3Value.innerText = formatMoney(Math.abs(netDebtBalance));
    card3Value.style.color = netDebtBalance >= 0 ? "var(--success)" : "var(--danger)";
    card3Sub.innerText = netDebtBalance >= 0 ? "Foydali balans (Nasiya ko'p)" : "Diqqat! Olingan qarz ko'p";
  }
}

/* Borrowed & Lent Debt Action Handlers */
function openAddBorrowedDebtModal() {
  openModal('addBorrowedDebtModal');
}

function toggleBorrowInputs() {
  const type = document.getElementById('borrowType').value;
  const goldGrp = document.getElementById('borrowGoldGroup');
  if (goldGrp) goldGrp.style.display = type === 'gold' ? 'block' : 'none';
}

function saveBorrowedDebt() {
  const lenderName = document.getElementById('borrowLenderName').value.trim();
  const type = document.getElementById('borrowType').value;
  let amount = parseFloat(document.getElementById('borrowAmount').value) || 0;
  const goldGrams = parseFloat(document.getElementById('borrowGoldGrams').value) || 0;
  const dueDate = document.getElementById('borrowDueDate').value;
  const note = document.getElementById('borrowNote').value.trim();

  if (!lenderName) {
    alert("Iltimos, qarz beruvchi (ta'minotchi / sherik) ismini kiriting!");
    return;
  }

  if (type === 'gold' && goldGrams > 0 && amount === 0) {
    amount = goldGrams * ((state.rules && state.rules.goldGramPriceUZS) ? state.rules.goldGramPriceUZS : 950000);
  }

  if (amount <= 0) {
    alert("Iltimos, to'g'ri qarz summasi yoki oltin grammini kiriting!");
    return;
  }

  const record = {
    id: 'BRW-' + Math.floor(100 + Math.random() * 900),
    profile: state.currentProfile,
    date: new Date().toISOString().split('T')[0],
    lenderName: lenderName,
    type: type,
    amount: amount,
    goldGrams: goldGrams,
    status: 'active',
    dueDate: dueDate,
    note: note || (type === 'gold' ? `${goldGrams}g oltin qarz olindi` : 'Olingan qarz')
  };

  if (!state.debtsBorrowed) state.debtsBorrowed = [];
  state.debtsBorrowed.unshift(record);
  saveStateToStorage();
  syncDebtsToMarkdown(false);
  closeModal('addBorrowedDebtModal');
  renderCurrentTab();
  alert("Olingan qarz muvaffaqiyatli saqlandi!");
}

function openAddLentDebtModal() {
  openModal('addLentDebtModal');
}

function saveLentDebt() {
  const name = document.getElementById('lentCustomerName').value.trim();
  const phone = document.getElementById('lentCustomerPhone').value.trim() || '+998 90 000 00 00';
  const amount = parseFloat(document.getElementById('lentAmount').value) || 0;
  const note = document.getElementById('lentNote').value.trim();

  if (!name || amount <= 0) {
    alert("Iltimos, mijoz nomi va berilgan qarz summasini kiriting!");
    return;
  }

  let cust = state.customers.find(c => c.name.toLowerCase() === name.toLowerCase() && (c.profile || 'retail') === state.currentProfile);
  if (!cust) {
    cust = {
      id: 'C' + Math.floor(100 + Math.random() * 900),
      profile: state.currentProfile,
      name: name,
      phone: phone,
      debt: amount,
      totalBought: amount
    };
    state.customers.unshift(cust);
  } else {
    cust.debt = (cust.debt || 0) + amount;
    cust.totalBought = (cust.totalBought || 0) + amount;
  }

  state.sales.unshift({
    id: 'LEND-' + Math.floor(1000 + Math.random() * 9000),
    date: new Date().toISOString().split('T')[0],
    customerId: cust.id,
    customerName: `${cust.name} (Qarz Berildi)`,
    totalAmount: amount,
    profit: 0,
    payMethod: 'debt',
    profile: state.currentProfile,
    items: [{ name: note || "Berilgan Qarz / Nasiya", qty: 1, price: amount }]
  });

  saveStateToStorage();
  syncDebtsToMarkdown(false);
  closeModal('addLentDebtModal');
  populateCustomerDropdown();
  renderCurrentTab();
  alert("Berilgan qarz muvaffaqiyatli saqlandi!");
}

function openRepayBorrowedDebtModal(debtId) {
  const record = (state.debtsBorrowed || []).find(d => d.id === debtId);
  if (!record) return;

  document.getElementById('repayDebtId').value = record.id;
  document.getElementById('repayLenderName').value = record.lenderName;
  document.getElementById('repayCurrentAmount').value = formatMoney(record.amount);
  document.getElementById('repayAmountInput').value = record.amount;
  openModal('repayBorrowedDebtModal');
}

function processRepayBorrowedDebt() {
  const debtId = document.getElementById('repayDebtId').value;
  const payAmt = parseFloat(document.getElementById('repayAmountInput').value) || 0;
  const record = (state.debtsBorrowed || []).find(d => d.id === debtId);

  if (!record || payAmt <= 0) {
    alert("Iltimos, to'g'ri to'lov summasini kiriting!");
    return;
  }

  record.amount = Math.max(0, record.amount - payAmt);
  if (record.amount === 0) {
    record.status = 'paid';
  }

  state.expenses.unshift({
    id: 'EXP-BRW-' + Math.floor(100 + Math.random() * 900),
    profile: state.currentProfile,
    date: new Date().toISOString().split('T')[0],
    category: 'Qarz Qaytirish',
    amount: payAmt,
    note: `${record.lenderName} ga olingan qarz qaytarildi`
  });

  saveStateToStorage();
  syncDebtsToMarkdown(false);
  closeModal('repayBorrowedDebtModal');
  renderCurrentTab();
  alert("Olingan qarz qaytarilishi saqlandi!");
}

function deleteBorrowedDebt(id) {
  if (confirm("Ushbu olingan qarz yozuvini o'chirmoqchimisiz?")) {
    state.debtsBorrowed = (state.debtsBorrowed || []).filter(d => d.id !== id);
    saveStateToStorage();
    syncDebtsToMarkdown(false);
    renderCurrentTab();
  }
}

function deleteProduct(id) {
  if (confirm('Rostdan ham ushbu mahsulotni bazadan o\'chirmoqchimisiz?')) {
    state.products = state.products.filter(p => p.id !== id);
    saveStateToStorage();
    renderExplorerTable();
  }
}

function openAddDataModal() {
  if (state.currentExplorerSubTab === 'products') openAddProductModal();
  else if (state.currentExplorerSubTab === 'purchases') openPurchaseModal();
  else if (state.currentExplorerSubTab === 'customers') openAddCustomerModal();
  else if (state.currentExplorerSubTab === 'expenses') openAddExpenseModal();
  else alert('Sotuvlar amali Kassa Sotuv tabida avtomatik shakllanadi.');
}

function openAddCustomerModal() {
  openModal('addCustomerModal');
}

function saveNewCustomer() {
  const name = document.getElementById('newCName').value.trim();
  const phone = document.getElementById('newCPhone').value.trim() || '+998 90 000 00 00';
  const debt = parseFloat(document.getElementById('newCDebt').value) || 0;

  if (!name) {
    alert('Iltimos, mijoz F.I.SH kiriting!');
    return;
  }

  const newCust = {
    id: 'C' + Math.floor(100 + Math.random() * 900),
    profile: state.currentProfile,
    name: name,
    phone: phone,
    debt: debt,
    totalBought: debt
  };

  state.customers.unshift(newCust);
  saveStateToStorage();
  closeModal('addCustomerModal');
  populateCustomerDropdown();
  renderCurrentTab();
}

function openPayDebtModal(customerId) {
  const c = state.customers.find(item => item.id === customerId);
  if (!c) return;

  document.getElementById('payDebtCustomerId').value = c.id;
  document.getElementById('payDebtCustomerName').value = c.name;
  document.getElementById('payDebtCurrentAmount').value = formatMoney(c.debt || 0);
  document.getElementById('payDebtAmountInput').value = c.debt || 0;

  openModal('payDebtModal');
}

function processDebtPayment() {
  const custId = document.getElementById('payDebtCustomerId').value;
  const payAmt = parseFloat(document.getElementById('payDebtAmountInput').value) || 0;
  const c = state.customers.find(item => item.id === custId);

  if (!c || payAmt <= 0) {
    alert('Iltimos, to\'g\'ri to\'lov summasini kiriting!');
    return;
  }

  c.debt = Math.max(0, (c.debt || 0) - payAmt);

  // Record income entry in sales as debt repayment
  state.sales.unshift({
    id: 'REPAY-' + Math.floor(1000 + Math.random() * 9000),
    date: new Date().toISOString().split('T')[0],
    customerId: c.id,
    customerName: `${c.name} (Qarz to'lovi)`,
    totalAmount: payAmt,
    profit: payAmt,
    payMethod: 'cash',
    profile: state.currentProfile,
    items: [{ name: "Nasiya Qarzini Yopish", qty: 1, price: payAmt }]
  });

  saveStateToStorage();
  syncDebtsToMarkdown(false);
  closeModal('payDebtModal');
  renderCurrentTab();
}

function deleteCustomer(id) {
  if (confirm('Mijozni o\'chirmoqchimisiz?')) {
    state.customers = state.customers.filter(c => c.id !== id);
    saveStateToStorage();
    populateCustomerDropdown();
    renderExplorerTable();
  }
}

function deleteExpense(id) {
  if (confirm('Xarajat yozuvini o\'chirmoqchimisiz?')) {
    state.expenses = state.expenses.filter(e => e.id !== id);
    saveStateToStorage();
    renderCurrentTab();
  }
}

function reprintReceipt(saleId) {
  const sale = state.sales.find(s => s.id === saleId);
  if (!sale) return;

  document.getElementById('rcptShopName').innerText = `MUHASIB - ${sale.profile ? sale.profile.toUpperCase() : 'POS'}`;
  document.getElementById('rcptDate').innerText = `Sana: ${sale.date}`;
  document.getElementById('rcptId').innerText = `Chek №: ${sale.id}`;
  document.getElementById('rcptTotal').innerText = formatMoney(sale.totalAmount);
  document.getElementById('rcptPayMethod').innerText = sale.payMethod.toUpperCase();

  const rcptBody = document.getElementById('rcptItemsBody');
  const items = sale.items || [{ name: "Tranzaksiya", qty: 1, price: sale.totalAmount }];
  rcptBody.innerHTML = items.map(item => `
    <tr>
      <td>${escapeHtml(item.name)}</td>
      <td style="text-align:center;">${item.qty || 1}</td>
      <td style="text-align:right;">${formatMoney((item.price || sale.totalAmount) * (item.qty || 1))}</td>
    </tr>
  `).join('');

  openModal('receiptModal');
}

/* Baza Import */
function openImportModal() {
  openModal('importModal');
}

function handleFileImport(event) {
  const file = event.target.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = function(e) {
    try {
      const parsed = JSON.parse(e.target.result);
      applyImportedData(parsed);
    } catch (err) {
      alert("JSON faylini o'qishda xatolik yuz berdi: " + err.message);
    }
  };
  reader.readAsText(file);
}

function submitJsonTextImport() {
  const txt = document.getElementById('importJsonText').value.trim();
  if (!txt) {
    alert("Iltimos, JSON matnini kiriting yoki fayl tanlang!");
    return;
  }
  try {
    const parsed = JSON.parse(txt);
    applyImportedData(parsed);
  } catch (err) {
    alert("JSON formati noto'g'ri: " + err.message);
  }
}

function applyImportedData(parsed) {
  if (parsed.products) state.products = parsed.products;
  if (parsed.sales) state.sales = parsed.sales;
  if (parsed.customers) state.customers = parsed.customers;
  if (parsed.expenses) state.expenses = parsed.expenses;
  if (parsed.currentProfile) state.currentProfile = parsed.currentProfile;

  saveStateToStorage();
  closeModal('importModal');
  populateCustomerDropdown();
  updateUIHeader();
  renderCurrentTab();
  alert("Ma'lumotlar bazasi muvaffaqiyatli import qilindi va yangilandi!");
}

/* CSV Export */
function exportCurrentTableCSV() {
  let csvContent = "data:text/csv;charset=utf-8,";
  const sub = state.currentExplorerSubTab;

  if (sub === 'products') {
    csvContent += "ID,Code,Name,Category,CostPrice,Price,Stock\n";
    state.products.filter(p => p.profile === state.currentProfile || p.profile === 'all').forEach(p => {
      csvContent += `${p.id},"${p.code}","${p.name}","${p.category}",${p.costPrice},${p.price},${p.stock}\n`;
    });
  } else if (sub === 'sales') {
    csvContent += "ID,Date,Customer,TotalAmount,Profit,PayMethod\n";
    currentBusinessRecords(state.sales).forEach(s => {
      csvContent += `${s.id},${s.date},"${s.customerName}",${s.totalAmount},${s.profit},${s.payMethod}\n`;
    });
  } else if (sub === 'customers') {
    csvContent += "ID,Name,Phone,TotalBought,Debt\n";
    currentBusinessRecords(state.customers).forEach(c => {
      csvContent += `${c.id},"${c.name}","${c.phone}",${c.totalBought || 0},${c.debt || 0}\n`;
    });
  } else if (sub === 'expenses') {
    csvContent += "ID,Date,Category,Note,Amount\n";
    currentBusinessRecords(state.expenses).forEach(e => {
      csvContent += `${e.id},${e.date},"${e.category}","${e.note}",${e.amount}\n`;
    });
  }

  const encodedUri = encodeURI(csvContent);
  const link = document.createElement("a");
  link.setAttribute("href", encodedUri);
  link.setAttribute("download", `muhasib_${sub}_baza.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

/* ==========================================================================
   4. POS Helpers
   ========================================================================== */

/* ==========================================================================
   Modals & Helpers
   ========================================================================== */

function openModal(id) {
  document.getElementById(id).classList.add('active');
}

function closeModal(id) {
  document.getElementById(id).classList.remove('active');
}

function openAddProductModal() {
  openModal('addProductModal');
}

function openAddExpenseModal() {
  openModal('addExpenseModal');
}

function saveNewProduct() {
  const name = document.getElementById('newPName').value.trim();
  const code = document.getElementById('newPCode').value.trim() || 'BC-' + Math.floor(Math.random() * 1000000);
  const category = document.getElementById('newPCategory').value.trim() || 'Umumiy';
  const cost = parseFloat(document.getElementById('newPCost').value) || 0;
  const price = parseFloat(document.getElementById('newPPrice').value) || 0;
  const stock = parseInt(document.getElementById('newPStock').value) || 0;
  const gross = parseFloat(document.getElementById('newPGrossWeight').value) || 0;
  const proba = parseInt(document.getElementById('newPProba').value) || ((state.rules && state.rules.goldProba) ? state.rules.goldProba : 585);

  if (!name || price <= 0) {
    alert('Iltimos, tovar nomi va sotish narxini to\'g\'ri kiriting!');
    return;
  }

  const newProd = {
    id: 'P' + Math.floor(1000 + Math.random() * 9000),
    profile: state.currentProfile,
    code: code,
    name: name,
    category: category,
    costPrice: cost,
    price: price,
    stock: stock,
    unit: gross > 0 ? 'dona (gramm)' : 'dona',
    grossWeight: gross,
    proba: proba,
    pureWeight: gross > 0 ? (gross * proba / 1000) : 0
  };

  state.products.unshift(newProd);
  saveStateToStorage();
  closeModal('addProductModal');
  renderCurrentTab();
}

function saveExpense() {
  const category = document.getElementById('expCategory').value;
  const amount = parseFloat(document.getElementById('expAmount').value) || 0;
  const note = document.getElementById('expNote').value.trim();

  if (amount <= 0) {
    alert('Iltimos, xarajat summasini kiriting!');
    return;
  }

  const newExp = {
    id: 'E' + Math.floor(100 + Math.random() * 900),
    profile: state.currentProfile,
    date: new Date().toISOString().split('T')[0],
    category: category,
    amount: amount,
    note: note
  };

  state.expenses.unshift(newExp);
  saveStateToStorage();
  closeModal('addExpenseModal');
  renderCurrentTab();
}

function loadDemoData() {
  seedInitialDemoData();
  alert('Demo ma\'lumotlar bazaga muvaffaqiyatli yuklandi!');
  renderCurrentTab();
}

function resetDatabase() {
  if (confirm('DIQQAT: Barcha mahsulotlar, sotuvlar va mijozlar ma\'lumotlari tozalansinmi?')) {
    localStorage.removeItem('muhasib_state_v3');
    state.products = [];
    state.sales = [];
    state.customers = [];
    state.expenses = [];
    renderCurrentTab();
  }
}

function exportDatabaseJSON() {
  const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(state));
  const downloadAnchor = document.createElement('a');
  downloadAnchor.setAttribute("href", dataStr);
  downloadAnchor.setAttribute("download", `muhasib_full_baza_${new Date().toISOString().split('T')[0]}.json`);
  document.body.appendChild(downloadAnchor);
  downloadAnchor.click();
  downloadAnchor.remove();
}

/* Money Formatter */
function formatMoney(amount) {
  return new Intl.NumberFormat('uz-UZ').format(amount || 0) + ' UZS';
}

function escapeHtml(str) {
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

/* ==========================================================================
   Qarzim Bormi? — Qarz Auditi, Hisob-Kitobi va QARZLAR.md Integratsiyasi
   ========================================================================== */

function openCheckDebtModal() {
  renderDebtCheckSummary();
  openModal('checkDebtModal');
  syncDebtsToMarkdown(false);
}

function renderDebtCheckSummary() {
  const activeBorrowed = currentBusinessRecords(state.debtsBorrowed || []).filter(d => d.status === 'active');
  const activeLent = currentBusinessRecords(state.customers).filter(c => (c.debt || 0) > 0);
  
  const totalBorrowed = activeBorrowed.reduce((sum, d) => sum + (d.amount || 0), 0);
  const totalLent = activeLent.reduce((sum, c) => sum + (c.debt || 0), 0);
  
  const goldGramPrice = (state.rules && state.rules.goldGramPriceUZS) ? state.rules.goldGramPriceUZS : 950000;
  const proba = (state.rules && state.rules.goldProba) ? state.rules.goldProba : 585;

  const totalGoldGrams = activeBorrowed
    .filter(d => d.type === 'gold')
    .reduce((sum, d) => sum + (d.goldGrams || 0), 0);

  const netBalance = totalLent - totalBorrowed;

  // Banner Update
  const banner = document.getElementById('debtStatusAlertBanner');
  const icon = document.getElementById('debtStatusIcon');
  const title = document.getElementById('debtStatusTitle');
  const detail = document.getElementById('debtStatusDetail');

  if (banner && title && detail) {
    if (netBalance < 0) {
      banner.style.background = "rgba(239, 68, 68, 0.12)";
      banner.style.borderColor = "rgba(239, 68, 68, 0.35)";
      if (icon) {
        icon.className = "fa-solid fa-triangle-exclamation";
        icon.style.color = "var(--danger)";
      }
      title.innerHTML = `⚠️ Diqqat! Sizda <strong>${formatMoney(Math.abs(netBalance))}</strong> sof burchingiz bor!`;
      detail.innerText = `Olingan qarzlar (${formatMoney(totalBorrowed)}) mijozlar nasiyasidan (${formatMoney(totalLent)}) ko'proq. Qarz qaytarish va monitoring zarur.`;
    } else if (netBalance > 0) {
      banner.style.background = "rgba(16, 185, 129, 0.12)";
      banner.style.borderColor = "rgba(16, 185, 129, 0.35)";
      if (icon) {
        icon.className = "fa-solid fa-circle-check";
        icon.style.color = "var(--success)";
      }
      title.innerHTML = `✅ Sizda net burch yo'q! Nasiyalar <strong>${formatMoney(netBalance)}</strong> ko'proq!`;
      detail.innerText = `Mijozlar nasiyasi (${formatMoney(totalLent)}) olingan burchingizdan (${formatMoney(totalBorrowed)}) yuqori. Moliyaviy balans barqaror.`;
    } else {
      banner.style.background = "rgba(99, 102, 241, 0.12)";
      banner.style.borderColor = "rgba(99, 102, 241, 0.35)";
      if (icon) {
        icon.className = "fa-solid fa-scale-balanced";
        icon.style.color = "var(--primary)";
      }
      title.innerText = "⚖️ Qarzlar Balansi Teng / Qarz Yo'q";
      detail.innerText = "Tizimda active olingan qarzlar va mijozlar nasiyalari teng yoki mavjud emas.";
    }
  }

  // Cards update
  const borrowedTotalEl = document.getElementById('debtModalBorrowedTotal');
  const goldInfoEl = document.getElementById('debtModalGoldInfo');
  const lendersCountEl = document.getElementById('debtModalLendersCount');

  const lentTotalEl = document.getElementById('debtModalLentTotal');
  const debtorsCountEl = document.getElementById('debtModalDebtorsCount');

  if (borrowedTotalEl) borrowedTotalEl.innerText = formatMoney(totalBorrowed);
  if (goldInfoEl) {
    goldInfoEl.innerText = `💍 ${totalGoldGrams}g (${proba} proba oltin rule: ~${formatMoney(totalGoldGrams * goldGramPrice)})`;
  }
  if (lendersCountEl) lendersCountEl.innerText = `${activeBorrowed.length} ta active olingan qarz`;

  if (lentTotalEl) lentTotalEl.innerText = formatMoney(totalLent);
  if (debtorsCountEl) debtorsCountEl.innerText = `${activeLent.length} nafar qarzdor mijoz`;

  // Table Body
  const tableBody = document.getElementById('debtModalTableBody');
  if (tableBody) {
    const borrowedRows = activeBorrowed.map(b => `
      <tr>
        <td><strong>${escapeHtml(b.lenderName)}</strong><br><span style="font-size:10px; color:var(--text-muted);">${b.date}</span></td>
        <td><span class="badge badge-borrowed"><i class="fa-solid fa-arrow-down"></i> Qarz Oldim</span></td>
        <td><strong style="color:var(--danger);">${formatMoney(b.amount)}</strong>${b.type === 'gold' ? `<br><span style="font-size:11px; color:var(--warning);">💍 ${b.goldGrams}g 585 proba</span>` : ''}</td>
        <td><span class="badge badge-warning">Ochiq Burch</span></td>
        <td>
          <button class="btn-primary" style="padding:3px 8px; font-size:11px;" onclick="openRepayBorrowedDebtModal('${b.id}'); closeModal('checkDebtModal');"><i class="fa-solid fa-money-bill-transfer"></i> Qaytirish</button>
        </td>
      </tr>
    `);

    const lentRows = activeLent.map(c => `
      <tr>
        <td><strong>${escapeHtml(c.name)}</strong><br><span style="font-size:10px; color:var(--text-muted);">${c.phone}</span></td>
        <td><span class="badge badge-lent"><i class="fa-solid fa-arrow-up"></i> Qarz Berdim</span></td>
        <td><strong style="color:var(--success);">${formatMoney(c.debt)}</strong></td>
        <td><span class="badge badge-warning">Ochiq Nasiya</span></td>
        <td>
          <button class="btn-primary" style="padding:3px 8px; font-size:11px;" onclick="openPayDebtModal('${c.id}'); closeModal('checkDebtModal');"><i class="fa-solid fa-hand-holding-dollar"></i> Yopish</button>
        </td>
      </tr>
    `);

    const combinedRows = [...borrowedRows, ...lentRows];
    if (combinedRows.length === 0) {
      tableBody.innerHTML = '<tr><td colspan="5" style="text-align:center; color:var(--text-muted); padding:20px;">Hozirda active qarz yozuvlari yo\'q (Barcha qarzlar toza)</td></tr>';
    } else {
      tableBody.innerHTML = combinedRows.join('');
    }
  }
}

function syncDebtsToMarkdown(userAlert = false) {
  const activeBorrowed = currentBusinessRecords(state.debtsBorrowed || []).filter(d => d.status === 'active');
  const activeLent = currentBusinessRecords(state.customers).filter(c => (c.debt || 0) > 0);
  
  const totalBorrowed = activeBorrowed.reduce((sum, d) => sum + (d.amount || 0), 0);
  const totalLent = activeLent.reduce((sum, c) => sum + (c.debt || 0), 0);
  
  const totalGoldGrams = activeBorrowed
    .filter(d => d.type === 'gold')
    .reduce((sum, d) => sum + (d.goldGrams || 0), 0);

  const netBalance = totalLent - totalBorrowed;
  let netStatusStr = "Toza balans";
  if (netBalance > 0) netStatusStr = "Foydali (Nasiya ko'p)";
  else if (netBalance < 0) netStatusStr = "Diqqat (Burchimiz ko'p)";

  const debtsPayload = [];

  (state.debtsBorrowed || []).forEach(d => {
    debtsPayload.push({
      date: d.date || '-',
      person: d.lenderName || '-',
      amount: formatMoney(d.amount),
      type: d.type === 'gold' ? `Oltin (${d.goldGrams}g 585 proba)` : 'Olingan Qarz (Burch)',
      note: d.note || '',
      status: d.status === 'active' ? 'Ochiq (Burch)' : 'Yopilgan'
    });
  });

  (state.customers || []).filter(c => (c.debt || 0) > 0).forEach(c => {
    debtsPayload.push({
      date: 'Nasiya',
      person: c.name || '-',
      amount: formatMoney(c.debt),
      type: 'Berilgan Qarz (Mijoz Nasiyasi)',
      note: `Tel: ${c.phone}`,
      status: 'Ochiq (Nasiya)'
    });
  });

  const payload = {
    summary: {
      borrowedTotalStr: formatMoney(totalBorrowed),
      goldGramsStr: `${totalGoldGrams} gramm (585 proba)`,
      lentTotalStr: formatMoney(totalLent),
      netBalanceStr: formatMoney(Math.abs(netBalance)),
      netStatusStr: netStatusStr
    },
    debts: debtsPayload
  };

  fetch('/api/debts/sync', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  }).then(res => res.json()).then(data => {
    if (userAlert) {
      if (data.status === 'ok') {
        alert("Qarzlar holati va auditi QARZLAR.md fayliga saqlandi!");
      } else {
        alert("Saqlashda xatolik: " + (data.error || 'Noma\'lum xato'));
      }
    }
  }).catch(err => {
    console.error('Debts sync error:', err);
    if (userAlert) alert("Server bilan bog'lanishda xatolik ro'y berdi.");
  });
}

/* ==========================================================================
   Omborda Nima Bor? — Ombor Qoldiqlari & Auditi Integratsiyasi
   ========================================================================== */

function openCheckOmborModal() {
  renderOmborCheckSummary();
  openModal('checkOmborModal');
}

function renderOmborCheckSummary() {
  const currentProfileProducts = state.products.filter(p => p.profile === state.currentProfile || p.profile === 'all');
  const usdRate = (state.rules && state.rules.usdExchangeRate) ? state.rules.usdExchangeRate : 12800;

  const totalTypes = currentProfileProducts.length;
  const totalQty = currentProfileProducts.reduce((sum, p) => sum + (p.stock || 0), 0);
  const totalValueUZS = currentProfileProducts.reduce((sum, p) => sum + ((p.price || p.costPrice || 0) * (p.stock || 0)), 0);
  const totalValueUSD = Math.round(totalValueUZS / usdRate);

  const lowItems = currentProfileProducts.filter(p => (p.stock || 0) <= 5 && (p.stock || 0) > 0);
  const outOfStockItems = currentProfileProducts.filter(p => (p.stock || 0) === 0);

  // Jewelry calculations
  const totalGross = currentProfileProducts.reduce((sum, p) => sum + ((p.grossWeight || 0) * (p.stock || 0)), 0);
  const totalPure = currentProfileProducts.reduce((sum, p) => sum + ((p.pureWeight || ((p.grossWeight || 0) * 0.585)) * (p.stock || 0)), 0);

  // Update Header Banner
  const bannerTitle = document.getElementById('omborStatusTitle');
  const bannerDetail = document.getElementById('omborStatusDetail');
  if (bannerTitle && bannerDetail) {
    bannerTitle.innerHTML = `📦 Ombor Zaxirasi: <strong>${totalTypes} turdagi</strong> mahsulot, Jami <strong>${totalQty} dona/kg</strong> qoldiq`;
    let detailText = `Omborning umumiy sotish qiymati: ${formatMoney(totalValueUZS)} (~$${totalValueUSD.toLocaleString()} USD).`;
    if (state.currentProfile === 'jewelry' || totalGross > 0) {
      detailText += ` Tillalar: ${totalGross.toFixed(1)}g brutto (${totalPure.toFixed(1)}g 585 proba sof oltin).`;
    }
    if (lowItems.length > 0 || outOfStockItems.length > 0) {
      detailText += ` ⚠️ Ogohlantirish: ${lowItems.length} ta tovar oz qolgan, ${outOfStockItems.length} ta tovar tugagan!`;
    } else {
      detailText += ` ✅ Barcha tovarlar zaxirasi yetarli darajada!`;
    }
    bannerDetail.innerText = detailText;
  }

  // Update KPI Cards
  const typesEl = document.getElementById('omborModalItemTypesCount');
  const totalQtyEl = document.getElementById('omborModalTotalQty');
  const valUZSEl = document.getElementById('omborModalTotalValueUZS');
  const valUSDEl = document.getElementById('omborModalTotalValueUSD');
  const statusTextEl = document.getElementById('omborModalStockStatusText');
  const goldSubTextEl = document.getElementById('omborModalGoldSubText');

  if (typesEl) typesEl.innerText = `${totalTypes} turda`;
  if (totalQtyEl) totalQtyEl.innerText = `Jami qoldiq: ${totalQty} dona/kg`;
  if (valUZSEl) valUZSEl.innerText = formatMoney(totalValueUZS);
  if (valUSDEl) valUSDEl.innerText = `$${totalValueUSD.toLocaleString()} USD (1 USD = ${usdRate} UZS)`;

  if (statusTextEl) {
    if (outOfStockItems.length > 0) {
      statusTextEl.innerHTML = `<span style="color:var(--danger);">${outOfStockItems.length} ta tugagan</span>, ${lowItems.length} ta oz qoldi`;
    } else if (lowItems.length > 0) {
      statusTextEl.innerHTML = `<span style="color:var(--warning);">${lowItems.length} ta kam qoldi</span>`;
    } else {
      statusTextEl.innerHTML = `<span style="color:var(--success);">✅ Hamma tovar yetarli</span>`;
    }
  }

  if (goldSubTextEl) {
    if (totalGross > 0 || state.currentProfile === 'jewelry') {
      goldSubTextEl.innerText = `💍 ${totalGross.toFixed(1)}g tilla (${totalPure.toFixed(1)}g 585 proba ekvivalenti)`;
    } else {
      goldSubTextEl.innerText = `Ombor statusi a'lo darajada`;
    }
  }

  // Populate Categories Dropdown
  const catSelect = document.getElementById('omborModalCatFilter');
  if (catSelect) {
    const cats = Array.from(new Set(currentProfileProducts.map(p => p.category || 'Umumiy'))).sort();
    catSelect.innerHTML = '<option value="ALL">Barcha Kategoriyalar</option>' + cats.map(c => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join('');
  }

  // Render Table
  renderOmborModalTableRows(currentProfileProducts);
}

function filterOmborModalTable() {
  const currentProfileProducts = state.products.filter(p => p.profile === state.currentProfile || p.profile === 'all');
  const query = (document.getElementById('omborModalSearchInput')?.value || '').toLowerCase().trim();
  const selectedCat = document.getElementById('omborModalCatFilter')?.value || 'ALL';

  const filtered = currentProfileProducts.filter(p => {
    const matchesSearch = !query || p.name.toLowerCase().includes(query) || (p.code || '').toLowerCase().includes(query) || (p.category || '').toLowerCase().includes(query);
    const matchesCat = selectedCat === 'ALL' || (p.category || 'Umumiy') === selectedCat;
    return matchesSearch && matchesCat;
  });

  renderOmborModalTableRows(filtered);
}

function renderOmborModalTableRows(productsList) {
  const tableBody = document.getElementById('omborModalTableBody');
  if (!tableBody) return;

  if (productsList.length === 0) {
    tableBody.innerHTML = '<tr><td colspan="8" style="text-align:center; color:var(--text-muted); padding:20px;">Hech qanday mahsulot topilmadi.</td></tr>';
    return;
  }

  tableBody.innerHTML = productsList.map(p => {
    const stock = p.stock || 0;
    const price = p.price || 0;
    const totalVal = stock * price;
    let statusBadge = '<span class="badge badge-success">Yetarli</span>';
    if (stock === 0) statusBadge = '<span class="badge badge-danger">Tugagan</span>';
    else if (stock <= 5) statusBadge = '<span class="badge badge-warning">Kam qoldi</span>';

    return `
      <tr>
        <td><code>${escapeHtml(p.code || '-')}</code></td>
        <td><strong>${escapeHtml(p.name)}</strong></td>
        <td><span class="badge badge-secondary">${escapeHtml(p.category || 'Umumiy')}</span></td>
        <td><strong style="color:${stock <= 5 ? 'var(--warning)' : '#fff'};">${stock} ${escapeHtml(p.unit || 'dona')}</strong></td>
        <td>${formatMoney(price)}</td>
        <td><strong style="color:var(--success);">${formatMoney(totalVal)}</strong></td>
        <td>${statusBadge}</td>
        <td>
          <button class="btn-secondary" style="padding:3px 8px; font-size:11px;" onclick="quickAddStock('${p.id}'); renderOmborCheckSummary();">+10 Qoldiq</button>
        </td>
      </tr>
    `;
  }).join('');
}

function exportOmborExcel() {
  window.open('/api/excel/data?path=' + encodeURIComponent('mahsulotlar.xlsx'), '_blank');
}

