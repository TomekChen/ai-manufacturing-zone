import React, { useState, useEffect, useCallback, useRef } from 'react';

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

const METRIC_FALLBACK_LABEL = {
  faithfulness: '忠实度',
  answer_relevance: '答案相关性',
  context_precision: '上下文精确率',
  context_recall: '上下文召回率',
};

const INTENT_LABEL = { knowledge: '知识问答', smalltalk: '闲聊', offtopic: '超出范围' };
const RETR_LABEL = { vector: '纯向量', bm25: 'BM25', hybrid: '混合' };

// 0–1 显示为 xx.x%；null 显示 —
const score = (x) => (x === null || x === undefined) ? '—' : (x * 100).toFixed(1) + '%';

// 轻量 count-up：值变化时从上一个值补间到新值（与 Slice 4 看板一致的观感）
function useCountUp(value, dur = 700) {
  const [disp, setDisp] = useState(0);
  const fromRef = useRef(0);
  useEffect(() => {
    const from = fromRef.current;
    const to = value || 0;
    if (from === to) { setDisp(to); return; }
    let raf;
    const start = performance.now();
    const tick = (now) => {
      const p = Math.min(1, (now - start) / dur);
      const eased = 1 - Math.pow(1 - p, 3);
      setDisp(from + (to - from) * eased);
      if (p < 1) raf = requestAnimationFrame(tick);
      else fromRef.current = to;
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, dur]);
  return disp;
}

function MetricCard({ label, value, delta, tone }) {
  const d = useCountUp(value || 0);
  const deltaNum = (delta === null || delta === undefined) ? null : delta;
  const deltaStr = deltaNum === null ? '首次' :
    (deltaNum >= 0 ? '↑ ' : '↓ ') + Math.abs(deltaNum * 100).toFixed(1) + ' pt';
  return (
    <div className={`an-card ${tone || ''}`}>
      <div className="an-card-num">{(d * 100).toFixed(1)}<span className="an-card-suffix">%</span></div>
      <div className="an-card-hint">{label}</div>
      <div className={`ev-delta ${deltaNum === null ? 'first' : deltaNum >= 0 ? 'up' : 'down'}`}>{deltaStr}</div>
    </div>
  );
}

// 一 metric 一行的对比条：主条=knowledge 均分（accent），副条=control 均分（灰），用来做敏感度自检
function CompareRow({ label, know, ctl }) {
  const wKnow = Math.max(0, Math.min(1, know || 0)) * 100;
  const wCtl = Math.max(0, Math.min(1, ctl || 0)) * 100;
  return (
    <div className="ev-compare-row">
      <span className="ev-compare-label">{label}</span>
      <div className="ev-compare-bars">
        <div className="ev-bar-track"><div className="ev-bar-fill ev-bar-know" style={{ width: wKnow + '%' }} /></div>
        <div className="ev-bar-track ev-bar-thin"><div className="ev-bar-fill ev-bar-ctl" style={{ width: wCtl + '%' }} /></div>
      </div>
      <span className="ev-compare-vals"><b>{score(know)}</b> <span className="muted">/ {score(ctl)}</span></span>
    </div>
  );
}

function SnapshotChips({ snap }) {
  if (!snap) return null;
  const items = [
    ['检索策略', RETR_LABEL[snap.retrieval] || snap.retrieval],
    ['分块', snap.chunking],
    ['top_k', snap.top_k],
    ['分块大小', snap.chunk_size],
    ['重叠', snap.chunk_overlap],
    ['RRF k', snap.rrf_k],
    ['嵌入维度', snap.embed_dim],
    ['问答模型', snap.chat_model],
    ['裁判模型', snap.judge_model],
  ];
  return (
    <div className="ev-snapshot">
      {items.map(([k, v]) => (
        <span key={k} className="ev-snapshot-chip">
          <span className="ev-snapshot-k">{k}</span>
          <span className="ev-snapshot-v">{v ?? '—'}</span>
        </span>
      ))}
    </div>
  );
}

/* ===== 后台「评测」标签页（Slice 6）：手动重跑 RAGAS-lite 四指标 + 横向对比 ===== */
export default function AdminEval({ token }) {
  const [metrics, setMetrics] = useState(Object.keys(METRIC_FALLBACK_LABEL));
  const [labels, setLabels] = useState(METRIC_FALLBACK_LABEL);
  const [latest, setLatest] = useState(null);       // 已完成的最近一次 record
  const [prev, setPrev] = useState(null);           // 上一次 record（做 delta 用）
  const [status, setStatus] = useState(null);       // {running, current, total, current_qid, error}
  const [apiKeyOk, setApiKeyOk] = useState(true);   // 400 时置 false，灰按钮
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [err, setErr] = useState(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const pollRef = useRef(null);

  const auth = { Authorization: `Bearer ${token}` };

  const loadResults = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/admin/kb/eval/results?limit=5`, { headers: auth });
      if (res.status === 400 || res.status === 401) throw new Error(await readError(res));
      if (!res.ok) throw new Error(await readError(res));
      const data = await res.json();
      if (Array.isArray(data.metrics) && data.metrics.length) setMetrics(data.metrics);
      if (data.labels) setLabels({ ...METRIC_FALLBACK_LABEL, ...data.labels });
      const hist = data.history || [];
      setLatest(hist[hist.length - 1] || null);
      setPrev(hist.length >= 2 ? hist[hist.length - 2] : null);
    } catch (e) {
      setErr(e?.message || '加载评测历史失败');
    }
  }, [token]);

  const loadStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/admin/kb/eval/status`, { headers: auth });
      if (!res.ok) return;
      const st = await res.json();
      setStatus(st);
      // 若已完成但 latest 还没刷 → 拉一次历史
      if (st && !st.running && st.last_record_id && (!latest || latest.id !== st.last_record_id)) {
        loadResults();
      }
    } catch { /* 轮询失败静默 */ }
  }, [auth, loadResults, latest]);

  // 首次挂载：并行拉历史 + 状态
  useEffect(() => {
    let alive = true;
    (async () => {
      setLoading(true);
      await Promise.all([loadResults(), loadStatus()]);
      if (alive) setLoading(false);
    })();
    return () => { alive = false; };
  }, []); // eslint-disable-line

  // 运行时每 3 秒轮询状态
  useEffect(() => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    if (status?.running) {
      pollRef.current = setInterval(loadStatus, 3000);
    }
    return () => { if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; } };
  }, [status?.running, loadStatus]);

  const runEval = async () => {
    setErr(null);
    setStarting(true);
    try {
      const res = await fetch(`${API_BASE}/admin/kb/eval/run`, { method: 'POST', headers: auth });
      if (res.status === 400) {
        const body = await res.json().catch(() => ({}));
        setApiKeyOk(false);
        throw new Error(body.error || '无法启动评测（很可能未配置 DASHSCOPE_API_KEY）');
      }
      if (res.status === 409) {
        // 已有一轮在跑，直接进入轮询
        await loadStatus();
        return;
      }
      if (!res.ok) throw new Error(await readError(res));
      // 启动成功，立刻把 running 打开，让轮询开始
      setStatus((s) => ({ ...(s || {}), running: true, current: 0, error: null }));
      loadStatus();
    } catch (e) {
      setErr(e?.message || '启动评测失败');
    } finally {
      setStarting(false);
    }
  };

  const running = !!status?.running;
  const prog = running && status.total
    ? Math.round((status.current / status.total) * 100)
    : (running ? 0 : 100);

  const overall = latest?.overall || {};
  const ctlOverall = latest?.by_type?.control || {};
  const prevOverall = prev?.overall || null;

  return (
    <div className="an-panel ev-panel">
      <div className="an-toolbar">
        <div className="an-toolbar-title">
          离线评测
          <span className="an-sub">RAGAS-lite · 18 题小标准集 · 手动重跑才花额度</span>
        </div>
        <div className="an-range">
          <button
            className="btn btn-ghost"
            onClick={loadResults}
            disabled={loading}
            title="刷新结果"
          >刷新</button>
          <button
            className="btn btn-primary ev-run-btn"
            onClick={runEval}
            disabled={running || starting || !apiKeyOk}
            title={running ? '评测正在运行中' : (!apiKeyOk ? '未配置 DASHSCOPE_API_KEY，无法启动' : '启动一次完整评测')}
          >
            {running ? '评测中…' : (starting ? '启动中…' : '▶ 重跑评测')}
          </button>
        </div>
      </div>

      {status?.error && <div className="an-error">上次评测异常：{status.error}</div>}
      {err && <div className="an-error">{err}</div>}

      {running && (
        <div className="ev-progress">
          <div className="ev-progress-bar"><div className="ev-progress-fill" style={{ width: prog + '%' }} /></div>
          <div className="ev-progress-text">
            正在评测 {status.current + 1} / {status.total}
            {status.current_qid ? ` · 当前题目 ${status.current_qid}` : ''}
            <span className="muted"> · 预计需要 2–4 分钟，可切走稍后再看</span>
          </div>
        </div>
      )}

      {loading && !latest && <div className="an-empty">加载中…</div>}

      {!loading && !latest && !running && (
        <div className="an-empty">
          还没有跑过评测。点击右上角「▶ 重跑评测」启动第一次（约 2–4 分钟，会产生 LLM 调用额度）。
        </div>
      )}

      {latest && (
        <>
          {/* 顶部四指标卡：主指标（knowledge 均分）+ 与上次的 Δ */}
          <div className="an-cards">
            {metrics.map((m) => (
              <MetricCard
                key={m}
                label={labels[m] || m}
                value={overall[m]}
                delta={prevOverall ? (overall[m] - (prevOverall[m] ?? 0)) : null}
              />
            ))}
          </div>

          <div className="an-meta">
            上次完成：{latest.ts?.replace('T', ' ')} · 耗时 {latest.elapsed ? latest.elapsed.toFixed(1) + 's' : '—'} ·
            {' '}共 {latest.counts?.total ?? '—'} 题（知识 {latest.counts?.knowledge ?? 0} · 对照 {latest.counts?.control ?? 0}）
          </div>

          <SnapshotChips snap={latest.strategy_snapshot} />

          {/* 主指标 vs 对照组 横向条形对比 */}
          <div className="an-block">
            <div className="an-block-title">
              指标对比<small>粗条=知识题均分（越高越好）· 细条=对照组均分（越低说明评测越敏感）</small>
            </div>
            {metrics.map((m) => (
              <CompareRow key={m} label={labels[m] || m} know={overall[m]} ctl={ctlOverall[m]} />
            ))}
          </div>

          {/* 每题分数明细：折叠，展开后是表格 */}
          <div className="an-block">
            <div className="an-block-title ev-detail-head" onClick={() => setDetailOpen((v) => !v)}>
              <span>逐题分数明细</span>
              <small>{detailOpen ? '点击收起' : '点击展开'} · 共 {(latest.per_question || []).length} 题</small>
            </div>
            {detailOpen && (
              <table className="an-table ev-detail-table">
                <thead>
                  <tr>
                    <th>题目</th>
                    <th>类别</th>
                    <th>意图</th>
                    <th>检索</th>
                    <th className="an-col-count">命中</th>
                    {metrics.map((m) => (
                      <th key={m} className="ev-col-score">{(labels[m] || m).slice(0, 5)}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(latest.per_question || []).map((q) => (
                    <tr key={q.id} className={q.type === 'control' ? 'ev-row-control' : ''}>
                      <td className="ev-col-q" title={q.question}>{q.id} · {q.question?.slice(0, 22) || ''}…</td>
                      <td className="ev-col-cat">{q.category}</td>
                      <td>{INTENT_LABEL[q.intent] || q.intent || '—'}</td>
                      <td>{RETR_LABEL[q.retrieval] || q.retrieval || '—'}</td>
                      <td className="an-col-count">{q.hits_count ?? '—'}</td>
                      {metrics.map((m) => (
                        <td key={m} className="ev-col-score">{score(q.scores?.[m])}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}
    </div>
  );
}
