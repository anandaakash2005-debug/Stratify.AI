/* ───────────────────────────────────────────
   ai-mentor-init.js — Satquery.AI AI Mentor
   Initializes the floating mentor widget on
   authenticated pages.
   ─────────────────────────────────────────── */
(function () {
  'use strict';
  console.log("AI INIT START");

  var excluded = ['signin.html', 'signup.html', 'chatbot.html'];

  function shouldLoad() {
    // Auth is declared with const in main.js — NOT on window
    if (typeof Auth === 'undefined') return false;
    if (Auth.isLoggedIn && !Auth.isLoggedIn()) return false;
    var page = window.location.pathname.split('/').pop() || 'index.html';
    return excluded.indexOf(page) === -1;
  }

  function init() {
    console.log("shouldLoad =", shouldLoad());
    if (!shouldLoad()) return;

    console.log("Loading CSS");
    if (!document.querySelector('link[href*="ai-mentor.css"]')) {
      var link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = 'css/ai-mentor.css';
      document.head.appendChild(link);
    }

    function loadScript(src) {
      return new Promise(function (resolve) {
        var script = document.createElement('script');
        script.src = src;
        script.onload = resolve;
        script.onerror = resolve;
        document.head.appendChild(script);
      });
    }

    var dependencies = Promise.resolve()
      .then(function () {
        return typeof marked === 'undefined'
          ? loadScript('https://cdn.jsdelivr.net/npm/marked@12.0.2/marked.min.js')
          : null;
      })
      .then(function () {
        return typeof DOMPurify === 'undefined'
          ? loadScript('https://cdn.jsdelivr.net/npm/dompurify@3.1.6/dist/purify.min.js')
          : null;
      });

    dependencies.then(function () {
      console.log("Loading JS");
      if (typeof AIMentor === 'undefined') {
        loadScript('js/ai-mentor.js').then(function () {
          if (typeof AIMentor !== 'undefined') AIMentor.init();
        });
      } else {
        AIMentor.init();
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
