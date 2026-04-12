/* Hermemes Landing — matching hermemes.xyz */

/* ─── Particle Background ─── */
(function initParticles() {
  const canvas = document.getElementById('particles');
  const ctx = canvas.getContext('2d');
  let w, h, particles = [];

  function resize() {
    w = canvas.width = window.innerWidth;
    h = canvas.height = window.innerHeight;
  }
  resize();
  window.addEventListener('resize', resize);

  for (let i = 0; i < 60; i++) {
    particles.push({
      x: Math.random() * w,
      y: Math.random() * h,
      vx: (Math.random() - 0.5) * 0.3,
      vy: (Math.random() - 0.5) * 0.3,
      r: Math.random() * 1.5 + 0.5,
      a: Math.random() * 0.3 + 0.05,
    });
  }

  function draw() {
    ctx.clearRect(0, 0, w, h);

    for (const p of particles) {
      p.x += p.vx;
      p.y += p.vy;
      if (p.x < 0) p.x = w;
      if (p.x > w) p.x = 0;
      if (p.y < 0) p.y = h;
      if (p.y > h) p.y = 0;

      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(255,255,255,${p.a})`;
      ctx.fill();
    }

    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const dx = particles[i].x - particles[j].x;
        const dy = particles[i].y - particles[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 120) {
          ctx.beginPath();
          ctx.moveTo(particles[i].x, particles[i].y);
          ctx.lineTo(particles[j].x, particles[j].y);
          ctx.strokeStyle = `rgba(255,255,255,${0.04 * (1 - dist / 120)})`;
          ctx.lineWidth = 0.5;
          ctx.stroke();
        }
      }
    }

    requestAnimationFrame(draw);
  }
  draw();
})();

/* ─── GitHub Widget — fetch real data ─── */
(async function fetchGitHub() {
  const widget = document.getElementById('github-widget');

  try {
    const [repoRes, contribRes] = await Promise.all([
      fetch('https://api.github.com/repos/NousResearch/hermes-agent'),
      fetch('https://api.github.com/repos/NousResearch/hermes-agent/contributors?per_page=8'),
    ]);

    const repo = await repoRes.json();
    const contribs = await contribRes.json();

    // Stars
    const starsEl = document.getElementById('gh-stars');
    animateCount(starsEl, repo.stargazers_count || 0);

    // Forks
    const forksEl = document.getElementById('gh-forks');
    animateCount(forksEl, repo.forks_count || 0);

    // Updated
    const updatedEl = document.getElementById('gh-updated');
    updatedEl.textContent = timeAgo(repo.pushed_at);

    // Contributors
    const contribEl = document.getElementById('gh-contributors');
    if (Array.isArray(contribs)) {
      contribEl.innerHTML = contribs.map(c =>
        `<img src="${c.avatar_url}" alt="${c.login}" title="${c.login}"/>`
      ).join('') + `<span style="font-size:9px;color:rgba(255,255,255,0.2);margin-left:6px">${contribs.length}+</span>`;
    }

    // Make widget a link
    widget.onclick = () => window.open('https://github.com/NousResearch/hermes-agent', '_blank');

  } catch (e) {
    console.error('GitHub fetch error:', e);
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
