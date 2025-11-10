import aiosqlite
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class CacheDB:
    def __init__(self, db_path: str = "cache.db"):
        self.db_path = db_path
        
    async def initialize(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS inference_stats (
                    epoch_id INTEGER NOT NULL,
                    height INTEGER NOT NULL,
                    participant_index TEXT NOT NULL,
                    stats_json TEXT NOT NULL,
                    seed_signature TEXT,
                    cached_at TEXT NOT NULL,
                    PRIMARY KEY (epoch_id, height, participant_index)
                )
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_epoch_height 
                ON inference_stats(epoch_id, height)
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS epoch_status (
                    epoch_id INTEGER PRIMARY KEY,
                    is_finished BOOLEAN NOT NULL,
                    finish_height INTEGER,
                    marked_at TEXT NOT NULL
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS jail_status (
                    epoch_id INTEGER NOT NULL,
                    participant_index TEXT NOT NULL,
                    is_jailed BOOLEAN NOT NULL,
                    jailed_until TEXT,
                    ready_to_unjail BOOLEAN,
                    valcons_address TEXT,
                    moniker TEXT,
                    identity TEXT,
                    keybase_username TEXT,
                    keybase_picture_url TEXT,
                    website TEXT,
                    validator_consensus_key TEXT,
                    consensus_key_mismatch BOOLEAN,
                    recorded_at TEXT NOT NULL,
                    PRIMARY KEY (epoch_id, participant_index)
                )
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_participant_jail 
                ON jail_status(participant_index)
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS node_health (
                    participant_index TEXT NOT NULL,
                    is_healthy BOOLEAN NOT NULL,
                    last_check TEXT NOT NULL,
                    error_message TEXT,
                    response_time_ms INTEGER,
                    PRIMARY KEY (participant_index)
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS participant_rewards (
                    epoch_id INTEGER NOT NULL,
                    participant_id TEXT NOT NULL,
                    rewarded_coins TEXT NOT NULL,
                    claimed INTEGER NOT NULL,
                    last_updated TEXT NOT NULL,
                    PRIMARY KEY (epoch_id, participant_id)
                )
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_participant_rewards
                ON participant_rewards(participant_id)
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS participant_warm_keys (
                    epoch_id INTEGER NOT NULL,
                    participant_id TEXT NOT NULL,
                    grantee_address TEXT NOT NULL,
                    granted_at TEXT NOT NULL,
                    last_updated TEXT NOT NULL,
                    PRIMARY KEY (epoch_id, participant_id, grantee_address)
                )
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_warm_keys_participant
                ON participant_warm_keys(epoch_id, participant_id)
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS participant_hardware_nodes (
                    epoch_id INTEGER NOT NULL,
                    participant_id TEXT NOT NULL,
                    local_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    models_json TEXT NOT NULL,
                    hardware_json TEXT NOT NULL,
                    host TEXT NOT NULL,
                    port TEXT NOT NULL,
                    poc_weight INTEGER,
                    last_updated TEXT NOT NULL,
                    PRIMARY KEY (epoch_id, participant_id, local_id)
                )
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_hardware_nodes_participant
                ON participant_hardware_nodes(epoch_id, participant_id)
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS epoch_total_rewards (
                    epoch_id INTEGER PRIMARY KEY,
                    total_rewards_gnk INTEGER NOT NULL,
                    calculated_at TEXT NOT NULL
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS models (
                    epoch_id INTEGER NOT NULL,
                    model_id TEXT NOT NULL,
                    total_weight INTEGER NOT NULL,
                    participant_count INTEGER NOT NULL,
                    cached_at TEXT NOT NULL,
                    PRIMARY KEY (epoch_id, model_id)
                )
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_models_epoch
                ON models(epoch_id)
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS models_api_cache (
                    epoch_id INTEGER NOT NULL,
                    height INTEGER NOT NULL,
                    models_all_json TEXT NOT NULL,
                    models_stats_json TEXT NOT NULL,
                    cached_at TEXT NOT NULL,
                    PRIMARY KEY (epoch_id, height)
                )
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_models_api_epoch
                ON models_api_cache(epoch_id)
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS participant_inferences (
                    epoch_id INTEGER NOT NULL,
                    participant_id TEXT NOT NULL,
                    inference_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    start_block_height TEXT NOT NULL,
                    start_block_timestamp TEXT NOT NULL,
                    validated_by_json TEXT,
                    prompt_hash TEXT,
                    response_hash TEXT,
                    prompt_payload TEXT,
                    response_payload TEXT,
                    prompt_token_count TEXT,
                    completion_token_count TEXT,
                    model TEXT,
                    last_updated TEXT NOT NULL,
                    PRIMARY KEY (epoch_id, participant_id, inference_id)
                )
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_participant_inferences
                ON participant_inferences(epoch_id, participant_id, status)
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS timeline_cache (
                    id INTEGER PRIMARY KEY,
                    timeline_json TEXT NOT NULL,
                    cached_at TEXT NOT NULL
                )
            """)
            
            await db.commit()
            logger.info(f"Database initialized at {self.db_path}")
    
    async def save_stats(
        self,
        epoch_id: int,
        height: int,
        participant_index: str,
        stats: Dict[str, Any],
        seed_signature: Optional[str] = None
    ):
        cached_at = datetime.utcnow().isoformat()
        stats_json = json.dumps(stats)
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO inference_stats 
                (epoch_id, height, participant_index, stats_json, seed_signature, cached_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (epoch_id, height, participant_index, stats_json, seed_signature, cached_at))
            await db.commit()
    
    async def save_stats_batch(
        self,
        epoch_id: int,
        height: int,
        participants_stats: List[Dict[str, Any]]
    ):
        cached_at = datetime.utcnow().isoformat()
        
        async with aiosqlite.connect(self.db_path) as db:
            for stats in participants_stats:
                participant_index = stats.get("index")
                seed_signature = stats.get("seed_signature")
                stats_json = json.dumps(stats)
                
                await db.execute("""
                    INSERT OR REPLACE INTO inference_stats 
                    (epoch_id, height, participant_index, stats_json, seed_signature, cached_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (epoch_id, height, participant_index, stats_json, seed_signature, cached_at))
            
            await db.commit()
            logger.info(f"Saved {len(participants_stats)} stats for epoch {epoch_id} at height {height}")
    
    async def get_stats(self, epoch_id: int, height: Optional[int] = None) -> Optional[List[Dict[str, Any]]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            if height is not None:
                query = """
                    SELECT participant_index, stats_json, seed_signature, height, cached_at
                    FROM inference_stats
                    WHERE epoch_id = ? AND height = ?
                """
                params = (epoch_id, height)
            else:
                query = """
                    SELECT participant_index, stats_json, seed_signature, height, cached_at
                    FROM inference_stats
                    WHERE epoch_id = ?
                """
                params = (epoch_id,)
            
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                
                if not rows:
                    return None
                
                results = []
                for row in rows:
                    stats = json.loads(row["stats_json"])
                    stats["_cached_at"] = row["cached_at"]
                    stats["_height"] = row["height"]
                    stats["_seed_signature"] = row["seed_signature"]
                    results.append(stats)
                
                return results
    
    async def has_stats_for_epoch(self, epoch_id: int, height: Optional[int] = None) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            if height is not None:
                query = "SELECT COUNT(*) as count FROM inference_stats WHERE epoch_id = ? AND height = ?"
                params = (epoch_id, height)
            else:
                query = "SELECT COUNT(*) as count FROM inference_stats WHERE epoch_id = ?"
                params = (epoch_id,)
            
            async with db.execute(query, params) as cursor:
                row = await cursor.fetchone()
                return row[0] > 0
    
    async def mark_epoch_finished(self, epoch_id: int, finish_height: int):
        marked_at = datetime.utcnow().isoformat()
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO epoch_status 
                (epoch_id, is_finished, finish_height, marked_at)
                VALUES (?, ?, ?, ?)
            """, (epoch_id, True, finish_height, marked_at))
            await db.commit()
            logger.info(f"Marked epoch {epoch_id} as finished at height {finish_height}")
    
    async def is_epoch_finished(self, epoch_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT is_finished FROM epoch_status WHERE epoch_id = ?
            """, (epoch_id,)) as cursor:
                row = await cursor.fetchone()
                return row["is_finished"] if row else False
    
    async def get_epoch_finish_height(self, epoch_id: int) -> Optional[int]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT finish_height FROM epoch_status WHERE epoch_id = ?
            """, (epoch_id,)) as cursor:
                row = await cursor.fetchone()
                return row["finish_height"] if row else None
    
    async def clear_epoch_stats(self, epoch_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM inference_stats WHERE epoch_id = ?", (epoch_id,))
            await db.execute("DELETE FROM epoch_status WHERE epoch_id = ?", (epoch_id,))
            await db.commit()
    
    async def save_jail_status_batch(
        self,
        epoch_id: int,
        jail_statuses: List[Dict[str, Any]]
    ):
        recorded_at = datetime.utcnow().isoformat()
        
        async with aiosqlite.connect(self.db_path) as db:
            for status in jail_statuses:
                await db.execute("""
                    INSERT OR REPLACE INTO jail_status 
                    (epoch_id, participant_index, is_jailed, jailed_until, ready_to_unjail, valcons_address, 
                     moniker, identity, keybase_username, keybase_picture_url, website, 
                     validator_consensus_key, consensus_key_mismatch, recorded_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    epoch_id,
                    status.get("participant_index"),
                    status.get("is_jailed", False),
                    status.get("jailed_until"),
                    status.get("ready_to_unjail", False),
                    status.get("valcons_address"),
                    status.get("moniker"),
                    status.get("identity"),
                    status.get("keybase_username"),
                    status.get("keybase_picture_url"),
                    status.get("website"),
                    status.get("validator_consensus_key"),
                    status.get("consensus_key_mismatch"),
                    recorded_at
                ))
            
            await db.commit()
            logger.info(f"Saved {len(jail_statuses)} jail statuses for epoch {epoch_id}")
    
    async def get_jail_status(self, epoch_id: int, participant_index: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            if participant_index:
                query = """
                    SELECT * FROM jail_status
                    WHERE epoch_id = ? AND participant_index = ?
                """
                params = (epoch_id, participant_index)
            else:
                query = """
                    SELECT * FROM jail_status
                    WHERE epoch_id = ?
                """
                params = (epoch_id,)
            
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                
                if not rows:
                    return None
                
                results = []
                for row in rows:
                    row_dict = dict(row)
                    results.append({
                        "epoch_id": row_dict["epoch_id"],
                        "participant_index": row_dict["participant_index"],
                        "is_jailed": bool(row_dict["is_jailed"]),
                        "jailed_until": row_dict["jailed_until"],
                        "ready_to_unjail": bool(row_dict["ready_to_unjail"]) if row_dict["ready_to_unjail"] is not None else None,
                        "valcons_address": row_dict["valcons_address"],
                        "moniker": row_dict.get("moniker"),
                        "identity": row_dict.get("identity"),
                        "keybase_username": row_dict.get("keybase_username"),
                        "keybase_picture_url": row_dict.get("keybase_picture_url"),
                        "website": row_dict.get("website"),
                        "validator_consensus_key": row_dict.get("validator_consensus_key"),
                        "consensus_key_mismatch": bool(row_dict.get("consensus_key_mismatch")) if row_dict.get("consensus_key_mismatch") is not None else None,
                        "recorded_at": row_dict["recorded_at"]
                    })
                
                return results
    
    async def save_node_health_batch(
        self,
        health_statuses: List[Dict[str, Any]]
    ):
        last_check = datetime.utcnow().isoformat()
        
        async with aiosqlite.connect(self.db_path) as db:
            for status in health_statuses:
                await db.execute("""
                    INSERT OR REPLACE INTO node_health 
                    (participant_index, is_healthy, last_check, error_message, response_time_ms)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    status.get("participant_index"),
                    status.get("is_healthy", False),
                    last_check,
                    status.get("error_message"),
                    status.get("response_time_ms")
                ))
            
            await db.commit()
            logger.info(f"Saved {len(health_statuses)} node health statuses")
    
    async def get_node_health(self, participant_index: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            if participant_index:
                query = "SELECT * FROM node_health WHERE participant_index = ?"
                params = (participant_index,)
            else:
                query = "SELECT * FROM node_health"
                params = ()
            
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                
                if not rows:
                    return None
                
                results = []
                for row in rows:
                    results.append({
                        "participant_index": row["participant_index"],
                        "is_healthy": bool(row["is_healthy"]),
                        "last_check": row["last_check"],
                        "error_message": row["error_message"],
                        "response_time_ms": row["response_time_ms"]
                    })
                
                return results
    
    async def save_reward_batch(
        self,
        rewards: List[Dict[str, Any]]
    ):
        last_updated = datetime.utcnow().isoformat()
        
        async with aiosqlite.connect(self.db_path) as db:
            for reward in rewards:
                await db.execute("""
                    INSERT OR REPLACE INTO participant_rewards 
                    (epoch_id, participant_id, rewarded_coins, claimed, last_updated)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    reward.get("epoch_id"),
                    reward.get("participant_id"),
                    reward.get("rewarded_coins", "0"),
                    1 if reward.get("claimed") else 0,
                    last_updated
                ))
            
            await db.commit()
            logger.info(f"Saved {len(rewards)} rewards")
    
    async def get_reward(self, epoch_id: int, participant_id: str) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            async with db.execute("""
                SELECT * FROM participant_rewards
                WHERE epoch_id = ? AND participant_id = ?
            """, (epoch_id, participant_id)) as cursor:
                row = await cursor.fetchone()
                
                if not row:
                    return None
                
                return {
                    "epoch_id": row["epoch_id"],
                    "participant_id": row["participant_id"],
                    "rewarded_coins": row["rewarded_coins"],
                    "claimed": bool(row["claimed"]),
                    "last_updated": row["last_updated"]
                }
    
    async def get_rewards_for_participant(
        self,
        participant_id: str,
        epoch_ids: List[int]
    ) -> List[Dict[str, Any]]:
        if not epoch_ids:
            return []
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            placeholders = ",".join("?" * len(epoch_ids))
            query = f"""
                SELECT * FROM participant_rewards
                WHERE participant_id = ? AND epoch_id IN ({placeholders})
                ORDER BY epoch_id DESC
            """
            params = [participant_id] + epoch_ids
            
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                
                results = []
                for row in rows:
                    results.append({
                        "epoch_id": row["epoch_id"],
                        "participant_id": row["participant_id"],
                        "rewarded_coins": row["rewarded_coins"],
                        "claimed": bool(row["claimed"]),
                        "last_updated": row["last_updated"]
                    })
                
                return results
    
    async def save_warm_keys_batch(
        self,
        epoch_id: int,
        participant_id: str,
        warm_keys: List[Dict[str, Any]]
    ):
        last_updated = datetime.utcnow().isoformat()
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                DELETE FROM participant_warm_keys
                WHERE epoch_id = ? AND participant_id = ?
            """, (epoch_id, participant_id))
            
            for warm_key in warm_keys:
                await db.execute("""
                    INSERT INTO participant_warm_keys 
                    (epoch_id, participant_id, grantee_address, granted_at, last_updated)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    epoch_id,
                    participant_id,
                    warm_key.get("grantee_address"),
                    warm_key.get("granted_at"),
                    last_updated
                ))
            
            await db.commit()
            logger.info(f"Saved {len(warm_keys)} warm keys for participant {participant_id} in epoch {epoch_id}")
    
    async def get_warm_keys(
        self,
        epoch_id: int,
        participant_id: str
    ) -> Optional[List[Dict[str, Any]]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            async with db.execute("""
                SELECT grantee_address, granted_at
                FROM participant_warm_keys
                WHERE epoch_id = ? AND participant_id = ?
                ORDER BY granted_at DESC
            """, (epoch_id, participant_id)) as cursor:
                rows = await cursor.fetchall()
                
                if not rows:
                    return None
                
                results = []
                for row in rows:
                    results.append({
                        "grantee_address": row["grantee_address"],
                        "granted_at": row["granted_at"]
                    })
                
                return results
    
    async def save_hardware_nodes_batch(
        self,
        epoch_id: int,
        participant_id: str,
        hardware_nodes: List[Dict[str, Any]]
    ):
        last_updated = datetime.utcnow().isoformat()
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                DELETE FROM participant_hardware_nodes
                WHERE epoch_id = ? AND participant_id = ?
            """, (epoch_id, participant_id))
            
            for node in hardware_nodes:
                models_json = json.dumps(node.get("models", []))
                hardware_json = json.dumps(node.get("hardware", []))
                
                await db.execute("""
                    INSERT INTO participant_hardware_nodes 
                    (epoch_id, participant_id, local_id, status, models_json, hardware_json, host, port, poc_weight, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    epoch_id,
                    participant_id,
                    node.get("local_id", ""),
                    node.get("status", ""),
                    models_json,
                    hardware_json,
                    node.get("host", ""),
                    node.get("port", ""),
                    node.get("poc_weight"),
                    last_updated
                ))
            
            await db.commit()
            logger.info(f"Saved {len(hardware_nodes)} hardware nodes for participant {participant_id} in epoch {epoch_id}")
    
    async def get_hardware_nodes(
        self,
        epoch_id: int,
        participant_id: str
    ) -> Optional[List[Dict[str, Any]]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            async with db.execute("""
                SELECT local_id, status, models_json, hardware_json, host, port, poc_weight
                FROM participant_hardware_nodes
                WHERE epoch_id = ? AND participant_id = ?
                ORDER BY local_id ASC
            """, (epoch_id, participant_id)) as cursor:
                rows = await cursor.fetchall()
                
                if not rows:
                    return None
                
                results = []
                for row in rows:
                    results.append({
                        "local_id": row["local_id"],
                        "status": row["status"],
                        "models": json.loads(row["models_json"]),
                        "hardware": json.loads(row["hardware_json"]),
                        "host": row["host"],
                        "port": row["port"],
                        "poc_weight": row["poc_weight"]
                    })
                
                return results
    
    async def save_epoch_total_rewards(
        self,
        epoch_id: int,
        total_rewards_gnk: int
    ):
        calculated_at = datetime.utcnow().isoformat()
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO epoch_total_rewards 
                (epoch_id, total_rewards_gnk, calculated_at)
                VALUES (?, ?, ?)
            """, (epoch_id, total_rewards_gnk, calculated_at))
            await db.commit()
            logger.info(f"Saved total rewards {total_rewards_gnk} GNK for epoch {epoch_id}")
    
    async def get_epoch_total_rewards(
        self,
        epoch_id: int
    ) -> Optional[int]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            async with db.execute("""
                SELECT total_rewards_gnk
                FROM epoch_total_rewards
                WHERE epoch_id = ?
            """, (epoch_id,)) as cursor:
                row = await cursor.fetchone()
                
                if not row:
                    return None
                
                return row["total_rewards_gnk"]
    
    async def delete_epoch_total_rewards(
        self,
        epoch_id: int
    ):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                DELETE FROM epoch_total_rewards
                WHERE epoch_id = ?
            """, (epoch_id,))
            await db.commit()
            logger.info(f"Deleted total rewards cache for epoch {epoch_id}")
    
    async def save_models_batch(
        self,
        epoch_id: int,
        models_data: List[Dict[str, Any]]
    ):
        cached_at = datetime.utcnow().isoformat()
        
        async with aiosqlite.connect(self.db_path) as db:
            for model in models_data:
                model_id = model.get("model_id")
                total_weight = model.get("total_weight", 0)
                participant_count = model.get("participant_count", 0)
                
                await db.execute("""
                    INSERT OR REPLACE INTO models 
                    (epoch_id, model_id, total_weight, participant_count, cached_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (epoch_id, model_id, total_weight, participant_count, cached_at))
            
            await db.commit()
            logger.info(f"Saved {len(models_data)} models for epoch {epoch_id}")
    
    async def get_models(
        self,
        epoch_id: int
    ) -> Optional[List[Dict[str, Any]]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            async with db.execute("""
                SELECT model_id, total_weight, participant_count, cached_at
                FROM models
                WHERE epoch_id = ?
            """, (epoch_id,)) as cursor:
                rows = await cursor.fetchall()
                
                if not rows:
                    return None
                
                results = []
                for row in rows:
                    results.append({
                        "model_id": row["model_id"],
                        "total_weight": row["total_weight"],
                        "participant_count": row["participant_count"],
                        "cached_at": row["cached_at"]
                    })
                
                return results
    
    async def save_participant_inferences_batch(
        self,
        epoch_id: int,
        participant_id: str,
        inferences: List[Dict[str, Any]]
    ):
        last_updated = datetime.utcnow().isoformat()
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                DELETE FROM participant_inferences
                WHERE epoch_id = ? AND participant_id = ?
            """, (epoch_id, participant_id))
            
            if len(inferences) == 0:
                await db.execute("""
                    INSERT INTO participant_inferences 
                    (epoch_id, participant_id, inference_id, status, start_block_height, 
                     start_block_timestamp, validated_by_json, prompt_hash, response_hash,
                     prompt_payload, response_payload, prompt_token_count, 
                     completion_token_count, model, last_updated)
                    VALUES (?, ?, NULL, '_EMPTY_MARKER_', '0', '0', '[]', NULL, NULL, NULL, NULL, NULL, NULL, NULL, ?)
                """, (epoch_id, participant_id, last_updated))
            else:
                for inference in inferences:
                    validated_by_json = json.dumps(inference.get("validated_by", []))
                    
                    await db.execute("""
                        INSERT INTO participant_inferences 
                        (epoch_id, participant_id, inference_id, status, start_block_height, 
                         start_block_timestamp, validated_by_json, prompt_hash, response_hash,
                         prompt_payload, response_payload, prompt_token_count, 
                         completion_token_count, model, last_updated)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        epoch_id,
                        participant_id,
                        inference.get("inference_id"),
                        inference.get("status"),
                        inference.get("start_block_height"),
                        inference.get("start_block_timestamp"),
                        validated_by_json,
                        inference.get("prompt_hash"),
                        inference.get("response_hash"),
                        inference.get("prompt_payload"),
                        inference.get("response_payload"),
                        inference.get("prompt_token_count"),
                        inference.get("completion_token_count"),
                        inference.get("model"),
                        last_updated
                    ))
            
            await db.commit()
            logger.info(f"Saved {len(inferences)} inferences for participant {participant_id} in epoch {epoch_id}")
    
    async def get_participant_inferences(
        self,
        epoch_id: int,
        participant_id: str
    ) -> Optional[List[Dict[str, Any]]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            logger.debug(f"Querying inferences for participant {participant_id} in epoch {epoch_id}")
            
            async with db.execute("""
                SELECT inference_id, status, start_block_height, start_block_timestamp,
                       validated_by_json, prompt_hash, response_hash, prompt_payload,
                       response_payload, prompt_token_count, completion_token_count, model
                FROM participant_inferences
                WHERE epoch_id = ? AND participant_id = ?
                ORDER BY start_block_timestamp DESC
            """, (epoch_id, participant_id)) as cursor:
                rows = await cursor.fetchall()
                
                logger.debug(f"Found {len(rows)} rows for participant {participant_id} in epoch {epoch_id}")
                
                if not rows:
                    logger.debug(f"No rows found, returning None")
                    return None
                
                has_marker = any(row["status"] == "_EMPTY_MARKER_" for row in rows)
                
                results = []
                for row in rows:
                    try:
                        if row["status"] == "_EMPTY_MARKER_":
                            continue
                        
                        validated_by = []
                        if row["validated_by_json"]:
                            try:
                                validated_by = json.loads(row["validated_by_json"])
                            except json.JSONDecodeError as e:
                                logger.warning(f"Invalid JSON in validated_by for inference {row['inference_id']}: {e}")
                        
                        results.append({
                            "inference_id": row["inference_id"],
                            "status": row["status"],
                            "start_block_height": row["start_block_height"],
                            "start_block_timestamp": row["start_block_timestamp"],
                            "validated_by": validated_by,
                            "prompt_hash": row["prompt_hash"],
                            "response_hash": row["response_hash"],
                            "prompt_payload": row["prompt_payload"],
                            "response_payload": row["response_payload"],
                            "prompt_token_count": row["prompt_token_count"],
                            "completion_token_count": row["completion_token_count"],
                            "model": row["model"]
                        })
                    except Exception as e:
                        logger.warning(f"Failed to parse inference record {row.get('inference_id', 'unknown')}: {e}")
                        continue
                
                if has_marker and not results:
                    return []
                
                return results if results else None
    
    async def save_models_api_cache(
        self,
        epoch_id: int,
        height: int,
        models_all: Dict[str, Any],
        models_stats: Dict[str, Any]
    ):
        cached_at = datetime.utcnow().isoformat()
        models_all_json = json.dumps(models_all)
        models_stats_json = json.dumps(models_stats)
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO models_api_cache 
                (epoch_id, height, models_all_json, models_stats_json, cached_at)
                VALUES (?, ?, ?, ?, ?)
            """, (epoch_id, height, models_all_json, models_stats_json, cached_at))
            await db.commit()
            logger.info(f"Cached models API data for epoch {epoch_id} at height {height}")
    
    async def get_models_api_cache(
        self,
        epoch_id: int,
        height: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            if height is not None:
                query = """
                    SELECT models_all_json, models_stats_json, cached_at, height
                    FROM models_api_cache
                    WHERE epoch_id = ? AND height = ?
                """
                params = (epoch_id, height)
            else:
                query = """
                    SELECT models_all_json, models_stats_json, cached_at, height
                    FROM models_api_cache
                    WHERE epoch_id = ?
                    ORDER BY height DESC
                    LIMIT 1
                """
                params = (epoch_id,)
            
            async with db.execute(query, params) as cursor:
                row = await cursor.fetchone()
                
                if not row:
                    return None
                
                return {
                    "models_all": json.loads(row["models_all_json"]),
                    "models_stats": json.loads(row["models_stats_json"]),
                    "cached_at": row["cached_at"],
                    "cached_height": row["height"]
                }
    
    async def save_timeline_cache(self, timeline_data: Dict[str, Any]):
        cached_at = datetime.utcnow().isoformat()
        timeline_json = json.dumps(timeline_data)
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM timeline_cache")
            await db.execute("""
                INSERT INTO timeline_cache (id, timeline_json, cached_at)
                VALUES (1, ?, ?)
            """, (timeline_json, cached_at))
            await db.commit()
            logger.info("Cached timeline data")
    
    async def get_timeline_cache(self) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            async with db.execute("""
                SELECT timeline_json, cached_at
                FROM timeline_cache
                WHERE id = 1
            """) as cursor:
                row = await cursor.fetchone()
                
                if not row:
                    return None
                
                return {
                    "timeline": json.loads(row["timeline_json"]),
                    "cached_at": row["cached_at"]
                }

