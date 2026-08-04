import { apiRequest } from "./api.js";
import { requirePageUser } from "./auth.js?v=20260730-manager2";
import { createChatController } from "./chat.js?v=20260803-chat1";
import {
  createManagerFilesController,
} from "./manager-files.js?v=20260804-files1";
import { formatBytes, setBusy, showToast } from "./ui.js";

const user = await requirePageUser(["admin", "manager"]);
if (user) {
  initializeAdminPage();
}

function initializeAdminPage() {
  const isAdmin = user.role === "admin";
  const state = {
    wikiReady: false,
    selectedFile: null,
    updateChanges: null,
    busy: false,
  };
  const elements = {
    addedCount: byId("addedCount"),
    adminUploadSection: byId("adminUploadSection"),
    brandLink: byId("managementHomeLink"),
    brandSubtitle: byId("brandSubtitle"),
    deletedCount: byId("deletedCount"),
    dropHint: byId("dropHint"),
    dropTitle: byId("dropTitle"),
    dropZone: byId("dropZone"),
    emptyResult: byId("emptyResult"),
    modifiedCount: byId("modifiedCount"),
    rawResponse: byId("rawResponse"),
    refreshChangesButton: byId("refreshChangesButton"),
    refreshStatusButton: byId("refreshStatusButton"),
    resultBadge: byId("resultBadge"),
    resultContent: byId("resultContent"),
    resultSummary: byId("resultSummary"),
    selectedFile: byId("selectedFile"),
    selectedFileName: byId("selectedFileName"),
    selectedFileSize: byId("selectedFileSize"),
    sourceFile: byId("sourceFile"),
    sourceFileCount: byId("sourceFileCount"),
    statusMessage: byId("statusMessage"),
    statusOrb: byId("statusOrb"),
    statusTitle: byId("statusTitle"),
    updateButton: byId("updateButton"),
    updateChangeSummary: byId("updateChangeSummary"),
    updateChangeTitle: byId("updateChangeTitle"),
    updateForm: byId("updateForm"),
    updateMessage: byId("updateMessage"),
    updateStepState: byId("updateStepState"),
    uploadButton: byId("uploadButton"),
    uploadStepState: byId("uploadStepState"),
    validationGrid: byId("validationGrid"),
    wikiPageCount: byId("wikiPageCount"),
    accessNotice: byId("accessNotice"),
  };
  configurePageForRole();
  const chat = createChatController({
    userId: user.id,
  });
  createManagerFilesController({
    onFilesChanged: () => refreshChanges({ quiet: true }),
  });

  elements.refreshStatusButton.addEventListener("click", refreshStatus);
  elements.refreshChangesButton.addEventListener("click", refreshChanges);
  elements.updateForm.addEventListener("submit", updateWiki);
  if (isAdmin) {
    elements.uploadButton.addEventListener("click", uploadSource);
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
  }

  refreshStatus({ quiet: true });

  function configurePageForRole() {
    if (isAdmin) return;
    document.title = "DeepBook · 部门管理控制台";
    document.body.classList.add("is-manager");
    elements.adminUploadSection.hidden = true;
    elements.brandLink.href = "/manager";
    elements.brandLink.setAttribute("aria-label", "返回部门管理控制台");
    elements.brandSubtitle.textContent = "部门管理控制台";
    elements.accessNotice.textContent =
      "部门经理可执行增量检查和更新；问答与资料浏览仅限所属部门。初始化上传仅限管理员。";
  }

  async function refreshStatus({ quiet = false } = {}) {
    elements.refreshStatusButton.disabled = true;
    elements.statusOrb.className = "status-orb is-loading";
    elements.statusTitle.textContent = "正在检查";
    elements.statusMessage.textContent = "正在扫描服务器中的 DeepBook 文件。";
    try {
      const data = await apiRequest("/api/wiki/status", { method: "POST" });
      applyStatus(data);
      if (data.initialized) {
        await refreshChanges({ quiet: true });
      } else {
        showUpdateUnavailable(
          isAdmin
            ? "尚未生成 DeepBook，请先上传公司资料包。"
            : "尚未生成 DeepBook，请联系管理员完成初始化。",
        );
      }
      return data;
    } catch (error) {
      showStatusError(error.message);
      showUpdateUnavailable("无法读取当前 DeepBook 状态。");
      if (!quiet) showToast(error.message, "error");
      return null;
    } finally {
      elements.refreshStatusButton.disabled = false;
    }
  }

  function applyStatus(data) {
    state.wikiReady = Boolean(data.initialized);
    chat.setReady(state.wikiReady);
    elements.statusOrb.className =
      `status-orb ${state.wikiReady ? "" : "is-empty"}`;
    elements.statusTitle.textContent =
      state.wikiReady ? "DeepBook 已初始化" : "等待上传资料";
    elements.statusMessage.textContent = data.message;
    elements.sourceFileCount.textContent =
      String(data.source_file_count || 0);
    elements.wikiPageCount.textContent =
      String(data.wiki_page_count || 0);
    if (isAdmin) {
      elements.uploadStepState.textContent =
        state.wikiReady ? "已完成" : "等待资料";
      elements.uploadStepState.className =
        `step-state ${state.wikiReady ? "is-ready" : "is-locked"}`;

      const uploadLocked = state.wikiReady || state.busy;
      elements.dropZone.classList.toggle("is-disabled", uploadLocked);
      elements.dropZone.setAttribute("aria-disabled", String(uploadLocked));
      elements.sourceFile.disabled = uploadLocked;
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
    }
  }

  function showStatusError(message) {
    state.wikiReady = false;
    chat.setReady(false);
    elements.statusOrb.className = "status-orb is-error";
    elements.statusTitle.textContent = "检查失败";
    elements.statusMessage.textContent = message;
    elements.sourceFileCount.textContent = "—";
    elements.wikiPageCount.textContent = "—";
    if (isAdmin) {
      elements.uploadStepState.textContent = "状态未知";
      elements.uploadStepState.className = "step-state is-locked";
      elements.dropZone.classList.add("is-disabled");
      elements.dropZone.setAttribute("aria-disabled", "true");
      elements.sourceFile.disabled = true;
      elements.uploadButton.disabled = true;
    }
  }

  async function refreshChanges({ quiet = false } = {}) {
    if (state.busy) return null;
    elements.refreshChangesButton.disabled = true;
    try {
      const data = await apiRequest(
        "/api/wiki/update/changes",
        { method: "POST" },
      );
      applyChanges(data);
      return data;
    } catch (error) {
      showUpdateUnavailable(error.message);
      if (!quiet && error.status !== 409) {
        showToast(error.message, "error");
      }
      return null;
    } finally {
      elements.refreshChangesButton.disabled = false;
    }
  }

  function applyChanges(data) {
    const changes = data.changes || {};
    const actionRequired = Boolean(changes.has_changes);
    state.updateChanges = { ...changes, action_required: actionRequired };
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
    elements.updateChangeTitle.textContent =
      total ? `发现 ${total} 个资料变化` : "Wiki 已与资料同步";
    elements.updateChangeSummary.textContent = !changes.baseline_exists
      ? `这是旧项目首次建立 update 基线，将检查当前 ${added} 个资料文件与现有 Wiki 的一致性。`
      : total
        ? `新增 ${added}、修改 ${modified}、删除 ${deleted}。执行时只维护受影响页面。`
        : "资料内容与上次成功运行时一致，不需要调用模型。";
    elements.updateButton.disabled = !actionRequired;
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
  }

  async function updateWiki(event) {
    event.preventDefault();
    if (!state.updateChanges?.action_required || state.busy) return;
    const payload = {};
    const message = elements.updateMessage.value.trim();
    if (message) payload.message = message;

    state.busy = true;
    setBusy(elements.updateButton, true, "正在增量更新", "更新受影响页面");
    elements.updateMessage.disabled = true;
    elements.refreshChangesButton.disabled = true;
    setLoadingResult("Deep Agent 正在分析资料变化并维护受影响页面");
    try {
      const data = await apiRequest("/api/wiki/update", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const pageSummary =
        `更新 ${data.updated_pages?.length || 0} 个页面，` +
        `删除 ${data.deleted_pages?.length || 0} 个失效页面。`;
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
      state.busy = false;
      setBusy(
        elements.updateButton,
        false,
        "正在增量更新",
        "更新受影响页面",
      );
      elements.updateMessage.disabled = false;
      await refreshChanges({ quiet: true });
    }
  }

  function selectFile(file) {
    if (!file || state.wikiReady || state.busy) return;
    if (!file.name.toLowerCase().endsWith(".zip")) {
      showToast("请选择 .zip 格式的公司资料包。", "error");
      return;
    }
    state.selectedFile = file;
    elements.selectedFile.hidden = false;
    elements.selectedFileName.textContent = file.name;
    elements.selectedFileSize.textContent = formatBytes(file.size);
    elements.uploadButton.disabled = false;
  }

  async function uploadSource() {
    if (!isAdmin || !state.selectedFile || state.wikiReady || state.busy) return;
    const form = new FormData();
    form.append("file", state.selectedFile);

    state.busy = true;
    setBusy(elements.uploadButton, true, "正在生成 Wiki", "上传并生成 Wiki");
    setLoadingResult("正在解压资料、调用 MinerU，并生成 Wiki，请耐心等待。");
    try {
      const data = await apiRequest("/api/wiki/sources/upload", {
        method: "POST",
        body: form,
      });
      setResult(
        "success",
        data.validation?.valid ? "Wiki 已生成" : "Wiki 已生成，发现诊断问题",
        data,
        `${data.summary || "生成任务已结束"}\n` +
          `${
            data.validation?.valid
              ? "自动诊断未发现问题。"
              : "生成结果已保留，请查看非阻断诊断并按需修正。"
          }`,
      );
      state.selectedFile = null;
      elements.sourceFile.value = "";
      elements.selectedFile.hidden = true;
      showToast(
        data.validation?.valid
          ? "Wiki 已生成，可以开始问答。"
          : "Wiki 已生成，同时记录了待检查项。",
        data.validation?.valid ? "success" : "warning",
      );
      await refreshStatus({ quiet: true });
    } catch (error) {
      setResult(
        "error",
        `上传失败 · HTTP ${error.status || "—"}`,
        error.data || {},
        error.message,
      );
      showToast(error.message, "error");
    } finally {
      state.busy = false;
      setBusy(elements.uploadButton, false, "正在生成 Wiki", "上传并生成 Wiki");
      elements.uploadButton.disabled =
        state.wikiReady || !state.selectedFile;
    }
  }

  function setLoadingResult(title) {
    elements.emptyResult.hidden = true;
    elements.resultContent.hidden = false;
    elements.validationGrid.hidden = true;
    elements.resultBadge.className = "result-badge is-loading";
    elements.resultBadge.textContent = "处理中";
    elements.resultSummary.replaceChildren();
    const heading = document.createElement("strong");
    heading.textContent = title;
    elements.resultSummary.append(
      heading,
      document.createTextNode("请求已经提交，请等待服务返回结果。"),
    );
    elements.rawResponse.textContent = "";
  }

  function setResult(mode, title, data, summary = "") {
    elements.emptyResult.hidden = true;
    elements.resultContent.hidden = false;
    elements.resultBadge.className = `result-badge is-${mode}`;
    elements.resultBadge.textContent = title;
    elements.resultSummary.replaceChildren();
    const heading = document.createElement("strong");
    heading.textContent = title;
    elements.resultSummary.append(
      heading,
      document.createTextNode(summary),
    );
    elements.rawResponse.textContent = JSON.stringify(data, null, 2);
    renderValidation(data?.validation);
  }

  function renderValidation(validation) {
    if (!validation) {
      elements.validationGrid.hidden = true;
      elements.validationGrid.replaceChildren();
      return;
    }
    elements.validationGrid.hidden = false;
    const metrics = [
      ["诊断结果", validation.valid ? "未发现问题" : "发现问题"],
      ["检查文件", validation.checked_files ?? 0],
      ["错误", validation.errors ?? 0],
      ["警告", validation.warnings ?? 0],
    ];
    elements.validationGrid.replaceChildren(
      ...metrics.map(([label, value]) => {
        const metric = document.createElement("div");
        metric.className = "metric";
        const caption = document.createElement("span");
        caption.textContent = label;
        const number = document.createElement("strong");
        number.textContent = value;
        metric.append(caption, number);
        return metric;
      }),
    );
  }
}

function byId(id) {
  return document.querySelector(`#${id}`);
}
