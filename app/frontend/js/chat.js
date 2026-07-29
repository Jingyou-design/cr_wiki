import { streamChat } from "./api.js?v=20260728-sse";
import { currentUser } from "./auth.js";
import { renderMarkdown } from "./markdown.js";
import { setBusy, showToast } from "./ui.js";

export function createChatController(configRevision) {
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
  };

  elements.form.addEventListener("submit", ask);
  elements.question.addEventListener("input", resizeInput);
  elements.question.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      elements.form.requestSubmit();
    }
  });
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
    appendTurn("user", question);
    const answerElement = appendTurn(
      "assistant",
      "正在检索公司资料并组织回答…",
    );
    let answer = "";

    try {
      await streamChat(payload, (eventData) => {
        if (eventData.type === "start") {
          state.conversationId = eventData.conversation_id;
        } else if (eventData.type === "delta") {
          answer += eventData.content;
          renderMarkdown(answerElement, answer);
          elements.answer.scrollTop = elements.answer.scrollHeight;
        } else if (eventData.type === "done") {
          renderSources(eventData.sources);
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
      answerElement.textContent = error.message;
      elements.sources.replaceChildren();
      showToast(error.message, "error");
    } finally {
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
      const path = document.createElement("code");
      path.textContent = source;
      elements.sources.append(path);
    }
  }

  function resizeInput() {
    elements.question.style.height = "auto";
    elements.question.style.height =
      `${Math.min(elements.question.scrollHeight, 160)}px`;
  }

  return { setReady };
}
