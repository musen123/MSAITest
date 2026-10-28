"""测试数据中心 AI 造数 prompt。

文件造数：LLM 只产**文件规格清单**（引用名/文件名/类型/文本内容/表格/目标大小），
真实二进制由代码（file_forge）按规格生成——LLM 绝不碰二进制。
数据集造数：根据列定义生成合成测试数据。
"""

from __future__ import annotations

import json
from typing import Optional

_FILE_KINDS = "pdf, docx, xlsx, csv, txt, json, md, png, bin"


def build_file_spec_prompt(
    *, requirement: str, count: int, existing_names: Optional[list[str]] = None
) -> list[tuple[str, str]]:
    """据自然语言需求产文件规格清单（供 file_forge 逐个生成真实文件）。

    只产规格与文本内容，不产二进制。existing_names 用于避免引用名撞已有资产。
    """
    system = (
        "你是测试文件规格师。根据用户的测试文件需求，产出一份要生成的文件清单。"
        "你只负责给出每个文件的**规格与文本内容**，真实文件（PDF/Word/Excel 等二进制）"
        "由系统按你的规格生成——你绝不要输出二进制或 base64。\n"
        f"支持的文件类型 kind：{_FILE_KINDS}。\n"
        "每个文件对象字段：\n"
        "- name：资产引用名（简短、项目内唯一、不含空格/冒号/花括号，如 `合同样本A`、`用户导入模板`）；\n"
        "- file_name：文件名含扩展名（如 `contract_a.pdf`）；\n"
        "- kind：上面支持的类型之一；\n"
        "- text：文件的文本内容（pdf/docx/txt/md/json/png 用；写贴合测试场景的真实内容，"
        "如合同就写甲乙方/金额/条款）；\n"
        "- table_headers + table_rows：表格类（xlsx/csv）用，headers 是表头、rows 是二维数组；\n"
        "- target_size_bytes：仅当需求明确要「大文件」时给（如 10MB=10485760），"
        "只对 pdf/txt/csv/bin 生效；普通文件不要给。\n"
        "要求：文件数量尽量等于需求；内容多样、贴合被测业务；notes 一句中文小结。"
    )
    avoid = (
        f"\n已存在的引用名（换个名，别撞）：{', '.join(existing_names[:50])}"
        if existing_names
        else ""
    )
    human = (
        f"测试文件需求：{requirement}\n"
        f"期望文件数量：{count}{avoid}\n"
        "请产出文件规格清单（结构化字段）。"
    )
    return [("system", system), ("human", human)]


def spec_to_forge(spec_obj: dict) -> dict:
    """LLM 规格对象 → file_forge.forge_file 入参（组装 table、透传 target_size）。"""
    table = None
    headers = spec_obj.get("table_headers") or []
    rows = spec_obj.get("table_rows") or []
    if headers or rows:
        table = {"headers": headers, "rows": rows}
    return {
        "kind": spec_obj.get("kind") or "",
        "file_name": spec_obj.get("file_name") or "",
        "text": spec_obj.get("text") or "",
        "table": table,
        "target_size_bytes": spec_obj.get("target_size_bytes"),
    }


def build_dataset_gen_prompt(
    *, columns: list[dict], count: int, intent: Optional[str]
) -> list[tuple[str, str]]:
    """构造数据集造数 prompt。

    **安全口径**:只发列的「名称/说明/性质(kind)」与意图,**绝不发任何样例值**
    (避免把已有真实数据喂给外部 LLM)。kind 不再决定"生成与否"——所有列都生成,kind 仅作
    生成风格提示(内部自测平台:允许造账号/口令等自测数据,用户另行批量注册对应真实账号)。
    """
    system = "你是测试数据生成专家。为测试场景的「数据驱动」生成多行测试数据(每条用例用一行)。每列给了名称 name、说明 desc、性质 kind。**为每一列的每一行都生成值,任何列都不要留空**;kind 只决定生成风格:\n- kind=synthetic:领域真实、彼此多样的合成值(姓名/地址/搜索词/商品SKU/手机号等),贴合数据集意图;\n- kind=identity:身份/账号类(用户名/邮箱/账号ID),**每行必须唯一**、风格统一、便于批量注册(如 testuser0001…0100,或 test+序号@test.com);\n- kind=secret:口令/令牌类(密码/token),生成符合常见复杂度要求的字符串;\n  说明:这些是**自测数据**,不要求在被测系统里真实存在——用户会用其他方式批量注册对应账号;\n- 每行是一个对象,**键必须与下方列定义的 name 完全一致(逐字照抄,包括可能的拼写/大小写,不要纠正)**,只含声明的列,不多不少;\n- 行数尽量等于要求的数量;notes 用一句中文说明生成了哪些列。\n只输出结构化字段。"
    cols_meta = [
        {
            "name": c.get("name"),
            "desc": c.get("desc") or "",
            "kind": c.get("kind") or "synthetic",
        }
        for c in columns or []
    ]
    _style = {
        "identity": "**为每行生成唯一的身份/账号值**(便于批量注册)",
        "secret": "**为每行生成口令/令牌类字符串**",
    }
    directives = "\n".join(
        (
            f"  - {m['name']}（说明:{m['desc'] or '无'}）→ kind={m['kind']} → "
            + _style.get(m["kind"], "**为每行生成多样化的值**")
            for m in cols_meta
        )
    )
    human = f"数据集意图：{intent or '通用测试数据'}\n列定义(仅元信息,无样例值)：{json.dumps(cols_meta, ensure_ascii=False)}\n逐列填充要求(行对象的键须严格用下方 name):\n{directives}\n需要生成的行数：{count}"
    return [("system", system), ("human", human)]
