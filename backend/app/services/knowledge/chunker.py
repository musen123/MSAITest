"""结构感知分块器（设计文档《知识库自研-总体设计方案》§3#6/#7，WP3 旗舰件）

输入解析产物 Markdown，输出父子块草稿序列（纯函数，不碰 DB/网络，独立单测）：

  - **标题树**：MarkdownHeaderTextSplitter 按 #/##/### 切章节，产出 heading_path
    面包屑（「3 退款 › 3.2 退款时效」）——引用溯源载体 + 召回上下文头
  - **父子块**：child（≤400 字/overlap 60）是嵌入与召回单元；parent（≤2000 字，
    按段落边界贪心打包相邻片段）是上下文单元。短小节（≤480 字）只出 child 不出
    parent——省一半存储，child 本身已自足
  - **原子块**：MD 表格整块保留（超长按行组切、**每片重复表头行**——接口参数表被
    拦腰切断是通用分块在研发文档上的典型失败）；fenced 代码块整块保留
  - **中文句读**：child 切分分隔符含 。！？；——评审实锤：早期死代码分块器
    的分隔符只有换行，长中文段落会在 400 字符处硬切断句
  - **嵌入/索引文本**（embed 节点使用）= heading_path + "\\n" + content 拼接
    （build_index_text）——「参数说明」这类脱离章节即无意义的块靠上下文头找回质量

seq 语义：按文档顺序统一编号（parent 与其 children 相邻），child.parent_seq 指向
所属 parent 的 seq；入库时先插 parent 拿 id 再回填 child.parent_chunk_id。
"""

import hashlib
import re
from dataclasses import dataclass, field
from typing import Optional

from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from app.models.knowledge.chunk import KbChunkType

# —— 锁定常量（任务拆解文档冻结；改动=改设计文档） ——
CHILD_TARGET_CHARS = 400
CHILD_OVERLAP_CHARS = 60
PARENT_MAX_CHARS = 2000
CHILD_ONLY_THRESHOLD = 480  # 小节 ≤ 此值只出 child 不出 parent
TABLE_SLICE_MAX_CHARS = 1500  # 表格超此值按行组切（每片重复表头）
HEADING_SEP = " › "
HEADING_PATH_MAX = 768  # kb_chunk.heading_path 列宽

# doc_type 分块 profile（P1a WP-A8）：
#   api_doc  —— 接口节原子化：一份接口定义（说明+参数表+响应）被 400 字细切后
#               「参数说明」脱离接口名即无意义;叶子节 ≤1200 字整节一块不再细切
#   test_case —— 每条用例一块（chunk_type=case）,同样 1200 字原子上限
# 超过原子上限的超长节回落通用父子块策略（不为 profile 牺牲超长内容的召回粒度）
ATOMIC_SECTION_MAX_CHARS = 1200
_PROFILE_ATOMIC_TYPES = {"api_doc", "test_case"}
_PROFILE_CHILD_TYPE = {"test_case": KbChunkType.CASE.value}

_HEADERS = [("#", "h1"), ("##", "h2"), ("###", "h3")]
# 中文句读优先于英文标点；空串兜底保证永远可切
_CHILD_SEPARATORS = ["\n\n", "\n", "。", "！", "？", "；", ". ", "; ", "，", " ", ""]


@dataclass
class ChunkDraft:
    """分块草稿（入库前的中间形态，字段对齐 kb_chunk 列）"""

    seq: int
    chunk_type: str
    heading_path: str
    content: str
    parent_seq: Optional[int] = None
    char_len: int = 0
    token_len: int = 0
    content_hash: str = ""

    def __post_init__(self) -> None:
        self.char_len = len(self.content)
        self.token_len = _count_tokens(self.content)
        self.content_hash = hashlib.sha256(self.content.encode("utf-8")).hexdigest()


_tiktoken_enc = None


def _count_tokens(text: str) -> int:
    """token 计数：tiktoken cl100k（随 langchain-openai 在 lock）；失败退化字符数"""
    global _tiktoken_enc
    try:
        if _tiktoken_enc is None:
            import tiktoken

            _tiktoken_enc = tiktoken.get_encoding("cl100k_base")
        return len(_tiktoken_enc.encode(text))
    except Exception:  # noqa: BLE001 —— 计数是计量不是正确性，退化不阻断
        return len(text)


def build_index_text(heading_path: str, content: str) -> str:
    """被嵌入的文本 = 上下文头 + 正文（§3#7）。全文索引由 (heading_path, content)
    复合 FULLTEXT 覆盖，无需二次拼接。"""
    return f"{heading_path}\n{content}" if heading_path else content


# ────────────────────────── 段落切分（表格/代码原子化） ──────────────────────────

_TABLE_LINE = re.compile(r"^\s*\|.+\|\s*$")
_FENCE = re.compile(r"^\s*(```|~~~)")


def _segment_blocks(text: str) -> list[tuple[str, str]]:
    """把一段 Markdown 切成 [(kind, text)]，kind ∈ text/table/code。

    行级扫描：fenced 代码块（```/~~~ 成对）与连续 |...| 行（≥2 行含分隔行的
    才算表格，单行竖线是误伤）各自聚合为原子段，其余聚合为 text 段。
    """
    segments: list[tuple[str, str]] = []
    buf: list[str] = []
    lines = text.split("\n")
    i = 0

    def flush_text() -> None:
        if buf:
            chunk = "\n".join(buf).strip("\n")
            if chunk.strip():
                segments.append(("text", chunk))
            buf.clear()

    while i < len(lines):
        line = lines[i]
        fence = _FENCE.match(line)
        if fence:
            flush_text()
            marker = fence.group(1)
            block = [line]
            i += 1
            while i < len(lines):
                block.append(lines[i])
                if _FENCE.match(lines[i]) and lines[i].strip().startswith(marker):
                    i += 1
                    break
                i += 1
            segments.append(("code", "\n".join(block)))
            continue
        if _TABLE_LINE.match(line):
            j = i
            while j < len(lines) and _TABLE_LINE.match(lines[j]):
                j += 1
            if j - i >= 2:
                flush_text()
                segments.append(("table", "\n".join(lines[i:j])))
                i = j
                continue
        buf.append(line)
        i += 1
    flush_text()
    return segments


def _slice_table(table_text: str) -> list[str]:
    """表格超长按行组切，每片重复表头（前两行 = 表头 + 分隔线）"""
    if len(table_text) <= TABLE_SLICE_MAX_CHARS:
        return [table_text]
    lines = [ln for ln in table_text.split("\n") if ln.strip()]
    if len(lines) < 3:
        return [table_text]
    header = lines[:2]
    header_len = len("\n".join(header))
    slices: list[str] = []
    cur: list[str] = []
    cur_len = header_len
    for row in lines[2:]:
        if cur and cur_len + len(row) + 1 > TABLE_SLICE_MAX_CHARS:
            slices.append("\n".join(header + cur))
            cur, cur_len = [], header_len
        cur.append(row)
        cur_len += len(row) + 1
    if cur:
        slices.append("\n".join(header + cur))
    return slices


# ────────────────────────── 主入口 ──────────────────────────

def chunk_markdown(markdown: str, *, doc_type: str = "other") -> list[ChunkDraft]:
    """Markdown → 父子块草稿序列（文档顺序编号）。

    doc_type 分块 profile（P1a WP-A8）：api_doc/test_case 的叶子节
    ≤ATOMIC_SECTION_MAX_CHARS 整节一块不细切（接口定义/单条用例保持完整）；
    test_case 的文本块标记 chunk_type=case。其余类型走通用策略。
    """
    md = (markdown or "").strip()
    if not md:
        return []

    header_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=_HEADERS, strip_headers=True
    )
    sections = header_splitter.split_text(md)

    child_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHILD_TARGET_CHARS,
        chunk_overlap=CHILD_OVERLAP_CHARS,
        separators=_CHILD_SEPARATORS,
        keep_separator="end",
    )
    parent_packer = RecursiveCharacterTextSplitter(
        chunk_size=PARENT_MAX_CHARS,
        chunk_overlap=0,
        separators=["\n\n", "\n", "。", ""],
        keep_separator="end",
    )

    atomic_max = (
        ATOMIC_SECTION_MAX_CHARS if doc_type in _PROFILE_ATOMIC_TYPES else CHILD_ONLY_THRESHOLD
    )
    text_child_type = _PROFILE_CHILD_TYPE.get(doc_type, KbChunkType.TEXT.value)

    drafts: list[ChunkDraft] = []
    seq = 0

    def next_seq() -> int:
        nonlocal seq
        s = seq
        seq += 1
        return s

    for section in sections:
        text = section.page_content.strip()
        if not text:
            continue
        heading_path = HEADING_SEP.join(
            v for k, v in sorted(section.metadata.items()) if v
        )[:HEADING_PATH_MAX]

        segments = _segment_blocks(text)

        # 贪心把相邻段打包成 parent 组（原子段不拆；超长 text 段先按段落拆开再包）
        groups: list[list[tuple[str, str]]] = []
        cur_group: list[tuple[str, str]] = []
        cur_len = 0
        for kind, seg in segments:
            pieces = (
                [(kind, p) for p in parent_packer.split_text(seg)]
                if kind == "text" and len(seg) > PARENT_MAX_CHARS
                else [(kind, seg)]
            )
            for k, piece in pieces:
                if cur_group and cur_len + len(piece) > PARENT_MAX_CHARS:
                    groups.append(cur_group)
                    cur_group, cur_len = [], 0
                cur_group.append((k, piece))
                cur_len += len(piece)
        if cur_group:
            groups.append(cur_group)

        for group in groups:
            group_text = "\n\n".join(p for _, p in group)
            small = len(group_text) <= atomic_max
            has_atomic = any(k != "text" for k, _ in group)

            parent_seq: Optional[int] = None
            if not (small and not has_atomic):
                parent_seq = next_seq()
                drafts.append(
                    ChunkDraft(
                        seq=parent_seq,
                        chunk_type=KbChunkType.PARENT.value,
                        heading_path=heading_path,
                        content=group_text,
                    )
                )

            if small and not has_atomic:
                # 小纯文本组：只出 child（自足，无需父上下文）
                drafts.append(
                    ChunkDraft(
                        seq=next_seq(),
                        chunk_type=text_child_type,
                        heading_path=heading_path,
                        content=group_text,
                    )
                )
                continue

            for kind, piece in group:
                if kind == "code":
                    drafts.append(
                        ChunkDraft(
                            seq=next_seq(),
                            chunk_type=KbChunkType.CODE.value,
                            heading_path=heading_path,
                            content=piece,
                            parent_seq=parent_seq,
                        )
                    )
                elif kind == "table":
                    for slice_text in _slice_table(piece):
                        drafts.append(
                            ChunkDraft(
                                seq=next_seq(),
                                chunk_type=KbChunkType.TABLE.value,
                                heading_path=heading_path,
                                content=slice_text,
                                parent_seq=parent_seq,
                            )
                        )
                else:
                    for piece_child in child_splitter.split_text(piece):
                        pc = piece_child.strip()
                        if pc:
                            drafts.append(
                                ChunkDraft(
                                    seq=next_seq(),
                                    chunk_type=text_child_type,
                                    heading_path=heading_path,
                                    content=pc,
                                    parent_seq=parent_seq,
                                )
                            )

    return drafts
