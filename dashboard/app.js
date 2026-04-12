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

  const services = ['OpenRouter', 'BscScan', 'Telegram', 'Discord', 'BSC RPC'];
  let html = '';

  for (const svc of services) {
    const val = data[svc] || 'not configured';
    const isOk = val.includes('configured');
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
}

function startAutoRefresh() {
  stopAutoRefresh();
  refreshTimer = setInterval(refreshAll, 10000);
}

function stopAutoRefresh() {
  if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null; }
}

/* ─── ASCII Art Avatar Effect ─── */
(function initAsciiAvatar() {
  const img = document.getElementById('avatar-img');
  const asciiEl = document.getElementById('ascii-art');
  const chars = ' .:-=+*#%@';
  let asciiReady = false;

  function generateAscii() {
    if (asciiReady) return;
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    const w = 28, h = 28;
    canvas.width = w;
    canvas.height = h;
    ctx.drawImage(img, 0, 0, w, h);

    try {
      const data = ctx.getImageData(0, 0, w, h).data;
      let ascii = '';
      for (let y = 0; y < h; y++) {
        for (let x = 0; x < w; x++) {
          const i = (y * w + x) * 4;
          const brightness = (data[i] * 0.299 + data[i+1] * 0.587 + data[i+2] * 0.114) / 255;
          const charIdx = Math.floor(brightness * (chars.length - 1));
          ascii += chars[charIdx];
        }
        ascii += '\n';
      }
      asciiEl.textContent = ascii;
      asciiReady = true;
    } catch(e) {
      asciiEl.textContent = [
        '    ██╗  ██╗    ',
        '    ██║  ██║    ',
        '    ███████║    ',
        '    ██╔══██║    ',
        '    ██║  ██║    ',
        '    ╚═╝  ╚═╝    ',
        '   HERMEMES    ',
      ].join('\n');
      asciiReady = true;
    }
  }

  if (img.complete) generateAscii();
  else img.addEventListener('load', generateAscii);

  let shuffleInterval;
  const panel = document.getElementById('profile-panel');

  panel.addEventListener('mouseenter', () => {
    generateAscii();
    shuffleInterval = setInterval(() => {
      if (!asciiEl.textContent) return;
      const lines = asciiEl.textContent.split('\n');
      const randLine = Math.floor(Math.random() * lines.length);
      const line = lines[randLine];
      if (!line) return;
      const randCol = Math.floor(Math.random() * line.length);
      const glitchChars = '░▒▓█▀▄╗╔╚╝║═┃━☤◆◇●○';
      const arr = line.split('');
      arr[randCol] = glitchChars[Math.floor(Math.random() * glitchChars.length)];
      lines[randLine] = arr.join('');
      asciiEl.textContent = lines.join('\n');
    }, 60);
  });

  panel.addEventListener('mouseleave', () => {
    clearInterval(shuffleInterval);
    asciiReady = false;
    generateAscii();
  });
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
