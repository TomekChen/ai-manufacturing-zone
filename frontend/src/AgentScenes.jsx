import React, { useState, useCallback } from 'react';
import { readError } from './api';
import ShowcasePicker, { DemoSlot } from './Showcase';

/* ===== 场景分镜师 · 公开在线体验弹窗（第五个上线智能体） =====
   品牌/行业输入 → 分镜脚本（场景顺序/内容/静帧提示词/镜头衔接）。
   ui=scenes 的智能体走本弹窗（main.jsx 按 agent.ui 分流）；
   样式复用 prd-* 体系，不新增 CSS。
   A12：输入框上方「先看示例」，示例脚本复用本弹窗自己的镜头列表渲染。
   A13：示例改在独立浮层里看（点「看示例」当场出结果，不用往下滚）；
        渲染 JSX 只有一份，由 Showcase 的 DemoSlot 决定放浮层还是放原位。 */
export default function AgentScenes({ agent, onClose }) {
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState('');
  const [result, setResult] = useState(null);
  const [demo, setDemo] = useState(null);
  const [fillTip, setFillTip] = useState('');

  const endpoint = (agent && agent.endpoint) || '/api/agents/scene-director/run';

  // A12/A13 示例：快照只喂给下面的镜头列表渲染，不覆盖客户自己跑过的结果
  const showDemo = (row) => { setErr(''); setFillTip(''); setDemo(row); };
  const useDemo = (row) => {
    setText(String((row.input || {}).text || ''));
    setFillTip('示例原文已填入，点「生成分镜脚本」即可自己跑一遍');
  };

  const run = useCallback(async () => {
    const t = text.trim();
    if (!t || loading) return;
    setErr(''); setLoading(true); setResult(null); setDemo(null); setFillTip('');
    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: t }),
      });
      if (!res.ok) { setErr(await readError(res)); return; }
      const data = await res.json();
      const inner = data.result && typeof data.result === 'object' ? data.result : data;
      setResult({ ...inner, confidence: data.confidence });
    } catch (e) {
      setErr('网络错误：' + (e.message || e));
    } finally {
      setLoading(false);
    }
  }, [text, loading, endpoint]);

  const plan = (demo ? demo.output : result) || {};
  const confidence = demo ? demo.confidence : result?.confidence;
  const scenes = Array.isArray(plan.scenes) ? plan.scenes : [];

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal modal-xl agent-prd-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>{agent?.emoji || '🎬'} {agent?.name || '场景分镜师'} · 在线体验</h3>
          <button className="icon-btn" onClick={onClose} aria-label="关闭">✕</button>
        </div>
        <div className="agent-prd-body">
          <div className="prd-intro">
            <div className="prd-intro-sub">
              {agent?.desc || '给出品牌名和想展示的行业内容，自动扩写成 4-8 个首尾衔接的滚动漫游分镜脚本。'}
            </div>
          </div>

          <div className="prd-form">
            <ShowcasePicker agentId={agent?.id} active={demo?.label} onShow={showDemo} onUse={useDemo} />
            <div className="prd-field">
              <label>品牌 / 行业 / 想展示的内容 <span className="prd-req">*</span></label>
              <textarea value={text} maxLength={2000} rows={5}
                        placeholder={'例如：\n"华阳精工——汽车零部件精密制造企业，展示从研发设计、智能产线、AI 质检到仓储物流的滚动漫游"'}
                        onChange={e => setText(e.target.value)}
                        onKeyDown={e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) run(); }} />
              <div className="prd-count">{text.length}/2000</div>
            </div>
            <div className="prd-actions">
              <button className="btn btn-primary" onClick={run} disabled={!text.trim() || loading}>
                {loading ? '正在生成分镜脚本…' : '生成分镜脚本'}
              </button>
              <span className="agent-kb-tip">Ctrl + Enter 快速提交</span>
            </div>
            {fillTip && <div style={{ margin: '8px 0', fontSize: 13, color: '#0369a1' }}>{fillTip}</div>}
            {loading && <div className="prd-loading"><span className="prd-spinner" /> AI 正在编排镜头与场景，请稍候…</div>}
            {err && <div className="prd-err">{err}</div>}
          </div>

          {(demo || result) && (
            <DemoSlot demo={demo} title={agent?.name || '场景分镜师'}
                      onClose={() => setDemo(null)}
                      onUse={() => { useDemo(demo); setDemo(null); }}>
            <div className="prd-result">
              <div className="prd-result-bar">
                <span className={`prd-badge ${scenes.length >= 4 && scenes.length <= 8 ? 'ok' : 'muted'}`}>
                  {scenes.length} 个场景
                </span>
                <span className="prd-badge muted">
                  置信度：{typeof confidence === 'number' ? Math.round(confidence * 100) + '%' : '—'}
                </span>
              </div>
              {plan.brand && (
                <div style={{ margin: '10px 0', fontSize: 15, fontWeight: 600 }}>
                  {plan.brand} · 滚动漫游分镜
                </div>
              )}
              {plan.style && (
                <div style={{ margin: '8px 0', fontSize: 13, opacity: 0.75 }}>美术方向：{plan.style}</div>
              )}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 12 }}>
                {scenes.map((s, i) => (
                  <div key={i} style={{ border: '1px solid var(--border, #e5e7eb)', borderRadius: 10, padding: '10px 14px' }}>
                    <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
                      <span style={{ fontSize: 18, fontWeight: 700, opacity: 0.35 }}>{s.no || String(i + 1).padStart(2, '0')}</span>
                      <span style={{ fontWeight: 600 }}>{s.title}</span>
                    </div>
                    {s.desc && <div style={{ margin: '4px 0 0 2px', fontSize: 14 }}>{s.desc}</div>}
                    {s.camera_move && (
                      <div style={{ margin: '6px 0 0 2px', fontSize: 13, color: '#2563eb' }}>🎥 {s.camera_move}</div>
                    )}
                    {s.still_prompt && (
                      <div style={{ margin: '6px 0 0 2px', fontSize: 12, opacity: 0.6, wordBreak: 'break-all' }}>
                        静帧提示词：{s.still_prompt}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
            </DemoSlot>
          )}
        </div>
      </div>
    </div>
  );
}
