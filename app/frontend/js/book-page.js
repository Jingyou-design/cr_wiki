import { apiRequest } from "./api.js";
import {
  requirePageUser,
  routeForUser,
} from "./auth.js?v=20260730-manager2";
import { renderMarkdown } from "./markdown.js?v=20260729-book1";
import { showToast } from "./ui.js";

const user = await requirePageUser(["admin", "manager", "employee"]);

if (user) {
  const homeRoute = routeForUser(user);
  for (const link of document.querySelectorAll("[data-role-home]")) {
    link.href = homeRoute;
  }
  initializeBook();
}

async function initializeBook() {
  const elements = {
    breadcrumbs: document.querySelector("#bookBreadcrumbs"),
    document: document.querySelector("#wikiDocument"),
    empty: document.querySelector("#bookTreeEmpty"),
    loading: document.querySelector("#bookLoading"),
    pageState: document.querySelector("#bookPageState"),
    search: document.querySelector("#bookSearch"),
    summary: document.querySelector("#treeSummary"),
    tree: document.querySelector("#bookTree"),
  };
  const state = {
    currentPath: null,
    roots: [],
  };

  elements.search.addEventListener("input", () => {
    renderTree(elements, state, elements.search.value.trim());
  });
  elements.tree.addEventListener("click", (event) => {
    const toggle = event.target.closest("[data-tree-toggle]");
    if (toggle) {
      const branch = toggle.closest(".book-tree-branch");
      const children = branch?.querySelector(":scope > .book-tree-children");
      if (children) {
        children.hidden = !children.hidden;
        toggle.setAttribute("aria-expanded", String(!children.hidden));
      }
      return;
    }
    const pageLink = event.target.closest("[data-wiki-path]");
    if (pageLink) loadPage(pageLink.dataset.wikiPath);
  });
  elements.document.addEventListener("click", (event) => {
    const link = event.target.closest("[data-wiki-path]");
    if (!link) return;
    event.preventDefault();
    loadPage(link.dataset.wikiPath);
  });
  window.addEventListener("popstate", () => {
    const path = new URL(window.location.href).searchParams.get("path");
    if (path) loadPage(path, false);
  });

  try {
    const data = await apiRequest("/api/wiki/tree");
    state.roots = data.roots || [];
    elements.summary.textContent = `${countPages(state.roots)} 个页面`;
    renderTree(elements, state);

    const requested = new URL(window.location.href).searchParams.get("path");
    const firstPage = requested || findFirstPage(state.roots);
    if (firstPage) {
      await loadPage(firstPage, !requested);
    } else {
      elements.loading.hidden = true;
      elements.empty.hidden = false;
      elements.pageState.textContent = "暂无资料";
    }
  } catch (error) {
    elements.loading.hidden = true;
    elements.empty.hidden = false;
    elements.summary.textContent = "加载失败";
    showToast(error.message, "error");
  }

  async function loadPage(path, updateHistory = true) {
    if (!path) return;
    elements.loading.hidden = false;
    elements.document.hidden = true;
    elements.pageState.textContent = "正在读取";

    try {
      const data = await apiRequest(
        `/api/wiki/page?path=${encodeURIComponent(path)}`,
      );
      state.currentPath = data.path;
      renderMarkdown(elements.document, data.content, {
        stripFrontMatter: true,
        wikiLinks: true,
      });
      prepareWikiLinks(elements.document, data.path);
      renderBreadcrumbs(elements.breadcrumbs, data.path);
      markActivePage(elements.tree, data.path);
      elements.document.hidden = false;
      elements.pageState.textContent = "已同步";

      if (updateHistory) {
        const url = new URL(window.location.href);
        url.searchParams.set("path", data.path);
        window.history.pushState({}, "", url);
      }
    } catch (error) {
      elements.pageState.textContent = "读取失败";
      showToast(error.message, "error");
    } finally {
      elements.loading.hidden = true;
    }
  }
}

function renderTree(elements, state, query = "") {
  const roots = query
    ? filterNodes(state.roots, query.toLocaleLowerCase())
    : state.roots;
  const fragment = document.createDocumentFragment();

  for (const node of roots) {
    fragment.append(renderTreeNode(node));
  }
  elements.tree.replaceChildren(fragment);
  elements.empty.hidden = roots.length > 0;
  markActivePage(elements.tree, state.currentPath);
}

function renderTreeNode(node) {
  const branch = document.createElement("div");
  branch.className = "book-tree-branch";

  const row = document.createElement("div");
  row.className = `book-tree-row is-${node.type}`;

  if (node.children?.length) {
    const toggle = document.createElement("button");
    toggle.className = "book-tree-toggle";
    toggle.type = "button";
    toggle.dataset.treeToggle = "";
    toggle.setAttribute("aria-expanded", "true");
    toggle.setAttribute("aria-label", `展开或收起${node.name}`);
    toggle.textContent = "⌄";
    row.append(toggle);
  } else {
    const spacer = document.createElement("span");
    spacer.className = "book-tree-spacer";
    row.append(spacer);
  }

  const label = document.createElement(node.path ? "button" : "span");
  label.className = "book-tree-label";
  label.textContent = node.name;
  if (node.path) {
    label.type = "button";
    label.dataset.wikiPath = node.path;
  }
  row.append(label);
  branch.append(row);

  if (node.children?.length) {
    const children = document.createElement("div");
    children.className = "book-tree-children";
    children.hidden = false;
    for (const child of node.children) {
      children.append(renderTreeNode(child));
    }
    branch.append(children);
  }
  return branch;
}

function filterNodes(nodes, query) {
  return nodes.flatMap((node) => {
    if (node.name.toLocaleLowerCase().includes(query)) return [node];
    const children = filterNodes(node.children || [], query);
    return children.length ? [{ ...node, children }] : [];
  });
}

function markActivePage(tree, path) {
  for (const link of tree.querySelectorAll("[data-wiki-path]")) {
    link.classList.toggle("is-active", link.dataset.wikiPath === path);
  }
}

function renderBreadcrumbs(container, path) {
  const parts = path.split("/");
  const fragment = document.createDocumentFragment();

  parts.forEach((part, index) => {
    if (index > 0) {
      const divider = document.createElement("span");
      divider.textContent = "/";
      fragment.append(divider);
    }
    const isPage = index === parts.length - 1;
    const label = document.createElement(isPage ? "strong" : "span");
    label.textContent = isPage ? part.replace(/\.md$/i, "") : part;
    fragment.append(label);
  });
  container.replaceChildren(fragment);
}

function prepareWikiLinks(container, currentPath) {
  for (const link of container.querySelectorAll("[data-wiki-link]")) {
    const path = resolveWikiLink(currentPath, link.dataset.wikiLink);
    if (!path) continue;
    link.dataset.wikiPath = path;
    link.href = `/book?path=${encodeURIComponent(path)}`;
  }
}

function resolveWikiLink(currentPath, href) {
  if (!currentPath || !href || href.startsWith("#")) return null;
  let value;
  try {
    value = decodeURIComponent(href.split("#")[0]);
  } catch {
    value = href.split("#")[0];
  }
  value = value.replaceAll("\\", "/");
  const prefix = "generated-wiki/drafts/";
  if (value.replace(/^\/+/, "").startsWith(prefix)) {
    return value.replace(/^\/+/, "").slice(prefix.length);
  }

  const parts = currentPath.split("/");
  parts.pop();
  for (const part of value.split("/")) {
    if (!part || part === ".") continue;
    if (part === "..") parts.pop();
    else parts.push(part);
  }
  return parts.join("/");
}

function findFirstPage(nodes) {
  for (const node of nodes) {
    if (node.path) return node.path;
    const child = findFirstPage(node.children || []);
    if (child) return child;
  }
  return null;
}

function countPages(nodes) {
  return nodes.reduce(
    (total, node) => (
      total + (node.path ? 1 : 0) + countPages(node.children || [])
    ),
    0,
  );
}
