"""
Bug AI 分析结果 CRUD 操作
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bug.bug_ai_analysis import AnalysisStatus, BugAiAnalysis


class CRUDBugAiAnalysis:
    """Bug AI 分析结果 CRUD 操作类"""

    async def create_or_reset(
        self,
        db: AsyncSession,
        *,
        bug_id: int,
    ) -> BugAiAnalysis:
        """
        创建或重置 AI 分析记录。

        若已存在分析记录，则清空旧结果并重置为 processing 状态；
        否则创建新记录。

        Args:
            db: 数据库会话
            bug_id: Bug ID

        Returns:
            BugAiAnalysis: 分析记录实例
        """
        analysis_id = f"analysis_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"

        existing = await self.get_by_bug(db, bug_id)
        if existing:
            existing.analysis_id = analysis_id
            existing.analysis_status = AnalysisStatus.PROCESSING.value
            existing.root_cause_analysis = None
            existing.solution_recommendation = None
            existing.similar_bugs = None
            existing.severity_assessment = None
            existing.error_message = None
            existing.completed_at = None
            db.add(existing)
            await db.commit()
            await db.refresh(existing)
            return existing

        record = BugAiAnalysis(
            bug_id=bug_id,
            analysis_id=analysis_id,
            analysis_status=AnalysisStatus.PROCESSING.value,
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        return record

    async def get_by_bug(
        self,
        db: AsyncSession,
        bug_id: int,
    ) -> Optional[BugAiAnalysis]:
        """
        获取 Bug 的 AI 分析记录（一对一）。

        Args:
            db: 数据库会话
            bug_id: Bug ID

        Returns:
            Optional[BugAiAnalysis]: 分析记录，不存在返回 None
        """
        stmt = select(BugAiAnalysis).where(BugAiAnalysis.bug_id == bug_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_result(
        self,
        db: AsyncSession,
        *,
        analysis: BugAiAnalysis,
        root_cause_analysis: Optional[dict] = None,
        solution_recommendation: Optional[dict] = None,
        similar_bugs: Optional[list] = None,
        severity_assessment: Optional[dict] = None,
        status: str = AnalysisStatus.COMPLETED.value,
        error_message: Optional[str] = None,
    ) -> BugAiAnalysis:
        """
        更新 AI 分析结果。

        Args:
            db: 数据库会话
            analysis: 分析记录实例
            root_cause_analysis: 根因分析结果
            solution_recommendation: 解决方案推荐
            similar_bugs: 相似 Bug 列表
            severity_assessment: 严重程度评估
            status: 分析状态（completed/failed）
            error_message: 失败时的错误信息

        Returns:
            BugAiAnalysis: 更新后的分析记录
        """
        analysis.analysis_status = status
        analysis.root_cause_analysis = root_cause_analysis
        analysis.solution_recommendation = solution_recommendation
        analysis.similar_bugs = similar_bugs
        analysis.severity_assessment = severity_assessment
        analysis.error_message = error_message
        analysis.completed_at = datetime.utcnow()
        db.add(analysis)
        await db.commit()
        await db.refresh(analysis)
        return analysis


crud_bug_ai_analysis = CRUDBugAiAnalysis()
