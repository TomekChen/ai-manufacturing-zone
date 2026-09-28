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
        {
          id: 'fin-reimburse', name: '智能报销审核', agentId: 'agent-finance',
          feature: {
            category: '财务核算',
            summary: '员工贴票报销，财务要逐张核对发票真伪、金额、科目与预算，月底常常堆积如山。AI 智能体自动识别发票、校验合规、生成凭证，只有异常单据才转人工复核。',
            metrics: [
              { value: '99.2%', label: '发票识别准确率' },
              { value: '-70%', label: '报销处理时长' },
              { value: '-60%', label: '人工复核量' },
            ],
            flowLabel: '处理流程',
            flow: ['拍照上传票据', 'OCR 识别发票', '合规与预算校验', '自动生成凭证', '异常转人工'],
            before: [
              '逐张手工核对发票，月底集中爆量易出错',
              '假票、重复报销靠人眼难以发现',
              '员工垫资久、报销体验差',
            ],
            after: [
              '秒级识别发票自动入账，员工当天到账',
              '假票与重复报销系统自动拦截',
              '财务从核对转向异常处理与经营分析',
            ],
          },
        },
        {
          id: 'fin-cost', name: '成本核算分析', agentId: 'agent-finance',
          feature: {
            category: '财务核算',
            summary: '制造成本要把料、工、费归集分摊到每张工单，传统靠月底手工分摊，既滞后又不准。AI 智能体实时抓取 MES / ERP 数据自动归集分摊，随时给出成本与毛利。',
            metrics: [
              { value: '天→小时', label: '核算周期' },
              { value: '+15%', label: '成本归集准确率' },
              { value: '提前7天', label: '毛利异常发现' },
            ],
            flowLabel: '处理流程',
            flow: ['采集工单领料', '归集人工制费', '自动分摊', '计算单位成本', '毛利异常预警'],
            before: [
              '月底手工分摊，成本数据严重滞后',
              '分摊规则靠经验，口径不稳定',
              '毛利异常往往事后才发现',
            ],
            after: [
              '成本实时归集，随时可查',
              '分摊规则统一，口径一致可追溯',
              '毛利异常即时预警，辅助定价与降本',
            ],
          },
        },
        {
          id: 'fin-ar', name: '应收应付预警', agentId: 'agent-finance',
          feature: {
            category: '资金风控',
            summary: '客户回款、供应商付款节点繁多，靠人盯账期容易漏，逾期直接影响现金流。AI 智能体自动跟踪账期，临期分级提醒并生成催收 / 付款建议。',
            metrics: [
              { value: '-45%', label: '逾期应收' },
              { value: '+60%', label: '对账效率' },
              { value: '92%', label: '现金流预测准确率' },
            ],
            flowLabel: '处理流程',
            flow: ['同步开票与合同', '计算账期', '临期分级预警', '推送催收建议', '回款核销'],
            before: [
              '账期靠人工盯表，逾期发现晚',
              '催收无据、口径不一',
              '现金流预测凭经验，波动大',
            ],
            after: [
              '临期自动分级提醒，逾期显著下降',
              '催收 / 付款建议自动生成',
              '现金流预测更准，资金安排更从容',
            ],
          },
        },
      ],
    },
    {
      id: 'engineering',
      name: '工程部',
      en: 'Engineering',
      color: '#3b82f6',
      positions: ['项目部', '设计部'],
      scenarios: [
        {
          id: 'eng-project', name: '项目交付跟踪', agentId: 'agent-engineering',
          feature: {
            category: '项目协同',
            summary: '新品项目节点多、跨部门，进度散落在群聊和表格里，延期常常后知后觉。AI 智能体自动汇总各任务状态，识别关键路径风险并提醒责任人。',
            metrics: [
              { value: '+22%', label: '项目按期率' },
              { value: '-80%', label: '进度收集耗时' },
              { value: '提前5天', label: '延期风险预警' },
            ],
            flowLabel: '处理流程',
            flow: ['拆解项目任务', '采集各节点进展', '识别关键路径', '延期风险预警', '推送责任人'],
            before: [
              '进度靠人问人催，信息滞后',
              '关键路径风险难提前发现',
              '跨部门协同责任不清',
            ],
            after: [
              '进度自动汇总，实时可视',
              '关键路径延期提前预警',
              '责任到人，协同更顺',
            ],
          },
        },
        {
          id: 'eng-bom', name: '图纸BOM问答', agentId: 'agent-engineering',
          feature: {
            category: '工艺知识',
            summary: '工程师查图纸、找版本、比对 BOM 差异，要在海量文件里翻找。AI 智能体基于图纸与 BOM 知识库做自然语言问答，秒级给出结果并附出处。',
            metrics: [
              { value: '-85%', label: '查图找料时间' },
              { value: '94%', label: '问答准确率' },
              { value: '-70%', label: '版本误用' },
            ],
            flowLabel: '处理流程',
            flow: ['自然语言提问', '检索图纸 / BOM 库', '定位有效版本', '生成答案', '附来源溯源'],
            before: [
              '图纸版本多，找对最新版费时',
              'BOM 差异靠人工逐项比对',
              '工艺知识散在个人手里难沉淀',
            ],
            after: [
              '秒级定位有效版本与差异',
              '答案附出处，可追溯可信',
              '工艺知识沉淀成企业知识库',
            ],
          },
        },
        {
          id: 'eng-trial', name: '新品试产分析', agentId: 'agent-engineering',
          feature: {
            category: '工艺知识',
            summary: '试产数据多、问题杂，靠人工整理报告慢且不全。AI 智能体自动汇总试产良率、尺寸与工艺参数，定位问题项并给出改善建议。',
            metrics: [
              { value: '天→分钟', label: '试产报告生成' },
              { value: '+50%', label: '问题定位效率' },
              { value: '+12%', label: '一次试产成功率' },
            ],
            flowLabel: '处理流程',
            flow: ['采集试产数据', '关联工艺参数', '定位不良项', '生成分析报告', '给出改善建议'],
            before: [
              '试产数据分散，人工汇总费时',
              '问题项靠经验判断，易遗漏',
              '报告格式不统一、复用性差',
            ],
            after: [
              '数据自动汇总，报告分钟级生成',
              '不良项精准定位',
              '改善建议沉淀，提升一次成功率',
            ],
          },
        },
      ],
    },
    {
      id: 'admin',
      name: '行政部',
      en: 'Administrative',
      color: '#14b8a6',
      positions: ['人事', '后勤', '设备科', 'IT'],
      scenarios: [
        {
          id: 'adm-attend', name: '智能考勤排班', agentId: 'agent-admin',
          feature: {
            category: '人事行政',
            summary: '排班要兼顾工时、技能与合规，人工排一次要几小时还常返工。AI 智能体按规则与人力自动排班，员工还能自助问答考勤政策。',
            metrics: [
              { value: '-90%', label: '排班耗时' },
              { value: '+50%', label: '考勤异常处理效率' },
              { value: '99%', label: '工时合规率' },
            ],
            flowLabel: '处理流程',
            flow: ['采集出勤与需求', '匹配技能与工时', '自动生成排班', '冲突校验', '政策问答答疑'],
            before: [
              '手工排班费时且易违反工时规则',
              '调班、请假靠人工反复协调',
              '考勤政策咨询占用 HR 大量时间',
            ],
            after: [
              '自动排班满足多重约束，秒级完成',
              '调班冲突自动校验提醒',
              '考勤政策自助问答，HR 从答疑中解放',
            ],
          },
        },
        {
          id: 'adm-equip', name: '设备预测性维护', agentId: 'agent-equipment',
          feature: {
            category: '设备运维',
            summary: '压铸机、CNC 一旦非计划停机，损失巨大。AI 智能体 7×24 监测振动与温度趋势，提前预警故障并自动生成保养工单。',
            metrics: [
              { value: '-40%', label: '非计划停机' },
              { value: '提前7-30天', label: '故障预警' },
              { value: '+12%', label: '设备 OEE' },
            ],
            flowLabel: '处理流程',
            flow: ['采集设备传感数据', '趋势与异常分析', '故障概率预测', '提前预警', '自动生成保养工单'],
            before: [
              '事后维修，停机损失大',
              '定期保养一刀切，过保或欠保',
              '备件靠经验备，急用时缺货',
            ],
            after: [
              '故障提前预测，变事后为事前',
              '按需保养，兼顾成本与可靠',
              '备件建议智能生成，减少停机等待',
            ],
          },
        },
        {
          id: 'adm-it', name: 'IT运维助手', agentId: 'agent-admin',
          feature: {
            category: 'IT 服务',
            summary: '员工 IT 问题重复率高，运维被密码重置、装软件占满。AI 智能体做自助问答与常见故障自动处置，复杂问题才转人工。',
            metrics: [
              { value: '65%', label: '常见工单自助解决' },
              { value: '<2分钟', label: '平均响应' },
              { value: '-40%', label: '运维人力占用' },
            ],
            flowLabel: '处理流程',
            flow: ['员工描述故障', '意图识别', '知识库自助处置', '自动开工单', '疑难转人工'],
            before: [
              '重复问题反复占用运维人力',
              '报修排队，响应慢',
              '知识散落在个人，难复用',
            ],
            after: [
              '常见问题自助秒级解决',
              '自动分派工单，响应更快',
              '运维聚焦疑难，效率提升',
            ],
          },
        },
      ],
    },
    {
      id: 'business',
      name: '业务部',
      en: 'Business',
      color: '#6366f1',
      positions: ['客服', '跟单'],
      scenarios: [
        {
          id: 'biz-order',
          name: '订单智能跟单',
          agentId: 'agent-business',
          feature: {
            category: '业务跟单',
            summary:
              '客户下单后，订单进度散落在 ERP、MES、WMS 与物流系统里，跟单员要一个个系统翻、打电话催。AI 智能体打通这些系统，自动盯住每张订单的关键节点，交期有风险提前预警，客户问起秒级给出进度与原因。',
            metrics: [
              { value: '<30秒', label: '订单进度响应' },
              { value: '-73%', label: '人工跟单量' },
              { value: '+18分', label: '客户满意度 NPS' },
            ],
            flowLabel: '处理流程',
            flow: ['接收客户询单', '跨系统查订单状态', '识别延期风险', '生成进度回复', '异常升级人工'],
            before: [
              '跟单员在 ERP / MES / WMS 间反复横跳，查一单要十几分钟',
              '交期风险靠人工盯，往往到了节点才发现延误',
              '客户催单时答复口径不一，体验参差',
            ],
            after: [
              '7×24 自动盯单，进度查询秒级返回',
              '延期风险提前预警，主动通知客户',
              '跟单员从查单中解放，专注异常处理与客户关系',
            ],
          },
        },
        {
          id: 'biz-cs', name: '智能客服问答', agentId: 'agent-business',
          feature: {
            category: '客户服务',
            summary: '客户咨询重复且量大，客服疲于应对、夜间无人值守。AI 智能体 7×24 理解自然语言提问，秒级给出准确回复并沉淀常见问题。',
            metrics: [
              { value: '<10秒', label: '首次响应' },
              { value: '70%', label: '自动解决率' },
              { value: '-50%', label: '客服人力' },
            ],
            flowLabel: '处理流程',
            flow: ['多渠道接收咨询', '意图识别', '检索订单 / 知识库', '生成回复', '复杂转人工'],
            before: [
              '重复问题占用客服大量时间',
              '夜间与高峰无人应答，客户流失',
              '回复口径不一，质量参差',
            ],
            after: [
              '7×24 秒级响应，不受时间限制',
              '常见问题自动解决，人力聚焦复杂',
              '回复标准统一，满意度提升',
            ],
          },
        },
        {
          id: 'biz-lead', name: '交期预警', agentId: 'agent-business',
          feature: {
            category: '订单交付',
            summary: '交期牵动订单、排产、物料多条线，人工核对慢且易漏。AI 智能体实时联动多系统测算交期风险，提前预警并给应对建议。',
            metrics: [
              { value: '提前5-7天', label: '交期延误预警' },
              { value: '+15%', label: '准时交付率' },
              { value: '-35%', label: '客户投诉' },
            ],
            flowLabel: '处理流程',
            flow: ['汇总订单与排产', '联动物料产能', '测算交期', '风险分级预警', '推送应对建议'],
            before: [
              '交期靠多系统人工拼算，费时易错',
              '延误往往到临期才发现',
              '对客户答复缺乏依据',
            ],
            after: [
              '交期实时测算，延误提前预警',
              '主动通知客户，降低投诉',
              '答复有据，履约更稳',
            ],
          },
        },
      ],
    },
    {
      id: 'pcm',
      name: 'PCM部',
      en: 'PCM',
      color: '#f59e0b',
      positions: ['PC', 'MC', '仓库'],
      scenarios: [
        {
          id: 'pcm-pc', name: '生产计划排程', agentId: 'agent-pcm',
          feature: {
            category: '计划排程',
            summary: '排产要平衡交期、机台、模具与物料，靠 Excel 排一次要大半天。AI 智能体多约束自动排程，插单变更秒级重排。',
            metrics: [
              { value: '-85%', label: '排程耗时' },
              { value: '+18%', label: '计划达成率' },
              { value: '-25%', label: '换线时间' },
            ],
            flowLabel: '处理流程',
            flow: ['读取订单与产能', '多约束求解排程', '生成工单计划', '插单动态重排', '下发执行'],
            before: [
              '手工排程慢，难以兼顾多约束',
              '一有插单全盘重排，费时',
              '计划与实际脱节，达成率低',
            ],
            after: [
              '多约束自动排程，分钟级完成',
              '插单秒级重排，快速响应',
              '计划可执行性强，达成率提升',
            ],
          },
        },
        {
          id: 'pcm-mc', name: '物料齐套分析', agentId: 'agent-pcm',
          feature: {
            category: '物料控制',
            summary: '开工才发现缺料，停线等待成本高。AI 智能体按 BOM 与库存实时算齐套，缺料提前预警并建议采购。',
            metrics: [
              { value: '-60%', label: '缺料停线' },
              { value: '小时→分钟', label: '齐套核算' },
              { value: '-30%', label: '呆滞料' },
            ],
            flowLabel: '处理流程',
            flow: ['展开工单 BOM', '比对库存与在途', '计算齐套缺口', '缺料预警', '生成采购建议'],
            before: [
              '齐套靠人工查表，慢且易漏',
              '缺料往往到开工才发现',
              '采购与计划脱节',
            ],
            after: [
              '齐套实时核算，缺口一目了然',
              '缺料提前预警，保障不断料',
              '采购建议自动生成，协同更紧',
            ],
          },
        },
        {
          id: 'pcm-wh', name: '库存水位优化', agentId: 'agent-pcm',
          feature: {
            category: '库存管理',
            summary: '库存压多占资金、压少易断料，安全库存靠经验拍脑袋。AI 智能体按需求波动动态测算水位，自动预警积压与短缺。',
            metrics: [
              { value: '-20%', label: '库存资金占用' },
              { value: '-55%', label: '断料次数' },
              { value: '+25%', label: '库存周转率' },
            ],
            flowLabel: '处理流程',
            flow: ['采集出入库与需求', '分析消耗波动', '动态安全库存', '水位越限预警', '优化建议'],
            before: [
              '安全库存靠经验，长期不变',
              '积压与短缺并存，两头吃亏',
              '库存资金占用高',
            ],
            after: [
              '水位随需求动态调整',
              '积压与短缺双向预警',
              '资金占用下降，周转更快',
            ],
          },
        },
      ],
    },
    {
      id: 'production',
      name: '生产部',
      en: 'Production',
      color: '#ef4444',
      positions: ['压铸', '后加工', '装检'],
      scenarios: [
        {
          id: 'prod-cast', name: '压铸排产', agentId: 'agent-production',
          feature: {
            category: '生产排产',
            summary: '压铸机台、模具、合金料与交期相互交织，排产复杂。AI 智能体综合机台与模具状态自动排产，减少换模与等待。',
            metrics: [
              { value: '+15%', label: '设备利用率' },
              { value: '-30%', label: '换模时间' },
              { value: '+80%', label: '排产效率' },
            ],
            flowLabel: '处理流程',
            flow: ['读取订单与机台', '匹配模具与工艺', '自动排产', '换模优化', '下发工单'],
            before: [
              '排产靠经验，机台模具匹配费时',
              '换模顺序不合理，等待多',
              '插单变更重排困难',
            ],
            after: [
              '机台模具自动匹配，排产分钟级',
              '换模顺序优化，减少停机等待',
              '设备利用率与产出双升',
            ],
          },
        },
        {
          id: 'prod-exception', name: '产线异常处置', agentId: 'agent-production',
          feature: {
            category: '现场管控',
            summary: '产线一异常，靠人工层层上报，停机损失大。AI 智能体实时接收异常，自动定位原因、推送处置并升级跟踪。',
            metrics: [
              { value: '-70%', label: '异常响应时间' },
              { value: '-35%', label: '平均停机时长' },
              { value: '95%', label: '异常闭环率' },
            ],
            flowLabel: '处理流程',
            flow: ['接收异常上报', '关联数据分析', '定位根因', '推送处置方案', '超时升级'],
            before: [
              '异常靠人工逐级上报，响应慢',
              '处置经验不共享，重复踩坑',
              '超时无人跟进，闭环率低',
            ],
            after: [
              '异常即时触达，秒级响应',
              '根因与处置方案自动推送',
              '超时自动升级，闭环可追溯',
            ],
          },
        },
        {
          id: 'prod-capacity', name: '产能瓶颈分析', agentId: 'agent-production',
          feature: {
            category: '产能分析',
            summary: '瓶颈在哪、还能不能加单，靠经验判断不准。AI 智能体多维分析负荷，量化瓶颈工序并给出改善与接单建议。',
            metrics: [
              { value: '+12%', label: '有效产能识别' },
              { value: '天→实时', label: '瓶颈定位' },
              { value: '90%', label: '加单评估准确率' },
            ],
            flowLabel: '评估维度',
            flowStyle: 'dims',
            flow: ['机台负荷', '模具可用性', '人力配置', '物料齐套', '换型频次'],
            before: [
              '瓶颈工序靠估，看不清',
              '能不能接单心里没底',
              '改善抓不到重点',
            ],
            after: [
              '多维负荷量化，瓶颈一目了然',
              '接单能力科学评估',
              '改善聚焦关键，投入产出更高',
            ],
          },
        },
      ],
    },
    {
      id: 'mold',
      name: '模具部',
      en: 'Mold',
      color: '#a855f7',
      positions: ['制模', '加工'],
      scenarios: [
        {
          id: 'mold-review', name: '模具设计评审', agentId: 'agent-mold',
          feature: {
            category: '模具工艺',
            summary: '模具设计评审靠老师傅经验，要点容易遗漏。AI 智能体对照标准与历史问题自动预审，列出风险点让评审更聚焦。',
            metrics: [
              { value: '+40%', label: '评审效率' },
              { value: '-25%', label: '设计变更' },
              { value: '-50%', label: '缺陷漏检' },
            ],
            flowLabel: '评估维度',
            flowStyle: 'dims',
            flow: ['结构合理性', '脱模与冷却', '加工可行性', '用料成本', '历史相似问题'],
            before: [
              '评审依赖个人经验，标准不一',
              '历史踩过的坑重复出现',
              '问题到制模后才暴露，返工贵',
            ],
            after: [
              '标准与历史问题自动比对预审',
              '风险点提前列出，评审聚焦',
              '设计缺陷前置发现，减少返工',
            ],
          },
        },
        {
          id: 'mold-progress', name: '制模进度跟踪', agentId: 'agent-mold',
          feature: {
            category: '模具工艺',
            summary: '制模工序多、外协杂，进度靠人一个个问。AI 智能体自动汇总各工序进展，识别延误并提醒责任人。',
            metrics: [
              { value: '90%', label: '进度采集自动化' },
              { value: '-15%', label: '制模周期' },
              { value: '提前3天', label: '延误发现' },
            ],
            flowLabel: '处理流程',
            flow: ['拆解制模工序', '采集各工序进展', '关联交期', '延误预警', '推送责任人'],
            before: [
              '进度靠人问，信息滞后',
              '外协环节不透明',
              '延误发现晚，影响新品上市',
            ],
            after: [
              '各工序进展自动汇总可视',
              '外协进度纳入跟踪',
              '延误提前预警，保障交期',
            ],
          },
        },
        {
          id: 'mold-cnc', name: 'CNC加工排程', agentId: 'agent-mold',
          feature: {
            category: '加工排程',
            summary: 'CNC 机台、刀具、程序与工件匹配复杂，排程靠人工。AI 智能体按交期与机台负荷自动排程，提升设备利用。',
            metrics: [
              { value: '+18%', label: 'CNC 利用率' },
              { value: '-75%', label: '排程耗时' },
              { value: '分钟级', label: '急单插单响应' },
            ],
            flowLabel: '处理流程',
            flow: ['读取加工任务', '匹配机台刀具', '自动排程', '插单重排', '下发程序'],
            before: [
              '机台刀具匹配靠经验，排程慢',
              '急单插单打乱全局',
              '设备空转与等待并存',
            ],
            after: [
              '自动排程兼顾交期与负荷',
              '插单秒级重排',
              '设备利用率显著提升',
            ],
          },
        },
      ],
    },
    {
      id: 'quality',
      name: '品质部',
      en: 'Quality',
      color: '#06b6d4',
      positions: ['QE', 'QC', '检测中心', '体系'],
      scenarios: [
        {
          id: 'qa-visual', name: 'AI视觉质检', agentId: 'agent-quality',
          feature: {
            category: '智能质检',
            summary: '人工目检慢、易疲劳漏检，标准还因人而异。AI 智能体用视觉模型实时检测缺陷，自动判定并剔除，标准始终一致。',
            metrics: [
              { value: '+300%', label: '检测速度' },
              { value: '-80%', label: '漏检率' },
              { value: '-50%', label: '质检人力' },
            ],
            flowLabel: '处理流程',
            flow: ['图像采集', '视觉模型识别', '缺陷分类定位', '自动判定剔除', '数据回传分析'],
            before: [
              '人工目检效率低、易疲劳漏检',
              '判定标准因人而异',
              '缺陷数据难沉淀分析',
            ],
            after: [
              '高速在线检测，漏检大幅下降',
              '判定标准统一、可追溯',
              '缺陷数据自动回传，反哺改善',
            ],
          },
        },
        {
          id: 'qa-rootcause', name: '不良根因分析', agentId: 'agent-quality',
          feature: {
            category: '质量改进',
            summary: '不良发生后追溯原因要翻多个系统数据，慢且主观。AI 智能体自动关联工艺、设备、物料数据，定位根因并给改善方向。',
            metrics: [
              { value: '-70%', label: '根因定位时间' },
              { value: '-35%', label: '重复不良' },
              { value: '天→小时', label: '8D 报告生成' },
            ],
            flowLabel: '处理流程',
            flow: ['汇集不良数据', '关联工艺 / 设备 / 料', '相关性分析', '定位根因', '生成改善建议'],
            before: [
              '跨系统取数费时，分析滞后',
              '根因靠经验推断，易误判',
              '同类不良反复发生',
            ],
            after: [
              '多源数据自动关联，快速定位',
              '根因有数据支撑，判断更准',
              '改善建议沉淀，减少重复不良',
            ],
          },
        },
        {
          id: 'qa-spc', name: 'SPC数据分析', agentId: 'agent-quality',
          feature: {
            category: '过程控制',
            summary: 'SPC 控制图靠人画、异常靠人盯，超限常常后知后觉。AI 智能体实时采集量测自动判异，过程失控即时预警。',
            metrics: [
              { value: '100%', label: '异常判异实时率' },
              { value: '全工序', label: 'CPK 达标监控' },
              { value: '+40%', label: '批量不良预防' },
            ],
            flowLabel: '处理流程',
            flow: ['采集量测数据', '计算控制限', '自动判异', '失控预警', '趋势分析'],
            before: [
              '控制图人工绘制，更新慢',
              '判异规则复杂易漏',
              '过程失控发现晚，酿成批量不良',
            ],
            after: [
              '量测实时采集，控制图自动更新',
              '判异规则自动执行，不漏报',
              '失控即时预警，预防批量不良',
            ],
          },
        },
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
