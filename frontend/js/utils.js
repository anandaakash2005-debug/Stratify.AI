/* ============================================
   UTILS.JS — Shared Utility Functions
   Startup Survival Intelligence Platform
   ============================================ */

/**
 * Clamp a number between min and max
 */
function clamp(val, min, max) {
  return Math.min(Math.max(val, min), max);
}

/**
 * Animate a number counter from 0 to target
 */
function animateCounter(el, target, duration = 1200, suffix = '') {
  if (!el) return;
  const start = performance.now();
  const easeOut = t => 1 - Math.pow(1 - t, 3);

  function frame(now) {
    const elapsed = now - start;
    const progress = clamp(elapsed / duration, 0, 1);
    const value = Math.round(easeOut(progress) * target);
    el.textContent = value + suffix;
    if (progress < 1) requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
}

/**
 * Animate progress bars to their target width
 */
function animateProgressBars(container = document) {
  const bars = container.querySelectorAll('.progress-fill[data-width]');
  bars.forEach(bar => {
    const targetWidth = bar.dataset.width;
    setTimeout(() => {
      bar.style.width = targetWidth + '%';
    }, parseInt(bar.dataset.delay || 0));
  });
}

/**
 * Intersection Observer for scroll-triggered animations
 */
function observeAnimations() {
  if (!window.IntersectionObserver) return;

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('in-view');
        observer.unobserve(entry.target);
        // Trigger progress bars if inside
        animateProgressBars(entry.target.parentElement);
      }
    });
  }, { threshold: 0.15 });

  document.querySelectorAll('[data-animate]').forEach(el => observer.observe(el));
}

/**
 * Format number with commas
 */
function formatNumber(n) {
  return new Intl.NumberFormat().format(n);
}

/**
 * Parse stored JSON safely
 */
function safeJSON(str, fallback = null) {
  try { return JSON.parse(str); }
  catch { return fallback; }
}

/**
 * Local storage helpers
 */
const store = {
  set: (key, val) => localStorage.setItem(key, JSON.stringify(val)),
  get: (key, fallback = null) => safeJSON(localStorage.getItem(key), fallback),
  del: (key) => localStorage.removeItem(key),
  clear: () => localStorage.clear(),
};

/**
 * Initialize navbar hamburger menu
 */
function initNavbar() {
  const ham = document.querySelector('.nav-hamburger');
  const mobileMenu = document.querySelector('.nav-mobile-menu');
  if (!ham || !mobileMenu) return;

  ham.addEventListener('click', () => {
    ham.classList.toggle('open');
    mobileMenu.classList.toggle('open');
  });

  // Close on outside click
  document.addEventListener('click', (e) => {
    if (!ham.contains(e.target) && !mobileMenu.contains(e.target)) {
      ham.classList.remove('open');
      mobileMenu.classList.remove('open');
    }
  });
}

/**
 * Initialize sidebar for dashboard pages
 */
function initSidebar() {
  const toggle = document.querySelector('#sidebar-toggle');
  const sidebar = document.querySelector('.sidebar');
  const overlay = document.querySelector('.sidebar-overlay');
  if (!toggle || !sidebar) return;

  function openSidebar() {
    sidebar.classList.add('mobile-open');
    if (overlay) overlay.classList.add('active');
    document.body.style.overflow = 'hidden';
  }

  function closeSidebar() {
    sidebar.classList.remove('mobile-open');
    if (overlay) overlay.classList.remove('active');
    document.body.style.overflow = '';
  }

  toggle.addEventListener('click', () => {
    sidebar.classList.contains('mobile-open') ? closeSidebar() : openSidebar();
  });

  if (overlay) overlay.addEventListener('click', closeSidebar);
}

/**
 * Initialize tab switching
 */
function initTabs(container = document) {
  container.querySelectorAll('[data-tab-group]').forEach(group => {
    const tabs = group.querySelectorAll('[data-tab]');
    const panels = document.querySelectorAll(`[data-panel="${group.dataset.tabGroup}"]`);

    tabs.forEach(tab => {
      tab.addEventListener('click', () => {
        const target = tab.dataset.tab;
        tabs.forEach(t => t.classList.remove('active'));
        panels.forEach(p => p.classList.remove('active'));
        tab.classList.add('active');
        const panel = document.querySelector(`[data-panel="${group.dataset.tabGroup}"][data-id="${target}"]`);
        if (panel) panel.classList.add('active');
      });
    });
  });
}

// Export for module usage or just use globally
if (typeof module !== 'undefined') {
  module.exports = {
    clamp, animateCounter, animateProgressBars, observeAnimations,
    formatNumber, safeJSON,
    store, initNavbar, initSidebar, initTabs
  };
}