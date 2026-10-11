import React, { useEffect, useState, useCallback } from 'react';
import { API_BASE, readError } from './api';


/* ===== 管理后台 · 订单捕获（A8：邮箱 IMAP 轮询 → 订单机器人抽取） =====
   上半：邮箱配置（口令只写不回显，留空保持原值）+ 测试连接 + 立即拉取；
   下半：捕获账本列表（新→旧），确认/忽略状态流转，抽取失败记录不丢可人工补录。 */
const STATUS_LABEL = {
  new: '待处理', confirmed: '已确认', ignored: '已忽略',
  error: '抽取失败', skipped: '无可抽取正文',
};

function StatusPill({ status }) {
  const cls = status === 'confirmed' ? 'online' : (status === 'error' ? 'offline' : '');
  return <span className={`status-pill ${cls}`}>{STATUS_LABEL[status] || status}</span>;
}

function OrderSummary({ cap }) {
  if (cap.status === 'error') {
    return <span className="muted">{cap.error || '抽取失败'}{cap.body_excerpt ? '（原文已存，可人工补录）' : ''}</span>;
  }
  if (cap.status === 'skipped') return <span className="muted">{cap.note}</span>;
  const o = cap.order || {};
  const prods = (o.products || []).map(p => `${p.name}${p.qty ? '×' + p.qty : ''}${p.unit || ''}`).join('、');
  return (
    <div style={{ fontSize: 13, lineHeight: 1.6 }}>
      <div><strong>{o.customer || '（客户未识别）'}</strong>
        {o.order_no && <span className="muted"> · {o.order_no}</span>}
        {o.delivery_date && <span> · 交期 {o.delivery_date}</span>}
      </div>
      <div className="muted">{prods || '（未抽取到产品明细）'}</div>
      {(o.missing || []).length > 0 && (
        <div style={{ color: '#b45309' }}>缺失字段：{o.missing.join('、')}</div>
      )}
    </div>
  );
}

export default function AdminOrderMail({ token }) {
  const [cfg, setCfg] = useState({ host: '', port: 993, user: '', folder: 'INBOX', ssl: true, enabled: false });
  const [password, setPassword] = useState('');
  const [passwordSet, setPasswordSet] = useState(false);
  const [status, setStatus] = useState(null);   // last_check / last_error / last_result
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [msg, setMsg] = useState('');
  const [err, setErr] = useState('');

  const H = useCallback(() => ({ 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }), [token]);

  const loadAll = useCallback(async () => {
    setLoading(true); setErr('');
    try {
      const [cfgRes, capRes] = await Promise.all([
        fetch(`${API_BASE}/admin/order-mail`, { headers: { Authorization: `Bearer ${token}` } }),
        fetch(`${API_BASE}/admin/order-mail/captures`, { headers: { Authorization: `Bearer ${token}` } }),
      ]);
      if (!cfgRes.ok) throw new Error(await readError(cfgRes));
      const d = await cfgRes.json();
      setCfg({ host: d.host || '', port: d.port || 993, user: d.user || '',
               folder: d.folder || 'INBOX', ssl: d.ssl !== false, enabled: !!d.enabled });
      setPasswordSet(!!d.password_set);
      setStatus(d);
      if (capRes.ok) setItems(await capRes.json());
    } catch (e) {
      setErr(e?.message || '加载失败');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { loadAll(); }, [loadAll]);

  const save = async () => {
    setBusy('save'); setErr(''); setMsg('');
    try {
      const res = await fetch(`${API_BASE}/admin/order-mail`, {
        method: 'POST', headers: H(),
        body: JSON.stringify({ ...cfg, password: password || undefined }),
      });
      if (!res.ok) throw new Error(await readError(res));
      const d = await res.json();
      setPasswordSet(!!d.password_set);
      setPassword('');
      setMsg('配置已保存' + (cfg.enabled ? '，轮询线程将在 5 分钟内开始巡检' : '（当前未启用自动轮询）'));
    } catch (e) { setErr(e?.message || '保存失败'); }
    finally { setBusy(''); }
  };

  const testConn = async () => {
    setBusy('test'); setErr(''); setMsg('');
    try {
      const res = await fetch(`${API_BASE}/admin/order-mail/test`, {
        method: 'POST', headers: H(),
        body: JSON.stringify({ ...cfg, password: password || undefined }),
      });
      const d = await res.json();
      if (d.ok) setMsg(`连接成功，文件夹「${cfg.folder || 'INBOX'}」共 ${d.count} 封邮件`);
      else setErr(d.error || '连接失败');
    } catch (e) { setErr(e?.message || '测试失败'); }
    finally { setBusy(''); }
  };

  const fetchNow = async () => {
    setBusy('fetch'); setErr(''); setMsg('');
    try {
      const res = await fetch(`${API_BASE}/admin/order-mail/fetch`, { method: 'POST', headers: H() });
      if (!res.ok) throw new Error(await readError(res));
      const d = await res.json();
      setMsg(`拉取完成：检查 ${d.checked} 封，新捕获 ${d.new} 条${d.errors ? `，失败 ${d.errors} 条（已记入账本）` : ''}`);
      await loadAll();
    } catch (e) { setErr(e?.message || '拉取失败'); }
    finally { setBusy(''); }
  };

  const setStatusOf = async (cap, s) => {
    setBusy(cap.id);
    try {
      const res = await fetch(`${API_BASE}/admin/order-mail/captures/${cap.id}`, {
        method: 'POST', headers: H(), body: JSON.stringify({ status: s }),
      });
      if (!res.ok) throw new Error(await readError(res));
      await loadAll();
    } catch (e) { setErr(e?.message || '操作失败'); }
    finally { setBusy(''); }
  };

  if (loading) return <div className="muted" style={{ padding: 12 }}>加载中…</div>;

  return (
    <>
      <div className="admin-form" style={{ maxWidth: 560 }}>
        <div className="admin-toolbar" style={{ paddingLeft: 0 }}>
          <span className="muted" style={{ fontSize: 13 }}>
            邮箱配置只保存在服务器 data/ 目录，口令不回显、不入 git。
          </span>
        </div>
        <label>IMAP 服务器</label>
        <input type="text" placeholder="例如 imap.exmail.qq.com" value={cfg.host}
               onChange={(e) => setCfg({ ...cfg, host: e.target.value })} />
        <div style={{ display: 'flex', gap: 12 }}>
          <div style={{ flex: 1 }}>
            <label>账号</label>
            <input type="text" placeholder="orders@example.com" value={cfg.user}
                   onChange={(e) => setCfg({ ...cfg, user: e.target.value })} />
          </div>
          <div style={{ width: 110 }}>
            <label>端口</label>
            <input type="number" value={cfg.port}
                   onChange={(e) => setCfg({ ...cfg, port: Number(e.target.value) || 993 })} />
          </div>
        </div>
        <label>密码 {passwordSet && <span className="muted" style={{ fontSize: 12 }}>（已设置，留空保持不变）</span>}</label>
        <input type="password" value={password} placeholder={passwordSet ? '••••••••' : '邮箱密码/授权码'}
               onChange={(e) => setPassword(e.target.value)} />
        <div style={{ display: 'flex', gap: 12 }}>
          <div style={{ flex: 1 }}>
            <label>文件夹</label>
            <input type="text" value={cfg.folder} onChange={(e) => setCfg({ ...cfg, folder: e.target.value })} />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, paddingTop: 26 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, margin: 0 }}>
              <input type="checkbox" checked={cfg.ssl} onChange={(e) => setCfg({ ...cfg, ssl: e.target.checked })} /> SSL
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, margin: 0 }}>
              <input type="checkbox" checked={cfg.enabled} onChange={(e) => setCfg({ ...cfg, enabled: e.target.checked })} /> 启用自动轮询（每 5 分钟）
            </label>
          </div>
        </div>
        <div className="admin-toolbar" style={{ paddingLeft: 0 }}>
          <button className="btn btn-primary" disabled={busy !== '' || !cfg.host || !cfg.user}
                  onClick={save}>{busy === 'save' ? '保存中…' : '保存配置'}</button>
          <button className="btn btn-ghost" disabled={busy !== '' || !cfg.host || !cfg.user}
                  onClick={testConn}>{busy === 'test' ? '测试中…' : '测试连接'}</button>
          <button className="btn btn-ghost" disabled={busy !== '' || !cfg.host || !cfg.user}
                  onClick={fetchNow}>{busy === 'fetch' ? '拉取中…' : '立即拉取'}</button>
        </div>
        {status?.last_check && (
          <div className="muted" style={{ fontSize: 12 }}>
            上次拉取：{status.last_check.replace('T', ' ')}
            {status.last_error && <span style={{ color: '#b91c1c' }}> · 上次错误：{status.last_error}</span>}
          </div>
        )}
        {msg && <div style={{ color: '#15803d', fontSize: 13 }}>{msg}</div>}
        {err && <div className="form-error">{err}</div>}
      </div>

      <div className="admin-toolbar" style={{ marginTop: 8 }}>
        <button className="btn btn-ghost btn-sm" onClick={loadAll}>刷新</button>
        <span className="muted">共 {items.length} 条捕获记录 · 新的在前 · 后端最多保留 500 条</span>
      </div>
      {items.length === 0 ? (
        <div className="muted" style={{ padding: 12 }}>
          还没有捕获记录。配置邮箱后点「立即拉取」，新订单邮件会自动抽取成结构化工单出现在这里。
        </div>
      ) : (
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr><th>时间</th><th>发件人 / 主题</th><th>抽取结果</th><th>置信度</th><th>操作</th></tr>
            </thead>
            <tbody>
              {items.map(cap => (
                <tr key={cap.id}>
                  <td className="muted" style={{ whiteSpace: 'nowrap' }}>{(cap.ts || '').replace('T', ' ')}</td>
                  <td style={{ maxWidth: 220 }}>
                    <div style={{ fontSize: 13 }}>{cap.from}</div>
                    <div className="muted" style={{ fontSize: 12, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {cap.subject}
                    </div>
                  </td>
                  <td style={{ maxWidth: 320 }}><OrderSummary cap={cap} /></td>
                  <td>
                    <StatusPill status={cap.status} />
                    {typeof cap.confidence === 'number' && cap.status === 'new' && (
                      <div className="muted" style={{ fontSize: 12 }}>{Math.round(cap.confidence * 100)}%</div>
                    )}
                  </td>
                  <td style={{ whiteSpace: 'nowrap' }}>
                    {cap.status !== 'confirmed' && (
                      <button className="btn btn-sm" disabled={busy === cap.id} onClick={() => setStatusOf(cap, 'confirmed')}>确认</button>
                    )}{' '}
                    {cap.status !== 'ignored' && (
                      <button className="btn btn-ghost btn-sm" disabled={busy === cap.id} onClick={() => setStatusOf(cap, 'ignored')}>忽略</button>
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
