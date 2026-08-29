import React, { useState, useEffect, useCallback } from 'react';

const API_BASE = '/api';

/* ===== 底部友情链接区：访客点击跳转；管理员可快捷「采集入库」 ===== */
export default function LinkFooter({ isAdmin, token }) {
  const [links, setLinks] = useState([]);
  const [crawling, setCrawling] = useState(null); // 正在采集的 link id
  const [crawlMsg, setCrawlMsg] = useState(null); // {ok, text}

  const fetchLinks = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/links`);
      if (res.ok) setLinks(await res.json());
    } catch { /* 静默失败，footer 不弹错 */ }
  }, []);

  useEffect(() => { fetchLinks(); }, [fetchLinks]);

  const crawl = async (link) => {
    if (crawling) return;
    if (!confirm(`采集「${link.name}」页面内容到知识库？`)) return;
    setCrawling(link.id);
    setCrawlMsg(null);
    try {
      const res = await fetch(`${API_BASE}/admin/links/${link.id}/crawl`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || '采集失败');
      setCrawlMsg({ ok: true, text: data.message || '采集成功，已入库' });
    } catch (err) {
      setCrawlMsg({ ok: false, text: err?.message || '采集失败' });
    } finally {
      setCrawling(null);
    }
  };

  if (!links.length) return null;

  return (
    <div className="links-strip">
      <div className="container">
        <div className="links-head">
          <span className="links-title">推荐站点 · 行业权威信息来源</span>
          {isAdmin && <span className="links-admin-hint">（可在后台管理并一键采集入库）</span>}
        </div>
        <div className="links-list">
          {links.map((l) => (
            <div className="link-chip-wrap" key={l.id}>
              <a className="link-chip" href={l.url} target="_blank" rel="noreferrer" title={l.desc || l.url}>
                {l.name}
              </a>
              {isAdmin && (
                <button
                  className="link-crawl-btn"
                  onClick={() => crawl(l)}
                  disabled={crawling === l.id}
                  title="抓取该页面内容并入知识库"
                >
                  {crawling === l.id ? '采集中…' : '采集'}
                </button>
              )}
            </div>
          ))}
        </div>
        {crawlMsg && <div className={`links-crawl-msg ${crawlMsg.ok ? 'ok' : 'err'}`}>{crawlMsg.text}</div>}
      </div>
    </div>
  );
}
