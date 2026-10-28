"""统一 AI 任务 CRUD"""

from datetime import datetime, timedelta
from typing import Any, Optional, Sequence

from sqlalchemy import and_, delete as sa_delete, func, or_, select, update
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai.ai_task import AiTask, AiTaskStatus
from app.models.ai.ai_task_event import AiTaskEvent

# 活跃状态（用于提交去重）
ACTIVE_STATUSES = (AiTaskStatus.PENDING.value, AiTaskStatus.RUNNING.value)


class CRUDAiTask:
    """统一 AI 任务 CRUD"""

    # ── 主表 ────────────────────────────────────────────────

    async def create(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        created_by: int,
        task_type: str,
        title: str = "",
        biz_ref_type: Optional[str] = None,
        biz_ref_id: Optional[int] = None,
        input_params: Optional[dict] = None,
        ai_model: Optional[str] = None,
    ) -> AiTask:
        task = AiTask(
            project_id=project_id,
            created_by=created_by,
            task_type=task_type,
            title=title,
            biz_ref_type=biz_ref_type,
            biz_ref_id=biz_ref_id,
            status=AiTaskStatus.PENDING.value,
            input_params=input_params,
            ai_model=ai_model,
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)
        return task

    async def get(self, db: AsyncSession, task_id: int) -> Optional[AiTask]:
        return await db.get(AiTask, task_id)

    async def find_active(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        task_type: str,
        biz_ref_id: Optional[int],
        device_udid: Optional[str] = None,
    ) -> Optional[AiTask]:
        """查找同 (project, type, biz_ref[, device]) 的活跃任务（提交去重第1层）。

        device_udid 非 None 时按 input_params.device_udid 细化——同一用例/套件
        可在不同设备上并行（单 Agent 多设备并行），只拦同设备重复提交。
        过滤在 Python 侧做（活跃集恒小，不上 JSON_EXTRACT 免方言耦合）。
        """
        cond = [
            AiTask.project_id == project_id,
            AiTask.task_type == task_type,
            AiTask.status.in_(ACTIVE_STATUSES),
        ]
        if biz_ref_id is not None:
            cond.append(AiTask.biz_ref_id == biz_ref_id)
        stmt = select(AiTask).where(*cond).order_by(AiTask.created_at.desc())
        if device_udid is None:
            return (await db.execute(stmt.limit(1))).scalars().first()
        for task in (await db.execute(stmt)).scalars().all():
            if (task.input_params or {}).get("device_udid") == device_udid:
                return task
        return None

    async def list_by_project(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        task_type: Optional[str] = None,
        task_types: Optional[frozenset[str]] = None,
        exclude_task_types: Optional[frozenset[str]] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[AiTask], int]:
        cond = [AiTask.project_id == project_id]
        if task_type:
            cond.append(AiTask.task_type == task_type)
        if task_types:
            cond.append(AiTask.task_type.in_(task_types))
        if exclude_task_types:
            cond.append(AiTask.task_type.not_in(exclude_task_types))
        if status:
            cond.append(AiTask.status == status)

        stmt = (
            select(AiTask)
            .where(*cond)
            .order_by(AiTask.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        count_stmt = select(func.count()).select_from(AiTask).where(*cond)
        items = list((await db.execute(stmt)).scalars().all())
        total = (await db.execute(count_stmt)).scalar_one_or_none() or 0
        return items, total

    async def count_by_status(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        task_type: Optional[str] = None,
        task_types: Optional[frozenset[str]] = None,
        exclude_task_types: Optional[frozenset[str]] = None,
    ) -> dict[str, int]:
        """按状态分组统计任务数（任务中心统计卡）"""
        cond = [AiTask.project_id == project_id]
        if task_type:
            cond.append(AiTask.task_type == task_type)
        if task_types:
            cond.append(AiTask.task_type.in_(task_types))
        if exclude_task_types:
            cond.append(AiTask.task_type.not_in(exclude_task_types))
        stmt = (
            select(AiTask.status, func.count())
            .where(*cond)
            .group_by(AiTask.status)
        )
        rows = (await db.execute(stmt)).all()
        return {status: count for status, count in rows}

    async def count_active_by_type(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        task_type: Optional[str] = None,
        task_types: Optional[frozenset[str]] = None,
    ) -> int:
        """统计某项目下指定 task_type(s) 的活跃(pending/running)任务数。

        压测发起的项目级并发上限闸（PERF_MAX_CONCURRENT_RUNS_PER_PROJECT）用它，
        避免同项目同时跑过多压测打爆资源。计划压测与单场景压测须**合并计数**
        （传 task_types），否则两条发起路径各自计数会让总并发翻倍击穿上限。
        """
        cond = [
            AiTask.project_id == project_id,
            AiTask.status.in_(ACTIVE_STATUSES),
        ]
        if task_type:
            cond.append(AiTask.task_type == task_type)
        if task_types:
            cond.append(AiTask.task_type.in_(task_types))
        stmt = select(func.count()).select_from(AiTask).where(*cond)
        return (await db.execute(stmt)).scalar_one_or_none() or 0

    async def set_celery_task_id(
        self, db: AsyncSession, *, task_id: int, celery_task_id: str
    ) -> None:
        await db.execute(
            update(AiTask)
            .where(AiTask.id == task_id)
            .values(celery_task_id=celery_task_id)
        )
        await db.commit()

    async def set_ai_model(
        self, db: AsyncSession, *, task_id: int, ai_model: str
    ) -> None:
        """回写所用模型名。

        壳层只在 llm_kind != none 时自动回写；llm_kind="none" 但图内
        按需加载模型的任务（如 run_web_script 的 agent 模式）调用此方法补记。
        """
        await db.execute(
            update(AiTask).where(AiTask.id == task_id).values(ai_model=ai_model)
        )
        await db.commit()

    async def try_claim_running(
        self, db: AsyncSession, *, task_id: int
    ) -> bool:
        """原子抢占 pending -> running（执行幂等第2层）

        返回 True 表示本 worker 成功抢到执行权；False 表示已被抢/已完成
        （broker 重投或并发重复执行的兜底）。
        """
        now = datetime.now()
        res = await db.execute(
            update(AiTask)
            .where(AiTask.id == task_id, AiTask.status == AiTaskStatus.PENDING.value)
            .values(
                status=AiTaskStatus.RUNNING.value,
                started_at=now,
                heartbeat_at=now,
            )
        )
        await db.commit()
        return (res.rowcount or 0) == 1

    async def update_progress(
        self,
        db: AsyncSession,
        *,
        task_id: int,
        progress: Optional[int] = None,
        current_stage: Optional[str] = None,
        stage_index: Optional[int] = None,
        total_stages: Optional[int] = None,
        heartbeat: bool = True,
    ) -> None:
        values: dict[str, Any] = {}
        if progress is not None:
            values["progress"] = max(0, min(100, int(progress)))
        if current_stage is not None:
            values["current_stage"] = current_stage
        if stage_index is not None:
            values["stage_index"] = stage_index
        if total_stages is not None:
            values["total_stages"] = total_stages
        if heartbeat:
            values["heartbeat_at"] = datetime.now()
        if not values:
            return
        await db.execute(update(AiTask).where(AiTask.id == task_id).values(**values))
        await db.commit()

    async def heartbeat(self, db: AsyncSession, *, task_id: int) -> None:
        await db.execute(
            update(AiTask)
            .where(AiTask.id == task_id)
            .values(heartbeat_at=datetime.now())
        )
        await db.commit()

    async def set_succeeded(
        self,
        db: AsyncSession,
        *,
        task_id: int,
        result_summary: Optional[dict] = None,
        result_ref: Optional[dict] = None,
    ) -> bool:
        """仅当任务仍处于 pending/running 时写成功终态（条件 UPDATE，不覆盖终态）。

        防终态互覆盖：若任务已被僵尸回收改成 failed/canceled，跑完的 worker 再
        调用本方法将更新 0 行、不覆盖。返回是否实际更新。
        """
        result = await db.execute(
            update(AiTask)
            .where(AiTask.id == task_id, AiTask.status.in_(ACTIVE_STATUSES))
            .values(
                status=AiTaskStatus.SUCCEEDED.value,
                progress=100,
                result_summary=result_summary,
                result_ref=result_ref,
                completed_at=datetime.now(),
            )
        )
        await db.commit()
        return result.rowcount == 1

    async def set_failed(
        self, db: AsyncSession, *, task_id: int, error_message: str
    ) -> bool:
        """仅当任务仍处于 pending/running 时写失败终态（条件 UPDATE，不覆盖终态）。

        防终态互覆盖：若任务已被僵尸回收/取消改成其它终态，再调用本方法将更新
        0 行、不覆盖。返回是否实际更新。
        """
        result = await db.execute(
            update(AiTask)
            .where(AiTask.id == task_id, AiTask.status.in_(ACTIVE_STATUSES))
            .values(
                status=AiTaskStatus.FAILED.value,
                error_message=error_message[:2000],
                completed_at=datetime.now(),
            )
        )
        await db.commit()
        return result.rowcount == 1

    async def fail_if_active(
        self, db: AsyncSession, *, task_id: int, error_message: str
    ) -> bool:
        """仅当任务仍处于 pending/running 时标记失败（条件 UPDATE，不覆盖终态）。

        用于壳崩溃后的最后兜底与僵尸回收，返回是否实际更新。
        """
        result = await db.execute(
            update(AiTask)
            .where(AiTask.id == task_id, AiTask.status.in_(ACTIVE_STATUSES))
            .values(
                status=AiTaskStatus.FAILED.value,
                error_message=error_message[:2000],
                completed_at=datetime.now(),
            )
        )
        await db.commit()
        return result.rowcount == 1

    async def fail_if_zombie(
        self, db: AsyncSession, *, task: AiTask, timeout_s: int
    ) -> bool:
        """判定并回收僵尸任务，返回 True 表示已就地标记失败。

        僵尸定义：
          - pending 且创建超过 timeout_s 仍未被 worker 领取（投递丢失/worker 启动即崩）
          - running 且 heartbeat_at 超过 timeout_s 未更新（worker 进程死亡）
        """
        now = datetime.now()
        if task.status == AiTaskStatus.PENDING.value:
            ref_time = task.created_at
            reason = f"排队超时（{timeout_s}s 内未被 worker 领取），已自动标记失败"
        elif task.status == AiTaskStatus.RUNNING.value:
            ref_time = task.heartbeat_at or task.started_at or task.created_at
            reason = f"心跳超时（{timeout_s}s 无心跳，worker 可能已崩溃），已自动标记失败"
        else:
            return False

        if ref_time is None or (now - ref_time).total_seconds() < timeout_s:
            return False
        return await self.fail_if_active(db, task_id=task.id, error_message=reason)

    async def list_zombies(
        self,
        db: AsyncSession,
        *,
        running_timeout_s: int,
        pending_timeout_s: int,
    ) -> list[AiTask]:
        """列出僵尸候选任务（beat 巡检用）。

        - running：心跳超时即判死（壳内 5s 心跳线程，超时必为 worker 崩溃）
        - pending：用独立的更长阈值——worker 全忙时排队是正常状态，不能误杀
        """
        now = datetime.now()
        running_deadline = now - timedelta(seconds=running_timeout_s)
        pending_deadline = now - timedelta(seconds=pending_timeout_s)
        stmt = select(AiTask).where(
            or_(
                and_(
                    AiTask.status == AiTaskStatus.RUNNING.value,
                    func.coalesce(
                        AiTask.heartbeat_at, AiTask.started_at, AiTask.created_at
                    )
                    < running_deadline,
                ),
                and_(
                    AiTask.status == AiTaskStatus.PENDING.value,
                    AiTask.created_at < pending_deadline,
                ),
            )
        )
        return list((await db.execute(stmt)).scalars().all())

    async def set_canceled(self, db: AsyncSession, *, task_id: int) -> bool:
        """仅当任务仍处于 pending/running 时写取消终态（条件 UPDATE，不覆盖终态）。

        防终态互覆盖：若任务已被僵尸回收改成 failed 或已自然完成，再调用本方法将
        更新 0 行、不覆盖。返回是否实际更新。
        """
        result = await db.execute(
            update(AiTask)
            .where(AiTask.id == task_id, AiTask.status.in_(ACTIVE_STATUSES))
            .values(
                status=AiTaskStatus.CANCELED.value,
                completed_at=datetime.now(),
            )
        )
        await db.commit()
        return result.rowcount == 1

    async def cancel_if_pending(self, db: AsyncSession, *, task_id: int) -> bool:
        """仅当任务仍在排队（pending）时直接写取消终态。

        取消端点专用：排队中的任务可能根本没有 worker 会来领（broker 消息丢失 /
        队列无 worker），协作式取消信号永远无人响应。本方法与 worker 侧
        try_claim_running 同为「status == pending」条件 UPDATE，二者安全竞争、
        恰有一方成功：本方法赢 → 任务直接终态；worker 赢 → 0 行更新，
        协作取消标志会让刚起跑的图很快自行收尾。返回是否实际更新。
        """
        result = await db.execute(
            update(AiTask)
            .where(AiTask.id == task_id, AiTask.status == AiTaskStatus.PENDING.value)
            .values(
                status=AiTaskStatus.CANCELED.value,
                completed_at=datetime.now(),
            )
        )
        await db.commit()
        return result.rowcount == 1

    async def delete(self, db: AsyncSession, *, task_id: int) -> None:
        """删除任务（事件流由外键 ON DELETE CASCADE 级联清理）"""
        task = await db.get(AiTask, task_id)
        if task is not None:
            await db.delete(task)
            await db.commit()

    # ── 事件 ────────────────────────────────────────────────

    async def max_event_seq(self, db: AsyncSession, *, task_id: int) -> int:
        """返回该任务已落库事件的最大 seq；无事件返回 0。

        供 StreamAdapter 初始化时续接 seq —— task_acks_late 重投同一任务时，
        新 worker 从 DB 已有 max_seq+1 继续编号，不会与已落库 seq 撞唯一约束。
        """
        stmt = select(func.max(AiTaskEvent.seq)).where(AiTaskEvent.task_id == task_id)
        return (await db.execute(stmt)).scalar_one_or_none() or 0

    async def append_events(
        self, db: AsyncSession, *, task_id: int, events: Sequence[dict]
    ) -> None:
        """批量落库事件（INSERT IGNORE，忽略 (task_id,seq) 唯一约束冲突）。

        events 每项需含 seq/type/payload。task_acks_late=True 的重投可能让同一
        (task_id, seq) 再次入库——用 MySQL ``INSERT ... IGNORE`` 语义让已存在的
        行被静默跳过，既不报错、也不回滚整批，保证回放数据与实时流不丢段。
        events 内部若有重复 seq，去重保留首次出现的那条。
        """
        if not events:
            return
        seen: set[int] = set()
        rows: list[dict] = []
        for ev in events:
            seq = ev["seq"]
            if seq in seen:
                continue
            seen.add(seq)
            rows.append(
                {
                    "task_id": task_id,
                    "seq": seq,
                    "event_type": ev["type"],
                    "payload": ev.get("payload"),
                }
            )
        # prefix_with("IGNORE") -> INSERT IGNORE INTO ...：冲突行跳过，不抛 IntegrityError
        await db.execute(mysql_insert(AiTaskEvent).prefix_with("IGNORE"), rows)
        await db.commit()

    async def list_events(
        self, db: AsyncSession, *, task_id: int, after_seq: int = 0
    ) -> list[AiTaskEvent]:
        stmt = (
            select(AiTaskEvent)
            .where(AiTaskEvent.task_id == task_id, AiTaskEvent.seq > after_seq)
            .order_by(AiTaskEvent.seq.asc())
        )
        return list((await db.execute(stmt)).scalars().all())

    # ── 归档 ────────────────────────────────────────────────

    async def list_archivable_task_ids(
        self, db: AsyncSession, *, before: datetime, limit: int
    ) -> list[int]:
        """终态早于 before 且仍有事件留存的任务 id（归档候选）"""
        stmt = (
            select(AiTask.id)
            .where(
                AiTask.status.notin_(ACTIVE_STATUSES),
                AiTask.completed_at.isnot(None),
                AiTask.completed_at < before,
                select(AiTaskEvent.id)
                .where(AiTaskEvent.task_id == AiTask.id)
                .limit(1)
                .exists(),
            )
            .order_by(AiTask.completed_at.asc())
            .limit(limit)
        )
        return list((await db.execute(stmt)).scalars().all())

    async def delete_events(self, db: AsyncSession, *, task_id: int) -> int:
        """删除任务的全部事件行（归档导出成功后调用），返回删除行数"""
        res = await db.execute(
            sa_delete(AiTaskEvent).where(AiTaskEvent.task_id == task_id)
        )
        await db.commit()
        return res.rowcount or 0


crud_ai_task = CRUDAiTask()
