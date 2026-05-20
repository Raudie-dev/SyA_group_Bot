/* ============================================================
   SyA Group Chile · main.js  — Rev. 2026-C
   - Navbar scroll
   - Mobile nav
   - Hero Carousel
   - Carrusel infinito de clientes
   - Chat widget con Django backend
   - Scroll reveal
   - Inyección de SVG topográfico en .topo-canvas
   ============================================================ */

document.addEventListener('DOMContentLoaded', () => {

  /* ── 1. NAVBAR SCROLL ─────────────────────────────── */
  const navbar = document.getElementById('navbar');
  if (navbar) {
    window.addEventListener('scroll', () => {
      navbar.classList.toggle('solid', window.scrollY > 50);
    }, { passive: true });
  }

  /* ── 2. MOBILE NAV ────────────────────────────────── */
  const navDesktop    = document.getElementById('nav-links-desktop');
  const navToggle     = document.getElementById('nav-toggle');
  const navMobilePanel = document.getElementById('navMobilePanel');

  function closeMobileNav() {
    if (navMobilePanel) navMobilePanel.classList.remove('open');
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
    navMobilePanel.querySelectorAll('a[href^="#"]').forEach(link => {
      link.addEventListener('click', closeMobileNav);
    });
  }

  /* ── 3. HERO CAROUSEL ─────────────────────────────── */
  const track   = document.getElementById('cTrack');
  const cBar    = document.getElementById('cBar');
  const ctrlCur = document.getElementById('cNumCur');
  const btnPrev = document.getElementById('ctrlPrev');
  const btnNext = document.getElementById('ctrlNext');

  if (track) {
    const slides = Array.from(track.querySelectorAll('.c-slide'));
    const N      = slides.length;
    const DELAY  = 6200;
    let cur = 0, timer = null, rafId = null, rafStart = null;

    const barItems = cBar ? Array.from(cBar.querySelectorAll('.c-bar-item')) : [];
    barItems.forEach(item => {
      const idx = parseInt(item.getAttribute('data-idx'), 10);
      item.addEventListener('click', () => goTo(idx));
    });

    function getProgBar(idx) {
      if (!barItems[idx]) return null;
      return barItems[idx].querySelector('.c-bar-prog');
    }
    function resetAllProgBars() {
      barItems.forEach(item => {
        const pb = item.querySelector('.c-bar-prog');
        if (pb) { pb.style.transition = 'none'; pb.style.width = '0%'; }
      });
    }
    function startProg(idx) {
      cancelAnimationFrame(rafId);
      resetAllProgBars();
      const pb = getProgBar(idx);
      if (!pb) return;
      rafStart = performance.now();
      function step(now) {
        const pct = Math.min(((now - rafStart) / DELAY) * 100, 100);
        pb.style.width = pct + '%';
        if (pct < 100) rafId = requestAnimationFrame(step);
      }
      rafId = requestAnimationFrame(step);
    }
    function pad(n) { return String(n + 1).padStart(2, '0'); }
    function updateUI(idx) {
      slides.forEach((s, i) => s.classList.toggle('active', i === idx));
      barItems.forEach((item, i) => item.classList.toggle('active', i === idx));
      track.style.transform = `translateX(-${idx * 100}%)`;
      if (ctrlCur) ctrlCur.textContent = pad(idx);
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

    if (btnNext) btnNext.addEventListener('click', () => goTo(cur + 1));
    if (btnPrev) btnPrev.addEventListener('click', () => goTo(cur - 1));

    let touchStartX = 0;
    track.addEventListener('touchstart', e => { touchStartX = e.touches[0].clientX; }, { passive: true });
    track.addEventListener('touchend', e => {
      const dx = e.changedTouches[0].clientX - touchStartX;
      if (Math.abs(dx) > 50) goTo(dx < 0 ? cur + 1 : cur - 1);
    }, { passive: true });

    document.addEventListener('visibilitychange', () => {
      if (document.hidden) { clearInterval(timer); cancelAnimationFrame(rafId); }
      else goTo(cur);
    });
  }

  /* ── 4. CARRUSEL INFINITO DE CLIENTES ─────────────── */
  function createInfiniteCarousel(trackEl) {
    if (!trackEl) return;

    const speed = 0.04; // px/ms
    const items = Array.from(trackEl.children);
    if (!items.length) return;

    /* Duplicar ítems para el loop */
    items.map(item => item.cloneNode(true)).forEach(clone => trackEl.appendChild(clone));

    let offset    = 0;
    let prevTime  = null;
    let halfWidth = trackEl.scrollWidth / 2 || 1;
    let isDragging = false, startX = 0, startOffset = 0;

    trackEl.style.display    = 'flex';
    trackEl.style.flexWrap   = 'nowrap';
    trackEl.style.willChange = 'transform';
    trackEl.style.cursor     = 'grab';

    const wrapper = trackEl.closest('.brands-carousel-wrapper');
    if (wrapper) wrapper.style.cursor = 'grab';

    function normalize(val) {
      while (val >= halfWidth) val -= halfWidth;
      while (val < 0)          val += halfWidth;
      return val;
    }

    function animate(ts) {
      if (prevTime === null) prevTime = ts;
      const delta = ts - prevTime;
      prevTime = ts;
      halfWidth = trackEl.scrollWidth / 2 || 1;
      if (!isDragging) {
        offset = normalize(offset + delta * speed);
        trackEl.style.transform = `translateX(-${offset}px)`;
      }
      requestAnimationFrame(animate);
    }

    function endDrag(e) {
      if (!isDragging) return;
      isDragging = false;
      trackEl.style.cursor = 'grab';
      if (wrapper) wrapper.style.cursor = 'grab';
      if (e && e.pointerId) { try { trackEl.releasePointerCapture(e.pointerId); } catch(_){} }
    }

    trackEl.addEventListener('pointerdown', e => {
      isDragging = true;
      startX = e.clientX;
      startOffset = offset;
      prevTime = e.timeStamp;
      try { trackEl.setPointerCapture(e.pointerId); } catch(_){}
      trackEl.style.cursor = 'grabbing';
      if (wrapper) wrapper.style.cursor = 'grabbing';
    });
    trackEl.addEventListener('pointermove', e => {
      if (!isDragging) return;
      offset = normalize(startOffset - (e.clientX - startX));
      trackEl.style.transform = `translateX(-${offset}px)`;
    });
    trackEl.addEventListener('pointerup',     endDrag);
    trackEl.addEventListener('pointercancel', endDrag);
    trackEl.addEventListener('pointerleave',  endDrag);

    requestAnimationFrame(animate);
  }

  /* Iniciar carrusel de clientes — busca el track directamente */
  const clientesTrack = document.getElementById('clientesCarouselTrackLTR');
  createInfiniteCarousel(clientesTrack);

  /* ── 5. SCROLL REVEAL ─────────────────────────────── */
  const revealEls = document.querySelectorAll('.reveal');
  if ('IntersectionObserver' in window) {
    const revealObs = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
          revealObs.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });
    revealEls.forEach(el => revealObs.observe(el));
  } else {
    revealEls.forEach(el => el.classList.add('visible'));
  }

  /* ── 6. INYECCIÓN SVG TOPOGRÁFICO ────────────────── */
  /*
     Genera un SVG de curvas de nivel tipo croquis cartográfico.
     Se reutiliza en todos los .topo-canvas de la página.
     El color cambia según la clase: topo-light (azul), topo-dark (blanco), topo-warm (naranja).
  */
  function buildTopoSVG(colorStroke) {
    // Puntos de control para ~18 curvas de nivel concéntricas
    // con variaciones orgánicas para parecer un relieve real
    const W = 1440, H = 800;
    const cx = W * 0.38, cy = H * 0.48; // centro del "pico" principal
    const cx2 = W * 0.72, cy2 = H * 0.32; // pico secundario
    const cx3 = W * 0.18, cy3 = H * 0.72; // pico terciario

    let paths = '';

    // Función para generar una curva de nivel elíptica con ruido
    function noisyEllipse(ocx, ocy, rx, ry, seed, label) {
      const pts = 28;
      const points = [];
      for (let i = 0; i <= pts; i++) {
        const a  = (i / pts) * Math.PI * 2;
        // añadir ruido seudo-aleatorio basado en seed
        const noise = Math.sin(a * 3.7 + seed) * rx * 0.14
                    + Math.sin(a * 7.1 + seed * 1.3) * ry * 0.09
                    + Math.sin(a * 1.9 + seed * 0.7) * rx * 0.07;
        const nx = ocx + (rx + noise) * Math.cos(a);
        const ny = ocy + (ry + noise * 0.65) * Math.sin(a);
        points.push([nx, ny]);
      }
      // Convertir a SVG path con curvas suaves
      let d = `M ${points[0][0].toFixed(1)} ${points[0][1].toFixed(1)}`;
      for (let i = 1; i < points.length; i++) {
        const prev = points[i - 1];
        const curr = points[i];
        const cpx1 = prev[0] + (curr[0] - (i >= 2 ? points[i-2][0] : prev[0])) * 0.2;
        const cpy1 = prev[1] + (curr[1] - (i >= 2 ? points[i-2][1] : prev[1])) * 0.2;
        const cpx2 = curr[0] - (i < points.length - 1 ? (points[i+1][0] - prev[0]) : 0) * 0.2;
        const cpy2 = curr[1] - (i < points.length - 1 ? (points[i+1][1] - prev[1]) : 0) * 0.2;
        d += ` C ${cpx1.toFixed(1)} ${cpy1.toFixed(1)}, ${cpx2.toFixed(1)} ${cpy2.toFixed(1)}, ${curr[0].toFixed(1)} ${curr[1].toFixed(1)}`;
      }
      d += ' Z';

      let labelTag = '';
      if (label) {
        // Posición de la etiqueta: a la derecha del pico
        const lx = (ocx + rx * 1.05).toFixed(0);
        const ly = ocy.toFixed(0);
        labelTag = `<text x="${lx}" y="${ly}" font-size="11" fill="${colorStroke}" opacity="0.5" font-family="monospace" letter-spacing="0.5">${label}</text>`;
      }
      return `<path d="${d}" fill="none" stroke="${colorStroke}" stroke-width="0.9"/>${labelTag}`;
    }

    // Pico principal — curvas concéntricas
    const levelsMain = [
      { rx: 38,  ry: 28,  seed: 1.1,  lbl: null },
      { rx: 68,  ry: 52,  seed: 2.3,  lbl: '500' },
      { rx: 104, ry: 80,  seed: 3.7,  lbl: null },
      { rx: 145, ry: 112, seed: 5.1,  lbl: '400' },
      { rx: 190, ry: 148, seed: 6.4,  lbl: null },
      { rx: 238, ry: 186, seed: 7.8,  lbl: '300' },
      { rx: 288, ry: 228, seed: 9.2,  lbl: null },
      { rx: 342, ry: 272, seed: 10.5, lbl: '200' },
      { rx: 400, ry: 318, seed: 11.9, lbl: null },
      { rx: 460, ry: 366, seed: 13.2, lbl: '100' },
      { rx: 524, ry: 418, seed: 14.6, lbl: null },
    ];
    levelsMain.forEach(l => {
      paths += noisyEllipse(cx, cy, l.rx, l.ry, l.seed, l.lbl);
    });

    // Pico secundario — más pequeño, desplazado
    const levelsSec = [
      { rx: 24,  ry: 18,  seed: 2.2,  lbl: null },
      { rx: 48,  ry: 36,  seed: 3.8,  lbl: '450' },
      { rx: 76,  ry: 58,  seed: 5.4,  lbl: null },
      { rx: 108, ry: 82,  seed: 7.0,  lbl: '350' },
      { rx: 146, ry: 110, seed: 8.6,  lbl: null },
      { rx: 186, ry: 142, seed: 10.2, lbl: '250' },
    ];
    levelsSec.forEach(l => {
      paths += noisyEllipse(cx2, cy2, l.rx, l.ry, l.seed, l.lbl);
    });

    // Pico terciario — pequeño
    const levelsTer = [
      { rx: 18,  ry: 14,  seed: 4.1,  lbl: null },
      { rx: 36,  ry: 28,  seed: 5.9,  lbl: '300' },
      { rx: 58,  ry: 44,  seed: 7.7,  lbl: null },
      { rx: 82,  ry: 62,  seed: 9.5,  lbl: '200' },
      { rx: 108, ry: 82,  seed: 11.3, lbl: null },
    ];
    levelsTer.forEach(l => {
      paths += noisyEllipse(cx3, cy3, l.rx, l.ry, l.seed, l.lbl);
    });

    // Algunas líneas de valles interrumpidos (punteadas)
    const dashes = [
      `M 520 ${H*0.62} Q 620 ${H*0.55} 720 ${H*0.60} Q 820 ${H*0.65} 920 ${H*0.58}`,
      `M 80  ${H*0.35} Q 140 ${H*0.28} 200 ${H*0.33}`,
      `M ${W*0.6} ${H*0.78} Q ${W*0.68} ${H*0.72} ${W*0.78} ${H*0.76}`,
    ];
    dashes.forEach(d => {
      paths += `<path d="${d}" fill="none" stroke="${colorStroke}" stroke-width="0.7" stroke-dasharray="4 5" opacity="0.6"/>`;
    });

    return `<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid slice">${paths}</svg>`;
  }

  // Inyectar SVG en cada .topo-canvas
  document.querySelectorAll('.topo-canvas').forEach(canvas => {
    let color = '#1249A0'; // azul por defecto (topo-light)
    if (canvas.classList.contains('topo-dark'))  color = '#FFFFFF';
    if (canvas.classList.contains('topo-warm'))  color = '#E67E22';
    canvas.innerHTML = buildTopoSVG(color);
  });

  /* También inyectar en .topo-cta-bg (misma lógica, siempre blanco) */
  document.querySelectorAll('.topo-cta-bg').forEach(bg => {
    bg.innerHTML = buildTopoSVG('#FFFFFF');
  });

  /* ── 7. CERT MODAL ────────────────────────────────── */
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

  /* ── 8. CHAT WIDGET ───────────────────────────────── */
  const sendUrl  = window.CHAT_SEND_URL  || '/chat/public/';
  const resetUrl = window.CHAT_RESET_URL || '/chat/reset/';

  function getCookie(name) {
    let val = null;
    document.cookie.split(';').forEach(c => {
      c = c.trim();
      if (c.startsWith(name + '=')) val = decodeURIComponent(c.slice(name.length + 1));
    });
    return val;
  }

  function timeLabel() {
    const n = new Date();
    return n.getHours().toString().padStart(2,'0') + ':' + n.getMinutes().toString().padStart(2,'0');
  }

  function renderMarkdown(text) {
    return text
      .replace(/\*\*(.*?)\*\*/g,   '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g,       '<em>$1</em>')
      .replace(/^- (.+)$/gm,       '<li>$1</li>')
      .replace(/(<li>.*<\/li>)/gs, '<ul style="margin:6px 0 6px 16px;padding:0;list-style:disc;">$1</ul>')
      .replace(/\n{2,}/g, '<br><br>').replace(/\n/g, '<br>');
  }

  function botAvatar() {
    return `<div style="width:26px;height:26px;border-radius:50%;background:linear-gradient(135deg,#0a1628,#0e4d6e);display:flex;align-items:center;justify-content:center;flex-shrink:0;margin-top:2px;"><i class="fas fa-water" style="color:#4ecdc4;font-size:.6rem;"></i></div>`;
  }

  function appendMessage(text, fromUser) {
    const history  = document.getElementById('chat-history');
    const messages = document.getElementById('chat-messages');
    if (!history || !messages) return;
    const w = document.createElement('div');
    w.className = 'msg-row';
    w.style.cssText = 'display:flex;flex-direction:column;gap:3px;' + (fromUser ? 'align-items:flex-end;' : 'align-items:flex-start;');
    w.innerHTML = fromUser
      ? `<div class="msg-user">${renderMarkdown(text)}</div><span class="msg-time">${timeLabel()}</span>`
      : `<div style="display:flex;align-items:flex-start;gap:7px;">${botAvatar()}<div><div class="msg-bot">${renderMarkdown(text)}</div><span class="msg-time" style="padding-left:3px;">${timeLabel()}</span></div></div>`;
    history.appendChild(w);
    messages.scrollTop = messages.scrollHeight;
  }

  function showTyping() {
    const history  = document.getElementById('chat-history');
    const messages = document.getElementById('chat-messages');
    if (!history) return;
    const el = document.createElement('div');
    el.id = 'typing-indicator';
    el.className = 'msg-row';
    el.style.cssText = 'display:flex;align-items:flex-start;gap:7px;';
    el.innerHTML = `${botAvatar()}<div class="msg-bot" style="padding:10px 14px;display:flex;gap:4px;align-items:center;"><span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span></div>`;
    history.appendChild(el);
    if (messages) messages.scrollTop = messages.scrollHeight;
  }

  function hideTyping() {
    const el = document.getElementById('typing-indicator');
    if (el) el.remove();
  }

  function showTransferCard() {
    const history  = document.getElementById('chat-history');
    const messages = document.getElementById('chat-messages');
    if (!history) return;
    const card = document.createElement('div');
    card.className = 'msg-row';
    card.style.paddingLeft = '34px';
    card.innerHTML = `<div class="transfer-card"><div class="transfer-card-title"><i class="fas fa-circle-check" style="color:#1a5fa8;"></i> Consulta transferida exitosamente</div><p style="font-size:.78rem;color:#374151;margin-bottom:12px;line-height:1.5;">Un asesor recibió tu información y se pondrá en contacto contigo pronto.</p><div style="display:flex;gap:8px;flex-wrap:wrap;"><button class="transfer-btn transfer-btn-primary" onclick="doResetChat()"><i class="fas fa-rotate-right"></i> Nueva consulta</button><button class="transfer-btn transfer-btn-secondary" onclick="closeChatWindow()"><i class="fas fa-xmark"></i> Cerrar chat</button></div></div>`;
    history.appendChild(card);
    if (messages) messages.scrollTop = messages.scrollHeight;
  }

  function buildQuickReplies() {
    const qrDiv = document.createElement('div');
    qrDiv.id = 'quick-replies';
    qrDiv.style.cssText = 'display:flex;flex-wrap:wrap;gap:6px;padding-left:34px;';
    qrDiv.innerHTML = `<button class="qr-chip" onclick="quickReply('¿Qué servicios ofrecen?')"><i class="fas fa-water" style="font-size:.6rem;"></i>Servicios</button><button class="qr-chip" onclick="quickReply('Necesito estudios marinos')"><i class="fas fa-microscope" style="font-size:.6rem;"></i>Est. Marinos</button><button class="qr-chip" onclick="quickReply('¿Cuáles son sus precios?')"><i class="fas fa-tag" style="font-size:.6rem;"></i>Precios</button><button class="qr-chip" onclick="quickReply('¿Cómo los contacto?')"><i class="fas fa-phone" style="font-size:.6rem;"></i>Contacto</button>`;
    return qrDiv;
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
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
        'X-CSRFToken': getCookie('csrftoken'),
        'X-Requested-With': 'XMLHttpRequest'
      },
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

  window.doResetChat = async function() {
    await fetch(resetUrl, { method: 'POST', headers: { 'X-CSRFToken': getCookie('csrftoken') } });
    const history = document.getElementById('chat-history');
    if (!history) return;
    history.innerHTML = '';
    const welcomeMsg = window.CHAT_WELCOME || '¡Hola! ¿En qué puedo ayudarte hoy?';
    const row = document.createElement('div');
    row.className = 'msg-row';
    row.style.cssText = 'display:flex;align-items:flex-start;gap:8px;';
    row.innerHTML = `${botAvatar()}<div><div class="msg-bot">${welcomeMsg}</div><p class="msg-time" style="padding-left:3px;">Ahora mismo</p></div>`;
    history.appendChild(row);
    history.appendChild(buildQuickReplies());
    const msgs = document.getElementById('chat-messages');
    if (msgs) msgs.scrollTop = 0;
  };

  function updateChatFullscreenState(isFull) {
    const cw        = document.getElementById('chat-window');
    const toggleBtn = document.getElementById('toggle-fullscreen');
    if (!cw || !toggleBtn) return;
    cw.classList.toggle('fullscreen', isFull);
    const icon = toggleBtn.querySelector('i');
    if (icon) icon.className = isFull ? 'fas fa-compress' : 'fas fa-expand';
    toggleBtn.title = isFull ? 'Restaurar tamaño' : 'Ampliar chat';
    document.body.classList.toggle('chat-fullscreen', isFull);
  }

  window.toggleChatFullscreen = function() {
    const cw = document.getElementById('chat-window');
    if (cw) updateChatFullscreenState(!cw.classList.contains('fullscreen'));
  };

  window.closeChatWindow = function() {
    updateChatFullscreenState(false);
    const cw  = document.getElementById('chat-window');      if (cw)  cw.classList.add('hidden');
    const ico = document.getElementById('chat-icon-open');   if (ico) ico.style.display = 'block';
    const icx = document.getElementById('chat-icon-close');  if (icx) icx.style.display = 'none';
  };

  window.openChat = function() {
    const cw  = document.getElementById('chat-window');      if (cw)  cw.classList.remove('hidden');
    const cta = document.getElementById('chat-cta');         if (cta) cta.classList.add('hidden');
    const ico = document.getElementById('chat-icon-open');   if (ico) ico.style.display = 'none';
    const icx = document.getElementById('chat-icon-close');  if (icx) icx.style.display = 'block';
    const inp = document.getElementById('chat-input');       if (inp) inp.focus();
  };

  window.quickReply = text => window.sendChatMessage(text);

  const chatBtn       = document.getElementById('chat-button');
  const chatWin       = document.getElementById('chat-window');
  const closeBtn      = document.getElementById('close-chat');
  const resetBtn      = document.getElementById('reset-chat');
  const fullscreenBtn = document.getElementById('toggle-fullscreen');
  const sendBtn       = document.getElementById('chat-send');
  const chatInput     = document.getElementById('chat-input');

  if (chatBtn) chatBtn.addEventListener('click', () =>
    chatWin && chatWin.classList.contains('hidden') ? window.openChat() : window.closeChatWindow());
  if (fullscreenBtn) fullscreenBtn.addEventListener('click', window.toggleChatFullscreen);
  if (closeBtn)  closeBtn.addEventListener('click', window.closeChatWindow);
  if (resetBtn)  resetBtn.addEventListener('click', window.doResetChat);
  if (sendBtn)   sendBtn.addEventListener('click', () => window.sendChatMessage());
  if (chatInput) chatInput.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); window.sendChatMessage(); }
  });

}); // END DOMContentLoaded