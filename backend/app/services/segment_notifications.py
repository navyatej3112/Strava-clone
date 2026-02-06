"""Segment PR/KOM notification logic with idempotency and anti-spam."""
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from app.models import SegmentEffort, Notification
from app.models.notification import NotificationType
from app.models.activity import ActivityVisibility


async def maybe_notify_segment_pr(
    db: AsyncSession,
    user_id: UUID,
    segment_id: UUID,
    segment_name: str,
    new_effort_time_s: int,
    activity_id: UUID,
) -> bool:
    """
    Check if new effort is a PR and create notification if so.
    Returns True if notification was created, False otherwise.
    """
    # Get user's best effort_time_s for this segment (all visibilities)
    best_stmt = (
        select(func.min(SegmentEffort.effort_time_s))
        .where(SegmentEffort.user_id == user_id)
        .where(SegmentEffort.segment_id == segment_id)
    )
    best_result = await db.execute(best_stmt)
    best_time = best_result.scalar()

    # If this is not the best, no PR
    if best_time is None or new_effort_time_s != best_time:
        return False

    # Get previous best (second best, excluding this activity)
    prev_best_stmt = (
        select(func.min(SegmentEffort.effort_time_s))
        .where(SegmentEffort.user_id == user_id)
        .where(SegmentEffort.segment_id == segment_id)
        .where(SegmentEffort.activity_id != activity_id)
    )
    prev_best_result = await db.execute(prev_best_stmt)
    prev_best_time = prev_best_result.scalar()

    # Only notify if improvement >= 1 second
    if prev_best_time is not None and (prev_best_time - new_effort_time_s) < 1:
        return False

    # Create notification with dedupe_key (upsert pattern)
    dedupe_key = f"segment_pr:{user_id}:{segment_id}"
    stmt = (
        insert(Notification)
        .values(
            recipient_user_id=user_id,
            actor_user_id=user_id,
            type=NotificationType.SEGMENT_PR,
            activity_id=activity_id,
            data={
                "segment_id": str(segment_id),
                "segment_name": segment_name,
                "activity_id": str(activity_id),
                "effort_time_s": new_effort_time_s,
                "type": "pr",
            },
            dedupe_key=dedupe_key,
        )
        .on_conflict_do_nothing(index_elements=["dedupe_key"])
    )
    await db.execute(stmt)
    await db.flush()
    return True


async def maybe_notify_segment_kom(
    db: AsyncSession,
    user_id: UUID,
    segment_id: UUID,
    segment_name: str,
    new_effort_time_s: int,
    activity_id: UUID,
    activity_visibility: str,
) -> bool:
    """
    Check if new PUBLIC effort is a KOM and create notification if so.
    Returns True if notification was created, False otherwise.
    """
    # KOM only for public activities
    if activity_visibility != ActivityVisibility.PUBLIC.value:
        return False

    # Get segment's best PUBLIC effort_time_s
    best_public_stmt = (
        select(func.min(SegmentEffort.effort_time_s))
        .where(SegmentEffort.segment_id == segment_id)
        .where(SegmentEffort.visibility == ActivityVisibility.PUBLIC.value)
    )
    best_public_result = await db.execute(best_public_stmt)
    best_public_time = best_public_result.scalar()

    # If this is not the best public, no KOM
    if best_public_time is None or new_effort_time_s != best_public_time:
        return False

    # Get previous best public (excluding this activity)
    prev_best_public_stmt = (
        select(func.min(SegmentEffort.effort_time_s))
        .where(SegmentEffort.segment_id == segment_id)
        .where(SegmentEffort.visibility == ActivityVisibility.PUBLIC.value)
        .where(SegmentEffort.activity_id != activity_id)
    )
    prev_best_public_result = await db.execute(prev_best_public_stmt)
    prev_best_public_time = prev_best_public_result.scalar()

    # Only notify if improvement >= 1 second
    if prev_best_public_time is not None and (prev_best_public_time - new_effort_time_s) < 1:
        return False

    # Create notification with dedupe_key (upsert pattern)
    dedupe_key = f"segment_kom:{user_id}:{segment_id}"
    stmt = (
        insert(Notification)
        .values(
            recipient_user_id=user_id,
            actor_user_id=user_id,
            type=NotificationType.SEGMENT_KOM,
            activity_id=activity_id,
            data={
                "segment_id": str(segment_id),
                "segment_name": segment_name,
                "activity_id": str(activity_id),
                "effort_time_s": new_effort_time_s,
                "type": "kom",
            },
            dedupe_key=dedupe_key,
        )
        .on_conflict_do_nothing(index_elements=["dedupe_key"])
    )
    await db.execute(stmt)
    await db.flush()
    return True
