import React, { useState, useCallback } from 'react';
import renderMarkdown from './markdown';

/* ===== 知识管家 · 公开在线体验弹窗（A3 第二个上线智能体） =====
   经注册表 endpoint 调用，与首页「知识问答」区同一条后端链路。
   ui=qa 的智能体走本弹窗（main.jsx 按 agent.ui 分流）。
   说明文字 ≥14px，输入区加大。 */
const SUGGESTIONS = [
  '知识库里有哪些资料？',
  'AI 质检能解决什么问题？',
  '制造企业上 MES 系统一般分几步？',
];

async function readError(res) {
  const text = await res.text();
  try {
    const json = JSON.parse(text);
    if (json.error) return json.error;
    if (json.message) return json.message;
  } catch {}
  return text || `请求失败（HTTP ${res.status}）`;
}

export default function AgentKB({ agent, onClose }) {
  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState('');
  const [result, setResult] = useState(null);

  // 端点来自注册表；老 agent 对象缺 endpoint 时回退
  const endpoint = (agent && agent.endpoint) || '/api/agents/kb-assistant/run';

  const ask = useCallback(async (q) => {
    const text = (q ?? question).trim();
    if (!text || loading) return;
    setErr(''); setLoading(true); setResult(null);
    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: text }),
      });
      if (!res.ok) { setErr(await readError(res)); return; }
      const data = await res.json();
      // A2 统一契约 {ok, agent_id, result, refs, confidence}：明细在 result 里，
      // confidence 在外层，合进来方便展示
      const inner = data.result && typeof data.result === 'object' ? data.result : data;
      setResult({ ...inner, confidence: data.confidence !== undefined ? data.confidence : inner.confidence });
    } catch (e) {
      setErr('网络错误：' + (e.message || e));
    } finally {
      setLoading(false);
    }
  }, [question, loading, endpoint]);

  const sources = (result?.sources) || [];

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal modal-xl agent-prd-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>{agent?.emoji || '📚'} {agent?.name || '知识管家'} · 在线体验</h3>
          <button className="icon-btn" onClick={onClose} aria-label="关闭">✕</button>
        </div>
        <div className="agent-prd-body">
          <div className="prd-intro">
            <div className="prd-intro-sub">
              {agent?.desc || '基于本站知识库的制造业数字化问答，回答附引用出处。'}
            </div>
          </div>

          <div className="prd-form">
            <div className="prd-field">
              <label>您的问题 <span className="prd-req">*</span></label>
              <textarea value={question} maxLength={500} rows={3}
                        placeholder="例如：预测性维护是怎么工作的？"
                        onChange={e => setQuestion(e.target.value)}
                        onKeyDown={e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) ask(); }} />
              <div className="prd-count">{question.length}/500</div>
            </div>

            <div className="agent-kb-suggestions">
              {SUGGESTIONS.map(s => (
                <button key={s} type="button" className="qa-suggestion"
                        onClick={() => { setQuestion(s); ask(s); }}>{s}</button>
              ))}
            </div>

            <div className="prd-actions">
              <button className="btn btn-primary" onClick={() => ask()}
                      disabled={!question.trim() || loading}>
                {loading ? '正在检索知识库…' : '提问'}
              </button>
              <span className="agent-kb-tip">Ctrl + Enter 快速提交</span>
            </div>
            {loading && <div className="prd-loading"><span className="prd-spinner" /> 正在检索知识库并生成回答，请稍候…</div>}
            {err && <div className="prd-err">{err}</div>}
          </div>

          {result && (
            <div className="prd-result">
              <div className="prd-result-bar">
                <span className={`prd-badge ${sources.length > 0 ? 'ok' : 'muted'}`}>
                  {sources.length > 0 ? `引用知识库 ${sources.length} 条` : '未命中知识库（仅供参考）'}
                </span>
                <span className="prd-badge muted">
                  置信度：{((c) => (typeof c === 'number' ? Math.round(c * 100) + '%' : '—'))(result.confidence)}
                </span>
              </div>
              {sources.length > 0 && (
                <div className="qa-sources agent-kb-sources">
                  <div className="qa-sources-title">参考来源</div>
                  {sources.map((s, j) => (
                    <div className="qa-source" key={j}>
                      <span className="qa-source-num">{j + 1}</span>
                      {s.url
                        ? <a href={s.url} target="_blank" rel="noreferrer" className="qa-source-name" title={s.snippet || s.title}>{s.title || s.url}</a>
                        : <span className="qa-source-name" title={s.snippet || s.title}>{s.title}</span>}
                    </div>
                  ))}
                </div>
              )}
              <div className="agent-kb-answer qa-answer-content"
                   dangerouslySetInnerHTML={{ __html: renderMarkdown(result.answer || '') }} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
