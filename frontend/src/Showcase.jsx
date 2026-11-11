import React, { useEffect, useState } from 'react';

/* ===== 对外示例条（A12）：体验弹窗里「先看示例」 =====
   客户不知道生成出来是什么玩意就没有付费理由，所以输入框上方先给一条真跑出来的结果。
   示例内容一律来自后台从「内置样例实测」候选池挑定的快照（GET /api/agents/<id>/showcases），
   前端不写死任何示例数据；本组件只负责「选哪一条」和「把输入交还给产品弹窗回填」，
   结果渲染仍走各产品自己的组件（订单出工单表、对账出三堆分组……不降级成纯文本）。
   样式复用 prd-* / qa-suggestion 体系，不新增 CSS。 */

// 固定口径：示例是内置样例（全虚构）实测出来的，不是客户产线数据
export const DEMO_NOTE = '示例为内置样例实测结果，非客户产线数据';

export function useShowcases(agentId) {
  const [rows, setRows] = useState([]);
  useEffect(() => {
    if (!agentId) { setRows([]); return undefined; }
    let alive = true;
    // 拉不到示例不影响客户自己输入生成，静默降级为不显示示例条
    fetch(`/api/agents/${agentId}/showcases`)
      .then(r => (r.ok ? r.json() : { showcases: [] }))
      .then(d => { if (alive) setRows(Array.isArray(d.showcases) ? d.showcases : []); })
      .catch(() => {});
    return () => { alive = false; };
  }, [agentId]);
  return rows;
}

// 示例输入摘要：mode 这类程序开关不展示给客户看，只留人看得懂的业务文字
const SKIP_KEYS = { mode: 1 };
const brief = (input) => Object.entries(input || {})
  .filter(([k, v]) => !SKIP_KEYS[k] && typeof v === 'string' && v.trim())
  .map(([, v]) => v)
  .join(' · ').replace(/\s+/g, ' ').slice(0, 46);

export function DemoNote() {
  return <div className="prd-sources" style={{ color: '#0369a1' }}>ℹ️ {DEMO_NOTE}</div>;
}

export default function ShowcasePicker({ agentId, active, onShow, onUse }) {
  const rows = useShowcases(agentId);
  if (rows.length === 0) return null;
  return (
    <div className="prd-field" style={{ marginBottom: 12 }}>
      <label>先看示例 <span className="prd-opt">下面是内置样例真跑出来的结果：「看示例」直接看产出，「用这条试试」把原文填回输入框自己跑一遍</span></label>
      {rows.map(r => (
        <div key={r.label} style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6, flexWrap: 'wrap' }}>
          <span className={`prd-badge ${active === r.label ? 'ok' : 'muted'}`}>{r.label}</span>
          <span className="muted" style={{ fontSize: 13, flex: '1 1 160px' }}>{brief(r.input)}…</span>
          <span style={{ display: 'flex', gap: 6, whiteSpace: 'nowrap' }}>
            <button type="button" className="btn btn-sm btn-ghost" onClick={() => onShow(r)}>看示例</button>
            <button type="button" className="btn btn-sm btn-ghost" onClick={() => onUse(r)}>用这条试试</button>
          </span>
        </div>
      ))}
    </div>
  );
}
