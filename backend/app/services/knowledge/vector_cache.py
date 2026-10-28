"""项目向量矩阵缓存（设计文档 §6.0 内存三件套之二：memmap 跨进程共享一份物理内存）

分层：
  MySQL kb_chunk.embedding BLOB = 唯一事实源（可随时全量重建一切）
  磁盘 {KB_VECTOR_DIR}/{project_id}_v{index_version}.vec.npy（L2 归一化 float32 [N,D]）
       {project_id}_v{index_version}.ids.npy（int64 [N]，行号 ↔ chunk_id）
  进程 np.memmap 只读映射 + LRU（KB_VECTOR_CACHE_PROJECTS 个项目）

失效：文件名含 index_version——任何 chunk 写路径 bump 版本后，旧文件天然失配，
下次查询按新版本重建（构建后顺手清理该项目旧版本文件）。多进程并发重建靠
tmp + os.replace 原子落盘，双方产物等价、后写覆盖无害。

归一化裁定：向量在**建矩阵时** L2 归一化落盘，查询向量在检索时归一化——
余弦 = 归一化后点积，matmul 一步到位；不信任 embedding API "已归一化"的口头承诺。
"""

import asyncio
import os
from collections import OrderedDict
from pathlib import Path
from typing import Optional

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.crud.knowledge.chunk import crud_kb_chunk

_MATRIX_LOCK = asyncio.Lock()  # 进程内构建互斥（跨进程靠原子 rename）
_lru: "OrderedDict[int, tuple[int, np.ndarray, np.ndarray]]" = OrderedDict()
# project_id -> (index_version, ids int64[N], mat float32[N,D] memmap)


def _vec_dir() -> Path:
    d = Path(settings.KB_VECTOR_DIR)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _paths(project_id: int, version: int) -> tuple[Path, Path]:
    d = _vec_dir()
    return (
        d / f"{project_id}_v{version}.vec.npy",
        d / f"{project_id}_v{version}.ids.npy",
    )


def _cleanup_stale(project_id: int, keep_version: int) -> None:
    """清理该项目旧版本物化文件（best-effort，失败不阻断）"""
    try:
        for f in _vec_dir().glob(f"{project_id}_v*.npy"):
            if f"_v{keep_version}." not in f.name:
                f.unlink(missing_ok=True)
    except OSError:
        pass


def _build_files(
    project_id: int, version: int, dim: int, rows: list[tuple[int, bytes]]
) -> None:
    """同步构建 .npy（to_thread 里跑）：BLOB → 归一化矩阵，tmp+rename 原子落盘"""
    vec_path, ids_path = _paths(project_id, version)
    ids = np.asarray([r[0] for r in rows], dtype=np.int64)
    mat = np.frombuffer(b"".join(r[1] for r in rows), dtype="<f4").reshape(len(rows), dim)
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    mat = (mat / norms).astype("<f4")

    for path, arr in ((vec_path, mat), (ids_path, ids)):
        tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
        np.save(tmp, arr, allow_pickle=False)
        # np.save 自动补 .npy 后缀
        os.replace(str(tmp) + ".npy", path)
    _cleanup_stale(project_id, version)


def _mmap_load(project_id: int, version: int) -> Optional[tuple[np.ndarray, np.ndarray]]:
    vec_path, ids_path = _paths(project_id, version)
    if not (vec_path.exists() and ids_path.exists()):
        return None
    try:
        mat = np.load(vec_path, mmap_mode="r", allow_pickle=False)
        ids = np.load(ids_path, allow_pickle=False)
        if len(ids) != mat.shape[0]:
            return None  # 半途文件，视为 miss 重建
        return ids, mat
    except Exception:  # noqa: BLE001 —— 损坏文件按 miss 处理（可重建的派生物）
        return None


async def get_matrix(
    db: AsyncSession, *, project_id: int, index_version: int, dim: int
) -> Optional[tuple[np.ndarray, np.ndarray]]:
    """取项目向量矩阵 (ids, mat)。空库返回 None。

    命中序：进程 LRU（版本一致）→ 磁盘 memmap → MySQL 重建落盘再 memmap。
    """
    cached = _lru.get(project_id)
    if cached and cached[0] == index_version:
        _lru.move_to_end(project_id)
        return cached[1], cached[2]

    async with _MATRIX_LOCK:
        cached = _lru.get(project_id)
        if cached and cached[0] == index_version:
            return cached[1], cached[2]

        loaded = _mmap_load(project_id, index_version)
        if loaded is None:
            rows = await crud_kb_chunk.fetch_recall_embeddings(db, project_id=project_id)
            rows = [(cid, blob) for cid, blob in rows if len(blob) == dim * 4]
            if not rows:
                _lru.pop(project_id, None)
                return None
            await asyncio.to_thread(_build_files, project_id, index_version, dim, rows)
            loaded = _mmap_load(project_id, index_version)
            if loaded is None:
                return None

        ids, mat = loaded
        _lru[project_id] = (index_version, ids, mat)
        _lru.move_to_end(project_id)
        while len(_lru) > max(1, settings.KB_VECTOR_CACHE_PROJECTS):
            _lru.popitem(last=False)
        return ids, mat


def _topk_sync(mat: np.ndarray, ids: np.ndarray, q: np.ndarray, k: int) -> list[tuple[int, float]]:
    qn = q.astype("<f4")
    n = np.linalg.norm(qn)
    if n > 0:
        qn = qn / n
    sims = mat @ qn
    k = min(k, len(sims))
    if k <= 0:
        return []
    idx = np.argpartition(-sims, k - 1)[:k]
    idx = idx[np.argsort(-sims[idx])]
    return [(int(ids[i]), float(sims[i])) for i in idx]


async def vector_topk(
    db: AsyncSession,
    *,
    project_id: int,
    index_version: int,
    dim: int,
    query_vec: np.ndarray,
    k: int = 30,
) -> list[tuple[int, float]]:
    """向量召回 top-k：[(chunk_id, cosine)]。numpy 计算 to_thread 包装不阻塞事件循环。"""
    got = await get_matrix(db, project_id=project_id, index_version=index_version, dim=dim)
    if got is None:
        return []
    ids, mat = got
    return await asyncio.to_thread(_topk_sync, mat, ids, query_vec, k)
