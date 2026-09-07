import React, { useEffect, useState, useCallback } from 'react';

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

/* ===== 管理后台 · 预约演示列表 =====
   GET /api/admin/demo/bookings（需管理员 token），后端按时间倒序返回，最多 200 条。 */
export default function AdminBookings({ token }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');

  const load = useCallback(async () => {
    setLoading(true); setErr('');
    try {
      const res = await fetch(`${API_BASE}/admin/demo/bookings`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(await readError(res));
      const d = await res.json();
      setItems(Array.isArray(d) ? d : (d.bookings || []));
    } catch (e) {
      setErr(e?.message || '加载失败');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { load(); }, [load]);

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
        <span className="muted">共 {items.length} 条 · 新的在前 · 后端最多保留 200 条</span>
      </div>
      {items.length === 0 ? (
        <div className="muted" style={{ padding: 12 }}>还没有预约记录。</div>
      ) : (
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr><th>时间</th><th>称呼</th><th>联系方式</th><th>想看项目</th><th>备注</th><th>邮件</th></tr>
            </thead>
            <tbody>
              {items.map(b => (
                <tr key={b.id}>
                  <td className="muted" style={{ whiteSpace: 'nowrap' }}>{(b.ts || '').replace('T', ' ')}</td>
                  <td><strong>{b.name}</strong></td>
                  <td>{b.contact}</td>
                  <td>{b.project || '—'}</td>
                  <td className="muted"
                      style={{ maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                      title={b.note}>{b.note || '—'}</td>
                  <td>
                    <span className={`status-pill ${b.notified ? 'online' : 'offline'}`}>
                      {b.notified ? '已通知' : '未发出'}
                    </span>
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
