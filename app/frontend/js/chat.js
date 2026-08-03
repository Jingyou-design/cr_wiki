import { streamChat } from "./api.js?v=20260728-sse";
import { currentUser } from "./auth.js?v=20260730-manager2";
import { renderMarkdown } from "./markdown.js?v=20260729-book1";
import { setBusy, showToast } from "./ui.js";

const CHAT_STORAGE_PREFIX = "deepbook-chat:";

export function createChatController({ userId, configRevision }) {
  const elements = {
    answer: document.querySelector("#chatAnswer"),
    answerContent: document.querySelector("#chatAnswerContent"),
    answerEmpty: document.querySelector("#chatAnswerEmpty"),
    button: document.querySelector("#chatButton"),
    form: document.querySelector("#chatForm"),
    messages: document.querySelector("#chatMessages"),
    question: document.querySelector("#chatQuestion"),
    sources: document.querySelector("#chatSourceList"),
  };
  const state = {
    ready: false,
    busy: false,
    conversationId: null,
    configRevision,
    messages: [],
    sources: [],
  };
  const storageKey = `${CHAT_STORAGE_PREFIX}${userId}:${configRevision}`;

  elements.form.addEventListener("submit", ask);
  elements.question.addEventListener("input", resizeInput);
  elements.question.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      elements.form.requestSubmit();
    }
  });
  removeStaleSessions();
  restoreSession();

  function setReady(ready) {
    state.ready = Boolean(ready);
    elements.question.disabled = !state.ready || state.busy;
    elements.button.disabled = !state.ready || state.busy;
  }

  async function ask(event) {
    event.preventDefault();
    if (
      !state.ready ||
      state.busy ||
      !elements.form.reportValidity()
    ) {
      return;
    }
    const question = elements.question.value.trim();
    if (!question) return;

    state.busy = true;
    setBusy(elements.button, true, "校验中", "发送");
    elements.question.disabled = true;
    try {
      const latestUser = await currentUser();
      if (latestUser.config_revision !== state.configRevision) {
        showToast("权限配置已更新，正在刷新页面。", "info");
        window.setTimeout(() => window.location.reload(), 600);
        return;
      }
    } catch (error) {
      state.busy = false;
      setBusy(elements.button, false, "校验中", "发送");
      setReady(state.ready);
      showToast(error.message, "error");
      return;
    }

    const payload = { question };
    if (state.conversationId) {
      payload.conversation_id = state.conversationId;
    }

    setBusy(elements.button, true, "检索中", "发送");
    elements.answerEmpty.hidden = true;
    elements.answerContent.hidden = false;
    elements.sources.replaceChildren();
    state.sources = [];
    appendTurn("user", question);
    state.messages.push({ role: "user", content: question });
    const answerElement = appendTurn(
      "assistant",
      "正在检索公司资料并组织回答…",
    );
    const answerMessage = { role: "assistant", content: "" };
    state.messages.push(answerMessage);
    saveSession();
    let answer = "";

    try {
      await streamChat(payload, (eventData) => {
        if (eventData.type === "start") {
          state.conversationId = eventData.conversation_id;
          saveSession();
        } else if (eventData.type === "delta") {
          answer += eventData.content;
          answerMessage.content = answer;
          renderMarkdown(answerElement, answer);
          elements.answer.scrollTop = elements.answer.scrollHeight;
        } else if (eventData.type === "done") {
          state.sources = Array.isArray(eventData.sources)
            ? eventData.sources.map(String)
            : [];
          renderSources(state.sources);
          saveSession();
        } else if (eventData.type === "error") {
          throw new Error(eventData.detail || "知识库问答失败。");
        }
      });
      if (!answer) {
        throw new Error("知识库问答 Agent 没有返回有效回答。");
      }
      elements.question.value = "";
      resizeInput();
    } catch (error) {
      const errorMessage = error.message || "知识库问答失败。";
      answerMessage.content = answer || errorMessage;
      if (answer) {
        renderMarkdown(answerElement, answer);
      } else {
        answerElement.textContent = errorMessage;
      }
      state.sources = [];
      elements.sources.replaceChildren();
      saveSession();
      showToast(errorMessage, "error");
    } finally {
      if (answer) {
        answerMessage.content = answer;
        saveSession();
      }
      state.busy = false;
      setBusy(elements.button, false, "检索中", "发送");
      setReady(state.ready);
    }
  }

  function appendTurn(role, text) {
    elements.answerEmpty.hidden = true;
    elements.answerContent.hidden = false;
    const turn = document.createElement("article");
    turn.className = `chat-turn is-${role}`;
    const content = document.createElement("div");
    content.className =
      role === "assistant"
        ? "chat-answer-text markdown-body"
        : "chat-answer-text";
    content.textContent = text;
    if (role === "assistant") {
      const label = document.createElement("p");
      label.className = "chat-answer-label";
      label.textContent = "知识库回答";
      turn.append(label);
    }
    turn.append(content);
    elements.messages.append(turn);
    return content;
  }

  function renderSources(sources) {
    elements.sources.replaceChildren();
    if (!Array.isArray(sources) || sources.length === 0) return;
    const heading = document.createElement("strong");
    heading.textContent = "本次回答来源";
    elements.sources.append(heading);
    for (const source of sources) {
      const sourcePath = String(source);
      const normalizedPath = sourcePath
        .replaceAll("\\", "/");
      const wikiPath = normalizedPath.replace(
        /^\/?generated-wiki\/drafts\//,
        "",
      );
      if (wikiPath !== normalizedPath) {
        const link = document.createElement("a");
        link.className = "chat-source-link";
        link.href = `/book?path=${encodeURIComponent(wikiPath)}`;
        link.textContent = sourcePath;
        elements.sources.append(link);
      } else {
        const path = document.createElement("code");
        path.textContent = sourcePath;
        elements.sources.append(path);
      }
    }
  }

  function restoreSession() {
    let saved;
    try {
      saved = JSON.parse(window.sessionStorage.getItem(storageKey) || "null");
    } catch {
      try {
        window.sessionStorage.removeItem(storageKey);
      } catch {
        // Ignore browsers that block session storage.
      }
      return;
    }
    if (
      !saved
      || saved.version !== 1
      || !Array.isArray(saved.messages)
    ) {
      return;
    }
    state.conversationId =
      typeof saved.conversationId === "string"
        ? saved.conversationId
        : null;
    state.messages = saved.messages
      .filter((message) => (
        (message?.role === "user" || message?.role === "assistant")
        && typeof message.content === "string"
        && message.content
      ))
      .map((message) => ({
        role: message.role,
        content: message.content,
      }));
    state.sources = Array.isArray(saved.sources)
      ? saved.sources.map(String)
      : [];
    for (const message of state.messages) {
      const content = appendTurn(message.role, message.content);
      if (message.role === "assistant") {
        renderMarkdown(content, message.content);
      }
    }
    renderSources(state.sources);
    if (state.messages.length) {
      elements.answer.scrollTop = elements.answer.scrollHeight;
    }
  }

  function saveSession() {
    try {
      window.sessionStorage.setItem(
        storageKey,
        JSON.stringify({
          version: 1,
          conversationId: state.conversationId,
          messages: state.messages,
          sources: state.sources,
        }),
      );
    } catch {
      // Chat remains usable when browser storage is unavailable or full.
    }
  }

  function removeStaleSessions() {
    const userPrefix = `${CHAT_STORAGE_PREFIX}${userId}:`;
    try {
      for (let index = window.sessionStorage.length - 1; index >= 0; index -= 1) {
        const key = window.sessionStorage.key(index);
        if (key?.startsWith(userPrefix) && key !== storageKey) {
          window.sessionStorage.removeItem(key);
        }
      }
    } catch {
      // Ignore browsers that block session storage.
    }
  }

  function resizeInput() {
    elements.question.style.height = "auto";
    elements.question.style.height =
      `${Math.min(elements.question.scrollHeight, 160)}px`;
  }

  return { setReady };
}
