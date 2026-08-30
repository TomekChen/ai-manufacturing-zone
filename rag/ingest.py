# -*- coding: utf-8 -*-
"""采集与解析：网页正文抽取（简易 readability）、导航页判定、PDF 文本提取。

这些和"检索策略"无关，只负责把外部资料变成纯文本，交给上层分块。
"""
import re

import requests

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover
    BeautifulSoup = None


# 抓取时要整体丢弃的"结构性噪音"标签（这些永远不会是文章正文）
_BOILERPLATE_TAGS = ["script", "style", "noscript", "iframe", "svg", "canvas",
                     "form", "button", "input", "select", "nav", "header", "footer", "aside"]

# 优先认定为"正文容器"的选择器（覆盖常见 CMS / 政府站 TRS 编辑器 / 资讯站）
_CONTENT_SELECTORS = [
    "article", "main", "[role=main]",
    ".article", ".article-content", ".article_content", ".post-content",
    ".content", ".detail", ".detail-content", ".news-content", ".txt",
    ".TRS_Editor", "#UCAP-CONTENT", ".pages_content", "#content", "#article", "#zoom",
]

# id/class 里出现这些词，基本是推荐位/评论/分享/版权等噪音块
_JUNK_PAT = re.compile(
    r"(comment|related|recommend|crumb|breadcrumb|banner|copyright|beian|share|"
    r"more|responsible|editor-?info|appendix|xgwj|sw|footer|header|nav|menu|"
    r"sidebar|side-?bar|ads?|advert|login|search|tool|function|download|"
    r"app-?down|erweima|qrcode|pop|dialog|mask)", re.I)


def _link_density(node):
    """节点内链接文字占比。正文低、导航/列表高——用来排除"一堆标题"的块。"""
    total = len(node.get_text(strip=True))
    if not total:
        return 1.0
    link = sum(len(a.get_text(strip=True)) for a in node.find_all("a"))
    return link / total


def _extract_main_node(soup):
    """挑出最像"文章正文"的 DOM 子树（简易 readability）。"""
    for sel in _CONTENT_SELECTORS:
        try:
            node = soup.select_one(sel)
        except Exception:
            node = None
        if node is not None and len(node.get_text(strip=True)) > 200 and _link_density(node) < 0.5:
            return node
    best, best_score = None, 0.0
    for node in soup.find_all(["div", "section", "article", "td"]):
        text_len = len(node.get_text(strip=True))
        if text_len < 200:
            continue
        score = text_len * (1.0 - _link_density(node))
        if score > best_score:
            best, best_score = node, score
    return best


def _pick_title(soup, fallback=""):
    """标题优先级：og:title / twitter:title > <h1> > <title>（去掉站点后缀）。"""
    for attrs in ({"property": "og:title"}, {"name": "og:title"},
                  {"property": "twitter:title"}, {"name": "twitter:title"}):
        m = soup.find("meta", attrs=attrs)
        if m and (m.get("content") or "").strip():
            return m["content"].strip()
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return h1.get_text(strip=True)
    if soup.title and soup.title.string:
        t = soup.title.string.strip()
        for sep in ("_", "-", "|", "—", "－"):
            if sep in t:
                head = t.split(sep, 1)[0].strip()
                if len(head) >= 6:
                    return head
        return t
    return fallback


def fetch_url_text(url, timeout=25):
    """抓取网页并提取【正文】文本，返回 (title, text)。

    注意：应传入"具体文章页"地址。门户首页正文本来就是一堆栏目标题，
    抓出来没有知识价值（链接密度过滤会尽力剔除这类导航块）。
    """
    if BeautifulSoup is None:
        raise RuntimeError("服务器缺少 beautifulsoup4 依赖")
    r = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                               "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"},
        timeout=timeout,
        verify=False,
    )
    r.raise_for_status()
    r.encoding = r.apparent_encoding or r.encoding or "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")

    title = _pick_title(soup, fallback=url)

    for tag in soup(_BOILERPLATE_TAGS):
        tag.decompose()
    for node in soup.find_all(attrs={"id": _JUNK_PAT}) + soup.find_all(attrs={"class": _JUNK_PAT}):
        if len(node.get_text(strip=True)) < 600:
            node.decompose()

    main = _extract_main_node(soup) or soup.body or soup
    text = main.get_text("\n", strip=True)
    text = re.sub(r"[ \t\u3000]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return title, text


def looks_like_nav_page(text):
    """判断抽出来的"正文"是不是一堆标题/导航（首页、列表页的典型特征）。

    正文页应有成段的长文本；若几乎没有一行像句子（长度≥40 或含句读），
    基本就是门户首页/栏目标题列表，采进来没有知识价值。
    """
    lines = [ln.strip() for ln in (text or "").split("\n") if ln.strip()]
    if not lines:
        return True
    has_paragraph = any(
        len(ln) >= 40 or any(p in ln for p in ("。", "！", "？", "；"))
        for ln in lines
    )
    return not has_paragraph


def extract_pdf_text(fileobj):
    from pypdf import PdfReader
    reader = PdfReader(fileobj)
    parts = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    return "\n".join(parts)
