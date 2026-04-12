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

/* ─── WebGL Halftone Character ─── */
(function initHalftone() {
  const canvas = document.getElementById('halftone-canvas');
  const img = document.getElementById('character-src');
  const wrap = document.getElementById('character-wrap');
  if (!canvas || !img) return;

  const gl = canvas.getContext('webgl', { alpha: true, premultipliedAlpha: false });
  if (!gl) return;

  const vsSource = `
    attribute vec2 a_position;
    attribute vec2 a_texCoord;
    varying vec2 v_texCoord;
    void main() {
      gl_Position = vec4(a_position, 0.0, 1.0);
      v_texCoord = a_texCoord;
    }
  `;

  const fsSource = `
    precision mediump float;
    varying vec2 v_texCoord;
    uniform sampler2D u_image;
    uniform vec2 u_resolution;
    uniform vec2 u_mouse;
    uniform float u_time;
    uniform float u_spacing;

    void main() {
      vec2 pixel = v_texCoord * u_resolution;
      vec2 cell = floor(pixel / u_spacing) * u_spacing + u_spacing * 0.5;
      vec2 cellUV = cell / u_resolution;

      vec4 texColor = texture2D(u_image, cellUV);
      float gray = dot(texColor.rgb, vec3(0.299, 0.587, 0.114));

      float dotRadius = gray * u_spacing * 0.48;
      float dist = length(pixel - cell);
      float dot = 1.0 - smoothstep(dotRadius - 0.8, dotRadius + 0.8, dist);

      // Mouse reveal field
      vec2 mousePixel = u_mouse * u_resolution;
      vec2 diff = (pixel - mousePixel);
      diff.x *= 0.7; // stretch ellipse
      float mouseDist = length(diff);
      float reveal = 1.0 - exp(-dot(diff, diff) / (120.0 * 120.0));

      // Mix halftone dots with original image
      vec3 dotColor = vec3(dot * gray);
      vec3 originalColor = texColor.rgb;
      vec3 finalColor = mix(originalColor, dotColor, reveal);

      // Fade alpha for transparent parts
      float alpha = max(dot * reveal, (1.0 - reveal)) * texColor.a;

      gl_FragColor = vec4(finalColor, alpha);
    }
  `;

  function createShader(type, source) {
    const s = gl.createShader(type);
    gl.shaderSource(s, source);
    gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
      console.error(gl.getShaderInfoLog(s));
      gl.deleteShader(s);
      return null;
    }
    return s;
  }

  const vs = createShader(gl.VERTEX_SHADER, vsSource);
  const fs = createShader(gl.FRAGMENT_SHADER, fsSource);
  const program = gl.createProgram();
  gl.attachShader(program, vs);
  gl.attachShader(program, fs);
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    console.error(gl.getProgramInfoLog(program));
    return;
  }

  const posLoc = gl.getAttribLocation(program, 'a_position');
  const texLoc = gl.getAttribLocation(program, 'a_texCoord');
  const uRes = gl.getUniformLocation(program, 'u_resolution');
  const uMouse = gl.getUniformLocation(program, 'u_mouse');
  const uTime = gl.getUniformLocation(program, 'u_time');
  const uSpacing = gl.getUniformLocation(program, 'u_spacing');

  const posBuf = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, posBuf);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([
    -1,-1,  1,-1,  -1,1,
    -1,1,   1,-1,   1,1
  ]), gl.STATIC_DRAW);

  const texBuf = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, texBuf);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([
    0,1,  1,1,  0,0,
    0,0,  1,1,  1,0
  ]), gl.STATIC_DRAW);

  let mouseX = -1, mouseY = -1;
  let texture = null;
  let running = false;

  wrap.addEventListener('mousemove', (e) => {
    const rect = canvas.getBoundingClientRect();
    mouseX = (e.clientX - rect.left) / rect.width;
    mouseY = (e.clientY - rect.top) / rect.height;
  });
  wrap.addEventListener('mouseleave', () => {
    mouseX = -1;
    mouseY = -1;
  });

  function loadTexture() {
    texture = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, texture);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, img);
  }

  function resize() {
    const rect = wrap.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    gl.viewport(0, 0, canvas.width, canvas.height);
  }

  function render(time) {
    if (!running) return;
    const t = time * 0.001;

    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);

    gl.useProgram(program);

    gl.bindBuffer(gl.ARRAY_BUFFER, posBuf);
    gl.enableVertexAttribArray(posLoc);
    gl.vertexAttribPointer(posLoc, 2, gl.FLOAT, false, 0, 0);

    gl.bindBuffer(gl.ARRAY_BUFFER, texBuf);
    gl.enableVertexAttribArray(texLoc);
    gl.vertexAttribPointer(texLoc, 2, gl.FLOAT, false, 0, 0);

    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, texture);

    gl.uniform2f(uRes, canvas.width, canvas.height);
    gl.uniform2f(uMouse, mouseX, mouseY);
    gl.uniform1f(uTime, t);
    gl.uniform1f(uSpacing, 6.0 * (Math.min(window.devicePixelRatio || 1, 2)));

    gl.drawArrays(gl.TRIANGLES, 0, 6);
    requestAnimationFrame(render);
  }

  function start() {
    resize();
    loadTexture();
    running = true;
    requestAnimationFrame(render);
  }

  if (img.complete && img.naturalWidth > 0) start();
  else img.addEventListener('load', start);

  window.addEventListener('resize', resize);
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
