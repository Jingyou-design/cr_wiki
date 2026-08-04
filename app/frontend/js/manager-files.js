import { apiRequest } from "./api.js";
import { formatBytes, setBusy, showToast } from "./ui.js";

export function createManagerFilesController({ onFilesChanged } = {}) {
  const elements = {
    actionBase: byId("managerFileActionBase"),
    actionForm: byId("managerFileActionForm"),
    actionInput: byId("managerFileActionInput"),
    actionTitle: byId("managerFileActionTitle"),
    cancelAction: byId("cancelManagerFileAction"),
    closeButton: byId("closeManagerFilesButton"),
    content: byId("managerFileContent"),
    createDirectoryButton: byId("createManagerDirectoryButton"),
    createFileButton: byId("createManagerFileButton"),
    dialog: byId("managerFilesDialog"),
    editStatus: byId("managerFileEditStatus"),
    editor: byId("managerFileEditor"),
    editorEmpty: byId("managerFileEditorEmpty"),
    fileCount: byId("managerFileCount"),
    fileName: byId("managerFileName"),
    filePath: byId("managerFilePath"),
    fileSize: byId("managerFileSize"),
    moveButton: byId("moveManagerPathButton"),
    openButton: byId("openManagerFilesButton"),
    refreshButton: byId("refreshManagerFilesButton"),
    saveButton: byId("saveManagerFileButton"),
    summary: byId("managerFilesSummary"),
    toolbarStatus: byId("managerFilesToolbarStatus"),
    tree: byId("managerFileTree"),
  };
  const state = {
    action: null,
    busy: false,
    dirty: false,
    expanded: new Set(),
    originalContent: "",
    roots: [],
    selected: null,
  };

  elements.openButton.addEventListener("click", open);
  elements.closeButton.addEventListener("click", close);
  elements.refreshButton.addEventListener("click", refresh);
  elements.createFileButton.addEventListener(
    "click",
    () => beginAction("file"),
  );
  elements.createDirectoryButton.addEventListener(
    "click",
    () => beginAction("directory"),
  );
  elements.moveButton.addEventListener("click", () => beginAction("move"));
  elements.cancelAction.addEventListener("click", closeAction);
  elements.actionForm.addEventListener("submit", submitAction);
  elements.saveButton.addEventListener("click", save);
  elements.content.addEventListener("input", updateDirtyState);
  elements.content.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
      event.preventDefault();
      if (state.dirty && !state.busy) save();
    }
  });
  elements.dialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    close();
  });
  elements.dialog.addEventListener("click", (event) => {
    if (event.target === elements.dialog) close();
  });
  window.addEventListener("beforeunload", (event) => {
    if (!state.dirty) return;
    event.preventDefault();
    event.returnValue = "";
  });

  async function open() {
    elements.dialog.showModal();
    if (!state.roots.length) await loadTree();
  }

  function close() {
    if (!confirmDiscard()) return;
    closeAction();
    state.selected = null;
    clearEditor();
    renderTree();
    elements.dialog.close();
  }

  async function refresh() {
    if (!confirmDiscard()) return;
    const selectedPath = state.selected?.path;
    const selectedType = state.selected?.type;
    state.dirty = false;
    await loadTree(selectedPath);
    if (selectedType === "file" && state.selected) {
      await loadFile(state.selected);
    } else {
      clearEditor();
    }
  }

  async function loadTree(selectedPath = state.selected?.path) {
    setBusyState(true, "正在读取目录");
    try {
      const data = await apiRequest("/api/manager/files/tree");
      state.roots = Array.isArray(data.roots) ? data.roots : [];
      for (const root of state.roots) state.expanded.add(root.path);
      state.selected = selectedPath
        ? findNode(state.roots, selectedPath)
        : null;
      if (selectedPath && !state.selected) clearEditor();
      renderTree();
      updateSummary();
      elements.toolbarStatus.textContent =
        state.roots.length ? "目录已更新" : "当前没有可管理的资料目录";
    } catch (error) {
      state.roots = [];
      state.selected = null;
      renderTree(error.message);
      updateSummary();
      elements.toolbarStatus.textContent = "目录读取失败";
      showToast(error.message, "error");
    } finally {
      setBusyState(false);
    }
  }

  function renderTree(errorMessage = "") {
    elements.tree.replaceChildren();
    if (!state.roots.length) {
      const empty = document.createElement("p");
      empty.className = "manager-file-empty";
      empty.textContent = errorMessage || "当前没有可管理的资料目录。";
      elements.tree.append(empty);
      updateControls();
      return;
    }

    const list = document.createElement("ul");
    list.className = "manager-file-tree-list";
    for (const root of state.roots) list.append(renderNode(root, 0));
    elements.tree.append(list);
    updateControls();
  }

  function renderNode(node, depth) {
    const item = document.createElement("li");
    const row = document.createElement("div");
    row.className = "manager-file-tree-row";
    row.style.setProperty("--tree-depth", depth);
    if (state.selected?.path === node.path) row.classList.add("is-selected");

    const isDirectory = node.type === "directory";
    const expanded = isDirectory && state.expanded.has(node.path);
    const toggle = document.createElement("button");
    toggle.className = "manager-file-tree-toggle";
    toggle.type = "button";
    toggle.disabled = !isDirectory || !node.children?.length;
    toggle.textContent = isDirectory
      ? node.children?.length
        ? expanded ? "−" : "+"
        : "·"
      : "·";
    toggle.setAttribute(
      "aria-label",
      expanded ? `折叠 ${node.name}` : `展开 ${node.name}`,
    );
    toggle.addEventListener("click", () => {
      if (expanded) state.expanded.delete(node.path);
      else state.expanded.add(node.path);
      renderTree();
    });

    const select = document.createElement("button");
    select.className = "manager-file-tree-select";
    select.type = "button";
    select.title = node.path;
    const icon = document.createElement("span");
    icon.className = "manager-file-tree-icon";
    icon.textContent = isDirectory ? "▱" : "MD";
    const name = document.createElement("span");
    name.textContent = node.name;
    select.append(icon, name);
    select.addEventListener("click", () => selectNode(node));
    row.append(toggle, select);
    item.append(row);

    if (isDirectory && expanded && node.children?.length) {
      const children = document.createElement("ul");
      children.className = "manager-file-tree-list";
      for (const child of node.children) {
        children.append(renderNode(child, depth + 1));
      }
      item.append(children);
    }
    return item;
  }

  async function selectNode(node) {
    if (state.selected?.path === node.path) return;
    if (!confirmDiscard()) return;
    closeAction();
    state.selected = node;
    renderTree();
    if (node.type === "directory") {
      clearEditor();
      elements.toolbarStatus.textContent = node.path;
      return;
    }
    await loadFile(node);
  }

  async function loadFile(node) {
    setBusyState(true, "正在读取文件");
    try {
      const data = await apiRequest(
        `/api/manager/files/content?path=${encodeURIComponent(node.path)}`,
      );
      state.originalContent = data.content;
      state.dirty = false;
      elements.editorEmpty.hidden = true;
      elements.editor.hidden = false;
      elements.fileName.textContent = node.name;
      elements.filePath.textContent = data.path;
      elements.fileSize.textContent = formatBytes(data.size);
      elements.content.value = data.content;
      elements.editStatus.textContent = "没有未保存修改";
      elements.toolbarStatus.textContent = data.path;
    } catch (error) {
      clearEditor();
      showToast(error.message, "error");
    } finally {
      setBusyState(false);
    }
  }

  function beginAction(action) {
    if (state.busy || !state.roots.length) return;
    if (action === "move" && !state.selected) return;
    if (action === "move" && !confirmDiscard()) return;

    state.action = action;
    const base = activeDirectory();
    if (action === "file") {
      elements.actionTitle.textContent = "新建 Markdown 文件";
      elements.actionBase.textContent = `创建位置：${base}`;
      elements.actionInput.value = "";
      elements.actionInput.placeholder = "例如：项目管理办法.md";
    } else if (action === "directory") {
      elements.actionTitle.textContent = "新建目录";
      elements.actionBase.textContent = `创建位置：${base}`;
      elements.actionInput.value = "";
      elements.actionInput.placeholder = "例如：2026年制度";
    } else {
      elements.actionTitle.textContent = "重命名或移动";
      elements.actionBase.textContent = `原路径：${state.selected.path}`;
      elements.actionInput.value = state.selected.path;
      elements.actionInput.placeholder = "输入新的完整路径";
    }
    elements.actionForm.hidden = false;
    elements.actionInput.focus();
    elements.actionInput.select();
  }

  function closeAction() {
    state.action = null;
    elements.actionForm.hidden = true;
    elements.actionInput.value = "";
  }

  async function submitAction(event) {
    event.preventDefault();
    if (!state.action || state.busy) return;
    const value = elements.actionInput.value.trim();
    if (!value) return;

    const action = state.action;
    const sourcePath = state.selected?.path;
    const targetPath = action === "move"
      ? value
      : joinPath(activeDirectory(), value);
    if (action === "move" && targetPath === sourcePath) {
      closeAction();
      return;
    }

    const submitButton = elements.actionForm.querySelector(
      "button[type='submit']",
    );
    state.busy = true;
    setBusy(submitButton, true, "处理中", "确认");
    updateControls();
    try {
      if (action === "file") {
        await apiRequest("/api/manager/files/content", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ path: targetPath, content: "" }),
        });
      } else if (action === "directory") {
        await apiRequest("/api/manager/files/directory", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ path: targetPath }),
        });
      } else {
        await apiRequest("/api/manager/files/path", {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            source_path: sourcePath,
            target_path: targetPath,
          }),
        });
      }

      closeAction();
      clearEditor();
      await loadTree(targetPath);
      const targetNode = findNode(state.roots, targetPath);
      if (targetNode?.type === "file") await loadFile(targetNode);
      showToast(actionMessage(action));
      if (action !== "directory") notifyFilesChanged();
    } catch (error) {
      showToast(error.message, "error");
    } finally {
      state.busy = false;
      setBusy(submitButton, false, "处理中", "确认");
      updateControls();
    }
  }

  async function save() {
    if (!state.selected || !state.dirty || state.busy) return;
    state.busy = true;
    setBusy(elements.saveButton, true, "正在保存", "保存文件");
    updateControls();
    try {
      const data = await apiRequest("/api/manager/files/content", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          path: state.selected.path,
          content: elements.content.value,
        }),
      });
      state.originalContent = elements.content.value;
      state.dirty = false;
      elements.fileSize.textContent = formatBytes(data.size);
      elements.editStatus.textContent = "已保存";
      await loadTree(state.selected.path);
      showToast("文件已保存。");
      notifyFilesChanged();
    } catch (error) {
      showToast(error.message, "error");
    } finally {
      state.busy = false;
      setBusy(elements.saveButton, false, "正在保存", "保存文件");
      updateControls();
    }
  }

  function updateDirtyState() {
    state.dirty = elements.content.value !== state.originalContent;
    elements.editStatus.textContent =
      state.dirty ? "有未保存修改" : "没有未保存修改";
    updateControls();
  }

  function clearEditor() {
    state.originalContent = "";
    state.dirty = false;
    elements.editor.hidden = true;
    elements.editorEmpty.hidden = false;
    elements.content.value = "";
    updateControls();
  }

  function setBusyState(busy, status = "") {
    state.busy = busy;
    if (status) elements.toolbarStatus.textContent = status;
    updateControls();
  }

  function updateControls() {
    const hasRoots = state.roots.length > 0;
    elements.refreshButton.disabled = state.busy;
    elements.createFileButton.disabled = state.busy || !hasRoots;
    elements.createDirectoryButton.disabled = state.busy || !hasRoots;
    elements.moveButton.disabled = state.busy || !state.selected;
    elements.content.disabled = state.busy;
    elements.saveButton.disabled =
      state.busy || !state.selected || !state.dirty;
  }

  function updateSummary() {
    const count = countFiles(state.roots);
    elements.fileCount.textContent = `${count} 个文件`;
    elements.summary.textContent = state.roots.length
      ? `${state.roots.length} 个资料目录 · ${count} 个文件`
      : "当前没有可管理的资料目录";
  }

  function confirmDiscard() {
    if (!state.dirty) return true;
    return window.confirm("当前文件有未保存修改，确定放弃吗？");
  }

  function activeDirectory() {
    if (state.selected?.type === "directory") return state.selected.path;
    if (state.selected?.path) {
      return state.selected.path.split("/").slice(0, -1).join("/");
    }
    return state.roots[0]?.path || "";
  }

  function notifyFilesChanged() {
    if (typeof onFilesChanged !== "function") return;
    Promise.resolve(onFilesChanged()).catch(() => {});
  }

  return { open };
}

function findNode(nodes, path) {
  for (const node of nodes) {
    if (node.path === path) return node;
    const found = findNode(node.children || [], path);
    if (found) return found;
  }
  return null;
}

function countFiles(nodes) {
  return nodes.reduce(
    (total, node) => total
      + (node.type === "file" ? 1 : countFiles(node.children || [])),
    0,
  );
}

function joinPath(parent, name) {
  return `${parent.replace(/\/+$/, "")}/${name.replace(/^\/+/, "")}`;
}

function actionMessage(action) {
  if (action === "file") return "文件已创建。";
  if (action === "directory") return "目录已创建。";
  return "路径已更新。";
}

function byId(id) {
  return document.querySelector(`#${id}`);
}
