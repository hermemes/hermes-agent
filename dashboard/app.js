/* Hermemes Control Interface — All data is REAL */

const API_BASE = window.location.origin;
let autoRefresh = true;
let refreshTimer = null;
let commandHistory = [];
let historyIdx = -1;
let logEntries = [];

/* ─── Clock ─── */
function updateClock() {
  const now = new Date();
  document.getElementById('clock').textContent =
    [now.getHours(), now.getMinutes(), now.getSeconds()]
      .map(n => String(n).padStart(2, '0')).join(':');
}
setInterval(updateClock, 1000);
updateClock();

/* ─── API Helper ─── */
async function api(endpoint) {
  try {
    const res = await fetch(API_BASE + endpoint);
    const data = await res.json();
    addLog('INFO', `API ${endpoint} → ${res.status}`);
    return data;
  } catch (e) {
    addLog('ERROR', `API ${endpoint} failed: ${e.message}`);
    return null;
  }
}

/* ─── System Monitor (REAL) ─── */
async function fetchSystemStats() {
  const data = await api('/api/system');
  if (!data) return;

  const update = (id, val, unit = '%') => {
    document.getElementById(id + '-value').textContent = val + unit;
    const bar = document.getElementById(id + '-bar');
    if (bar) bar.style.width = parseFloat(val) + '%';
  };

  update('cpu', data.cpu_percent.toFixed(1));
  update('mem', Math.round(data.memory_percent));
  update('disk', Math.round(data.disk_percent));
  document.getElementById('uptime-value').textContent = data.uptime;
}

/* ─── BSC Chain Data (REAL from RPC + Binance API) ─── */
async function fetchChainData() {
  const data = await api('/api/chain');
  if (!data) return;

  document.getElementById('bsc-gas').textContent = data.gas_gwei != null ? data.gas_gwei + ' Gwei' : '—';
  document.getElementById('bsc-block').textContent = data.block ? '#' + Number(data.block).toLocaleString() : '—';
  document.getElementById('bnb-price').textContent = data.bnb_price ? '$' + Number(data.bnb_price).toFixed(2) : '—';
}

/* ─── Agent Status (REAL from config) ─── */
async function fetchStatus() {
  const data = await api('/api/status');
  if (!data) return;

  addLog('OK', `Agent: ${data.status} — ${data.tools_count} tools, model: ${data.model || '—'}, provider: ${data.provider || '—'}`);

  if (data.token_usage) {
    const u = data.token_usage;
    document.getElementById('total-tokens').textContent = (u.total || 0).toLocaleString();
    document.getElementById('io-tokens').textContent = `${(u.input || 0).toLocaleString()} / ${(u.output || 0).toLocaleString()}`;
    document.getElementById('api-calls').textContent = (u.api_calls || 0).toString();
    document.getElementById('sessions-count').textContent = (u.sessions || 0).toString();
  }
}

/* ─── Cron Jobs (REAL — scans cron/ directory) ─── */
async function fetchCronJobs() {
  const data = await api('/api/cron');
  const el = document.getElementById('cron-list');
  if (!data || !data.jobs || data.jobs.length === 0 || (data.jobs.length === 1 && data.jobs[0].name === 'none')) {
    el.innerHTML = '<div class="cron-empty">No scheduled jobs</div>';
    return;
  }
  el.innerHTML = data.jobs.map(j => `
    <div style="padding:4px 0;font-size:10px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between">
      <span>${j.name}</span>
      <span style="color:var(--text-dim)">${j.schedule}</span>
    </div>
  `).join('');
}

/* ─── KOL Pool (REAL — reads pool file) ─── */
async function fetchKolPool() {
  const data = await api('/api/kol/pool');
  if (!data) return;

  document.getElementById('pool-count').textContent = (data.total || 0) + ' wallets';
  document.getElementById('kol-a-plus').textContent = data.grades?.['A+'] || 0;
  document.getElementById('kol-a').textContent = data.grades?.['A'] || 0;
  document.getElementById('kol-b').textContent = data.grades?.['B'] || 0;
  document.getElementById('kol-alerts').textContent = data.alerts || 0;
  document.getElementById('kol-last-scan').textContent = 'Last scan: ' + (data.last_scan || 'never');
}

/* ─── Tool Usage (REAL — tracked from dashboard commands) ─── */
async function fetchToolUsage() {
  const data = await api('/api/tools/usage');
  if (!data || !data.tools) return;

  const el = document.getElementById('tool-rank-list');
  const max = Math.max(...data.tools.map(t => t.count), 1);

  el.innerHTML = data.tools.map(t => `
    <div class="tool-rank-item">
      <span class="tool-rank-name">${t.name}</span>
      <span class="tool-rank-bar"><span class="tr-fill" style="width:${t.count > 0 ? (t.count / max * 100).toFixed(0) : 0}%"></span></span>
      <span class="tool-rank-count">${t.count}</span>
    </div>
  `).join('');
}

/* ─── Agent List (REAL — scans config + cron directory) ─── */
async function fetchAgents() {
  const data = await api('/api/agents');
  const el = document.getElementById('agent-list');
  if (!data || !Array.isArray(data)) {
    el.innerHTML = '<div class="dim" style="font-size:10px;padding:4px">No agents detected</div>';
    return;
  }

  el.innerHTML = data.map((a, i) => {
    const isActive = a.status === 'active';
    const tagClass = isActive ? 'tag-active' : a.type === 'cron' ? 'tag-cron' : 'tag-idle';
    const tagText = isActive ? 'ACTIVE' : a.type === 'cron' ? 'CRON' : 'IDLE';
    const icon = isActive ? '◆' : '◇';
    return `
      <div class="agent-item ${isActive ? 'active' : ''}">
        <span class="agent-icon">${icon}</span>
        <span class="agent-label">${a.name}</span>
        <span class="agent-tag ${tagClass}">${tagText}</span>
      </div>`;
  }).join('');
}

/* ─── Recent Sessions (REAL — from actual API call history) ─── */
async function fetchSessions() {
  const data = await api('/api/sessions');
  const el = document.getElementById('session-list');
  if (!data || !data.sessions || data.sessions.length === 0) {
    el.innerHTML = '<div class="session-item dim">No sessions yet</div>';
    return;
  }
  el.innerHTML = data.sessions.map(s => `
    <div class="session-item">
      <span class="session-title">${s.title}</span>
      <span class="session-time">${s.time}</span>
    </div>
  `).join('');
}

/* ─── Information (REAL — checks actual env vars) ─── */
async function fetchEnvInfo() {
  const data = await api('/api/env');
  const el = document.getElementById('info-list');
  if (!data) { el.innerHTML = '<div class="dim">Failed to load</div>'; return; }

  const services = ['OpenRouter', 'BscScan', 'Telegram', 'GMGN', 'BSC RPC'];
  let html = '';

  for (const svc of services) {
    const raw = data[svc] || 'not configured';
    const isOk = raw.includes('configured');
    const val = isOk ? 'configured' : 'not configured';
    const dotClass = isOk ? 'green' : 'yellow';
    html += `<div class="info-row"><span class="info-dot ${dotClass}"></span> ${svc}: ${val}</div>`;
  }

  html += '<div class="info-sep"></div>';
  html += `<div class="info-row dim">Terminal: ${data.Terminal || 'LOCAL'}</div>`;
  html += `<div class="info-row dim">Platform: ${data.Platform || '—'}</div>`;
  html += `<div class="info-row dim">Agent: Hermemes</div>`;

  el.innerHTML = html;
}

/* ─── Logging (REAL — all entries come from actual API calls) ─── */
function addLog(level, message) {
  const now = new Date();
  const ts = [now.getHours(), now.getMinutes(), now.getSeconds()]
    .map(n => String(n).padStart(2, '0')).join(':');

  const cls = level === 'ERROR' ? 'error' : level === 'WARN' ? 'warn' : level === 'OK' ? 'ok' : 'info';
  logEntries.push({ ts, level, cls, message });
  if (logEntries.length > 200) logEntries.shift();
  renderLogs();
}

function renderLogs() {
  const body = document.getElementById('log-body');
  const filter = (document.getElementById('log-filter').value || '').toLowerCase();
  const filtered = filter
    ? logEntries.filter(l => l.message.toLowerCase().includes(filter))
    : logEntries;

  body.innerHTML = filtered.map(l => `
    <div class="log-line">
      <span class="log-ts">${l.ts}</span>
      <span class="log-level ${l.cls}">${l.level}</span>
      <span>${escapeHtml(l.message)}</span>
    </div>
  `).join('');
  body.scrollTop = body.scrollHeight;
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

/* ─── GMGN Trending (REAL from gmgn.ai) ─── */
async function fetchGmgnTrending() {
  const data = await api('/api/gmgn/trending');
  const el = document.getElementById('gmgn-trending');
  if (!el) return;
  if (!data || !data.tokens || data.tokens.length === 0) {
    el.innerHTML = '<div class="dim" style="padding:8px;font-size:10px">No trending data</div>';
    return;
  }
  el.innerHTML = data.tokens.slice(0, 12).map((t, i) => {
    const change = t.price_change_1h != null ? Number(t.price_change_1h) * 100 : 0;
    const changeColor = change >= 0 ? 'var(--green)' : 'var(--red)';
    const changeStr = (change >= 0 ? '+' : '') + change.toFixed(1) + '%';
    const price = t.price != null ? (Number(t.price) < 0.01 ? Number(t.price).toExponential(2) : '$' + Number(t.price).toFixed(4)) : '—';
    const sm = t.smart_money_count || 0;
    const kol = t.kol_count || 0;
    const logoHtml = t.logo ? `<img src="${t.logo}" width="14" height="14" style="border-radius:3px;flex-shrink:0" onerror="this.style.display='none'">` : '';
    return `<div class="gmgn-row">
      <span class="gmgn-rank">${i + 1}</span>
      ${logoHtml}
      <div class="gmgn-token-info">
        <span class="gmgn-token-name">${t.symbol || t.name}</span>
        <span class="gmgn-token-tags">${sm > 0 ? 'SM:' + sm : ''} ${kol > 0 ? 'KOL:' + kol : ''}</span>
      </div>
      <span class="gmgn-price">${price}</span>
      <span class="gmgn-change" style="color:${changeColor}">${changeStr}</span>
    </div>`;
  }).join('');
}

/* ─── GMGN Smart Money Trending (REAL) ─── */
async function fetchGmgnSmartMoney() {
  const data = await api('/api/gmgn/smart-money');
  const el = document.getElementById('gmgn-smart-money');
  if (!el) return;
  if (!data || !data.tokens || data.tokens.length === 0) {
    el.innerHTML = '<div class="dim" style="padding:8px;font-size:10px">No smart money data</div>';
    return;
  }
  el.innerHTML = data.tokens.slice(0, 10).map((t, i) => {
    const smCount = t.smart_money_count || 0;
    const kolCount = t.kol_count || 0;
    const price = t.price != null ? (Number(t.price) < 0.01 ? Number(t.price).toExponential(2) : '$' + Number(t.price).toFixed(4)) : '—';
    const logoHtml = t.logo ? `<img src="${t.logo}" width="14" height="14" style="border-radius:3px;flex-shrink:0" onerror="this.style.display='none'">` : '';
    return `<div class="gmgn-trade-row">
      <span class="gmgn-rank">${i + 1}</span>
      ${logoHtml}
      <span class="gmgn-trade-token">${t.symbol || t.name || '?'}</span>
      <span class="gmgn-price">${price}</span>
      <span style="color:var(--gold);font-weight:600;min-width:70px;text-align:right;font-size:9px">SM:${smCount} KOL:${kolCount}</span>
    </div>`;
  }).join('');
}

/* ─── Log Tabs ─── */
document.querySelectorAll('.log-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.log-tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    addLog('INFO', `Switched to ${tab.dataset.tab} log view`);
  });
});

document.getElementById('log-filter').addEventListener('input', renderLogs);

/* ─── Terminal Input ─── */
const termInput = document.getElementById('term-input');
const termBody = document.getElementById('terminal');

termInput.addEventListener('keydown', async (e) => {
  if (e.key === 'Enter') {
    const cmd = termInput.value.trim();
    if (!cmd) return;
    commandHistory.push(cmd);
    historyIdx = commandHistory.length;
    appendTermLine(`hermemes $ ${cmd}`, 'cyan');
    termInput.value = '';
    const result = await executeCommand(cmd);
    if (result) appendTermLine(result, 'text');
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    if (historyIdx > 0) { historyIdx--; termInput.value = commandHistory[historyIdx]; }
  } else if (e.key === 'ArrowDown') {
    e.preventDefault();
    if (historyIdx < commandHistory.length - 1) { historyIdx++; termInput.value = commandHistory[historyIdx]; }
    else { historyIdx = commandHistory.length; termInput.value = ''; }
  }
});

function appendTermLine(text, color) {
  const div = document.createElement('div');
  div.style.color = color === 'cyan' ? 'var(--cyan)' :
                    color === 'gold' ? 'var(--gold)' :
                    color === 'green' ? 'var(--green)' :
                    color === 'red' ? 'var(--red)' : 'var(--text)';
  div.style.whiteSpace = 'pre-wrap';
  div.textContent = text;
  const inputWrap = document.querySelector('.terminal-input-wrap');
  termBody.insertBefore(div, inputWrap);
  termBody.scrollTop = termBody.scrollHeight;
}

async function executeCommand(cmd) {
  const parts = cmd.split(/\s+/);
  const action = parts[0];

  switch(action) {
    case 'help':
      return [
        'Available commands:',
        '  status      — Show agent status',
        '  tools       — List available tools',
        '  system      — Show system stats',
        '  chain       — Show BSC chain data',
        '  env         — Show environment config',
        '  kol scan    — Trigger KOL pool scan',
        '  kol analyze <wallet> — Analyze a KOL wallet',
        '  safety <token> — Quick token safety check',
        '  gmgn        — GMGN on-chain intelligence (type gmgn for subcommands)',
        '  clear       — Clear terminal',
        '  help        — Show this help',
      ].join('\n');

    case 'clear': {
      const banner = document.querySelector('.ascii-banner');
      const info = document.querySelector('.terminal-info');
      const inputWrap = document.querySelector('.terminal-input-wrap');
      const toRemove = [];
      for (const child of termBody.children) {
        if (child !== banner && child !== info && child !== inputWrap) toRemove.push(child);
      }
      toRemove.forEach(c => c.remove());
      return null;
    }

    case 'status': {
      const data = await api('/api/status');
      if (!data) return 'Failed to fetch status';
      return `Status: ${data.status}\nModel: ${data.model}\nProvider: ${data.provider}\nTools: ${data.tools_count}\nAPI Calls: ${data.token_usage?.api_calls || 0}`;
    }

    case 'tools': {
      const data = await api('/api/tools');
      if (!data || !data.tools) return 'Failed to fetch tools';
      return `${data.count} tools loaded:\n` + data.tools.map(t => `  • ${t}`).join('\n');
    }

    case 'system': {
      const data = await api('/api/system');
      if (!data) return 'Failed';
      return `CPU: ${data.cpu_percent}%  MEM: ${data.memory_percent}%  DISK: ${data.disk_percent}%  Uptime: ${data.uptime}`;
    }

    case 'chain': {
      const data = await api('/api/chain');
      if (!data) return 'Failed';
      return `Gas: ${data.gas_gwei} Gwei  Block: #${data.block?.toLocaleString()}  BNB: $${data.bnb_price}`;
    }

    case 'env': {
      const data = await api('/api/env');
      if (!data) return 'Failed';
      return Object.entries(data).map(([k, v]) => `  ${k}: ${v}`).join('\n');
    }

    case 'kol':
      if (parts[1] === 'scan') {
        const data = await api('/api/kol/scan');
        return data ? JSON.stringify(data, null, 2) : 'Scan failed';
      }
      if (parts[1] === 'analyze' && parts[2]) {
        const data = await api(`/api/kol/analyze/${parts[2]}`);
        return data ? JSON.stringify(data, null, 2) : 'Analysis failed';
      }
      return 'Usage: kol scan | kol analyze <wallet>';

    case 'safety':
      if (parts[1]) {
        const data = await api(`/api/safety/${parts[1]}`);
        return data ? JSON.stringify(data, null, 2) : 'Safety check failed';
      }
      return 'Usage: safety <token_address>';

    case 'gmgn': {
      const chain = parts.includes('--sol') ? 'sol' : parts.includes('--eth') ? 'eth' : parts.includes('--base') ? 'base' : 'bsc';
      const cleanParts = parts.filter(p => !p.startsWith('--'));
      if (cleanParts[1] === 'trending') {
        const data = await api(`/api/gmgn/trending${chain !== 'bsc' ? '/' + chain : ''}`);
        if (!data || !data.tokens) return 'Failed to fetch trending';
        return `Trending [${chain.toUpperCase()}]:\n` + data.tokens.slice(0, 15).map((t, i) =>
          `${i+1}. ${t.symbol} — ${t.price ? (t.price < 0.01 ? Number(t.price).toExponential(2) : '$' + Number(t.price).toFixed(4)) : '?'} | SM:${t.smart_money_count||0} KOL:${t.kol_count||0}`
        ).join('\n');
      }
      if (cleanParts[1] === 'token' && cleanParts[2]) {
        const data = await api(`/api/gmgn/token/${chain}/${cleanParts[2]}`);
        return data ? JSON.stringify(data, null, 2) : 'Token not found';
      }
      if (cleanParts[1] === 'security' && cleanParts[2]) {
        const data = await api(`/api/gmgn/token/${chain}/${cleanParts[2]}/security`);
        return data ? JSON.stringify(data, null, 2) : 'Security check failed';
      }
      if (cleanParts[1] === 'holders' && cleanParts[2]) {
        const tag = cleanParts[3] === 'kol' ? '/kol' : cleanParts[3] === 'smart' ? '/smart' : '';
        const data = await api(`/api/gmgn/token/${chain}/${cleanParts[2]}/holders${tag}`);
        return data ? JSON.stringify(data, null, 2) : 'Holders data failed';
      }
      if (cleanParts[1] === 'wallet' && cleanParts[2]) {
        const data = await api(`/api/gmgn/wallet/${chain}/${cleanParts[2]}`);
        return data ? JSON.stringify(data, null, 2) : 'Wallet data failed';
      }
      if (cleanParts[1] === 'smart') {
        const data = await api(`/api/gmgn/smart-money${chain !== 'bsc' ? '/' + chain : ''}`);
        if (!data || !data.tokens) return 'No smart money data';
        return `Smart Money [${chain.toUpperCase()}]:\n` + data.tokens.slice(0, 15).map((t, i) =>
          `${i+1}. ${t.symbol} — SM:${t.smart_money_count||0} | Buy:${t.smart_buy_24h||0} Sell:${t.smart_sell_24h||0}`
        ).join('\n');
      }
      return [
        'GMGN on-chain intelligence:',
        '  gmgn trending             — Trending tokens (BSC default)',
        '  gmgn trending --sol       — Solana trending',
        '  gmgn trending --eth       — Ethereum trending',
        '  gmgn smart                — Smart money trending',
        '  gmgn token <addr>         — Token info',
        '  gmgn security <addr>      — Token security check',
        '  gmgn holders <addr>       — Top holders',
        '  gmgn holders <addr> kol   — KOL holders',
        '  gmgn holders <addr> smart — Smart money holders',
        '  gmgn wallet <addr>        — Wallet holdings',
        '',
        '  Add --sol / --eth / --base for other chains',
      ].join('\n');
    }

    default:
      return `Unknown command: ${action}. Type 'help' for available commands.`;
  }
}

/* ─── Auto-Refresh ─── */
document.getElementById('btn-auto').addEventListener('click', function() {
  autoRefresh = !autoRefresh;
  this.classList.toggle('tb-active', autoRefresh);
  this.textContent = autoRefresh ? 'AUTO' : 'MANUAL';
  if (autoRefresh) startAutoRefresh();
  else stopAutoRefresh();
});

function refreshAll() {
  fetchSystemStats();
  fetchChainData();
  fetchCronJobs();
  fetchKolPool();
  fetchToolUsage();
  fetchSessions();
  fetchGmgnTrending();
  fetchGmgnSmartMoney();
}

function startAutoRefresh() {
  stopAutoRefresh();
  refreshTimer = setInterval(refreshAll, 10000);
}

function stopAutoRefresh() {
  if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null; }
}

/* ─── Global ASCII Cursor Trail ─── */
(function initAsciiTrail() {
  const chars = 'hermemesagent';
  let lastX = 0, lastY = 0;
  let throttle = 0;
  const MAX_PARTICLES = 40;
  let particleCount = 0;

  document.addEventListener('mousemove', (e) => {
    const now = Date.now();
    if (now - throttle < 40) return;

    const dx = e.clientX - lastX;
    const dy = e.clientY - lastY;
    const dist = Math.sqrt(dx * dx + dy * dy);
    if (dist < 12) return;

    throttle = now;
    lastX = e.clientX;
    lastY = e.clientY;

    if (particleCount >= MAX_PARTICLES) return;

    const count = 1 + Math.floor(Math.random() * 2);
    for (let i = 0; i < count; i++) {
      spawnParticle(e.clientX, e.clientY);
    }
  });

  function spawnParticle(x, y) {
    const el = document.createElement('span');
    el.className = 'ascii-particle';
    el.textContent = chars[Math.floor(Math.random() * chars.length)];

    const size = 10 + Math.random() * 8;
    const offsetX = (Math.random() - 0.5) * 24;
    const offsetY = (Math.random() - 0.5) * 24;
    const driftX = (Math.random() - 0.5) * 40;
    const driftY = -15 - Math.random() * 30;

    el.style.left = (x + offsetX) + 'px';
    el.style.top = (y + offsetY) + 'px';
    el.style.fontSize = size + 'px';
    el.style.setProperty('--dx', driftX + 'px');
    el.style.setProperty('--dy', driftY + 'px');

    document.body.appendChild(el);
    particleCount++;

    el.addEventListener('animationend', () => {
      el.remove();
      particleCount--;
    });
  }
})();

/* ─── Init ─── */
(function init() {
  addLog('INFO', 'Hermemes Control Interface loaded');
  addLog('INFO', 'Connecting to backend — all data is REAL');

  fetchStatus();
  fetchAgents();
  fetchEnvInfo();
  refreshAll();

  if (autoRefresh) startAutoRefresh();
  termInput.focus();
})();
