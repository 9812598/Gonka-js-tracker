import pytest
import pytest_asyncio
from backend.database import CacheDB
from backend.models import InferenceResponse
import tempfile
import os


@pytest_asyncio.fixture
async def db():
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    temp_db.close()
    
    cache_db = CacheDB(temp_db.name)
    await cache_db.initialize()
    
    yield cache_db
    
    os.unlink(temp_db.name)


@pytest.mark.asyncio
async def test_save_and_get_epoch_total_rewards(db):
    await db.save_epoch_total_rewards(epoch_id=10, total_rewards_gnk=50000)
    
    result = await db.get_epoch_total_rewards(epoch_id=10)
    assert result == 50000


@pytest.mark.asyncio
async def test_get_epoch_total_rewards_not_found(db):
    result = await db.get_epoch_total_rewards(epoch_id=999)
    assert result is None


@pytest.mark.asyncio
async def test_replace_epoch_total_rewards(db):
    await db.save_epoch_total_rewards(epoch_id=10, total_rewards_gnk=50000)
    await db.save_epoch_total_rewards(epoch_id=10, total_rewards_gnk=60000)
    
    result = await db.get_epoch_total_rewards(epoch_id=10)
    assert result == 60000


@pytest.mark.asyncio
async def test_multiple_epochs_total_rewards(db):
    await db.save_epoch_total_rewards(epoch_id=10, total_rewards_gnk=50000)
    await db.save_epoch_total_rewards(epoch_id=11, total_rewards_gnk=60000)
    await db.save_epoch_total_rewards(epoch_id=12, total_rewards_gnk=70000)
    
    assert await db.get_epoch_total_rewards(epoch_id=10) == 50000
    assert await db.get_epoch_total_rewards(epoch_id=11) == 60000
    assert await db.get_epoch_total_rewards(epoch_id=12) == 70000


def test_inference_response_with_total_rewards():
    from backend.models import ParticipantStats, CurrentEpochStats
    
    stats = CurrentEpochStats(
        inference_count="100",
        missed_requests="5",
        earned_coins="1000000000",
        rewarded_coins="950000000",
        burned_coins="50000000",
        validated_inferences="95",
        invalidated_inferences="5"
    )
    
    participant = ParticipantStats(
        index="0",
        address="gonka1abc123",
        weight=100,
        validator_key="validatorkey123",
        inference_url="http://localhost:8000",
        status="INFERENCE",
        models=["model1"],
        current_epoch_stats=stats
    )
    
    response = InferenceResponse(
        epoch_id=10,
        height=12345,
        participants=[participant],
        cached_at="2023-01-01T00:00:00",
        is_current=False,
        total_assigned_rewards_gnk=50000
    )
    
    assert response.total_assigned_rewards_gnk == 50000
    assert response.is_current == False


def test_inference_response_without_total_rewards():
    from backend.models import ParticipantStats, CurrentEpochStats
    
    stats = CurrentEpochStats(
        inference_count="100",
        missed_requests="5",
        earned_coins="1000000000",
        rewarded_coins="950000000",
        burned_coins="50000000",
        validated_inferences="95",
        invalidated_inferences="5"
    )
    
    participant = ParticipantStats(
        index="0",
        address="gonka1abc123",
        weight=100,
        current_epoch_stats=stats
    )
    
    response = InferenceResponse(
        epoch_id=10,
        height=12345,
        participants=[participant],
        is_current=True
    )
    
    assert response.total_assigned_rewards_gnk is None
    assert response.is_current == True

