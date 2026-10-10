import React, { useState, useCallback } from 'react';
import { readError } from './api';

/* ===== 订单机器人 · 公开在线体验弹窗（A7 第三个上线智能体） =====
   粘贴订单原文（邮件/网页询盘/聊天记录）→ 后端抽成结构化工单。
   ui=order 的智能体走本弹窗（main.jsx 按 agent.ui 分流）；
   样式复用 prd-* 体系，不新增 CSS。 */
export default function AgentOrder({ agent, onClose }) {
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState('');
  const [result, setResult] = useState(null);

  const endpoint = (agent && agent.endpoint) || '/api/agents/order-catcher/run';

  const extract = useCallback(async () => {
    const t = text.trim();
    if (!t || loading) return;
    setErr(''); setLoading(true); setResult(null);
    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: t }),
      });
      if (!res.ok) { setErr(await readError(res)); return; }
      const data = await res.json();
      setResult(data.result && typeof data.result === 'object' ? data.result : data);
    } catch (e) {
      setErr('网络错误：' + (e.message || e));
    } finally {
      setLoading(false);
    }
  }, [text, loading, endpoint]);

  const order = result || {};
  const products = order.products || [];
  const missing = order.missing || [];
  const fieldRow = (label, value) => (
    <div className="prd-field" style={{ marginBottom: 8 }}>
      <label style={{ marginBottom: 2 }}>{label}</label>
      <div style={{ fontSize: 14 }}>{value || <span style={{ opacity: 0.5 }}>（未提供）</span>}</div>
    </div>
  );

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal modal-xl agent-prd-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>{agent?.emoji || '📨'} {agent?.name || '订单机器人'} · 在线体验</h3>
          <button className="icon-btn" onClick={onClose} aria-label="关闭">✕</button>
        </div>
        <div className="agent-prd-body">
          <div className="prd-intro">
            <div className="prd-intro-sub">
              {agent?.desc || '把客户邮件、网页询盘、聊天记录里的订单原文粘贴进来，自动抽取成结构化工单。'}
            </div>
          </div>

          <div className="prd-form">
            <div className="prd-field">
              <label>订单原文 <span className="prd-req">*</span></label>
              <textarea value={text} maxLength={12000} rows={7}
                        placeholder={'例如粘贴一封客户订单邮件：\n"李经理 138xxxx8888：我司（华阳汽车零部件）需订购 304 不锈钢法兰盘 DN50 带颈对焊 2000 件，12 月 20 日前交货到苏州仓库，木箱包装……"'}
                        onChange={e => setText(e.target.value)}
                        onKeyDown={e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) extract(); }} />
              <div className="prd-count">{text.length}/12000</div>
            </div>
            <div className="prd-actions">
              <button className="btn btn-primary" onClick={extract} disabled={!text.trim() || loading}>
                {loading ? '正在抽取工单…' : '抽取工单'}
              </button>
              <span className="agent-kb-tip">Ctrl + Enter 快速提交</span>
            </div>
            {loading && <div className="prd-loading"><span className="prd-spinner" /> AI 正在解析订单原文，请稍候…</div>}
            {err && <div className="prd-err">{err}</div>}
          </div>

          {result && (
            <div className="prd-result">
              <div className="prd-result-bar">
                <span className={`prd-badge ${missing.length === 0 ? 'ok' : 'muted'}`}>
                  {missing.length === 0 ? '关键字段齐全' : `缺失字段 ${missing.length} 项`}
                </span>
                <span className="prd-badge muted">
                  置信度：{typeof result.confidence === 'number' ? Math.round(result.confidence * 100) + '%' : '—'}
                </span>
              </div>
              {missing.length > 0 && (
                <div className="prd-sources" style={{ color: '#b45309' }}>
                  ⚠️ 以下信息原文未提供，建议回询客户以免漏单：
                  {missing.map((m, i) => <span key={i} className="prd-src">{m}</span>)}
                </div>
              )}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 24px', margin: '12px 0' }}>
                {fieldRow('订单号', order.order_no)}
                {fieldRow('客户', order.customer)}
                {fieldRow('联系人/方式', order.contact)}
                {fieldRow('交货日期', order.delivery_date)}
              </div>
              <div className="prd-field">
                <label>产品明细（{products.length} 项）</label>
                {products.length > 0 ? (
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
                    <thead>
                      <tr>
                        {['品名', '规格', '数量', '单位'].map(h => (
                          <th key={h} style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: '6px 8px' }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {products.map((p, i) => (
                        <tr key={i}>
                          {[p.name, p.spec, p.qty, p.unit].map((v, j) => (
                            <td key={j} style={{ borderBottom: '1px solid #eee', padding: '6px 8px' }}>{v || '—'}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : <div style={{ opacity: 0.5, fontSize: 14 }}>未识别到产品条目</div>}
              </div>
              {order.notes && (
                <div className="prd-field">
                  <label>备注</label>
                  <div style={{ fontSize: 14 }}>{order.notes}</div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
