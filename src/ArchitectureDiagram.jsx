import React, { useState } from 'react';
import { ARCHITECTURE, findAgentByScenario, getAgentsByDepartment, getDepartmentById } from './architectureData';
import './architecture.css';

/* ===== 层间连接箭头 ===== */
function LayerConnector() {
  return (
    <div className="arch-connector">
      <svg width="24" height="32" viewBox="0 0 24 32" fill="none">
        <line x1="12" y1="0" x2="12" y2="26" stroke="url(#connGrad)" strokeWidth="2" strokeDasharray="4 3" />
        <polyline points="7,21 12,28 17,21" stroke="url(#connGrad)" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
        <defs>
          <linearGradient id="connGrad" x1="12" y1="0" x2="12" y2="28" gradientUnits="userSpaceOnUse">
            <stop stopColor="#06b6d4" stopOpacity="0.6" />
            <stop offset="1" stopColor="#3b82f6" stopOpacity="0.3" />
          </linearGradient>
        </defs>
      </svg>
    </div>
  );
}

/* ===== 业务顶层：企业 ===== */
function EnterpriseLayer() {
  const { enterprise } = ARCHITECTURE;
  return (
    <div className="arch-layer arch-enterprise-layer">
      <div className="arch-enterprise-box">
        <div className="arch-enterprise-icon">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 002 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z" />
            <path d="M7.5 4.21l4.5 2.6 4.5-2.6M7.5 19.79V14.6L3 12M21 12l-4.5 2.6v5.19M3.27 6.96L12 12.01l8.73-5.05M12 22.08V12" />
          </svg>
        </div>
        <div>
          <div className="arch-enterprise-title">{enterprise.title}</div>
          <div className="arch-enterprise-sub">{enterprise.subtitle}</div>
        </div>
      </div>
    </div>
  );
}

/* ===== 组织架构树：总经理 → 副总 / 生产厂长 ===== */
function OrgTree() {
  const { org } = ARCHITECTURE;
  return (
    <div className="arch-orgtree">
      {/* 总经理 */}
      <div className="arch-org-ceo">
        <div className="arch-org-ceo-name">{org.ceo.name}</div>
        <div className="arch-org-ceo-en">{org.ceo.en}</div>
      </div>
      {/* 连接线 */}
      <div className="arch-org-trunk" />
      <div className="arch-org-branches">
        {org.branches.map((b, i) => (
          <div className="arch-org-branch" key={i}>
            <div className="arch-org-drop" />
            <div className="arch-org-branch-node">
              <div className="arch-org-branch-name">{b.name}</div>
              <div className="arch-org-branch-en">{b.en}</div>
            </div>
            <div className="arch-org-drop" />
            <div className="arch-org-depts">
              {b.deptIds.map((id) => {
                const d = getDepartmentById(id);
                if (!d) return null;
                return (
                  <span key={id} className="arch-org-leaf" style={{ '--leaf-color': d.color }}>
                    {d.name}
                  </span>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ===== 第一层：部门-岗位-业务场景 ===== */
function DepartmentLayer({ onScenarioClick }) {
  const { departments } = ARCHITECTURE;
  return (
    <div className="arch-layer arch-dept-layer">
      <div className="arch-layer-label">
        <span className="arch-layer-tag">第一层</span>
        部门 - 岗位 - 业务场景层（业务入口 · 点击查看对应智能体）
      </div>
      <div className="arch-dept-grid">
        {departments.map((dept) => (
          <div className="arch-dept-col" key={dept.id}>
            <div className="arch-dept-header" style={{ borderColor: dept.color }}>
              <span className="arch-dept-dot" style={{ background: dept.color }}></span>
              <div className="arch-dept-head-txt">
                <span className="arch-dept-name">{dept.name}</span>
                <span className="arch-dept-en">{dept.en}</span>
              </div>
            </div>
            {/* 子岗位 */}
            <div className="arch-pos-list">
              {dept.positions.map((p, i) => (
                <span key={i} className="arch-pos-tag" style={{ color: dept.color, borderColor: dept.color + '55' }}>
                  {p}
                </span>
              ))}
            </div>
            {/* 业务场景 */}
            <div className="arch-scenario-list">
              {dept.scenarios.map((s) => (
                <button
                  key={s.id}
                  className="arch-scenario-box"
                  onClick={() => onScenarioClick(s.id)}
                  style={{ '--dept-color': dept.color }}
                >
                  {s.name}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ===== 第二层：AI 智能体集群 ===== */
function AgentLayer({ onAgentClick }) {
  const { agents } = ARCHITECTURE;
  return (
    <div className="arch-layer arch-agent-layer">
      <div className="arch-layer-label">
        <span className="arch-layer-tag">第二层</span>
        垂直业务 AI 智能体集群（数字员工层）
      </div>
      <div className="arch-agent-strip">
        {agents.map((a) => (
          <button
            key={a.id}
            className="arch-agent-chip"
            onClick={() => onAgentClick(a.id)}
            style={{ '--agent-color': a.color }}
          >
            <span className="arch-agent-chip-emoji">{a.emoji}</span>
            <span className="arch-agent-chip-name">{a.name}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

/* ===== 第三层：Agent 协同调度中枢 ===== */
function CoordinatorLayer() {
  const { coordinator } = ARCHITECTURE;
  return (
    <div className="arch-layer arch-coord-layer">
      <div className="arch-layer-label">
        <span className="arch-layer-tag">第三层</span>
        {coordinator.title}（{coordinator.subtitle}）
      </div>
      <div className="arch-coord-box">
        <div className="arch-coord-grid">
          {coordinator.capabilities.map((c, i) => (
            <span key={i} className="arch-coord-item">{c}</span>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ===== 第四层：AI 能力中台 ===== */
function PlatformLayer() {
  const { platform } = ARCHITECTURE;
  return (
    <div className="arch-layer arch-platform-layer">
      <div className="arch-layer-label">
        <span className="arch-layer-tag">第四层</span>
        {platform.title}（{platform.subtitle}）
      </div>
      <div className="arch-platform-box">
        <div className="arch-cap-grid">
          {platform.capabilities.map((c, i) => (
            <div key={i} className="arch-cap-item">
              {c.icon && <span className="arch-cap-icon">{c.icon}</span>}
              <span>{c.name}</span>
            </div>
          ))}
        </div>
        <div className="arch-adapter-bar">
          <span className="arch-adapter-label">企业系统对接适配器</span>
          <span className="arch-adapter-list">{platform.adapters}</span>
        </div>
      </div>
    </div>
  );
}

/* ===== 第五层：技术底座 ===== */
function TechLayer() {
  const { techStack, deploymentModes, dataFlow } = ARCHITECTURE;
  return (
    <div className="arch-layer arch-tech-layer">
      <div className="arch-layer-label">
        <span className="arch-layer-tag">第五层</span>
        {techStack.title}
      </div>
      <div className="arch-tech-grid">
        {techStack.items.map((item, i) => (
          <div key={i} className="arch-tech-item">
            <div className="arch-tech-item-icon">{item.icon}</div>
            <div className="arch-tech-item-cat">{item.category}</div>
            <div className="arch-tech-item-desc">{item.desc}</div>
          </div>
        ))}
      </div>
      {/* 部署模式 */}
      <div className="arch-deploy-row">
        {deploymentModes.map((m, i) => (
          <div key={i} className="arch-deploy-card">
            <div className="arch-deploy-icon">{m.icon}</div>
            <div className="arch-deploy-name">{m.name}</div>
            <div className="arch-deploy-desc">{m.desc}</div>
          </div>
        ))}
      </div>
      {/* 数据流闭环 */}
      <div className="arch-dataflow">
        <div className="arch-dataflow-title">{dataFlow.title}（智能制造业务闭环）</div>
        <div className="arch-dataflow-steps">
          {dataFlow.steps.map((step, i) => (
            <React.Fragment key={i}>
              <span className="arch-dataflow-step">{step}</span>
              {i < dataFlow.steps.length - 1 && <span className="arch-dataflow-arrow">→</span>}
            </React.Fragment>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ===== 侧边栏：场景/智能体详情 ===== */
function DetailSidebar({ data, onClose }) {
  if (!data) return null;
  const { department, scenario, agent } = data;
  const deptAgents = getAgentsByDepartment(department.id);

  return (
    <>
      <div className="arch-sidebar-overlay" onClick={onClose} />
      <div className="arch-sidebar">
        <div className="arch-sidebar-header">
          <div>
            <div className="arch-sidebar-dept" style={{ color: department.color }}>
              <span className="arch-sidebar-dept-dot" style={{ background: department.color }}></span>
              {department.name}
              {department.positions && (
                <span className="arch-sidebar-dept-pos"> · {department.positions.join(' / ')}</span>
              )}
            </div>
            <h3 className="arch-sidebar-scenario">{scenario.name}</h3>
          </div>
          <button className="arch-sidebar-close" onClick={onClose}></button>
        </div>

        {agent && (
          <div className="arch-sidebar-agent">
            <div className="arch-sidebar-agent-head">
              <div className="arch-sidebar-agent-avatar" style={{ background: agent.color + '20', borderColor: agent.color }}>
                <span>{agent.emoji}</span>
              </div>
              <div>
                <div className="arch-sidebar-agent-name">{agent.name}</div>
                <div className="arch-sidebar-agent-role">{agent.role}</div>
              </div>
            </div>
            <p className="arch-sidebar-agent-desc">{agent.desc}</p>
            <div className="arch-sidebar-agent-caps">
              {agent.capabilities.map((c, i) => (
                <span key={i} className="arch-cap-tag" style={{ borderColor: agent.color + '60', color: agent.color }}>{c}</span>
              ))}
            </div>
          </div>
        )}

        {/* 同部门其他智能体 */}
        {deptAgents.length > 1 && (
          <div className="arch-sidebar-related">
            <div className="arch-sidebar-related-title">同部门其他智能体</div>
            {deptAgents.filter((a) => a.id !== agent?.id).map((a) => (
              <div key={a.id} className="arch-sidebar-related-item">
                <span className="arch-sidebar-related-emoji">{a.emoji}</span>
                <div>
                  <div className="arch-sidebar-related-name">{a.name}</div>
                  <div className="arch-sidebar-related-role">{a.role}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  );
}

/* ===== 主组件 ===== */
export default function ArchitectureDiagram() {
  const [sidebarData, setSidebarData] = useState(null);

  const handleScenarioClick = (scenarioId) => {
    const data = findAgentByScenario(scenarioId);
    if (data) setSidebarData(data);
  };

  const handleAgentClick = (agentId) => {
    // 找到该智能体对应的第一个场景
    for (const dept of ARCHITECTURE.departments) {
      const scenario = dept.scenarios.find((s) => s.agentId === agentId);
      if (scenario) {
        setSidebarData({ department: dept, scenario, agent: ARCHITECTURE.agents.find((a) => a.id === agentId) });
        return;
      }
    }
  };

  return (
    <section className="arch-section" id="architecture">
      <div className="arch-container">
        {/* 标题 */}
        <div className="arch-main-title">
          <div className="arch-title-tag">
            <span className="arch-title-tag-line"></span>
            整体解决方案架构
            <span className="arch-title-tag-line"></span>
          </div>
          <h2 className="arch-title-text">
            <span className="arch-title-gradient">智能制造</span> AI 智能体整体解决方案
          </h2>
          <p className="arch-title-desc">
            组织架构 → 部门岗位 → 业务场景 → 智能体集群 → 协同调度 → 能力中台 → 技术底座
          </p>
        </div>

        {/* 架构图 */}
        <div className="arch-diagram">
          <EnterpriseLayer />
          <OrgTree />
          <LayerConnector />
          <DepartmentLayer onScenarioClick={handleScenarioClick} />
          <LayerConnector />
          <AgentLayer onAgentClick={handleAgentClick} />
          <LayerConnector />
          <CoordinatorLayer />
          <LayerConnector />
          <PlatformLayer />
          <LayerConnector />
          <TechLayer />
        </div>
      </div>

      {/* 侧边栏 */}
      <DetailSidebar data={sidebarData} onClose={() => setSidebarData(null)} />
    </section>
  );
}
