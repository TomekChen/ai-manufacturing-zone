import React, { useEffect, useState, useCallback } from 'react';
import { readError } from './api';

const API_BASE = '/api';

/* ===== 管理后台 · 网页抓单（A8 增强③） =====
   客户订单只在他们的门户网站里（无邮件无 API）时，配置来源 → 立即抓取 →
   订单机器人抽取 → 进「订单捕获」账本。抓取引擎自动选择：
   装了 Playwright 用真浏览器渲染，否则 requests 兜底（服务端渲染页可用）。 */
export default function AdminWebCapture({ token }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');
  const [msg, setMsg] = useState('');
  const [busy, setBusy] = useState('');
  const [form, setForm] = useState({ name: '', url: '' });
  const [lastResult, setLastResult] = useState(null);

  const load = useCallback(async () => {
    setLoading(true); setErr('');
    try {
      const res = await fetch(`${API_BASE}/admin/web-sources`, {
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

  const save = async () => {
    setBusy('save'); setErr(''); setMsg('');
    try {
      const res = await fetch(`${API_BASE}/admin/web-sources`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      if (!res.ok) throw new Error(await readError(res));
      setMsg(`来源「${form.name}」已保存`);
      setForm({ name: '', url: '' });
      load();
    } catch (e) {
      setErr(e?.message || '保存失败');
    } finally {
      setBusy('');
    }
  };

  const remove = async (s) => {
    if (!window.confirm(`删除来源「${s.name}」？（已抓取的捕获记录保留）`)) return;
    setBusy(s.id); setErr('');
    try {
      const res = await fetch(`${API_BASE}/admin/web-sources/${s.id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(await readError(res));
      load();
    } catch (e) {
      setErr(e?.message || '删除失败');
    } finally {
      setBusy('');
    }
  };

  const fetchNow = async (s) => {
    setBusy(s.id); setErr(''); setMsg(''); setLastResult(null);
    try {
      const res = await fetch(`${API_BASE}/admin/web-capture/fetch`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: s.id }),
      });
      const d = await res.json();
      if (!res.ok) throw new Error(d.error || '抓取失败');
      setLastResult(d.capture);
      setMsg(`「${s.name}」抓取完成（引擎：${d.capture.engine}），结果见下方，账本详情到「订单捕获」页签查看`);
      load();
    } catch (e) {
      setErr(e?.message || '抓取失败');
    } finally {
      setBusy('');
    }
  };

  if (loading) return <div className="muted" style={{ padding: 12 }}>加载中…</div>;

  return (
    <>
      <div className="admin-toolbar">
        <span className="muted">
          客户订单只在门户网站里时配一个来源抓取；引擎自动选 Playwright（JS 动态页）或 requests（静态页）。
          抓取结果进「订单捕获」账本统一处理。
        </span>
      </div>
      {msg && <div style={{ margin: '8px 12px', color: '#15803d', fontSize: 13 }}>{msg}</div>}
      {err && <div className="form-error" style={{ margin: '8px 12px' }}>{err}</div>}

      <div style={{ margin: '8px 12px', padding: '10px 12px', border: '1px solid #e5e7eb', borderRadius: 8 }}>
        <div style={{ fontWeight: 600, marginBottom: 8 }}>新增抓取来源</div>
        <input value={form.name} placeholder="来源名称，如：华阳客户门户"
               onChange={e => setForm({ ...form, name: e.target.value })}
               style={{ marginRight: 8, padding: '6px 8px', width: 200 }} />
        <input value={form.url} placeholder="https://portal.customer.com/orders"
               onChange={e => setForm({ ...form, url: e.target.value })}
               style={{ marginRight: 8, padding: '6px 8px', width: 320 }} />
        <button className="btn btn-primary btn-sm" disabled={!form.name.trim() || !form.url.trim() || busy === 'save'}
                onClick={save}>
          {busy === 'save' ? '保存中…' : '保存来源'}
        </button>
      </div>

      {items.length === 0 ? (
        <div className="muted" style={{ padding: 12 }}>还没有配置来源。新增一个客户门户地址开始抓单。</div>
      ) : (
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr><th>来源</th><th>地址</th><th>最近抓取</th><th>状态</th><th>操作</th></tr>
            </thead>
            <tbody>
              {items.map(s => (
                <tr key={s.id}>
                  <td><strong>{s.name}</strong></td>
                  <td className="muted" style={{ maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    <a href={s.url} target="_blank" rel="noreferrer">{s.url}</a>
                  </td>
                  <td className="muted" style={{ whiteSpace: 'nowrap' }}>{(s.last_fetch || '—').replace('T', ' ')}</td>
                  <td>{s.last_status === 'new' ? <span className="status-pill online">已捕获</span>
                        : s.last_status === 'skipped' ? <span className="status-pill offline">内容未变</span>
                        : s.last_status ? <span className="status-pill offline">{s.last_status}</span>
                        : <span className="muted">未抓取</span>}</td>
                  <td style={{ whiteSpace: 'nowrap' }}>
                    <button className="btn btn-sm" disabled={busy === s.id} onClick={() => fetchNow(s)}>
                      {busy === s.id ? '抓取中…' : '立即抓取'}
                    </button>{' '}
                    <button className="btn btn-ghost btn-sm" disabled={busy === s.id} onClick={() => remove(s)}>
                      删除
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {lastResult && (
        <div style={{ margin: '8px 12px', padding: '10px 12px', border: '1px solid #e5e7eb', borderRadius: 8 }}>
          <div style={{ fontWeight: 600, marginBottom: 6 }}>
            本次抓取：{lastResult.status === 'new' ? '✅ 捕获新订单建议' :
                       lastResult.status === 'skipped' ? '↩️ 内容未变化，跳过' : lastResult.status}
            {lastResult.engine && <span className="muted"> · 引擎 {lastResult.engine}</span>}
          </div>
          <pre style={{ fontSize: 12, whiteSpace: 'pre-wrap', margin: 0 }}>
            {JSON.stringify(lastResult.order || lastResult.note || {}, null, 2)}
          </pre>
        </div>
      )}
    </>
  );
}
