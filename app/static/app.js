const ACTOR_ID = localStorage.getItem("agentcore.actorId") || "demo-user";

const state = {
  actorId: ACTOR_ID,
  sessionId: null,
  sessions: [],
  sending: false,
};

const els = {
  sidebar: document.getElementById("sidebar"),
  backdrop: document.getElementById("backdrop"),
  menuButton: document.getElementById("menuButton"),
  sidebarClose: document.getElementById("sidebarClose"),
  newChat: document.getElementById("newChat"),
  sessions: document.getElementById("sessions"),
  messages: document.getElementById("messages"),
  emptyState: document.getElementById("emptyState"),
  composer: document.getElementById("composer"),
  input: document.getElementById("input"),
  send: document.getElementById("send"),
  banner: document.getElementById("banner"),
  topbarTitle: document.getElementById("topbarTitle"),
  topbarSubtitle: document.getElementById("topbarSubtitle"),
  statusDot: document.getElementById("statusDot"),
  statusText: document.getElementById("statusText"),
};

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch (_) {
      /* ignore parse errors */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return response.json();
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatDate(value) {
  if (!value) return "Just now";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Just now";
  return date.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function setBanner(message, isError = false) {
  if (!message) {
    els.banner.classList.add("hidden");
    els.banner.textContent = "";
    return;
  }
  els.banner.textContent = message;
  els.banner.classList.toggle("error", isError);
  els.banner.classList.remove("hidden");
}

function setStatus(ok, text) {
  els.statusDot.classList.remove("ok", "error");
  if (ok === true) els.statusDot.classList.add("ok");
  if (ok === false) els.statusDot.classList.add("error");
  els.statusText.textContent = text;
}

function openSidebar() {
  els.sidebar.classList.add("open");
  els.backdrop.classList.remove("hidden");
}

function closeSidebar() {
  els.sidebar.classList.remove("open");
  els.backdrop.classList.add("hidden");
}

function showEmptyState(show) {
  els.emptyState.classList.toggle("hidden", !show);
}

function scrollToBottom() {
  els.messages.scrollTop = els.messages.scrollHeight;
}

function renderSessions() {
  els.sessions.innerHTML = "";
  if (state.sessions.length === 0) {
    const empty = document.createElement("p");
    empty.className = "sessions-empty";
    empty.textContent = "No conversations yet.";
    els.sessions.appendChild(empty);
    return;
  }

  for (const session of state.sessions) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "session-item";
    if (session.session_id === state.sessionId) button.classList.add("active");

    const title = document.createElement("span");
    title.className = "session-title";
    title.textContent = formatDate(session.created_at);

    const meta = document.createElement("span");
    meta.className = "session-meta";
    meta.textContent = `session ${session.session_id.slice(0, 8)}`;

    button.append(title, meta);
    button.addEventListener("click", () => {
      selectSession(session.session_id);
      closeSidebar();
    });
    els.sessions.appendChild(button);
  }
}

function addMessage(role, text, { error = false } = {}) {
  showEmptyState(false);

  const row = document.createElement("div");
  row.className = `message-row ${role}`;

  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.textContent = role === "user" ? "You" : "AI";

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  if (error) bubble.classList.add("error");
  bubble.textContent = text;

  row.append(avatar, bubble);
  els.messages.appendChild(row);
  scrollToBottom();
  return row;
}

function addTyping() {
  showEmptyState(false);
  const row = document.createElement("div");
  row.className = "message-row assistant";

  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.textContent = "AI";

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.innerHTML =
    '<span class="typing"><span></span><span></span><span></span></span>';

  row.append(avatar, bubble);
  els.messages.appendChild(row);
  scrollToBottom();
  return row;
}

function setTopbar(title, subtitle) {
  els.topbarTitle.textContent = title;
  els.topbarSubtitle.textContent = subtitle;
}

async function refreshSessions() {
  try {
    state.sessions = await api(
      `/api/sessions?actor_id=${encodeURIComponent(state.actorId)}`
    );
    renderSessions();
  } catch (error) {
    setBanner(`Could not load sessions: ${error.message}`, true);
  }
}

async function selectSession(sessionId) {
  if (state.sending) return;
  state.sessionId = sessionId;
  els.messages.querySelectorAll(".message-row").forEach((el) => el.remove());
  renderSessions();
  setTopbar(`Session ${sessionId.slice(0, 8)}`, "Loading conversation…");

  try {
    const messages = await api(
      `/api/sessions/${encodeURIComponent(sessionId)}/messages?actor_id=${encodeURIComponent(
        state.actorId
      )}`
    );
    if (messages.length === 0) {
      showEmptyState(true);
      setTopbar("New chat", "Stored in Amazon Bedrock AgentCore Memory");
      return;
    }
    for (const message of messages) {
      addMessage(message.role === "assistant" ? "assistant" : "user", message.text);
    }
    setTopbar(
      `Session ${sessionId.slice(0, 8)}`,
      `${messages.length} message${messages.length === 1 ? "" : "s"}`
    );
  } catch (error) {
    addMessage("assistant", `Could not load this conversation: ${error.message}`, {
      error: true,
    });
    setTopbar("Session error", "Try selecting the conversation again.");
  }
}

function startNewChat() {
  if (state.sending) return;
  state.sessionId = null;
  els.messages.querySelectorAll(".message-row").forEach((el) => el.remove());
  showEmptyState(true);
  renderSessions();
  setTopbar("New chat", "Stored in Amazon Bedrock AgentCore Memory");
  els.input.focus();
}

async function ensureSession() {
  if (state.sessionId) return state.sessionId;
  const data = await api("/api/sessions", { method: "POST", body: "{}" });
  state.sessionId = data.session_id;
  return state.sessionId;
}

async function sendMessage() {
  const text = els.input.value.trim();
  if (!text || state.sending) return;

  state.sending = true;
  els.send.disabled = true;
  els.input.value = "";
  autosize();
  setBanner("");

  addMessage("user", text);
  const typingRow = addTyping();

  try {
    const sessionId = await ensureSession();
    const data = await api("/api/chat", {
      method: "POST",
      body: JSON.stringify({
        session_id: sessionId,
        message: text,
        actor_id: state.actorId,
      }),
    });

    typingRow.remove();
    addMessage("assistant", data.reply);
    setTopbar(
      `Session ${sessionId.slice(0, 8)}`,
      "Stored in Amazon Bedrock AgentCore Memory"
    );
    await refreshSessions();
  } catch (error) {
    typingRow.remove();
    addMessage("assistant", `Request failed: ${error.message}`, { error: true });
    setBanner(error.message, true);
  } finally {
    state.sending = false;
    els.send.disabled = false;
    els.input.focus();
  }
}

function autosize() {
  els.input.style.height = "auto";
  els.input.style.height = `${Math.min(els.input.scrollHeight, 180)}px`;
}

async function checkHealth() {
  try {
    const health = await api("/api/health");
    if (health.ready) {
      setStatus(true, `Memory ACTIVE · ${health.region}`);
      setBanner("");
    } else {
      setStatus(false, health.memory_status || "Memory not ready");
      setBanner(
        health.detail
          ? `AgentCore Memory is not ready: ${health.detail}`
          : "AgentCore Memory is not ACTIVE yet. Run scripts/create_memory.py and update config.py.",
        true
      );
    }
  } catch (error) {
    setStatus(false, "Backend unreachable");
    setBanner(`Backend health check failed: ${error.message}`, true);
  }
}

els.composer.addEventListener("submit", (event) => {
  event.preventDefault();
  sendMessage();
});

els.input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    sendMessage();
  }
});

els.input.addEventListener("input", autosize);
els.newChat.addEventListener("click", startNewChat);
els.menuButton.addEventListener("click", openSidebar);
els.sidebarClose.addEventListener("click", closeSidebar);
els.backdrop.addEventListener("click", closeSidebar);

document.querySelectorAll(".suggestion").forEach((button) => {
  button.addEventListener("click", () => {
    els.input.value = button.dataset.prompt || "";
    autosize();
    els.input.focus();
  });
});

async function init() {
  await checkHealth();
  await refreshSessions();
  els.input.focus();
}

init();
