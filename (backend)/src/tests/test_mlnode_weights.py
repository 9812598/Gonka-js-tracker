import pytest
from backend.service import _extract_ml_nodes_map
from backend.models import MLNodeInfo, HardwareInfo


def test_extract_ml_nodes_map_simple():
    ml_nodes_data = [{
        "ml_nodes": [{
            "node_id": "node1",
            "poc_weight": 1000,
            "timeslot_allocation": [True, False]
        }]
    }]
    
    result = _extract_ml_nodes_map(ml_nodes_data)
    
    assert result == {"node1": 1000}


def test_extract_ml_nodes_map_multiple_nodes():
    ml_nodes_data = [{
        "ml_nodes": [
            {
                "node_id": "node1",
                "poc_weight": 1000,
                "timeslot_allocation": [True, False]
            },
            {
                "node_id": "node2",
                "poc_weight": 2000,
                "timeslot_allocation": [True, True]
            },
            {
                "node_id": "node3",
                "poc_weight": 1500,
                "timeslot_allocation": [False, True]
            }
        ]
    }]
    
    result = _extract_ml_nodes_map(ml_nodes_data)
    
    assert result == {
        "node1": 1000,
        "node2": 2000,
        "node3": 1500
    }


def test_extract_ml_nodes_map_empty():
    ml_nodes_data = []
    
    result = _extract_ml_nodes_map(ml_nodes_data)
    
    assert result == {}


def test_extract_ml_nodes_map_empty_wrapper():
    ml_nodes_data = [{"ml_nodes": []}]
    
    result = _extract_ml_nodes_map(ml_nodes_data)
    
    assert result == {}


def test_extract_ml_nodes_map_missing_node_id():
    ml_nodes_data = [{
        "ml_nodes": [{
            "poc_weight": 1000,
            "timeslot_allocation": [True, False]
        }]
    }]
    
    result = _extract_ml_nodes_map(ml_nodes_data)
    
    assert result == {}


def test_extract_ml_nodes_map_missing_poc_weight():
    ml_nodes_data = [{
        "ml_nodes": [{
            "node_id": "node1",
            "timeslot_allocation": [True, False]
        }]
    }]
    
    result = _extract_ml_nodes_map(ml_nodes_data)
    
    assert result == {}


def test_extract_ml_nodes_map_null_poc_weight():
    ml_nodes_data = [{
        "ml_nodes": [{
            "node_id": "node1",
            "poc_weight": None,
            "timeslot_allocation": [True, False]
        }]
    }]
    
    result = _extract_ml_nodes_map(ml_nodes_data)
    
    assert result == {}


def test_extract_ml_nodes_map_zero_poc_weight():
    ml_nodes_data = [{
        "ml_nodes": [{
            "node_id": "node1",
            "poc_weight": 0,
            "timeslot_allocation": [True, False]
        }]
    }]
    
    result = _extract_ml_nodes_map(ml_nodes_data)
    
    assert result == {"node1": 0}


def test_mlnode_info_with_poc_weight():
    hardware = [HardwareInfo(type="GPU", count=2)]
    
    ml_node = MLNodeInfo(
        local_id="node1",
        status="INFERENCE",
        models=["model1"],
        hardware=hardware,
        host="localhost",
        port="8080",
        poc_weight=1500
    )
    
    assert ml_node.local_id == "node1"
    assert ml_node.status == "INFERENCE"
    assert ml_node.models == ["model1"]
    assert ml_node.hardware == hardware
    assert ml_node.host == "localhost"
    assert ml_node.port == "8080"
    assert ml_node.poc_weight == 1500


def test_mlnode_info_without_poc_weight():
    hardware = [HardwareInfo(type="GPU", count=2)]
    
    ml_node = MLNodeInfo(
        local_id="node1",
        status="INFERENCE",
        models=["model1"],
        hardware=hardware,
        host="localhost",
        port="8080"
    )
    
    assert ml_node.local_id == "node1"
    assert ml_node.poc_weight is None


def test_mlnode_info_with_none_poc_weight():
    hardware = [HardwareInfo(type="GPU", count=2)]
    
    ml_node = MLNodeInfo(
        local_id="node1",
        status="INFERENCE",
        models=["model1"],
        hardware=hardware,
        host="localhost",
        port="8080",
        poc_weight=None
    )
    
    assert ml_node.local_id == "node1"
    assert ml_node.poc_weight is None


@pytest.mark.asyncio
async def test_database_save_and_get_hardware_nodes_with_poc_weight(tmp_path):
    from backend.database import CacheDB
    
    db_path = str(tmp_path / "test.db")
    cache_db = CacheDB(db_path)
    await cache_db.initialize()
    
    hardware_nodes = [{
        "local_id": "node1",
        "status": "INFERENCE",
        "models": ["model1", "model2"],
        "hardware": [{"type": "GPU", "count": 2}],
        "host": "localhost",
        "port": "8080",
        "poc_weight": 1500
    }, {
        "local_id": "node2",
        "status": "INFERENCE",
        "models": ["model3"],
        "hardware": [{"type": "GPU", "count": 1}],
        "host": "remotehost",
        "port": "8081",
        "poc_weight": 2000
    }]
    
    await cache_db.save_hardware_nodes_batch(50, "gonka1test", hardware_nodes)
    
    result = await cache_db.get_hardware_nodes(50, "gonka1test")
    
    assert result is not None
    assert len(result) == 2
    assert result[0]["local_id"] == "node1"
    assert result[0]["poc_weight"] == 1500
    assert result[1]["local_id"] == "node2"
    assert result[1]["poc_weight"] == 2000


@pytest.mark.asyncio
async def test_database_save_and_get_hardware_nodes_without_poc_weight(tmp_path):
    from backend.database import CacheDB
    
    db_path = str(tmp_path / "test.db")
    cache_db = CacheDB(db_path)
    await cache_db.initialize()
    
    hardware_nodes = [{
        "local_id": "node1",
        "status": "INFERENCE",
        "models": ["model1"],
        "hardware": [{"type": "GPU", "count": 1}],
        "host": "localhost",
        "port": "8080"
    }]
    
    await cache_db.save_hardware_nodes_batch(50, "gonka1test", hardware_nodes)
    
    result = await cache_db.get_hardware_nodes(50, "gonka1test")
    
    assert result is not None
    assert len(result) == 1
    assert result[0]["local_id"] == "node1"
    assert result[0]["poc_weight"] is None


@pytest.mark.asyncio
async def test_database_save_and_get_hardware_nodes_with_none_poc_weight(tmp_path):
    from backend.database import CacheDB
    
    db_path = str(tmp_path / "test.db")
    cache_db = CacheDB(db_path)
    await cache_db.initialize()
    
    hardware_nodes = [{
        "local_id": "node1",
        "status": "INFERENCE",
        "models": ["model1"],
        "hardware": [{"type": "GPU", "count": 1}],
        "host": "localhost",
        "port": "8080",
        "poc_weight": None
    }]
    
    await cache_db.save_hardware_nodes_batch(50, "gonka1test", hardware_nodes)
    
    result = await cache_db.get_hardware_nodes(50, "gonka1test")
    
    assert result is not None
    assert len(result) == 1
    assert result[0]["local_id"] == "node1"
    assert result[0]["poc_weight"] is None

