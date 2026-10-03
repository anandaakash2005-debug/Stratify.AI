/* ============================================
   CHATBOT.JS — AI Startup Intelligence Chat
   ChatGPT-style sidebar + conversation history
   ============================================ */

const ChatBot = (() => {
  const API_URL = (typeof CONFIG !== 'undefined' && CONFIG.API_URL) || 'http://localhost:8000';
  const messagesEl = document.getElementById('chat-messages');
  const inputEl = document.getElementById('chat-input');
  const sendBtn = document.getElementById('chat-send-btn');
  const badgeEl = document.getElementById('analysis-badge');
  const statusDot = document.getElementById('chat-status-dot');
  const analysisLabel = document.getElementById('analysis-label');
  const recentChatsEl = document.getElementById('recent-chats');
  const newChatBtn = document.getElementById('new-chat-btn');
  const chatSearch = document.getElementById('chat-search');
  let isLoading = false;
  let allHistory = [];

  function getAnalysis() {
    try {
      const raw = localStorage.getItem('latest_analysis');
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  }

  async function getToken() {
    try {
      const mod = await import('./supabase.js');
      const { data } = await mod.supabase.auth.getSession();
      if (data?.session?.access_token) return data.session.access_token;
    } catch {}
    return (typeof Auth !== 'undefined' && Auth.getToken) ? Auth.getToken() : null;
  }

  function updateAnalysisStatus() {
    const analysis = getAnalysis();
    const hasAnalysis = !!analysis;
    const startupName = analysis?.startup?.name || '';

    if (hasAnalysis) {
      badgeEl.className = 'chat-analysis-badge';
      badgeEl.innerHTML = `<span>✅ Analysis loaded${startupName ? ': ' + escapeHtml(startupName) : ''}</span>`;
      statusDot.className = 'chat-status-dot';
      analysisLabel.textContent = startupName ? 'Analysis: ' + startupName : 'Analysis loaded';
    } else {
      badgeEl.className = 'chat-analysis-badge no-analysis';
      badgeEl.innerHTML = '<span>⚠️ No analysis data found. Run an analysis first.</span><a href="analysis.html">Analyze Now →</a>';
      statusDot.className = 'chat-status-dot no-analysis';
      analysisLabel.textContent = 'No analysis loaded';
    }
  }

  function addMessage(text, role, intent) {
    const div = document.createElement('div');
    div.className = 'msg ' + role;
    let html = escapeHtml(text).replace(/\r?\n/g, '<br>');
    if (role === 'bot' && intent) {
      html += `<span class="msg-meta">intent: ${escapeHtml(intent)}</span>`;
    }
    div.innerHTML = html;
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function severityColor(val) {
    if (val === undefined || val === null) return 'yellow';
    if (typeof val === 'string') return severityColor(parseFloat(val));
    return val < 40 ? 'red' : val < 70 ? 'yellow' : 'green';
  }

  function suggestedQuestionsHtml(questions) {
    return `<div class="mentor-suggestions">${questions.map((question, index) =>
      `<button type="button" data-suggestion-index="${index}">${escapeHtml(question)}</button>`
    ).join('')}</div>`;
  }

  function wireSuggestedQuestions(container, questions) {
    container.querySelectorAll('[data-suggestion-index]').forEach(button => {
      const index = Number(button.dataset.suggestionIndex);
      if (Number.isInteger(index) && index >= 0 && index < questions.length) {
        button.addEventListener('click', () => send(questions[index]));
      }
    });
  }

  function renderBotResponse(data) {
    const div = document.createElement('div');
    div.className = 'msg bot';
    let html = '';
    const questions = Array.isArray(data.suggested_questions)
      ? data.suggested_questions.map(question => String(question ?? ''))
      : [];

    if (data.headline) {
      html += `<div class="mentor-headline">${escapeHtml(data.headline)}</div>`;
    }

    if (data.summary) {
      html += `<div class="mentor-summary">${escapeHtml(data.summary)}</div>`;
    }

    if (data.metrics && Array.isArray(data.metrics) && data.metrics.length > 0) {
      html += `<div class="mentor-metrics">`;
      data.metrics.forEach(m => {
        const cls = severityColor(m.severity);
        html += `<span class="mentor-metric-chip ${cls}">`;
        if (m.label) html += `<span>${escapeHtml(m.label)}</span>`;
        if (m.value !== undefined && m.value !== null) html += ` <strong>${escapeHtml(String(m.value))}</strong>`;
        html += `</span>`;
      });
      html += `</div>`;
    }

    if (data.insights && Array.isArray(data.insights) && data.insights.length > 0) {
      html += `<div class="mentor-section"><div class="mentor-section-title">${data.intent === 'risk_assessment' ? '🔍 Key Risks' : '💡 Key Insights'}</div>`;
      data.insights.forEach(item => {
        html += `<div class="mentor-insight-item">${escapeHtml(item)}</div>`;
      });
      html += `</div>`;
    }

    if (data.action_items && Array.isArray(data.action_items) && data.action_items.length > 0) {
      html += `<div class="mentor-section"><div class="mentor-section-title">✅ Recommended Actions</div>`;
      data.action_items.forEach(item => {
        const text = typeof item === 'string' ? item : (item.action || item.description || item.task || String(item));
        html += `<div class="mentor-action-item" onclick="this.querySelector('.mentor-action-checkbox').classList.toggle('checked')">
          <span class="mentor-action-checkbox"></span><span>${escapeHtml(text)}</span>
        </div>`;
      });
      html += `</div>`;
    }

    if (data.follow_up) {
      html += `<div class="mentor-follow-up">${escapeHtml(data.follow_up)}</div>`;
    }

    if (questions.length > 0) html += suggestedQuestionsHtml(questions);

    if (data.reply) {
      html += `<button class="mentor-deep-toggle" onclick="var n=this.nextElementSibling;n.classList.toggle('open');this.textContent=n.classList.contains('open')?'▲ Show less':'▼ Deep dive'">▼ Deep dive</button>`;
      html += `<div class="mentor-deep-content">${escapeHtml(data.reply).replace(/\r?\n/g, '<br>')}</div>`;
    }

    if (data.intent) {
      html += `<span class="msg-meta">intent: ${escapeHtml(data.intent)}</span>`;
    }

    div.innerHTML = html;
    messagesEl.appendChild(div);
    wireSuggestedQuestions(div, questions);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function renderMentorCards(data) {
    const div = document.createElement('div');
    div.className = 'msg bot';
    let html = '';
    const questions = Array.isArray(data.suggested_questions)
      ? data.suggested_questions.map(question => String(question ?? ''))
      : [];

    if (data.headline) {
      html += `<div class="mentor-headline">${escapeHtml(data.headline)}</div>`;
    }
    if (data.summary) {
      html += `<div class="mentor-summary">${escapeHtml(data.summary)}</div>`;
    }

    const medals = ['🥇', '🥈', '🥉'];
    if (data.mentors && Array.isArray(data.mentors)) {
      data.mentors.forEach((m, i) => {
        const badge = medals[i] || `${i+1}.`;
        const rawScore = Number(m.match_score);
        const score = Number.isFinite(rawScore) ? Math.max(0, Math.min(100, rawScore)) : 0;
        const severity = score >= 85 ? 'green' : score >= 70 ? 'yellow' : 'red';
        html += `<div style="background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);border-radius:10px;padding:.75rem 1rem;margin-bottom:.6rem">`;
        html += `<div style="display:flex;align-items:center;gap:.6rem;margin-bottom:.3rem">`;
        html += `<span style="font-size:1.1rem">${badge}</span>`;
        html += `<div style="flex:1"><strong>${escapeHtml(m.name)}</strong><br><span style="font-size:.78rem;color:var(--text-muted)">${escapeHtml(m.role || '')}</span></div>`;
        html += `<span class="mentor-metric-chip ${severity}">${score}%</span>`;
        html += `</div>`;
        if (m.why) {
          html += `<div style="font-size:.78rem;color:var(--text-secondary);padding-left:1.7rem;line-height:1.4">${escapeHtml(m.why)}</div>`;
        }
        html += `</div>`;
      });
    }

    if (data.action_items && data.action_items.length > 0) {
      html += `<div class="mentor-section" style="margin-top:.5rem"><div class="mentor-section-title">✅ Next Steps</div>`;
      data.action_items.forEach(item => {
        html += `<div class="mentor-action-item" onclick="this.querySelector('.mentor-action-checkbox').classList.toggle('checked')">
          <span class="mentor-action-checkbox"></span><span>${escapeHtml(item)}</span>
        </div>`;
      });
      html += `</div>`;
    }

    if (data.follow_up) {
      html += `<div class="mentor-follow-up">${escapeHtml(data.follow_up)}</div>`;
    }

    if (questions.length > 0) html += suggestedQuestionsHtml(questions);

    div.innerHTML = html;
    messagesEl.appendChild(div);
    wireSuggestedQuestions(div, questions);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function showTyping() {
    const div = document.createElement('div');
    div.className = 'chat-typing';
    div.id = 'chat-typing-indicator';
    div.innerHTML = '<span></span><span></span><span></span>';
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function hideTyping() {
    const el = document.getElementById('chat-typing-indicator');
    if (el) el.remove();
  }

  function setLoading(state) {
    isLoading = state;
    if (sendBtn) sendBtn.disabled = state;
    if (inputEl) inputEl.disabled = state;
  }

  // ── Sidebar rendering ──────────────────────────────────────────────────────

  function renderRecentChats(history) {
    allHistory = history;
    if (!recentChatsEl) return;
    recentChatsEl.innerHTML = '';

    if (!history || history.length === 0) {
      recentChatsEl.innerHTML = '<p style="color:var(--text-muted);font-size:.78rem;padding:.5rem 0">No conversations yet.</p>';
      return;
    }

    history.forEach(chat => {
      const rawMessageCount = Number(chat.message_count);
      const messageCount = Number.isFinite(rawMessageCount) && rawMessageCount > 0
        ? Math.floor(rawMessageCount)
        : 0;
      const btn = document.createElement('button');
      btn.className = 'chat-history-item';
      btn.innerHTML = `
        <div class="h-title">${escapeHtml(chat.title || 'Chat')}</div>
        <div class="h-meta">${messageCount} message${messageCount !== 1 ? 's' : ''}</div>
        ${chat.report_id ? '<div class="h-badge">Report</div>' : ''}
      `;
      btn.addEventListener('click', () => {
        loadConversation(chat.report_id || null);
      });
      recentChatsEl.appendChild(btn);
    });
  }

  function escapeHtml(str) {
    const d = document.createElement('div');
    d.textContent = str == null ? '' : String(str);
    return d.innerHTML;
  }

  // ── Load history for sidebar ───────────────────────────────────────────────

  async function loadChatHistory() {
    const token = await getToken();
    if (!token) return;

    try {
      const res = await fetch(API_URL + '/api/v1/chatbot/history', {
        headers: { Authorization: 'Bearer ' + token }
      });
      if (!res.ok) return;
      const data = await res.json();
      renderRecentChats(data.history || []);
    } catch (err) {
      console.error('Failed to load chat history:', err);
    }
  }

  // ── Load full conversation into chat ───────────────────────────────────────

  async function loadConversation(reportId) {
    const token = await getToken();
    if (!token) return;

    try {
      const res = await fetch(API_URL + '/api/v1/chatbot/history/raw', {
        headers: { Authorization: 'Bearer ' + token }
      });
      if (!res.ok) return;
      const data = await res.json();
      const messages = data.history || [];

      messagesEl.innerHTML = '';
      let loaded = 0;
      messages.forEach(item => {
        if (reportId === null) {
          if (item.report_id) return;
        } else {
          if (item.report_id !== reportId) return;
        }
        addMessage(item.message, 'user');
        addMessage(item.response, 'bot', item.intent);
        loaded++;
      });

      if (loaded === 0) {
        addWelcomeMessage();
      }
    } catch (err) {
      console.error('Failed to load conversation:', err);
    }
  }

  function addWelcomeMessage() {
    const div = document.createElement('div');
    div.className = 'msg bot';
    div.innerHTML = `Hi! I'm your startup intelligence assistant. Ask me anything about your analysis — survival score, risks, funding readiness, team evaluation, or recommendations.
      <div class="welcome-suggestions">
        <button onclick="window.ChatBot.send('What is my survival score?')">What is my survival score?</button>
        <button onclick="window.ChatBot.send('What are my biggest risks?')">What are my biggest risks?</button>
        <button onclick="window.ChatBot.send('How can I improve funding readiness?')">How can I improve funding readiness?</button>
        <button onclick="window.ChatBot.send('Analyze my startup')">Analyze my startup</button>
      </div>`;
    messagesEl.appendChild(div);
  }

  // ── Search filter ──────────────────────────────────────────────────────────

  function filterChats(query) {
    if (!allHistory.length) return;
    const q = query.toLowerCase();
    const filtered = allHistory.filter(c => (c.title || '').toLowerCase().includes(q));
    renderRecentChats(filtered);
  }

  // ── Send message ───────────────────────────────────────────────────────────

  async function send(message) {
    if (!message) return;
    if (isLoading) return;

    addMessage(message, 'user');
    inputEl.value = '';

    const token = await getToken();
    if (!token) {
      addMessage('Please sign in to use the AI Assistant.', 'bot');
      return;
    }

    const analysis = getAnalysis();
    const reportId = analysis?.report_id || null;
    showTyping();
    setLoading(true);

    try {
      const response = await fetch(API_URL + '/api/v1/mentor/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer ' + token,
        },
        body: JSON.stringify({
          message: message,
          report_id: reportId,
          structured: true,
        }),
      });

      hideTyping();

      if (!response.ok) {
        const errBody = await response.json().catch(() => ({}));
        addMessage('Sorry, I ran into an error: ' + (errBody.detail || 'Unknown error'), 'bot');
        setLoading(false);
        return;
      }

      // ── SSE stream reader ──
      const botDiv = document.createElement('div');
      botDiv.className = 'msg bot';
      const botContent = document.createElement('div');
      botDiv.appendChild(botContent);
      messagesEl.appendChild(botDiv);

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let structuredData = null;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n');
        buffer = parts.pop() || '';

        for (const line of parts) {
          const trimmed = line.trim();
          if (!trimmed || !trimmed.startsWith('data: ')) continue;

          try {
            const event = JSON.parse(trimmed.slice(6));

            if (event.type === 'structured') {
              structuredData = event.data;
            } else if (event.type === 'error') {
              botContent.textContent += '\n\n⚠️ ' + String(event.message || 'Error');
            }
          } catch (e) { /* skip malformed SSE lines */ }
        }
      }

      // Render structured data
      if (structuredData) {
        botDiv.remove(); // remove the empty streaming bubble
        if (structuredData.type === 'mentor_recommendation') {
          renderMentorCards(structuredData);
        } else {
          renderBotResponse(structuredData);
        }
      } else {
        botContent.innerHTML = '(no response)';
      }

    } catch (err) {
      hideTyping();
      addMessage('Network error — could not reach the server. Is the backend running?', 'bot');
    }

    setLoading(false);
    loadChatHistory();
  }

  function handleSend() {
    const text = (inputEl.value || '').trim();
    if (text) send(text);
  }

  function init() {
    updateAnalysisStatus();
    loadChatHistory();

    if (sendBtn) sendBtn.addEventListener('click', handleSend);
    if (inputEl) {
      inputEl.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          handleSend();
        }
      });
    }

    if (newChatBtn) {
      newChatBtn.addEventListener('click', () => {
        messagesEl.innerHTML = '';
        addWelcomeMessage();
      });
    }

    if (chatSearch) {
      chatSearch.addEventListener('input', (e) => filterChats(e.target.value));
    }

    window.ChatBot = { send };
  }

  document.addEventListener('DOMContentLoaded', init);
  if (document.readyState !== 'loading') init();

  return { send };
})();
