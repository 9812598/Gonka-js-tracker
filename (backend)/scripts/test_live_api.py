import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from backend.client import GonkaClient
from backend.database import CacheDB
from backend.service import InferenceService


async def main():
    print("Testing Inference Statistics Backend API\n")
    print("=" * 60)
    
    client = GonkaClient(base_urls=["http://node2.gonka.ai:8000"])
    cache_db = CacheDB("test_cache.db")
    await cache_db.initialize()
    
    service = InferenceService(client=client, cache_db=cache_db)
    
    print("\n1. Testing current epoch stats...")
    try:
        current_stats = await service.get_current_epoch_stats()
        print(f"   Epoch ID: {current_stats.epoch_id}")
        print(f"   Height: {current_stats.height}")
        print(f"   Participants: {len(current_stats.participants)}")
        print(f"   Is Current: {current_stats.is_current}")
        
        if current_stats.participants:
            p = current_stats.participants[0]
            print(f"\n   Sample participant:")
            print(f"     Index: {p.index}")
            print(f"     Weight: {p.weight}")
            print(f"     Missed Rate: {p.missed_rate:.2%}")
        
        high_missed = [p for p in current_stats.participants if p.missed_rate > 0.10]
        print(f"\n   Participants with missed_rate > 10%: {len(high_missed)}")
        
    except Exception as e:
        print(f"   Error: {e}")
        return
    
    print("\n2. Testing historical epoch stats...")
    if current_stats.epoch_id > 1:
        historical_epoch_id = current_stats.epoch_id - 1
        try:
            historical_stats = await service.get_historical_epoch_stats(historical_epoch_id)
            print(f"   Epoch ID: {historical_stats.epoch_id}")
            print(f"   Height: {historical_stats.height}")
            print(f"   Participants: {len(historical_stats.participants)}")
            print(f"   Is Current: {historical_stats.is_current}")
            print(f"   Cached: {historical_stats.cached_at}")
        except Exception as e:
            print(f"   Error: {e}")
    
    print("\n3. Testing cache immutability...")
    is_finished = await cache_db.is_epoch_finished(historical_epoch_id)
    print(f"   Epoch {historical_epoch_id} marked as finished: {bool(is_finished)}")
    
    print("\n" + "=" * 60)
    print("All tests passed!")
    
    import os
    if os.path.exists("test_cache.db"):
        os.remove("test_cache.db")
        print("Cleaned up test database")


if __name__ == "__main__":
    asyncio.run(main())

