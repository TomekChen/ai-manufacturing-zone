// 智能制造 AI 智能体整体解决方案 — 五层架构数据
// 原型阶段硬编码，数据结构设计为后续可接入管理后台配置

export const ARCHITECTURE = {
  // 第一层：企业顶层
  enterprise: {
    title: '智能制造企业',
    subtitle: '制造型企业 / 智能工厂 / 数字化车间',
  },

  // 第一层：部门-业务场景
  departments: [
    {
      id: 'production',
      name: '生产部',
      color: '#3b82f6',
      scenarios: [
        { id: 'prod-schedule', name: '生产排程', agentId: 'agent-production' },
        { id: 'prod-exception', name: '产线异常处置', agentId: 'agent-production' },
        { id: 'prod-capacity', name: '产能分析', agentId: 'agent-production' },
        { id: 'prod-order', name: '工单跟踪', agentId: 'agent-production' },
      ],
    },
    {
      id: 'quality',
      name: '品质部',
      color: '#22c55e',
      scenarios: [
        { id: 'qa-visual', name: 'AI视觉质检', agentId: 'agent-quality' },
        { id: 'qa-rootcause', name: '不良根因分析', agentId: 'agent-quality' },
        { id: 'qa-spc', name: 'SPC数据分析', agentId: 'agent-quality' },
        { id: 'qa-report', name: '质检报告生成', agentId: 'agent-quality' },
      ],
    },
    {
      id: 'warehouse',
      name: '仓储物流部',
      color: '#f59e0b',
      scenarios: [
        { id: 'wh-inventory', name: '库存优化', agentId: 'agent-warehouse' },
        { id: 'wh-agv', name: 'AGV调度', agentId: 'agent-warehouse' },
        { id: 'wh-audit', name: '出入库稽核', agentId: 'agent-warehouse' },
        { id: 'wh-supply', name: '供应链预警', agentId: 'agent-warehouse' },
      ],
    },
    {
      id: 'equipment',
      name: '设备运维部',
      color: '#ef4444',
      scenarios: [
        { id: 'eq-predict', name: '预测性维护', agentId: 'agent-equipment' },
        { id: 'eq-diagnose', name: '故障诊断', agentId: 'agent-equipment' },
        { id: 'eq-maintain', name: '保养计划', agentId: 'agent-equipment' },
        { id: 'eq-spare', name: '备件管理', agentId: 'agent-equipment' },
      ],
    },
    {
      id: 'rnd',
      name: '研发工艺部',
      color: '#a855f7',
      scenarios: [
        { id: 'rd-simulate', name: '工艺仿真优化', agentId: 'agent-rnd' },
        { id: 'rd-trial', name: '新品试产分析', agentId: 'agent-rnd' },
        { id: 'rd-bom', name: 'BOM智能校对', agentId: 'agent-rnd' },
        { id: 'rd-doc', name: '图纸文档问答', agentId: 'agent-rnd' },
      ],
    },
  ],

  // 第二层：AI 智能体集群
  agents: [
    {
      id: 'agent-production',
      emoji: '📋',
      name: '生产调度智能体',
      role: '智能排产与产线管控',
      color: '#3b82f6',
      desc: '多约束优化排产引擎，在交期、产能、物料、成本之间找到最优平衡点，实现产线异常实时响应与工单全链路跟踪。',
      capabilities: [
        '排产效率提升 10 倍',
        '支持 50+ 约束条件',
        '动态插单快速响应',
        '产能利用率提升 15%',
        '产线异常实时告警',
        '工单全链路跟踪',
      ],
    },
    {
      id: 'agent-quality',
      emoji: '🔍',
      name: '质检分析智能体',
      role: 'AI 视觉质检与品质管控',
      color: '#22c55e',
      desc: '基于深度学习的视觉检测系统，支持多种缺陷类型的实时识别与分类，结合 SPC 统计过程控制实现品质趋势预警。',
      capabilities: [
        '检测精度 ≥ 99.5%',
        '支持 20+ 缺陷类型',
        '毫秒级响应速度',
        '缺陷趋势统计分析',
        '质检报告自动生成',
        '不良品根因追溯',
      ],
    },
    {
      id: 'agent-warehouse',
      emoji: '📦',
      name: '仓储供应链智能体',
      role: '库存优化与物流调度',
      color: '#f59e0b',
      desc: '智能库存水位管理与 AGV 调度协同，打通出入库稽核与供应链预警，实现仓储物流全链路智能化。',
      capabilities: [
        '库存周转率提升 30%',
        'AGV 路径最优调度',
        '出入库自动稽核',
        '供应链到货预警',
        '安全库存动态计算',
        '物流成本优化分析',
      ],
    },
    {
      id: 'agent-equipment',
      emoji: '🔧',
      name: '设备运维智能体',
      role: '预测性维护与故障诊断',
      color: '#ef4444',
      desc: '7×24 小时监测设备健康状态，通过振动频谱分析和温度趋势预测，提前发现潜在故障并自动生成维护工单。',
      capabilities: [
        '故障预警提前 7-30 天',
        '振动频谱实时分析',
        '自动生成维护工单',
        '备件库存智能建议',
        '保养计划自动排程',
        '设备OEE实时监控',
      ],
    },
    {
      id: 'agent-rnd',
      emoji: '🧪',
      name: '工艺研发智能体',
      role: '工艺仿真与知识管理',
      color: '#a855f7',
      desc: '融合工艺仿真、BOM 校对与文档问答能力，加速新品试产流程，构建企业工艺知识库。',
      capabilities: [
        '工艺参数智能寻优',
        'BOM 自动校对纠错',
        '图纸文档智能问答',
        '仿真数据自动分析',
        '新品试产周期缩短 40%',
        '工艺知识沉淀管理',
      ],
    },
    {
      id: 'agent-gm',
      emoji: '📊',
      name: '经营决策智能体',
      role: '工厂经营分析与决策支持',
      color: '#06b6d4',
      desc: '面向总经理/经营层的全局数据视图，跨部门数据汇总分析，自动生成月度经营分析报告与决策建议。',
      capabilities: [
        '工厂经营实时看板',
        '跨部门数据自动汇总',
        '月度经营分析报告',
        '关键指标异常预警',
        '决策方案智能推荐',
        '行业对标分析',
      ],
    },
  ],

  // 第三层：Agent 协同调度中枢
  coordinator: {
    title: 'Agent 协同调度中枢',
    subtitle: '多智能体编排层',
    capabilities: [
      '智能体任务分发',
      '跨部门协同调度',
      '任务优先级管理',
      '会话记忆管理',
      '工作流引擎',
      '事件触发器',
      '告警路由',
      '多Agent协作决策',
    ],
  },

  // 第四层：AI 能力中台
  platform: {
    title: 'AI 能力中台层',
    subtitle: '共享能力',
    capabilities: [
      { name: 'RAG知识库', icon: '📚' },
      { name: 'OCR文档解析', icon: '📄' },
      { name: '视觉识别能力', icon: '👁️' },
      { name: '数据洞察引擎', icon: '📈' },
      { name: '数字孪生接口', icon: '' },
      { name: '工具调用库', icon: '🛠️' },
      { name: 'API连接器', icon: '' },
      { name: '报表生成器', icon: '📊' },
      { name: '自然语言问答', icon: '' },
      { name: '流程自动化RPA', icon: '⚙️' },
    ],
    adapters: 'ERP / MES / WMS / QMS / PLM / SCADA / 设备PLC / 工业数据库',
  },

  // 第五层：技术底座
  techStack: {
    title: '技术底座 & 算力基础设施层',
    items: [
      {
        category: '大模型基座',
        desc: '通用大模型 / 工业垂类大模型',
        icon: '🧠',
      },
      {
        category: '数据存储',
        desc: '向量数据库、时序数据库、业务数据库',
        icon: '🗄️',
      },
      {
        category: '算力资源',
        desc: 'GPU服务器 / 智跃一体机 / 私有云 / 边缘算力 / 速桥云算力',
        icon: '⚡',
      },
      {
        category: '部署方案',
        desc: '私有化部署 / 混合云部署 / 公有云方案',
        icon: '☁️',
      },
    ],
  },

  // 部署模式
  deploymentModes: [
    {
      name: '私有化本地部署',
      desc: '一体机部署在工厂内网，数据不出厂',
      icon: '🏭',
    },
    {
      name: '混合云部署',
      desc: '智能体调度云端，工厂设备数据本地边缘侧处理',
      icon: '',
    },
    {
      name: '云端 SaaS 模式',
      desc: '智能体托管算力平台（速桥云），工厂通过 API 接入',
      icon: '☁️',
    },
  ],

  // 数据流闭环
  dataFlow: {
    title: '横向数据流闭环',
    steps: [
      '设备采集数据',
      '业务系统 (MES/PLC)',
      '中台适配器',
      'AI 智能体分析决策',
      '下发指令回产线执行 + 告警推送部门负责人',
    ],
  },
};

// 根据场景 ID 查找对应智能体
export function findAgentByScenario(scenarioId) {
  for (const dept of ARCHITECTURE.departments) {
    const scenario = dept.scenarios.find((s) => s.id === scenarioId);
    if (scenario) {
      const agent = ARCHITECTURE.agents.find((a) => a.id === scenario.agentId);
      return { department: dept, scenario, agent };
    }
  }
  return null;
}

// 根据智能体 ID 查找
export function findAgentById(agentId) {
  return ARCHITECTURE.agents.find((a) => a.id === agentId);
}

// 获取某部门下所有场景对应的智能体（去重）
export function getAgentsByDepartment(deptId) {
  const dept = ARCHITECTURE.departments.find((d) => d.id === deptId);
  if (!dept) return [];
  const agentIds = [...new Set(dept.scenarios.map((s) => s.agentId))];
  return agentIds.map((id) => findAgentById(id)).filter(Boolean);
}
