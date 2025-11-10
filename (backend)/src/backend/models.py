from pydantic import BaseModel, Field, computed_field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime


class CurrentEpochStats(BaseModel):
    inference_count: str
    missed_requests: str
    earned_coins: str
    rewarded_coins: str
    burned_coins: str
    validated_inferences: str
    invalidated_inferences: str


class ParticipantStats(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    index: str
    address: str
    weight: int
    validator_key: Optional[str] = None
    inference_url: Optional[str] = None
    status: Optional[str] = None
    models: List[str] = []
    current_epoch_stats: CurrentEpochStats
    is_jailed: Optional[bool] = None
    jailed_until: Optional[str] = None
    ready_to_unjail: Optional[bool] = None
    node_healthy: Optional[bool] = None
    node_health_checked_at: Optional[str] = None
    moniker: Optional[str] = None
    identity: Optional[str] = None
    keybase_username: Optional[str] = None
    keybase_picture_url: Optional[str] = None
    website: Optional[str] = None
    validator_consensus_key: Optional[str] = None
    consensus_key_mismatch: Optional[bool] = None
    seed_signature: Optional[str] = None
    ml_nodes_map: Optional[Dict[str, int]] = None
    
    @computed_field
    @property
    def missed_rate(self) -> float:
        missed = int(self.current_epoch_stats.missed_requests)
        inferences = int(self.current_epoch_stats.inference_count)
        total = missed + inferences
        
        if total == 0:
            return 0.0
        
        return round(missed / total, 4)
    
    @computed_field
    @property
    def invalidation_rate(self) -> float:
        invalidated = int(self.current_epoch_stats.invalidated_inferences)
        inferences = int(self.current_epoch_stats.inference_count)
        
        if inferences == 0:
            return 0.0
        
        return round(invalidated / inferences, 4)


class InferenceResponse(BaseModel):
    epoch_id: int
    height: int
    participants: List[ParticipantStats]
    cached_at: Optional[str] = None
    is_current: bool = False
    total_assigned_rewards_gnk: Optional[int] = None
    current_block_height: Optional[int] = None
    current_block_timestamp: Optional[str] = None
    avg_block_time: Optional[float] = None
    next_poc_start_block: Optional[int] = None
    set_new_validators_block: Optional[int] = None


class EpochParticipant(BaseModel):
    index: str
    validator_key: str
    weight: int
    inference_url: str
    models: List[str]


class EpochInfo(BaseModel):
    epoch_group_id: int
    poc_start_block_height: int
    effective_block_height: int
    created_at_block_height: int
    participants: List[EpochParticipant]


class RewardInfo(BaseModel):
    epoch_id: int
    assigned_reward_gnk: int
    claimed: bool


class SeedInfo(BaseModel):
    participant: str
    epoch_index: int
    signature: str


class WarmKeyInfo(BaseModel):
    grantee_address: str
    granted_at: str


class HardwareInfo(BaseModel):
    type: str
    count: int


class MLNodeInfo(BaseModel):
    local_id: str
    status: str
    models: List[str]
    hardware: List[HardwareInfo]
    host: str
    port: str
    poc_weight: Optional[int] = None


class ParticipantDetailsResponse(BaseModel):
    participant: ParticipantStats
    rewards: List[RewardInfo]
    seed: Optional[SeedInfo]
    warm_keys: List[WarmKeyInfo]
    ml_nodes: List[MLNodeInfo]


class LatestEpochInfo(BaseModel):
    block_height: int
    latest_epoch: dict
    phase: str


class BlockInfo(BaseModel):
    height: int
    timestamp: str


class TimelineEvent(BaseModel):
    block_height: int
    description: str
    occurred: bool


class TimelineResponse(BaseModel):
    current_block: BlockInfo
    reference_block: BlockInfo
    avg_block_time: float
    events: List[TimelineEvent]
    current_epoch_start: int
    current_epoch_index: int
    epoch_length: int
    epoch_stages: Optional[Dict[str, Any]] = None
    next_epoch_stages: Optional[Dict[str, Any]] = None


class ModelInfo(BaseModel):
    id: str
    total_weight: int
    participant_count: int
    proposed_by: str
    v_ram: str
    throughput_per_nonce: str
    units_of_compute_per_token: str
    hf_repo: str
    hf_commit: str
    model_args: List[str]
    validation_threshold: dict


class ModelStats(BaseModel):
    model: str
    ai_tokens: str
    inferences: int


class ModelsResponse(BaseModel):
    epoch_id: int
    height: int
    models: List[ModelInfo]
    stats: List[ModelStats]
    cached_at: str
    is_current: bool
    current_block_timestamp: Optional[str] = None
    avg_block_time: Optional[float] = None


class InferenceDetail(BaseModel):
    inference_id: str
    status: str
    start_block_height: str
    start_block_timestamp: str
    validated_by: List[str]
    prompt_hash: Optional[str] = None
    response_hash: Optional[str] = None
    prompt_payload: Optional[str] = None
    response_payload: Optional[str] = None
    prompt_token_count: Optional[str] = None
    completion_token_count: Optional[str] = None
    model: Optional[str] = None


class ParticipantInferencesResponse(BaseModel):
    epoch_id: int
    participant_id: str
    successful: List[InferenceDetail]
    expired: List[InferenceDetail]
    invalidated: List[InferenceDetail]
    cached_at: Optional[str] = None

