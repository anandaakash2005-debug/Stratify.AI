/* ============================================
   MAIN.JS — App Bootstrapper, Toast & Modal
   Startup Survival Intelligence Platform
   ============================================ */

/* ---- Theme System (Dark/Light) ---- */
const Theme = (() => {
  const STORAGE_KEY = 'survivaliq-theme';
  const DARK = 'dark';
  const LIGHT = 'light';

  function getTheme() {
    return localStorage.getItem(STORAGE_KEY) || DARK;
  }

  function setTheme(theme) {
    if (theme !== DARK && theme !== LIGHT) theme = DARK;
    localStorage.setItem(STORAGE_KEY, theme);
    document.documentElement.setAttribute('data-theme', theme);
    updateThemeIcon();
  }

  function toggle() {
    const current = getTheme();
    const newTheme = current === DARK ? LIGHT : DARK;
    setTheme(newTheme);
    Toast.info(newTheme === LIGHT ? '☀️ Light Mode' : '🌙 Dark Mode', 'Theme updated');
    return newTheme;
  }

  function updateThemeIcon() {
    const btn = document.getElementById('theme-toggle');
    if (!btn) return;
    const theme = getTheme();
    btn.textContent = theme === LIGHT ? '🌙' : '☀️';
    btn.title = theme === LIGHT ? 'Switch to Dark Mode' : 'Switch to Light Mode';
  }

  function init() {
    const theme = getTheme();
    document.documentElement.setAttribute('data-theme', theme);
    updateThemeIcon();

    const btn = document.getElementById('theme-toggle');
    if (btn) {
      btn.addEventListener('click', () => toggle());
    }
  }

  return { init, toggle, setTheme, getTheme };
})();


/* ---- Toast Notification System ---- */
const Toast = (() => {
  let container;

  function getContainer() {
    if (!container) {
      container = document.getElementById('toast-container');
      if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        document.body.appendChild(container);
      }
    }
    return container;
  }

  const icons = {
    success: '✓',
    error:   '✕',
    warning: '⚠',
    info:    'ℹ',
  };

  /**
   * Show a toast notification
   * @param {string} type     - success | error | warning | info
   * @param {string} title    - Bold title text
   * @param {string} message  - Descriptive message
   * @param {number} duration - Auto-dismiss delay in ms (0 = sticky)
   */
  function show(type = 'info', title = '', message = '', duration = 4000) {
    const wrap = getContainer();

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
      <div class="toast-icon">${icons[type] || 'ℹ'}</div>
      <div class="toast-body">
        <div class="toast-title">${sanitize(title)}</div>
        ${message ? `<div class="toast-message">${sanitize(message)}</div>` : ''}
      </div>
      <button class="toast-close" aria-label="Dismiss">×</button>
    `;

    const closeBtn = toast.querySelector('.toast-close');
    closeBtn.addEventListener('click', () => dismiss(toast));

    wrap.appendChild(toast);

    if (duration > 0) {
      setTimeout(() => dismiss(toast), duration);
    }

    return toast;
  }

  function dismiss(toast) {
    toast.classList.add('toast-out');
    setTimeout(() => toast.remove(), 350);
  }

  function sanitize(str) {
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
  }

  return {
    success: (title, msg, d) => show('success', title, msg, d),
    error:   (title, msg, d) => show('error',   title, msg, d),
    warning: (title, msg, d) => show('warning', title, msg, d),
    info:    (title, msg, d) => show('info',    title, msg, d),
  };
})();


/* ---- Modal Manager ---- */
const Modal = (() => {
  const stack = [];

  function open(id) {
    const overlay = document.getElementById(id);
    if (!overlay) return;
    overlay.classList.add('active');
    document.body.style.overflow = 'hidden';
    stack.push(id);

    // Close on backdrop click
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) close(id);
    });
  }

  function close(id) {
    const overlay = document.getElementById(id);
    if (!overlay) return;
    overlay.classList.remove('active');
    stack.splice(stack.indexOf(id), 1);
    if (stack.length === 0) document.body.style.overflow = '';
  }

  function closeAll() {
    [...stack].forEach(id => close(id));
  }

  // Close on Escape
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && stack.length > 0) {
      close(stack[stack.length - 1]);
    }
  });

  // Wire up [data-modal-open] and [data-modal-close] attributes
  function initTriggers() {
    document.querySelectorAll('[data-modal-open]').forEach(btn => {
      btn.addEventListener('click', () => open(btn.dataset.modalOpen));
    });
    document.querySelectorAll('[data-modal-close]').forEach(btn => {
      btn.addEventListener('click', () => close(btn.dataset.modalClose));
    });
  }

  return { open, close, closeAll, initTriggers };
})();


/* ---- Loading Overlay Controller ---- */
const Loader = (() => {
  const STEPS = [
    'Parsing startup inputs…',
    'Running market analysis…',
    'Evaluating competitive landscape…',
    'Calculating failure risk vectors…',
    'Scoring health & survival probability…',
    'Generating AI recommendations…',
    'Finalizing your report…',
  ];

  let overlay, stepEls, current = 0, stepTimer;

  function getOverlay() {
    if (!overlay) overlay = document.getElementById('loading-overlay');
    return overlay;
  }

  function buildStepList() {
    const list = document.querySelector('#loading-overlay .loader-steps');
    if (!list) return;
    list.innerHTML = STEPS.map((s, i) => `
      <div class="loader-step" data-step="${i}">
        <div class="loader-step-dot"></div>
        <span>${s}</span>
      </div>
    `).join('');
    stepEls = list.querySelectorAll('.loader-step');
  }

  function advanceStep() {
    if (!stepEls) return;
    stepEls.forEach((s, i) => {
      s.classList.remove('active', 'done');
      if (i < current)  s.classList.add('done');
      if (i === current) s.classList.add('active');
    });
    if (current < STEPS.length - 1) {
      current++;
      stepTimer = setTimeout(advanceStep, 600 + Math.random() * 500);
    }
  }

  function show() {
    const ov = getOverlay();
    if (!ov) return;
    buildStepList();
    current = 0;
    ov.classList.add('active');
    document.body.style.overflow = 'hidden';
    requestAnimationFrame(advanceStep);
  }

  function hide() {
    clearTimeout(stepTimer);
    const ov = getOverlay();
    if (!ov) return;
    ov.classList.remove('active');
    document.body.style.overflow = '';
    current = 0;
  }

  return { show, hide };
})();


/* ---- Ripple Effect on Buttons ---- */
function initRipple() {
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('.btn-primary, .btn-outline');
    if (!btn) return;
    const rect = btn.getBoundingClientRect();
    const ripple = document.createElement('span');
    ripple.style.cssText = `
      position:absolute; border-radius:50%; pointer-events:none;
      background:rgba(255,255,255,0.25);
      width:10px; height:10px;
      left:${e.clientX - rect.left - 5}px;
      top:${e.clientY - rect.top - 5}px;
      animation:ripple 0.6s ease forwards;
    `;
    btn.style.position = 'relative';
    btn.style.overflow = 'hidden';
    btn.appendChild(ripple);
    setTimeout(() => ripple.remove(), 700);
  });
}


/* ---- Smooth anchor scrolling ---- */
function initSmoothScroll() {
  document.querySelectorAll('a[href^="#"]').forEach(a => {
    a.addEventListener('click', e => {
      const target = document.querySelector(a.getAttribute('href'));
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });
}


/* ---- Animated counters on scroll ---- */
function initCounters() {
  if (!window.IntersectionObserver) return;
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      const el = entry.target;
      const target = parseFloat(el.dataset.count);
      const suffix = el.dataset.suffix || '';
      animateCounter(el, target, 1400, suffix);
      observer.unobserve(el);
    });
  }, { threshold: 0.5 });

  document.querySelectorAll('[data-count]').forEach(el => observer.observe(el));
}


/* ---- Progress bar animations on scroll ---- */
function initProgressObserver() {
  if (!window.IntersectionObserver) return;
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      animateProgressBars(entry.target);
      observer.unobserve(entry.target);
    });
  }, { threshold: 0.2 });

  document.querySelectorAll('.progress-track').forEach(el => observer.observe(el));
}


/* ---- Active nav link highlighting ---- */
function highlightActiveNav() {
  const path = window.location.pathname.split('/').pop() || 'index.html';
  document.querySelectorAll('.nav-link, .sidebar-link').forEach(link => {
    const href = (link.getAttribute('href') || '').split('/').pop();
    if (href === path) link.classList.add('active');
  });
}


/* ---- Authentication Management ---- */
const Auth = (() => {
  const SESSION_KEY = 'survivaliq_auth';

  function getRawAuth() {
    return localStorage.getItem(SESSION_KEY) || sessionStorage.getItem(SESSION_KEY);
  }

  function parseAuth() {
    const raw = getRawAuth();
    try {
      return raw ? JSON.parse(raw) : null;
    } catch (err) {
      return null;
    }
  }

  function isLoggedIn() {
    const auth = parseAuth();
    return !!(auth && auth.user && auth.token);
  }

  function getUser() {
    const auth = parseAuth();
    return auth?.user || null;
  }

  function getToken() {
    const auth = parseAuth();
    return auth?.token || null;
  }

  function storeAuth(payload, remember = false) {
    const storage = remember ? localStorage : sessionStorage;
    storage.setItem(SESSION_KEY, JSON.stringify({
      user:  payload.user,
      token: payload.token,
      createdAt: Date.now(),
    }));
  }

  function clearAuth() {
    localStorage.removeItem(SESSION_KEY);
    sessionStorage.removeItem(SESSION_KEY);
  }

  function requireAuth(redirectPath = 'signin.html') {
    if (!isLoggedIn()) {
      Toast.warning('Login required', 'Please sign in before accessing Analyze.');
      setTimeout(() => {
        const target = encodeURIComponent(redirectPath);
        window.location.href = `signin.html?redirect=${target}`;
      }, 1400);
      return false;
    }
    return true;
  }

  function updateNavbarAuth() {
    const navCta = document.querySelector('.nav-cta');
    if (!navCta) return;

    const userInfo = navCta.querySelector('.nav-user-info');
    if (!isLoggedIn()) {
      if (userInfo) userInfo.remove();
      return;
    }

    const user = getUser();
    const userName = user?.user_metadata?.full_name || user?.user_metadata?.name || user?.name || user?.email?.split('@')[0] || 'User';

    const signInBtn = navCta.querySelector('a[href="signin.html"]');
    if (signInBtn) signInBtn.remove();

    if (!userInfo) {
      const info = document.createElement('div');
      info.className = 'nav-user-info';
      info.style.cssText = 'display:flex; align-items:center; gap:0.75rem; margin-left:auto;';
      const name = document.createElement('span');
      name.style.cssText = 'font-size:0.875rem; color:var(--text-secondary);';
      name.textContent = `👤 ${userName.split(' ')[0]}`;
      const logoutButton = document.createElement('button');
      logoutButton.id = 'logout-btn';
      logoutButton.className = 'btn btn-ghost btn-sm';
      logoutButton.style.cssText = 'padding:0.4rem 0.8rem;';
      logoutButton.textContent = 'Sign Out';
      info.append(name, logoutButton);
      navCta.insertBefore(info, navCta.firstChild);
      const btn = document.getElementById('logout-btn');
      if (btn) btn.addEventListener('click', () => {
        clearAuth();
        Toast.success('Logged Out', 'You have been signed out.');
        setTimeout(() => {
          window.location.href = 'index.html';
        }, 1200);
      });
    }
  }

  return { isLoggedIn, getUser, getToken, storeAuth, clearAuth, requireAuth, updateNavbarAuth };
})();


/* ---- Master init ---- */
document.addEventListener('DOMContentLoaded', () => {
  Theme.init();
  initNavbar();
  initSidebar();
  initTabs();
  Modal.initTriggers();
  initRipple();
  initSmoothScroll();
  initCounters();
  initProgressObserver();
  observeAnimations();
  highlightActiveNav();
  Auth.updateNavbarAuth();

});