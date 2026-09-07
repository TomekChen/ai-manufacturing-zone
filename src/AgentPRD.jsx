import React, { useState, useCallback } from 'react';
import { MarkdownView } from './AdminPRD';

async function readError(res) {
  const text = await res.text();
  try {
    const json = JSON.parse(text);
    if (json.error) return json.error;
    if (json.message) return json.message;
  } catch {}
  return text || `请求失败（HTTP ${res.status}）`;
}

/* ===== 售前方案师 · 公开在线体验弹窗（A1 曳光弹，A2 接入注册表） =====
   与后台版 AdminPRD 同一引擎；端点取自智能体注册表（agent.endpoint），
   无需管理员登录，按 IP 限流（每 IP 每小时 5 次）。说明文字 ≥14px，输入区加大。 */
export default function AgentPRD({ agent, onClose }) {
  const [company, setCompany] = useState('');
  const [industry, setIndustry] = useState('');
  const [business, setBusiness] = useState('');
  const [mode, setMode] = useState('guide');
  const [raw, setRaw] = useState('');
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState('');
  const [result, setResult] = useState(null);

  // A2：端点来自注册表，而非硬编码；老 agent 对象缺 endpoint 时回退
  const endpoint = (agent && agent.endpoint) || '/api/agents/prd-advisor/run';

  const generate = useCallback(async () => {
    setErr('');
    setLoading(true);
    setResult(null);
    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ company, industry, business, mode, raw_requirements: raw }),
      });
      if (!res.ok) { setErr(await readError(res)); return; }
      const data = await res.json();
      // A2 起统一契约 {ok, agent_id, result, refs, confidence}；PRD 明细在 result 里
      // 兼容旧扁平返回（A1 缓存的页面拿到旧结构也能渲染）
      setResult(data.result && typeof data.result === 'object' ? data.result : data);
    } catch (e) {
      setErr('网络错误：' + (e.message || e));
    } finally {
      setLoading(false);
    }
  }, [company, industry, business, mode, raw, endpoint]);

  const copyPrd = useCallback(async () => {
    if (!result?.prd) return;
    try { await navigator.clipboard.writeText(result.prd); }
    catch {
      const ta = document.createElement('textarea');
      ta.value = result.prd; document.body.appendChild(ta); ta.select();
      document.execCommand('copy'); document.body.removeChild(ta);
    }
  }, [result]);

  const downloadPrd = useCallback(() => {
    if (!result?.prd) return;
    const blob = new Blob([result.prd], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${(company || '客户').replace(/[\\/:*?"<>|]/g, '')}-AI智能体平台PRD.md`;
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [result, company]);

  const canSubmit = company.trim() && business.trim().length >= 5 && !loading;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal modal-xl agent-prd-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>{agent?.emoji || '🧭'} {agent?.name || '售前方案师'} · 在线体验</h3>
          <button className="icon-btn" onClick={onClose} aria-label="关闭">✕</button>
        </div>
        <div className="agent-prd-body">
          <div className="prd-intro">
            <div className="prd-intro-sub">
              {agent?.desc || '填写客户公司与业务信息，一键生成一份面向该客户的《AI 智能体平台功能需求 PRD》。'}
              生成前会自动检索知识库做行业接地（当前知识库越充实，产出越专业）。
            </div>
          </div>

          <div className="prd-form">
            <div className="prd-field">
              <label>公司名称 <span className="prd-req">*</span></label>
              <input value={company} maxLength={60} placeholder="例如：某某精密制造股份有限公司"
                     onChange={e => setCompany(e.target.value)} />
            </div>
            <div className="prd-field">
              <label>所属行业 <span className="prd-opt">（选填，留空则从业务描述推断）</span></label>
              <input value={industry} maxLength={40} placeholder="例如：汽车零部件 / 3C 电子 / 装备制造"
                     onChange={e => setIndustry(e.target.value)} />
            </div>
            <div className="prd-field">
              <label>业务介绍 <span className="prd-req">*</span></label>
              <textarea value={business} maxLength={4000} rows={4}
                        placeholder="客户主营什么、规模、现有系统（ERP/MES/PLM…）、想解决的核心问题等，越具体越好。"
                        onChange={e => setBusiness(e.target.value)} />
              <div className="prd-count">{business.length}/4000</div>
            </div>

            <div className="prd-field">
              <label>生成模式</label>
              <div className="prd-modes">
                <label className={`prd-mode ${mode === 'guide' ? 'active' : ''}`}>
                  <input type="radio" name="agent-prd-mode" value="guide" checked={mode === 'guide'}
                         onChange={() => setMode('guide')} />
                  <span className="prd-mode-name">引导模式</span>
                  <span className="prd-mode-desc">客户还不太清楚要什么，先给一版完整方案草稿 + 待澄清问题</span>
                </label>
                <label className={`prd-mode ${mode === 'normalize' ? 'active' : ''}`}>
                  <input type="radio" name="agent-prd-mode" value="normalize" checked={mode === 'normalize'}
                         onChange={() => setMode('normalize')} />
                  <span className="prd-mode-name">规范化模式</span>
                  <span className="prd-mode-desc">客户已给原始需求，整理成规范 PRD 并标注缺口/歧义</span>
                </label>
              </div>
            </div>

            {mode === 'normalize' && (
              <div className="prd-field">
                <label>客户原始需求 <span className="prd-req">*</span></label>
                <textarea value={raw} maxLength={6000} rows={5}
                          placeholder="把客户口述/微信/邮件里的需求原样贴进来，越全越好。"
                          onChange={e => setRaw(e.target.value)} />
                <div className="prd-count">{raw.length}/6000</div>
              </div>
            )}

            <div className="prd-actions">
              <button className="btn btn-primary" onClick={generate} disabled={!canSubmit}>
                {loading ? '正在生成（约 15–40 秒）…' : '生成 PRD'}
              </button>
              {result && (
                <>
                  <button className="btn btn-ghost" onClick={copyPrd}>复制全文</button>
                  <button className="btn btn-ghost" onClick={downloadPrd}>下载 .md</button>
                </>
              )}
            </div>
            {loading && <div className="prd-loading"><span className="prd-spinner" /> AI 正在撰写方案，请稍候…</div>}
            {err && <div className="prd-err">{err}</div>}
          </div>

          {result && (
            <div className="prd-result">
              <div className="prd-result-bar">
                <span className={`prd-badge ${result.grounded ? 'ok' : 'muted'}`}>
                  {result.grounded ? `已接地知识库 ${result.hits} 条` : '未接地（知识库无相关命中）'}
                </span>
                <span className="prd-badge muted">模式：{result.mode === 'guide' ? '引导' : '规范化'}</span>
                <span className="prd-badge muted">模型：{result.model}</span>
              </div>
              {result.sources && result.sources.length > 0 && (
                <div className="prd-sources">
                  参考来源：
                  {result.sources.map((s, i) => (
                    <span key={i} className="prd-src">
                      {s.url ? <a href={s.url} target="_blank" rel="noreferrer">{s.title}</a> : s.title}
                    </span>
                  ))}
                </div>
              )}
              <MarkdownView text={result.prd} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
