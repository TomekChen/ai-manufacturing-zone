import React, { useState, useCallback } from 'react';

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

// ── 轻量 Markdown 渲染（不引第三方库）：标题 / 粗体 / 行内码 / 有序无序列表 / 表格 / 分隔线 ──
function inline(text) {
  // 先按 **粗体** 与 `code` 切分
  const nodes = [];
  let key = 0;
  const re = /(\*\*([^*]+)\*\*|`([^`]+)`)/g;
  let last = 0, m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) nodes.push(text.slice(last, m.index));
    if (m[2] !== undefined) nodes.push(<strong key={key++}>{m[2]}</strong>);
    else if (m[3] !== undefined) nodes.push(<code key={key++} className="prd-code">{m[3]}</code>);
    last = m.index + m[0].length;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

function isTableSep(line) {
  return /^\s*\|?[\s:|-]+\|?\s*$/.test(line) && line.includes('-');
}

function MarkdownView({ text }) {
  const lines = (text || '').replace(/\r\n/g, '\n').split('\n');
  const out = [];
  let i = 0, key = 0;
  while (i < lines.length) {
    const line = lines[i];
    // 表格：当前行含 | 且下一行是分隔线
    if (line.trim().startsWith('|') && i + 1 < lines.length && isTableSep(lines[i + 1])) {
      const header = line.split('|').slice(1, -1).map(s => s.trim());
      i += 2;
      const rows = [];
      while (i < lines.length && lines[i].trim().startsWith('|')) {
        rows.push(lines[i].split('|').slice(1, -1).map(s => s.trim()));
        i++;
      }
      out.push(
        <table key={key++} className="prd-table">
          <thead><tr>{header.map((h, j) => <th key={j}>{inline(h)}</th>)}</tr></thead>
          <tbody>{rows.map((r, ri) => <tr key={ri}>{r.map((c, ci) => <td key={ci}>{inline(c)}</td>)}</tr>)}</tbody>
        </table>
      );
      continue;
    }
    const h = line.match(/^(#{1,6})\s+(.*)$/);
    if (h) {
      const lvl = h[1].length;
      const El = ('h' + Math.min(lvl + 2, 6));
      out.push(<El key={key++} className={`prd-h prd-h${lvl}`}>{inline(h[2])}</El>);
      i++; continue;
    }
    if (/^\s*---+\s*$/.test(line)) { out.push(<hr key={key++} className="prd-hr" />); i++; continue; }
    if (/^\s*[-*]\s+/.test(line)) {
      const items = [];
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) { items.push(lines[i].replace(/^\s*[-*]\s+/, '')); i++; }
      out.push(<ul key={key++} className="prd-ul">{items.map((t, j) => <li key={j}>{inline(t)}</li>)}</ul>);
      continue;
    }
    if (/^\s*\d+\.\s+/.test(line)) {
      const items = [];
      while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) { items.push(lines[i].replace(/^\s*\d+\.\s+/, '')); i++; }
      out.push(<ol key={key++} className="prd-ol">{items.map((t, j) => <li key={j}>{inline(t)}</li>)}</ol>);
      continue;
    }
    if (line.trim() === '') { i++; continue; }
    // 段落：聚到空行/结构行为止
    const buf = [];
    while (i < lines.length && lines[i].trim() !== '' &&
           !/^(#{1,6})\s+/.test(lines[i]) && !/^\s*[-*]\s+/.test(lines[i]) &&
           !/^\s*\d+\.\s+/.test(lines[i]) && !(lines[i].trim().startsWith('|')) &&
           !/^\s*---+\s*$/.test(lines[i])) {
      buf.push(lines[i]); i++;
    }
    out.push(<p key={key++} className="prd-p">{inline(buf.join(' '))}</p>);
  }
  return <div className="prd-doc">{out}</div>;
}

// ── 主组件 ──
export default function AdminPRD({ token }) {
  const [company, setCompany] = useState('');
  const [industry, setIndustry] = useState('');
  const [business, setBusiness] = useState('');
  const [mode, setMode] = useState('guide');
  const [raw, setRaw] = useState('');
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState('');
  const [result, setResult] = useState(null);

  const generate = useCallback(async () => {
    setErr('');
    setLoading(true);
    setResult(null);
    try {
      const res = await fetch(`${API_BASE}/admin/prd/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ company, industry, business, mode, raw_requirements: raw }),
      });
      if (!res.ok) { setErr(await readError(res)); return; }
      const data = await res.json();
      setResult(data);
    } catch (e) {
      setErr('网络错误：' + (e.message || e));
    } finally {
      setLoading(false);
    }
  }, [token, company, industry, business, mode, raw]);

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
    <div className="prd-panel">
      <div className="prd-intro">
        <div className="prd-intro-title">AI 智能体平台功能需求 PRD 生成器</div>
        <div className="prd-intro-sub">
          填写客户公司与业务信息，一键生成一份面向该客户的《AI 智能体平台功能需求 PRD》。
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
              <input type="radio" name="prd-mode" value="guide" checked={mode === 'guide'}
                     onChange={() => setMode('guide')} />
              <span className="prd-mode-name">引导模式</span>
              <span className="prd-mode-desc">客户还不太清楚要什么，先给一版完整方案草稿 + 待澄清问题</span>
            </label>
            <label className={`prd-mode ${mode === 'normalize' ? 'active' : ''}`}>
              <input type="radio" name="prd-mode" value="normalize" checked={mode === 'normalize'}
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
  );
}
