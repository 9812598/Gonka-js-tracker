import pytest
import pytest_asyncio
import tempfile
import os
from backend.database import CacheDB


@pytest_asyncio.fixture
async def db():
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
        db_path = f.name
    
    cache_db = CacheDB(db_path)
    await cache_db.initialize()
    
    yield cache_db
    
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.mark.asyncio
async def test_database_initialization(db):
    assert os.path.exists(db.db_path)


@pytest.mark.asyncio
async def test_save_and_get_stats(db):
    stats = {
        "index": "participant_1",
        "address": "gonka1abc...",
        "inference_count": "10",
        "missed_requests": "2",
        "validated_inferences": "8",
        "invalidated_inferences": "0"
    }
    
    await db.save_stats(epoch_id=1, height=1000, participant_index="participant_1", stats=stats)
    
    result = await db.get_stats(epoch_id=1)
    assert result is not None
    assert len(result) == 1
    assert result[0]["index"] == "participant_1"
    assert result[0]["inference_count"] == "10"
    assert "_cached_at" in result[0]
    assert "_height" in result[0]


@pytest.mark.asyncio
async def test_save_stats_batch(db):
    participants_stats = [
        {
            "index": "participant_1",
            "address": "gonka1abc...",
            "inference_count": "10",
            "missed_requests": "2"
        },
        {
            "index": "participant_2",
            "address": "gonka1def...",
            "inference_count": "15",
            "missed_requests": "1"
        }
    ]
    
    await db.save_stats_batch(epoch_id=2, height=2000, participants_stats=participants_stats)
    
    result = await db.get_stats(epoch_id=2)
    assert result is not None
    assert len(result) == 2


@pytest.mark.asyncio
async def test_has_stats_for_epoch(db):
    assert not await db.has_stats_for_epoch(epoch_id=3)
    
    await db.save_stats(
        epoch_id=3,
        height=3000,
        participant_index="participant_1",
        stats={"index": "participant_1", "inference_count": "5"}
    )
    
    assert await db.has_stats_for_epoch(epoch_id=3)


@pytest.mark.asyncio
async def test_mark_and_check_epoch_finished(db):
    assert not await db.is_epoch_finished(epoch_id=4)
    
    await db.mark_epoch_finished(epoch_id=4, finish_height=4000)
    
    assert await db.is_epoch_finished(epoch_id=4)
    
    finish_height = await db.get_epoch_finish_height(epoch_id=4)
    assert finish_height == 4000


@pytest.mark.asyncio
async def test_epoch_stats_immutability(db):
    stats_v1 = {
        "index": "participant_1",
        "inference_count": "10"
    }
    
    await db.save_stats(epoch_id=5, height=5000, participant_index="participant_1", stats=stats_v1)
    await db.mark_epoch_finished(epoch_id=5, finish_height=5000)
    
    result_v1 = await db.get_stats(epoch_id=5, height=5000)
    assert result_v1[0]["inference_count"] == "10"
    
    stats_v2 = {
        "index": "participant_1",
        "inference_count": "20"
    }
    await db.save_stats(epoch_id=5, height=5100, participant_index="participant_1", stats=stats_v2)
    
    result_v2_at_5100 = await db.get_stats(epoch_id=5, height=5100)
    assert result_v2_at_5100[0]["inference_count"] == "20"
    
    result_v1_still_at_5000 = await db.get_stats(epoch_id=5, height=5000)
    assert result_v1_still_at_5000[0]["inference_count"] == "10"


@pytest.mark.asyncio
async def test_clear_epoch_stats(db):
    await db.save_stats(
        epoch_id=6,
        height=6000,
        participant_index="participant_1",
        stats={"index": "participant_1"}
    )
    await db.mark_epoch_finished(epoch_id=6, finish_height=6000)
    
    assert await db.has_stats_for_epoch(epoch_id=6)
    assert await db.is_epoch_finished(epoch_id=6)
    
    await db.clear_epoch_stats(epoch_id=6)
    
    assert not await db.has_stats_for_epoch(epoch_id=6)
    assert not await db.is_epoch_finished(epoch_id=6)


@pytest.mark.asyncio
async def test_multiple_participants_same_epoch(db):
    participants = [
        {"index": f"participant_{i}", "inference_count": f"{i * 10}"}
        for i in range(1, 11)
    ]
    
    await db.save_stats_batch(epoch_id=7, height=7000, participants_stats=participants)
    
    result = await db.get_stats(epoch_id=7)
    assert len(result) == 10
    
    indices = [p["index"] for p in result]
    assert "participant_1" in indices
    assert "participant_10" in indices


@pytest.mark.asyncio
async def test_save_and_retrieve_models(db):
    stats = {
        "index": "participant_1",
        "address": "gonka1abc...",
        "models": ["Llama-3.1-8B", "Qwen2.5-7B"],
        "inference_count": "10",
        "missed_requests": "2"
    }
    
    await db.save_stats(epoch_id=8, height=8000, participant_index="participant_1", stats=stats)
    
    result = await db.get_stats(epoch_id=8)
    assert result is not None
    assert len(result) == 1
    assert result[0]["index"] == "participant_1"
    assert result[0]["models"] == ["Llama-3.1-8B", "Qwen2.5-7B"]


@pytest.mark.asyncio
async def test_save_stats_with_empty_models(db):
    stats = {
        "index": "participant_2",
        "address": "gonka1def...",
        "models": [],
        "inference_count": "5"
    }
    
    await db.save_stats(epoch_id=9, height=9000, participant_index="participant_2", stats=stats)
    
    result = await db.get_stats(epoch_id=9)
    assert result is not None
    assert result[0]["models"] == []


@pytest.mark.asyncio
async def test_save_and_get_jail_status(db):
    jail_statuses = [
        {
            "participant_index": "gonka1abc",
            "is_jailed": True,
            "jailed_until": "2025-10-20T00:00:00Z",
            "ready_to_unjail": False,
            "valcons_address": "gonkavalcons1abc"
        },
        {
            "participant_index": "gonka1def",
            "is_jailed": False,
            "jailed_until": None,
            "ready_to_unjail": False,
            "valcons_address": "gonkavalcons1def"
        }
    ]
    
    await db.save_jail_status_batch(epoch_id=56, jail_statuses=jail_statuses)
    
    result = await db.get_jail_status(epoch_id=56)
    assert result is not None
    assert len(result) == 2
    assert result[0]["participant_index"] in ["gonka1abc", "gonka1def"]
    assert result[0]["is_jailed"] in [True, False]


@pytest.mark.asyncio
async def test_get_jail_status_for_participant(db):
    jail_statuses = [
        {
            "participant_index": "gonka1abc",
            "is_jailed": True,
            "jailed_until": "2025-10-20T00:00:00Z",
            "ready_to_unjail": True,
            "valcons_address": "gonkavalcons1abc"
        }
    ]
    
    await db.save_jail_status_batch(epoch_id=56, jail_statuses=jail_statuses)
    
    result = await db.get_jail_status(epoch_id=56, participant_index="gonka1abc")
    assert result is not None
    assert len(result) == 1
    assert result[0]["is_jailed"] is True
    assert result[0]["ready_to_unjail"] is True


@pytest.mark.asyncio
async def test_save_and_get_node_health(db):
    health_statuses = [
        {
            "participant_index": "gonka1abc",
            "is_healthy": True,
            "error_message": None,
            "response_time_ms": 150
        },
        {
            "participant_index": "gonka1def",
            "is_healthy": False,
            "error_message": "Connection timeout",
            "response_time_ms": None
        }
    ]
    
    await db.save_node_health_batch(health_statuses=health_statuses)
    
    result = await db.get_node_health()
    assert result is not None
    assert len(result) == 2
    
    healthy_node = next(r for r in result if r["participant_index"] == "gonka1abc")
    assert healthy_node["is_healthy"] is True
    assert healthy_node["response_time_ms"] == 150
    
    unhealthy_node = next(r for r in result if r["participant_index"] == "gonka1def")
    assert unhealthy_node["is_healthy"] is False
    assert unhealthy_node["error_message"] == "Connection timeout"


@pytest.mark.asyncio
async def test_get_node_health_for_participant(db):
    health_statuses = [
        {
            "participant_index": "gonka1abc",
            "is_healthy": True,
            "error_message": None,
            "response_time_ms": 200
        }
    ]
    
    await db.save_node_health_batch(health_statuses=health_statuses)
    
    result = await db.get_node_health(participant_index="gonka1abc")
    assert result is not None
    assert len(result) == 1
    assert result[0]["is_healthy"] is True
    assert result[0]["response_time_ms"] == 200


@pytest.mark.asyncio
async def test_save_stats_with_seed_signature(db):
    stats = {
        "index": "participant_1",
        "address": "gonka1abc...",
        "inference_count": "10",
        "missed_requests": "2"
    }
    seed_sig = "ed2e44480f2c280c39a4241bc4750480"
    
    await db.save_stats(
        epoch_id=1, 
        height=1000, 
        participant_index="participant_1", 
        stats=stats,
        seed_signature=seed_sig
    )
    
    result = await db.get_stats(epoch_id=1)
    assert result is not None
    assert len(result) == 1
    assert result[0]["_seed_signature"] == seed_sig


@pytest.mark.asyncio
async def test_save_stats_batch_with_seed(db):
    stats_list = [
        {
            "index": "participant_1",
            "address": "gonka1abc",
            "inference_count": "10",
            "seed_signature": "seed_sig_1"
        },
        {
            "index": "participant_2",
            "address": "gonka2def",
            "inference_count": "5",
            "seed_signature": "seed_sig_2"
        }
    ]
    
    await db.save_stats_batch(epoch_id=1, height=1000, participants_stats=stats_list)
    
    result = await db.get_stats(epoch_id=1)
    assert result is not None
    assert len(result) == 2
    assert result[0]["_seed_signature"] == "seed_sig_1"
    assert result[1]["_seed_signature"] == "seed_sig_2"


@pytest.mark.asyncio
async def test_save_and_get_reward(db):
    rewards = [
        {
            "epoch_id": 56,
            "participant_id": "gonka1abc",
            "rewarded_coins": "38627452617213",
            "claimed": True
        }
    ]
    
    await db.save_reward_batch(rewards)
    
    result = await db.get_reward(epoch_id=56, participant_id="gonka1abc")
    assert result is not None
    assert result["epoch_id"] == 56
    assert result["participant_id"] == "gonka1abc"
    assert result["rewarded_coins"] == "38627452617213"
    assert result["claimed"] is True


@pytest.mark.asyncio
async def test_get_rewards_for_participant(db):
    rewards = [
        {
            "epoch_id": 54,
            "participant_id": "gonka1abc",
            "rewarded_coins": "50842445416245",
            "claimed": True
        },
        {
            "epoch_id": 55,
            "participant_id": "gonka1abc",
            "rewarded_coins": "0",
            "claimed": False
        },
        {
            "epoch_id": 56,
            "participant_id": "gonka1abc",
            "rewarded_coins": "38627452617213",
            "claimed": True
        }
    ]
    
    await db.save_reward_batch(rewards)
    
    result = await db.get_rewards_for_participant(
        participant_id="gonka1abc",
        epoch_ids=[54, 55, 56]
    )
    assert result is not None
    assert len(result) == 3
    assert result[0]["epoch_id"] == 56
    assert result[1]["epoch_id"] == 55
    assert result[2]["epoch_id"] == 54


@pytest.mark.asyncio
async def test_get_rewards_empty(db):
    result = await db.get_reward(epoch_id=99, participant_id="nonexistent")
    assert result is None
    
    result = await db.get_rewards_for_participant(
        participant_id="nonexistent",
        epoch_ids=[54, 55, 56]
    )
    assert result == []

