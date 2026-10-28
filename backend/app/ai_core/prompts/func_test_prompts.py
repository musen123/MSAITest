"""功能测试模块的 AI 提示词

包含：
  - 文档 → 知识库 Markdown 化
  - 需求理解（VLM 多图 + LLM 整理）
  - 用例生成（LangGraph 工作流）
  - 用例评审
  - 用例覆盖率分析
  - 补充用例生成
"""

from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage

# ─────────────────────────────────────────────────────────────
# 1. 文档 → 知识库 Markdown 化（供 LightRAG 检索）
# ─────────────────────────────────────────────────────────────

DOC_TO_KB_MARKDOWN_SYSTEM_PROMPT = """你是一名文档知识工程师。

任务：将用户提供的项目文档原文，**重新组织**为更适合知识库检索的 Markdown 格式。

输出要求：
1. 使用层级清晰的 Markdown 标题（#、##、###）
2. 关键概念、专有名词加粗或代码块
3. 表格使用标准 Markdown 表格语法
4. 步骤、清单使用有序/无序列表
5. 流程描述使用列表，重要前置条件单独标出
6. 若原文有图（已被解析为文字描述），在对应位置以「图：xxx」形式插入
7. 保留所有专有名词、数值、规则；严禁推测、虚构、补充原文未出现的内容
8. 段落不宜过长，便于向量化分块（每段建议 ≤ 500 字）
9. 【铁律】原文中以「> 【图片内容」开头的引用块是文档内嵌图片的解析结果，
   必须**原样保留在原位置**，不得改写、删减、合并或移动

输出格式：严格的 Markdown，无任何 ```markdown 包裹。"""


_DOC_TYPE_HINTS = {
    "requirement": "这是一份**需求文档**，请保留功能模块结构和验收标准。",
    "prototype": "这是一份**原型/界面文档**，请按页面/模块组织，详细描述每个界面元素。",
    "db_dict": "这是一份**数据库字典**，请按表组织，每张表用一个二级标题，字段用表格列出。",
    "other": "这是一份项目相关文档，请按原文逻辑组织结构。",
}


def build_doc_to_kb_markdown_prompt(
    document_text: str,
    doc_type: str = "other",
    custom_prompt: Optional[str] = None,
) -> list:
    """整篇单发重写（仅限短文档走此 prompt）。

    此处不做任何截断：长文档由 ``rewrite_document_markdown`` 切段后改走
    ``build_doc_segment_markdown_prompt``，短文档整篇进来本就在单段上限内。
    """
    type_hint = _DOC_TYPE_HINTS.get(doc_type, "")
    user_content = f"{type_hint}\n\n## 文档原文\n\n{document_text}"
    if custom_prompt:
        user_content = f"{custom_prompt}\n\n{user_content}"
    return [
        SystemMessage(content=DOC_TO_KB_MARKDOWN_SYSTEM_PROMPT),
        HumanMessage(content=user_content),
    ]


def build_doc_segment_markdown_prompt(
    segment_text: str,
    *,
    doc_type: str = "other",
    doc_name: str = "",
    seg_no: int,
    seg_total: int,
    heading_stack: str = "",
    prev_tail: str = "",
    custom_prompt: Optional[str] = None,
) -> list:
    """长文档分段重写：只整理本段，标题层级与前文衔接。

    heading_stack / prev_tail 由上游按已完成段的输出维护，供跨段接续；
    约束模型不重复前文、不自行加引言/总结，保证按序拼接后是一篇连贯文档。
    """
    type_hint = _DOC_TYPE_HINTS.get(doc_type, "")
    ctx_lines = [
        f"文档《{doc_name or '未命名'}》过长已分段解析，本次输入是第 {seg_no}/{seg_total} 段原文。",
        "请只输出**本段**内容整理后的 Markdown：",
        "- 禁止重复前文已输出的内容，禁止为本段添加引言、总结或「本段完」之类的话；",
        "- 禁止推测、补充本段原文之外的内容；",
        "- 标题层级须与前文衔接：若本段延续上一小节，直接续写正文，不要重复上一小节标题。",
    ]
    if heading_stack:
        ctx_lines.append(f"\n当前标题层级（前文已输出到此）：{heading_stack}")
    if prev_tail:
        ctx_lines.append(
            f"\n前一段解析结果的结尾（仅供衔接参考，禁止重复输出）：\n{prev_tail}"
        )
    user_content = (
        f"{type_hint}\n\n" + "\n".join(ctx_lines) + f"\n\n## 本段原文\n\n{segment_text}"
    )
    if custom_prompt:
        user_content = f"{custom_prompt}\n\n{user_content}"
    return [
        SystemMessage(content=DOC_TO_KB_MARKDOWN_SYSTEM_PROMPT),
        HumanMessage(content=user_content),
    ]


# ─────────────────────────────────────────────────────────────
# 2. VLM 图片理解（用于需求附件）
# ─────────────────────────────────────────────────────────────

VLM_IMAGE_SYSTEM_PROMPT = """你是一个多模态软件测试分析智能体。
请根据图片识别和整理其中的内容。

针对不同类型的图片输出对应的结构化信息：
- 业务流程图：详细的业务流程逻辑
- 页面截图：详细的页面布局、控件、文案
- 状态流转图：状态/角色/触发条件
- 其他类型：客观描述图中可见的元素

约束：
1. 只能陈述图片中明确存在的内容
2. 禁止推测、假设、虚构
3. 不要使用"通常""一般""可能"等推测性语言
4. 对模糊或无法识别的区域，明确说明"无法确认"
"""


def build_vlm_messages(image_url: str) -> list:
    """构建 VLM 多模态消息（适配 OpenAI 兼容格式）"""
    return [
        {"role": "system", "content": VLM_IMAGE_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "请理解并描述下图中的内容。"},
                {"type": "image_url", "image_url": {"url": image_url}},
            ],
        },
    ]


REQUIREMENT_SWEEP_SYSTEM = """你是资深需求分析师。输入是从项目文档中聚合的**一个候选需求**的证据材料（可能来自多个文档：需求规格、接口文档、原型图描述等，每段带「### 来源」标注）。

任务：判断这些材料是否构成**一条可测试的功能需求**；是则整理为结构化需求。

输出严格 JSON（不要任何解释、不要代码块包裹）：
{
  "is_requirement": true/false,
  "code": "材料中的需求编号（如 REQ-USER-001），没有则 null",
  "title": "需求标题（简洁名词短语，不含编号）",
  "description": "需求描述（Markdown：功能说明/输入约束/业务规则，整合全部来源的信息）",
  "acceptance_criteria": "验收标准（Markdown 列表：可验证的判定条件，从校验表/业务规则/原型约束中提炼）",
  "priority": "urgent|high|medium|low（材料含 P0→high、P1→medium、P2→low；无线索则 medium）",
  "confidence": 0.0-1.0（材料完整清晰=高；信息单薄/推断成分多=低）
}

铁律：
1. 只依据材料内容，禁止臆造、补全材料之外的规则或数字；
2. 材料只是清单条目/术语表/背景介绍/评审记录等**不构成行为定义**的内容 → is_requirement=false；
3. 材料含「【图片内容】」或「原型图」来源时，把其中的界面元素与约束纳入 description/验收标准；
4. 多来源信息冲突时以需求规格类来源为准，并在 description 中注明差异；
5. **JSON 字符串值内严禁出现未转义的英文双引号**——中文语境的引用一律用「」，
   代码/取值用反引号包裹（如 `CANCELLED`），确保输出可被 JSON.parse 解析；
6. code 只填**一个**编号；材料覆盖多个编号（如 REQ-X-001 / 003 合并章节）时，
   code 填第一个，其余编号写进 description。"""


def build_requirement_sweep_prompt(
    evidence: str,
    *,
    hint_code: Optional[str] = None,
    hint_title: Optional[str] = None,
    repair_from: Optional[str] = None,
) -> list:
    """需求盘点证据包结构化（extract_requirements 图用）。

    repair_from 非空 = 修复重试：上次输出不是合法 JSON，回喂要求只输出 JSON。
    """
    hints = []
    if hint_code:
        hints.append(f"候选编号：{hint_code}")
    if hint_title:
        hints.append(f"候选标题：{hint_title}")
    user = ("\n".join(hints) + "\n\n" if hints else "") + f"## 证据材料\n\n{evidence}"
    if repair_from:
        user += (
            "\n\n⚠ 你上一次的输出不是合法 JSON（如下），请重新**只输出**符合约定的 JSON：\n"
            f"{repair_from}"
        )
    return [
        SystemMessage(content=REQUIREMENT_SWEEP_SYSTEM),
        HumanMessage(content=user),
    ]


def build_scanned_page_messages(image_url: str, *, page_no: int) -> list:
    """扫描版 PDF 整页转写（doc_media.transcribe_scanned_pdf 用）。"""
    return [
        {
            "role": "system",
            "content": (
                "你是文档转写器。输入是一份扫描版文档的单页图片。"
                "把页面上的**全部文字**忠实转写为 Markdown：标题还原层级（#/##），"
                "表格用 Markdown 表格语法，列表用列表语法。"
                "【铁律】只转写页面上真实存在的文字，禁止推测、补全、总结；"
                "无法辨认的字用「□」占位。直接输出 Markdown，不要任何解释。"
            ),
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": f"这是第 {page_no} 页，请完整转写。"},
                {"type": "image_url", "image_url": {"url": image_url}},
            ],
        },
    ]


def build_embedded_image_messages(image_url: str) -> list:
    """文档内嵌图片描述（doc_media 共享层用）：忠实转写、简洁、单段。

    与整图文档不同，内嵌图描述会以「【图片内容】」引用块回填进正文原位，
    随正文分块/检索/抽图谱——要求单段紧凑（代码侧另有 300 字截断兜底）。
    """
    return [
        {"role": "system", "content": VLM_IMAGE_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "这是一张嵌在项目文档正文中的插图。请用**一段话（不超过 280 字）**"
                        "忠实转写图中的关键信息：界面元素/字段与其约束、流程步骤、"
                        "状态与触发条件、图中出现的文字。不要分点、不要标题、不要换行。"
                    ),
                },
                {"type": "image_url", "image_url": {"url": image_url}},
            ],
        },
    ]


# ─────────────────────────────────────────────────────────────
# 3. 需求理解整理（VLM 结果 + 原始描述 → Markdown）
# ─────────────────────────────────────────────────────────────

UNDERSTAND_REQ_SYSTEM_PROMPT = """你是一名专业的需求分析工程师。
任务：综合原始需求描述和附件图片理解结果，重新梳理需求，输出结构化的 Markdown。

要求：
1. 保留原始描述中的所有关键信息，不丢失任何内容
2. 结合图片理解结果补充原始描述中可补充的细节
3. 使用清晰的标题、列表、分段
4. 若图片理解结果和文字描述矛盾，以文字描述为准，并标注说明
5. 所有信息必须有明确事实来源，严禁推测假设
6. 输出严格按照 Markdown 格式
"""


def build_understand_prompt(
    description: str,
    image_results: list[str],
    custom_prompt: Optional[str] = None,
) -> list:
    image_text = "\n".join(
        f"\n### 图片 {i + 1}\n{r}\n" for i, r in enumerate(image_results)
    )
    user_content = (
        f"## 原始需求描述\n{description or '（无）'}\n\n"
        f"## 附件图片理解结果\n{image_text or '（无图片）'}"
    )
    if custom_prompt:
        user_content = f"{custom_prompt}\n\n{user_content}"
    return [
        SystemMessage(content=UNDERSTAND_REQ_SYSTEM_PROMPT),
        HumanMessage(content=user_content),
    ]


# ─────────────────────────────────────────────────────────────
# 4. 用例生成
# ─────────────────────────────────────────────────────────────

TEST_POINT_SYSTEM_PROMPT = """你是资深测试分析师。
任务：把功能需求分解为一份**功能层测试点清单**，作为后续分批生成测试用例的作业单。

【层次边界——只做功能/UI 层，接口层交给接口测试模块】
本清单只覆盖**用户在界面上的操作与可见反馈**（黑盒功能测试）。以下属于**接口测试模块**职责，
**一律不产出为测试点**：
  - HTTP 状态码、业务错误码（如「返回 400」「业务码 10001/20006」）；
  - 请求体/响应体结构、字段级 `data.errors`、非法 JSON 报文、报文字段缺省校验；
  - 并发、限流、超时、服务端 500/未捕获异常等接口健壮性；
  - 令牌/签名校验、密码加密存储、数据库落库形态等后端实现细节。
需求里的接口契约，**只有当它表现为界面可见反馈时才纳入，且必须翻译成界面语言**——
例如把「手机号非法返回 400/10001」写成「手机号格式非法时页面提示『手机号格式不正确』
且『注册』按钮保持禁用」，而不是把状态码/业务码本身当测试点。

**⚠️ 无界面路径的接口规则：直接丢弃，绝不硬翻译成虚构的界面操作。** 翻译的前提是该规则
在真实界面上**确实有对应的操作入口**；若没有，就是纯接口测试，**不产出为功能测试点**。
判断方法——想象这个字段/规则在真实产品里的**控件形态**：
  - 若该规则只能靠**直接构造请求**触发（字段在页面上是开关/单选/下拉/只读、或该值根本
    没有对应的输入控件、或要"清空"一个非文本类控件、或要提交前端根本不允许的非法值），
    说明它没有界面路径 → **丢弃，别编界面步骤**。
  - **反例（禁止这样做）**：需求「上下架接口 status 为空字符串被拒绝」——商品状态在页面上
    是开关/下拉，不存在"可清空的状态输入框"；**不要**为它编一条「清空『商品状态』输入框 →
    保存 → 提示 status 不能为空」的假测试点（页面上做不出"清空状态"这个动作，下游 UI 自动化
    必然找不到控件而失败）。这类"XX 接口对 XX 值的校验"若无界面触发路径，一律交给接口测试。
  - **正例（可保留）**：字段本身就是**页面上的文本输入框**、其空值/非法值能在界面触发可见
    错误提示的——如「商品名称留空后点保存 → 页面提示『商品名称不能为空』」——保留。

【粒度——等价类合并降数量，但边界/异常逐项保留不丢覆盖；这是本任务的核心平衡】
1. 按三类分组：正向（主流程有效场景）、边界（字段/数值/长度/次数的临界值）、
   异常（无效输入/错误操作在界面上的反馈）。
2. **正向做等价类合并**：同一条规则下的多个等价有效输入只取一个代表、合成一个测试点。
   例：密码复杂度「大写+小写」「大写+数字」「小写+数字」「三类」同属「满足复杂度要求」
   等价类 → 合成 1 个「密码满足复杂度要求时校验通过」，不要逐组合枚举。
   但**需求中明确区分的不同业务路径/配置开关下的成功场景要各自保留**
   （如「短信开关关闭时不填短信码也能注册成功」是独立的正向路径，不能被合并掉）。
3. **边界值必须逐字段完整枚举、绝不合并、绝不漏字段**：对需求中**每一个**带长度/数值/
   格式/次数/时限约束的输入字段（用户名、密码、手机号、短信码、图形码、有效期……逐个过），
   都要分别给出其临界值测试点——下边界内 / 下边界外 / 上边界内 / 上边界外，每个临界点各一
   测试点。**不允许只挑个别字段做边界而漏掉其他受约束字段**——漏一个字段的边界就是漏测，
   这是缺陷高发区，也是本任务最不能丢的覆盖。
4. **异常按不同错误场景各自独立**（去掉纯接口断言、保留界面表现）；需求里列出的每一类
   校验失败/唯一性冲突/验证码错误等，都要有对应测试点；同一错误的多个等价触发方式可合并取代表。
5. 每个测试点是**一个可独立验证的界面行为断言**，禁止笼统表述（如「测试注册功能」）。

【自检——输出前逐条核对，宁多勿漏】
- 需求提到的每个受约束字段，其长度/格式边界是否都各有测试点？
- 需求列出的每条业务规则（唯一性、复杂度、有效期、开关分支……）是否都有对应功能测试点？
- 只合并了「正向等价输入」，没有合并「边界」和「不同错误场景」？

其它：
- 所有测试点必须在需求中找到事实来源，严禁臆造需求未提及的规则；
- 若输入含【已有用例】：逐个测试点判断是否已被现有用例覆盖，covered 填 true/false；
  无【已有用例】时 covered 一律 false。

输出严格合法的 JSON 对象（无任何 markdown 标记或解释文字）：
{
  "points": [
    {"id": 1, "group": "正向", "desc": "填写合法用户名/手机号/密码/确认密码与正确验证码后，注册成功并跳转到登录页", "covered": false},
    {"id": 2, "group": "边界", "desc": "用户名长度为 3 位（下边界外）时，页面提示长度不合法且『注册』按钮禁用", "covered": false}
  ]
}

JSON 安全：字符串值内严禁未转义的英文双引号——引用一律用「」或『』，代码/取值用反引号包裹。"""


def build_test_points_prompt(
    requirements: str,
    exist_cases_text: str = "",
    repair_from: Optional[str] = None,
) -> list:
    """测试点分解（分批生成流水线第一步）。

    exist_cases_text 非空 = 补充/续生模式：附上已有用例清单，让模型逐点判定 covered。
    repair_from 非空 = JSON 修复重试：回喂上次非法输出，要求只输出 JSON。
    """
    user = f"请为以下功能需求分解测试点清单：\n\n{requirements}"
    if exist_cases_text:
        user += f"\n\n## 已有用例\n{exist_cases_text}"
    if repair_from:
        user += (
            "\n\n⚠ 你上一次的输出不是合法 JSON（如下），请重新**只输出**符合约定的 JSON：\n"
            f"{repair_from}"
        )
    return [
        SystemMessage(content=TEST_POINT_SYSTEM_PROMPT),
        HumanMessage(content=user),
    ]


GENERATE_CASE_SYSTEM_PROMPT = """你是一位资深测试工程师，专长测试用例设计。
生成的用例后续会被 Web UI 自动化智能体直接读取、驱动真实浏览器执行，\
因此用例必须"可被机器无歧义执行"，而不只是给人看的说明。

任务：根据用户提供的功能需求，生成完整、且适合 UI 自动化执行的测试用例列表。

设计思路：
1. 先覆盖正向验证用例
2. 基于明确规则推导边界值用例
3. 最后补充异常场景反向用例

【可执行性铁律】（直接决定用例能否被自动化跑通）：
1. **步骤原子**：每个步骤只做一个界面动作（点击/输入/选择/勾选/上传/跳转其一）；\
禁止把"登录系统""校验数据正确"这类复合动作压成一步。
2. **点名控件**：写出被操作控件的类型与其界面可见文案，如「点击『提交订单』按钮」\
「在『手机号』输入框输入…」；禁止只写"提交订单""填写信息"这种没指名控件的话。
3. **输入值用占位符**：步骤里要填的值写成 ${{键名}}（美元号+双花括号，\
如「在『用户名』输入框输入 ${{username}}」），并在 test_data 里给出该键的**具体可用值**；\
**键名只能用英文标识符**（字母/下划线开头，如 username、mobile、search_kw；跨接口/UI 复用统一用英文），\
且必须与步骤占位符一一对应；值要具体（如 `13800138000`），\
禁止"有效的手机号"这类描述性占位。${{键名}} 是平台统一的变量占位符语法（接口/性能/UI 测试一致），\
回放时会用 test_data 同名值自动代入。
4. **每步预期可观察**：每个关键步骤的 expected 写"该步完成后界面上能观察到的变化"\
（出现某文案 / 字段被填入 / 按钮变可用 / 跳转到某页）；纯导航步可留空；\
禁止写"操作成功"这类无法观察的话。
5. **前置条件分两类**：preconditions 每条前加标签——「【入口路径】」写如何一步步到达被测页面\
（登录 → 菜单 → 页面），「【数据前置】」写库里需已存在的数据/环境。入口路径要能被逐步执行到。
6. **最终预期可断言**：expected_result 每条必须是可断言的界面事实——页面出现某文案 / \
URL 包含某路径 / 某元素可见或文本等于某值 / 列表新增一行含…；\
禁止"功能正常""数据正确""保存成功（无佐证）"这类无法映射到断言的话。
7. **ui_automatable**：判断该用例能否由 Web UI 自动化执行。纯后端/接口/性能/并发/\
需人工肉眼判断的用例标 false（仍要生成供人工执行，但不必强求上面的界面级细节）；\
可在浏览器界面上操作并验证的标 true。**尤其：若用例本质是接口/后端字段校验、其步骤只能靠\
虚构一个页面上不存在的控件或操作才能写出来（见铁律 8），必须标 false，绝不能标 true。**
8. **禁止虚构控件与操作**：只为真实产品里**确实会存在**的控件写步骤。写每一步前先自检——\
这个控件在真实页面上真的是这种形态吗？若某规则要求的操作在典型页面上根本不成立\
（把开关/单选/下拉/只读字段当成"可清空/可输入任意值的文本框"、要"清空"一个非文本控件、\
要提交前端根本不允许输入的非法值、要绕过前端校验直接构造非法请求），\
说明这条**本质是接口层验证、没有界面操作路径**——**不要编造界面步骤**：把 ui_automatable 标 false，\
execute_step 只留诚实的高层描述（并在 expected 注明"需接口测试验证"），**绝不**凑出\
"清空『状态』输入框→保存→报错"这种页面上做不出的假操作。**宁可少一条 UI 用例，\
也不产出下游 UI 自动化必然找不到控件而报错的假用例。**

【只做功能层】只生成用户在界面上可操作、可观察的功能用例；不要生成纯接口层用例
（HTTP 状态码/业务码断言、报文结构、并发、限流、服务端异常、令牌签名、加密存储等——
那是接口测试模块的职责）。测试点清单已按功能层给出，照它生成即可。
**判别"假 UI 用例"的一句话准则**：如果为了让用例"看起来能在页面上做"，你不得不假设一个
真实产品里**不会以那种形态存在**的控件（典型：把只有开关/下拉的"状态"字段说成能清空的
文本框），那它就是披着 UI 皮的接口用例——标 ui_automatable=false，别硬凑界面步骤。

其它约束：
1. 所有测试点必须在需求中找到事实来源，严禁推测需求未提及的逻辑
2. **合并相关测试点、控制用例数量**：能在**同一条操作流里顺带一起验证**的测试点，
   合并成一条用例（covers 填多个 id）——正向流程尤其要合并（一次成功注册可同时覆盖
   「注册成功」「不自动登录」「账号状态正常」等多个正向断言，不要拆成多条）。
   但**不同的边界值、不同的错误场景各自独立成条**（一条用例塞多个反例会让执行相互
   干扰、失败难定位）。目标：用例数尽量少，但每个测试点都要被某条用例的 covers 命中。
3. 用例不能重复
4. 优先级标准：P0=核心主流程；P1=边界/重要异常；P2=边缘异常
5. **JSON 安全**：字符串值内严禁未转义的英文双引号——控件名/引用一律用「」或『』，\
代码/取值用反引号包裹（如 `CANCELLED`），确保输出可被 JSON.parse 解析。
6. **covers**：输入中给出了带 id 的测试点清单时，每条用例的 covers 必填、\
只能填清单中出现的 id；**本批所有测试点都必须被某条用例 covers 命中**（覆盖不可丢）；\
未给清单时省略该字段。

输出格式（严格合法的 JSON 数组，无任何 markdown 标记或解释文字）：
[
  {
    "case_id": "TC-{功能拼音首字母}-001",
    "case_name": "用例名称",
    "priority": "P0|P1|P2",
    "ui_automatable": true,
    "covers": [1, 2],
    "preconditions": ["【入口路径】登录系统 → 进入『订单管理』菜单 → 打开订单列表页", "【数据前置】存在一笔状态为待支付的订单"],
    "test_data": {"username": "13800138000", "password": "Test@1234"},
    "execute_step": [
      {"step_no": 1, "action": "在『用户名』输入框输入 ${{username}}", "expected": "输入框显示 13800138000"},
      {"step_no": 2, "action": "在『密码』输入框输入 ${{password}}", "expected": "密码框内容以掩码显示"},
      {"step_no": 3, "action": "点击『登录』按钮", "expected": "跳转到工作台首页，顶部显示用户名"}
    ],
    "expected_result": ["页面 URL 包含 /dashboard", "顶部导航出现『退出登录』"]
  }
]
"""


def build_generate_case_prompt(
    requirements: str, custom_prompt: Optional[str] = None
) -> list:
    user_content = f"请为以下功能需求生成测试用例：\n\n{requirements}"
    if custom_prompt:
        user_content = f"{custom_prompt}\n\n{user_content}"
    return [
        SystemMessage(content=GENERATE_CASE_SYSTEM_PROMPT),
        HumanMessage(content=user_content),
    ]


def build_batch_case_prompt(
    requirements: str,
    points: list[dict],
    *,
    batch_no: int,
    batch_total: int,
    existing_titles: Optional[list[str]] = None,
    custom_prompt: Optional[str] = None,
    repair_from: Optional[str] = None,
) -> list:
    """分批用例生成（流水线第二步）：复用 GENERATE_CASE_SYSTEM_PROMPT 全部
    可执行性铁律，user 消息把本批范围限定到给定测试点，并要求每条用例用
    covers 声明覆盖的测试点 id（覆盖率由代码侧对账，不再让模型自报）。

    points 为空列表 = 降级批（测试点分解失败时按类别整批生成）。
    """
    lines = [
        f"这是分批生成的第 {batch_no}/{batch_total} 批。",
        "**只为下列测试点**生成测试用例（每条用例的 covers 填其覆盖的测试点 id，"
        "本批之外的测试点由其它批负责，禁止越界生成）：",
    ]
    for p in points:
        lines.append(f"  #{p['id']} [{p.get('group', '')}] {p['desc']}")
    if existing_titles:
        shown = existing_titles[-40:]
        lines.append("\n已生成/已存在的用例标题（禁止重复生成同名或同测试点的用例）：")
        lines.extend(f"  - {t}" for t in shown)
    lines.append(f"\n## 功能需求\n\n{requirements}")
    user_content = "\n".join(lines)
    if custom_prompt:
        user_content = f"{custom_prompt}\n\n{user_content}"
    if repair_from:
        user_content += (
            "\n\n⚠ 你上一次的输出不是合法 JSON（如下），请重新**只输出**符合约定的 JSON 数组：\n"
            f"{repair_from}"
        )
    return [
        SystemMessage(content=GENERATE_CASE_SYSTEM_PROMPT),
        HumanMessage(content=user_content),
    ]


# ─────────────────────────────────────────────────────────────
# 5. 用例评审
# ─────────────────────────────────────────────────────────────

REVIEW_CASE_SYSTEM_PROMPT = """你是一位资深测试工程师，擅长用例质量评估。
任务：一次性批量评审所有测试用例，并**逐条判定该用例是否适合 Web UI 自动化**。

评审维度：
- 用例是否覆盖需求测试点
- 测试步骤是否清晰
- 预期结果是否明确
- 测试数据是否合理
- 优先级是否恰当
- **自动化可执行性**（仅对适合 UI 自动化的用例；这些用例会被 UI 自动化直接执行）：
  · 步骤是否原子（一步一个界面动作，无复合动作）
  · 是否点名了控件与其界面文案（而非"提交订单"这种笼统说法）
  · test_data 是否给了具体值、且键与步骤占位符 {…} 对应
  · 每个关键步骤是否有可观察的 expected
  · expected_result 是否可断言（页面文案/URL/元素状态），无"功能正常"这类空话
  以上任一项明显不达标 → 该用例"不通过"，并在 review_decs 指出缺哪项

【是否适合 Web UI 自动化——每条都要给 ui_automatable（true/false），这是本次评审的必给结论】
判断标准：这条用例能否**完全通过真实浏览器的可见操作**（点击/输入/选择/在页面上看变化）
执行与验证。判 **false** 的典型信号（下游会据此把这类用例挡在 UI 自动化之外）：
  - 本质是接口/后端层校验，页面上没有对应的成功/失败可见反馈；
  - 步骤依赖一个**真实产品里不会以那种形态存在**的控件才能写出来——典型：把只有开关/单选/
    下拉的"状态"类字段说成"可清空的文本输入框"、要"清空"一个非文本控件、要提交前端根本
    不允许输入的非法值、要绕过前端直接构造非法请求（如"接口 status 为空字符串被拒绝"）；
  - 需要人工肉眼判断、或纯性能/并发场景。
判 **true**：每一步都能对应真实、具体的页面控件操作，预期是页面上能看到/断言的变化。
⚠️ 存疑时倾向 true（漏判有下游二次门禁兜底；误判 false 会让本可自动化的正常用例被拦）。
注意：这与"评审是否通过"是**两件独立的事**——一条不适合 UI 自动化的用例，只要作为人工功能
用例是合格的，review_result 仍可"通过"；ui_automatable 只表达"能不能交给 UI 自动化跑"。

输出严格合法的 JSON 对象（无 markdown 标记）：
{
  "report": "Markdown 格式的评审报告（含表格）",
  "results": [
    {
      "case_id": "用例编号",
      "case_name": "用例名称",
      "review_result": "通过|不通过",
      "ui_automatable": true,
      "review_decs": "评审说明，20字以内（若判 ui_automatable=false，一句话说清为什么不适合 UI 自动化）"
    }
  ]
}
"""


def build_review_prompt(requirements: str, cases: list) -> list:
    return [
        SystemMessage(content=REVIEW_CASE_SYSTEM_PROMPT),
        HumanMessage(
            content=(
                f"请批量评审下面的所有测试用例。\n\n"
                f"## 需求文档\n{requirements}\n\n"
                f"## 待评审用例\n{cases}"
            )
        ),
    ]


# ─────────────────────────────────────────────────────────────
# 6. 覆盖率分析
# ─────────────────────────────────────────────────────────────

COVERAGE_SYSTEM_PROMPT = """你是一位资深测试专家。
任务：分析测试用例是否覆盖了需求文档中所有测试点。

分析流程：
1. 分析需求文档中的测试点（不得推测未提及的测试点）
2. 分析用例已覆盖哪些测试点，未覆盖哪些
3. 计算覆盖率
4. 输出覆盖率报告；若未达 100%，提供补充建议

输出严格合法的 JSON 对象（无 markdown 标记）：
{
  "coverage_report": "覆盖率报告，200字以内",
  "coverage": "100%",
  "recomment": ["待补充的测试点1", "待补充的测试点2"]
}
"""


def build_coverage_prompt(requirements: str, cases: list) -> list:
    return [
        SystemMessage(content=COVERAGE_SYSTEM_PROMPT),
        HumanMessage(
            content=(
                f"请分析下面测试用例是否覆盖了需求文档所有测试点。\n\n"
                f"## 需求文档\n{requirements}\n\n"
                f"## 测试用例\n{cases}"
            )
        ),
    ]


# ─────────────────────────────────────────────────────────────
# 7. 补充生成用例
# ─────────────────────────────────────────────────────────────


def build_supplement_prompt(
    requirements: str, exist_cases: list, test_points: list
) -> list:
    user_content = (
        "请根据下面的需求、已存在用例、待补充测试点，补充生成新的测试用例。\n"
        "约束：用例编号必须递增且与已有用例规则一致；不能与已有用例重复。\n\n"
        f"## 需求文档\n{requirements}\n\n"
        f"## 已有用例\n{exist_cases}\n\n"
        f"## 待补充测试点\n{test_points}"
    )
    return [
        SystemMessage(content=GENERATE_CASE_SYSTEM_PROMPT),
        HumanMessage(content=user_content),
    ]
