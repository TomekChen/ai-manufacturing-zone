# -*- coding: utf-8 -*-
"""意图路由的纯规则层（Slice 5）。零 token、零网络、可离线确定性单测（Seam S5）。

对外四个纯函数：
  classify_intent(question, has_history) -> "knowledge" | "smalltalk" | "offtopic"
  pick_retrieval(question)                -> "bm25" | "hybrid"     （知识问答时选检索策略）
  needs_rewrite(question, history)        -> bool                  （多轮检索前要不要做上下文改写）
  build_messages(system, history, user, max_turns) -> list[dict]   （组装带多轮上下文的对话消息）

设计原则：宁可多走知识库也不误拒——判不清一律默认 knowledge。规则是启发式，
覆盖常见闲聊/超范围与指代追问；边界外的情形交给 knowledge 路径（改写 + 检索 + 生成）兜底。
"""
import re

KNOWLEDGE = "knowledge"
SMALLTALK = "smalltalk"
OFFTOPIC = "offtopic"

# 归一化：去掉标点/空白、转小写，仅保留中文与字母数字
_NONWORD = re.compile(r"[^\w\u4e00-\u9fff]+", re.UNICODE)


def _norm(text):
    return _NONWORD.sub("", (text or "").strip().lower())


# 领域关键词：命中即判定为知识问答（先于闲聊/超范围检查，保证「你好，MES是什么」走 KB）
DOMAIN_KEYWORDS = [
    "智能制造", "智能工厂", "智能装备", "数字化", "数字化转型", "数字孪生", "数字主线", "数字模型",
    "预测性维护", "故障诊断", "健康管理", "设备管理", "工业物联网", "工业互联网", "工业软件", "工业以太网",
    "工业相机", "上位机", "下位机", "组态", "柔性制造", "柔性产线", "生产线", "产线", "车间", "工厂",
    "机器人", "机械臂", "自动化", "半自动化", "数控", "数控机床", "加工中心", "伺服", "变频", "plc",
    "cnc", "mes", "erp", "plm", "scada", "dcs", "opc", "agv", "amr", "wms",
    "传感器", "执行器", "控制器", "边缘计算", "云计算", "大数据", "机器学习", "深度学习", "人工智能",
    "工业大模型", "视觉检测", "机器视觉", "增材制造", "3d打印", "供应链管理", "仓储物流", "智能仓储",
    "能耗", "能效", "绿色制造", "精益", "精益生产", "工艺", "质量检测", "产品质量", "质量管理",
    "报警", "运维", "工业", "制造", "产线效率", "黑灯工厂", "灯塔工厂", "建模", "仿真",
]

# 闲聊标记（须无领域词且很短时才算，避免把真实提问误判成寒暄）
SMALLTALK_MARKERS = [
    "你好", "您好", "哈喽", "嗨", "hi", "hello", "hey", "在吗", "在么", "在不在",
    "你是谁", "你叫什么", "自我介绍", "介绍一下你自己", "你能做什么", "你会什么",
    "谢谢", "多谢", "感谢", "辛苦了", "再见", "拜拜", "88", "哈哈", "呵呵", "早上好", "晚上好", "午安",
]
SMALLTALK_MAX_LEN = 12

# 超范围标记（无领域词且命中其一，判为超范围，礼貌拒答引导）
OFFTOPIC_MARKERS = [
    "天气", "下雨", "气温", "做饭", "菜谱", "食谱", "做菜", "星座", "运势", "算命", "塔罗",
    "旅游", "景点", "攻略", "酒店", "机票", "签证", "电影", "电视剧", "综艺", "明星", "八卦",
    "游戏", "王者荣耀", "英雄联盟", "原神", "恋爱", "相亲", "表白", "分手", "脱单",
    "写诗", "写一首", "首诗", "歌词", "作文", "论文", "讲故事", "讲个故事", "笑话", "讲个笑话",
    "翻译", "拍照", "修图", "减肥", "化妆", "股票", "基金", "彩票", "赌博", "六合彩",
    "情书", "睡前故事", "取名字", "起名",
]

# 指代/口语追问词：命中即视为需要结合历史改写
ANAPHORA = [
    "它", "他", "她", "它们", "他们", "这", "那", "这些", "那些", "这样", "那样",
    "其", "该", "此", "上面", "上述", "前面", "刚才", "还有", "另外", "继续", "呢", "它呢", "这个", "那个",
]
REWRITE_SHORT_LEN = 12

# 精确型问题信号：型号 / 编号 / 较长数字串 -> 偏 BM25；否则偏 hybrid
_PRECISE = re.compile(r"[A-Za-z]+\d+|\d+[A-Za-z]+|\d{2,}|[A-Za-z]+-\d+", re.UNICODE)


def classify_intent(question, has_history=False):
    """判定意图。顺序：领域词 -> knowledge；短闲聊 -> smalltalk；超范围 -> offtopic；默认 knowledge。"""
    q = _norm(question)
    if not q:
        return KNOWLEDGE
    if any(k in q for k in DOMAIN_KEYWORDS):
        return KNOWLEDGE
    # 有历史上下文时优先当作追问走 KB，只有极明确的寒暄/致谢才仍判闲聊
    if any(m in q for m in SMALLTALK_MARKERS) and len(q) <= SMALLTALK_MAX_LEN:
        if not has_history or m_is_pure_greeting(q):
            return SMALLTALK
    if any(m in q for m in OFFTOPIC_MARKERS):
        return OFFTOPIC
    return KNOWLEDGE


def m_is_pure_greeting(q_norm):
    """几乎只由寒暄词组成（去掉寒暄词与标点后基本不剩内容）。"""
    rest = q_norm
    for m in SMALLTALK_MARKERS:
        rest = rest.replace(m, "")
    return len(rest) <= 1


def pick_retrieval(question):
    """按问题特征自动选检索策略：含型号/编号/数字等精确词用 bm25，否则用 hybrid。"""
    q = (question or "").strip()
    return "bm25" if _PRECISE.search(q) else "hybrid"


def needs_rewrite(question, history):
    """多轮：是否需要结合历史把追问改写成自足问题再检索。无历史 False；短/含指代词 True。"""
    if not history:
        return False
    q = (question or "").strip()
    if not q:
        return False
    if any(p in q for p in ANAPHORA):
        return True
    return len(_norm(q)) <= REWRITE_SHORT_LEN


def build_messages(system, history, user, max_turns=12):
    """组装 OpenAI 风格 messages：system + 最近 max_turns 条(仅 user/assistant) + 当前 user。"""
    clean = []
    for h in history or []:
        role = h.get("role")
        content = (h.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            clean.append({"role": role, "content": content})
    if max_turns and len(clean) > max_turns:
        clean = clean[-max_turns:]
    return [{"role": "system", "content": system}] + clean + [{"role": "user", "content": user}]
