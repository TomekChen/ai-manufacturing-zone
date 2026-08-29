/* 轻量级 Markdown 渲染（仅支持 LLM 回答常见语法：标题、加粗、斜体、列表、行内代码）。
 * 不引入外部库，避免 npm install 踩坑。输出已做 HTML 转义，可安全用于 dangerouslySetInnerHTML。
 */

function escapeHtml(s) {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function inlineMarkup(line) {
  return line
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>');
}

export function renderMarkdown(md = '') {
  if (!md) return '';
  const lines = String(md).split('\n');
  const out = [];
  let inUl = false;
  let inOl = false;
  const closeLists = () => {
    if (inUl) { out.push('</ul>'); inUl = false; }
    if (inOl) { out.push('</ol>'); inOl = false; }
  };
  const pBuf = [];
  let pOpen = false;
  const flushP = () => {
    if (pOpen && pBuf.length) {
      out.push('<p>' + pBuf.join('') + '</p>');
      pBuf.length = 0;
      pOpen = false;
    }
  };

  for (const raw of lines) {
    const line = inlineMarkup(escapeHtml(raw));
    const trimmed = raw.trim();

    if (!trimmed) {
      flushP();
      closeLists();
      continue;
    }

    const h = trimmed.match(/^(#{1,6}) (.*)$/);
    if (h) {
      flushP();
      closeLists();
      const tag = 'h' + h[1].length;
      out.push(`<${tag}>${inlineMarkup(escapeHtml(h[2]))}</${tag}>`);
      continue;
    }

    const ul = trimmed.match(/^[-*+] (.*)$/);
    if (ul) {
      flushP();
      if (inOl) closeLists();
      if (!inUl) { out.push('<ul>'); inUl = true; }
      out.push(`<li>${inlineMarkup(escapeHtml(ul[1]))}</li>`);
      continue;
    }

    const ol = trimmed.match(/^(\d+)\. (.*)$/);
    if (ol) {
      flushP();
      if (inUl) closeLists();
      if (!inOl) { out.push('<ol>'); inOl = true; }
      out.push(`<li>${inlineMarkup(escapeHtml(ol[2]))}</li>`);
      continue;
    }

    closeLists();
    if (pBuf.length) pBuf.push('<br/>');
    pBuf.push(line);
    pOpen = true;
  }
  flushP();
  closeLists();
  return out.join('');
}

export default renderMarkdown;
