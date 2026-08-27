// 智能制造 AI 智能体整体解决方案 — 五层架构数据
// 通用离散/压铸制造业组织架构（部门-岗位-场景-智能体映射）
// 原型阶段硬编码，数据结构设计为后续可接入管理后台配置

export const ARCHITECTURE = {
  // 业务顶层：通用制造企业
  enterprise: {
    title: '智能制造企业',
    subtitle: 'AI 智能体赋能 · 制造业全流程数字化转型',
  },

  // 组织架构树：总经理 → 副总 / 生产厂长 → 8 部门
  org: {
    ceo: { name: '总经理', en: 'General Manager' },
    branches: [
      {
        name: '副总',
        en: 'Deputy General Manager',
        deptIds: ['finance', 'engineering', 'admin', 'business'],
      },
      {
        name: '生产厂长',
        en: 'Production Director',
        deptIds: ['pcm', 'production', 'mold', 'quality'],
      },
    ],
  },

  // 第一层：部门-业务场景（真实 8 部门 + 子岗位）
  departments: [
    {
      id: 'finance',
      name: '财务部',
      en: 'Finance',
      color: '#10b981',
      positions: ['会计', '出纳'],
      scenarios: [
        { id: 'fin-reimburse', name: '智能报销审核', agentId: 'agent-finance' },
        { id: 'fin-cost', name: '成本核算分析', agentId: 'agent-finance' },
        { id: 'fin-ar', name: '应收应付预警', agentId: 'agent-finance' },
      ],
    },
    {
      id: 'engineering',
      name: '工程部',
      en: 'Engineering',
      color: '#3b82f6',
      positions: ['项目部', '设计部'],
      scenarios: [
        { id: 'eng-project', name: '项目交付跟踪', agentId: 'agent-engineering' },
        { id: 'eng-bom', name: '图纸BOM问答', agentId: 'agent-engineering' },
        { id: 'eng-trial', name: '新品试产分析', agentId: 'agent-engineering' },
      ],
    },
    {
      id: 'admin',
      name: '行政部',
      en: 'Administrative',
      color: '#14b8a6',
      positions: ['人事', '后勤', '设备科', 'IT'],
      scenarios: [
        { id: 'adm-attend', name: '智能考勤排班', agentId: 'agent-admin' },
        { id: 'adm-equip', name: '设备预测性维护', agentId: 'agent-equipment' },
        { id: 'adm-it', name: 'IT运维助手', agentId: 'agent-admin' },
      ],
    },
    {
      id: 'business',
      name: '业务部',
      en: 'Business',
      color: '#6366f1',
      positions: ['客服', '跟单'],
      scenarios: [
        { id: 'biz-order', name: '订单智能跟单', agentId: 'agent-business' },
        { id: 'biz-cs', name: '智能客服问答', agentId: 'agent-business' },
        { id: 'biz-lead', name: '交期预警', agentId: 'agent-business' },
      ],
    },
    {
      id: 'pcm',
      name: 'PCM部',
      en: 'PCM',
      color: '#f59e0b',
      positions: ['PC', 'MC', '仓库'],
      scenarios: [
        { id: 'pcm-pc', name: '生产计划排程', agentId: 'agent-pcm' },
        { id: 'pcm-mc', name: '物料齐套分析', agentId: 'agent-pcm' },
        { id: 'pcm-wh', name: '库存水位优化', agentId: 'agent-pcm' },
      ],
    },
    {
      id: 'production',
      name: '生产部',
      en: 'Production',
      color: '#ef4444',
      positions: ['压铸', '后加工', '装检'],
      scenarios: [
        { id: 'prod-cast', name: '压铸排产', agentId: 'agent-production' },
        { id: 'prod-exception', name: '产线异常处置', agentId: 'agent-production' },
        { id: 'prod-capacity', name: '产能瓶颈分析', agentId: 'agent-production' },
      ],
    },
    {
      id: 'mold',
      name: '模具部',
      en: 'Mold',
      color: '#a855f7',
      positions: ['制模', '加工'],
      scenarios: [
        { id: 'mold-review', name: '模具设计评审', agentId: 'agent-mold' },
        { id: 'mold-progress', name: '制模进度跟踪', agentId: 'agent-mold' },
        { id: 'mold-cnc', name: 'CNC加工排程', agentId: 'agent-mold' },
      ],
    },
    {
      id: 'quality',
      name: '品质部',
      en: 'Quality',
      color: '#06b6d4',
      positions: ['QE', 'QC', '检测中心', '体系'],
      scenarios: [
        { id: 'qa-visual', name: 'AI视觉质检', agentId: 'agent-quality' },
        { id: 'qa-rootcause', name: '不良根因分析', agentId: 'agent-quality' },
        { id: 'qa-spc', name: 'SPC数据分析', agentId: 'agent-quality' },
      ],
    },
  ],

  // 第二层：AI 智能体集群（数字员工层）
  agents: [
    {
      id: 'agent-production',
      emoji: '🏭',
      name: '生产调度智能体',
      role: '生产排产与产线管控',
      color: '#ef4444',
      desc: '面向压铸/机加工全流程的智能排产引擎，在交期、机台、模具、物料之间找到最优平衡，实时响应产线异常与产能瓶颈。',
      capabilities: ['机台智能排产', '产线异常实时告警', '产能瓶颈分析', '工单全链路跟踪', '换模时间优化', '生产日报自动生成'],
    },
    {
      id: 'agent-quality',
      emoji: '🔍',
      name: '质检分析智能体',
      role: '高精度品质管控',
      color: '#06b6d4',
      desc: '融合二次元测量、视觉检测与 SPC 统计过程控制，保障关键尺寸精度与全流程低缺陷率（CPK>1.67、缺陷率 ≤50PPM）的高品质管控。',
      capabilities: ['AI视觉缺陷检测', 'SPC过程能力分析', '不良根因追溯', '检测数据自动判定', '气密性零泄漏监控', '质检报告自动生成'],
    },
    {
      id: 'agent-pcm',
      emoji: '📦',
      name: '供应链计划智能体',
      role: '生产计划与物料齐套',
      color: '#f59e0b',
      desc: '打通 PC 生产计划、MC 物料控制与仓库出入库，实现物料齐套分析、库存水位优化与到货预警，保障产线不断料。',
      capabilities: ['生产计划自动编排', '物料齐套分析', '库存水位优化', '安全库存动态计算', '到货延迟预警', '仓库出入库稽核'],
    },
    {
      id: 'agent-mold',
      emoji: '🛠️',
      name: '模具工艺智能体',
      role: '模具全生命周期管理',
      color: '#a855f7',
      desc: '覆盖模具设计评审、制作进度跟进、CNC加工排程到试模验收全流程，沉淀模具结构图、BOM 表与验收报告，缩短制模周期。',
      capabilities: ['模具设计评审辅助', '制模进度跟踪', 'CNC加工排程', '零配件铜公检测提醒', '模具寿命管理', '试模数据分析'],
    },
    {
      id: 'agent-engineering',
      emoji: '📐',
      name: '工艺研发智能体',
      role: '项目交付与工艺知识',
      color: '#3b82f6',
      desc: '支撑工程部项目部与设计部，提供图纸/BOM 智能问答、新品试产数据分析与项目交付跟踪，构建企业工艺知识库。',
      capabilities: ['图纸文档智能问答', 'BOM 自动校对', '新品试产分析', '工艺参数寻优', '项目进度跟踪', '技术知识沉淀'],
    },
    {
      id: 'agent-business',
      emoji: '🤝',
      name: '业务跟单智能体',
      role: '订单交付与客户协同',
      color: '#6366f1',
      desc: '面向业务部客服与跟单岗位，实现订单智能跟单、交期预警与客户咨询问答，提升订单履约率与客户满意度。',
      capabilities: ['订单状态自动跟踪', '交期风险预警', '智能客服问答', '客户需求解析', '报价辅助生成', '客户档案沉淀'],
    },
    {
      id: 'agent-equipment',
      emoji: '🔧',
      name: '设备运维智能体',
      role: '压铸/加工设备预测性维护',
      color: '#f97316',
      desc: '7×24 监测压铸机、注塑机、CNC 等核心设备健康状态，通过振动与温度趋势预测提前发现故障，自动生成保养工单。',
      capabilities: ['设备健康实时监测', '故障预警提前 7-30 天', '保养计划自动生成', '备件库存智能建议', '设备 OEE 分析', '维修工单派发'],
    },
    {
      id: 'agent-admin',
      emoji: '👥',
      name: '行政人事智能体',
      role: '人事考勤与 IT 运维',
      color: '#14b8a6',
      desc: '服务行政部人事、后勤与 IT 岗位，提供智能考勤排班、员工服务问答与 IT 运维自助，减轻行政事务负担。',
      capabilities: ['智能考勤排班', '人事政策问答', '后勤申请处理', 'IT 故障自助', '员工服务助手', '通知自动触达'],
    },
    {
      id: 'agent-finance',
      emoji: '💰',
      name: '财务分析智能体',
      role: '成本核算与账务智能',
      color: '#10b981',
      desc: '面向财务部会计与出纳，提供智能报销审核、生产成本核算与应收应付预警，让财务数据实时可查、异常自动提示。',
      capabilities: ['发票智能识别审核', '生产成本核算', '毛利异常分析', '应收应付预警', '财务报表自动生成', '税务风险提醒'],
    },
    {
      id: 'agent-gm',
      emoji: '📊',
      name: '经营决策智能体',
      role: '总经理经营驾驶舱',
      color: '#0ea5e9',
      desc: '面向总经理/经营层，跨部门汇总生产、品质、交付、成本数据，生成经营看板与月度分析报告，辅助科学决策。',
      capabilities: ['工厂经营看板', '跨部门数据汇总', '月度经营分析', '关键指标预警', '决策方案推荐', '行业对标分析'],
    },
  ],

  // 第三层：Agent 协同调度中枢
  coordinator: {
    title: 'Agent 协同调度中枢',
    subtitle: '多智能体编排层',
    capabilities: [
      '智能体任务分发', '跨部门协同调度', '任务优先级管理', '会话记忆管理',
      '工作流引擎', '事件触发器', '告警路由', '多Agent协作决策',
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
      { name: '数字孪生接口', icon: '🏗️' },
      { name: '工具调用库', icon: '🛠️' },
      { name: 'API连接器', icon: '🔌' },
      { name: '报表生成器', icon: '📊' },
      { name: '自然语言问答', icon: '💬' },
      { name: '流程自动化RPA', icon: '⚙️' },
    ],
    adapters: 'ERP / MES / WMS / QMS / PLM / SCADA / 设备PLC / 工业数据库',
  },

  // 第五层：技术底座
  techStack: {
    title: '技术底座 & 算力基础设施层',
    items: [
      { category: '大模型基座', desc: '通用大模型 / 工业垂类大模型', icon: '🧠' },
      { category: '数据存储', desc: '向量数据库、时序数据库、业务数据库', icon: '🗄️' },
      { category: '算力资源', desc: 'GPU服务器 / 智跃一体机 / 私有云 / 边缘算力 / 速桥云算力', icon: '⚡' },
      { category: '部署方案', desc: '私有化部署 / 混合云部署 / 公有云方案', icon: '☁️' },
    ],
  },

  // 部署模式
  deploymentModes: [
    { name: '私有化本地部署', desc: '一体机部署在工厂内网，数据不出厂', icon: '🏭' },
    { name: '混合云部署', desc: '智能体调度云端，工厂设备数据本地边缘侧处理', icon: '🔗' },
    { name: '云端 SaaS 模式', desc: '智能体托管算力平台（速桥云），工厂通过 API 接入', icon: '☁️' },
  ],

  // 数据流闭环
  dataFlow: {
    title: '横向数据流闭环',
    steps: [
      '设备采集数据', '业务系统 (MES/PLC)', '中台适配器',
      'AI 智能体分析决策', '下发指令回产线执行 + 告警推送部门负责人',
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

// 按 id 取部门
export function getDepartmentById(deptId) {
  return ARCHITECTURE.departments.find((d) => d.id === deptId);
}
