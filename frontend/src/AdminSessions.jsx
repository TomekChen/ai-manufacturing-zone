import React, { useEffect, useState, useCallback } from 'react';
import { readError } from './api';

const API_BASE = '/api';

/* 分享访问图表（小项：统计图表化）：最近 14 天迷你柱状图 + 热门会话 Top3，纯 SVG 零依赖 */
function ShareStatsChart({ stats }) {
  const days = (stats.days || []).slice(-14);
  const max = Math.max(1, ...days.map(d => d.views));
  const W = 420, H = 80, BW = W / Math.max(days.length, 1);
  const top = (stats.top || []).slice(0, 3);
  return (
    <div style={{ margin: '8px 12px 4px', padding: '10px 12px', border: '1px solid #e5e7eb', borderRadius: 8, display: 'flex', gap: 20, flexWrap: 'wrap', alignItems: 'center' }}>
      <div>
        <div className="muted" style={{ fontSize: 12, marginBottom: 4 }}>分享页访问 · 最近 14 天（共 {(stats.days || []).reduce((a, d) => a + d.views, 0)} 次/30天）</div>
        <svg width={W} height={H} role="img" aria-label="分享访问柱状图">
          {days.map((d, i) => {
            const h = Math.round((d.views / max) * (H - 18));
            return (
              <g key={d.date}>
                <rect x={i * BW + 2} y={H - h - 12} width={BW - 4} height={Math.max(h, d.views ? 2 : 0)}
                      fill="#2563eb" opacity="0.75" rx="2"><title>{`${d.date}：${d.views} 次`}</title></rect>
                {(i % 3 === 0 || i === days.length - 1) &&
                  <text x={i * BW + BW / 2} y={H - 2} fontSize="8" textAnchor="middle" fill="#9ca3af">{d.date.slice(5)}</text>}
              </g>
            );
          })}
        </svg>
      </div>
      {top.length > 0 && (
        <div style={{ fontSize: 12 }}>
          <div className="muted" style={{ marginBottom: 4 }}>最热方案</div>
          {top.map(t => (
            <div key={t.sid} style={{ marginBottom: 2 }}>
              🔥 {t.title.length > 16 ? t.title.slice(0, 16) + '…' : t.title} · {t.views} 次
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


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
  const [stats, setStats] = useState(null);

  const load = useCallback(async () => {
    setLoading(true); setErr('');
    try {
      const res = await fetch(`${API_BASE}/admin/prd-sessions`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(await readError(res));
      const d = await res.json();
      setItems(Array.isArray(d) ? d : (d.sessions || []));
      const sres = await fetch(`${API_BASE}/admin/share-stats`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (sres.ok) setStats(await sres.json());
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

  const remove = async (s) => {
    if (!window.confirm(`确定删除会话「${s.title}」？分享页将同时失效，不可恢复。`)) return;
    setBusy(s.id); setErr(''); setMsg('');
    try {
      const res = await fetch(`${API_BASE}/admin/prd-sessions/${s.id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(await readError(res));
      setMsg(`已删除「${s.title}」`);
      await load();
    } catch (e) {
      setErr(e?.message || '删除失败');
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
      {stats && stats.days && <ShareStatsChart stats={stats} />}
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
              <tr><th>最近更新</th><th>客户会话</th><th>创建时间</th><th>版本数</th><th>分享访问</th><th>操作</th></tr>
            </thead>
            <tbody>
              {items.map(s => (
                <tr key={s.id}>
                  <td className="muted" style={{ whiteSpace: 'nowrap' }}>{(s.updated || '').replace('T', ' ')}</td>
                  <td><strong>{s.title}</strong></td>
                  <td className="muted" style={{ whiteSpace: 'nowrap' }}>{(s.created || '').replace('T', ' ')}</td>
                  <td>
                    <span className="status-pill online">v1–v{s.version_count}</span>
                    {s.expired && <span className="status-pill offline" style={{ marginLeft: 6 }}>分享已过期</span>}
                  </td>
                  <td className="muted" style={{ whiteSpace: 'nowrap' }}>
                    {s.share_views || 0} 次{(s.last_viewed || '') && ` · ${(s.last_viewed || '').replace('T', ' ')}`}
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
                    )}{' '}
                    <button className="btn btn-ghost btn-sm" disabled={busy === s.id}
                            style={{ color: '#b91c1c' }} onClick={() => remove(s)}>
                      删除
                    </button>
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
