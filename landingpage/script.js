/* Hermemes Landing — matching hermemes.xyz */

/* ─── Matrix Dithering Dot Grid ─── */
(function initMatrix() {
  const canvas = document.getElementById('particles');
  const ctx = canvas.getContext('2d');
  let w, h, cols, rows;
  const GAP = 16;

  function resize() {
    w = canvas.width = window.innerWidth;
    h = canvas.height = window.innerHeight;
    cols = Math.ceil(w / GAP) + 1;
    rows = Math.ceil(h / GAP) + 1;
  }
  resize();
  window.addEventListener('resize', resize);

  const cx = () => w * 0.5;
  const cy = () => h * 0.5;

  function draw(time) {
    const t = time * 0.001;
    ctx.clearRect(0, 0, w, h);

    const centerX = cx();
    const centerY = cy();

    for (let row = 0; row < rows; row++) {
      for (let col = 0; col < cols; col++) {
        const x = col * GAP;
        const y = row * GAP;

        const dx = x - centerX;
        const dy = y - centerY;
        const dist = Math.sqrt(dx * dx + dy * dy);

        const wave1 = Math.sin(dist * 0.025 - t * 2) * 0.5 + 0.5;
        const wave2 = (Math.sin(x * 0.01 + t * 0.7) * Math.cos(y * 0.01 + t * 0.5)) * 0.5 + 0.5;
        const wave3 = Math.sin((x + y) * 0.005 + t * 1.2) * 0.5 + 0.5;

        const combined = wave1 * 0.45 + wave2 * 0.3 + wave3 * 0.25;

        const alpha = 0.02 + combined * 0.23;
        const radius = 0.3 + combined * 1.9;

        ctx.beginPath();
        ctx.arc(x, y, radius, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255,255,255,${alpha})`;
        ctx.fill();
      }
    }

    requestAnimationFrame(draw);
  }
  requestAnimationFrame(draw);
})();


/* ─── GitHub Widget — fetch real data ─── */
(async function fetchGitHub() {
  const widget = document.getElementById('github-widget');
  const repoUrl = 'https://github.com/hermemes/hermes-agent';
  const apiBase = 'https://api.github.com/repos/hermemes/hermes-agent';

  widget.onclick = () => window.open(repoUrl, '_blank');

  try {
    const [repoRes, contribRes] = await Promise.all([
      fetch(apiBase),
      fetch(apiBase + '/contributors?per_page=8'),
    ]);

    if (!repoRes.ok) throw new Error('API ' + repoRes.status);

    const repo = await repoRes.json();
    const contribs = contribRes.ok ? await contribRes.json() : [];

    const starsEl = document.getElementById('gh-stars');
    animateCount(starsEl, repo.stargazers_count || 0);

    const forksEl = document.getElementById('gh-forks');
    animateCount(forksEl, repo.forks_count || 0);

    const updatedEl = document.getElementById('gh-updated');
    if (repo.pushed_at) updatedEl.textContent = timeAgo(repo.pushed_at);

    const contribEl = document.getElementById('gh-contributors');
    if (Array.isArray(contribs) && contribs.length > 0) {
      contribEl.innerHTML = contribs.map(c =>
        `<img src="${c.avatar_url}" alt="${c.login}" title="${c.login}"/>`
      ).join('') + `<span style="font-size:9px;color:rgba(255,255,255,0.2);margin-left:6px">${contribs.length}+</span>`;
    }

  } catch (e) {
    console.warn('GitHub API unavailable (rate limit?), widget stays visible:', e.message);
    document.getElementById('gh-stars').textContent = '–';
    document.getElementById('gh-forks').textContent = '–';
  }
})();

function animateCount(el, target) {
  if (target <= 0) { el.textContent = '0'; return; }
  const duration = 1400;
  const start = performance.now();
  function step(now) {
    const t = Math.min((now - start) / duration, 1);
    const ease = 1 - Math.pow(1 - t, 4);
    el.textContent = Math.round(ease * target).toLocaleString();
    if (t < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

function timeAgo(dateStr) {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 30) return `${days}d ago`;
  return `${Math.floor(days / 30)}mo ago`;
}
