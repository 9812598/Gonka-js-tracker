import pytest
import pytest_asyncio
import tempfile
import os
import json
from backend.database import CacheDB
from backend.models import HardwareInfo, MLNodeInfo, ParticipantDetailsResponse, ParticipantStats, CurrentEpochStats


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
async def test_save_and_get_hardware_nodes(db):
    
    hardware_nodes = [
        {
            "local_id": "node-1",
            "status": "INFERENCE",
            "models": ["model-a", "model-b"],
            "hardware": [{"type": "NVIDIA RTX 3090", "count": 2}],
            "host": "192.168.1.1",
            "port": "8080"
        },
        {
            "local_id": "node-2",
            "status": "INFERENCE",
            "models": ["model-c"],
            "hardware": [],
            "host": "192.168.1.2",
            "port": "8080"
        }
    ]
    
    await db.save_hardware_nodes_batch(
        epoch_id=50,
        participant_id="gonka1test",
        hardware_nodes=hardware_nodes
    )
    
    result = await db.get_hardware_nodes(50, "gonka1test")
    
    assert result is not None
    assert len(result) == 2
    assert result[0]["local_id"] == "node-1"
    assert result[0]["status"] == "INFERENCE"
    assert result[0]["models"] == ["model-a", "model-b"]
    assert len(result[0]["hardware"]) == 1
    assert result[0]["hardware"][0]["type"] == "NVIDIA RTX 3090"
    assert result[0]["hardware"][0]["count"] == 2
    assert result[0]["host"] == "192.168.1.1"
    assert result[0]["port"] == "8080"
    
    assert result[1]["local_id"] == "node-2"
    assert result[1]["hardware"] == []


@pytest.mark.asyncio
async def test_hardware_nodes_replacement(db):
    
    hardware_nodes_v1 = [
        {
            "local_id": "node-1",
            "status": "INFERENCE",
            "models": ["model-a"],
            "hardware": [{"type": "GPU-A", "count": 1}],
            "host": "host-1",
            "port": "8080"
        }
    ]
    
    await db.save_hardware_nodes_batch(50, "gonka1test", hardware_nodes_v1)
    
    hardware_nodes_v2 = [
        {
            "local_id": "node-2",
            "status": "POC",
            "models": ["model-b"],
            "hardware": [{"type": "GPU-B", "count": 2}],
            "host": "host-2",
            "port": "8081"
        },
        {
            "local_id": "node-3",
            "status": "INFERENCE",
            "models": ["model-c"],
            "hardware": [],
            "host": "host-3",
            "port": "8082"
        }
    ]
    
    await db.save_hardware_nodes_batch(50, "gonka1test", hardware_nodes_v2)
    
    result = await db.get_hardware_nodes(50, "gonka1test")
    
    assert result is not None
    assert len(result) == 2
    assert result[0]["local_id"] == "node-2"
    assert result[1]["local_id"] == "node-3"


@pytest.mark.asyncio
async def test_empty_hardware_nodes(db):
    
    result = await db.get_hardware_nodes(50, "gonka1nonexistent")
    
    assert result is None


@pytest.mark.asyncio
async def test_multiple_participants_hardware_nodes(db):
    
    nodes_p1 = [
        {
            "local_id": "p1-node-1",
            "status": "INFERENCE",
            "models": ["model-1"],
            "hardware": [{"type": "GPU-1", "count": 1}],
            "host": "host-p1",
            "port": "8080"
        }
    ]
    
    nodes_p2 = [
        {
            "local_id": "p2-node-1",
            "status": "POC",
            "models": ["model-2"],
            "hardware": [{"type": "GPU-2", "count": 2}],
            "host": "host-p2",
            "port": "8080"
        }
    ]
    
    await db.save_hardware_nodes_batch(50, "gonka1participant1", nodes_p1)
    await db.save_hardware_nodes_batch(50, "gonka1participant2", nodes_p2)
    
    result_p1 = await db.get_hardware_nodes(50, "gonka1participant1")
    result_p2 = await db.get_hardware_nodes(50, "gonka1participant2")
    
    assert result_p1 is not None
    assert len(result_p1) == 1
    assert result_p1[0]["local_id"] == "p1-node-1"
    
    assert result_p2 is not None
    assert len(result_p2) == 1
    assert result_p2[0]["local_id"] == "p2-node-1"


def test_hardware_info_model():
    hw = HardwareInfo(type="NVIDIA RTX 3090", count=2)
    
    assert hw.type == "NVIDIA RTX 3090"
    assert hw.count == 2


def test_mlnode_info_model():
    hw1 = HardwareInfo(type="NVIDIA RTX 3090", count=2)
    hw2 = HardwareInfo(type="NVIDIA A100", count=1)
    
    node = MLNodeInfo(
        local_id="node-1",
        status="INFERENCE",
        models=["model-a", "model-b"],
        hardware=[hw1, hw2],
        host="192.168.1.1",
        port="8080"
    )
    
    assert node.local_id == "node-1"
    assert node.status == "INFERENCE"
    assert len(node.models) == 2
    assert len(node.hardware) == 2
    assert node.hardware[0].type == "NVIDIA RTX 3090"
    assert node.hardware[0].count == 2
    assert node.host == "192.168.1.1"
    assert node.port == "8080"


def test_mlnode_info_empty_hardware():
    node = MLNodeInfo(
        local_id="node-1",
        status="INFERENCE",
        models=["model-a"],
        hardware=[],
        host="192.168.1.1",
        port="8080"
    )
    
    assert len(node.hardware) == 0


@pytest.mark.asyncio
async def test_hardware_nodes_sorting(db):
    
    hardware_nodes = [
        {
            "local_id": "node-z",
            "status": "INFERENCE",
            "models": [],
            "hardware": [],
            "host": "host-z",
            "port": "8080"
        },
        {
            "local_id": "node-a",
            "status": "INFERENCE",
            "models": [],
            "hardware": [],
            "host": "host-a",
            "port": "8080"
        },
        {
            "local_id": "node-m",
            "status": "INFERENCE",
            "models": [],
            "hardware": [],
            "host": "host-m",
            "port": "8080"
        }
    ]
    
    await db.save_hardware_nodes_batch(50, "gonka1test", hardware_nodes)
    
    result = await db.get_hardware_nodes(50, "gonka1test")
    
    assert result is not None
    assert len(result) == 3
    assert result[0]["local_id"] == "node-a"
    assert result[1]["local_id"] == "node-m"
    assert result[2]["local_id"] == "node-z"

