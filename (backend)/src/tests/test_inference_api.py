import pytest
import pytest_asyncio
import tempfile
import os
from fastapi.testclient import TestClient
from backend.app import app
from backend.router import set_inference_service
from backend.client import GonkaClient
from backend.database import CacheDB
from backend.service import InferenceService


@pytest_asyncio.fixture
async def setup_service():
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
        db_path = f.name
    
    cache_db = CacheDB(db_path)
    await cache_db.initialize()
    
    client = GonkaClient(base_urls=["http://node2.gonka.ai:8000"])
    service = InferenceService(client=client, cache_db=cache_db)
    
    set_inference_service(service)
    
    yield service
    
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def client():
    return TestClient(app)


def test_hello_endpoint(client):
    response = client.get("/v1/hello")
    assert response.status_code == 200
    assert response.json() == {"message": "hello"}


@pytest.mark.asyncio
async def test_current_inference_endpoint(client, setup_service):
    response = client.get("/v1/inference/current")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "epoch_id" in data
    assert "height" in data
    assert "participants" in data
    assert "is_current" in data
    
    assert data["is_current"] is True
    assert data["epoch_id"] > 0
    assert len(data["participants"]) > 0
    
    first_participant = data["participants"][0]
    assert "index" in first_participant
    assert "address" in first_participant
    assert "weight" in first_participant
    assert "current_epoch_stats" in first_participant
    assert "missed_rate" in first_participant


@pytest.mark.asyncio
async def test_historical_epoch_endpoint(client, setup_service):
    current_response = client.get("/v1/inference/current")
    assert current_response.status_code == 200
    current_data = current_response.json()
    current_epoch_id = current_data["epoch_id"]
    
    if current_epoch_id > 1:
        historical_epoch_id = current_epoch_id - 1
        
        response = client.get(f"/v1/inference/epochs/{historical_epoch_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["epoch_id"] == historical_epoch_id
        assert data["is_current"] is False


def test_invalid_epoch_id(client):
    response = client.get("/v1/inference/epochs/0")
    assert response.status_code == 400


def test_invalid_epoch_id_negative(client):
    response = client.get("/v1/inference/epochs/-1")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_epoch_with_specific_height(client, setup_service):
    current_response = client.get("/v1/inference/current")
    assert current_response.status_code == 200
    current_data = current_response.json()
    current_epoch_id = current_data["epoch_id"]
    
    if current_epoch_id > 1:
        historical_epoch_id = current_epoch_id - 1
        current_height = current_data["height"]
        
        response = client.get(f"/v1/inference/epochs/{historical_epoch_id}?height={current_height}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["epoch_id"] == historical_epoch_id
        assert data["height"] < current_height


def test_invalid_height_parameter(client):
    response = client.get("/v1/inference/epochs/1?height=0")
    assert response.status_code == 400
    
    response = client.get("/v1/inference/epochs/1?height=-100")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_height_before_epoch_start(client, setup_service):
    current_response = client.get("/v1/inference/current")
    assert current_response.status_code == 200
    current_data = current_response.json()
    current_epoch_id = current_data["epoch_id"]
    
    if current_epoch_id > 1:
        historical_epoch_id = current_epoch_id - 1
        
        response = client.get(f"/v1/inference/epochs/{historical_epoch_id}?height=1")
        assert response.status_code == 400
        assert "before epoch" in response.json()["detail"].lower()

