const state = {
  wikiReady: false,
  selectedFile: null,
  conversationId: null,
  updateChanges: null,
  busy: false,
};

const elements = {
  addedCount: document.querySelector("#addedCount"),
  chatAnswerContent: document.querySelector("#chatAnswerContent"),
  chatAnswerEmpty: document.querySelector("#chatAnswerEmpty"),
  chatAnswerText: document.querySelector("#chatAnswerText"),
  chatButton: document.querySelector("#chatButton"),
  chatConversationLabel: document.querySelector("#chatConversationLabel"),
  chatForm: document.querySelector("#chatForm"),
  chatQuestion: document.querySelector("#chatQuestion"),
  chatSourceList: document.querySelector("#chatSourceList"),
  dropHint: document.querySelector("#dropHint"),
  dropTitle: document.querySelector("#dropTitle"),
  dropZone: document.querySelector("#dropZone"),
  emptyResult: document.querySelector("#emptyResult"),
  messageInput: document.querySelector("#messageInput"),
  modifiedCount: document.querySelector("#modifiedCount"),
  newChatButton: document.querySelector("#newChatButton"),
  rawResponse: document.querySelector("#rawResponse"),
  refreshChangesButton: document.querySelector("#refreshChangesButton"),
  refreshStatusButton: document.querySelector("#refreshStatusButton"),
  resultBadge: document.querySelector("#resultBadge"),
  resultContent: document.querySelector("#resultContent"),
  resultSummary: document.querySelector("#resultSummary"),
  scopeInput: document.querySelector("#scopeInput"),
  selectedFile: document.querySelector("#selectedFile"),
  selectedFileName: document.querySelector("#selectedFileName"),
  selectedFileSize: document.querySelector("#selectedFileSize"),
  sourceFile: document.querySelector("#sourceFile"),
  sourceFileCount: document.querySelector("#sourceFileCount"),
  statusMessage: document.querySelector("#statusMessage"),
  statusOrb: document.querySelector("#statusOrb"),
  statusTitle: document.querySelector("#statusTitle"),
  toastRegion: document.querySelector("#toastRegion"),
  deletedCount: document.querySelector("#deletedCount"),
  uploadButton: document.querySelector("#uploadButton"),
  uploadStepState: document.querySelector("#uploadStepState"),
  updateButton: document.querySelector("#updateButton"),
  updateChangeSummary: document.querySelector("#updateChangeSummary"),
  updateChangeTitle: document.querySelector("#updateChangeTitle"),
  updateForm: document.querySelector("#updateForm"),
  updateMessage: document.querySelector("#updateMessage"),
  updateStepState: document.querySelector("#updateStepState"),
  validationGrid: document.querySelector("#validationGrid"),
  wikiPageCount: document.querySelector("#wikiPageCount"),
};

function formatBytes(value) {
  if (!Number.isFinite(value) || value <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const unitIndex = Math.min(
    Math.floor(Math.log(value) / Math.log(1024)),
    units.length - 1,
  );
  const amount = value / 1024 ** unitIndex;
  return `${amount.toFixed(amount >= 10 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

function setBusy(button, busy, busyText, defaultText) {
  state.busy = busy;
  button.disabled = busy;
  button.classList.toggle("is-loading", busy);
  button.querySelector("span").textContent = busy ? busyText : defaultText;
  button.querySelector(".button-arrow").textContent = busy ? "↻" : "→";
}

function showToast(message, kind = "success") {
  const toast = document.createElement("div");
  toast.className = `toast${kind === "error" ? " is-error" : ""}`;
  toast.textContent = message;
  elements.toastRegion.append(toast);
  window.setTimeout(() => toast.remove(), 4200);
}

function setResult(mode, title, data, summary = "") {
  elements.emptyResult.hidden = true;
  elements.resultContent.hidden = false;
  elements.resultBadge.className = `result-badge is-${mode}`;
  elements.resultBadge.textContent = title;
  elements.resultSummary.innerHTML = "";

  const heading = document.createElement("strong");
  heading.textContent = title;
  elements.resultSummary.append(heading);
  elements.resultSummary.append(document.createTextNode(summary));
  elements.rawResponse.textContent = JSON.stringify(data, null, 2);

  const validation = data?.validation;
  if (validation) {
    elements.validationGrid.hidden = false;
    const metrics = [
      ["校验结果", validation.valid ? "通过" : "未通过"],
      ["检查文件", validation.checked_files ?? 0],
      ["错误", validation.errors ?? 0],
      ["警告", validation.warnings ?? 0],
    ];
    elements.validationGrid.replaceChildren(
      ...metrics.map(([label, value]) => {
        const metric = document.createElement("div");
        metric.className = "metric";
        const caption = document.createElement("span");
        const number = document.createElement("strong");
        caption.textContent = label;
        number.textContent = value;
        metric.append(caption, number);
        return metric;
      }),
    );
  } else {
    elements.validationGrid.hidden = true;
    elements.validationGrid.replaceChildren();
  }
}

function setLoadingResult(title) {
  elements.emptyResult.hidden = true;
  elements.resultContent.hidden = false;
  elements.validationGrid.hidden = true;
  elements.resultBadge.className = "result-badge is-loading";
  elements.resultBadge.textContent = "处理中";
  elements.resultSummary.innerHTML = "";
  const heading = document.createElement("strong");
  heading.textContent = title;
  elements.resultSummary.append(heading);
  elements.resultSummary.append(
    document.createTextNode("请求已经提交，请等待服务返回结果。"),
  );
  elements.rawResponse.textContent = "";
}

function applyWikiStatus(data) {
  state.wikiReady = Boolean(data.initialized);
  elements.statusOrb.className = `status-orb ${state.wikiReady ? "" : "is-empty"}`;
  elements.statusTitle.textContent = state.wikiReady
    ? "Wiki 已初始化"
    : "等待上传资料";
  elements.statusMessage.textContent = data.message;
  elements.sourceFileCount.textContent = String(data.source_file_count || 0);
  elements.wikiPageCount.textContent = String(data.wiki_page_count || 0);
  elements.uploadStepState.textContent = state.wikiReady ? "已完成" : "等待资料";
  elements.uploadStepState.className =
    `step-state ${state.wikiReady ? "is-ready" : "is-locked"}`;

  const uploadLocked = state.wikiReady || state.busy;
  elements.dropZone.classList.toggle("is-disabled", uploadLocked);
  elements.dropZone.setAttribute("aria-disabled", String(uploadLocked));
  elements.sourceFile.disabled = uploadLocked;
  elements.scopeInput.disabled = uploadLocked;
  elements.messageInput.disabled = uploadLocked;
  elements.uploadButton.disabled =
    uploadLocked || !state.selectedFile;

  if (state.wikiReady) {
    state.selectedFile = null;
    elements.sourceFile.value = "";
    elements.selectedFile.hidden = true;
    elements.dropTitle.textContent = "当前 Wiki 已存在";
    elements.dropHint.textContent =
      "上传功能已锁定，请使用下方的增量更新维护现有知识库。";
  } else {
    elements.dropTitle.textContent = "拖入 ZIP，或点击选择文件";
    elements.dropHint.textContent =
      "支持 PDF、Word、Excel、PPT、图片及常见文本格式";
  }

  elements.chatQuestion.disabled = !state.wikiReady;
  elements.chatButton.disabled = !state.wikiReady;
  elements.refreshChangesButton.disabled = !state.wikiReady;
}

function showWikiStatusError(message) {
  state.wikiReady = false;
  elements.statusOrb.className = "status-orb is-error";
  elements.statusTitle.textContent = "检查失败";
  elements.statusMessage.textContent = message;
  elements.sourceFileCount.textContent = "—";
  elements.wikiPageCount.textContent = "—";
  elements.uploadStepState.textContent = "状态未知";
  elements.uploadStepState.className = "step-state is-locked";
  elements.dropZone.classList.add("is-disabled");
  elements.dropZone.setAttribute("aria-disabled", "true");
  elements.sourceFile.disabled = true;
  elements.scopeInput.disabled = true;
  elements.messageInput.disabled = true;
  elements.uploadButton.disabled = true;
  elements.chatQuestion.disabled = true;
  elements.chatButton.disabled = true;
}

async function refreshWikiStatus({ quiet = false } = {}) {
  elements.refreshStatusButton.disabled = true;
  elements.statusOrb.className = "status-orb is-loading";
  elements.statusTitle.textContent = "正在检查";
  elements.statusMessage.textContent = "正在扫描服务器中的 Wiki 文件。";
  try {
    const data = await request("/api/wiki/status");
    applyWikiStatus(data);
    if (data.initialized) {
      await refreshUpdateChanges({ quiet: true });
    } else {
      showUpdateUnavailable("尚未生成 Wiki，请先在上方上传公司资料包。");
    }
    return data;
  } catch (error) {
    showWikiStatusError(error.message);
    showUpdateUnavailable("无法读取当前 Wiki 状态。");
    if (!quiet) showToast(error.message, "error");
    return null;
  } finally {
    elements.refreshStatusButton.disabled = false;
  }
}

async function request(url, options = {}) {
  const response = await fetch(url, options);
  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json")
    ? await response.json()
    : { detail: await response.text() };
  if (!response.ok) {
    const detail =
      typeof data.detail === "string"
        ? data.detail
        : data.detail?.message || `请求失败（HTTP ${response.status}）`;
    const error = new Error(detail);
    error.status = response.status;
    error.data = data;
    throw error;
  }
  return data;
}

function applyUpdateChanges(data) {
  const changes = data.changes || {};
  const actionRequired = Boolean(changes.has_changes);
  state.updateChanges = {
    ...changes,
    action_required: actionRequired,
  };
  const added = changes.added?.length || 0;
  const modified = changes.modified?.length || 0;
  const deleted = changes.deleted?.length || 0;
  const total = added + modified + deleted;
  elements.addedCount.textContent = String(added);
  elements.modifiedCount.textContent = String(modified);
  elements.deletedCount.textContent = String(deleted);
  elements.updateStepState.textContent = total ? "发现变化" : "没有变化";
  elements.updateStepState.className =
    `step-state ${actionRequired ? "is-ready" : "is-locked"}`;
  elements.updateChangeTitle.textContent = total
    ? `发现 ${total} 个资料变化`
    : "Wiki 已与资料同步";
  elements.updateChangeSummary.textContent = !changes.baseline_exists
    ? `这是旧项目首次建立 update 基线，将检查当前 ${added} 个资料文件与现有 Wiki 的一致性。`
    : total
      ? `新增 ${added}、修改 ${modified}、删除 ${deleted}。执行时只维护受影响页面。`
      : "资料内容与上次成功运行时一致，不需要调用模型。";
  elements.updateButton.disabled = !actionRequired;
  elements.chatQuestion.disabled = !state.wikiReady;
  elements.chatButton.disabled = !state.wikiReady;
}

function showUpdateUnavailable(message) {
  state.updateChanges = null;
  elements.addedCount.textContent = "—";
  elements.modifiedCount.textContent = "—";
  elements.deletedCount.textContent = "—";
  elements.updateStepState.textContent = "暂不可用";
  elements.updateStepState.className = "step-state is-locked";
  elements.updateChangeTitle.textContent = "需要先完成 Wiki 初始化";
  elements.updateChangeSummary.textContent = message;
  elements.updateButton.disabled = true;
  elements.chatQuestion.disabled = !state.wikiReady;
  elements.chatButton.disabled = !state.wikiReady;
}

async function refreshUpdateChanges({ quiet = false } = {}) {
  if (state.busy) return null;
  elements.refreshChangesButton.disabled = true;
  try {
    const data = await request("/api/wiki/update/changes");
    applyUpdateChanges(data);
    return data;
  } catch (error) {
    showUpdateUnavailable(error.message);
    if (!quiet && error.status !== 409) showToast(error.message, "error");
    return null;
  } finally {
    elements.refreshChangesButton.disabled = false;
  }
}

async function updateWiki(event) {
  event.preventDefault();
  if (
    !state.updateChanges?.action_required ||
    state.busy
  ) return;
  const message = elements.updateMessage.value.trim();
  const payload = {};
  if (message) payload.message = message;

  setBusy(elements.updateButton, true, "正在增量更新", "更新受影响页面");
  elements.updateMessage.disabled = true;
  elements.refreshChangesButton.disabled = true;
  setLoadingResult("Deep Agent 正在分析资料变化并维护受影响页面");
  try {
    const data = await request("/api/wiki/update", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const pageSummary = `更新 ${data.updated_pages?.length || 0} 个页面，删除 ${data.deleted_pages?.length || 0} 个失效页面。`;
    setResult(
      "success",
      data.status === "no_changes" ? "没有资料变化" : "Wiki 增量更新完成",
      data,
      `${data.summary}\n${pageSummary}`,
    );
    showToast(
      data.status === "no_changes"
        ? "资料没有变化，无需更新。"
        : "受影响的 Wiki 页面已经更新。",
    );
  } catch (error) {
    setResult(
      "error",
      `更新失败 · HTTP ${error.status || "—"}`,
      error.data || {},
      error.message,
    );
    showToast(error.message, "error");
  } finally {
    setBusy(elements.updateButton, false, "正在增量更新", "更新受影响页面");
    elements.updateMessage.disabled = false;
    await refreshUpdateChanges({ quiet: true });
  }
}

function selectFile(file) {
  if (
    !file ||
    elements.sourceFile.disabled ||
    state.wikiReady ||
    state.busy
  ) return;
  if (!file.name.toLowerCase().endsWith(".zip")) {
    showToast("请选择 .zip 格式的公司资料包。", "error");
    return;
  }
  state.selectedFile = file;
  elements.selectedFile.hidden = false;
  elements.selectedFileName.textContent = file.name;
  elements.selectedFileSize.textContent = formatBytes(file.size);
  elements.uploadButton.disabled = state.busy;
}

async function uploadSource() {
  if (
    !state.selectedFile ||
    state.wikiReady ||
    state.busy
  ) return;
  const form = new FormData();
  form.append("file", state.selectedFile);
  form.append("scope", elements.scopeInput.value.trim() || "全部公司资料");
  if (elements.messageInput.value.trim()) form.append("message", elements.messageInput.value.trim());
  setBusy(elements.uploadButton, true, "正在生成 Wiki", "上传并生成 Wiki");
  setLoadingResult("正在解压资料、调用 MinerU，并生成 Wiki，请耐心等待。");
  try {
    const completed = await request("/api/wiki/sources/upload", {
      method: "POST",
      body: form,
    });
    setResult(
      "success",
      completed.validation?.valid ? "Wiki 已生成" : "Wiki 已生成，校验未通过",
      completed,
      `${completed.summary || "生成任务已结束"}\n${completed.validation?.valid ? "最终机械校验已经通过。" : "请查看校验问题。"}`,
    );
    state.selectedFile = null;
    elements.sourceFile.value = "";
    elements.selectedFile.hidden = true;
    showToast("Wiki 已生成，可以开始问答。", completed.validation?.valid ? "success" : "error");
    await refreshWikiStatus({ quiet: true });
  } catch (error) {
    setResult("error", `上传失败 · HTTP ${error.status || "—"}`, error.data || {}, error.message);
    showToast(error.message, "error");
  } finally {
    setBusy(elements.uploadButton, false, "正在生成 Wiki", "上传并生成 Wiki");
    elements.uploadButton.disabled =
      state.busy || state.wikiReady || !state.selectedFile;
  }
}

async function askChat(event) {
  event.preventDefault();
  if (
    !state.wikiReady ||
    state.busy ||
    !elements.chatForm.reportValidity()
  ) {
    return;
  }
  const question = elements.chatQuestion.value.trim();
  if (!question) return;
  const payload = { question };
  if (state.conversationId) {
    payload.conversation_id = state.conversationId;
  }

  setBusy(elements.chatButton, true, "正在检索资料", "提交问题");
  elements.chatQuestion.disabled = true;
  elements.chatAnswerEmpty.hidden = true;
  elements.chatAnswerContent.hidden = false;
  elements.chatAnswerText.textContent = "正在检索公司资料并组织回答…";
  elements.chatSourceList.replaceChildren();
  try {
    const data = await request("/api/wiki/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    state.conversationId = data.conversation_id;
    elements.chatConversationLabel.textContent =
      `会话：${state.conversationId}`;
    elements.newChatButton.disabled = false;
    renderChatAnswer(data);
  } catch (error) {
    elements.chatAnswerText.textContent = error.message;
    elements.chatSourceList.replaceChildren();
    showToast(error.message, "error");
  } finally {
    setBusy(elements.chatButton, false, "正在检索资料", "提交问题");
    elements.chatQuestion.disabled = !state.wikiReady;
    elements.chatButton.disabled = !state.wikiReady;
  }
}

function renderChatAnswer(data) {
  elements.chatAnswerEmpty.hidden = true;
  elements.chatAnswerContent.hidden = false;
  elements.chatAnswerText.textContent = data.answer;
  elements.chatSourceList.replaceChildren();
  if (!Array.isArray(data.sources) || data.sources.length === 0) return;

  const heading = document.createElement("strong");
  heading.textContent = "本次回答来源";
  elements.chatSourceList.append(heading);
  for (const source of data.sources) {
    const path = document.createElement("code");
    path.textContent = source;
    elements.chatSourceList.append(path);
  }
}

async function resetChat() {
  if (!state.conversationId || state.busy) return;
  const conversationId = state.conversationId;
  elements.newChatButton.disabled = true;
  try {
    await request(`/api/wiki/chat/${encodeURIComponent(conversationId)}`, {
      method: "DELETE",
    });
    state.conversationId = null;
    elements.chatConversationLabel.textContent = "尚未开始会话";
    elements.chatQuestion.value = "";
    elements.chatAnswerContent.hidden = true;
    elements.chatAnswerEmpty.hidden = false;
    elements.chatAnswerText.textContent = "";
    elements.chatSourceList.replaceChildren();
    showToast("已开始新的问答会话。");
  } catch (error) {
    elements.newChatButton.disabled = false;
    showToast(error.message, "error");
  }
}

elements.dropZone.addEventListener("click", () => {
  if (!state.busy && !state.wikiReady) elements.sourceFile.click();
});

elements.dropZone.addEventListener("keydown", (event) => {
  if (
    !state.busy &&
    !state.wikiReady &&
    (event.key === "Enter" || event.key === " ")
  ) {
    event.preventDefault();
    elements.sourceFile.click();
  }
});

elements.sourceFile.addEventListener("change", (event) => {
  selectFile(event.target.files?.[0]);
});

for (const eventName of ["dragenter", "dragover"]) {
  elements.dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    if (!state.busy && !state.wikiReady) {
      elements.dropZone.classList.add("is-dragging");
    }
  });
}

for (const eventName of ["dragleave", "drop"]) {
  elements.dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    elements.dropZone.classList.remove("is-dragging");
  });
}

elements.dropZone.addEventListener("drop", (event) => {
  if (!state.busy && !state.wikiReady) {
    selectFile(event.dataTransfer?.files?.[0]);
  }
});

elements.uploadButton.addEventListener("click", uploadSource);
elements.refreshStatusButton.addEventListener("click", () =>
  refreshWikiStatus(),
);
elements.refreshChangesButton.addEventListener("click", () =>
  refreshUpdateChanges(),
);
elements.updateForm.addEventListener("submit", updateWiki);
elements.chatForm.addEventListener("submit", askChat);
elements.newChatButton.addEventListener("click", resetChat);

refreshWikiStatus({ quiet: true });
