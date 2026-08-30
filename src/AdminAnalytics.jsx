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

// 策略中文名（展示用，key 来自后端聚合，注册表为准）
const RETR_LABEL = { vector: '纯向量', bm25: 'BM25', hybrid: '混合', unknown: '未知' };
const label = (map, key) => map[key] || key;
const pct = (x) => `${Math.round((x || 0) * 100)}%`;

// 轻量数字滚动动画（count-up）：值变化时从上一个值补间到新值
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

function StatCard({ value, digits = 0, suffix = '', hint, tone }) {
  const d = useCountUp(value);
  const shown = suffix === '%' ? Math.round(d) : d.toFixed(digits);
  return (
    <div className={`an-card ${tone || ''}`}>
      <div className="an-card-num">{shown}<span className="an-card-suffix">{suffix}</span></div>
      <div className="an-card-hint">{hint}</div>
    </div>
  );
}

// 一条 0–1 的横向条形（拒绝率、👍率这类可比指标用）
function MiniBar({ ratio, fill }) {
  const w = Math.max(0, Math.min(1, ratio || 0)) * 100;
  return (
    <span className="an-bar">
      <span className="an-bar-fill" style={{ width: `${w}%`, background: fill }} />
    </span>
  );
}

// 问答量时间趋势：极简内联 SVG 折线 + 面积，自适应 viewBox
function TrendChart({ trend }) {
  const pts = trend || [];
  const W = 720, H = 160, pad = 8;
  if (pts.length === 0) return <div className="an-empty">暂无数据</div>;
  const maxC = Math.max(1, ...pts.map((p) => p.count));
  const n = pts.length;
  const x = (i) => n === 1 ? W / 2 : pad + (i * (W - 2 * pad)) / (n - 1);
  const y = (c) => H - pad - (c / maxC) * (H - 2 * pad);
  const line = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(p.count).toFixed(1)}`).join(' ');
  const area = `${line} L${x(n - 1).toFixed(1)},${H - pad} L${x(0).toFixed(1)},${H - pad} Z`;
  // 日期标签：首、中、末三个
  const ticks = [0, Math.floor((n - 1) / 2), n - 1].filter((v, i, a) => a.indexOf(v) === i);
  return (
    <div className="an-trend">
      <div className="an-trend-max">峰值 {maxC} 问/天</div>
      <svg className="an-trend-svg" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img" aria-label="问答量趋势">
        <defs>
          <linearGradient id="anTrendFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.35" />
            <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={area} fill="url(#anTrendFill)" />
        <path d={line} fill="none" stroke="var(--accent)" strokeWidth="2" vectorEffect="non-scaling-stroke" />
        {pts.map((p, i) => (
          <circle key={i} cx={x(i)} cy={y(p.count)} r="2.5" fill="var(--accent)" />
        ))}
      </svg>
      <div className="an-trend-axis">
        {ticks.map((i) => (
          <span key={i} style={{ left: `${(x(i) / W) * 100}%` }}>{pts[i]?.date?.slice(5) || ''}</span>
        ))}
      </div>
    </div>
  );
}

/* ===== 后台「问答分析」标签页（Slice 4）：真实流量指标看板，零 token ===== */
export default function AdminAnalytics({ token }) {
  const [days, setDays] = useState(30);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);

  const auth = { Authorization: `Bearer ${token}` };

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const res = await fetch(`${API_BASE}/admin/kb/analytics?days=${days}`, { headers: auth });
      if (!res.ok) throw new Error(await readError(res));
      setData(await res.json());
    } catch (e) {
      setErr(e?.message || '加载失败');
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [days, token]);

  useEffect(() => { load(); }, [load]);

  const strategies = data ? Object.entries(data.by_strategy || {}) : [];

  return (
    <div className="an-panel">
      <div className="an-toolbar">
        <div className="an-toolbar-title">问答看板<span className="an-sub">真实流量统计 · 不消耗额度</span></div>
        <div className="an-range">
          {[7, 14, 30].map((d) => (
            <button key={d} className={days === d ? 'an-range-btn active' : 'an-range-btn'} onClick={() => setDays(d)}>
              近 {d} 天
            </button>
          ))}
          <button className="an-refresh" onClick={load} disabled={loading}>{loading ? '刷新中…' : '刷新'}</button>
        </div>
      </div>

      {err && <div className="an-error">{err}</div>}

      {data && (
        <>
          {/* 顶部数字卡 */}
          <div className="an-cards">
            <StatCard value={data.total} hint="总提问数" />
            <StatCard value={Math.round((data.refuse_rate || 0) * 100)} suffix="%" hint="无命中/拒绝率" tone={data.refuse_rate > 0.3 ? 'warn' : ''} />
            <StatCard value={Math.round((data.up_rate || 0) * 100)} suffix="%" hint="👍 满意率" tone="good" />
            <StatCard value={data.avg_hits} digits={1} hint="平均命中片段数" />
          </div>

          <div className="an-meta">
            👍 {data.feedback_up} · 👎 {data.feedback_down} · 统计窗口 近 {data.days} 天
          </div>

          {/* 各策略并排对比 */}
          <div className="an-block">
            <div className="an-block-title">检索策略对比<small>同策略内可比；得分量纲不同故只做数值展示</small></div>
            {strategies.length === 0 ? (
              <div className="an-empty">窗口内暂无问答</div>
            ) : (
              <div className="an-strategy-grid">
                {strategies.map(([name, b]) => (
                  <div className="an-strategy" key={name}>
                    <div className="an-strategy-name">{label(RETR_LABEL, name)}</div>
                    <div className="an-strategy-count">{b.count} 问</div>
                    <div className="an-row">
                      <span className="an-row-label">拒绝率</span>
                      <MiniBar ratio={b.refuse_rate} fill="var(--danger, #ef4444)" />
                      <span className="an-row-val">{pct(b.refuse_rate)}</span>
                    </div>
                    <div className="an-row">
                      <span className="an-row-label">👍率</span>
                      <MiniBar ratio={b.count ? b.up / (b.up + b.down || 1) : 0} fill="var(--good, #22c55e)" />
                      <span className="an-row-val">{b.up + b.down ? pct(b.up / (b.up + b.down)) : '—'}</span>
                    </div>
                    <div className="an-row">
                      <span className="an-row-label">平均最高分</span>
                      <span className="an-row-val an-plain">{b.avg_top_score ? b.avg_top_score.toFixed(3) : '—'}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* 时间趋势 */}
          <div className="an-block">
            <div className="an-block-title">问答量趋势</div>
            <TrendChart trend={data.trend} />
          </div>

          {/* 未命中 / 被拒问题清单 */}
          <div className="an-block">
            <div className="an-block-title">知识库缺口 · 未命中问题<small>按提问频次排序，可据此补内容或换策略</small></div>
            {(data.unanswered || []).length === 0 ? (
              <div className="an-empty">窗口内没有未命中的提问，覆盖良好 👍</div>
            ) : (
              <table className="an-table">
                <thead>
                  <tr><th>问题</th><th className="an-col-count">次数</th><th className="an-col-time">最近提问</th></tr>
                </thead>
                <tbody>
                  {data.unanswered.map((u, i) => (
                    <tr key={i}>
                      <td>{u.question}</td>
                      <td className="an-col-count"><span className="an-freq">{u.count}</span></td>
                      <td className="an-col-time">{u.last_ts ? u.last_ts.slice(0, 16).replace('T', ' ') : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}

      {!data && !loading && !err && <div className="an-empty">暂无数据</div>}
    </div>
  );
}
