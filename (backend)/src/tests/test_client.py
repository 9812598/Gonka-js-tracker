import pytest
import json
from pathlib import Path
from backend.client import GonkaClient


@pytest.fixture
def test_data_dir():
    return Path(__file__).parent.parent.parent / "test_data"


@pytest.fixture
def current_epoch_data(test_data_dir):
    with open(test_data_dir / "current_epoch_participants.json") as f:
        return json.load(f)


@pytest.fixture
def all_participants_data(test_data_dir):
    files = list(test_data_dir.glob("all_participants_height_*.json"))
    if not files:
        pytest.skip("No all_participants data file found")
    with open(files[0]) as f:
        return json.load(f)


def test_current_epoch_structure(current_epoch_data):
    assert "active_participants" in current_epoch_data
    active = current_epoch_data["active_participants"]
    
    assert "participants" in active
    assert "epoch_group_id" in active
    assert "poc_start_block_height" in active
    
    participants = active["participants"]
    assert len(participants) > 0
    
    first = participants[0]
    assert "index" in first
    assert "weight" in first
    assert "inference_url" in first


def test_all_participants_structure(all_participants_data):
    assert "participant" in all_participants_data
    participants = all_participants_data["participant"]
    assert len(participants) > 0
    
    first = participants[0]
    assert "index" in first
    assert "address" in first
    assert "current_epoch_stats" in first
    
    stats = first["current_epoch_stats"]
    assert "inference_count" in stats
    assert "missed_requests" in stats
    assert "validated_inferences" in stats
    assert "invalidated_inferences" in stats


def test_client_initialization():
    client = GonkaClient(base_urls=["http://node1.example.com", "http://node2.example.com"])
    assert len(client.base_urls) == 2
    assert client.current_url_index == 0


def test_url_rotation():
    client = GonkaClient(base_urls=["http://node1.example.com", "http://node2.example.com"])
    
    assert client._get_current_url() == "http://node1.example.com"
    
    client._rotate_url()
    assert client._get_current_url() == "http://node2.example.com"
    
    client._rotate_url()
    assert client._get_current_url() == "http://node1.example.com"


@pytest.mark.asyncio
async def test_client_live_connection():
    client = GonkaClient(base_urls=["http://node2.gonka.ai:8000"])
    
    height = await client.get_latest_height()
    assert height > 0
    assert isinstance(height, int)


@pytest.mark.asyncio
async def test_client_current_epoch():
    client = GonkaClient(base_urls=["http://node2.gonka.ai:8000"])
    
    data = await client.get_current_epoch_participants()
    assert "active_participants" in data
    assert "participants" in data["active_participants"]
    assert len(data["active_participants"]["participants"]) > 0


@pytest.mark.asyncio
async def test_client_all_participants():
    client = GonkaClient(base_urls=["http://node2.gonka.ai:8000"])
    
    height = await client.get_latest_height()
    data = await client.get_all_participants(height=height)
    
    assert "participant" in data
    assert len(data["participant"]) > 0


def test_pubkey_to_valcons():
    test_pubkey = "YrQI3q3zBpHDLEMZvgqEkNwjc/BmZ5HkEMYgQwYp+8E="
    
    valcons = GonkaClient.pubkey_to_valcons(test_pubkey)
    
    assert valcons.startswith("gonkavalcons1")
    assert len(valcons) > 20


def test_pubkey_to_valcons_custom_hrp():
    test_pubkey = "YrQI3q3zBpHDLEMZvgqEkNwjc/BmZ5HkEMYgQwYp+8E="
    
    valcons = GonkaClient.pubkey_to_valcons(test_pubkey, hrp="cosmosvalcons")
    
    assert valcons.startswith("cosmosvalcons1")


@pytest.mark.asyncio
async def test_check_node_health_no_url():
    client = GonkaClient(base_urls=["http://node2.gonka.ai:8000"])
    
    result = await client.check_node_health("")
    
    assert result["is_healthy"] is False
    assert result["error_message"] == "No inference URL"
    assert result["response_time_ms"] is None


@pytest.mark.asyncio
async def test_check_node_health_invalid_url():
    client = GonkaClient(base_urls=["http://node2.gonka.ai:8000"])
    
    result = await client.check_node_health("http://invalid.url.that.does.not.exist:99999")
    
    assert result["is_healthy"] is False
    assert result["error_message"] is not None
    assert result["response_time_ms"] is None


@pytest.fixture
def performance_summary_data(test_data_dir):
    files = list(test_data_dir.glob("epoch_performance_summary_*.json"))
    if not files:
        pytest.skip("No epoch_performance_summary data file found")
    with open(files[0]) as f:
        return json.load(f)


def test_performance_summary_structure(performance_summary_data):
    assert "epochPerformanceSummary" in performance_summary_data
    summary = performance_summary_data["epochPerformanceSummary"]
    
    assert "epoch_index" in summary
    assert "participant_id" in summary
    assert "rewarded_coins" in summary
    assert "claimed" in summary

