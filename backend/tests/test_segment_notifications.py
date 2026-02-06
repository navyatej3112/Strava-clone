"""Tests for segment PR/KOM notification triggers."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Segment, SegmentEffort, Activity, Notification, User, TrackPoint
from app.models.activity import ActivitySportType, ActivityStatus, ActivityVisibility
from app.models.notification import NotificationType
from app.services.segment_notifications import maybe_notify_segment_pr, maybe_notify_segment_kom


@pytest.mark.asyncio
async def test_pr_notify_created_when_new_effort_is_fastest(db: AsyncSession):
    """PR notification created when new effort becomes user's fastest."""
    user_id = uuid4()
    segment_id = uuid4()
    activity_id = uuid4()

    # Create user and segment
    user = User(id=user_id, email="test@example.com", name="Test User", hashed_password="hash")
    db.add(user)
    segment = Segment(
        id=segment_id,
        owner_user_id=user_id,
        name="Test Segment",
        polyline="test_polyline",
        distance_m=1000.0,
    )
    db.add(segment)
    await db.commit()

    # Create an existing slower effort
    old_effort = SegmentEffort(
        id=uuid4(),
        segment_id=segment_id,
        activity_id=uuid4(),
        user_id=user_id,
        visibility=ActivityVisibility.PUBLIC.value,
        effort_time_s=120,
        effort_distance_m=1000.0,
        avg_speed_kmh=30.0,
        started_at=datetime.now(timezone.utc),
    )
    db.add(old_effort)
    await db.commit()

    # New faster effort (100s vs 120s, improvement >= 1s)
    result = await maybe_notify_segment_pr(
        db, user_id, segment_id, "Test Segment", 100, activity_id
    )
    await db.commit()

    assert result is True
    notif = await db.execute(
        select(Notification).where(Notification.dedupe_key == f"segment_pr:{user_id}:{segment_id}")
    )
    n = notif.scalar_one_or_none()
    assert n is not None
    assert n.type == NotificationType.SEGMENT_PR
    assert n.recipient_user_id == user_id
    assert n.data["segment_name"] == "Test Segment"
    assert n.data["effort_time_s"] == 100


@pytest.mark.asyncio
async def test_pr_notify_not_created_when_equal_or_worse(db: AsyncSession):
    """PR notification not created when effort is equal or worse."""
    user_id = uuid4()
    segment_id = uuid4()
    activity_id = uuid4()

    user = User(id=user_id, email="test@example.com", name="Test User", hashed_password="hash")
    db.add(user)
    segment = Segment(
        id=segment_id,
        owner_user_id=user_id,
        name="Test Segment",
        polyline="test_polyline",
        distance_m=1000.0,
    )
    db.add(segment)
    await db.commit()

    # Existing effort at 100s
    old_effort = SegmentEffort(
        id=uuid4(),
        segment_id=segment_id,
        activity_id=uuid4(),
        user_id=user_id,
        visibility=ActivityVisibility.PUBLIC.value,
        effort_time_s=100,
        effort_distance_m=1000.0,
        avg_speed_kmh=30.0,
        started_at=datetime.now(timezone.utc),
    )
    db.add(old_effort)
    await db.commit()

    # New effort at same time (100s) - no improvement
    result = await maybe_notify_segment_pr(
        db, user_id, segment_id, "Test Segment", 100, activity_id
    )
    await db.commit()

    assert result is False
    notif = await db.execute(
        select(Notification).where(Notification.dedupe_key == f"segment_pr:{user_id}:{segment_id}")
    )
    assert notif.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_kom_notify_created_only_for_public_fastest(db: AsyncSession):
    """KOM notification created only for public effort that is fastest public."""
    user_id = uuid4()
    segment_id = uuid4()
    activity_id = uuid4()

    user = User(id=user_id, email="test@example.com", name="Test User", hashed_password="hash")
    db.add(user)
    segment = Segment(
        id=segment_id,
        owner_user_id=user_id,
        name="Test Segment",
        polyline="test_polyline",
        distance_m=1000.0,
    )
    db.add(segment)
    await db.commit()

    # Existing slower public effort
    old_effort = SegmentEffort(
        id=uuid4(),
        segment_id=segment_id,
        activity_id=uuid4(),
        user_id=uuid4(),  # different user
        visibility=ActivityVisibility.PUBLIC.value,
        effort_time_s=120,
        effort_distance_m=1000.0,
        avg_speed_kmh=30.0,
        started_at=datetime.now(timezone.utc),
    )
    db.add(old_effort)
    await db.commit()

    # New faster public effort (100s vs 120s)
    result = await maybe_notify_segment_kom(
        db, user_id, segment_id, "Test Segment", 100, activity_id, ActivityVisibility.PUBLIC.value
    )
    await db.commit()

    assert result is True
    notif = await db.execute(
        select(Notification).where(Notification.dedupe_key == f"segment_kom:{user_id}:{segment_id}")
    )
    n = notif.scalar_one_or_none()
    assert n is not None
    assert n.type == NotificationType.SEGMENT_KOM
    assert n.data["type"] == "kom"


@pytest.mark.asyncio
async def test_kom_notify_not_created_for_private(db: AsyncSession):
    """KOM notification not created for private/followers activities."""
    user_id = uuid4()
    segment_id = uuid4()
    activity_id = uuid4()

    user = User(id=user_id, email="test@example.com", name="Test User", hashed_password="hash")
    db.add(user)
    segment = Segment(
        id=segment_id,
        owner_user_id=user_id,
        name="Test Segment",
        polyline="test_polyline",
        distance_m=1000.0,
    )
    db.add(segment)
    await db.commit()

    # Try with private visibility
    result = await maybe_notify_segment_kom(
        db, user_id, segment_id, "Test Segment", 50, activity_id, ActivityVisibility.PRIVATE.value
    )
    await db.commit()

    assert result is False
    notif = await db.execute(
        select(Notification).where(Notification.dedupe_key == f"segment_kom:{user_id}:{segment_id}")
    )
    assert notif.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_notification_idempotency(db: AsyncSession):
    """Running notification logic twice does not create duplicate notifications."""
    user_id = uuid4()
    segment_id = uuid4()
    activity_id = uuid4()

    user = User(id=user_id, email="test@example.com", name="Test User", hashed_password="hash")
    db.add(user)
    segment = Segment(
        id=segment_id,
        owner_user_id=user_id,
        name="Test Segment",
        polyline="test_polyline",
        distance_m=1000.0,
    )
    db.add(segment)
    await db.commit()

    # First call creates notification
    result1 = await maybe_notify_segment_pr(
        db, user_id, segment_id, "Test Segment", 100, activity_id
    )
    await db.commit()
    assert result1 is True

    # Second call with same dedupe_key should not create duplicate
    result2 = await maybe_notify_segment_pr(
        db, user_id, segment_id, "Test Segment", 100, activity_id
    )
    await db.commit()

    # Count notifications with this dedupe_key
    count = await db.execute(
        select(func.count(Notification.id)).where(
            Notification.dedupe_key == f"segment_pr:{user_id}:{segment_id}"
        )
    )
    assert count.scalar() == 1


@pytest.mark.asyncio
async def test_improvement_threshold_one_second(db: AsyncSession):
    """Only notify if improvement is >= 1 second."""
    user_id = uuid4()
    segment_id = uuid4()
    activity_id = uuid4()

    user = User(id=user_id, email="test@example.com", name="Test User", hashed_password="hash")
    db.add(user)
    segment = Segment(
        id=segment_id,
        owner_user_id=user_id,
        name="Test Segment",
        polyline="test_polyline",
        distance_m=1000.0,
    )
    db.add(segment)
    await db.commit()

    # Existing effort at 100s
    old_effort = SegmentEffort(
        id=uuid4(),
        segment_id=segment_id,
        activity_id=uuid4(),
        user_id=user_id,
        visibility=ActivityVisibility.PUBLIC.value,
        effort_time_s=100,
        effort_distance_m=1000.0,
        avg_speed_kmh=30.0,
        started_at=datetime.now(timezone.utc),
    )
    db.add(old_effort)
    await db.commit()

    # New effort at 99s (improvement of only 1s, should notify)
    result = await maybe_notify_segment_pr(
        db, user_id, segment_id, "Test Segment", 99, activity_id
    )
    await db.commit()
    assert result is True

    # Clear and try again with 100s (no improvement)
    await db.execute(select(Notification).where(Notification.dedupe_key == f"segment_pr:{user_id}:{segment_id}").delete())
    await db.commit()

    result2 = await maybe_notify_segment_pr(
        db, user_id, segment_id, "Test Segment", 100, activity_id
    )
    await db.commit()
    assert result2 is False
