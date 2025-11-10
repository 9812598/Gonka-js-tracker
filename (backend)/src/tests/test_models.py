import pytest
import json
from pathlib import Path
from backend.models import (
    ParticipantStats,
    CurrentEpochStats,
    InferenceResponse,
    EpochInfo,
    RewardInfo,
    SeedInfo,
    ParticipantDetailsResponse,
    HardwareInfo,
    MLNodeInfo
)


def test_current_epoch_stats():
    stats = CurrentEpochStats(
        inference_count="10",
        missed_requests="2",
        earned_coins="100",
        rewarded_coins="95",
        burned_coins="5",
        validated_inferences="8",
        invalidated_inferences="2"
    )
    
    assert stats.inference_count == "10"
    assert stats.missed_requests == "2"


def test_participant_stats_missed_rate():
    stats = ParticipantStats(
        index="participant_1",
        address="gonka1abc...",
        weight=100,
        current_epoch_stats=CurrentEpochStats(
            inference_count="8",
            missed_requests="2",
            earned_coins="0",
            rewarded_coins="0",
            burned_coins="0",
            validated_inferences="8",
            invalidated_inferences="0"
        )
    )
    
    assert stats.missed_rate == 0.2


def test_participant_stats_zero_total():
    stats = ParticipantStats(
        index="participant_2",
        address="gonka1def...",
        weight=50,
        current_epoch_stats=CurrentEpochStats(
            inference_count="0",
            missed_requests="0",
            earned_coins="0",
            rewarded_coins="0",
            burned_coins="0",
            validated_inferences="0",
            invalidated_inferences="0"
        )
    )
    
    assert stats.missed_rate == 0.0


def test_participant_stats_high_missed_rate():
    stats = ParticipantStats(
        index="participant_3",
        address="gonka1ghi...",
        weight=200,
        current_epoch_stats=CurrentEpochStats(
            inference_count="5",
            missed_requests="95",
            earned_coins="0",
            rewarded_coins="0",
            burned_coins="0",
            validated_inferences="5",
            invalidated_inferences="0"
        )
    )
    
    assert stats.missed_rate == 0.95


def test_participant_stats_with_models():
    stats = ParticipantStats(
        index="participant_4",
        address="gonka1xyz...",
        weight=150,
        models=["Llama-3.1-8B", "Qwen2.5-7B"],
        current_epoch_stats=CurrentEpochStats(
            inference_count="10",
            missed_requests="0",
            earned_coins="0",
            rewarded_coins="0",
            burned_coins="0",
            validated_inferences="10",
            invalidated_inferences="0"
        )
    )
    
    assert stats.models == ["Llama-3.1-8B", "Qwen2.5-7B"]
    assert stats.missed_rate == 0.0


def test_participant_stats_invalidation_rate():
    stats = ParticipantStats(
        index="participant_5",
        address="gonka1inv...",
        weight=100,
        current_epoch_stats=CurrentEpochStats(
            inference_count="10",
            missed_requests="0",
            earned_coins="0",
            rewarded_coins="0",
            burned_coins="0",
            validated_inferences="8",
            invalidated_inferences="2"
        )
    )
    
    assert stats.invalidation_rate == 0.2


def test_participant_stats_high_invalidation_rate():
    stats = ParticipantStats(
        index="participant_6",
        address="gonka1bad...",
        weight=50,
        current_epoch_stats=CurrentEpochStats(
            inference_count="10",
            missed_requests="1",
            earned_coins="0",
            rewarded_coins="0",
            burned_coins="0",
            validated_inferences="5",
            invalidated_inferences="5"
        )
    )
    
    assert stats.invalidation_rate == 0.5


def test_participant_stats_zero_inferences_invalidation_rate():
    stats = ParticipantStats(
        index="participant_7",
        address="gonka1zero...",
        weight=75,
        current_epoch_stats=CurrentEpochStats(
            inference_count="0",
            missed_requests="0",
            earned_coins="0",
            rewarded_coins="0",
            burned_coins="0",
            validated_inferences="0",
            invalidated_inferences="0"
        )
    )
    
    assert stats.invalidation_rate == 0.0


def test_inference_response():
    participants = [
        ParticipantStats(
            index="participant_1",
            address="gonka1abc...",
            weight=100,
            current_epoch_stats=CurrentEpochStats(
                inference_count="10",
                missed_requests="1",
                earned_coins="0",
                rewarded_coins="0",
                burned_coins="0",
                validated_inferences="10",
                invalidated_inferences="0"
            )
        )
    ]
    
    response = InferenceResponse(
        epoch_id=1,
        height=1000,
        participants=participants,
        is_current=True
    )
    
    assert response.epoch_id == 1
    assert response.height == 1000
    assert len(response.participants) == 1
    assert response.is_current is True


def test_inference_response_serialization():
    participants = [
        ParticipantStats(
            index="participant_1",
            address="gonka1abc...",
            weight=100,
            models=["Model-A"],
            current_epoch_stats=CurrentEpochStats(
                inference_count="10",
                missed_requests="1",
                earned_coins="0",
                rewarded_coins="0",
                burned_coins="0",
                validated_inferences="9",
                invalidated_inferences="1"
            )
        )
    ]
    
    response = InferenceResponse(
        epoch_id=1,
        height=1000,
        participants=participants,
        cached_at="2025-10-19T12:00:00Z"
    )
    
    json_data = response.model_dump_json()
    assert "epoch_id" in json_data
    assert "participants" in json_data
    assert "missed_rate" in json_data
    assert "invalidation_rate" in json_data
    assert "models" in json_data


def test_model_from_real_data():
    test_data_dir = Path(__file__).parent.parent.parent / "test_data"
    files = list(test_data_dir.glob("all_participants_height_*.json"))
    
    if not files:
        pytest.skip("No test data available")
    
    with open(files[0]) as f:
        data = json.load(f)
    
    participants_data = data.get("participant", [])
    if not participants_data:
        pytest.skip("No participant data in file")
    
    first_participant = participants_data[0]
    
    participant = ParticipantStats(
        index=first_participant["index"],
        address=first_participant["address"],
        weight=first_participant["weight"],
        inference_url=first_participant.get("inference_url"),
        status=first_participant.get("status"),
        current_epoch_stats=CurrentEpochStats(**first_participant["current_epoch_stats"])
    )
    
    assert participant.index
    assert participant.address
    assert participant.missed_rate >= 0.0


def test_reward_info():
    reward = RewardInfo(
        epoch_id=56,
        assigned_reward_gnk=38,
        claimed=True
    )
    
    assert reward.epoch_id == 56
    assert reward.assigned_reward_gnk == 38
    assert reward.claimed is True


def test_seed_info():
    seed = SeedInfo(
        participant="gonka14cu38xpsd8pz5zdkkzwf0jwtpc0vv309ake364",
        epoch_index=56,
        signature="ed2e44480f2c280c39a4241bc4750480"
    )
    
    assert seed.participant == "gonka14cu38xpsd8pz5zdkkzwf0jwtpc0vv309ake364"
    assert seed.epoch_index == 56
    assert seed.signature == "ed2e44480f2c280c39a4241bc4750480"


def test_participant_details_response():
    participant = ParticipantStats(
        index="gonka1abc",
        address="gonka1abc",
        weight=100,
        current_epoch_stats=CurrentEpochStats(
            inference_count="10",
            missed_requests="1",
            earned_coins="0",
            rewarded_coins="0",
            burned_coins="0",
            validated_inferences="9",
            invalidated_inferences="1"
        )
    )
    
    rewards = [
        RewardInfo(epoch_id=56, assigned_reward_gnk=38, claimed=True),
        RewardInfo(epoch_id=55, assigned_reward_gnk=0, claimed=False)
    ]
    
    seed = SeedInfo(
        participant="gonka1abc",
        epoch_index=56,
        signature="test_signature"
    )
    
    response = ParticipantDetailsResponse(
        participant=participant,
        rewards=rewards,
        seed=seed,
        warm_keys=[],
        ml_nodes=[]
    )
    
    assert response.participant.index == "gonka1abc"
    assert len(response.rewards) == 2
    assert response.seed is not None
    assert response.seed.signature == "test_signature"
    assert response.warm_keys == []
    assert response.ml_nodes == []


def test_participant_details_response_no_seed():
    participant = ParticipantStats(
        index="gonka1abc",
        address="gonka1abc",
        weight=100,
        current_epoch_stats=CurrentEpochStats(
            inference_count="10",
            missed_requests="1",
            earned_coins="0",
            rewarded_coins="0",
            burned_coins="0",
            validated_inferences="9",
            invalidated_inferences="1"
        )
    )
    
    response = ParticipantDetailsResponse(
        participant=participant,
        rewards=[],
        seed=None,
        warm_keys=[],
        ml_nodes=[]
    )
    
    assert response.participant.index == "gonka1abc"
    assert len(response.rewards) == 0
    assert response.seed is None
    assert response.warm_keys == []
    assert response.ml_nodes == []


def test_participant_details_response_with_ml_nodes():
    participant = ParticipantStats(
        index="gonka1abc",
        address="gonka1abc",
        weight=100,
        current_epoch_stats=CurrentEpochStats(
            inference_count="10",
            missed_requests="1",
            earned_coins="0",
            rewarded_coins="0",
            burned_coins="0",
            validated_inferences="9",
            invalidated_inferences="1"
        )
    )
    
    hardware = [
        HardwareInfo(type="NVIDIA RTX 3090", count=2),
        HardwareInfo(type="NVIDIA A100", count=1)
    ]
    
    ml_nodes = [
        MLNodeInfo(
            local_id="node-1",
            status="INFERENCE",
            models=["Model-A", "Model-B"],
            hardware=hardware,
            host="192.168.1.1",
            port="8080"
        ),
        MLNodeInfo(
            local_id="node-2",
            status="POC",
            models=["Model-C"],
            hardware=[],
            host="192.168.1.2",
            port="8080"
        )
    ]
    
    response = ParticipantDetailsResponse(
        participant=participant,
        rewards=[],
        seed=None,
        warm_keys=[],
        ml_nodes=ml_nodes
    )
    
    assert response.participant.index == "gonka1abc"
    assert len(response.ml_nodes) == 2
    assert response.ml_nodes[0].local_id == "node-1"
    assert response.ml_nodes[0].status == "INFERENCE"
    assert len(response.ml_nodes[0].hardware) == 2
    assert response.ml_nodes[0].hardware[0].type == "NVIDIA RTX 3090"
    assert response.ml_nodes[0].hardware[0].count == 2
    assert response.ml_nodes[1].local_id == "node-2"
    assert len(response.ml_nodes[1].hardware) == 0

