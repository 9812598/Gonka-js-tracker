import asyncio
import logging
import time
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from backend.client import GonkaClient
from backend.database import CacheDB
from backend.models import (
    ParticipantStats,
    CurrentEpochStats,
    InferenceResponse,
    RewardInfo,
    SeedInfo,
    ParticipantDetailsResponse,
    WarmKeyInfo,
    HardwareInfo,
    MLNodeInfo,
    BlockInfo,
    TimelineEvent,
    TimelineResponse,
    ModelInfo,
    ModelStats,
    ModelsResponse
)

logger = logging.getLogger(__name__)


def _extract_ml_nodes_map(ml_nodes_data: List[Dict]) -> Dict[str, int]:
    result = {}
    for wrapper in ml_nodes_data:
        for node in wrapper.get("ml_nodes", []):
            node_id = node.get("node_id")
            if node_id:
                poc_weight = node.get("poc_weight")
                if poc_weight is not None:
                    result[node_id] = poc_weight
    return result


class InferenceService:
    def __init__(self, client: GonkaClient, cache_db: CacheDB):
        self.client = client
        self.cache_db = cache_db
        self.current_epoch_id: Optional[int] = None
        self.current_epoch_data: Optional[InferenceResponse] = None
        self.last_fetch_time: Optional[float] = None
        self.timeline_cache: Optional[TimelineResponse] = None
        self.timeline_cache_time: Optional[float] = None
        self.timeline_cache_ttl: float = 30.0
        self.cache_warming_in_progress: bool = False
        self.last_cache_warm_time: Optional[float] = None
    
    async def _calculate_avg_block_time(self, current_height: int) -> float:
        try:
            reference_height = current_height - 10000
            
            current_block_data = await self.client.get_block(current_height)
            current_timestamp = current_block_data["result"]["block"]["header"]["time"]
            
            reference_block_data = await self.client.get_block(reference_height)
            reference_timestamp = reference_block_data["result"]["block"]["header"]["time"]
            
            current_dt = datetime.fromisoformat(current_timestamp.replace('Z', '+00:00'))
            reference_dt = datetime.fromisoformat(reference_timestamp.replace('Z', '+00:00'))
            
            time_diff_seconds = (current_dt - reference_dt).total_seconds()
            block_diff = current_height - reference_height
            avg_block_time = round(time_diff_seconds / block_diff, 2)
            
            return avg_block_time
        except Exception as e:
            logger.warning(f"Failed to calculate avg block time: {e}")
            return 6.0
    
    async def get_canonical_height(self, epoch_id: int, requested_height: Optional[int] = None) -> int:
        if self.current_epoch_id is None:
            latest_info = await self.client.get_latest_epoch()
            current_epoch_id = latest_info["latest_epoch"]["index"]
            self.current_epoch_id = current_epoch_id
        else:
            current_epoch_id = self.current_epoch_id
            latest_info = None
        
        if epoch_id == current_epoch_id:
            current_height = await self.client.get_latest_height()
            return requested_height if requested_height else current_height
        
        epoch_data = await self.client.get_epoch_participants(epoch_id)
        effective_height = epoch_data["active_participants"]["effective_block_height"]
        
        try:
            next_epoch_data = await self.client.get_epoch_participants(epoch_id + 1)
            next_effective_height = next_epoch_data["active_participants"]["effective_block_height"]
            canonical_height = next_effective_height - 10
        except Exception:
            if latest_info is None:
                latest_info = await self.client.get_latest_epoch()
            canonical_height = latest_info["epoch_stages"]["next_poc_start"] - 10
        
        if requested_height is None:
            return canonical_height
        
        if requested_height < effective_height:
            raise ValueError(
                f"Height {requested_height} is before epoch {epoch_id} start (effective height: {effective_height}). "
                f"No data exists for this epoch at this height."
            )
        
        if requested_height >= canonical_height:
            logger.info(f"Height {requested_height} is after epoch {epoch_id} end. "
                      f"Clamping to canonical height {canonical_height}")
            return canonical_height
        
        return requested_height
    
    async def _load_cached_epoch_from_db(self, epoch_id: int) -> Optional[InferenceResponse]:
        try:
            cached_stats = await self.cache_db.get_stats(epoch_id)
            if not cached_stats:
                return None
            
            logger.info(f"Loading cached epoch {epoch_id} from database: {len(cached_stats)} participants")
            
            participants_stats = []
            for stats_dict in cached_stats:
                try:
                    participant = ParticipantStats(
                        index=stats_dict["index"],
                        address=stats_dict["address"],
                        weight=stats_dict.get("weight", 0),
                        validator_key=stats_dict.get("validator_key"),
                        inference_url=stats_dict.get("inference_url"),
                        status=stats_dict.get("status"),
                        models=stats_dict.get("models", []),
                        current_epoch_stats=CurrentEpochStats(**stats_dict["current_epoch_stats"]),
                        seed_signature=stats_dict.get("_seed_signature"),
                        ml_nodes_map=stats_dict.get("_ml_nodes_map", {})
                    )
                    participants_stats.append(participant)
                except Exception as e:
                    logger.warning(f"Failed to parse cached participant {stats_dict.get('index', 'unknown')}: {e}")
            
            if not participants_stats:
                return None
            
            cached_height = cached_stats[0].get("_height", 0)
            
            return InferenceResponse(
                epoch_id=epoch_id,
                height=cached_height,
                participants=participants_stats,
                cached_at=cached_stats[0].get("_cached_at", datetime.utcnow().isoformat()),
                is_current=True
            )
        except Exception as e:
            logger.warning(f"Failed to load cached epoch from database: {e}")
            return None
    
    async def get_current_epoch_stats(self, reload: bool = False) -> InferenceResponse:
        current_time = time.time()
        cache_age = (current_time - self.last_fetch_time) if self.last_fetch_time else None
        
        if not reload and self.current_epoch_data and cache_age and cache_age < 300:
            logger.info(f"Returning cached current epoch data (age: {cache_age:.1f}s)")
            return self.current_epoch_data
        
        if not self.current_epoch_data and not reload:
            try:
                latest_info = await self.client.get_latest_epoch()
                current_epoch_id = latest_info["latest_epoch"]["index"]
                
                db_cached = await self._load_cached_epoch_from_db(current_epoch_id)
                if db_cached:
                    logger.info(f"Loaded current epoch {current_epoch_id} from database on startup")
                    self.current_epoch_data = db_cached
                    self.current_epoch_id = current_epoch_id
                    self.last_fetch_time = current_time - 31
                    return db_cached
            except Exception as e:
                logger.warning(f"Failed to load cached data from database on startup: {e}")
        
        try:
            logger.info("Fetching fresh current epoch data")
            height = await self.client.get_latest_height()
            epoch_data = await self.client.get_current_epoch_participants()
            
            epoch_id = epoch_data["active_participants"]["epoch_group_id"]
            
            await self._mark_epoch_finished_if_needed(epoch_id, height)
            
            all_participants_data = await self.client.get_all_participants(height=height)
            participants_list = all_participants_data.get("participant", [])
            
            active_indices = {
                p["index"] for p in epoch_data["active_participants"]["participants"]
            }
            
            epoch_participant_data = {
                p["index"]: {
                    "weight": p.get("weight", 0),
                    "models": p.get("models", []),
                    "validator_key": p.get("validator_key"),
                    "seed_signature": p.get("seed", {}).get("signature"),
                    "ml_nodes_map": _extract_ml_nodes_map(p.get("ml_nodes", []))
                }
                for p in epoch_data["active_participants"]["participants"]
            }
            
            active_participants = [
                p for p in participants_list if p["index"] in active_indices
            ]
            
            participants_stats = []
            stats_for_saving = []
            for p in active_participants:
                try:
                    epoch_data_for_participant = epoch_participant_data.get(p["index"], {})
                    
                    participant = ParticipantStats(
                        index=p["index"],
                        address=p["address"],
                        weight=epoch_data_for_participant.get("weight", 0),
                        validator_key=epoch_data_for_participant.get("validator_key"),
                        inference_url=p.get("inference_url"),
                        status=p.get("status"),
                        models=epoch_data_for_participant.get("models", []),
                        current_epoch_stats=CurrentEpochStats(**p["current_epoch_stats"]),
                        seed_signature=epoch_data_for_participant.get("seed_signature"),
                        ml_nodes_map=epoch_data_for_participant.get("ml_nodes_map", {})
                    )
                    participants_stats.append(participant)
                    
                    stats_dict = p.copy()
                    stats_dict["weight"] = epoch_data_for_participant.get("weight", 0)
                    stats_dict["models"] = epoch_data_for_participant.get("models", [])
                    stats_dict["validator_key"] = epoch_data_for_participant.get("validator_key")
                    stats_dict["seed_signature"] = epoch_data_for_participant.get("seed_signature")
                    stats_dict["_ml_nodes_map"] = epoch_data_for_participant.get("ml_nodes_map", {})
                    stats_for_saving.append(stats_dict)
                except Exception as e:
                    logger.warning(f"Failed to parse participant {p.get('index', 'unknown')}: {e}")
            
            active_participants_list = epoch_data["active_participants"]["participants"]
            participants_stats = await self.merge_jail_and_health_data(epoch_id, participants_stats, height, active_participants_list)
            
            latest_info = await self.client.get_latest_epoch()
            latest_epoch_index = latest_info["latest_epoch"]["index"]
            
            next_poc_start_block = None
            set_new_validators_block = None
            current_block_height = None
            current_block_timestamp = None
            avg_block_time = None
            
            if epoch_id == latest_epoch_index:
                next_poc_start_block = latest_info["epoch_stages"]["next_poc_start"]
                set_new_validators_block = latest_info["next_epoch_stages"]["set_new_validators"]
                current_block_height = latest_info["block_height"]
                
                current_block_data = await self.client.get_block(current_block_height)
                current_block_timestamp = current_block_data["result"]["block"]["header"]["time"]
                
                avg_block_time = await self._calculate_avg_block_time(current_block_height)
            elif epoch_id == latest_info.get("next_epoch_stages", {}).get("epoch_index"):
                next_poc_start_block = latest_info["next_epoch_stages"]["next_poc_start"]
                set_new_validators_block = None
                current_block_height = latest_info["block_height"]
                
                current_block_data = await self.client.get_block(current_block_height)
                current_block_timestamp = current_block_data["result"]["block"]["header"]["time"]
                
                avg_block_time = await self._calculate_avg_block_time(current_block_height)
            
            response = InferenceResponse(
                epoch_id=epoch_id,
                height=height,
                participants=participants_stats,
                cached_at=datetime.utcnow().isoformat(),
                is_current=True,
                current_block_height=current_block_height,
                current_block_timestamp=current_block_timestamp,
                avg_block_time=avg_block_time,
                next_poc_start_block=next_poc_start_block,
                set_new_validators_block=set_new_validators_block
            )
            
            await self.cache_db.save_stats_batch(
                epoch_id=epoch_id,
                height=height,
                participants_stats=stats_for_saving
            )
            
            self.current_epoch_id = epoch_id
            self.current_epoch_data = response
            self.last_fetch_time = current_time
            
            asyncio.create_task(self.warm_participant_cache(
                epoch_data["active_participants"]["participants"],
                epoch_id,
                batch_size=10
            ))
            
            logger.info(f"Fetched current epoch {epoch_id} stats at height {height}: {len(participants_stats)} participants")
            
            return response
            
        except Exception as e:
            logger.error(f"Error fetching current epoch stats: {e}")
            if self.current_epoch_data:
                logger.info("Returning cached current epoch data due to error")
                return self.current_epoch_data
            raise
    
    async def get_historical_epoch_stats(self, epoch_id: int, height: Optional[int] = None, calculate_rewards_sync: bool = False) -> InferenceResponse:
        is_finished = await self.cache_db.is_epoch_finished(epoch_id)
        
        try:
            target_height = await self.get_canonical_height(epoch_id, height)
        except Exception as e:
            logger.error(f"Failed to determine target height for epoch {epoch_id}: {e}")
            raise
        
        cached_stats = await self.cache_db.get_stats(epoch_id, height=target_height)
        if cached_stats:
            logger.info(f"Returning cached stats for epoch {epoch_id} at height {target_height}")
            
            participants_stats = []
            for stats_dict in cached_stats:
                try:
                    stats_copy = dict(stats_dict)
                    stats_copy.pop("_cached_at", None)
                    stats_copy.pop("_height", None)
                    
                    participant = ParticipantStats(**stats_copy)
                    participants_stats.append(participant)
                except Exception as e:
                    logger.warning(f"Failed to parse cached participant: {e}")
            
            epoch_data = await self.client.get_epoch_participants(epoch_id)
            active_participants_list = epoch_data["active_participants"]["participants"]
            participants_stats = await self.merge_jail_and_health_data(epoch_id, participants_stats, target_height, active_participants_list)
            
            total_rewards_gnk = await self.cache_db.get_epoch_total_rewards(epoch_id)
            if total_rewards_gnk is None or total_rewards_gnk == 0:
                if total_rewards_gnk == 0:
                    logger.warning(f"Detected invalid cached total rewards (0 GNK) for epoch {epoch_id}, deleting and recalculating")
                    await self.cache_db.delete_epoch_total_rewards(epoch_id)
                
                if calculate_rewards_sync:
                    logger.info(f"Calculating total rewards synchronously for epoch {epoch_id}")
                    await self._calculate_and_cache_total_rewards(epoch_id)
                    total_rewards_gnk = await self.cache_db.get_epoch_total_rewards(epoch_id)
                else:
                    asyncio.create_task(self._calculate_and_cache_total_rewards(epoch_id))
            
            return InferenceResponse(
                epoch_id=epoch_id,
                height=target_height,
                participants=participants_stats,
                cached_at=cached_stats[0].get("_cached_at"),
                is_current=False,
                total_assigned_rewards_gnk=total_rewards_gnk
            )
        
        try:
            logger.info(f"Fetching historical epoch {epoch_id} at height {target_height}")
            
            all_participants_data = await self.client.get_all_participants(height=target_height)
            participants_list = all_participants_data.get("participant", [])
            
            epoch_data = await self.client.get_epoch_participants(epoch_id)
            active_indices = {
                p["index"] for p in epoch_data["active_participants"]["participants"]
            }
            
            epoch_participant_data = {
                p["index"]: {
                    "weight": p.get("weight", 0),
                    "models": p.get("models", []),
                    "validator_key": p.get("validator_key"),
                    "seed_signature": p.get("seed", {}).get("signature"),
                    "ml_nodes_map": _extract_ml_nodes_map(p.get("ml_nodes", []))
                }
                for p in epoch_data["active_participants"]["participants"]
            }
            
            active_participants = [
                p for p in participants_list if p["index"] in active_indices
            ]
            
            participants_stats = []
            stats_for_saving = []
            for p in active_participants:
                try:
                    epoch_data_for_participant = epoch_participant_data.get(p["index"], {})
                    
                    participant = ParticipantStats(
                        index=p["index"],
                        address=p["address"],
                        weight=epoch_data_for_participant.get("weight", 0),
                        validator_key=epoch_data_for_participant.get("validator_key"),
                        inference_url=p.get("inference_url"),
                        status=p.get("status"),
                        models=epoch_data_for_participant.get("models", []),
                        current_epoch_stats=CurrentEpochStats(**p["current_epoch_stats"]),
                        seed_signature=epoch_data_for_participant.get("seed_signature"),
                        ml_nodes_map=epoch_data_for_participant.get("ml_nodes_map", {})
                    )
                    participants_stats.append(participant)
                    
                    stats_dict = p.copy()
                    stats_dict["weight"] = epoch_data_for_participant.get("weight", 0)
                    stats_dict["models"] = epoch_data_for_participant.get("models", [])
                    stats_dict["validator_key"] = epoch_data_for_participant.get("validator_key")
                    stats_dict["seed_signature"] = epoch_data_for_participant.get("seed_signature")
                    stats_dict["_ml_nodes_map"] = epoch_data_for_participant.get("ml_nodes_map", {})
                    stats_for_saving.append(stats_dict)
                except Exception as e:
                    logger.warning(f"Failed to parse participant {p.get('index', 'unknown')}: {e}")
            
            await self.cache_db.save_stats_batch(
                epoch_id=epoch_id,
                height=target_height,
                participants_stats=stats_for_saving
            )
            
            if height is None and not is_finished:
                await self.cache_db.mark_epoch_finished(epoch_id, target_height)
            
            participants_stats = await self.merge_jail_and_health_data(epoch_id, participants_stats, target_height, epoch_data["active_participants"]["participants"])
            
            total_rewards_gnk = await self.cache_db.get_epoch_total_rewards(epoch_id)
            if total_rewards_gnk is None:
                asyncio.create_task(self._calculate_and_cache_total_rewards(epoch_id))
            
            response = InferenceResponse(
                epoch_id=epoch_id,
                height=target_height,
                participants=participants_stats,
                cached_at=datetime.utcnow().isoformat(),
                is_current=False,
                total_assigned_rewards_gnk=total_rewards_gnk
            )
            
            logger.info(f"Fetched and cached historical epoch {epoch_id} at height {target_height}: {len(participants_stats)} participants")
            
            return response
            
        except Exception as e:
            logger.error(f"Error fetching historical epoch {epoch_id}: {e}")
            raise
    
    async def _mark_epoch_finished_if_needed(self, current_epoch_id: int, current_height: int):
        if self.current_epoch_id is None:
            return
        
        if current_epoch_id > self.current_epoch_id:
            old_epoch_id = self.current_epoch_id
            is_already_finished = await self.cache_db.is_epoch_finished(old_epoch_id)
            
            if not is_already_finished:
                logger.info(f"Epoch transition detected: {old_epoch_id} -> {current_epoch_id}")
                
                try:
                    await self.get_historical_epoch_stats(old_epoch_id, calculate_rewards_sync=True)
                    logger.info(f"Marked epoch {old_epoch_id} as finished and cached final stats with total rewards")
                except Exception as e:
                    logger.error(f"Failed to mark epoch {old_epoch_id} as finished: {e}")
    
    async def fetch_and_cache_jail_statuses(self, epoch_id: int, height: int, active_participants: List[Dict[str, Any]]):
        try:
            validators = await self.client.get_all_validators(height=height)
            validators_with_tokens = [v for v in validators if v.get("tokens") and int(v.get("tokens")) > 0]
            
            active_indices = {p["index"] for p in active_participants}
            participant_map = {p["index"]: p for p in active_participants}
            
            validator_by_operator = {}
            for v in validators_with_tokens:
                operator_address = v.get("operator_address", "")
                if operator_address:
                    validator_by_operator[operator_address] = v
            
            jail_statuses = []
            now_utc = datetime.now(timezone.utc)
            
            for participant_index in active_indices:
                participant = participant_map.get(participant_index)
                if not participant:
                    continue
                
                valoper_address = self.client.convert_bech32_address(participant_index, "gonkavaloper")
                if not valoper_address:
                    continue
                
                validator = validator_by_operator.get(valoper_address)
                if not validator:
                    continue
                
                consensus_pub = (
                    (validator.get("consensus_pubkey") or {}).get("key")
                    or (validator.get("consensus_pubkey") or {}).get("value")
                    or ""
                )
                
                participant_validator_key = participant.get("validator_key", "")
                
                consensus_key_mismatch = False
                if consensus_pub and participant_validator_key:
                    consensus_key_mismatch = consensus_pub != participant_validator_key
                
                is_jailed = bool(validator.get("jailed"))
                valcons_addr = self.client.pubkey_to_valcons(consensus_pub) if consensus_pub else None
                
                jailed_until = None
                ready_to_unjail = False
                
                if is_jailed and valcons_addr:
                    signing_info = await self.client.get_signing_info(valcons_addr, height=height)
                    if signing_info:
                        jailed_until_str = signing_info.get("jailed_until")
                        if jailed_until_str and "1970-01-01" not in jailed_until_str:
                            jailed_until = jailed_until_str
                            try:
                                jailed_until_dt = datetime.fromisoformat(jailed_until_str.replace("Z", "")).replace(tzinfo=timezone.utc)
                                ready_to_unjail = now_utc > jailed_until_dt
                            except Exception:
                                pass
                
                description = validator.get("description", {})
                moniker = description.get("moniker", "").strip()
                identity = description.get("identity", "").strip()
                website = description.get("website", "").strip()
                
                if moniker and moniker.startswith("gonkavaloper"):
                    moniker = ""
                
                keybase_username = None
                keybase_picture_url = None
                if identity:
                    keybase_username, keybase_picture_url = await self.client.get_keybase_info(identity)
                
                jail_statuses.append({
                    "participant_index": participant_index,
                    "is_jailed": is_jailed,
                    "jailed_until": jailed_until,
                    "ready_to_unjail": ready_to_unjail,
                    "valcons_address": valcons_addr,
                    "moniker": moniker if moniker else None,
                    "identity": identity if identity else None,
                    "keybase_username": keybase_username,
                    "keybase_picture_url": keybase_picture_url,
                    "website": website if website else None,
                    "validator_consensus_key": consensus_pub if consensus_pub else None,
                    "consensus_key_mismatch": consensus_key_mismatch if consensus_pub and participant_validator_key else None
                })
            
            await self.cache_db.save_jail_status_batch(epoch_id, jail_statuses)
            logger.info(f"Cached jail statuses for {len(jail_statuses)} participants in epoch {epoch_id}")
            
        except Exception as e:
            logger.error(f"Failed to fetch and cache jail statuses: {e}")
    
    async def fetch_and_cache_node_health(self, active_participants: List[Dict[str, Any]]):
        try:
            health_statuses = []
            
            for participant in active_participants:
                participant_index = participant.get("index")
                inference_url = participant.get("inference_url")
                
                if not participant_index:
                    continue
                
                health_result = await self.client.check_node_health(inference_url)
                
                health_statuses.append({
                    "participant_index": participant_index,
                    "is_healthy": health_result["is_healthy"],
                    "error_message": health_result["error_message"],
                    "response_time_ms": health_result["response_time_ms"]
                })
            
            await self.cache_db.save_node_health_batch(health_statuses)
            logger.info(f"Cached health statuses for {len(health_statuses)} participants")
            
        except Exception as e:
            logger.error(f"Failed to fetch and cache node health: {e}")
    
    async def merge_jail_and_health_data(self, epoch_id: int, participants: List[ParticipantStats], height: int, active_participants: List[Dict[str, Any]]) -> List[ParticipantStats]:
        try:
            jail_statuses_list = await self.cache_db.get_jail_status(epoch_id)
            jail_map = {}
            if jail_statuses_list:
                jail_map = {j["participant_index"]: j for j in jail_statuses_list}
            else:
                logger.info(f"No cached jail statuses for epoch {epoch_id}, fetching inline")
                await self.fetch_and_cache_jail_statuses(epoch_id, height, active_participants)
                jail_statuses_list = await self.cache_db.get_jail_status(epoch_id)
                if jail_statuses_list:
                    jail_map = {j["participant_index"]: j for j in jail_statuses_list}
            
            health_statuses_list = await self.cache_db.get_node_health()
            health_map = {}
            if health_statuses_list:
                health_map = {h["participant_index"]: h for h in health_statuses_list}
            else:
                logger.info("No cached health statuses, fetching inline")
                await self.fetch_and_cache_node_health(active_participants)
                health_statuses_list = await self.cache_db.get_node_health()
                if health_statuses_list:
                    health_map = {h["participant_index"]: h for h in health_statuses_list}
            
            for participant in participants:
                jail_info = jail_map.get(participant.index)
                if jail_info:
                    participant.is_jailed = jail_info["is_jailed"]
                    participant.jailed_until = jail_info["jailed_until"]
                    participant.ready_to_unjail = jail_info["ready_to_unjail"]
                    participant.moniker = jail_info.get("moniker")
                    participant.identity = jail_info.get("identity")
                    participant.keybase_username = jail_info.get("keybase_username")
                    participant.keybase_picture_url = jail_info.get("keybase_picture_url")
                    participant.website = jail_info.get("website")
                    participant.validator_consensus_key = jail_info.get("validator_consensus_key")
                    participant.consensus_key_mismatch = jail_info.get("consensus_key_mismatch")
                
                health_info = health_map.get(participant.index)
                if health_info:
                    participant.node_healthy = health_info["is_healthy"]
                    participant.node_health_checked_at = health_info["last_check"]
            
            return participants
            
        except Exception as e:
            logger.error(f"Failed to merge jail and health data: {e}")
            return participants
    
    async def get_participant_details(
        self,
        participant_id: str,
        epoch_id: int,
        height: Optional[int] = None
    ) -> Optional[ParticipantDetailsResponse]:
        try:
            if self.current_epoch_id is None:
                latest_info = await self.client.get_latest_epoch()
                current_epoch_id = latest_info["latest_epoch"]["index"]
                self.current_epoch_id = current_epoch_id
            else:
                current_epoch_id = self.current_epoch_id
            
            is_current = (epoch_id == current_epoch_id)
            
            participant = None
            if is_current and self.current_epoch_data:
                for p in self.current_epoch_data.participants:
                    if p.index == participant_id:
                        participant = p
                        break
            
            if not participant:
                if is_current:
                    stats = await self.get_current_epoch_stats()
                else:
                    stats = await self.get_historical_epoch_stats(epoch_id, height)
                
                for p in stats.participants:
                    if p.index == participant_id:
                        participant = p
                        break
            
            if not participant:
                return None
            
            if epoch_id == current_epoch_id:
                epoch_ids = [current_epoch_id - i for i in range(1, 6) if current_epoch_id - i > 0]
            elif epoch_id < current_epoch_id:
                epoch_ids = [epoch_id - i for i in range(5, -1, -1) if epoch_id - i > 0]
            else:
                epoch_ids = []
            
            rewards_data = await self.cache_db.get_rewards_for_participant(participant_id, epoch_ids) if epoch_ids else []
            cached_epoch_ids = {r["epoch_id"] for r in rewards_data}
            missing_epoch_ids = [eid for eid in epoch_ids if eid not in cached_epoch_ids]
            
            warm_keys_data = await self.cache_db.get_warm_keys(epoch_id, participant_id)
            hardware_nodes_data = await self.cache_db.get_hardware_nodes(epoch_id, participant_id)
            
            fetch_tasks = []
            
            if missing_epoch_ids:
                logger.info(f"Fetching missing rewards inline for epochs {missing_epoch_ids}")
                for missing_epoch in missing_epoch_ids:
                    fetch_tasks.append(('reward', missing_epoch, 
                        self.client.get_epoch_performance_summary(missing_epoch, participant_id)))
            
            if warm_keys_data is None:
                logger.info(f"Fetching warm keys inline for participant {participant_id}")
                fetch_tasks.append(('warm_keys', None, self.client.get_authz_grants(participant_id)))
            
            if hardware_nodes_data is None:
                logger.info(f"Fetching hardware nodes inline for participant {participant_id}")
                fetch_tasks.append(('hardware', None, self.client.get_hardware_nodes(participant_id)))
            
            if fetch_tasks:
                results = await asyncio.gather(*[task[2] for task in fetch_tasks], return_exceptions=True)
                
                newly_fetched_rewards = []
                for i, (task_type, task_epoch_id, _) in enumerate(fetch_tasks):
                    result = results[i]
                    
                    if isinstance(result, Exception):
                        logger.debug(f"Fetch failed for {task_type}: {result}")
                        continue
                    
                    if task_type == 'reward':
                        perf = result.get("epochPerformanceSummary", {})
                        newly_fetched_rewards.append({
                            "epoch_id": task_epoch_id,
                            "participant_id": participant_id,
                            "rewarded_coins": perf.get("rewarded_coins", "0"),
                            "claimed": perf.get("claimed", False)
                        })
                    elif task_type == 'warm_keys':
                        warm_keys_data = result if result else []
                        await self.cache_db.save_warm_keys_batch(epoch_id, participant_id, warm_keys_data)
                    elif task_type == 'hardware':
                        hardware_nodes_data = result if result else []
                        await self.cache_db.save_hardware_nodes_batch(epoch_id, participant_id, hardware_nodes_data)
                
                if newly_fetched_rewards:
                    await self.cache_db.save_reward_batch(newly_fetched_rewards)
                    logger.info(f"Cached {len(newly_fetched_rewards)} inline-fetched rewards")
                    rewards_data.extend(newly_fetched_rewards)
            
            if warm_keys_data is None:
                warm_keys_data = []
            if hardware_nodes_data is None:
                hardware_nodes_data = []
            
            rewards = []
            for reward_data in rewards_data:
                rewarded_coins = reward_data.get("rewarded_coins", "0")
                gnk = int(rewarded_coins) // 1_000_000_000 if rewarded_coins != "0" else 0
                
                rewards.append(RewardInfo(
                    epoch_id=reward_data["epoch_id"],
                    assigned_reward_gnk=gnk,
                    claimed=reward_data["claimed"]
                ))
            
            rewards.sort(key=lambda r: r.epoch_id, reverse=True)
            
            seed = None
            if participant.seed_signature:
                seed = SeedInfo(
                    participant=participant_id,
                    epoch_index=epoch_id,
                    signature=participant.seed_signature
                )
            else:
                cached_stats = await self.cache_db.get_stats(epoch_id, height)
                if cached_stats:
                    for s in cached_stats:
                        if s.get("index") == participant_id:
                            seed_sig = s.get("_seed_signature")
                            if seed_sig:
                                seed = SeedInfo(
                                    participant=participant_id,
                                    epoch_index=epoch_id,
                                    signature=seed_sig
                                )
                            break
            
            warm_keys = [
                WarmKeyInfo(
                    grantee_address=wk["grantee_address"],
                    granted_at=wk["granted_at"]
                )
                for wk in warm_keys_data
            ]
            
            ml_nodes_map = participant.ml_nodes_map if participant.ml_nodes_map else {}
            if not ml_nodes_map:
                cached_stats = await self.cache_db.get_stats(epoch_id, height)
                if cached_stats:
                    for s in cached_stats:
                        if s.get("index") == participant_id:
                            ml_nodes_map = s.get("_ml_nodes_map", {})
                            break
            
            ml_nodes = []
            for node in (hardware_nodes_data or []):
                local_id = node.get("local_id", "")
                poc_weight = ml_nodes_map.get(local_id) or node.get("poc_weight")
                
                hardware_list = [
                    HardwareInfo(type=hw["type"], count=hw["count"])
                    for hw in node.get("hardware", [])
                ]
                ml_nodes.append(MLNodeInfo(
                    local_id=local_id,
                    status=node.get("status", ""),
                    models=node.get("models", []),
                    hardware=hardware_list,
                    host=node.get("host", ""),
                    port=node.get("port", ""),
                    poc_weight=poc_weight
                ))
            
            return ParticipantDetailsResponse(
                participant=participant,
                rewards=rewards,
                seed=seed,
                warm_keys=warm_keys,
                ml_nodes=ml_nodes
            )
            
        except Exception as e:
            logger.error(f"Failed to get participant details: {e}")
            return None
    
    async def poll_participant_rewards(self):
        try:
            logger.info("Polling participant rewards")
            
            height = await self.client.get_latest_height()
            epoch_data = await self.client.get_current_epoch_participants()
            current_epoch = epoch_data["active_participants"]["epoch_group_id"]
            participants = epoch_data["active_participants"]["participants"]
            
            rewards_to_save = []
            
            for participant in participants:
                participant_id = participant["index"]
                
                for epoch_offset in range(1, 7):
                    check_epoch = current_epoch - epoch_offset
                    if check_epoch <= 0:
                        continue
                    
                    cached_reward = await self.cache_db.get_reward(check_epoch, participant_id)
                    if cached_reward and cached_reward["claimed"]:
                        continue
                    
                    try:
                        summary = await self.client.get_epoch_performance_summary(
                            check_epoch,
                            participant_id,
                            height=height
                        )
                        
                        perf = summary.get("epochPerformanceSummary", {})
                        rewarded_coins = perf.get("rewarded_coins", "0")
                        claimed = perf.get("claimed", False)
                        
                        rewards_to_save.append({
                            "epoch_id": check_epoch,
                            "participant_id": participant_id,
                            "rewarded_coins": rewarded_coins,
                            "claimed": claimed
                        })
                        
                    except Exception as e:
                        logger.debug(f"Failed to fetch reward for {participant_id} epoch {check_epoch}: {e}")
                        continue
            
            if rewards_to_save:
                await self.cache_db.save_reward_batch(rewards_to_save)
                logger.info(f"Saved {len(rewards_to_save)} reward records")
            
        except Exception as e:
            logger.error(f"Error polling participant rewards: {e}")
    
    async def poll_warm_keys(self, batch_size: int = 10, check_cache: bool = True):
        try:
            logger.info("Polling warm keys")
            
            epoch_data = await self.client.get_current_epoch_participants()
            current_epoch = epoch_data["active_participants"]["epoch_group_id"]
            participants = epoch_data["active_participants"]["participants"]
            
            async def fetch_warm_key(participant):
                participant_id = participant["index"]
                try:
                    if check_cache:
                        cached = await self.cache_db.get_warm_keys(current_epoch, participant_id)
                        if cached is not None:
                            return None
                    
                    warm_keys = await self.client.get_authz_grants(participant_id)
                    await self.cache_db.save_warm_keys_batch(current_epoch, participant_id, warm_keys)
                    logger.debug(f"Updated {len(warm_keys)} warm keys for {participant_id}")
                    return True
                except Exception as e:
                    logger.debug(f"Failed to fetch warm keys for {participant_id}: {e}")
                    return False
            
            fetched_count = 0
            for i in range(0, len(participants), batch_size):
                batch = participants[i:i+batch_size]
                results = await asyncio.gather(*[fetch_warm_key(p) for p in batch], return_exceptions=True)
                success_count = sum(1 for r in results if r is True)
                fetched_count += success_count
                logger.debug(f"Warm keys batch {i//batch_size + 1}: {success_count}/{len(batch)} fetched")
            
            logger.info(f"Completed warm keys polling: {fetched_count} fetched, {len(participants) - fetched_count} cached")
            
        except Exception as e:
            logger.error(f"Error polling warm keys: {e}")
    
    async def poll_hardware_nodes(self, batch_size: int = 10, check_cache: bool = True):
        try:
            logger.info("Polling hardware nodes")
            
            epoch_data = await self.client.get_current_epoch_participants()
            current_epoch = epoch_data["active_participants"]["epoch_group_id"]
            participants = epoch_data["active_participants"]["participants"]
            
            async def fetch_hardware_node(participant):
                participant_id = participant["index"]
                try:
                    if check_cache:
                        cached = await self.cache_db.get_hardware_nodes(current_epoch, participant_id)
                        if cached is not None:
                            return None
                    
                    hardware_nodes = await self.client.get_hardware_nodes(participant_id)
                    await self.cache_db.save_hardware_nodes_batch(current_epoch, participant_id, hardware_nodes)
                    logger.debug(f"Updated {len(hardware_nodes)} hardware nodes for {participant_id}")
                    return True
                except Exception as e:
                    logger.debug(f"Failed to fetch hardware nodes for {participant_id}: {e}")
                    return False
            
            fetched_count = 0
            for i in range(0, len(participants), batch_size):
                batch = participants[i:i+batch_size]
                results = await asyncio.gather(*[fetch_hardware_node(p) for p in batch], return_exceptions=True)
                success_count = sum(1 for r in results if r is True)
                fetched_count += success_count
                logger.debug(f"Hardware nodes batch {i//batch_size + 1}: {success_count}/{len(batch)} fetched")
            
            logger.info(f"Completed hardware nodes polling: {fetched_count} fetched, {len(participants) - fetched_count} cached")
            
        except Exception as e:
            logger.error(f"Error polling hardware nodes: {e}")
    
    async def warm_participant_cache(self, participants: List[Dict[str, Any]], current_epoch: int, batch_size: int = 10):
        current_time = time.time()
        
        if self.cache_warming_in_progress:
            logger.debug("Cache warming already in progress, skipping")
            return
        
        if self.last_cache_warm_time and (current_time - self.last_cache_warm_time) < 60:
            logger.debug("Cache warming ran recently, skipping")
            return
        
        self.cache_warming_in_progress = True
        self.last_cache_warm_time = current_time
        
        try:
            logger.info(f"Starting cache warming for {len(participants)} participants")
            
            total_warm_keys = 0
            total_hardware = 0
            
            async def warm_warm_keys(participant):
                participant_id = participant["index"]
                try:
                    cached = await self.cache_db.get_warm_keys(current_epoch, participant_id)
                    if cached is None:
                        warm_keys = await self.client.get_authz_grants(participant_id)
                        await self.cache_db.save_warm_keys_batch(current_epoch, participant_id, warm_keys)
                        return True
                except Exception as e:
                    logger.debug(f"Failed to warm warm_keys for {participant_id}: {e}")
                return False
            
            for i in range(0, len(participants), batch_size):
                batch = participants[i:i+batch_size]
                results = await asyncio.gather(*[warm_warm_keys(p) for p in batch], return_exceptions=True)
                total_warm_keys += sum(1 for r in results if r is True)
            
            async def warm_hardware(participant):
                participant_id = participant["index"]
                try:
                    cached = await self.cache_db.get_hardware_nodes(current_epoch, participant_id)
                    if cached is None:
                        hardware_nodes = await self.client.get_hardware_nodes(participant_id)
                        await self.cache_db.save_hardware_nodes_batch(current_epoch, participant_id, hardware_nodes)
                        return True
                except Exception as e:
                    logger.debug(f"Failed to warm hardware_nodes for {participant_id}: {e}")
                return False
            
            for i in range(0, len(participants), batch_size):
                batch = participants[i:i+batch_size]
                results = await asyncio.gather(*[warm_hardware(p) for p in batch], return_exceptions=True)
                total_hardware += sum(1 for r in results if r is True)
            
            logger.info(f"Cache warming completed: {total_warm_keys} warm_keys, {total_hardware} hardware_nodes fetched")
            
        except Exception as e:
            logger.error(f"Error during cache warming: {e}")
        finally:
            self.cache_warming_in_progress = False
    
    async def _calculate_and_cache_total_rewards(self, epoch_id: int):
        try:
            logger.info(f"Calculating total assigned rewards for epoch {epoch_id}")
            
            epoch_data = await self.client.get_epoch_participants(epoch_id)
            participants = epoch_data["active_participants"]["participants"]
            
            total_ugnk = 0
            fetched_count = 0
            rewards_batch = []
            participants_with_rewards = 0
            
            for participant in participants:
                participant_id = participant["index"]
                
                try:
                    summary = await self.client.get_epoch_performance_summary(
                        epoch_id,
                        participant_id
                    )
                    perf = summary.get("epochPerformanceSummary", {})
                    rewarded_coins = perf.get("rewarded_coins", "0")
                    rewarded_amount = int(rewarded_coins)
                    total_ugnk += rewarded_amount
                    fetched_count += 1
                    
                    if rewarded_amount > 0:
                        participants_with_rewards += 1
                    
                    rewards_batch.append({
                        "epoch_id": epoch_id,
                        "participant_id": participant_id,
                        "rewarded_coins": rewarded_coins,
                        "claimed": perf.get("claimed", False)
                    })
                except Exception as e:
                    logger.debug(f"Could not fetch reward for {participant_id} in epoch {epoch_id}: {e}")
                    continue
            
            if total_ugnk == 0 and fetched_count > 0:
                logger.warning(f"Epoch {epoch_id} rewards calculation returned 0 for all {fetched_count} participants - rewards may not be available yet, skipping cache")
                return
            
            if rewards_batch:
                await self.cache_db.save_reward_batch(rewards_batch)
                logger.debug(f"Cached {len(rewards_batch)} participant rewards during total calculation")
            
            total_gnk = total_ugnk // 1_000_000_000
            
            await self.cache_db.save_epoch_total_rewards(epoch_id, total_gnk)
            logger.info(f"Calculated and cached total rewards for epoch {epoch_id}: {total_gnk} GNK from {fetched_count}/{len(participants)} participants ({participants_with_rewards} with rewards)")
            
        except Exception as e:
            logger.error(f"Error calculating epoch total rewards for epoch {epoch_id}: {e}")
    
    async def poll_epoch_total_rewards(self):
        try:
            logger.info("Polling epoch total rewards")
            
            latest_info = await self.client.get_latest_epoch()
            current_epoch_id = latest_info["latest_epoch"]["index"]
            
            for offset in range(1, 6):
                epoch_id = current_epoch_id - offset
                if epoch_id <= 0:
                    continue
                
                cached_total = await self.cache_db.get_epoch_total_rewards(epoch_id)
                if cached_total is not None and cached_total > 0:
                    logger.debug(f"Epoch {epoch_id} total rewards already cached: {cached_total} GNK")
                    continue
                
                if cached_total == 0:
                    logger.warning(f"Detected invalid cached total rewards (0 GNK) for epoch {epoch_id}, recalculating")
                    await self.cache_db.delete_epoch_total_rewards(epoch_id)
                
                logger.info(f"Calculating total rewards for epoch {epoch_id}")
                await self._calculate_and_cache_total_rewards(epoch_id)
            
            logger.info("Completed epoch total rewards polling")
            
        except Exception as e:
            logger.error(f"Error polling epoch total rewards: {e}")
    
    async def get_timeline(self):
        current_time = time.time()
        
        if (self.timeline_cache is not None and 
            self.timeline_cache_time is not None and
            current_time - self.timeline_cache_time < self.timeline_cache_ttl):
            logger.info(f"Returning cached timeline data (age: {current_time - self.timeline_cache_time:.1f}s)")
            return self.timeline_cache
        
        if self.timeline_cache is None:
            cached_data = await self.cache_db.get_timeline_cache()
            if cached_data:
                logger.info("Loading timeline from database cache on startup")
                timeline_dict = cached_data["timeline"]
                try:
                    response = TimelineResponse(
                        current_block=BlockInfo(**timeline_dict["current_block"]),
                        reference_block=BlockInfo(**timeline_dict["reference_block"]),
                        avg_block_time=timeline_dict["avg_block_time"],
                        events=[TimelineEvent(**e) for e in timeline_dict["events"]],
                        current_epoch_start=timeline_dict["current_epoch_start"],
                        current_epoch_index=timeline_dict["current_epoch_index"],
                        epoch_length=timeline_dict["epoch_length"],
                        epoch_stages=timeline_dict.get("epoch_stages"),
                        next_epoch_stages=timeline_dict.get("next_epoch_stages")
                    )
                    self.timeline_cache = response
                    self.timeline_cache_time = current_time - 29
                    return response
                except Exception as e:
                    logger.warning(f"Failed to parse cached timeline data: {e}")
        
        logger.info("Fetching fresh timeline data")
        current_height = await self.client.get_latest_height()
        current_block_data = await self.client.get_block(current_height)
        current_timestamp = current_block_data["result"]["block"]["header"]["time"]
        
        reference_height = current_height - 10000
        reference_block_data = await self.client.get_block(reference_height)
        reference_timestamp = reference_block_data["result"]["block"]["header"]["time"]
        
        current_dt = datetime.fromisoformat(current_timestamp.replace('Z', '+00:00'))
        reference_dt = datetime.fromisoformat(reference_timestamp.replace('Z', '+00:00'))
        
        time_diff_seconds = (current_dt - reference_dt).total_seconds()
        block_diff = current_height - reference_height
        avg_block_time = round(time_diff_seconds / block_diff, 2)
        
        restrictions_data = await self.client.get_restrictions_params()
        restrictions_end_block = int(restrictions_data["params"]["restriction_end_block"])
        
        latest_epoch_info = await self.client.get_latest_epoch()
        current_epoch_start = latest_epoch_info["latest_epoch"]["poc_start_block_height"]
        current_epoch_index = latest_epoch_info["latest_epoch"]["index"]
        epoch_length = latest_epoch_info["epoch_params"]["epoch_length"]
        epoch_stages = latest_epoch_info.get("epoch_stages")
        next_epoch_stages = latest_epoch_info.get("next_epoch_stages")
        
        events = [
            TimelineEvent(
                block_height=restrictions_end_block,
                description="Money Transfer Enabled",
                occurred=current_height >= restrictions_end_block
            )
        ]
        
        response = TimelineResponse(
            current_block=BlockInfo(height=current_height, timestamp=current_timestamp),
            reference_block=BlockInfo(height=reference_height, timestamp=reference_timestamp),
            avg_block_time=avg_block_time,
            events=events,
            current_epoch_start=current_epoch_start,
            current_epoch_index=current_epoch_index,
            epoch_length=epoch_length,
            epoch_stages=epoch_stages,
            next_epoch_stages=next_epoch_stages
        )
        
        self.timeline_cache = response
        self.timeline_cache_time = current_time
        
        try:
            await self.cache_db.save_timeline_cache(response.dict())
        except Exception as e:
            logger.warning(f"Failed to save timeline to database: {e}")
        
        logger.info(f"Cached fresh timeline data")
        
        return response
    
    async def get_current_models(self) -> ModelsResponse:
        if self.current_epoch_id is None:
            try:
                latest_info = await self.client.get_latest_epoch()
                epoch_id = latest_info["latest_epoch"]["index"]
                self.current_epoch_id = epoch_id
            except Exception as e:
                logger.error(f"Failed to get current epoch ID: {e}")
                raise
        else:
            epoch_id = self.current_epoch_id
        
        cached_models = await self.cache_db.get_models(epoch_id)
        cached_api_data = await self.cache_db.get_models_api_cache(epoch_id)
        
        if cached_models and cached_api_data:
            logger.info(f"Returning fully cached models for epoch {epoch_id} from database")
            
            models_all_data = cached_api_data["models_all"]
            models_stats_data = cached_api_data["models_stats"]
            cached_height = cached_api_data.get("cached_height", 0)
            
            stats_list = models_stats_data.get("stats_models", [])
            models_list = models_all_data.get("model", [])
            cached_dict = {m["model_id"]: m for m in cached_models}
            
            models_info = []
            for model in models_list:
                model_id = model["id"]
                cached = cached_dict.get(model_id, {})
                
                models_info.append(ModelInfo(
                    id=model_id,
                    total_weight=cached.get("total_weight", 0),
                    participant_count=cached.get("participant_count", 0),
                    proposed_by=model.get("proposed_by", ""),
                    v_ram=model.get("v_ram", ""),
                    throughput_per_nonce=model.get("throughput_per_nonce", ""),
                    units_of_compute_per_token=model.get("units_of_compute_per_token", ""),
                    hf_repo=model.get("hf_repo", ""),
                    hf_commit=model.get("hf_commit", ""),
                    model_args=model.get("model_args", []),
                    validation_threshold=model.get("validation_threshold", {})
                ))
            
            stats_info = []
            for stat in stats_list:
                stats_info.append(ModelStats(
                    model=stat.get("model", ""),
                    ai_tokens=stat.get("ai_tokens", "0"),
                    inferences=stat.get("inferences", 0)
                ))
            
            current_block_timestamp = None
            avg_block_time = None
            if self.current_epoch_data:
                current_block_timestamp = self.current_epoch_data.current_block_timestamp
                avg_block_time = self.current_epoch_data.avg_block_time
            
            return ModelsResponse(
                epoch_id=epoch_id,
                height=cached_height,
                models=models_info,
                stats=stats_info,
                cached_at=cached_api_data.get("cached_at", datetime.utcnow().isoformat()),
                is_current=True,
                current_block_timestamp=current_block_timestamp,
                avg_block_time=avg_block_time
            )
        
        epoch_data = await self.client.get_current_epoch_participants()
        participants = epoch_data["active_participants"]["participants"]
        height = await self.client.get_latest_height()
        
        cached_models = await self.cache_db.get_models(epoch_id)
        
        if cached_models:
            logger.info(f"Returning cached models for epoch {epoch_id}")
        else:
            logger.info(f"Fetching and aggregating models for epoch {epoch_id}")
            
            model_weights: Dict[str, int] = {}
            model_participant_count: Dict[str, set] = {}
            
            for participant in participants:
                participant_index = participant["index"]
                models = participant.get("models", [])
                ml_nodes_high_level = participant.get("ml_nodes", [])
                
                for model, ml_nodes_entry in zip(models, ml_nodes_high_level):
                    if model not in model_weights:
                        model_weights[model] = 0
                        model_participant_count[model] = set()
                    
                    for ml_node in ml_nodes_entry.get("ml_nodes", []):
                        poc_weight = ml_node.get("poc_weight", 0)
                        model_weights[model] += poc_weight
                    
                    model_participant_count[model].add(participant_index)
            
            models_to_cache = []
            for model_id in model_weights:
                models_to_cache.append({
                    "model_id": model_id,
                    "total_weight": model_weights[model_id],
                    "participant_count": len(model_participant_count[model_id])
                })
            
            if models_to_cache:
                await self.cache_db.save_models_batch(epoch_id, models_to_cache)
            
            cached_models = models_to_cache
        
        cached_api_data = await self.cache_db.get_models_api_cache(epoch_id)
        
        if cached_api_data:
            cached_height = cached_api_data.get("cached_height", "unknown")
            logger.info(f"Using cached models API data for epoch {epoch_id} (cached at height {cached_height}, current height {height})")
            models_all_data = cached_api_data["models_all"]
            models_stats_data = cached_api_data["models_stats"]
        else:
            logger.info(f"Fetching fresh models API data for epoch {epoch_id} at height {height}")
            models_all_data = await self.client.get_models_all()
            models_stats_data = await self.client.get_models_stats()
            
            await self.cache_db.save_models_api_cache(
                epoch_id, height, models_all_data, models_stats_data
            )
        
        stats_list = models_stats_data.get("stats_models", [])
        models_list = models_all_data.get("model", [])
        
        models_dict = {m["id"]: m for m in models_list}
        cached_dict = {m["model_id"]: m for m in cached_models} if cached_models else {}
        
        models_info = []
        for model in models_list:
            model_id = model["id"]
            cached = cached_dict.get(model_id, {})
            
            models_info.append(ModelInfo(
                id=model_id,
                total_weight=cached.get("total_weight", 0),
                participant_count=cached.get("participant_count", 0),
                proposed_by=model.get("proposed_by", ""),
                v_ram=model.get("v_ram", ""),
                throughput_per_nonce=model.get("throughput_per_nonce", ""),
                units_of_compute_per_token=model.get("units_of_compute_per_token", ""),
                hf_repo=model.get("hf_repo", ""),
                hf_commit=model.get("hf_commit", ""),
                model_args=model.get("model_args", []),
                validation_threshold=model.get("validation_threshold", {})
            ))
        
        stats_info = []
        for stat in stats_list:
            stats_info.append(ModelStats(
                model=stat.get("model", ""),
                ai_tokens=stat.get("ai_tokens", "0"),
                inferences=stat.get("inferences", 0)
            ))
        
        current_block_timestamp = None
        avg_block_time = None
        if self.current_epoch_data:
            current_block_timestamp = self.current_epoch_data.current_block_timestamp
            avg_block_time = self.current_epoch_data.avg_block_time
        
        return ModelsResponse(
            epoch_id=epoch_id,
            height=height,
            models=models_info,
            stats=stats_info,
            cached_at=datetime.utcnow().isoformat(),
            is_current=True,
            current_block_timestamp=current_block_timestamp,
            avg_block_time=avg_block_time
        )
    
    async def get_historical_models(self, epoch_id: int, height: Optional[int] = None) -> ModelsResponse:
        epoch_data = await self.client.get_epoch_participants(epoch_id)
        participants = epoch_data["active_participants"]["participants"]
        target_height = await self.get_canonical_height(epoch_id, height)
        
        cached_models = await self.cache_db.get_models(epoch_id)
        
        if cached_models:
            logger.info(f"Returning cached models for epoch {epoch_id}")
        else:
            logger.info(f"Fetching and aggregating models for epoch {epoch_id}")
            
            model_weights: Dict[str, int] = {}
            model_participant_count: Dict[str, set] = {}
            
            for participant in participants:
                participant_index = participant["index"]
                models = participant.get("models", [])
                ml_nodes_high_level = participant.get("ml_nodes", [])
                
                for model, ml_nodes_entry in zip(models, ml_nodes_high_level):
                    if model not in model_weights:
                        model_weights[model] = 0
                        model_participant_count[model] = set()
                    
                    for ml_node in ml_nodes_entry.get("ml_nodes", []):
                        poc_weight = ml_node.get("poc_weight", 0)
                        model_weights[model] += poc_weight
                    
                    model_participant_count[model].add(participant_index)
            
            models_to_cache = []
            for model_id in model_weights:
                models_to_cache.append({
                    "model_id": model_id,
                    "total_weight": model_weights[model_id],
                    "participant_count": len(model_participant_count[model_id])
                })
            
            if models_to_cache:
                await self.cache_db.save_models_batch(epoch_id, models_to_cache)
            
            cached_models = models_to_cache
        
        cached_api_data = await self.cache_db.get_models_api_cache(epoch_id, target_height)
        
        if cached_api_data:
            logger.info(f"Using cached models API data for historical epoch {epoch_id} at height {target_height}")
            models_all_data = cached_api_data["models_all"]
            models_stats_data = cached_api_data["models_stats"]
        else:
            logger.info(f"Fetching fresh models API data for historical epoch {epoch_id} at height {target_height}")
            models_all_data = await self.client.get_models_all()
            models_stats_data = await self.client.get_models_stats()
            
            await self.cache_db.save_models_api_cache(
                epoch_id, target_height, models_all_data, models_stats_data
            )
        
        stats_list = models_stats_data.get("stats_models", [])
        models_list = models_all_data.get("model", [])
        
        models_dict = {m["id"]: m for m in models_list}
        cached_dict = {m["model_id"]: m for m in cached_models} if cached_models else {}
        
        models_info = []
        for model in models_list:
            model_id = model["id"]
            cached = cached_dict.get(model_id, {})
            
            models_info.append(ModelInfo(
                id=model_id,
                total_weight=cached.get("total_weight", 0),
                participant_count=cached.get("participant_count", 0),
                proposed_by=model.get("proposed_by", ""),
                v_ram=model.get("v_ram", ""),
                throughput_per_nonce=model.get("throughput_per_nonce", ""),
                units_of_compute_per_token=model.get("units_of_compute_per_token", ""),
                hf_repo=model.get("hf_repo", ""),
                hf_commit=model.get("hf_commit", ""),
                model_args=model.get("model_args", []),
                validation_threshold=model.get("validation_threshold", {})
            ))
        
        stats_info = []
        for stat in stats_list:
            stats_info.append(ModelStats(
                model=stat.get("model", ""),
                ai_tokens=stat.get("ai_tokens", "0"),
                inferences=stat.get("inferences", 0)
            ))
        
        current_block_timestamp = None
        avg_block_time = None
        if self.current_epoch_data:
            current_block_timestamp = self.current_epoch_data.current_block_timestamp
            avg_block_time = self.current_epoch_data.avg_block_time
        
        return ModelsResponse(
            epoch_id=epoch_id,
            height=target_height,
            models=models_info,
            stats=stats_info,
            cached_at=datetime.utcnow().isoformat(),
            is_current=False,
            current_block_timestamp=current_block_timestamp,
            avg_block_time=avg_block_time
        )
    
    async def poll_participant_inferences(self):
        try:
            logger.info("Polling participant inferences")
            
            epoch_data = await self.client.get_current_epoch_participants()
            current_epoch = epoch_data["active_participants"]["epoch_group_id"]
            current_epoch_effective_height = epoch_data["active_participants"]["effective_block_height"]
            participants = epoch_data["active_participants"]["participants"]
            participant_indices = {p["index"] for p in participants}
            
            latest_epoch_info = await self.client.get_latest_epoch()
            epoch_length = latest_epoch_info["epoch_params"]["epoch_length"]
            
            logger.info(f"Fetching all inferences (all epochs)")
            all_inferences = await self.client.get_all_inferences()
            logger.info(f"Fetched {len(all_inferences)} total inferences")
            logger.info(f"Current epoch: {current_epoch}, effective_height: {current_epoch_effective_height}, epoch_length: {epoch_length}")
            
            fixed_epoch_count = 0
            for inf in all_inferences:
                if inf.get("epoch_id") == "0":
                    start_height = int(inf.get("start_block_height", 0))
                    if start_height > 0:
                        if start_height >= current_epoch_effective_height:
                            calculated_epoch = current_epoch
                        else:
                            blocks_before_current = current_epoch_effective_height - start_height
                            epochs_back = (blocks_before_current + epoch_length - 1) // epoch_length
                            calculated_epoch = current_epoch - epochs_back
                        
                        if inf.get("status") == "EXPIRED":
                            logger.info(f"EXPIRED inference {inf.get('inference_id')}: start_height={start_height}, calculated_epoch={calculated_epoch}, assigned_to={inf.get('assigned_to')}")
                        
                        inf["epoch_id"] = str(calculated_epoch)
                        fixed_epoch_count += 1
            
            if fixed_epoch_count > 0:
                logger.info(f"Fixed epoch_id for {fixed_epoch_count} inferences with epoch_id='0'")
            
            epoch_distribution = {}
            for inf in all_inferences:
                eid = inf.get("epoch_id", "unknown")
                epoch_distribution[eid] = epoch_distribution.get(eid, 0) + 1
            logger.info(f"Epoch distribution before filtering: {epoch_distribution}")
            
            target_epochs = {str(current_epoch), str(current_epoch - 1)}
            all_inferences = [inf for inf in all_inferences if inf.get("epoch_id") in target_epochs]
            logger.info(f"After filtering by epochs {current_epoch} and {current_epoch - 1}: {len(all_inferences)} inferences")
            
            status_counts = {}
            for inf in all_inferences:
                status = inf.get("status", "UNKNOWN")
                status_counts[status] = status_counts.get(status, 0) + 1
            logger.info(f"Inference status distribution: {status_counts}")
            
            by_participant = {p["index"]: [] for p in participants}
            
            for inf in all_inferences:
                assigned_to = inf.get("assigned_to")
                if assigned_to:
                    if assigned_to not in by_participant:
                        by_participant[assigned_to] = []
                    by_participant[assigned_to].append(inf)
            
            logger.info(f"Grouped inferences for {len(by_participant)} participants (including those with no inferences)")
            
            saved_count = 0
            for participant_id, inferences in by_participant.items():
                try:
                    by_epoch = {}
                    wrong_epoch_count = 0
                    for inf in inferences:
                        epoch_id = inf.get("epoch_id")
                        if epoch_id not in target_epochs:
                            wrong_epoch_count += 1
                            continue
                        
                        status = inf.get("status", "")
                        if status in ["FINISHED", "VALIDATED", "EXPIRED", "INVALIDATED"]:
                            if epoch_id not in by_epoch:
                                by_epoch[epoch_id] = []
                            by_epoch[epoch_id].append(inf)
                    
                    if wrong_epoch_count > 0:
                        logger.warning(f"Participant {participant_id}: filtered out {wrong_epoch_count} inferences with wrong epoch_id")
                    
                    for epoch_str in target_epochs:
                        epoch_id = int(epoch_str)
                        epoch_inferences = by_epoch.get(epoch_str, [])
                        by_status = {
                            "successful": [],
                            "expired": [],
                            "invalidated": []
                        }
                        
                        for inf in epoch_inferences:
                            status = inf.get("status", "")
                            if status in ["FINISHED", "VALIDATED"]:
                                by_status["successful"].append(inf)
                            elif status == "EXPIRED":
                                by_status["expired"].append(inf)
                            elif status == "INVALIDATED":
                                by_status["invalidated"].append(inf)
                        
                        for key in by_status:
                            by_status[key] = sorted(
                                by_status[key],
                                key=lambda x: int(x.get("start_block_timestamp", 0)),
                                reverse=True
                            )[:10]
                        
                        to_save = by_status["successful"] + by_status["expired"] + by_status["invalidated"]
                        
                        await self.cache_db.save_participant_inferences_batch(
                            epoch_id=int(epoch_id),
                            participant_id=participant_id,
                            inferences=to_save
                        )
                        saved_count += len(to_save)
                        logger.info(f"Cached inferences for {participant_id} epoch {epoch_id}: {len(by_status['successful'])} successful, {len(by_status['expired'])} expired, {len(by_status['invalidated'])} invalidated")
                    
                except Exception as e:
                    logger.debug(f"Failed to process inferences for {participant_id}: {e}")
                    continue
            
            logger.info(f"Completed participant inferences polling: {saved_count} inferences cached for {len(by_participant)} participants across epochs {current_epoch} and {current_epoch - 1}")
            
        except Exception as e:
            logger.error(f"Error polling participant inferences: {e}")
    
    async def get_participant_inferences_summary(
        self,
        epoch_id: int,
        participant_id: str
    ) -> Dict[str, Any]:
        try:
            logger.info(f"Fetching inferences summary for participant {participant_id} in epoch {epoch_id}")
            
            cached_inferences = await self.cache_db.get_participant_inferences(
                epoch_id=epoch_id,
                participant_id=participant_id
            )
            
            logger.info(f"Cache result for {participant_id} epoch {epoch_id}: {type(cached_inferences)} with {len(cached_inferences) if cached_inferences is not None else 'None'} items")
            
            if cached_inferences is None:
                logger.warning(f"No cached inferences for {participant_id} in epoch {epoch_id}, returning empty (cache-only mode)")
                return {
                    "epoch_id": epoch_id,
                    "participant_id": participant_id,
                    "successful": [],
                    "expired": [],
                    "invalidated": [],
                    "cached_at": None
                }
            
            successful = []
            expired = []
            invalidated = []
            skipped_count = 0
            
            for inf in cached_inferences:
                try:
                    if not inf.get("inference_id") or not inf.get("status"):
                        skipped_count += 1
                        continue
                    
                    status = inf.get("status", "")
                    if status in ["FINISHED", "VALIDATED"]:
                        successful.append(inf)
                    elif status == "EXPIRED":
                        expired.append(inf)
                    elif status == "INVALIDATED":
                        invalidated.append(inf)
                except Exception as e:
                    logger.warning(f"Skipping invalid inference record for {participant_id}: {e}")
                    skipped_count += 1
                    continue
            
            if skipped_count > 0:
                logger.warning(f"Skipped {skipped_count} invalid inference records for {participant_id} in epoch {epoch_id}")
            
            return {
                "epoch_id": epoch_id,
                "participant_id": participant_id,
                "successful": successful[:10],
                "expired": expired[:10],
                "invalidated": invalidated[:10],
                "cached_at": datetime.utcnow().isoformat() if cached_inferences is not None else None
            }
            
        except Exception as e:
            logger.error(f"Error getting participant inferences summary for {participant_id} epoch {epoch_id}: {e}", exc_info=True)
            return {
                "epoch_id": epoch_id,
                "participant_id": participant_id,
                "successful": [],
                "expired": [],
                "invalidated": [],
                "cached_at": None
            }
    
    async def poll_models_api_cache(self):
        try:
            logger.info("Polling models API cache")
            
            epoch_data = await self.client.get_current_epoch_participants()
            epoch_id = epoch_data["active_participants"]["epoch_group_id"]
            height = await self.client.get_latest_height()
            
            models_all_data = await self.client.get_models_all()
            models_stats_data = await self.client.get_models_stats()
            
            await self.cache_db.save_models_api_cache(
                epoch_id, height, models_all_data, models_stats_data
            )
            logger.info(f"Cached models API data for current epoch {epoch_id} at height {height}")
            
        except Exception as e:
            logger.error(f"Error polling models API cache: {e}")

