/* ============================================================
   SyA Group Chile · main.js — Rev. 2026-F (optimizado)
   Cambios respecto a Rev. 2026-E:
   - Un único DOMContentLoaded (eliminado el doble listener)
   - Eliminado efecto magnético en botones (mousemove/mouseleave)
   - Carrusel de servicios: lógica robusta con loop real
   - Lab-slider: reescrito con lógica de opacidad, correcto
   - Carrusel clientes: sin cambios (funciona bien)
   - Resto de features conservadas
   ============================================================ */

document.addEventListener('DOMContentLoaded', () => {

  /* ══ 0. TRANSICIÓN DE ENTRADA ══════════════════════════ */
  document.body.style.opacity = '0';
  document.body.style.transition = 'opacity 0.5s ease';
  requestAnimationFrame(() => requestAnimationFrame(() => {
    document.body.style.opacity = '1';
  }));

  /* ══ 1. CURSOR PERSONALIZADO (sin efecto magnético) ════ */
  const dot  = document.createElement('div');
  const ring = document.createElement('div');
  dot.className  = 'cursor-dot';
  ring.className = 'cursor-ring';
  document.body.appendChild(dot);
  document.body.appendChild(ring);

  let mouseX = 0, mouseY = 0, ringX = 0, ringY = 0;
  document.addEventListener('mousemove', e => {
    mouseX = e.clientX; mouseY = e.clientY;
    dot.style.left = mouseX + 'px';
    dot.style.top  = mouseY + 'px';
  }, { passive: true });
  (function animateCursor() {
    ringX += (mouseX - ringX) * 0.14;
    ringY += (mouseY - ringY) * 0.14;
    ring.style.left = ringX + 'px';
    ring.style.top  = ringY + 'px';
    requestAnimationFrame(animateCursor);
  })();

  // Solo hover visual (agrandar ring), SIN mover el elemento
  document.querySelectorAll('a, button, .svc-card, .lead-card, .exp-card, .cert-doc-card, .geo-card, .c-pill, .c-bar-item, .qr-chip, .cliente-item').forEach(el => {
    el.addEventListener('mouseenter', () => document.body.classList.add('cursor-hover'));
    el.addEventListener('mouseleave', () => document.body.classList.remove('cursor-hover'));
  });

  /* ══ 2. SCROLL PROGRESS ════════════════════════════════ */
  const progressBar = document.createElement('div');
  progressBar.id = 'scroll-progress';
  document.body.prepend(progressBar);
  window.addEventListener('scroll', () => {
    const sy  = window.scrollY;
    const dh  = document.documentElement.scrollHeight - window.innerHeight;
    progressBar.style.width = (dh > 0 ? (sy / dh) * 100 : 0).toFixed(2) + '%';
  }, { passive: true });

  /* ══ 3. NAVBAR ══════════════════════════════════════════ */
  const navbar = document.getElementById('navbar');
  if (navbar) {
    window.addEventListener('scroll', () => {
      navbar.classList.toggle('solid', window.scrollY > 50);
    }, { passive: true });
  }

  /* ══ 4. MOBILE NAV ════════════════════════════════════ */
  const navDesktop     = document.getElementById('nav-links-desktop');
  const navToggle      = document.getElementById('nav-toggle');
  const navMobilePanel = document.getElementById('navMobilePanel');

  function closeMobileNav() {
    navMobilePanel && navMobilePanel.classList.remove('open');
    if (navToggle) {
      navToggle.setAttribute('aria-expanded', 'false');
      navToggle.classList.remove('is-open');
    }
  }
  function handleResize() {
    if (navDesktop) navDesktop.style.display = window.innerWidth >= 768 ? 'flex' : 'none';
    if (window.innerWidth >= 768) closeMobileNav();
  }
  handleResize();
  window.addEventListener('resize', handleResize);

  if (navToggle && navMobilePanel) {
    navToggle.addEventListener('click', () => {
      const open = navMobilePanel.classList.toggle('open');
      navToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      navToggle.classList.toggle('is-open', open);
    });
    navMobilePanel.querySelectorAll('a[href^="#"]').forEach(link =>
      link.addEventListener('click', closeMobileNav)
    );
  }

  /* ══ 5. HERO PARTÍCULAS ════════════════════════════════ */
  const hero = document.querySelector('.hero');
  if (hero) {
    const container = document.createElement('div');
    container.className = 'hero-particles';
    hero.prepend(container);

    const gridEl = document.createElement('div');
    gridEl.className = 'hero-grid';
    hero.prepend(gridEl);

    const colors = [
      'rgba(18,73,160,0.7)', 'rgba(14,165,233,0.6)',
      'rgba(230,126,34,0.5)', 'rgba(255,255,255,0.3)'
    ];
    for (let i = 0; i < 22; i++) {
      const p = document.createElement('div');
      p.className = 'hero-particle';
      const size  = 2 + Math.random() * 4;
      const drift = (Math.random() - 0.5) * 120 + 'px';
      const dur   = 8 + Math.random() * 14;
      const delay = Math.random() * 10;
      p.style.cssText = `width:${size}px;height:${size}px;left:${Math.random()*100}%;bottom:-20px;background:${colors[Math.floor(Math.random()*4)]};--drift:${drift};animation-duration:${dur}s;animation-delay:${-delay}s;filter:blur(${Math.random()>.7?1.5:0}px);`;
      container.appendChild(p);
    }
  }

  /* ══ 6. HERO CAROUSEL ══════════════════════════════════ */
  const track   = document.getElementById('cTrack');
  const cBar    = document.getElementById('cBar');
  if (track) {
    const slides   = Array.from(track.querySelectorAll('.c-slide'));
    const N        = slides.length;
    const DELAY    = 6200;
    let cur = 0, timer = null, rafId = null, rafStart = null;
    const barItems = cBar ? Array.from(cBar.querySelectorAll('.c-bar-item')) : [];

    barItems.forEach(item => {
      item.addEventListener('click', () => goTo(parseInt(item.dataset.idx, 10)));
    });

    function resetProgBars() {
      barItems.forEach(item => {
        const pb = item.querySelector('.c-bar-prog');
        if (pb) { pb.style.transition = 'none'; pb.style.width = '0%'; }
      });
    }
    function startProg(idx) {
      cancelAnimationFrame(rafId);
      resetProgBars();
      const pb = barItems[idx] ? barItems[idx].querySelector('.c-bar-prog') : null;
      if (!pb) return;
      rafStart = performance.now();
      (function step(now) {
        const pct = Math.min(((now - rafStart) / DELAY) * 100, 100);
        pb.style.width = pct + '%';
        if (pct < 100) rafId = requestAnimationFrame(step);
      })(performance.now());
    }
    function updateUI(idx) {
      slides.forEach((s, i)   => s.classList.toggle('active', i === idx));
      barItems.forEach((b, i) => b.classList.toggle('active', i === idx));
      track.style.transform = `translateX(-${idx * 100}%)`;
    }
    function goTo(idx) {
      cur = ((idx % N) + N) % N;
      updateUI(cur);
      clearInterval(timer);
      timer = setInterval(() => goTo(cur + 1), DELAY);
      startProg(cur);
    }

    updateUI(0);
    timer = setInterval(() => goTo(cur + 1), DELAY);
    startProg(0);

    // Touch
    let tx = 0;
    track.addEventListener('touchstart', e => { tx = e.touches[0].clientX; }, { passive: true });
    track.addEventListener('touchend',   e => {
      const dx = e.changedTouches[0].clientX - tx;
      if (Math.abs(dx) > 50) goTo(dx < 0 ? cur + 1 : cur - 1);
    }, { passive: true });

    // Keyboard
    document.addEventListener('keydown', e => {
      if (e.key === 'ArrowLeft')  goTo(cur - 1);
      if (e.key === 'ArrowRight') goTo(cur + 1);
    });

    // Visibilidad
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) { clearInterval(timer); cancelAnimationFrame(rafId); }
      else goTo(cur);
    });
  }

  /* ══ 7. CARRUSEL DE SERVICIOS (corregido, con controles) */
  (function initSvcCarousel() {
    const wrapper = document.querySelector('.svc-carousel-wrapper');
    const track   = document.getElementById('svcCarouselTrack');
    if (!track || !wrapper) return;

    const originalSlides = Array.from(track.querySelectorAll('.svc-carousel-slide'));
    const N = originalSlides.length;
    if (N === 0) return;

    // Crear controles (nav + dots)
    const navEl = document.createElement('div');
    navEl.className = 'svc-carousel-nav';
    navEl.innerHTML = `
      <button class="svc-carousel-btn" id="svcPrev" aria-label="Anterior"><i class="fas fa-chevron-left"></i></button>
      <div class="svc-carousel-dots" id="svcDots"></div>
      <button class="svc-carousel-btn" id="svcNext" aria-label="Siguiente"><i class="fas fa-chevron-right"></i></button>
    `;
    wrapper.appendChild(navEl);

    const dotsContainer = navEl.querySelector('#svcDots');
    const dots = originalSlides.map((_, i) => {
      const d = document.createElement('button');
      d.className = 'svc-carousel-dot' + (i === 0 ? ' active' : '');
      d.setAttribute('aria-label', `Slide ${i + 1}`);
      d.addEventListener('click', () => goTo(i));
      dotsContainer.appendChild(d);
      return d;
    });

    let current = 0;
    let autoTimer = null;
    const INTERVAL = 4500;

    function goTo(idx) {
      current = ((idx % N) + N) % N;
      track.style.transform = `translateX(-${current * 100}%)`;
      dots.forEach((d, i) => d.classList.toggle('active', i === current));
    }
    function startAuto() {
      clearInterval(autoTimer);
      autoTimer = setInterval(() => goTo(current + 1), INTERVAL);
    }
    function stopAuto() { clearInterval(autoTimer); }

    navEl.querySelector('#svcPrev').addEventListener('click', () => { goTo(current - 1); startAuto(); });
    navEl.querySelector('#svcNext').addEventListener('click', () => { goTo(current + 1); startAuto(); });

    wrapper.addEventListener('mouseenter', stopAuto);
    wrapper.addEventListener('mouseleave', startAuto);

    // Touch
    let touchX = 0;
    track.addEventListener('touchstart', e => { touchX = e.touches[0].clientX; stopAuto(); }, { passive: true });
    track.addEventListener('touchend',   e => {
      const dx = e.changedTouches[0].clientX - touchX;
      if (Math.abs(dx) > 40) goTo(dx < 0 ? current + 1 : current - 1);
      startAuto();
    }, { passive: true });

    goTo(0);
    startAuto();
  })();

  /* ══ 8. LAB SLIDER (carrusel de laboratorio, reescrito) */
  (function initLabSlider() {
    const container = document.getElementById('labSlider');
    const prevBtn   = document.getElementById('labPrev');
    const nextBtn   = document.getElementById('labNext');
    const dotsEl    = document.getElementById('labDots');
    if (!container) return;

    const slides = Array.from(container.querySelectorAll('.lab-subsection-slide'));
    const N = slides.length;
    if (N === 0) return;

    // Crear dots
    const dots = slides.map((_, i) => {
      const d = document.createElement('button');
      d.className = 'lab-subsection-dot' + (i === 0 ? ' active' : '');
      d.setAttribute('aria-label', `Imagen ${i + 1}`);
      d.addEventListener('click', () => goTo(i));
      dotsEl && dotsEl.appendChild(d);
      return d;
    });

    let current = 0;
    let autoTimer = null;
    const INTERVAL = 4000;

    function goTo(idx) {
      // Quitar active del slide anterior
      slides[current].classList.remove('active');
      dots[current] && dots[current].classList.remove('active');

      current = ((idx % N) + N) % N;

      slides[current].classList.add('active');
      dots[current] && dots[current].classList.add('active');
    }

    function startAuto() {
      clearInterval(autoTimer);
      autoTimer = setInterval(() => goTo(current + 1), INTERVAL);
    }
    function stopAuto() { clearInterval(autoTimer); }

    prevBtn && prevBtn.addEventListener('click', () => { goTo(current - 1); startAuto(); });
    nextBtn && nextBtn.addEventListener('click', () => { goTo(current + 1); startAuto(); });

    container.addEventListener('mouseenter', stopAuto);
    container.addEventListener('mouseleave', startAuto);

    // Touch
    let touchX = 0;
    container.addEventListener('touchstart', e => { touchX = e.touches[0].clientX; stopAuto(); }, { passive: true });
    container.addEventListener('touchend',   e => {
      const dx = e.changedTouches[0].clientX - touchX;
      if (Math.abs(dx) > 40) goTo(dx < 0 ? current + 1 : current - 1);
      startAuto();
    }, { passive: true });

    // Inicializar estado
    slides.forEach(s => s.classList.remove('active'));
    slides[0].classList.add('active');
    dots[0] && dots[0].classList.add('active');
    startAuto();
  })();

  /* ══ 9. CARRUSEL INFINITO DE CLIENTES ════════════════ */
  function createInfiniteCarousel(trackEl) {
    if (!trackEl) return;
    const items = Array.from(trackEl.children);
    if (!items.length) return;
    // Clonar para loop infinito
    items.forEach(item => trackEl.appendChild(item.cloneNode(true)));

    const speed = 0.04; // px por ms
    let offset = 0, prevTime = null, halfWidth = 1;
    let isDragging = false, startX = 0, startOffset = 0;
    const wrapper = trackEl.closest('.brands-carousel-wrapper');

    function normalize(val) {
      halfWidth = trackEl.scrollWidth / 2 || 1;
      while (val >= halfWidth) val -= halfWidth;
      while (val < 0)          val += halfWidth;
      return val;
    }
    (function animate(ts) {
      if (prevTime === null) prevTime = ts;
      const delta = ts - prevTime; prevTime = ts;
      if (!isDragging) {
        offset = normalize(offset + delta * speed);
        trackEl.style.transform = `translateX(-${offset}px)`;
      }
      requestAnimationFrame(animate);
    })(performance.now());

    const endDrag = (e) => {
      if (!isDragging) return;
      isDragging = false;
      trackEl.style.cursor = 'grab';
      if (wrapper) wrapper.style.cursor = 'grab';
      try { trackEl.releasePointerCapture(e.pointerId); } catch(_){}
    };
    trackEl.addEventListener('pointerdown', e => {
      isDragging = true; startX = e.clientX; startOffset = offset;
      trackEl.style.cursor = 'grabbing';
      if (wrapper) wrapper.style.cursor = 'grabbing';
      try { trackEl.setPointerCapture(e.pointerId); } catch(_){}
    });
    trackEl.addEventListener('pointermove', e => {
      if (!isDragging) return;
      offset = normalize(startOffset - (e.clientX - startX));
      trackEl.style.transform = `translateX(-${offset}px)`;
    });
    ['pointerup','pointercancel','pointerleave'].forEach(ev =>
      trackEl.addEventListener(ev, endDrag)
    );
  }
  createInfiniteCarousel(document.getElementById('clientesCarouselTrackLTR'));

  /* ══ 10. SCROLL REVEAL ════════════════════════════════ */
  const revealEls = document.querySelectorAll('.reveal, .reveal-left');
  if ('IntersectionObserver' in window) {
    const obs = new IntersectionObserver(entries => {
      entries.forEach(e => {
        if (e.isIntersecting) {
          e.target.classList.add('visible');
          obs.unobserve(e.target);
        }
      });
    }, { threshold: 0.1, rootMargin: '0px 0px -48px 0px' });
    revealEls.forEach(el => obs.observe(el));
  } else {
    revealEls.forEach(el => el.classList.add('visible'));
  }

  /* ══ 11. CONTADORES ANIMADOS ══════════════════════════ */
  function animateCounter(el, target, suffix, duration = 1600) {
    const num = parseFloat(target);
    if (isNaN(num)) { el.textContent = target; return; }
    const isDecimal = target.includes('.');
    const start = performance.now();
    function ease(t) { return 1 - Math.pow(1 - t, 4); }
    (function update(now) {
      const t = Math.min((now - start) / duration, 1);
      const val = num * ease(t);
      el.innerHTML = (isDecimal ? val.toFixed(1) : Math.floor(val)) + (suffix ? `<span>${suffix}</span>` : '');
      if (t < 1) requestAnimationFrame(update);
      else el.innerHTML = target + (suffix ? `<span>${suffix}</span>` : '');
    })(performance.now());
  }
  const counterObs = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (!entry.isIntersecting || entry.target.__counted) return;
      entry.target.__counted = true;
      const span   = entry.target.querySelector('span');
      const suffix = span ? span.textContent : '';
      const raw    = entry.target.textContent.replace(suffix, '').trim();
      if (!isNaN(parseFloat(raw))) animateCounter(entry.target, raw, suffix);
      counterObs.unobserve(entry.target);
    });
  }, { threshold: 0.5 });
  document.querySelectorAll('.team-stat-n').forEach(el => counterObs.observe(el));

  /* ══ 12. HOVER SPOTLIGHT EN CARDS ════════════════════ */
  document.querySelectorAll('.svc-card, .lead-card, .exp-card, .about-card, .spec-card, .geo-card').forEach(card => {
    card.addEventListener('mousemove', e => {
      const r = card.getBoundingClientRect();
      card.style.setProperty('--spotlight-x', ((e.clientX - r.left) / r.width  * 100) + '%');
      card.style.setProperty('--spotlight-y', ((e.clientY - r.top)  / r.height * 100) + '%');
    });
  });

  /* ══ 13. SVG TOPOGRÁFICO ══════════════════════════════ */
  function buildTopoSVG(color) {
    const W = 1440, H = 800;
    function noisyEllipse(cx, cy, rx, ry, seed, lbl) {
      const pts = 28, points = [];
      for (let i = 0; i <= pts; i++) {
        const a = (i / pts) * Math.PI * 2;
        const n = Math.sin(a*3.7+seed)*rx*.14 + Math.sin(a*7.1+seed*1.3)*ry*.09 + Math.sin(a*1.9+seed*.7)*rx*.07;
        points.push([cx+(rx+n)*Math.cos(a), cy+(ry+n*.65)*Math.sin(a)]);
      }
      let d = `M ${points[0][0].toFixed(1)} ${points[0][1].toFixed(1)}`;
      for (let i = 1; i < points.length; i++) {
        const [px,py] = points[i-1], [cx2,cy2] = points[i];
        const [ppx,ppy] = i>=2 ? points[i-2] : points[i-1];
        const [nx, ny]  = i<points.length-1 ? points[i+1] : points[i];
        d += ` C ${(px+(cx2-ppx)*.2).toFixed(1)} ${(py+(cy2-ppy)*.2).toFixed(1)}, ${(cx2-(nx-px)*.2).toFixed(1)} ${(cy2-(ny-py)*.2).toFixed(1)}, ${cx2.toFixed(1)} ${cy2.toFixed(1)}`;
      }
      d += ' Z';
      return `<path d="${d}" fill="none" stroke="${color}" stroke-width="0.9"/>${lbl ? `<text x="${(cx+rx*1.05).toFixed(0)}" y="${cy.toFixed(0)}" font-size="11" fill="${color}" opacity="0.5" font-family="monospace">${lbl}</text>` : ''}`;
    }
    let paths = '';
    [[W*.38,H*.48],[W*.72,H*.32],[W*.18,H*.72]].forEach(([cx,cy], g) => {
      const sizes = g===0 ? [38,68,104,145,190,238,288,342,400] : g===1 ? [24,48,76,108,146,186] : [18,36,58,82,108];
      const ry_f  = g===0 ? .76 : g===1 ? .74 : .77;
      sizes.forEach((rx, i) => {
        paths += noisyEllipse(cx, cy, rx, rx*ry_f, (g+1)*1.1 + i*1.4, null);
      });
    });
    return `<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid slice">${paths}</svg>`;
  }
  document.querySelectorAll('.topo-canvas').forEach(c => {
    c.innerHTML = buildTopoSVG(c.classList.contains('topo-dark') ? '#FFFFFF' : c.classList.contains('topo-warm') ? '#E67E22' : '#1249A0');
  });

  /* ══ 14. CERT MODAL ════════════════════════════════════ */
  window.openCertModal = function(url, title) {
    const modal = document.getElementById('cert-modal');
    if (!modal) return;
    document.getElementById('cert-modal-title').textContent = title;
    document.getElementById('cert-modal-frame').src = url;
    document.getElementById('cert-modal-dl').href = url;
    modal.classList.add('active');
    document.body.style.overflow = 'hidden';
  };
  window.closeCertModal = function() {
    const modal = document.getElementById('cert-modal');
    if (!modal) return;
    modal.classList.remove('active');
    document.getElementById('cert-modal-frame').src = '';
    document.body.style.overflow = '';
  };
  document.addEventListener('keydown', e => { if (e.key === 'Escape') window.closeCertModal(); });

  /* ══ 15. CHAT WIDGET ═══════════════════════════════════ */
  const sendUrl  = window.CHAT_SEND_URL  || '/chat/public/';
  const resetUrl = window.CHAT_RESET_URL || '/chat/reset/';

  function getCookie(name) {
    return document.cookie.split(';').reduce((acc, c) => {
      c = c.trim();
      return c.startsWith(name + '=') ? decodeURIComponent(c.slice(name.length + 1)) : acc;
    }, null);
  }
  function timeLabel() {
    const n = new Date();
    return String(n.getHours()).padStart(2,'0') + ':' + String(n.getMinutes()).padStart(2,'0');
  }
  function renderMarkdown(text) {
    return text
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g,     '<em>$1</em>')
      .replace(/^- (.+)$/gm,    '<li>$1</li>')
      .replace(/(<li>.*<\/li>)/gs, '<ul style="margin:6px 0 6px 16px;padding:0;list-style:disc;">$1</ul>')
      .replace(/\n{2,}/g, '<br><br>').replace(/\n/g, '<br>');
  }
  function botAvatar() {
    return `<div style="width:26px;height:26px;border-radius:50%;background:linear-gradient(135deg,#0a1628,#0e4d6e);display:flex;align-items:center;justify-content:center;flex-shrink:0;margin-top:2px;"><i class="fas fa-water" style="color:#4ecdc4;font-size:.6rem;"></i></div>`;
  }
  function appendMessage(text, fromUser) {
    const history  = document.getElementById('chat-history');
    const messages = document.getElementById('chat-messages');
    if (!history) return;
    const w = document.createElement('div');
    w.className = 'msg-row';
    w.style.cssText = 'display:flex;flex-direction:column;gap:3px;' + (fromUser ? 'align-items:flex-end;' : 'align-items:flex-start;');
    w.innerHTML = fromUser
      ? `<div class="msg-user">${renderMarkdown(text)}</div><span class="msg-time">${timeLabel()}</span>`
      : `<div style="display:flex;align-items:flex-start;gap:7px;">${botAvatar()}<div><div class="msg-bot">${renderMarkdown(text)}</div><span class="msg-time" style="padding-left:3px;">${timeLabel()}</span></div></div>`;
    history.appendChild(w);
    if (messages) messages.scrollTop = messages.scrollHeight;
  }
  function showTyping() {
    const history  = document.getElementById('chat-history');
    const messages = document.getElementById('chat-messages');
    if (!history) return;
    const el = document.createElement('div');
    el.id = 'typing-indicator'; el.className = 'msg-row';
    el.style.cssText = 'display:flex;align-items:flex-start;gap:7px;';
    el.innerHTML = `${botAvatar()}<div class="msg-bot" style="padding:10px 14px;display:flex;gap:4px;align-items:center;"><span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span></div>`;
    history.appendChild(el);
    if (messages) messages.scrollTop = messages.scrollHeight;
  }
  function hideTyping() { const el = document.getElementById('typing-indicator'); if (el) el.remove(); }

  function showTransferCard() {
    const history  = document.getElementById('chat-history');
    const messages = document.getElementById('chat-messages');
    if (!history) return;
    const card = document.createElement('div');
    card.className = 'msg-row'; card.style.paddingLeft = '34px';
    card.innerHTML = `<div class="transfer-card"><div class="transfer-card-title"><i class="fas fa-circle-check" style="color:#1a5fa8;"></i> Consulta transferida exitosamente</div><p style="font-size:.78rem;color:#374151;margin-bottom:12px;line-height:1.5;">Un asesor recibió tu información y se pondrá en contacto contigo pronto.</p><div style="display:flex;gap:8px;flex-wrap:wrap;"><button class="transfer-btn transfer-btn-primary" onclick="doResetChat()"><i class="fas fa-rotate-right"></i> Nueva consulta</button><button class="transfer-btn transfer-btn-secondary" onclick="closeChatWindow()"><i class="fas fa-xmark"></i> Cerrar chat</button></div></div>`;
    history.appendChild(card);
    if (messages) messages.scrollTop = messages.scrollHeight;
  }
  function buildQuickReplies() {
    const qr = document.createElement('div');
    qr.id = 'quick-replies';
    qr.style.cssText = 'display:flex;flex-wrap:wrap;gap:6px;padding-left:34px;';
    qr.innerHTML = `
      <button class="qr-chip" onclick="quickReply('¿Qué servicios ofrecen?')"><i class="fas fa-water" style="font-size:.6rem;"></i>Servicios</button>
      <button class="qr-chip" onclick="quickReply('Necesito estudios marinos')"><i class="fas fa-microscope" style="font-size:.6rem;"></i>Est. Marinos</button>
      <button class="qr-chip" onclick="quickReply('¿Cuáles son sus precios?')"><i class="fas fa-tag" style="font-size:.6rem;"></i>Precios</button>
      <button class="qr-chip" onclick="quickReply('¿Cómo los contacto?')"><i class="fas fa-phone" style="font-size:.6rem;"></i>Contacto</button>
    `;
    return qr;
  }

  window.sendChatMessage = function(override) {
    const input   = document.getElementById('chat-input');
    const message = override || (input && input.value.trim());
    if (!message) return;
    const qr = document.getElementById('quick-replies');
    if (qr) qr.remove();
    appendMessage(message, true);
    if (!override && input) { input.value = ''; input.focus(); }
    showTyping();
    fetch(sendUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8', 'X-CSRFToken': getCookie('csrftoken'), 'X-Requested-With': 'XMLHttpRequest' },
      body: new URLSearchParams({ message })
    })
    .then(r => r.json())
    .then(data => {
      hideTyping();
      if (!data.ok) { appendMessage(data.error || 'No se pudo obtener respuesta.', false); return; }
      const reply = data.reply || '';
      appendMessage(reply, false);
      if (['conectarte con un asesor','asesor para finalizar','en breve te contactarán','transferido'].some(k => reply.toLowerCase().includes(k)))
        setTimeout(showTransferCard, 800);
    })
    .catch(() => { hideTyping(); appendMessage('Error de conexión. Inténtalo de nuevo.', false); });
  };

  window.quickReply = function(msg) {
    const qr = document.getElementById('quick-replies');
    if (qr) qr.remove();
    window.sendChatMessage(msg);
  };
  window.doResetChat = function() {
    fetch(resetUrl, { method: 'POST', headers: { 'X-CSRFToken': getCookie('csrftoken'), 'X-Requested-With': 'XMLHttpRequest' } })
    .finally(() => {
      const history = document.getElementById('chat-history');
      if (history) {
        history.innerHTML = '';
        appendMessage(window.CHAT_WELCOME || '¡Hola de nuevo! ¿En qué puedo ayudarte hoy?', false);
        history.appendChild(buildQuickReplies());
      }
    });
  };

  window.openChat = function() {
    document.getElementById('chat-cta')?.classList.add('hidden');
    const chatWin = document.getElementById('chat-window');
    if (chatWin) {
      chatWin.classList.remove('hidden');
      chatWin.classList.add('fullscreen');
    }
    document.getElementById('chat-button')?.classList.add('active');
    const iconO = document.getElementById('chat-icon-open');
    const iconC = document.getElementById('chat-icon-close');
    if (iconO) iconO.style.display = 'none';
    if (iconC) iconC.style.display = 'block';
    document.getElementById('chat-input')?.focus();
  };
  window.closeChatWindow = function() {
    document.getElementById('chat-window')?.classList.add('hidden');
    document.getElementById('chat-button')?.classList.remove('active');
    const iconO = document.getElementById('chat-icon-open');
    const iconC = document.getElementById('chat-icon-close');
    if (iconO) iconO.style.display = 'block';
    if (iconC) iconC.style.display = 'none';
  };

  const chatBtn  = document.getElementById('chat-button');
  const closeBtn = document.getElementById('close-chat');
  const resetBtn = document.getElementById('reset-chat');
  const toggleFs = document.getElementById('toggle-fullscreen');
  const chatInput= document.getElementById('chat-input');
  const chatSend = document.getElementById('chat-send');

  chatBtn  && chatBtn.addEventListener('click', () => {
    const win = document.getElementById('chat-window');
    if (win && win.classList.contains('hidden')) window.openChat();
    else window.closeChatWindow();
  });
  closeBtn && closeBtn.addEventListener('click', window.closeChatWindow);
  resetBtn && resetBtn.addEventListener('click', window.doResetChat);
  chatInput && chatInput.addEventListener('keydown', e => { if (e.key === 'Enter') window.sendChatMessage(); });
  chatSend  && chatSend.addEventListener('click',  () => window.sendChatMessage());

  if (toggleFs) {
    toggleFs.addEventListener('click', () => {
      const win = document.getElementById('chat-window');
      if (!win) return;
      win.classList.toggle('fullscreen');
      toggleFs.innerHTML = win.classList.contains('fullscreen')
        ? '<i class="fas fa-compress"></i>'
        : '<i class="fas fa-expand"></i>';
    });
  }

  /* ══ 16. SMOOTH SCROLL ════════════════════════════════ */
  document.querySelectorAll('a[href^="#"]').forEach(link => {
    link.addEventListener('click', e => {
      const target = document.querySelector(link.getAttribute('href'));
      if (!target) return;
      e.preventDefault();
      window.scrollTo({ top: target.getBoundingClientRect().top + window.scrollY - 80, behavior: 'smooth' });
    });
  });

}); // fin DOMContentLoaded