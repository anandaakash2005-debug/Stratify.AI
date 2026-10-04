/* ============================================
   CHATBOT.JS — AI Startup Intelligence Chat
   ChatGPT-style sidebar + conversation history
   ============================================ */

import { CONFIG } from "./config.js";

const ChatBot = (() => {
  const API_URL = CONFIG.API_URL;

  const messagesEl = document.getElementById("chat-messages");
  const inputEl = document.getElementById("chat-input");
  const sendBtn = document.getElementById("chat-send-btn");
  const badgeEl = document.getElementById("analysis-badge");
  const statusDot = document.getElementById("chat-status-dot");
  const analysisLabel = document.getElementById("analysis-label");
  const recentChatsEl = document.getElementById("recent-chats");
  const newChatBtn = document.getElementById("new-chat-btn");
  const chatSearch = document.getElementById("chat-search");

  let isLoading = false;
  let allHistory = [];

  function escapeHtml(value) {
    const element = document.createElement("div");
    element.textContent = value == null ? "" : String(value);
    return element.innerHTML;
  }

  function getAnalysis() {
    try {
      const raw = localStorage.getItem("latest_analysis");
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  }

  async function getToken() {
    try {
      const module = await import("./supabase.js");
      const { data } = await module.supabase.auth.getSession();

      if (data?.session?.access_token) {
        return data.session.access_token;
      }
    } catch (error) {
      console.error("Unable to read the Supabase session:", error);
    }

    if (typeof window.Auth !== "undefined" && window.Auth.getToken) {
      return window.Auth.getToken();
    }

    return null;
  }

  function updateAnalysisStatus() {
    if (!badgeEl || !statusDot || !analysisLabel) {
      return;
    }

    const analysis = getAnalysis();
    const hasAnalysis = Boolean(analysis);
    const startupName = analysis?.startup?.name || "";

    if (hasAnalysis) {
      badgeEl.className = "chat-analysis-badge";
      badgeEl.innerHTML = `<span>✅ Analysis loaded${
        startupName ? `: ${escapeHtml(startupName)}` : ""
      }</span>`;

      statusDot.className = "chat-status-dot";
      analysisLabel.textContent = startupName
        ? `Analysis: ${startupName}`
        : "Analysis loaded";

      return;
    }

    badgeEl.className = "chat-analysis-badge no-analysis";
    badgeEl.innerHTML =
      '<span>⚠️ No analysis data found. Run an analysis first.</span>' +
      '<a href="analysis.html">Analyze Now →</a>';

    statusDot.className = "chat-status-dot no-analysis";
    analysisLabel.textContent = "No analysis loaded";
  }

  function addMessage(text, role, intent) {
    if (!messagesEl) {
      return;
    }

    const message = document.createElement("div");
    message.className = `msg ${role}`;

    let html = escapeHtml(text).replace(/\r?\n/g, "<br>");

    if (role === "bot" && intent) {
      html += `<span class="msg-meta">intent: ${escapeHtml(
        intent
      )}</span>`;
    }

    message.innerHTML = html;
    messagesEl.appendChild(message);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function severityColor(value) {
    if (value === undefined || value === null) {
      return "yellow";
    }

    const numericValue =
      typeof value === "string" ? Number.parseFloat(value) : Number(value);

    if (!Number.isFinite(numericValue)) {
      return "yellow";
    }

    if (numericValue < 40) {
      return "red";
    }

    if (numericValue < 70) {
      return "yellow";
    }

    return "green";
  }

  function suggestedQuestionsHtml(questions) {
    return `
      <div class="mentor-suggestions">
        ${questions
          .map(
            (question, index) => `
              <button
                type="button"
                data-suggestion-index="${index}"
              >
                ${escapeHtml(question)}
              </button>
            `
          )
          .join("")}
      </div>
    `;
  }

  function wireSuggestedQuestions(container, questions) {
    container
      .querySelectorAll("[data-suggestion-index]")
      .forEach((button) => {
        const index = Number(button.dataset.suggestionIndex);

        if (
          Number.isInteger(index) &&
          index >= 0 &&
          index < questions.length
        ) {
          button.addEventListener("click", () => {
            send(questions[index]);
          });
        }
      });
  }

  function renderBotResponse(data) {
    if (!messagesEl) {
      return;
    }

    const message = document.createElement("div");
    message.className = "msg bot";

    let html = "";

    const questions = Array.isArray(data.suggested_questions)
      ? data.suggested_questions
          .map((question) => String(question ?? "").trim())
          .filter(Boolean)
      : [];

    if (data.headline) {
      html += `
        <div class="mentor-headline">
          ${escapeHtml(data.headline)}
        </div>
      `;
    }

    if (data.summary) {
      html += `
        <div class="mentor-summary">
          ${escapeHtml(data.summary)}
        </div>
      `;
    }

    if (Array.isArray(data.metrics) && data.metrics.length > 0) {
      html += '<div class="mentor-metrics">';

      data.metrics.forEach((metric) => {
        if (!metric || typeof metric !== "object") {
          return;
        }

        const severity = severityColor(metric.severity);

        html += `<span class="mentor-metric-chip ${severity}">`;

        if (metric.label) {
          html += `<span>${escapeHtml(metric.label)}</span>`;
        }

        if (metric.value !== undefined && metric.value !== null) {
          html += `<strong>${escapeHtml(String(metric.value))}</strong>`;
        }

        html += "</span>";
      });

      html += "</div>";
    }

    if (Array.isArray(data.insights) && data.insights.length > 0) {
      const sectionTitle =
        data.intent === "risk_assessment"
          ? "🔍 Key Risks"
          : "💡 Key Insights";

      html += `
        <div class="mentor-section">
          <div class="mentor-section-title">${sectionTitle}</div>
      `;

      data.insights.forEach((item) => {
        html += `
          <div class="mentor-insight-item">
            ${escapeHtml(item)}
          </div>
        `;
      });

      html += "</div>";
    }

    if (
      Array.isArray(data.action_items) &&
      data.action_items.length > 0
    ) {
      html += `
        <div class="mentor-section">
          <div class="mentor-section-title">
            ✅ Recommended Actions
          </div>
      `;

      data.action_items.forEach((item) => {
        let itemText = "";

        if (typeof item === "string") {
          itemText = item;
        } else if (item && typeof item === "object") {
          itemText =
            item.action ||
            item.description ||
            item.task ||
            "Recommended action";
        }

        html += `
          <button
            type="button"
            class="mentor-action-item"
          >
            <span class="mentor-action-checkbox"></span>
            <span>${escapeHtml(itemText)}</span>
          </button>
        `;
      });

      html += "</div>";
    }

    if (data.follow_up) {
      html += `
        <div class="mentor-follow-up">
          ${escapeHtml(data.follow_up)}
        </div>
      `;
    }

    if (questions.length > 0) {
      html += suggestedQuestionsHtml(questions);
    }

    if (data.reply) {
      html += `
        <button
          type="button"
          class="mentor-deep-toggle"
        >
          ▼ Deep dive
        </button>
        <div class="mentor-deep-content">
          ${escapeHtml(data.reply).replace(/\r?\n/g, "<br>")}
        </div>
      `;
    }

    if (data.intent) {
      html += `
        <span class="msg-meta">
          intent: ${escapeHtml(data.intent)}
        </span>
      `;
    }

    if (!html.trim()) {
      html = `
        <div class="mentor-summary">
          I received a response, but it did not contain displayable content.
        </div>
      `;
    }

    message.innerHTML = html;
    messagesEl.appendChild(message);

    message.querySelectorAll(".mentor-action-item").forEach((button) => {
      button.addEventListener("click", () => {
        const checkbox = button.querySelector(
          ".mentor-action-checkbox"
        );

        checkbox?.classList.toggle("checked");
      });
    });

    const deepToggle = message.querySelector(".mentor-deep-toggle");
    const deepContent = message.querySelector(".mentor-deep-content");

    if (deepToggle && deepContent) {
      deepToggle.addEventListener("click", () => {
        deepContent.classList.toggle("open");

        deepToggle.textContent = deepContent.classList.contains("open")
          ? "▲ Show less"
          : "▼ Deep dive";
      });
    }

    wireSuggestedQuestions(message, questions);

    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function renderMentorCards(data) {
    if (!messagesEl) {
      return;
    }

    const message = document.createElement("div");
    message.className = "msg bot";

    let html = "";

    const questions = Array.isArray(data.suggested_questions)
      ? data.suggested_questions
          .map((question) => String(question ?? "").trim())
          .filter(Boolean)
      : [];

    if (data.headline) {
      html += `
        <div class="mentor-headline">
          ${escapeHtml(data.headline)}
        </div>
      `;
    }

    if (data.summary) {
      html += `
        <div class="mentor-summary">
          ${escapeHtml(data.summary)}
        </div>
      `;
    }

    const medals = ["🥇", "🥈", "🥉"];

    if (Array.isArray(data.mentors) && data.mentors.length > 0) {
      data.mentors.forEach((mentor, index) => {
        if (!mentor || typeof mentor !== "object") {
          return;
        }

        const badge = medals[index] || `${index + 1}.`;
        const rawScore = Number(mentor.match_score);

        const score = Number.isFinite(rawScore)
          ? Math.max(0, Math.min(100, rawScore))
          : 0;

        const severity =
          score >= 85 ? "green" : score >= 70 ? "yellow" : "red";

        html += `
          <div class="mentor-card">
            <div class="mentor-card-header">
              <span class="mentor-card-medal">${badge}</span>

              <div class="mentor-card-identity">
                <strong>${escapeHtml(
                  mentor.name || "Verified mentor"
                )}</strong>

                <span>${escapeHtml(mentor.role || "")}</span>
              </div>

              <span class="mentor-metric-chip ${severity}">
                ${score}%
              </span>
            </div>
        `;

        if (mentor.why) {
          html += `
            <div class="mentor-card-reason">
              ${escapeHtml(mentor.why)}
            </div>
          `;
        }

        html += "</div>";
      });
    }

    if (
      Array.isArray(data.action_items) &&
      data.action_items.length > 0
    ) {
      html += `
        <div class="mentor-section mentor-next-steps">
          <div class="mentor-section-title">✅ Next Steps</div>
      `;

      data.action_items.forEach((item) => {
        html += `
          <button
            type="button"
            class="mentor-action-item"
          >
            <span class="mentor-action-checkbox"></span>
            <span>${escapeHtml(item)}</span>
          </button>
        `;
      });

      html += "</div>";
    }

    if (data.follow_up) {
      html += `
        <div class="mentor-follow-up">
          ${escapeHtml(data.follow_up)}
        </div>
      `;
    }

    if (questions.length > 0) {
      html += suggestedQuestionsHtml(questions);
    }

    if (!html.trim()) {
      html = `
        <div class="mentor-summary">
          No verified mentor recommendations are currently available.
        </div>
      `;
    }

    message.innerHTML = html;
    messagesEl.appendChild(message);

    message.querySelectorAll(".mentor-action-item").forEach((button) => {
      button.addEventListener("click", () => {
        const checkbox = button.querySelector(
          ".mentor-action-checkbox"
        );

        checkbox?.classList.toggle("checked");
      });
    });

    wireSuggestedQuestions(message, questions);

    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function showTyping() {
    if (!messagesEl) {
      return;
    }

    hideTyping();

    const typingIndicator = document.createElement("div");
    typingIndicator.className = "chat-typing";
    typingIndicator.id = "chat-typing-indicator";
    typingIndicator.setAttribute("aria-label", "AI is thinking");
    typingIndicator.innerHTML =
      "<span></span><span></span><span></span>";

    messagesEl.appendChild(typingIndicator);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function hideTyping() {
    document.getElementById("chat-typing-indicator")?.remove();
  }

  function setLoading(state) {
    isLoading = state;

    if (sendBtn) {
      sendBtn.disabled = state;
    }

    if (inputEl) {
      inputEl.disabled = state;
    }
  }

  function renderRecentChats(history) {
    allHistory = Array.isArray(history) ? history : [];

    if (!recentChatsEl) {
      return;
    }

    recentChatsEl.replaceChildren();

    if (allHistory.length === 0) {
      const emptyMessage = document.createElement("p");
      emptyMessage.className = "sidebar-empty-message";
      emptyMessage.textContent = "No conversations yet.";
      recentChatsEl.appendChild(emptyMessage);
      return;
    }

    allHistory.forEach((chat) => {
      const rawMessageCount = Number(chat.message_count);

      const messageCount =
        Number.isFinite(rawMessageCount) && rawMessageCount > 0
          ? Math.floor(rawMessageCount)
          : 0;

      const button = document.createElement("button");
      button.type = "button";
      button.className = "chat-history-item";

      const title = document.createElement("div");
      title.className = "h-title";
      title.textContent = chat.title || "Chat";

      const metadata = document.createElement("div");
      metadata.className = "h-meta";
      metadata.textContent = `${messageCount} message${
        messageCount !== 1 ? "s" : ""
      }`;

      button.append(title, metadata);

      if (chat.report_id) {
        const badge = document.createElement("div");
        badge.className = "h-badge";
        badge.textContent = "Report";
        button.appendChild(badge);
      }

      button.addEventListener("click", () => {
        loadConversation(chat.report_id || null);
      });

      recentChatsEl.appendChild(button);
    });
  }

  async function loadChatHistory() {
    const token = await getToken();

    if (!token) {
      return;
    }

    try {
      const response = await fetch(
        `${API_URL}/api/v1/chatbot/history`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (!response.ok) {
        console.error(
          "Failed to load chat history:",
          response.status
        );
        return;
      }

      const data = await response.json();
      renderRecentChats(data.history || []);
    } catch (error) {
      console.error("Failed to load chat history:", error);
    }
  }

  async function loadConversation(reportId) {
    const token = await getToken();

    if (!token || !messagesEl) {
      return;
    }

    try {
      const response = await fetch(
        `${API_URL}/api/v1/chatbot/history/raw`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (!response.ok) {
        console.error(
          "Failed to load the conversation:",
          response.status
        );
        return;
      }

      const data = await response.json();
      const history = Array.isArray(data.history) ? data.history : [];

      messagesEl.replaceChildren();

      let loadedMessages = 0;

      history.forEach((item) => {
        const belongsToConversation =
          reportId === null
            ? !item.report_id
            : item.report_id === reportId;

        if (!belongsToConversation) {
          return;
        }

        addMessage(item.message, "user");
        addMessage(item.response, "bot", item.intent);
        loadedMessages += 1;
      });

      if (loadedMessages === 0) {
        addWelcomeMessage();
      }
    } catch (error) {
      console.error("Failed to load conversation:", error);
    }
  }

  function createSuggestionButton(question) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = question;

    button.addEventListener("click", () => {
      send(question);
    });

    return button;
  }

  function addWelcomeMessage() {
    if (!messagesEl) {
      return;
    }

    const message = document.createElement("div");
    message.className = "msg bot";

    const introduction = document.createElement("div");
    introduction.textContent =
      "Hi! I'm your startup intelligence assistant. Ask me anything about your analysis — survival score, risks, funding readiness, team evaluation, or recommendations.";

    const suggestions = document.createElement("div");
    suggestions.className = "welcome-suggestions";

    [
      "What is my survival score?",
      "What are my biggest risks?",
      "How can I improve funding readiness?",
      "Analyze my startup",
    ].forEach((question) => {
      suggestions.appendChild(createSuggestionButton(question));
    });

    message.append(introduction, suggestions);
    messagesEl.appendChild(message);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function filterChats(query) {
    const normalizedQuery = String(query || "")
      .trim()
      .toLowerCase();

    if (!normalizedQuery) {
      renderRecentChats(allHistory);
      return;
    }

    const filteredHistory = allHistory.filter((chat) =>
      String(chat.title || "")
        .toLowerCase()
        .includes(normalizedQuery)
    );

    renderRecentChats(filteredHistory);
  }

  function processSseEvent(event, streamState) {
    if (!event || typeof event !== "object") {
      return;
    }

    if (event.type === "structured") {
      streamState.structuredData = event.data;
      return;
    }

    if (event.type === "token") {
      const tokenText = String(
        event.content ?? event.token ?? event.text ?? ""
      );

      streamState.tokenText += tokenText;
      streamState.botContent.textContent = streamState.tokenText;
      messagesEl.scrollTop = messagesEl.scrollHeight;
      return;
    }

    if (event.type === "error") {
      const message = String(
        event.message || "The AI service returned an error."
      );

      streamState.errorMessage = message;
      streamState.botContent.textContent = `⚠️ ${message}`;
    }
  }

  function processSseLine(line, streamState) {
    const trimmedLine = line.trim();

    if (
      !trimmedLine ||
      trimmedLine.startsWith(":") ||
      !trimmedLine.startsWith("data:")
    ) {
      return;
    }

    const payload = trimmedLine.slice(5).trim();

    if (!payload || payload === "[DONE]") {
      return;
    }

    try {
      const event = JSON.parse(payload);
      processSseEvent(event, streamState);
    } catch (error) {
      console.warn("Skipped an invalid SSE event.", error);
    }
  }

  async function readStream(response, botContent) {
    if (!response.body) {
      throw new Error("The response stream is unavailable.");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    const streamState = {
      botContent,
      structuredData: null,
      tokenText: "",
      errorMessage: "",
    };

    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();

      if (done) {
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split(/\r?\n/);
      buffer = lines.pop() || "";

      lines.forEach((line) => {
        processSseLine(line, streamState);
      });
    }

    buffer += decoder.decode();

    if (buffer.trim()) {
      processSseLine(buffer, streamState);
    }

    return streamState;
  }

  async function send(message) {
    const cleanMessage = String(message || "").trim();

    if (
      !cleanMessage ||
      isLoading ||
      !messagesEl ||
      !inputEl
    ) {
      return;
    }

    addMessage(cleanMessage, "user");
    inputEl.value = "";

    const token = await getToken();

    if (!token) {
      addMessage(
        "Please sign in to use the AI Assistant.",
        "bot"
      );
      return;
    }

    const analysis = getAnalysis();
    const reportId = analysis?.report_id || null;

    showTyping();
    setLoading(true);

    try {
      const response = await fetch(
        `${API_URL}/api/v1/mentor/chat`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            message: cleanMessage,
            report_id: reportId,
            structured: true,
          }),
        }
      );

      hideTyping();

      if (!response.ok) {
        const errorBody = await response
          .json()
          .catch(() => ({}));

        addMessage(
          `Sorry, I ran into an error: ${
            errorBody.detail ||
            `Server returned status ${response.status}`
          }`,
          "bot"
        );

        return;
      }

      const botMessage = document.createElement("div");
      botMessage.className = "msg bot";

      const botContent = document.createElement("div");
      botContent.textContent = "";

      botMessage.appendChild(botContent);
      messagesEl.appendChild(botMessage);

      const streamState = await readStream(
        response,
        botContent
      );

      if (streamState.structuredData) {
        botMessage.remove();

        if (
          streamState.structuredData.type ===
          "mentor_recommendation"
        ) {
          renderMentorCards(streamState.structuredData);
        } else {
          renderBotResponse(streamState.structuredData);
        }
      } else if (streamState.errorMessage) {
        botContent.textContent = `⚠️ ${streamState.errorMessage}`;
      } else if (!streamState.tokenText.trim()) {
        botContent.textContent =
          "The AI returned an empty response. Please retry.";
      }

      messagesEl.scrollTop = messagesEl.scrollHeight;
    } catch (error) {
      console.error("AI Assistant request failed:", error);
      hideTyping();

      addMessage(
        "Network error — the AI Assistant could not reach the server. Please retry.",
        "bot"
      );
    } finally {
      setLoading(false);
      loadChatHistory();

      if (inputEl) {
        inputEl.focus();
      }
    }
  }

  function handleSend() {
    const text = inputEl?.value?.trim() || "";

    if (text) {
      send(text);
    }
  }

  function init() {
    updateAnalysisStatus();
    loadChatHistory();

    sendBtn?.addEventListener("click", handleSend);

    inputEl?.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        handleSend();
      }
    });

    newChatBtn?.addEventListener("click", () => {
      messagesEl?.replaceChildren();
      addWelcomeMessage();
      inputEl?.focus();
    });

    chatSearch?.addEventListener("input", (event) => {
      filterChats(event.target.value);
    });

    window.ChatBot = {
      send,
    };
  }

  if (document.readyState === "loading") {
    document.addEventListener(
      "DOMContentLoaded",
      init,
      { once: true }
    );
  } else {
    init();
  }

  return {
    send,
  };
})();