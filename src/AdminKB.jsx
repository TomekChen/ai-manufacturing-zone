import React, { useState, useEffect, useCallback } from 'react';
import DocPreview from './DocPreview';
import renderMarkdown from './markdown';

const API_BASE = '/api';

async function readError(res) {
  const text = await res.text();
  try {
    const json = JSON.parse(text);
    if (json.error) return json.error;
    if (json.message) return json.message;
  } catch {}
  return text || `请求失败（HTTP ${res.status}）`;
}

const STATUS_LABEL = {
  pending: ['待审核', 'status-pill pending'],
  approved: ['已入库', 'status-pill online'],
  rejected: ['已拒绝', 'status-pill offline'],
};
const TYPE_LABEL = { upload: '用户上传', url: 'URL 采集', link: '友情链接采集' };
// 策略中文名（仅展示用；下拉的可选值以后端 /options 为准，注册表是唯一事实来源）
const CHUNK_LABEL = { fixed: '固定窗口', semantic: '语义分块' };
const RETR_LABEL = { vector: '纯向量', bm25: 'BM25', hybrid: '混合' };
const label = (map, key) => map[key] || key;

/* ===== 后台「知识库管理」标签页：审核 + 采集(选分块) + 重建 + 问答调试 + 文档列表 ===== */
export default function AdminKB({ token, onNotify }) {
  const [docs, setDocs] = useState([]);
  const [stats, setStats] = useState(null);
  const [options, setOptions] = useState({
    chunking: ['fixed', 'semantic'], default_chunking: 'fixed',
    retrieval: ['vector', 'bm25', 'hybrid'], default_retrieval: 'hybrid',
  });
  const [filter, setFilter] = useState('all'); // pending | approved | rejected | all
  const [crawlUrl, setCrawlUrl] = useState('');
  const [crawlChunking, setCrawlChunking] = useState('fixed');
  const [crawling, setCrawling] = useState(false);
  const [busyId, setBusyId] = useState(null);
  const [rebuildingAll, setRebuildingAll] = useState(false);
  const [rebuildChoice, setRebuildChoice] = useState({}); // docId -> 重建时选的分块策略
  const [notice, setNotice] = useState(null); // {ok, text}
  const [previewDoc, setPreviewDoc] = useState(null);
  // 问答调试（选检索方式对比）
  const [dbgQ, setDbgQ] = useState('');
  const [dbgRetr, setDbgRetr] = useState('hybrid');
  const [dbgBusy, setDbgBusy] = useState(false);
  const [dbgResult, setDbgResult] = useState(null); // {answer, sources, retrieval, error}

  const auth = { Authorization: `Bearer ${token}` };

  const fetchOptions = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/admin/kb/options`, { headers: auth });
      if (!res.ok) return; // 老后端无此接口时静默用兜底值
      const data = await res.json();
      setOptions((o) => ({
        chunking: data.chunking?.length ? data.chunking : o.chunking,
        default_chunking: data.default_chunking || o.default_chunking,
        retrieval: data.retrieval?.length ? data.retrieval : o.retrieval,
        default_retrieval: data.default_retrieval || o.default_retrieval,
      }));
      setCrawlChunking((c) => c || data.default_chunking || 'fixed');
      setDbgRetr((r) => r || data.default_retrieval || 'hybrid');
    } catch { /* 忽略 */ }
  }, [token]);

  const fetchDocs = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/admin/kb/docs`, { headers: auth });
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
      const res = await fetch(`${API_BASE}/admin/kb/docs/${id}`, { headers: auth });
      if (!res.ok) throw new Error(await readError(res));
      setPreviewDoc(await res.json());
    } catch (err) {
      setNotice({ ok: false, text: err?.message || '加载预览失败' });
    }
  }, [token]);

  useEffect(() => { fetchOptions(); fetchDocs(); }, [fetchOptions, fetchDocs]);

  const doAction = async (id, action) => {
    // action: approve | reject | delete
    if (action === 'delete' && !confirm('确定删除该文档吗？知识库中对应内容将一并移除。')) return;
    setBusyId(id + action);
    setNotice(null);
    try {
      const res = action === 'delete'
        ? await fetch(`${API_BASE}/admin/kb/docs/${id}`, { method: 'DELETE', headers: auth })
        : await fetch(`${API_BASE}/admin/kb/docs/${id}/${action}`, { method: 'POST', headers: auth });
      if (!res.ok) throw new Error(await readError(res));
      await fetchDocs();
      setNotice({ ok: true, text: action === 'approve' ? '已审核通过并入库' : action === 'reject' ? '已拒绝' : '已删除' });
    } catch (err) {
      setNotice({ ok: false, text: err?.message || '操作失败' });
    } finally {
      setBusyId(null);
    }
  };

  const rebuildDoc = async (d) => {
    const chunking = rebuildChoice[d.id] || d.chunking;
    const msg = `将用「${label(CHUNK_LABEL, chunking)}」重新切分该文档并重新向量化（会重花 embedding 额度）。确定吗？`;
    if (!confirm(msg)) return;
    setBusyId(d.id + 'rebuild');
    setNotice(null);
    try {
      const res = await fetch(`${API_BASE}/admin/kb/docs/${d.id}/rebuild`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...auth },
        body: JSON.stringify({ chunking }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || '重建失败');
      await fetchDocs();
      setNotice({ ok: true, text: data.message || '单篇重建完成' });
    } catch (err) {
      setNotice({ ok: false, text: err?.message || '重建失败' });
    } finally {
      setBusyId(null);
    }
  };

  const rebuildAll = async () => {
    if (rebuildingAll) return;
    const msg = '全库重建：对每篇按其记录的分块策略重新切块并重新向量化，' +
      '文档较多时会消耗较多 embedding 额度、耗时也更长。确定执行吗？';
    if (!confirm(msg)) return;
    setRebuildingAll(true);
    setNotice(null);
    try {
      const res = await fetch(`${API_BASE}/admin/kb/rebuild`, { method: 'POST', headers: auth });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || '全库重建失败');
      await fetchDocs();
      setNotice({ ok: true, text: data.message || '全库重建完成' });
    } catch (err) {
      setNotice({ ok: false, text: err?.message || '全库重建失败' });
    } finally {
      setRebuildingAll(false);
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
        headers: { 'Content-Type': 'application/json', ...auth },
        body: JSON.stringify({ url: u, chunking: crawlChunking }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || '采集失败');
      setCrawlUrl('');
      await fetchDocs();
      setNotice({ ok: true, text: `采集成功：「${data.doc?.title || u}」已入库（${data.doc?.chars || 0} 字，${data.doc?.chunk_ids?.length || 0} 块，${label(CHUNK_LABEL, data.doc?.chunking)}）` });
      if (data.doc?.id) fetchDetail(data.doc.id);
    } catch (err) {
      setNotice({ ok: false, text: err?.message || '采集失败' });
    } finally {
      setCrawling(false);
    }
  };

  const debugAsk = async (e) => {
    e.preventDefault();
    const q = dbgQ.trim();
    if (!q || dbgBusy) return;
    setDbgBusy(true);
    setDbgResult(null);
    try {
      const res = await fetch(`${API_BASE}/kb/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q, retrieval: dbgRetr }),
      });
      if (!res.ok) throw new Error(await readError(res));
      const data = await res.json();
      setDbgResult({ answer: data.answer, sources: data.sources || [], retrieval: data.retrieval });
    } catch (err) {
      setDbgResult({ error: true, text: err?.message || '问答失败' });
    } finally {
      setDbgBusy(false);
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
      {/* 问答调试：选检索方式对比效果（Slice 2） */}
      <div className="kb-debug">
        <div className="kb-debug-title">问答调试（对比检索策略）</div>
        <form className="kb-debug-row" onSubmit={debugAsk}>
          <input
            type="text"
            value={dbgQ}
            onChange={(e) => setDbgQ(e.target.value)}
            placeholder="输入问题，测试不同检索方式的召回差异…"
            maxLength={500}
            disabled={dbgBusy}
          />
          <select value={dbgRetr} onChange={(e) => setDbgRetr(e.target.value)} disabled={dbgBusy} title="检索方式">
            {options.retrieval.map((r) => (<option key={r} value={r}>{label(RETR_LABEL, r)}</option>))}
          </select>
          <button type="submit" className="btn btn-primary btn-sm" disabled={dbgBusy || !dbgQ.trim()}>
            {dbgBusy ? '检索中…' : '提问'}
          </button>
        </form>
        {dbgResult && (
          <div className="kb-debug-answer">
            {dbgResult.error ? (
              <div className="kb-notice err">{dbgResult.text}</div>
            ) : (
              <>
                <div className="kb-debug-meta">
                  本次实际检索：<span className="kb-tag">{label(RETR_LABEL, dbgResult.retrieval)}</span>
                  {' · '}命中来源 {dbgResult.sources.length} 条
                </div>
                <div className="qa-answer-content" dangerouslySetInnerHTML={{ __html: renderMarkdown(dbgResult.answer) }} />
                {dbgResult.sources.length > 0 && (
                  <div className="qa-sources">
                    <div className="qa-sources-title">参考来源</div>
                    {dbgResult.sources.map((s, j) => (
                      <div className="qa-source" key={j}>
                        <span className="qa-source-num">{j + 1}</span>
                        {s.url ? (
                          <a href={s.url} target="_blank" rel="noreferrer" className="qa-source-name" title={s.snippet || s.title}>{s.title || s.url}</a>
                        ) : (
                          <span className="qa-source-name" title={s.snippet || s.title}>{s.title}</span>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>

      {/* URL 采集（可选分块方式，Slice 3） */}
      <form className="kb-crawl-row" onSubmit={crawl}>
        <input
          type="url"
          value={crawlUrl}
          onChange={(e) => setCrawlUrl(e.target.value)}
          placeholder="粘贴【具体文章页】地址（不要网站首页），抓取正文入库。例：某篇政策解读/技术文章的详情页 URL"
          required
        />
        <select value={crawlChunking} onChange={(e) => setCrawlChunking(e.target.value)} title="分块方式">
          {options.chunking.map((c) => (<option key={c} value={c}>{label(CHUNK_LABEL, c)}</option>))}
        </select>
        <button type="submit" className="btn btn-primary" disabled={crawling || !crawlUrl.trim()}>
          {crawling ? '采集中…' : '采集入库'}
        </button>
      </form>
      <div className="kb-crawl-hint">
        提示：请粘贴<strong>单篇文章的详情页地址</strong>。网站首页抓出来的只是栏目名和导航，没有正文价值。
        「分块方式」决定这篇文章怎么切：<strong>固定窗口</strong>稳妥通用，<strong>语义分块</strong>按段落聚合、更连贯。
        入库后可在下方对单篇「换分块策略重建」。
      </div>

      {/* 统计 + 筛选 + 全库重建 */}
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
          ].map(([key, labelTxt]) => (
            <button key={key} className={`kb-filter ${filter === key ? 'active' : ''}`} onClick={() => setFilter(key)}>
              {labelTxt}
            </button>
          ))}
          <button className="btn btn-ghost btn-sm" onClick={rebuildAll} disabled={rebuildingAll}
            title="按各文档记录的分块策略整体重新切块 + 重新向量化">
            {rebuildingAll ? '重建中…' : '全库重建'}
          </button>
        </div>
      </div>

      {notice && <div className={`kb-notice ${notice.ok ? 'ok' : 'err'}`}>{notice.text}</div>}

      {/* 文档列表 */}
      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr><th>标题</th><th>来源</th><th>分块</th><th>字数</th><th>时间</th><th>状态</th><th>操作</th></tr>
          </thead>
          <tbody>
            {shown.length === 0 && (
              <tr><td colSpan={7} className="kb-empty-row">暂无{filter === 'pending' ? '待审核' : ''}文档</td></tr>
            )}
            {shown.map((d) => {
              const [stLabel, stCls] = STATUS_LABEL[d.status] || [d.status, ''];
              const choice = rebuildChoice[d.id] || d.chunking || options.default_chunking;
              const changed = choice !== d.chunking;
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
                  <td><span className="kb-tag">{label(CHUNK_LABEL, d.chunking)}</span></td>
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
                    {/* 单篇换分块策略重建（Slice 3） */}
                    <select
                      className="kb-rebuild-select"
                      value={choice}
                      disabled={busyId === d.id + 'rebuild'}
                      onChange={(e) => setRebuildChoice((m) => ({ ...m, [d.id]: e.target.value }))}
                      title="选择重建用的分块策略"
                    >
                      {options.chunking.map((c) => (<option key={c} value={c}>{label(CHUNK_LABEL, c)}</option>))}
                    </select>
                    <button className="btn btn-ghost btn-sm" disabled={busyId === d.id + 'rebuild'}
                      onClick={() => rebuildDoc(d)}>
                      {busyId === d.id + 'rebuild' ? '重建中…' : (changed ? '换策略重建' : '重建')}
                    </button>
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
