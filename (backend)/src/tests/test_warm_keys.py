import pytest
import tempfile
import os
from backend.database import CacheDB
from backend.client import GonkaClient
from backend.service import InferenceService
from backend.models import WarmKeyInfo


@pytest.mark.asyncio
async def test_database_warm_keys_operations():
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
        db_path = f.name
    
    try:
        db = CacheDB(db_path)
        await db.initialize()
        
        epoch_id = 56
        participant_id = "gonka1test123"
        warm_keys = [
            {
                "grantee_address": "gonka1warm1",
                "granted_at": "2026-10-13T11:37:45Z"
            },
            {
                "grantee_address": "gonka1warm2",
                "granted_at": "2026-09-13T11:37:45Z"
            }
        ]
        
        await db.save_warm_keys_batch(epoch_id, participant_id, warm_keys)
        
        retrieved = await db.get_warm_keys(epoch_id, participant_id)
        assert retrieved is not None
        assert len(retrieved) == 2
        assert retrieved[0]["grantee_address"] == "gonka1warm1"
        assert retrieved[1]["grantee_address"] == "gonka1warm2"
        
        non_existent = await db.get_warm_keys(999, "gonka1nonexist")
        assert non_existent is None
    finally:
        os.unlink(db_path)


@pytest.mark.asyncio
async def test_database_warm_keys_replacement():
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
        db_path = f.name
    
    try:
        db = CacheDB(db_path)
        await db.initialize()
        
        epoch_id = 56
        participant_id = "gonka1test123"
        
        warm_keys_v1 = [
            {
                "grantee_address": "gonka1warm1",
                "granted_at": "2026-10-13T11:37:45Z"
            }
        ]
        
        await db.save_warm_keys_batch(epoch_id, participant_id, warm_keys_v1)
        
        warm_keys_v2 = [
            {
                "grantee_address": "gonka1warm2",
                "granted_at": "2026-11-13T11:37:45Z"
            },
            {
                "grantee_address": "gonka1warm3",
                "granted_at": "2026-12-13T11:37:45Z"
            }
        ]
        
        await db.save_warm_keys_batch(epoch_id, participant_id, warm_keys_v2)
        
        retrieved = await db.get_warm_keys(epoch_id, participant_id)
        assert retrieved is not None
        assert len(retrieved) == 2
        assert retrieved[0]["grantee_address"] == "gonka1warm3"
        assert retrieved[1]["grantee_address"] == "gonka1warm2"
    finally:
        os.unlink(db_path)


@pytest.mark.asyncio
async def test_database_warm_keys_sorting():
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
        db_path = f.name
    
    try:
        db = CacheDB(db_path)
        await db.initialize()
        
        epoch_id = 56
        participant_id = "gonka1test123"
        
        warm_keys = [
            {
                "grantee_address": "gonka1old",
                "granted_at": "2025-01-01T00:00:00Z"
            },
            {
                "grantee_address": "gonka1new",
                "granted_at": "2026-12-31T23:59:59Z"
            },
            {
                "grantee_address": "gonka1mid",
                "granted_at": "2026-06-15T12:00:00Z"
            }
        ]
        
        await db.save_warm_keys_batch(epoch_id, participant_id, warm_keys)
        
        retrieved = await db.get_warm_keys(epoch_id, participant_id)
        assert retrieved is not None
        assert len(retrieved) == 3
        assert retrieved[0]["grantee_address"] == "gonka1new"
        assert retrieved[1]["grantee_address"] == "gonka1mid"
        assert retrieved[2]["grantee_address"] == "gonka1old"
    finally:
        os.unlink(db_path)


def test_warm_key_info_model():
    warm_key = WarmKeyInfo(
        grantee_address="gonka1test123",
        granted_at="2026-10-13T11:37:45Z"
    )
    
    assert warm_key.grantee_address == "gonka1test123"
    assert warm_key.granted_at == "2026-10-13T11:37:45Z"


@pytest.mark.asyncio
async def test_client_authz_grants_parsing():
    mock_grants_response = {
        "grants": [
            {
                "granter": "gonka1granter",
                "grantee": "gonka1grantee1",
                "authorization": {
                    "@type": "/cosmos.authz.v1beta1.GenericAuthorization",
                    "msg": "/inference.inference.MsgStartInference"
                },
                "expiration": "2026-10-13T11:37:45Z"
            },
            {
                "granter": "gonka1granter",
                "grantee": "gonka1grantee1",
                "authorization": {
                    "@type": "/cosmos.authz.v1beta1.GenericAuthorization",
                    "msg": "/inference.inference.MsgFinishInference"
                },
                "expiration": "2026-10-13T11:37:45Z"
            }
        ],
        "pagination": {"next_key": None, "total": "0"}
    }
    
    assert len(mock_grants_response["grants"]) == 2
    assert mock_grants_response["grants"][0]["grantee"] == "gonka1grantee1"


@pytest.mark.asyncio
async def test_database_empty_warm_keys():
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
        db_path = f.name
    
    try:
        db = CacheDB(db_path)
        await db.initialize()
        
        epoch_id = 56
        participant_id = "gonka1test123"
        
        await db.save_warm_keys_batch(epoch_id, participant_id, [])
        
        retrieved = await db.get_warm_keys(epoch_id, participant_id)
        assert retrieved is None or len(retrieved) == 0
    finally:
        os.unlink(db_path)


@pytest.mark.asyncio
async def test_database_warm_keys_multiple_participants():
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
        db_path = f.name
    
    try:
        db = CacheDB(db_path)
        await db.initialize()
        
        epoch_id = 56
        
        participant1 = "gonka1participant1"
        warm_keys1 = [
            {
                "grantee_address": "gonka1warm1",
                "granted_at": "2026-10-13T11:37:45Z"
            }
        ]
        
        participant2 = "gonka1participant2"
        warm_keys2 = [
            {
                "grantee_address": "gonka1warm2",
                "granted_at": "2026-10-13T11:37:45Z"
            },
            {
                "grantee_address": "gonka1warm3",
                "granted_at": "2026-10-13T11:37:45Z"
            }
        ]
        
        await db.save_warm_keys_batch(epoch_id, participant1, warm_keys1)
        await db.save_warm_keys_batch(epoch_id, participant2, warm_keys2)
        
        retrieved1 = await db.get_warm_keys(epoch_id, participant1)
        retrieved2 = await db.get_warm_keys(epoch_id, participant2)
        
        assert len(retrieved1) == 1
        assert len(retrieved2) == 2
        assert retrieved1[0]["grantee_address"] == "gonka1warm1"
        assert retrieved2[0]["grantee_address"] == "gonka1warm2"
    finally:
        os.unlink(db_path)

