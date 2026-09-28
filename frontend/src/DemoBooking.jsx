import React, { useState } from 'react';

/* ===== 预约演示弹窗（公开接口） =====
   项目卡显示「待演示」（服务器为节省资源未保持容器常驻）时提供预约入口：
   提交后后端立即发邮件通知管理员（notify.send_email），并落盘 data/demo_bookings.json。
   按 IP 限流（每 IP 每小时 3 次）。说明文字 ≥14px，输入区加大。 */
export default function DemoBooking({ projects = [], preselect = '', onClose }) {
  const [name, setName] = useState('');
  const [contact, setContact] = useState('');
  const [project, setProject] = useState(preselect || '');
  const [note, setNote] = useState('');
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState('');
  const [done, setDone] = useState(null); // {ok, notified, message}

  const canSubmit = name.trim() && contact.trim().length >= 5 && !loading;

  const submit = async (e) => {
    e.preventDefault();
    setErr(''); setLoading(true);
    try {
      const res = await fetch('/api/demo/booking', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: name.trim(),
          contact: contact.trim(),
          project: project.trim(),
          note: note.trim(),
        }),
      });
      const text = await res.text();
      let data = {};
      try { data = JSON.parse(text); } catch {}
      if (!res.ok) {
        setErr(data.error || data.message || `提交失败（HTTP ${res.status}）`);
        return;
      }
      setDone(data);
    } catch (e2) {
      setErr('网络错误：' + (e2.message || e2));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>📅 预约演示</h3>
          <button className="icon-btn" onClick={onClose} aria-label="关闭">✕</button>
        </div>
        {done ? (
          <div className="booking-done">
            <div className="booking-done-icon">✅</div>
            <div className="booking-done-title">预约已提交</div>
            <div className="booking-done-sub">
              {done.notified
                ? '我们已同步收到邮件通知，会尽快与您联系。'
                : '我们已记录您的预约，会尽快与您联系。'}
            </div>
            <button className="btn btn-primary" onClick={onClose}>好的</button>
          </div>
        ) : (
          <form className="admin-form booking-form" onSubmit={submit}>
            <div className="booking-intro">
              该项目当前处于<b>待演示</b>状态（为节省服务器资源未保持常驻）。
              留下联系方式，我们启动环境后会第一时间与您约定在线演示时间。
            </div>
            <label>怎么称呼您 <span className="prd-req">*</span></label>
            <input value={name} maxLength={40} required
                   placeholder="如：王经理"
                   onChange={e => setName(e.target.value)} />
            <label>联系方式 <span className="prd-req">*</span></label>
            <input value={contact} maxLength={80} required
                   placeholder="手机号 / 微信号 / 邮箱，方便联系到您"
                   onChange={e => setContact(e.target.value)} />
            <div className="booking-hint">至少 5 个字符，请确保能联系到您</div>
            <label>想看的项目 <span className="prd-opt">（选填）</span></label>
            <select value={project} onChange={e => setProject(e.target.value)}>
              <option value="">暂不确定，想整体了解一下</option>
              {projects.map((p, i) => (
                <option key={p.id || i} value={p.name}>{p.name}</option>
              ))}
            </select>
            <label>想了解什么 <span className="prd-opt">（选填）</span></label>
            <textarea value={note} maxLength={500} rows={3}
                      placeholder="例如：想看预测性维护的完整流程；周三下午方便。"
                      onChange={e => setNote(e.target.value)} />
            {err && <div className="form-error">{err}</div>}
            <div className="modal-actions">
              <button type="button" className="btn btn-ghost" onClick={onClose} disabled={loading}>取消</button>
              <button type="submit" className="btn btn-primary" disabled={!canSubmit}>
                {loading ? '提交中…' : '提交预约'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
