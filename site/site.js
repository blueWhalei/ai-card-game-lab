(function () {
  const root = document.documentElement;
  const storageKey = 'cardlab-theme';

  function currentTheme() {
    const attr = root.getAttribute('data-theme');
    if (attr === 'light' || attr === 'dark') return attr;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  function applyTheme(theme) {
    root.setAttribute('data-theme', theme);
    try {
      localStorage.setItem(storageKey, theme);
    } catch {
      /* private mode */
    }
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', theme === 'dark' ? '#121816' : '#f2f4f3');
    const btn = document.querySelector('[data-theme-toggle]');
    if (btn) {
      const next = theme === 'dark' ? 'light' : 'dark';
      btn.setAttribute('aria-pressed', theme === 'dark' ? 'true' : 'false');
      const label = btn.getAttribute('data-label-' + next);
      if (label) btn.setAttribute('aria-label', label);
    }
  }

  applyTheme(currentTheme());

  document.querySelector('[data-theme-toggle]')?.addEventListener('click', function () {
    applyTheme(currentTheme() === 'dark' ? 'light' : 'dark');
  });

  const isWin = /Win/i.test(navigator.platform) || /Windows/i.test(navigator.userAgent);
  const defaultOs = isWin ? 'windows' : 'unix';
  const seg = document.querySelector('[data-os-seg]');
  const blocks = document.querySelectorAll('[data-os-block]');

  function showOs(os) {
    blocks.forEach(function (el) {
      el.hidden = el.getAttribute('data-os-block') !== os;
    });
    seg?.querySelectorAll('button').forEach(function (btn) {
      btn.setAttribute('aria-pressed', btn.getAttribute('data-os') === os ? 'true' : 'false');
    });
  }

  if (seg) {
    showOs(defaultOs);
    seg.addEventListener('click', function (event) {
      const btn = event.target.closest('button[data-os]');
      if (btn) showOs(btn.getAttribute('data-os'));
    });
  }

  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const nav = document.querySelector('.nav');

  function syncNav() {
    nav?.classList.toggle('is-scrolled', window.scrollY > 24);
  }

  syncNav();
  window.addEventListener('scroll', syncNav, { passive: true });

  const riseGroups = [
    '#loop .section-head',
    '#loop .steps li',
    '#gallery .section-head',
    '#gallery .shot',
    '#start .section-head',
    '#start .terminal',
  ];
  const riseNodes = [];

  riseGroups.forEach(function (selector) {
    document.querySelectorAll(selector).forEach(function (el, index) {
      el.classList.add('rise');
      if (el.matches('li, .shot')) {
        el.style.setProperty('--rise-delay', index * 70 + 'ms');
      }
      riseNodes.push(el);
    });
  });

  if (reduceMotion) {
    riseNodes.forEach(function (el) {
      el.classList.add('is-in');
    });
  } else if (riseNodes.length && 'IntersectionObserver' in window) {
    const io = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          entry.target.classList.add('is-in');
          io.unobserve(entry.target);
        });
      },
      { threshold: 0.16, rootMargin: '0px 0px -8% 0px' },
    );
    riseNodes.forEach(function (el) {
      io.observe(el);
    });
  } else {
    riseNodes.forEach(function (el) {
      el.classList.add('is-in');
    });
  }

  const lightbox = document.querySelector('[data-lightbox]');
  const lightboxImg = lightbox?.querySelector('img');
  let leaveTimer = 0;

  function openZoom(src, alt) {
    if (!lightbox || !lightboxImg) return;
    window.clearTimeout(leaveTimer);
    lightboxImg.src = src;
    lightboxImg.alt = alt || '';
    if (typeof lightbox.showModal !== 'function') return;
    lightbox.classList.add('is-leaving');
    lightbox.showModal();
    if (reduceMotion) {
      lightbox.classList.remove('is-leaving');
      return;
    }
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        lightbox.classList.remove('is-leaving');
      });
    });
  }

  function closeZoom() {
    if (!lightbox || !lightbox.open) return;
    window.clearTimeout(leaveTimer);
    if (reduceMotion) {
      lightbox.close();
      if (lightboxImg) lightboxImg.removeAttribute('src');
      return;
    }
    lightbox.classList.add('is-leaving');
    leaveTimer = window.setTimeout(function () {
      lightbox.classList.remove('is-leaving');
      lightbox.close();
      if (lightboxImg) lightboxImg.removeAttribute('src');
    }, 200);
  }

  document.querySelectorAll('[data-zoom]').forEach(function (btn) {
    const img = btn.querySelector('img');
    if (img && !btn.getAttribute('aria-label')) {
      btn.setAttribute('aria-label', img.alt);
    }
    btn.addEventListener('click', function () {
      if (img) openZoom(img.currentSrc || img.src, img.alt);
    });
  });

  lightbox?.addEventListener('click', function (event) {
    if (event.target === lightbox) closeZoom();
  });

  lightbox?.addEventListener('cancel', function (event) {
    event.preventDefault();
    closeZoom();
  });

  document.querySelector('[data-lightbox-close]')?.addEventListener('click', closeZoom);
})();
