(function(){
  if (typeof window.p5 === 'undefined') {
    console.warn('[Relief] p5.js not loaded, waiting...');
    window.addEventListener('load', arguments.callee);
    return;
  }

  const resolution = 6;
  const noiseScale = 0.0025;
  const numLevels = 8;
  const instances = [];

  function createReliefOnElement(el){
    if (!el || el.__reliefCreated) return;
    el.__reliefCreated = true;

    // Ensure element is positioned relatively for canvas overlay
    if (getComputedStyle(el).position === 'static') {
      el.style.position = 'relative';
    }

    const sketch = (p) => {
      let cvs;
      
      p.setup = function(){
        const w = el.clientWidth || 300;
        const h = el.clientHeight || 200;
        cvs = p.createCanvas(w, h);
        cvs.parent(el);
        cvs.style.position = 'absolute';
        cvs.style.top = '0';
        cvs.style.left = '0';
        cvs.style.pointerEvents = 'none';
        cvs.style.opacity = '0.4';
        cvs.style.mixBlendMode = 'overlay';
        cvs.style.zIndex = '1';
        p.noLoop();
        p.redraw();
      };

      p.draw = function(){
        p.clear();
        const isLight = el.dataset.reliefTheme === 'light';
        const strokeColor = isLight ? 'rgba(255,255,255,0.15)' : 'rgba(0,0,0,0.08)';
        p.stroke(strokeColor);
        p.strokeWeight(0.5);
        p.noFill();
        p.strokeJoin(p.ROUND);
        p.strokeCap(p.ROUND);

        const levels = [];
        for (let i = 1; i <= numLevels; i++) {
          levels.push(i / (numLevels + 1));
        }

        for (let x = 0; x < p.width; x += resolution) {
          for (let y = 0; y < p.height; y += resolution) {
            const n1 = p.noise(x * noiseScale, y * noiseScale);
            const n2 = p.noise((x + resolution) * noiseScale, y * noiseScale);
            const n3 = p.noise((x + resolution) * noiseScale, (y + resolution) * noiseScale);
            const n4 = p.noise(x * noiseScale, (y + resolution) * noiseScale);

            for (const lvl of levels) {
              const b1 = n1 >= lvl ? 1 : 0;
              const b2 = n2 >= lvl ? 1 : 0;
              const b3 = n3 >= lvl ? 1 : 0;
              const b4 = n4 >= lvl ? 1 : 0;
              const sum = b1 + b2 + b3 + b4;

              if (sum > 0 && sum < 4) {
                const xA = x + resolution / 2;
                const yA = y;
                const xB = x + resolution;
                const yB = y + resolution / 2;
                const xC = x + resolution / 2;
                const yC = y + resolution;
                const xD = x;
                const yD = y + resolution / 2;

                if (b1 !== b2) p.line(xA, yA, xB, yB);
                if (b2 !== b3) p.line(xB, yB, xC, yC);
                if (b3 !== b4) p.line(xC, yC, xD, yD);
                if (b4 !== b1) p.line(xD, yD, xA, yA);
              }
            }
          }
        }
      };

      p.windowResized = function(){
        if (cvs && el.offsetParent) {
          const w = el.clientWidth || 300;
          const h = el.clientHeight || 200;
          p.resizeCanvas(w, h);
          p.redraw();
        }
      };
    };

    try {
      const instance = new p5(sketch, el);
      instances.push({ element: el, instance });
    } catch (e) {
      console.error('[Relief] Failed to create p5 instance:', e);
    }
  }

  function observePlaceholders(){
    const placeholders = document.querySelectorAll('.relief-placeholder');
    
    if (placeholders.length === 0) {
      console.warn('[Relief] No .relief-placeholder elements found');
      return;
    }

    // Use IntersectionObserver for viewport-based loading
    const opts = { root: null, rootMargin: '100px', threshold: 0 };
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const parent = entry.target.parentElement;
          if (parent) {
            createReliefOnElement(parent);
            observer.unobserve(entry.target);
          }
        }
      });
    }, opts);

    placeholders.forEach(el => observer.observe(el));

    // Fallback for immediate visibility
    window.addEventListener('load', () => {
      placeholders.forEach(el => {
        if (!el.parentElement.__reliefCreated) {
          const parent = el.parentElement;
          const rect = parent.getBoundingClientRect();
          if (rect.top < window.innerHeight && rect.bottom > 0) {
            createReliefOnElement(parent);
          }
        }
      });
    });
  }

  // Initialize when p5 is ready
  const initReliefs = () => {
    if (typeof window.p5 !== 'undefined') {
      observePlaceholders();
    } else {
      window.addEventListener('load', initReliefs);
    }
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initReliefs);
  } else {
    initReliefs();
  }
})();