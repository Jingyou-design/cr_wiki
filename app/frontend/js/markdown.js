export function renderMarkdown(target, markdown) {
  target.innerHTML = markdownToHtml(markdown);
}

export function markdownToHtml(markdown) {
  const lines = markdown.replace(/\r\n?/g, "\n").split("\n");
  const blocks = [];
  let paragraph = [];
  let listType = "";
  let listItems = [];
  let codeFence = false;
  let codeLanguage = "";
  let codeLines = [];

  const flushParagraph = () => {
    if (!paragraph.length) return;
    const content = renderInline(paragraph.join("\n")).replace(/\n/g, "<br>");
    blocks.push(`<p>${content}</p>`);
    paragraph = [];
  };
  const flushList = () => {
    if (!listItems.length) return;
    const items = listItems
      .map((item) => `<li>${renderInline(item)}</li>`)
      .join("");
    blocks.push(`<${listType}>${items}</${listType}>`);
    listType = "";
    listItems = [];
  };

  for (const line of lines) {
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
    if (!line.trim()) {
      flushParagraph();
      flushList();
      continue;
    }
    const heading = line.match(/^(#{1,4})\s+(.+)$/);
    if (heading) {
      flushParagraph();
      flushList();
      const level = heading[1].length;
      blocks.push(`<h${level}>${renderInline(heading[2])}</h${level}>`);
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
      blocks.push(`<blockquote>${renderInline(quote[1])}</blockquote>`);
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

function renderInline(value) {
  const codeSpans = [];
  let escaped = escapeHtml(value).replace(/`([^`\n]+)`/g, (_match, code) => {
    const index = codeSpans.push(`<code>${code}</code>`) - 1;
    return `\u0000CODE${index}\u0000`;
  });
  escaped = escaped
    .replace(
      /\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g,
      '<a href="$2" target="_blank" rel="noreferrer">$1</a>',
    )
    .replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>")
    .replace(/__([^_\n]+)__/g, "<strong>$1</strong>")
    .replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>")
    .replace(/(^|[^_])_([^_\n]+)_/g, "$1<em>$2</em>");
  return escaped.replace(
    /\u0000CODE(\d+)\u0000/g,
    (_match, index) => codeSpans[index],
  );
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
