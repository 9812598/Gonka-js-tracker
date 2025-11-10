import pytest
import pytest_asyncio
import tempfile
import os
from backend.client import GonkaClient
from backend.database import CacheDB
from backend.service import InferenceService


@pytest_asyncio.fixture
async def cache_db():
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
        db_path = f.name
    
    db = CacheDB(db_path)
    await db.initialize()
    
    yield db
    
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest_asyncio.fixture
async def client():
    return GonkaClient(base_urls=["http://node2.gonka.ai:8000"])


@pytest_asyncio.fixture
async def service(client, cache_db):
    return InferenceService(client=client, cache_db=cache_db)


@pytest.mark.asyncio
async def test_service_initialization(service):
    assert service.client is not None
    assert service.cache_db is not None
    assert service.current_epoch_id is None


@pytest.mark.asyncio
async def test_get_current_epoch_stats(service):
    response = await service.get_current_epoch_stats()
    
    assert response is not None
    assert response.epoch_id > 0
    assert response.height > 0
    assert len(response.participants) > 0
    assert response.is_current is True
    
    first_participant = response.participants[0]
    assert first_participant.index
    assert first_participant.address
    assert first_participant.missed_rate >= 0.0


@pytest.mark.asyncio
async def test_get_current_epoch_caching(service):
    response1 = await service.get_current_epoch_stats()
    
    has_cached = await service.cache_db.has_stats_for_epoch(response1.epoch_id)
    assert has_cached is True


@pytest.mark.asyncio
async def test_get_historical_epoch_stats(service):
    current_response = await service.get_current_epoch_stats()
    current_epoch_id = current_response.epoch_id
    
    if current_epoch_id > 1:
        historical_epoch_id = current_epoch_id - 1
        
        historical_response = await service.get_historical_epoch_stats(historical_epoch_id)
        
        assert historical_response.epoch_id == historical_epoch_id
        assert historical_response.height > 0
        assert len(historical_response.participants) >= 0
        assert historical_response.is_current is False
        
        is_finished = await service.cache_db.is_epoch_finished(historical_epoch_id)
        assert is_finished


@pytest.mark.asyncio
async def test_historical_epoch_immutability(service):
    current_response = await service.get_current_epoch_stats()
    current_epoch_id = current_response.epoch_id
    
    if current_epoch_id > 1:
        historical_epoch_id = current_epoch_id - 1
        
        response1 = await service.get_historical_epoch_stats(historical_epoch_id)
        height1 = response1.height
        
        response2 = await service.get_historical_epoch_stats(historical_epoch_id)
        height2 = response2.height
        
        assert height1 == height2


@pytest.mark.asyncio
async def test_height_clamping_beyond_epoch_end(service):
    current_response = await service.get_current_epoch_stats()
    current_epoch_id = current_response.epoch_id
    current_height = current_response.height
    
    if current_epoch_id > 1:
        historical_epoch_id = current_epoch_id - 1
        
        response_at_current_height = await service.get_historical_epoch_stats(
            historical_epoch_id, 
            height=current_height
        )
        
        response_without_height = await service.get_historical_epoch_stats(historical_epoch_id)
        
        assert response_at_current_height.height == response_without_height.height
        assert response_at_current_height.epoch_id == historical_epoch_id


@pytest.mark.asyncio
async def test_height_wise_caching_different_results(service):
    current_response = await service.get_current_epoch_stats()
    current_epoch_id = current_response.epoch_id
    
    if current_epoch_id > 1:
        historical_epoch_id = current_epoch_id - 1
        
        epoch_data = await service.client.get_epoch_participants(historical_epoch_id)
        effective_height = epoch_data["active_participants"]["effective_block_height"]
        
        next_epoch_data = await service.client.get_epoch_participants(historical_epoch_id + 1)
        next_effective_height = next_epoch_data["active_participants"]["effective_block_height"]
        
        early_height = effective_height + 100
        late_height = next_effective_height - 100
        
        if late_height > early_height:
            response_early = await service.get_historical_epoch_stats(historical_epoch_id, height=early_height)
            response_late = await service.get_historical_epoch_stats(historical_epoch_id, height=late_height)
            
            assert response_early.height == early_height
            assert response_late.height == late_height
            assert response_early.epoch_id == response_late.epoch_id
            
            has_early = await service.cache_db.has_stats_for_epoch(historical_epoch_id, height=early_height)
            has_late = await service.cache_db.has_stats_for_epoch(historical_epoch_id, height=late_height)
            
            assert has_early
            assert has_late

