/* ───────────────────────────────────────────────
   ai-mentor.js — Satquery.AI AI Startup Mentor
   Floating widget with SSE streaming, context
   actions, insights, report awareness
   ─────────────────────────────────────────────── */
(function () {
  'use strict';

  if (document.getElementById('ai-mentor')) return;

  var API_URL = (window.CONFIG && window.CONFIG.API_URL) || 'http://localhost:8000';
  var DISMISSED_KEY = 'satquery_mentor_dismissed';

  var state = {
    open: false,
    dismissed: localStorage.getItem(DISMISSED_KEY) === 'true',
    loading: false,
    streaming: false,
    abortController: null,
    requestSequence: 0,
    activeRequestId: 0,
  };

  var el = {};
  var welcomeCtx = null; // context from welcome endpoint
  var currentReportId = null;

  // ─── Detect current report_id from page URL ──
  function detectReportId() {
    var params = new URLSearchParams(window.location.search);
    var id = params.get('id') || params.get('report_id') || null;
    // Also check localStorage
    if (!id) {
      try {
        var stored = JSON.parse(localStorage.getItem('latest_analysis') || '{}');
        id = stored.report_id || null;
      } catch (e) {}
    }
    return id;
  }

  // ─── Check if analysis exists ──────────────
  function hasAnalysis() {
    try {
      var raw = localStorage.getItem('latest_analysis');
      return !!(raw && JSON.parse(raw) && JSON.parse(raw).startup);
    } catch (e) {
      return false;
    }
  }

  // ─── Token ─────────────────────────────────
  async function getToken() {
    try {
      var mod = await import('./supabase.js');
      var sessionRes = await mod.supabase.auth.getSession();
      if (sessionRes.data && sessionRes.data.session && sessionRes.data.session.access_token) {
        return sessionRes.data.session.access_token;
      }
    } catch (e) {
      console.error('Session lookup failed:', e);
    }
    // Fallback: main.js Auth helper
    if (typeof Auth !== 'undefined' && Auth.getToken) return Auth.getToken();
    return null;
  }

  // ─── API helpers ──────────────────────────
  async function apiGet(path) {
    var token = await getToken();
    if (!token) {
      console.warn('MENTOR: no token, aborting GET', path);
      return null;
    }
    try {
      var res = await fetch(API_URL + path, {
        headers: { Authorization: 'Bearer ' + token },
      });
      if (!res.ok) return null;
      return await res.json();
    } catch (e) {
      return null;
    }
  }

  // ─── Safe Content Rendering ─────────────────────────────
  function renderAssistantMarkdown(markdown) {
    if (typeof markdown !== 'string') return '';
    var normalized = markdown.replace(/\r\n/g, '\n').trim();
    if (!normalized || typeof marked === 'undefined' || typeof DOMPurify === 'undefined') return null;
    try {
      marked.setOptions({ gfm: true, breaks: true });
      if (!DOMPurify.__mentorLinksConfigured) {
        DOMPurify.addHook('afterSanitizeAttributes', function (node) {
          if (node.tagName === 'A') {
            node.setAttribute('target', '_blank');
            node.setAttribute('rel', 'noopener noreferrer');
          }
        });
        DOMPurify.__mentorLinksConfigured = true;
      }
      return DOMPurify.sanitize(marked.parse(normalized), {
        USE_PROFILES: { html: true },
        FORBID_TAGS: ['form', 'iframe', 'style', 'script'],
        FORBID_ATTR: ['style']
      });
    } catch (e) {
      return null;
    }
  }

  function renderAssistantContent(element, content) {
    // Detect if content looks like raw JSON and prevent display
    if (typeof content === 'string' && content.trim().match(/^[\{\[]/)) {
      // It looks like JSON - don't display it
      element.textContent = 'I received a structured response. Please try again.';
      return;
    }

    var html = renderAssistantMarkdown(content);
    if (html === null) {
      element.textContent = typeof content === 'string' ? content : '';
    } else {
      element.innerHTML = html;
    }
  }

  // ─── Structured Response Renderer ─────────────────────────────
  function renderStructuredResponse(element, data) {
    if (!data || typeof data !== 'object') {
      element.textContent = 'Invalid response format.';
      return;
    }

    var container = document.createElement('div');
    container.className = 'mentor-structured-response';

    // Title
    if (data.title) {
      var title = document.createElement('h3');
      title.className = 'mentor-response-title';
      title.textContent = data.title;
      container.appendChild(title);
    }

    // Summary
    if (data.summary) {
      var summary = document.createElement('p');
      summary.className = 'mentor-response-summary';
      summary.textContent = data.summary;
      container.appendChild(summary);
    }

    // Sections
    if (data.sections && Array.isArray(data.sections)) {
      data.sections.forEach(function (section) {
        if (!section.heading) return;
        var sectionDiv = document.createElement('div');
        sectionDiv.className = 'mentor-section';

        var heading = document.createElement('h4');
        heading.className = 'mentor-section-heading';
        heading.textContent = section.heading;
        sectionDiv.appendChild(heading);

        if (section.items && Array.isArray(section.items)) {
          var list = document.createElement('ul');
          list.className = 'mentor-section-list';
          section.items.forEach(function (item) {
            if (!item.title) return;
            var li = document.createElement('li');
            li.className = 'mentor-section-item';
            var titleSpan = document.createElement('strong');
            titleSpan.textContent = item.title + ': ';
            li.appendChild(titleSpan);
            var descSpan = document.createElement('span');
            descSpan.textContent = item.description || '';
            li.appendChild(descSpan);
            list.appendChild(li);
          });
          sectionDiv.appendChild(list);
        }
        container.appendChild(sectionDiv);
      });
    }

    // Mentors
    if (data.mentors && Array.isArray(data.mentors) && data.mentors.length > 0) {
      var mentorsDiv = document.createElement('div');
      mentorsDiv.className = 'mentor-mentors-section';
      var mentorsHeading = document.createElement('h4');
      mentorsHeading.className = 'mentor-section-heading';
      mentorsHeading.textContent = 'Verified Mentors';
      mentorsDiv.appendChild(mentorsHeading);

      data.mentors.forEach(function (mentor) {
        var card = document.createElement('div');
        card.className = 'mentor-card';
        var name = document.createElement('div');
        name.className = 'mentor-card-name';
        name.textContent = mentor.name || 'Unknown';
        card.appendChild(name);

        if (mentor.current_role) {
          var role = document.createElement('div');
          role.className = 'mentor-card-role';
          role.textContent = mentor.current_role;
          card.appendChild(role);
        }

        if (mentor.organization) {
          var org = document.createElement('div');
          org.className = 'mentor-card-org';
          org.textContent = mentor.organization;
          card.appendChild(org);
        }

        if (mentor.expertise && mentor.expertise.length > 0) {
          var expertise = document.createElement('div');
          expertise.className = 'mentor-card-expertise';
          expertise.textContent = 'Expertise: ' + mentor.expertise.join(', ');
          card.appendChild(expertise);
        }

        if (mentor.contact) {
          var contactDiv = document.createElement('div');
          contactDiv.className = 'mentor-card-contact';
          if (mentor.contact.email) {
            var email = document.createElement('a');
            email.href = 'mailto:' + mentor.contact.email;
            email.textContent = mentor.contact.email;
            email.className = 'mentor-contact-link';
            contactDiv.appendChild(email);
          }
          if (mentor.contact.linkedin) {
            var linkedin = document.createElement('a');
            linkedin.href = mentor.contact.linkedin;
            linkedin.textContent = 'LinkedIn';
            linkedin.className = 'mentor-contact-link';
            linkedin.target = '_blank';
            linkedin.rel = 'noopener noreferrer';
            if (contactDiv.firstChild) {
              var sep = document.createTextNode(' | ');
              contactDiv.appendChild(sep);
            }
            contactDiv.appendChild(linkedin);
          }
          if (contactDiv.childNodes.length > 0) {
            card.appendChild(contactDiv);
          }
        }

        mentorsDiv.appendChild(card);
      });
      container.appendChild(mentorsDiv);
    }

    // Follow-up
    if (data.follow_up) {
      var followUp = document.createElement('p');
      followUp.className = 'mentor-follow-up';
      followUp.textContent = data.follow_up;
      container.appendChild(followUp);
    }

    // Fallback text if structured rendering is empty
    if (container.children.length === 0 && data.fallback_text) {
      var fallback = document.createElement('p');
      fallback.textContent = data.fallback_text;
      container.appendChild(fallback);
    }

    element.innerHTML = '';
    element.appendChild(container);
  }

  // ─── DOM helpers ──────────────────────────
  function addMsg(text, role) {
    var div = document.createElement('div');
    var isAssistant = role === 'bot' || role === 'assistant';
    div.className = 'ai-mentor-msg ai-mentor-msg-' + (isAssistant ? 'bot' : 'user') +
      (isAssistant ? ' mentor-message mentor-message--assistant' : '');
    if (isAssistant) {
      var avatar = document.createElement('div');
      avatar.className = 'mentor-avatar';
      avatar.setAttribute('aria-hidden', 'true');
      avatar.textContent = '🤖';
      div.appendChild(avatar);
    }
    var body = document.createElement('div');
    body.className = isAssistant ? 'mentor-message-body' : 'ai-mentor-msg-content';
    var content = document.createElement('div');
    content.className = isAssistant ? 'mentor-message-content markdown-body' : 'ai-mentor-msg-content';
    if (isAssistant) body.appendChild(content);
    else body = content;
    if (isAssistant) renderAssistantContent(content, text);
    else content.textContent = typeof text === 'string' ? text : '';
    div.appendChild(body);
    el.messages.appendChild(div);
    scrollBottom();
    return div;
  }

  function scrollBottom() {
    requestAnimationFrame(function () {
      el.messages.scrollTop = el.messages.scrollHeight;
    });
  }

  function showTyping() {
    hideTyping();
    var div = document.createElement('div');
    div.className = 'ai-mentor-msg ai-mentor-msg-bot ai-mentor-typing';
    div.id = 'ai-mentor-typing';
    div.setAttribute('role', 'status');
    div.setAttribute('aria-label', 'Mentor is thinking');
    var typingContent = document.createElement('div');
    typingContent.className = 'ai-mentor-msg-content';
    for (var i = 0; i < 3; i++) {
      var dot = document.createElement('span');
      dot.className = 'mentor-dot';
      typingContent.appendChild(dot);
    }
    div.appendChild(typingContent);
    el.messages.appendChild(div);
    scrollBottom();
  }

  function hideTyping() {
    var t = document.getElementById('ai-mentor-typing');
    if (t) t.remove();
  }

  // ─── Suggestion chips ─────────────────────
  function renderSuggestions() {
    var base = [
      'How can I improve PMF?',
      'What are my biggest risks?',
      'How investor-ready am I?',
      'How can I increase my survival score?',
      'Who are my main competitors?',
      'What should I do next?',
    ];
    el.suggestions.innerHTML = base
      .map(function (q) {
        return (
          '<button data-q="' + q.replace(/"/g, '&quot;') + '">' + q + '</button>'
        );
      })
      .join('');
  }

  // ─── Context quick actions ────────────────
  function renderContextActions() {
    var actions = [
      { label: 'Improve PMF', msg: 'How can I improve product-market fit?' },
      { label: 'Raise Funding', msg: 'How can I raise funding?' },
      { label: 'Analyze Competition', msg: 'Who are my competitors and how do I compete?' },
      { label: 'Growth Strategy', msg: 'What growth strategy should I follow?' },
    ];
    var wrap = document.createElement('div');
    wrap.className = 'ai-mentor-msg ai-mentor-msg-bot';
    wrap.innerHTML =
      '<div class="ai-mentor-msg-content" style="padding:8px 12px">' +
      '<div style="font-size:12px;color:rgba(255,255,255,0.5);margin-bottom:6px">Quick Actions</div>' +
      '<div style="display:flex;flex-wrap:wrap;gap:4px">' +
      actions
        .map(function (a) {
          return (
            '<button class="mentor-action-btn" data-q="' +
            a.msg.replace(/"/g, '&quot;') +
            '" style="background:rgba(99,102,241,0.1);border:1px solid rgba(99,102,241,0.15);border-radius:12px;padding:5px 12px;color:rgba(255,255,255,0.8);font-size:12px;font-family:inherit;cursor:pointer;transition:all .2s">' +
            a.label +
            '</button>'
          );
        })
        .join('') +
      '</div></div>';
    return wrap;
  }

  // ─── Context bar ──────────────────────────
  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function renderContextBar(ctx) {
    if (!ctx || !ctx.startup_name) {
      el.contextBar.style.display = 'none';
      return;
    }
    el.contextBar.style.display = 'flex';
    var color = 'green';
    if (ctx.survival_score < 50) color = 'red';
    else if (ctx.survival_score < 70) color = 'yellow';
    el.contextBar.innerHTML =
      '<span class="ctx-item">' +
      '<span class="ctx-dot ' + color + '"></span> ' +
      escapeHtml(ctx.startup_name || '') +
      '</span>' +
      '<span class="ctx-item">Score: ' + escapeHtml(ctx.survival_score || '--') + '</span>' +
      '<span class="ctx-item">Funding: ' + escapeHtml(ctx.funding_readiness || '--') + '%</span>';
  }

  // ─── Summary card ─────────────────────────
  function renderSummaryCard(ctx) {
    if (!ctx || !ctx.startup_name) return '';
    var sc = 'blue';
    if (ctx.survival_score >= 70) sc = 'green';
    else if (ctx.survival_score >= 50) sc = 'yellow';
    var rows =
      '<div class="sum-row"><span class="sum-label">Startup</span><span class="sum-value">' +
      escapeHtml(ctx.startup_name) +
      '</span></div>' +
      '<div class="sum-row"><span class="sum-label">Survival Score</span>' +
      '<span class="sum-value" style="color:var(--' + sc + ')">' +
      escapeHtml(ctx.survival_score || '--') +
      '/100</span></div>' +
      '<div class="sum-row"><span class="sum-label">Funding Readiness</span>' +
      '<span class="sum-value">' +
      escapeHtml(ctx.funding_readiness || '--') +
      '%</span></div>';
    if (ctx.runway_months) {
      rows +=
        '<div class="sum-row"><span class="sum-label">Runway</span>' +
        '<span class="sum-value">' +
        escapeHtml(ctx.runway_months) +
        ' months</span></div>';
    }
    return '<div class="ai-mentor-summary">' + rows + '</div>';
  }

  // ─── Insight alert ────────────────────────
  function renderInsight(ctx) {
    if (!ctx || !ctx.urgent_flag) return null;
    var flag = ctx.urgent_flag;
    // Only show if it's an actual warning, not "On track"
    if (flag.indexOf('On track') !== -1 || flag.indexOf('keep executing') !== -1)
      return null;
    var div = document.createElement('div');
    div.className = 'ai-mentor-msg ai-mentor-msg-bot';
    var content = document.createElement('div');
    content.className = 'ai-mentor-msg-content';
    renderAssistantContent(content, flag);
    var button = document.createElement('button');
    button.className = 'mentor-insight-btn';
    button.setAttribute('data-q', 'Give me recommendations for this');
    button.textContent = 'Get Recommendations';
    content.appendChild(document.createElement('br'));
    content.appendChild(button);
    div.appendChild(content);
    return div;
  }

  // ─── Welcome + Context load ───────────────
  async function loadWelcome() {
    var data = await apiGet('/api/v1/mentor/welcome');
    if (!data) {
      addMsg('Hi! Ask me anything about your startup.', 'bot');
      return null;
    }

    var ctx = await apiGet('/api/v1/mentor/context');
    welcomeCtx = ctx;
    renderContextBar(ctx);

    // Welcome message
    addMsg(data.message || 'Hi!', 'bot');

    // Summary card
    if (ctx && ctx.startup_name) {
      var summaryHtml = renderSummaryCard(ctx);
      if (summaryHtml) {
        var summaryDiv = document.createElement('div');
        summaryDiv.className = 'ai-mentor-msg ai-mentor-msg-bot';
        summaryDiv.innerHTML = summaryHtml;
        el.messages.appendChild(summaryDiv);
        scrollBottom();
      }
    }

    // Insight alert for urgent flags
    if (ctx) {
      var insightDiv = renderInsight(ctx);
      if (insightDiv) {
        el.messages.appendChild(insightDiv);
        scrollBottom();
      }
    }

    // Context actions
    var actionsDiv = renderContextActions();
    el.messages.appendChild(actionsDiv);
    scrollBottom();

    return ctx;
  }

  // ─── History ──────────────────────────────
  async function loadHistory() {
    var data = await apiGet('/api/v1/mentor/history');
    if (!data || !data.history || !data.history.length) return;
    data.history.forEach(function (item) {
      if (item.message) addMsg(item.message, 'user');
      if (item.response) addMsg(item.response, 'bot');
    });
  }

  // ─── Send message with SSE ────────────────
  async function send(message) {
    if (!message || !message.trim()) return;
    if (state.loading || state.streaming) return;

    var text = message.trim();
    var requestId = ++state.requestSequence;
    state.activeRequestId = requestId;
    state.loading = true;
    state.streaming = false;
    setBusy(true);
    el.input.value = '';
    el.suggestions.style.display = 'none';

    addMsg(text, 'user');

    showTyping();
    state.abortController = new AbortController();
    var assistantDiv = null;
    var botContent = null;
    var assistantText = '';
    var receivedContent = false;
    var terminalState = null;

    function isCurrent() {
      return state.activeRequestId === requestId;
    }

    function ensureAssistant() {
      if (assistantDiv) return;
      assistantDiv = document.createElement('div');
      assistantDiv.className = 'ai-mentor-msg ai-mentor-msg-bot mentor-message mentor-message--assistant';
      var avatar = document.createElement('div');
      avatar.className = 'mentor-avatar';
      avatar.setAttribute('aria-hidden', 'true');
      avatar.textContent = '🤖';
      var body = document.createElement('div');
      body.className = 'mentor-message-body';
      botContent = document.createElement('div');
      botContent.className = 'mentor-message-content markdown-body';
      body.appendChild(botContent);
      assistantDiv.appendChild(avatar);
      assistantDiv.appendChild(body);
      el.messages.appendChild(assistantDiv);
      scrollBottom();
    }

    function setAssistantText(value) {
      ensureAssistant();
      renderAssistantContent(botContent, value);
      scrollBottom();
    }

    function errorMessage(status, detail) {
      if (status === 401) return 'Your session expired. Please sign in again.';
      if (status === 429) return 'The AI is currently rate-limited. Please wait and retry.';
      if (status === 502) return 'The AI could not produce a valid response.';
      if (status === 504) return 'The AI took too long to respond.';
      if (status === 422) return detail || 'Please check your message and try again.';
      return detail || 'Could not reach the backend.';
    }

    try {
      var token = await getToken();
      if (!token) {
        hideTyping();
        addMsg('Please sign in to use the AI Mentor.', 'bot');
        terminalState = 'error';
        return;
      }
      state.abortController = new AbortController();
      var res = await fetch(API_URL + '/api/v1/mentor/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: 'Bearer ' + token,
        },
        body: JSON.stringify({
          message: text,
          report_id: currentReportId,
        }),
        signal: state.abortController.signal,
      });

      if (!isCurrent()) return;
      hideTyping();

      if (!res.ok) {
        var errBody = await res.json().catch(function () {
          return {};
        });
        var detail = errBody.detail || errBody.message || '';
        setAssistantText(errorMessage(res.status, detail));
        terminalState = 'error';
        return;
      }

      state.streaming = true;

      // SSE reader
      var reader = res.body.getReader();
      var decoder = new TextDecoder();
      var buffer = '';

      while (true) {
        var result = await reader.read();
        if (result.done) break;

        buffer += decoder.decode(result.value, { stream: true });
        var parts = buffer.split('\n');
        buffer = parts.pop() || '';

        for (var i = 0; i < parts.length; i++) {
          var line = parts[i].trim();
          if (!line || !line.startsWith('data: ')) continue;

          var jsonStr = line.slice(6);
          try {
            var event = JSON.parse(jsonStr);

            if (event.type === 'token' && isCurrent()) {
              receivedContent = true;
              // Don't display tokens that look like JSON start
              var token = typeof event.content === 'string' ? event.content : '';
              if (!assistantText && token.trim().match(/^[\{\[]/)) {
                // First token looks like JSON - buffer it
                assistantText += token;
              } else if (assistantText && assistantText.trim().match(/^[\{\[]/)) {
                // We're buffering JSON - continue buffering
                assistantText += token;
              } else {
                // Normal text - display immediately
                assistantText += token;
                setAssistantText(assistantText);
              }
            } else if (event.type === 'structured' && isCurrent()) {
              // Structured response - render with dedicated renderer
              receivedContent = true;
              var structuredData = event.data;
              if (structuredData && typeof structuredData === 'object') {
                renderStructuredResponse(botContent, structuredData);
                assistantText = structuredData.reply || JSON.stringify(structuredData);
              }
            } else if (event.type === 'done') {
              terminalState = 'success';
              state.streaming = false;
            } else if (event.type === 'error') {
              if (!receivedContent) setAssistantText(event.message || 'The AI could not complete the response.');
              terminalState = receivedContent ? 'success' : 'error';
              state.streaming = false;
            }
          } catch (e) {}
        }
      }

      state.streaming = false;
      if (!terminalState) terminalState = receivedContent ? 'success' : 'error';
      if (terminalState === 'error' && !receivedContent) {
        setAssistantText('The AI could not complete the response. Please try again.');
      }
    } catch (e) {
      hideTyping();
      if (e.name === 'AbortError') {
        terminalState = 'cancellation';
      } else if (isCurrent() && !receivedContent) {
        setAssistantText('Could not reach the backend.');
        terminalState = 'error';
      }
    } finally {
      if (isCurrent()) {
        state.loading = false;
        state.streaming = false;
        state.abortController = null;
        setBusy(false);
      }
    }
  }

  function setBusy(busy) {
    if (!el.sendBtn || !el.input) return;
    el.sendBtn.disabled = busy;
    el.input.disabled = busy;
    el.sendBtn.setAttribute('aria-busy', busy ? 'true' : 'false');
    el.messages.setAttribute('aria-busy', busy ? 'true' : 'false');
  }

  // ─── Panel open / close ───────────────────
  function openPanel(prefilled) {
    if (state.open) return;
    state.open = true;
    el.panel.classList.add('open');
    el.trigger.classList.add('hidden');
    setTimeout(function () {
      el.input.focus();
    }, 400);

    currentReportId = detectReportId();

    el.messages.innerHTML = '';
    el.suggestions.style.display = 'flex';
    renderSuggestions();

    loadWelcome().then(function () {
      loadHistory();
      scrollBottom();
    });

    if (prefilled) {
      setTimeout(function () {
        send(prefilled);
      }, 800);
    }
  }

  function closePanel() {
    if (!state.open) return;
    state.open = false;
    el.panel.classList.remove('open');
    el.trigger.classList.remove('hidden');

    if (state.abortController) {
      state.abortController.abort();
      state.abortController = null;
    }

    if (!state.dismissed) {
      state.dismissed = true;
      localStorage.setItem(DISMISSED_KEY, 'true');
      el.trigger.classList.add('collapsed');
    }
  }

  function toggle() {
    state.open ? closePanel() : openPanel();
  }

  // ─── Global API ──────────────────────────
  window.openMentor = function (question) {
    if (state.open) {
      send(question);
    } else {
      openPanel(question);
    }
  };

  // ─── Pulse timer ─────────────────────────
  function startPulse() {
    setInterval(function () {
      if (!state.open && !state.dismissed) {
        el.trigger.classList.add('pulse');
        setTimeout(function () {
          el.trigger.classList.remove('pulse');
        }, 2000);
      }
    }, 15000);
  }

  // ─── Build DOM ───────────────────────────
  function createWidget() {
    var analysisExists = hasAnalysis();
    var triggerLabel = analysisExists
      ? '<strong>AI Mentor</strong><small>Need help understanding your latest report?</small>'
      : '<strong>AI Mentor</strong><small>Need startup advice?</small>';

    var container = document.createElement('div');
    container.id = 'ai-mentor';
    container.innerHTML =
      '<div id="ai-mentor-trigger" class="ai-mentor-trigger' +
      (state.dismissed ? ' collapsed' : '') +
      '">' +
      '<div class="ai-mentor-trigger-label">' +
      '<span class="ai-mentor-avatar">🤖</span>' +
      '<div>' +
      triggerLabel +
      '</div>' +
      '</div>' +
      '<div class="ai-mentor-trigger-icon"><span>🤖</span></div>' +
      '</div>' +
      '<div class="ai-mentor-panel" id="ai-mentor-panel">' +
      '<div class="ai-mentor-panel-header">' +
      '<div class="ai-mentor-panel-header-left">' +
      '<span class="ai-mentor-avatar">🤖</span>' +
      '<div>' +
      '<strong>AI Startup Mentor</strong>' +
      '<small>Your startup co-founder assistant</small>' +
      '</div>' +
      '</div>' +
      '<button class="ai-mentor-panel-close" id="ai-mentor-panel-close" aria-label="Close">✕</button>' +
      '</div>' +
      '<div class="ai-mentor-context-bar" id="ai-mentor-context-bar"></div>' +
      '<div class="ai-mentor-messages" id="ai-mentor-messages" aria-live="polite" aria-label="Mentor conversation"></div>' +
      '<div class="ai-mentor-suggestions" id="ai-mentor-suggestions"></div>' +
      '<div class="ai-mentor-input-area">' +
      '<textarea id="ai-mentor-input" aria-label="Message the AI Startup Mentor" placeholder="Ask about your startup..." rows="1"></textarea>' +
      '<button id="ai-mentor-send" aria-label="Send message">Send</button>' +
      '</div>' +
      '</div>';

    document.body.appendChild(container);

    el.trigger = document.getElementById('ai-mentor-trigger');
    el.panel = document.getElementById('ai-mentor-panel');
    el.messages = document.getElementById('ai-mentor-messages');
    el.input = document.getElementById('ai-mentor-input');
    el.sendBtn = document.getElementById('ai-mentor-send');
    el.closeBtn = document.getElementById('ai-mentor-panel-close');
    el.suggestions = document.getElementById('ai-mentor-suggestions');
    el.contextBar = document.getElementById('ai-mentor-context-bar');

    // Events
    el.trigger.addEventListener('click', toggle);
    el.closeBtn.addEventListener('click', closePanel);
    el.sendBtn.addEventListener('click', function () {
      send(el.input.value);
    });

    el.input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        send(el.input.value);
      }
      el.input.style.height = 'auto';
      el.input.style.height = Math.min(el.input.scrollHeight, 120) + 'px';
    });

    // Delegate clicks for suggestion / action / insight buttons
    el.suggestions.addEventListener('click', function (e) {
      var btn = e.target.closest('button[data-q]');
      if (btn) send(btn.getAttribute('data-q'));
    });

    el.messages.addEventListener('click', function (e) {
      var btn = e.target.closest('button[data-q]');
      if (btn) send(btn.getAttribute('data-q'));
    });

    startPulse();
  }

  // ─── Expose ──────────────────────────────
  window.AIMentor = {
    init: createWidget,
    open: openPanel,
    close: closePanel,
    send: send,
  };
})();
