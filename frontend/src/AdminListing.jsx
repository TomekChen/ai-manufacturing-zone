import React, { useEffect, useState, useCallback, useRef } from 'react';
import { readError } from './api';

const API_BASE = '/api';

/* ===== 上架物料流水线（A11）：产品 → 实测数据 → 文案 → 分镜 → 审批出包 =====
   给淘宝/京东/社媒上架用：选一个智能体产品，后台跑四阶段并逐段记账，
   人工审批通过后下载物料包（体验地址 + 效果数据 + 商品文案 + 视频分镜脚本）。 */

const STAGE_LABEL = {
  health: '体检', metrics: '样例实测', copy: '商品文案', storyboard: '视频分镜',
};
const STAGE_ORDER = ['health', 'metrics', 'copy', 'storyboard'];

const STATUS = {
  running: { label: '生成中', cls: 'offline' },
  done: { label: '待审批', cls: 'offline' },
  failed: { label: '失败', cls: 'offline' },
  approved: { label: '已通过', cls: 'online' },
  rejected: { label: '已驳回', cls: 'offline' },
};

function StagePill({ state }) {
  const map = { running: '进行中…', done: '完成', failed: '失败', skipped: '跳过' };
  return <span className={`status-pill ${state === 'done' ? 'online' : 'offline'}`}>{map[state] || '排队'}</span>;
}

export default function AdminListing({ token }) {
  const [agents, setAgents] = useState([]);
  const [agentId, setAgentId] = useState('');
  const [rows, setRows] = useState([]);
  const [err, setErr] = useState('');
  const [msg, setMsg] = useState('');
  const [busy, setBusy] = useState(false);
  const [detail, setDetail] = useState(null);
  const [note, setNote] = useState('');
  const [sc, setSc] = useState(null);
  const timer = useRef(null);

  const auth = { headers: { Authorization: `Bearer ${token}` } };

  const load = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/admin/listings`, auth);
      if (!res.ok) throw new Error(await readError(res));
      const data = await res.json();
      setRows(data);
      // 有仍在生成的单，1.5 秒后再刷一次进度
      const running = data.some(r => r.status === 'running');
      if (running && !timer.current) {
        timer.current = setTimeout(() => { timer.current = null; load(); }, 1500);
      }
    } catch (e) {
      setErr(e?.message || '加载失败');
    }
  }, [token]);

  useEffect(() => {
    fetch(`${API_BASE}/agents`).then(r => r.json())
      .then(d => { const live = (d || []).filter(a => a.status === 'live'); setAgents(live); if (live[0]) setAgentId(live[0].id); })
      .catch(() => setAgents([]));
    load();
    return () => { if (timer.current) clearTimeout(timer.current); };
  }, [load]);

  const generate = async () => {
    if (!agentId || busy) return;
    setBusy(true); setErr(''); setMsg('');
    try {
      const res = await fetch(`${API_BASE}/admin/listings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ agent_id: agentId }),
      });
      if (!res.ok) throw new Error(await readError(res));
      setMsg('流水线已启动，四阶段跑完后即可审批');
      load();
    } catch (e) {
      setErr(e?.message || '启动失败');
    } finally {
      setBusy(false);
    }
  };

  const open = async (id) => {
    setErr(''); setNote('');
    try {
      const res = await fetch(`${API_BASE}/admin/listings/${id}`, auth);
      if (!res.ok) throw new Error(await readError(res));
      const row = await res.json();
      setDetail(row);
      loadShowcases(row.agent_id);
    } catch (e) {
      setErr(e?.message || '详情加载失败');
    }
  };

  // A12：实测输出留档后，在这里挑一条定为体验弹窗里的对外示例
  const loadShowcases = async (agentId) => {
    if (!agentId) return;
    try {
      const res = await fetch(`${API_BASE}/admin/showcases?agent_id=${agentId}`, auth);
      if (!res.ok) throw new Error(await readError(res));
      setSc(await res.json());
    } catch (e) {
      setSc(null);
    }
  };

  const pick = async (no, label) => {
    setErr('');
    try {
      const res = await fetch(`${API_BASE}/admin/showcases`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ agent_id: detail.agent_id, no, label }),
      });
      if (!res.ok) throw new Error(await readError(res));
      setMsg(`已将样例 ${no} 设为「${label}」示例`);
      loadShowcases(detail.agent_id);
    } catch (e) {
      setErr(e?.message || '设置示例失败');
    }
  };

  const review = async (action) => {
    if (!detail) return;
    try {
      const res = await fetch(`${API_BASE}/admin/listings/${detail.id}/review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ action, note }),
      });
      if (!res.ok) throw new Error(await readError(res));
      const d = await res.json();
      setDetail({ ...detail, status: d.listing.status });
      setMsg(action === 'approve' ? '已通过审批，可下载物料包' : '已驳回');
      load();
    } catch (e) {
      setErr(e?.message || '审批失败');
    }
  };

  const download = async () => {
    if (!detail) return;
    try {
      const res = await fetch(`${API_BASE}/admin/listings/${detail.id}/export`, auth);
      if (!res.ok) throw new Error(await readError(res));
      const md = await res.text();
      const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `${detail.agent_id}-${detail.id}.md`;
      a.click();
      URL.revokeObjectURL(a.href);
    } catch (e) {
      setErr(e?.message || '导出失败');
    }
  };

  const st = detail?.stages || {};
  const m = st.metrics?.data || {};
  const copy = st.copy?.data || {};
  const board = st.storyboard?.data || {};
  const canReview = detail && (detail.status === 'done' || detail.status === 'failed');
  const canExport = detail && (detail.status === 'approved' || detail.status === 'done');

  return (
    <div>
      <div className="admin-toolbar">
        <select value={agentId} onChange={e => setAgentId(e.target.value)} style={{ minWidth: 200 }}>
          {agents.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
        </select>
        <button className="btn btn-primary" onClick={generate} disabled={!agentId || busy}>
          {busy ? '启动中…' : '生成上架物料'}
        </button>
        <span className="muted">体检 → 样例实测（出效果数据）→ 商品文案 → 视频分镜，跑完人工审批后出包</span>
      </div>
      {msg && <div style={{ margin: '8px 0', fontSize: 13, color: '#15803d' }}>{msg}</div>}
      {err && <div className="prd-err">{err}</div>}

      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr><th>产品</th><th>阶段</th><th>状态</th><th>生成时间</th><th>操作</th></tr>
          </thead>
          <tbody>
            {rows.map(r => (
              <tr key={r.id}>
                <td><strong>{r.agent_name || r.agent_id}</strong><div className="muted">{r.id}</div></td>
                <td>{STAGE_ORDER.map(k => <span key={k} style={{ marginRight: 4 }} title={STAGE_LABEL[k]}><StagePill state={r.stages?.[k]} /></span>)}</td>
                <td><span className={`status-pill ${(STATUS[r.status] || STATUS.running).cls}`}>{(STATUS[r.status] || STATUS.running).label}</span></td>
                <td className="muted">{r.created_at}</td>
                <td><button className="btn btn-sm btn-ghost" onClick={() => open(r.id)}>查看</button></td>
              </tr>
            ))}
            {rows.length === 0 && <tr><td colSpan="5" className="muted">还没有物料单，选个产品点「生成上架物料」</td></tr>}
          </tbody>
        </table>
      </div>

      {detail && (
        <div className="modal-backdrop" onClick={() => setDetail(null)}>
          <div className="modal modal-xl" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{detail.agent_name} · 物料单 {detail.id}</h3>
              <button className="icon-btn" onClick={() => setDetail(null)} aria-label="关闭">✕</button>
            </div>
            <div className="agent-prd-body" style={{ maxHeight: '62vh', overflowY: 'auto' }}>
              <div className="prd-result-bar">
                <span className={`prd-badge ${(STATUS[detail.status] || STATUS.running).cls === 'online' ? 'ok' : 'muted'}`}>
                  {(STATUS[detail.status] || STATUS.running).label}
                </span>
                <span className="prd-badge muted">体验地址：{window.location.origin}</span>
              </div>
              {detail.error && <div className="prd-err">{detail.error}</div>}

              <h4 style={{ margin: '14px 0 6px' }}>一、体检</h4>
              {(st.health?.data?.checks || []).map((c, i) => (
                <div key={i} style={{ fontSize: 13 }}>
                  {c.ok ? '✅' : '❌'} {c.name}：<span className="muted">{c.detail}</span>
                </div>
              ))}

              <h4 style={{ margin: '14px 0 6px' }}>二、效果数据（内置样例实测）</h4>
              <div style={{ fontSize: 13 }}>
                样例 {m.total || 0} 组 · 成功 {m.success || 0} 组（成功率 {Math.round((m.success_rate || 0) * 100)}%）
                · 平均置信度 {m.avg_confidence != null ? Math.round(m.avg_confidence * 100) + '%' : '—'}
                · 输出完整度 {m.avg_coverage ? Math.round(m.avg_coverage * 100) + '%' : '—'}
                · 平均耗时 {m.avg_latency_ms || 0} ms
              </div>
              {(m.samples || []).map((s, i) => (
                <div key={i} className="muted" style={{ fontSize: 12, marginTop: 4 }}>
                  {s.no}. {s.input} → {s.ok ? `成功（${s.confidence != null ? Math.round(s.confidence * 100) + '%' : '—'}，${s.latency_ms}ms）` : `失败：${s.error || ''}`}
                </div>
              ))}

              <h4 style={{ margin: '14px 0 6px' }}>三、商品文案</h4>
              <div style={{ fontSize: 14, fontWeight: 600 }}>{copy.title}｜{copy.tagline}</div>
              {[['核心功能', copy.features], ['操作说明', copy.usage], ['应用场景', copy.scenarios]].map(([label, items]) => (
                <div key={label} style={{ marginTop: 6 }}>
                  <b style={{ fontSize: 13 }}>{label}：</b>
                  <ul style={{ margin: '2px 0 0 18px', fontSize: 13 }}>
                    {(items || []).map((x, i) => <li key={i}>{x}</li>)}
                  </ul>
                </div>
              ))}
              {copy.audience && <div style={{ fontSize: 13, marginTop: 6 }}>适合客户：{copy.audience}</div>}

              <h4 style={{ margin: '14px 0 6px' }}>四、宣传视频分镜（人工录制）</h4>
              <div className="muted" style={{ fontSize: 13 }}>美术方向：{board.style || '—'}</div>
              {(board.scenes || []).map((s, i) => (
                <div key={i} style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: '8px 12px', marginTop: 6 }}>
                  <b style={{ fontSize: 13 }}>{s.no} {s.title}</b>
                  <div style={{ fontSize: 13 }}>{s.desc}</div>
                  <div style={{ fontSize: 12, color: '#2563eb' }}>🎥 {s.camera_move}</div>
                  <div style={{ fontSize: 12, opacity: 0.65 }}>静帧提示词：{s.still_prompt}</div>
                </div>
              ))}

              {(detail.trail || []).length > 0 && (
                <>
                  <h4 style={{ margin: '14px 0 6px' }}>五、审批留痕</h4>
                  {detail.trail.map((t, i) => (
                    <div key={i} style={{ fontSize: 12 }}>
                      {t.ts} · {t.action === 'approve' ? '批准' : '驳回'}：{t.note || '—'}
                    </div>
                  ))}
                </>
              )}

              <h4 style={{ margin: '14px 0 6px' }}>六、对外示例（客户在体验弹窗里先看到的）</h4>
              <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>
                示例只能取自上面「样例实测」真跑出来的输出，不允许手写。每产品两格：「常规」放最顺的典型场景，
                「缺字段」放能体现它把缺失标出来、不瞎猜的那条。
              </div>
              {(sc?.showcases || []).map(s => (
                <div key={s.label} style={{ fontSize: 12, marginBottom: 4 }}>
                  <b>{s.label}</b>：样例 {s.no}（置信度 {s.confidence != null ? Math.round(s.confidence * 100) + '%' : '—'}
                  ，完整度 {s.coverage ? Math.round(s.coverage * 100) + '%' : '—'}，{s.latency_ms || 0} ms）
                </div>
              ))}
              {!(sc?.showcases || []).length && (
                <div className="muted" style={{ fontSize: 12 }}>两格都还没挑，体验弹窗暂时用出厂种子</div>
              )}
              {(sc?.candidates || []).map(cd => (
                <div key={cd.no} style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: '6px 10px', marginTop: 6, fontSize: 12 }}>
                  <b>样例 {cd.no}</b>
                  {cd.in_use && <span style={{ color: '#15803d' }}> · 已定为示例</span>}
                  <div className="muted" style={{ wordBreak: 'break-all' }}>{JSON.stringify(cd.input).slice(0, 120)}</div>
                  <div style={{ marginTop: 4 }}>
                    {(sc?.labels || []).map(lb => (
                      <button key={lb} className="btn btn-sm btn-ghost" style={{ marginRight: 6 }}
                              onClick={() => pick(cd.no, lb)}>设为「{lb}」</button>
                    ))}
                  </div>
                </div>
              ))}
              {!(sc?.candidates || []).length && (
                <div className="muted" style={{ fontSize: 12 }}>这个产品还没有实测输出留档，先点「生成上架物料」跑一轮实测</div>
              )}

              <div className="modal-actions" style={{ marginTop: 16 }}>
                {canReview && (
                  <>
                    <input style={{ flex: 1 }} placeholder="审批备注（驳回必填）" value={note} onChange={e => setNote(e.target.value)} />
                    <button className="btn btn-ghost" onClick={() => review('reject')}>驳回</button>
                    <button className="btn btn-primary" onClick={() => review('approve')}>批准</button>
                  </>
                )}
                {canExport && <button className="btn btn-primary" onClick={download}>下载物料包 .md</button>}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
