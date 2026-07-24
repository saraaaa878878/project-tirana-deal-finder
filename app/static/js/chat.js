/* chat.js — the floating assistant widget */
(function () {
  const panel = document.getElementById("chatPanel");
  const launcher = document.getElementById("chatLauncher");
  const closeBtn = document.getElementById("chatClose");
  const log = document.getElementById("chatLog");
  const form = document.getElementById("chatForm");
  const text = document.getElementById("chatText");
  const suggest = document.getElementById("chatSuggest");
  if (!panel) return;

  let conversationId = null;
  let busy = false;
  let greeted = false;

  // ---- Safe, tiny markdown renderer -------------------------------------
  // We escape ALL html first, then re-introduce only our own known-safe tags.
  // Listing links are restricted to /listing/<digits>, so no arbitrary URLs.
  function escapeHtml(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
  function inline(s) {
    return s
      // **bold**
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      // markdown listing link: [text](/listing/123)
      .replace(/\[([^\]]+)\]\(\/listing\/(\d+)\)/g,
               '<a class="chat-link" href="/listing/$2">$1</a>')
      // bare /listing/123 (anything not already linked above)
      .replace(/(^|[\s(])\/listing\/(\d+)/g,
               '$1<a class="chat-link" href="/listing/$2">listing $2</a>');
  }
  function renderRich(raw) {
    const lines = escapeHtml(raw).split("\n");
    let html = "";
    let inList = false;
    const closeList = () => { if (inList) { html += "</ul>"; inList = false; } };
    for (const line of lines) {
      const header = line.match(/^\s*#{1,6}\s+(.*)$/);
      const bullet = line.match(/^\s*[\*\-]\s+(.*)$/);
      if (header) {
        closeList();
        html += '<div class="chat-h">' + inline(header[1]) + "</div>";
      } else if (bullet) {
        if (!inList) { html += "<ul>"; inList = true; }
        html += "<li>" + inline(bullet[1]) + "</li>";
      } else if (line.trim() === "") {
        closeList();
      } else {
        closeList();
        html += "<p>" + inline(line) + "</p>";
      }
    }
    closeList();
    return html;
  }

  // ---- Open / close ------------------------------------------------------
  function open() {
    panel.classList.add("is-open");
    panel.setAttribute("aria-hidden", "false");
    launcher.classList.add("is-hidden");
    if (!greeted) {
      addBot("Hi! I can search listings, estimate a fair price, and find the best deals in Tirana. What are you after?");
      greeted = true;
    }
    setTimeout(() => text.focus(), 60);
  }
  function close() {
    panel.classList.remove("is-open");
    panel.setAttribute("aria-hidden", "true");
    launcher.classList.remove("is-hidden");
  }
  launcher.addEventListener("click", open);
  closeBtn.addEventListener("click", close);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && panel.classList.contains("is-open")) close();
  });

  suggest.querySelectorAll(".chat-chip").forEach((chip) => {
    chip.addEventListener("click", () => { text.value = chip.textContent; send(); });
  });

  text.addEventListener("input", () => {
    text.style.height = "auto";
    text.style.height = Math.min(text.scrollHeight, 120) + "px";
  });
  text.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  });
  form.addEventListener("submit", (e) => { e.preventDefault(); send(); });

  // ---- Messages ----------------------------------------------------------
  function addMsg(content, who, tools) {
    const el = document.createElement("div");
    el.className = "chat-msg chat-msg--" + who;
    if (who === "bot") {
      el.innerHTML = renderRich(content);   // safe: escaped + known tags only
    } else {
      el.textContent = content;             // user text is never rendered as html
    }
    if (tools && tools.length) {
      const tag = document.createElement("div");
      tag.className = "chat-tools";
      tag.textContent = "used: " + tools.join(", ");
      el.appendChild(tag);
    }
    log.appendChild(el);
    log.scrollTop = log.scrollHeight;
    return el;
  }
  const addUser = (t) => addMsg(t, "user");
  const addBot = (t, tools) => addMsg(t, "bot", tools);

  function addTyping() {
    const el = document.createElement("div");
    el.className = "chat-msg chat-msg--bot chat-typing";
    el.innerHTML = "<span></span><span></span><span></span>";
    log.appendChild(el);
    log.scrollTop = log.scrollHeight;
    return el;
  }

  async function send() {
    const message = text.value.trim();
    if (!message || busy) return;
    busy = true;
    suggest.classList.add("is-hidden");
    addUser(message);
    text.value = "";
    text.style.height = "auto";
    const typing = addTyping();

    try {
      const res = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: message, conversation_id: conversationId }),
      });
      const data = await res.json();
      typing.remove();
      if (data.conversation_id) conversationId = data.conversation_id;
      addBot(data.answer || "Sorry, I didn't catch that. Try again.", data.tools_used);
    } catch (err) {
      typing.remove();
      addBot("I couldn't reach the server. Check your connection and try again.");
    } finally {
      busy = false;
      text.focus();
    }
  }
})();
