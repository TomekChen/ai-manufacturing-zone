import React, { useState, useEffect, useCallback } from 'react';
import DocPreview from './DocPreview';

const API_BASE = '/api';

async function readError(res) {
  const text = await res.text();
  try {
    const json = JSON.parse(text);
    if (json.error) return json.error;
  } catch {}
  return text || `请求失败（HTTP ${res.status}）`;
}

const STATUS_LABEL = {
  pending: ['待审核', 'status-pill pending'],
  approved: ['已入库', 'status-pill online'],
  rejected: ['已拒绝', 'status-pill offline'],
};
const TYPE_LABEL = { upload: '用户上传', url: 'URL 采集', link: '友情链接采集' };

/* ===== 后台「知识库管理」标签页：审核 + URL 采集 + 文档列表 ===== */
export default function AdminKB({ token, onNotify }) {
  const [docs, setDocs] = useState([]);
  const [stats, setStats] = useState(null);
  const [filter, setFilter] = useState('all'); // pending | approved | rejected | all
  const [crawlUrl, setCrawlUrl] = useState('');
  const [crawling, setCrawling] = useState(false);
  const [busyId, setBusyId] = useState(null);
  const [notice, setNotice] = useState(null); // {ok, text}
  const [previewDoc, setPreviewDoc] = useState(null);

  const fetchDocs = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/admin/kb/docs`, { headers: { Authorization: `Bearer ${token}` } });
      if (!res.ok) throw new Error(await readError(res));
      const data = await res.json();
      setDocs(data.docs || []);
      setStats(data.stats);
    } catch (err) {
      setNotice({ ok: false, text: err?.message || '加载失败' });
    }
  }, [token]);

  const fetchDetail = useCallback(async (id) => {
    setPreviewDoc(null);
    try {
      const res = await fetch(`${API_BASE}/admin/kb/docs/${id}`, { headers: { Authorization: `Bearer ${token}` } });
      if (!res.ok) throw new Error(await readError(res));
      setPreviewDoc(await res.json());
    } catch (err) {
      setNotice({ ok: false, text: err?.message || '加载预览失败' });
    }
  }, [token]);

  useEffect(() => { fetchDocs(); }, [fetchDocs]);

  const doAction = async (id, action) => {
    // action: approve | reject | delete
    if (action === 'delete' && !confirm('确定删除该文档吗？知识库中对应内容将一并移除。')) return;
    setBusyId(id + action);
    setNotice(null);
    try {
      const res = action === 'delete'
        ? await fetch(`${API_BASE}/admin/kb/docs/${id}`, { method: 'DELETE', headers: { Authorization: `Bearer ${token}` } })
        : await fetch(`${API_BASE}/admin/kb/docs/${id}/${action}`, { method: 'POST', headers: { Authorization: `Bearer ${token}` } });
      if (!res.ok) throw new Error(await readError(res));
      await fetchDocs();
      setNotice({ ok: true, text: action === 'approve' ? '已审核通过并入库' : action === 'reject' ? '已拒绝' : '已删除' });
    } catch (err) {
      setNotice({ ok: false, text: err?.message || '操作失败' });
    } finally {
      setBusyId(null);
    }
  };

  const crawl = async (e) => {
    e.preventDefault();
    const u = crawlUrl.trim();
    if (!u || crawling) return;
    setCrawling(true);
    setNotice(null);
    try {
      const res = await fetch(`${API_BASE}/admin/kb/crawl`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ url: u }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || '采集失败');
      setCrawlUrl('');
      await fetchDocs();
      setNotice({ ok: true, text: `采集成功：「${data.doc?.title || u}」已入库（${data.doc?.chars || 0} 字，${data.doc?.chunk_ids?.length || 0} 块）` });
      if (data.doc?.id) fetchDetail(data.doc.id);
    } catch (err) {
      setNotice({ ok: false, text: err?.message || '采集失败' });
    } finally {
      setCrawling(false);
    }
  };

  const shown = filter === 'all' ? docs : docs.filter((d) => d.status === filter);
  const counts = {
    pending: docs.filter((d) => d.status === 'pending').length,
    approved: docs.filter((d) => d.status === 'approved').length,
    rejected: docs.filter((d) => d.status === 'rejected').length,
    all: docs.length,
  };

  return (
    <div className="kb-admin">
      {/* URL 采集 */}
      <form className="kb-crawl-row" onSubmit={crawl}>
        <input
          type="url"
          value={crawlUrl}
          onChange={(e) => setCrawlUrl(e.target.value)}
          placeholder="粘贴【具体文章页】地址（不要网站首页），抓取正文入库。例：某篇政策解读/技术文章的详情页 URL"
          required
        />
        <button type="submit" className="btn btn-primary" disabled={crawling || !crawlUrl.trim()}>
          {crawling ? '采集中…' : '采集入库'}
        </button>
      </form>
      <div className="kb-crawl-hint">
        提示：请粘贴<strong>单篇文章的详情页地址</strong>。网站首页（如 e-works 首页、工信部首页）抓出来的只是栏目名和导航，没有正文价值。
        采集成功后会自动弹出「预览」，可直接查看入库的分块正文。
      </div>

      {/* 统计 + 筛选 */}
      <div className="kb-toolbar">
        <div className="kb-stats">
          {stats && (
            <>
              <span className="kb-stat">共 {stats.total} 份文档</span>
              <span className="kb-stat ok">{stats.approved} 份已入库</span>
              <span className="kb-stat warn">{stats.pending} 份待审核</span>
              <span className="kb-stat muted">{stats.chunks} 个知识块</span>
            </>
          )}
        </div>
        <div className="kb-filters">
          {[
            ['pending', `待审核${counts.pending ? ` (${counts.pending})` : ''}`],
            ['approved', '已入库'],
            ['rejected', '已拒绝'],
            ['all', '全部'],
          ].map(([key, label]) => (
            <button key={key} className={`kb-filter ${filter === key ? 'active' : ''}`} onClick={() => setFilter(key)}>
              {label}
            </button>
          ))}
        </div>
      </div>

      {notice && <div className={`kb-notice ${notice.ok ? 'ok' : 'err'}`}>{notice.text}</div>}

      {/* 文档列表 */}
      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr><th>标题</th><th>来源</th><th>字数</th><th>时间</th><th>状态</th><th>操作</th></tr>
          </thead>
          <tbody>
            {shown.length === 0 && (
              <tr><td colSpan={6} className="kb-empty-row">暂无{filter === 'pending' ? '待审核' : ''}文档</td></tr>
            )}
            {shown.map((d) => {
              const [stLabel, stCls] = STATUS_LABEL[d.status] || [d.status, ''];
              return (
                <tr key={d.id}>
                  <td>
                    <strong>{d.title}</strong>
                    {d.url && (
                      <div className="muted" style={{ maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        <a href={d.url} target="_blank" rel="noreferrer">{d.url}</a>
                      </div>
                    )}
                  </td>
                  <td className="muted">{TYPE_LABEL[d.type] || d.type}</td>
                  <td className="muted">{d.chars}</td>
                  <td className="muted">{(d.created_at || '').slice(0, 16).replace('T', ' ')}</td>
                  <td><span className={stCls}>{stLabel}</span></td>
                  <td>
                    {d.status === 'pending' && (
                      <>
                        <button className="btn btn-primary btn-sm" disabled={busyId === d.id + 'approve'}
                          onClick={() => doAction(d.id, 'approve')}>
                          {busyId === d.id + 'approve' ? '入库中…' : '通过'}
                        </button>
                        <button className="btn btn-ghost btn-sm" disabled={busyId === d.id + 'reject'}
                          onClick={() => doAction(d.id, 'reject')}>拒绝</button>
                      </>
                    )}
                    {d.status === 'rejected' && (
                      <button className="btn btn-ghost btn-sm" disabled={busyId === d.id + 'approve'}
                        onClick={() => doAction(d.id, 'approve')}>重新通过</button>
                    )}
                    <button className="btn btn-ghost btn-sm" onClick={() => fetchDetail(d.id)}>预览</button>
                    <button className="btn btn-danger btn-sm" disabled={busyId === d.id + 'delete'}
                      onClick={() => doAction(d.id, 'delete')}>删除</button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {previewDoc && <DocPreview doc={previewDoc} onClose={() => setPreviewDoc(null)} />}
    </div>
  );
}
