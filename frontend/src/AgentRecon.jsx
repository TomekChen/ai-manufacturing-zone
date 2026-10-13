import React, { useState, useCallback } from 'react';
import { readError } from './api';

/* ===== 对账助手 · 公开在线体验弹窗（A9 第四个上线智能体） =====
   粘贴银行流水（必填）+ 应收应付台账（可选）→ 后端逐笔比对：
   完全匹配 / 疑似匹配（附核对要点）/ 未达账项 / 建议分录。
   ui=recon 的智能体走本弹窗（main.jsx 按 agent.ui 分流）；
   样式复用 prd-* 体系，不新增 CSS。 */

const Section = ({ title, children }) => (
  <div className="prd-field">
    <label>{title}</label>
    {children}
  </div>
);

const PairTable = ({ rows, columns, keyField }) => (
  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
    <thead>
      <tr>
        {columns.map(h => (
          <th key={h} style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: '6px 8px' }}>{h}</th>
        ))}
      </tr>
    </thead>
    <tbody>
      {rows.map((r, i) => (
        <tr key={i}>
          {keyField.map((k, j) => (
            <td key={j} style={{ borderBottom: '1px solid #eee', padding: '6px 8px' }}>{r[k] || '—'}</td>
          ))}
        </tr>
      ))}
    </tbody>
  </table>
);

export default function AgentRecon({ agent, onClose }) {
  const [statement, setStatement] = useState('');
  const [ledger, setLedger] = useState('');
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState('');
  const [result, setResult] = useState(null);

  const endpoint = (agent && agent.endpoint) || '/api/agents/reconciler/run';

  const run = useCallback(async () => {
    const s = statement.trim();
    if (!s || loading) return;
    setErr(''); setLoading(true); setResult(null);
    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ statement: s, ledger: ledger.trim() }),
      });
      if (!res.ok) { setErr(await readError(res)); return; }
      const data = await res.json();
      // A2 统一契约 {ok, agent_id, result, refs, confidence}：明细在 result 里，confidence 在外层，合进来展示
      const inner = data.result && typeof data.result === 'object' ? data.result : data;
      setResult({ ...inner, confidence: data.confidence !== undefined ? data.confidence : inner.confidence });
    } catch (e) {
      setErr('网络错误：' + (e.message || e));
    } finally {
      setLoading(false);
    }
  }, [statement, ledger, loading, endpoint]);

  const r = result || {};
  const matched = r.matched || [];
  const suspected = r.suspected || [];
  const unmatchedBank = r.unmatched_bank || [];
  const unmatchedLedger = r.unmatched_ledger || [];
  const suggestions = r.suggestions || [];
  const summary = r.summary || {};

  const confidenceBadge = typeof result?.confidence === 'number'
    ? Math.round(result.confidence * 100) + '%'
    : '—';

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal modal-xl agent-prd-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>{agent?.emoji || '🧮'} {agent?.name || '对账助手'} · 在线体验</h3>
          <button className="icon-btn" onClick={onClose} aria-label="关闭">✕</button>
        </div>
        <div className="agent-prd-body">
          <div className="prd-intro">
            <div className="prd-intro-sub">
              {agent?.desc || '把银行流水和台账粘贴进来，自动逐笔比对，差异不漏一笔。'}
            </div>
          </div>

          <div className="prd-form">
            <div className="prd-field">
              <label>银行流水 <span className="prd-req">*</span></label>
              <textarea value={statement} maxLength={12000} rows={6}
                        placeholder={'例如粘贴网银导出的流水：\n"2026-10-08 收 华阳汽车零部件 50,000.00 附言：PO-2026-1001 货款\n2026-10-09 付 苏州钢材贸易 32,100.00 附言：原材料款"'}
                        onChange={e => setStatement(e.target.value)}
                        onKeyDown={e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) run(); }} />
              <div className="prd-count">{statement.length}/12000</div>
            </div>
            <div className="prd-field">
              <label>应收应付台账（可选，没有则只做流水侧归类）</label>
              <textarea value={ledger} maxLength={8000} rows={4}
                        placeholder={'例如：\n"应收 华阳汽车零部件 50,000 单号 PO-2026-1001，10月8日到期\n应付 苏州钢材贸易 32,100 采购单 CG-0930，账期30天"'}
                        onChange={e => setLedger(e.target.value)} />
              <div className="prd-count">{ledger.length}/8000</div>
            </div>
            <div className="prd-actions">
              <button className="btn btn-primary" onClick={run} disabled={!statement.trim() || loading}>
                {loading ? '正在逐笔核对…' : '开始对账'}
              </button>
              <span className="agent-kb-tip">Ctrl + Enter 快速提交</span>
            </div>
            {loading && <div className="prd-loading"><span className="prd-spinner" /> AI 正在逐笔比对流水与台账，请稍候…</div>}
            {err && <div className="prd-err">{err}</div>}
          </div>

          {result && (
            <div className="prd-result">
              <div className="prd-result-bar">
                <span className={`prd-badge ${unmatchedBank.length + unmatchedLedger.length === 0 ? 'ok' : 'muted'}`}>
                  {unmatchedBank.length + unmatchedLedger.length === 0
                    ? '双边平账，无未达项'
                    : `未达项 ${unmatchedBank.length + unmatchedLedger.length} 笔`}
                </span>
                <span className="prd-badge muted">
                  置信度：{confidenceBadge}
                </span>
              </div>
              {(summary.matched_count !== undefined || matched.length > 0) && (
                <div className="prd-sources">
                  完全匹配 {summary.matched_count ?? matched.length} 笔 · 疑似 {summary.suspected_count ?? suspected.length} 笔 · 未达 {summary.unmatched_count ?? (unmatchedBank.length + unmatchedLedger.length)} 笔
                </div>
              )}

              {matched.length > 0 && (
                <Section title={`完全匹配（${matched.length} 笔）`}>
                  <PairTable rows={matched} columns={['台账条目', '流水条目', '金额', '匹配依据']}
                             keyField={['our', 'bank', 'amount', 'basis']} />
                </Section>
              )}

              {suspected.length > 0 && (
                <Section title={`疑似匹配（${suspected.length} 笔）· 请人工确认后再入账`}>
                  <PairTable rows={suspected} columns={['台账条目', '流水条目', '金额', '疑似原因', '核对要点']}
                             keyField={['our', 'bank', 'amount', 'reason', 'confirm_hint']} />
                </Section>
              )}

              {unmatchedBank.length > 0 && (
                <Section title={`银行有、台账无（${unmatchedBank.length} 笔）`}>
                  <div style={{ fontSize: 14 }}>
                    {unmatchedBank.map((x, i) => <div key={i} style={{ color: '#b45309' }}>• {x}</div>)}
                  </div>
                </Section>
              )}

              {unmatchedLedger.length > 0 && (
                <Section title={`台账有、银行无（${unmatchedLedger.length} 笔）`}>
                  <div style={{ fontSize: 14 }}>
                    {unmatchedLedger.map((x, i) => <div key={i} style={{ color: '#b45309' }}>• {x}</div>)}
                  </div>
                </Section>
              )}

              {suggestions.length > 0 && (
                <Section title="建议分录（AI 建议，入账前请财务复核）">
                  <div style={{ fontSize: 14 }}>
                    {suggestions.map((x, i) => <div key={i}>• {x}</div>)}
                  </div>
                </Section>
              )}

              {r.notes && (
                <Section title="其他提醒">
                  <div style={{ fontSize: 14 }}>{r.notes}</div>
                </Section>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
