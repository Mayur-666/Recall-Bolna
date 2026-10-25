import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import IngestionJob


class JobsRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def enqueue(self, user_id: uuid.UUID, conversation_id: uuid.UUID) -> IngestionJob:
        job = IngestionJob(user_id=user_id, conversation_id=conversation_id, status="queued")
        self.session.add(job)
        await self.session.flush()
        return job

    async def claim_next(self) -> IngestionJob | None:
        """Claim the oldest queued job. SKIP LOCKED lets several workers run safely."""
        job = await self.session.scalar(
            select(IngestionJob)
            .where(IngestionJob.status == "queued")
            .order_by(IngestionJob.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if job is not None:
            job.status = "running"
        return job

    async def claim(self, job_id: uuid.UUID) -> bool:
        """Claim one specific queued job; False if another worker already has it."""
        job = await self.session.scalar(
            select(IngestionJob)
            .where(IngestionJob.id == job_id, IngestionJob.status == "queued")
            .with_for_update(skip_locked=True)
        )
        if job is None:
            return False
        job.status = "running"
        return True
