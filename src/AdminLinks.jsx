import React, { useState, useEffect, useCallback } from 'react';

const API_BASE = '/api';

async function readError(res) {
  const text = await res.text();
  try {
    const json = JSON.parse(text);
    if (json.error) return json.error;
  } catch {}
  return text || `请求失败（HTTP ${res.status}）`;
}

/* ===== 后台「友情链接」标签页：增删改 + 一键采集入库 ===== */
export default function AdminLinks({ token }) {
  const [links, setLinks] = useState([]);
  const [editing, setEditing] = useState(null); // null | {id?, name, url, desc}
  const [crawling, setCrawling] = useState(null);
  const [notice, setNotice] = useState(null);
  const [saving, setSaving] = useState(false);

  const fetchLinks = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/admin/links`, { headers: { Authorization: `Bearer ${token}` } });
      if (!res.ok) throw new Error(await readError(res));
      setLinks(await res.json());
    } catch (err) {
      setNotice({ ok: false, text: err?.message || '加载失败' });
    }
  }, [token]);

  useEffect(() => { fetchLinks(); }, [fetchLinks]);

  const save = async (e) => {
    e.preventDefault();
    if (saving) return;
    setSaving(true);
    setNotice(null);
    try {
      const res = await fetch(`${API_BASE}/admin/links`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(editing),
      });
      if (!res.ok) throw new Error(await readError(res));
      setEditing(null);
      await fetchLinks();
      setNotice({ ok: true, text: '已保存' });
    } catch (err) {
      setNotice({ ok: false, text: err?.message || '保存失败' });
    } finally {
      setSaving(false);
    }
  };

  const remove = async (id) => {
    if (!confirm('确定删除该链接吗？')) return;
    try {
      const res = await fetch(`${API_BASE}/admin/links/${id}`, { method: 'DELETE', headers: { Authorization: `Bearer ${token}` } });
      if (!res.ok) throw new Error(await readError(res));
      await fetchLinks();
    } catch (err) {
      setNotice({ ok: false, text: err?.message || '删除失败' });
    }
  };

  const crawl = async (link) => {
    if (crawling) return;
    setCrawling(link.id);
    setNotice(null);
    try {
      const res = await fetch(`${API_BASE}/admin/links/${link.id}/crawl`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || '采集失败');
      setNotice({ ok: true, text: data.message || '采集成功，已入库' });
    } catch (err) {
      setNotice({ ok: false, text: err?.message || '采集失败' });
    } finally {
      setCrawling(null);
    }
  };

  return (
    <div className="links-admin">
      <div className="admin-toolbar">
        <button className="btn btn-primary" onClick={() => setEditing({ name: '', url: '', desc: '' })}>
          ＋ 新增链接
        </button>
        <span className="muted links-admin-hint">链接展示在首页底部，访客可点击跳转；「采集」按钮可将该页面内容抓取入知识库。</span>
      </div>

      {notice && <div className={`kb-notice ${notice.ok ? 'ok' : 'err'}`}>{notice.text}</div>}

      {editing && (
        <form className="admin-form link-edit-form" onSubmit={save}>
          <label>站点名称</label>
          <input type="text" value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })}
            placeholder="如：工业和信息化部" required />
          <label>站点地址</label>
          <input type="url" value={editing.url} onChange={(e) => setEditing({ ...editing, url: e.target.value })}
            placeholder="https://…" required />
          <label>说明（可选，鼠标悬停展示）</label>
          <input type="text" value={editing.desc || ''} onChange={(e) => setEditing({ ...editing, desc: e.target.value })}
            placeholder="一句话介绍该站点" />
          <div className="modal-actions">
            <button type="button" className="btn btn-ghost" onClick={() => setEditing(null)}>取消</button>
            <button type="submit" className="btn btn-primary" disabled={saving}>{saving ? '保存中…' : '保存'}</button>
          </div>
        </form>
      )}

      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr><th>名称</th><th>地址</th><th>说明</th><th>操作</th></tr>
          </thead>
          <tbody>
            {links.map((l) => (
              <tr key={l.id}>
                <td><strong>{l.name}</strong></td>
                <td className="muted" style={{ maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  <a href={l.url} target="_blank" rel="noreferrer">{l.url}</a>
                </td>
                <td className="muted">{l.desc}</td>
                <td>
                  <button className="btn btn-ghost btn-sm" disabled={crawling === l.id} onClick={() => crawl(l)}>
                    {crawling === l.id ? '采集中…' : '采集入库'}
                  </button>
                  <button className="btn btn-ghost btn-sm" onClick={() => setEditing(l)}>编辑</button>
                  <button className="btn btn-danger btn-sm" onClick={() => remove(l.id)}>删除</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
