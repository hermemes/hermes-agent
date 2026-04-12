/* Hermemes Landing Page */

/* ─── Mobile Nav ─── */
document.getElementById('nav-hamburger').addEventListener('click', () => {
  document.getElementById('nav-mobile').classList.toggle('open');
});

document.querySelectorAll('.nav-mobile a').forEach(a => {
  a.addEventListener('click', () => {
    document.getElementById('nav-mobile').classList.remove('open');
  });
});

/* ─── Copy Code ─── */
function copyCode() {
  const code = document.querySelector('.code-body code').textContent;
  navigator.clipboard.writeText(code).then(() => {
    const btn = document.querySelector('.code-copy');
    btn.textContent = 'Copied!';
    setTimeout(() => { btn.textContent = 'Copy'; }, 2000);
  });
}

/* ─── Cursor Trail (hermemes agent letters) ─── */
(function() {
  const chars = 'hermemesagent';
  let lastX = 0, lastY = 0, throttle = 0, count = 0;
  const MAX = 35;

  document.addEventListener('mousemove', (e) => {
    const now = Date.now();
    if (now - throttle < 45) return;
    const dx = e.clientX - lastX, dy = e.clientY - lastY;
    if (Math.sqrt(dx*dx + dy*dy) < 14) return;
    throttle = now;
    lastX = e.clientX;
    lastY = e.clientY;
    if (count >= MAX) return;

    const el = document.createElement('span');
    el.className = 'ascii-particle';
    el.textContent = chars[Math.floor(Math.random() * chars.length)];
    const size = 12 + Math.random() * 8;
    const ox = (Math.random() - 0.5) * 20;
    const oy = (Math.random() - 0.5) * 20;
    el.style.left = (e.clientX + ox) + 'px';
    el.style.top = (e.clientY + oy) + 'px';
    el.style.fontSize = size + 'px';
    el.style.setProperty('--dx', ((Math.random()-0.5)*40) + 'px');
    el.style.setProperty('--dy', (-15 - Math.random()*30) + 'px');
    document.body.appendChild(el);
    count++;
    el.addEventListener('animationend', () => { el.remove(); count--; });
  });
})();

/* ─── Scroll animations ─── */
const observer = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.style.opacity = '1';
      entry.target.style.transform = 'translateY(0)';
    }
  });
}, { threshold: 0.1 });

document.querySelectorAll('.feature-card, .step, .tool-item, .code-window').forEach(el => {
  el.style.opacity = '0';
  el.style.transform = 'translateY(20px)';
  el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
  observer.observe(el);
});
