import React, { useEffect, useState, useCallback } from 'react';
import { readError } from './api';

const API_BASE = '/api';


/* ===== 管理后台 · 方案会话列表（A4-T4：售前对话沉淀盘点） =====
   GET /api/admin/prd-sessions（需管理员 token），摘要列表新→旧，
   点"查看"打开只读分享页 /s/<id>（与发给客户的链接同一个页面）。
   A4.5 入库飞轮：一键把会话最新版方案送入知识库待审（status=pending），
   到「知识库」页签批准后知识管家即可引用。 */
export default function AdminSessions({ token }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState('');
  const [msg, setMsg] = useState('');

  const load = useCallback(async () => {
    setLoading(true); setErr('');
    try {
      const res = await fetch(`${API_BASE}/admin/prd-sessions`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(await readError(res));
      const d = await res.json();
      setItems(Array.isArray(d) ? d : (d.sessions || []));
    } catch (e) {
      setErr(e?.message || '加载失败');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { load(); }, [load]);

  const ingest = async (s) => {
    setBusy(s.id); setErr(''); setMsg('');
    try {
      const res = await fetch(`${API_BASE}/admin/prd-sessions/${s.id}/ingest`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(await readError(res));
      setMsg(`「${s.title}」已入待审库，到「知识库」页签批准后生效`);
      await load();
    } catch (e) {
      setErr(e?.message || '入库失败');
    } finally {
      setBusy('');
    }
  };

  if (loading) return <div className="muted" style={{ padding: 12 }}>加载中…</div>;
  if (err) return (
    <div>
      <div className="form-error" style={{ marginBottom: 12 }}>{err}</div>
      <button className="btn btn-ghost btn-sm" onClick={load}>重试</button>
    </div>
  );

  return (
    <>
      <div className="admin-toolbar">
        <button className="btn btn-ghost btn-sm" onClick={load}>刷新</button>
        <span className="muted">共 {items.length} 个会话 · 新的在前 · 后端最多保留 100 个</span>
      </div>
      {msg && <div style={{ margin: '8px 12px', color: '#15803d', fontSize: 13 }}>{msg}</div>}
      {err && <div className="form-error" style={{ margin: '8px 12px' }}>{err}</div>}
      {items.length === 0 ? (
        <div className="muted" style={{ padding: 12 }}>
          还没有方案会话。访客在首页用「售前方案师」生成方案后，这里会出现沉淀记录。
        </div>
      ) : (
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr><th>最近更新</th><th>客户会话</th><th>创建时间</th><th>版本数</th><th>操作</th></tr>
            </thead>
            <tbody>
              {items.map(s => (
                <tr key={s.id}>
                  <td className="muted" style={{ whiteSpace: 'nowrap' }}>{(s.updated || '').replace('T', ' ')}</td>
                  <td><strong>{s.title}</strong></td>
                  <td className="muted" style={{ whiteSpace: 'nowrap' }}>{(s.created || '').replace('T', ' ')}</td>
                  <td>
                    <span className="status-pill online">v1–v{s.version_count}</span>
                  </td>
                  <td style={{ whiteSpace: 'nowrap' }}>
                    <a className="btn btn-ghost btn-sm" href={`/s/${s.id}`} target="_blank" rel="noreferrer">
                      查看分享页
                    </a>{' '}
                    {s.ingested ? (
                      <span className="status-pill online">已入库</span>
                    ) : (
                      <button className="btn btn-sm" disabled={busy === s.id}
                              onClick={() => ingest(s)}>
                        {busy === s.id ? '入库中…' : '入库知识库'}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
