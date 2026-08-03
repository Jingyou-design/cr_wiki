export function renderMarkdown(target, markdown, options = {}) {
  target.innerHTML = markdownToHtml(markdown, options);
}

export function markdownToHtml(markdown, options = {}) {
  const source = options.stripFrontMatter
    ? stripFrontMatter(markdown)
    : markdown;
  const lines = source.replace(/\r\n?/g, "\n").split("\n");
  const blocks = [];
  let paragraph = [];
  let listType = "";
  let listItems = [];
  let codeFence = false;
  let codeLanguage = "";
  let codeLines = [];

  const flushParagraph = () => {
    if (!paragraph.length) return;
    const content = renderInline(
      paragraph.join("\n"),
      options,
    ).replace(/\n/g, "<br>");
    blocks.push(`<p>${content}</p>`);
    paragraph = [];
  };
  const flushList = () => {
    if (!listItems.length) return;
    const items = listItems
      .map((item) => `<li>${renderInline(item, options)}</li>`)
      .join("");
    blocks.push(`<${listType}>${items}</${listType}>`);
    listType = "";
    listItems = [];
  };

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    const fence = line.match(/^```\s*([\w+-]*)\s*$/);
    if (fence) {
      flushParagraph();
      flushList();
      if (codeFence) {
        const languageClass = codeLanguage
          ? ` class="language-${escapeHtml(codeLanguage)}"`
          : "";
        blocks.push(
          `<pre><code${languageClass}>${escapeHtml(codeLines.join("\n"))}</code></pre>`,
        );
        codeFence = false;
        codeLanguage = "";
        codeLines = [];
      } else {
        codeFence = true;
        codeLanguage = fence[1] || "";
      }
      continue;
    }
    if (codeFence) {
      codeLines.push(line);
      continue;
    }
    if (
      line.includes("|")
      && index + 1 < lines.length
      && isTableDivider(lines[index + 1])
    ) {
      flushParagraph();
      flushList();
      const table = renderTable(lines, index, options);
      blocks.push(table.html);
      index = table.lastIndex;
      continue;
    }
    if (!line.trim()) {
      flushParagraph();
      flushList();
      continue;
    }
    const heading = line.match(/^(#{1,6})\s+(.+)$/);
    if (heading) {
      flushParagraph();
      flushList();
      const level = heading[1].length;
      blocks.push(
        `<h${level}>${renderInline(heading[2], options)}</h${level}>`,
      );
      continue;
    }
    if (/^(---+|\*\*\*+)$/.test(line.trim())) {
      flushParagraph();
      flushList();
      blocks.push("<hr>");
      continue;
    }
    const unordered = line.match(/^\s*[-*+]\s+(.+)$/);
    const ordered = line.match(/^\s*\d+[.)]\s+(.+)$/);
    if (unordered || ordered) {
      flushParagraph();
      const nextType = unordered ? "ul" : "ol";
      if (listType && listType !== nextType) flushList();
      listType = nextType;
      listItems.push((unordered || ordered)[1]);
      continue;
    }
    const quote = line.match(/^>\s?(.*)$/);
    if (quote) {
      flushParagraph();
      flushList();
      blocks.push(
        `<blockquote>${renderInline(quote[1], options)}</blockquote>`,
      );
      continue;
    }
    flushList();
    paragraph.push(line);
  }
  if (codeFence) {
    blocks.push(`<pre><code>${escapeHtml(codeLines.join("\n"))}</code></pre>`);
  }
  flushParagraph();
  flushList();
  return blocks.join("");
}

function renderTable(lines, startIndex, options) {
  const headers = splitTableRow(lines[startIndex]);
  const rows = [];
  let lastIndex = startIndex + 1;

  for (
    let index = startIndex + 2;
    index < lines.length && lines[index].includes("|") && lines[index].trim();
    index += 1
  ) {
    rows.push(splitTableRow(lines[index]));
    lastIndex = index;
  }

  const head = headers
    .map((cell) => `<th>${renderInline(cell, options)}</th>`)
    .join("");
  const body = rows
    .map((row) => (
      `<tr>${headers
        .map((_, index) => (
          `<td>${renderInline(row[index] || "", options)}</td>`
        ))
        .join("")}</tr>`
    ))
    .join("");

  return {
    html: `<div class="markdown-table-wrap"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`,
    lastIndex,
  };
}

function splitTableRow(line) {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
}

function isTableDivider(line) {
  const cells = splitTableRow(line);
  return (
    cells.length > 0
    && cells.every((cell) => /^:?-{3,}:?$/.test(cell))
  );
}

function renderInline(value, options) {
  const tokens = [];
  const protect = (html) => {
    const index = tokens.push(html) - 1;
    return `\u0000TOKEN${index}\u0000`;
  };

  let source = String(value).replace(
    /`([^`\n]+)`/g,
    (_match, code) => protect(`<code>${escapeHtml(code)}</code>`),
  );
  source = source.replace(
    /\[([^\]]+)\]\(([^)\s]+)\)/g,
    (_match, label, href) => protect(renderLink(label, href, options)),
  );

  const escaped = escapeHtml(source)
    .replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>")
    .replace(/__([^_\n]+)__/g, "<strong>$1</strong>")
    .replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>")
    .replace(/(^|[^_])_([^_\n]+)_/g, "$1<em>$2</em>");

  return escaped.replace(
    /\u0000TOKEN(\d+)\u0000/g,
    (_match, index) => tokens[index],
  );
}

function renderLink(label, href, options) {
  const safeLabel = escapeHtml(label);
  const safeHref = escapeHtml(href);

  if (/^https?:\/\//i.test(href)) {
    return (
      `<a href="${safeHref}" target="_blank" rel="noreferrer">`
      + `${safeLabel}</a>`
    );
  }
  if (href.startsWith("#")) {
    return `<a href="${safeHref}">${safeLabel}</a>`;
  }
  if (options.wikiLinks && !/^[a-z][a-z0-9+.-]*:/i.test(href)) {
    return (
      `<a href="#" data-wiki-link="${safeHref}">`
      + `${safeLabel}</a>`
    );
  }
  return safeLabel;
}

function stripFrontMatter(markdown) {
  const lines = String(markdown).replace(/\r\n?/g, "\n").split("\n");
  if (lines[0]?.trim() !== "---") return markdown;

  const end = lines.findIndex(
    (line, index) => index > 0 && line.trim() === "---",
  );
  return end < 0 ? markdown : lines.slice(end + 1).join("\n");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
