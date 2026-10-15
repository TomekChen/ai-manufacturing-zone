import React, { useEffect, useState, useCallback } from 'react';
import { readError } from './api';

const API_BASE = '/api';

/* ===== 审批留痕（A10）：智能体产出先审后用 =====
   公开端提交的 AI 建议（对账分录/工单等）在此排队：
   pending → 批准/驳回（驳回必填理由）→ 回执归档。
   trail 为 append-only，已决事项不可改不可删（ISO 留痕）。 */

const STATUS = {
  pending: { label: '待审批', cls: 'offline' },
  approved: { label: '已批准', cls: 'online' },
  rejected: { label: '已驳回', cls: 'offline' },
};

const ACTION_LABEL = { submitted: '提交', approved: '批准', rejected: '驳回' };

export default function AdminApproval({ token }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');
  const [msg, setMsg] = useState('');
  const [busy, setBusy] = useState('');
  const [openId, setOpenId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [noteFor, setNoteFor] = useState(null);
  const [note, setNote] = useState('');

  const load = useCallback(async () => {
    setLoading(true); setErr('');
    try {
      const res = await fetch(`${API_BASE}/admin/approvals`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(await readError(res));
      setItems(await res.json());
    } catch (e) {
      setErr(e?.message || '加载失败');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { load(); }, [load]);

  const openDetail = async (id) => {
    if (openId === id) { setOpenId(null); setDetail(null); return; }
    setOpenId(id); setDetail(null); setErr('');
    try {
      const res = await fetch(`${API_BASE}/admin/approvals/${id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(await readError(res));
      setDetail(await res.json());
    } catch (e) {
      setErr(e?.message || '加载详情失败');
    }
  };

  const decide = async (item, action, n) => {
    setBusy(item.id); setErr(''); setMsg('');
    try {
      const res = await fetch(`${API_BASE}/admin/approvals/${item.id}/${action}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ note: n || '' }),
      });
      if (!res.ok) throw new Error(await readError(res));
      const d = await res.json();
      setMsg(`审批单 ${item.id} 已${action === 'approve' ? '批准' : '驳回'}（${d.decided_at}）`);
      setNoteFor(null); setNote('');
      await load();
      if (openId === item.id) await openDetail(item.id);
    } catch (e) {
      setErr(e?.message || '操作失败');
    } finally {
      setBusy('');
    }
  };

  if (loading) return <div className="muted" style={{ padding: 12 }}>加载中…</div>;
  if (err && items.length === 0) return (
    <div>
      <div className="form-error" style={{ marginBottom: 12 }}>{err}</div>
      <button className="btn btn-ghost btn-sm" onClick={load}>重试</button>
    </div>
  );

  const pendingCount = items.filter(x => x.status === 'pending').length;

  return (
    <>
      <div className="admin-toolbar">
        <button className="btn btn-ghost btn-sm" onClick={load}>刷新</button>
        <span className="muted">
          共 {items.length} 单 · 待审批 {pendingCount} · 留痕 append-only，已决事项不可改不可删
        </span>
      </div>
      {msg && <div style={{ margin: '8px 12px', color: '#15803d', fontSize: 13 }}>{msg}</div>}
      {err && <div className="form-error" style={{ margin: '8px 12px' }}>{err}</div>}
      {items.length === 0 ? (
        <div className="muted" style={{ padding: 12 }}>
          还没有审批单。访客在对账助手/订单机器人结果里点「提交人工审批」后，这里会出现待办。
        </div>
      ) : (
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr><th>提交时间</th><th>智能体</th><th>AI 摘要</th><th>状态</th><th>操作</th></tr>
            </thead>
            <tbody>
              {items.map(x => {
                const st = STATUS[x.status] || STATUS.pending;
                return (
                  <React.Fragment key={x.id}>
                    <tr>
                      <td className="muted" style={{ whiteSpace: 'nowrap' }}>{(x.created || '').replace('T', ' ')}</td>
                      <td><strong>{x.agent_name}</strong><div className="muted">{x.id}</div></td>
                      <td style={{ maxWidth: 320 }}>{x.summary}</td>
                      <td><span className={`status-pill ${st.cls}`}>{st.label}</span></td>
                      <td style={{ whiteSpace: 'nowrap' }}>
                        <button className="btn btn-ghost btn-sm" onClick={() => openDetail(x.id)}>
                          {openId === x.id ? '收起' : '详情'}
                        </button>{' '}
                        {x.status === 'pending' && (
                          <>
                            <button className="btn btn-sm" disabled={busy === x.id}
                                    onClick={() => decide(x, 'approve', '')}>
                              {busy === x.id ? '处理中…' : '批准'}
                            </button>{' '}
                            <button className="btn btn-ghost btn-sm" style={{ color: '#b91c1c' }}
                                    disabled={busy === x.id}
                                    onClick={() => { setNoteFor(x); setNote(''); }}>
                              驳回
                            </button>
                          </>
                        )}
                      </td>
                    </tr>
                    {openId === x.id && (
                      <tr>
                        <td colSpan={5} style={{ background: 'rgba(0,0,0,0.03)', padding: 12 }}>
                          {!detail ? <span className="muted">加载详情…</span> : (
                            <div style={{ fontSize: 13 }}>
                              <div style={{ marginBottom: 6 }}>
                                <strong>置信度：</strong>
                                {typeof detail.confidence === 'number'
                                  ? Math.round(detail.confidence * 100) + '%' : '—'}
                                {detail.note && <>　<strong>批注：</strong>{detail.note}</>}
                              </div>
                              <div style={{ marginBottom: 6 }}>
                                <strong>AI 结果：</strong>
                                <pre style={{ whiteSpace: 'pre-wrap', margin: '4px 0', fontSize: 12 }}>
                                  {JSON.stringify(detail.result, null, 2)}
                                </pre>
                              </div>
                              <div>
                                <strong>留痕轨迹：</strong>
                                {(detail.trail || []).map((t, i) => (
                                  <div key={i} style={{ margin: '2px 0 2px 12px' }}>
                                    {t.at} · {ACTION_LABEL[t.action] || t.action}
                                    {t.note ? ` · ${t.note}` : ''}
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {noteFor && (
        <div className="modal-backdrop" onClick={() => setNoteFor(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>驳回 {noteFor.id}</h3>
              <button className="icon-btn" onClick={() => setNoteFor(null)}>✕</button>
            </div>
            <div className="admin-form">
              <label>驳回理由（必填，将写入留痕）</label>
              <textarea rows={3} value={note} onChange={(e) => setNote(e.target.value)}
                        placeholder="例如：金额与发票不符，请核对后重新提交" />
              <div className="prd-actions" style={{ marginTop: 12 }}>
                <button className="btn" style={{ background: '#b91c1c', color: '#fff' }}
                        disabled={!note.trim() || busy === noteFor.id}
                        onClick={() => decide(noteFor, 'reject', note)}>
                  确认驳回
                </button>
                <button className="btn btn-ghost" onClick={() => setNoteFor(null)}>取消</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
