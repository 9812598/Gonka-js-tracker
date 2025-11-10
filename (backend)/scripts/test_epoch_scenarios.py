import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from backend.client import GonkaClient
from backend.database import CacheDB
from backend.service import InferenceService


async def test_last_50_epochs():
    print("=" * 80)
    print("Testing Last 50 Epochs Fetch")
    print("=" * 80)
    
    client = GonkaClient(base_urls=["http://node2.gonka.ai:8000"])
    cache_db = CacheDB("test_epochs.db")
    await cache_db.initialize()
    
    service = InferenceService(client=client, cache_db=cache_db)
    
    current_stats = await service.get_current_epoch_stats()
    current_epoch_id = current_stats.epoch_id
    print(f"\nCurrent Epoch: {current_epoch_id}")
    print(f"Current Height: {current_stats.height}")
    
    start_epoch = max(1, current_epoch_id - 50)
    print(f"\nTesting epochs from {start_epoch} to {current_epoch_id - 1}")
    
    successful = 0
    failed = []
    
    for epoch_id in range(start_epoch, current_epoch_id):
        try:
            stats = await service.get_historical_epoch_stats(epoch_id)
            print(f"  ✓ Epoch {epoch_id}: height={stats.height}, participants={len(stats.participants)}")
            successful += 1
        except Exception as e:
            print(f"  ✗ Epoch {epoch_id}: {str(e)[:80]}")
            failed.append((epoch_id, str(e)))
    
    print(f"\nResults: {successful} successful, {len(failed)} failed")
    
    import os
    if os.path.exists("test_epochs.db"):
        os.remove("test_epochs.db")
    
    return current_epoch_id, current_stats.height


async def test_different_heights(epoch_id, reference_height):
    print("\n" + "=" * 80)
    print(f"Testing Different Heights for Epoch {epoch_id}")
    print("=" * 80)
    
    client = GonkaClient(base_urls=["http://node2.gonka.ai:8000"])
    cache_db = CacheDB("test_heights.db")
    await cache_db.initialize()
    
    service = InferenceService(client=client, cache_db=cache_db)
    
    epoch_data = await client.get_epoch_participants(epoch_id)
    poc_start = epoch_data["active_participants"]["poc_start_block_height"]
    effective_height = epoch_data["active_participants"]["effective_block_height"]
    
    print(f"\nEpoch {epoch_id} info:")
    print(f"  PoC Start Height: {poc_start}")
    print(f"  Effective Height: {effective_height}")
    
    next_epoch_data = await client.get_epoch_participants(epoch_id + 1)
    next_poc_start = next_epoch_data["active_participants"]["poc_start_block_height"]
    print(f"  Next PoC Start: {next_poc_start}")
    
    test_heights = [
        effective_height,
        effective_height + 1000,
        effective_height + 5000,
        next_poc_start - 100,
        next_poc_start - 20,
        next_poc_start - 10,
    ]
    
    print(f"\nTesting different heights:")
    for height in test_heights:
        try:
            stats = await service.get_historical_epoch_stats(epoch_id, height=height)
            sample_participant = stats.participants[0] if stats.participants else None
            if sample_participant:
                print(f"  ✓ Height {height}: {len(stats.participants)} participants, "
                      f"sample missed_rate={sample_participant.missed_rate:.4f}")
            else:
                print(f"  ✓ Height {height}: {len(stats.participants)} participants")
        except Exception as e:
            print(f"  ✗ Height {height}: {str(e)[:80]}")
    
    import os
    if os.path.exists("test_heights.db"):
        os.remove("test_heights.db")


async def test_edge_cases(epoch_id):
    print("\n" + "=" * 80)
    print(f"Testing Edge Cases for Epoch {epoch_id}")
    print("=" * 80)
    
    client = GonkaClient(base_urls=["http://node2.gonka.ai:8000"])
    cache_db = CacheDB("test_edge_cases.db")
    await cache_db.initialize()
    
    service = InferenceService(client=client, cache_db=cache_db)
    
    epoch_data = await client.get_epoch_participants(epoch_id)
    poc_start = epoch_data["active_participants"]["poc_start_block_height"]
    effective_height = epoch_data["active_participants"]["effective_block_height"]
    
    next_epoch_data = await client.get_epoch_participants(epoch_id + 1)
    next_poc_start = next_epoch_data["active_participants"]["poc_start_block_height"]
    
    print(f"\nEpoch {epoch_id} boundaries:")
    print(f"  Effective Height: {effective_height}")
    print(f"  PoC Start: {poc_start}")
    print(f"  Next PoC Start: {next_poc_start}")
    
    print("\n1. Testing height BEFORE epoch start (should REJECT):")
    before_start = effective_height - 1000
    try:
        stats = await service.get_historical_epoch_stats(epoch_id, height=before_start)
        print(f"  ✗ Height {before_start} (before epoch): Should have been rejected but got {len(stats.participants)} participants")
    except ValueError as e:
        print(f"  ✓ Height {before_start} (before epoch): Correctly rejected")
        print(f"    Error: {str(e)[:100]}...")
    except Exception as e:
        print(f"  ✗ Height {before_start} (before epoch): Wrong error type: {str(e)[:80]}")
    
    print("\n2. Testing height AT epoch start (effective_height):")
    try:
        stats = await service.get_historical_epoch_stats(epoch_id, height=effective_height)
        print(f"  ✓ Height {effective_height} (epoch start): Got {len(stats.participants)} participants")
    except Exception as e:
        print(f"  ✗ Height {effective_height} (epoch start): {str(e)}")
    
    print("\n3. Testing height DURING epoch:")
    mid_height = effective_height + 1000
    try:
        stats = await service.get_historical_epoch_stats(epoch_id, height=mid_height)
        print(f"  ✓ Height {mid_height} (during epoch): Got {len(stats.participants)} participants")
    except Exception as e:
        print(f"  ✗ Height {mid_height} (during epoch): {str(e)}")
    
    print("\n4. Testing height AFTER epoch end (next PoC - 10):")
    after_end = next_poc_start - 10
    try:
        stats = await service.get_historical_epoch_stats(epoch_id, height=after_end)
        print(f"  ✓ Height {after_end} (after epoch end, next PoC-10): Got {len(stats.participants)} participants")
        print(f"    NOTE: Data exists because epoch was still active at this height")
    except Exception as e:
        print(f"  ✗ Height {after_end} (after epoch): {str(e)}")
    
    print("\n5. Comparing stats at different heights (should differ):")
    try:
        stats_start = await service.get_historical_epoch_stats(epoch_id, height=effective_height + 10)
        stats_end = await service.get_historical_epoch_stats(epoch_id, height=next_poc_start - 20)
        
        if stats_start.participants and stats_end.participants:
            p_start = stats_start.participants[0]
            p_end = stats_end.participants[0]
            
            start_count = int(p_start.current_epoch_stats.inference_count)
            end_count = int(p_end.current_epoch_stats.inference_count)
            
            print(f"  Sample participant at epoch start+10:")
            print(f"    Inferences: {start_count}, Missed: {p_start.current_epoch_stats.missed_requests}")
            print(f"  Sample participant at epoch end-20:")
            print(f"    Inferences: {end_count}, Missed: {p_end.current_epoch_stats.missed_requests}")
            
            if start_count != end_count:
                print(f"  ✓ Stats differ as expected (start: {start_count}, end: {end_count})")
            else:
                print(f"  ℹ Stats are same (might be low activity epoch)")
    except Exception as e:
        print(f"  ✗ Comparison failed: {str(e)}")
    
    import os
    if os.path.exists("test_edge_cases.db"):
        os.remove("test_edge_cases.db")


async def main():
    print("\n" + "=" * 80)
    print("COMPREHENSIVE EPOCH AND HEIGHT TESTING")
    print("=" * 80)
    
    current_epoch_id, current_height = await test_last_50_epochs()
    
    test_epoch = current_epoch_id - 1
    print(f"\nUsing epoch {test_epoch} for detailed testing")
    
    await test_different_heights(test_epoch, current_height)
    
    await test_edge_cases(test_epoch)
    
    print("\n" + "=" * 80)
    print("ALL TESTS COMPLETED")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())

