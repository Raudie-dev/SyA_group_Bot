(function(){
  if (typeof window.p5 === 'undefined') return;

  /* ─── Paleta y semillas fijas por clase de sección ─── */
  const SECTION_CONFIG = {
    'cert-full-section': { color: '#E67E22', seed: 42 },
    'geo-section':       { color: '#E67E22', seed: 42 },
    'topo-cta-strip':    { color: '#FFFFFF', seed: 77 },
    'services-section':  { color: '#1249A0', seed: 11 },
    'exp-section':       { color: '#1249A0', seed: 11 },
  };
  const DEFAULT_CONFIG = { color: '#1249A0', seed: 11 };

  const resolution = 4;
  const noiseScale = 0.0032;
  const numLevels  = 18;

  function getSectionConfig(el) {
    const section = el.closest('section') || el.parentElement;
    if (!section) return DEFAULT_CONFIG;
    for (const cls of section.classList) {
      if (SECTION_CONFIG[cls]) return SECTION_CONFIG[cls];
    }
    return DEFAULT_CONFIG;
  }

  function createReliefOnElement(el) {
    if (!el || el.__reliefCreated) return;
    el.__reliefCreated = true;

    const cfg = getSectionConfig(el);

    const sketch = (p) => {
      let cvs;

      p.setup = function() {
        /* Tomar dimensiones del contenedor padre, no del placeholder */
        const parent = el.parentElement || el;
        const w = parent.offsetWidth  || el.clientWidth  || 1200;
        const h = parent.offsetHeight || el.clientHeight || 600;

        cvs = p.createCanvas(w, h);
        cvs.parent(el);

        const c = cvs.elt;
        c.style.position = 'absolute';
        c.style.top = '0';
        c.style.left         = '0';
        c.style.width        = '100%';
        c.style.height       = '100%';
        c.style.pointerEvents = 'none';
        c.style.opacity      = String(cfg.opacity);
        c.style.zIndex       = '0';

        p.noLoop();
        p.redraw();
      };

      p.draw = function() {
        /* Semilla fija → mismo patrón siempre */
        p.noiseSeed(cfg.seed);

        p.clear();
        p.background(0, 0, 0, 0);
        p.stroke(cfg.color);
        p.strokeWeight(1.1);
        p.noFill();
        p.strokeJoin(p.ROUND);
        p.strokeCap(p.ROUND);

        const levels = [];
        for (let i = 1; i <= numLevels; i++) levels.push(i / (numLevels + 1));

        for (let x = 0; x < p.width; x += resolution) {
          for (let y = 0; y < p.height; y += resolution) {
            const n1 = p.noise( x * noiseScale,  y * noiseScale);
            const n2 = p.noise((x + resolution) * noiseScale,  y * noiseScale);
            const n3 = p.noise((x + resolution) * noiseScale, (y + resolution) * noiseScale);
            const n4 = p.noise( x * noiseScale, (y + resolution) * noiseScale);

            for (const lvl of levels) {
              const b1 = n1 >= lvl ? 1 : 0;
              const b2 = n2 >= lvl ? 1 : 0;
              const b3 = n3 >= lvl ? 1 : 0;
              const b4 = n4 >= lvl ? 1 : 0;
              const sum = b1 + b2 + b3 + b4;

              if (sum > 0 && sum < 4) {
                const xA = x + resolution / 2, yA = y;
                const xB = x + resolution, yB = y + resolution / 2;
                const xC = x + resolution / 2, yC = y + resolution;
                const xD = x, yD = y + resolution / 2;

                if (b1 !== b2) p.line(xA, yA, xD, yD);
                if (b2 !== b3) p.line(xA, yA, xB, yB);
                if (b3 !== b4) p.line(xB, yB, xC, yC);
                if (b4 !== b1) p.line(xC, yC, xD, yD);
              }
            }
          }
        }
      };

      p.windowResized = function() {
        if (!cvs) return;
        const parent = el.parentElement || el;
        const w = parent.offsetWidth  || 1200;
        const h = parent.offsetHeight || 600;
        p.resizeCanvas(w, h);
        p.redraw();
      };
    };

    try {
      new p5(sketch, el);
    } catch (e) {
      console.error('SY relief: failed for', el, e);
    }
  }

  function observePlaceholders() {
    const opts = { root: null, rootMargin: '0px', threshold: 0.04 };

    const io = new IntersectionObserver((entries, observer) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          createReliefOnElement(entry.target);
          observer.unobserve(entry.target);
        }
      });
    }, opts);

    document.querySelectorAll('.relief-placeholder').forEach(el => {
      io.observe(el);
    });

    /* Fallback: crear para los que ya están en viewport al cargar */
    window.addEventListener('load', () => {
      document.querySelectorAll('.relief-placeholder').forEach(el => {
        const rect = el.getBoundingClientRect();
        if (rect.top < window.innerHeight && rect.bottom > 0) {
          createReliefOnElement(el);
        }
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', observePlaceholders);
  } else {
    observePlaceholders();
  }
})();
