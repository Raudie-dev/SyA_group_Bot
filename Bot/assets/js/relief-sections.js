(function(){
  if (typeof window.p5 === 'undefined') return;

  const resolution = 4;
  const noiseScale = 0.0035;
  const numLevels = 16;

  function createReliefOnElement(el){
    if (!el) return;
    if (el.__reliefCreated) return;
    el.__reliefCreated = true;

    const sketch = (p) => {
      let cvs;
      p.setup = function(){
        cvs = p.createCanvas(el.clientWidth || 300, el.clientHeight || 200);
        cvs.parent(el);
        cvs.style.position = 'absolute';
        cvs.style.top = '0';
        cvs.style.left = '0';
        cvs.style.width = '100%';
        cvs.style.height = '100%';
        cvs.style.pointerEvents = 'none';
        cvs.style.opacity = '0.45';
        cvs.style.mixBlendMode = 'normal';
        cvs.style.zIndex = '0';
        p.noLoop();
        p.redraw();
      };

      p.draw = function(){
        p.clear();
        p.background(0,0,0,0);
        p.stroke('#222222');
        p.strokeWeight(1.2);
        p.noFill();
        p.strokeJoin(p.ROUND);
        p.strokeCap(p.ROUND);
        const levels = [];
        for (let i=1;i<=numLevels;i++) levels.push(i/(numLevels+1));
        for (let x=0;x<p.width;x+=resolution){
          for (let y=0;y<p.height;y+=resolution){
            let n1 = p.noise(x*noiseScale, y*noiseScale);
            let n2 = p.noise((x+resolution)*noiseScale, y*noiseScale);
            let n3 = p.noise((x+resolution)*noiseScale, (y+resolution)*noiseScale);
            let n4 = p.noise(x*noiseScale, (y+resolution)*noiseScale);
            for (let lvl of levels){
              let b1 = n1 >= lvl ? 1 : 0;
              let b2 = n2 >= lvl ? 1 : 0;
              let b3 = n3 >= lvl ? 1 : 0;
              let b4 = n4 >= lvl ? 1 : 0;
              let sum = b1+b2+b3+b4;
              if (sum>0 && sum<4){
                let xA = x + resolution/2;
                let yA = y;
                let xB = x + resolution;
                let yB = y + resolution/2;
                let xC = x + resolution/2;
                let yC = y + resolution;
                let xD = x;
                let yD = y + resolution/2;
                if (b1 !== b2) p.line(xA,yA,xD,yD);
                if (b2 !== b3) p.line(xA,yA,xB,yB);
                if (b3 !== b4) p.line(xB,yB,xC,yC);
                if (b4 !== b1) p.line(xC,yC,xD,yD);
              }
            }
          }
        }
      };

      p.windowResized = function(){
        if (cvs) {
          p.resizeCanvas(el.clientWidth || 300, el.clientHeight || 200);
          p.redraw();
        }
      };
    };

    // create a new p5 instance attached to the element
    try{
      new p5(sketch, el);
    }catch(e){
      console.error('Failed to create relief p5 instance for', el, e);
    }
  }

  function observePlaceholders(){
    const opts = { root: null, rootMargin: '0px', threshold: 0.05 };
    const io = new IntersectionObserver((entries, observer) => {
      entries.forEach(entry => {
        if (entry.isIntersecting){
          createReliefOnElement(entry.target);
          observer.unobserve(entry.target);
        }
      });
    }, opts);

    document.querySelectorAll('.relief-placeholder').forEach(el => {
      // ensure placeholder has height so canvas can size
      if (!el.style.minHeight) el.style.minHeight = '120px';
      io.observe(el);
    });

    // fallback: create for visible ones on load
    window.addEventListener('load', () => {
      document.querySelectorAll('.relief-placeholder').forEach(el => {
        const rect = el.getBoundingClientRect();
        if (rect.top < window.innerHeight && rect.bottom > 0) createReliefOnElement(el);
      });
    });

    // resize handling: debounce resize and call windowResized on all created instances
    let rTO;
    window.addEventListener('resize', ()=>{
      clearTimeout(rTO);
      rTO = setTimeout(()=>{
        // p5 instances expose global p5 instances on window._p5Instances? Not reliable.
        // Trigger redraw by dispatching a custom event handled by each canvas via window.resize.
        window.dispatchEvent(new Event('resize'));
      }, 200);
    });
  }

  // init
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', observePlaceholders);
  else observePlaceholders();
})();
