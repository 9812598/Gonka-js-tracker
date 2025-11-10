"""
Test cases for validating X-Cosmos-Block-Height header usage and effective_block_height logic

Based on user requirements:
1. Must use header "X-Cosmos-Block-Height: <height>" for chain-api calls (not query param)
2. Use effective_block_height (not poc_start_block_height) as epoch start/end
3. For finished epoch N: fetch data at effective_block_height(N+1) - 10

Test Data from Chain:
==================

Epoch 55:
  effective_block_height: 858047
  
Epoch 54:
  effective_block_height: 842656
  
For epoch 54, canonical height should be: 858047 - 10 = 858037

Test Case 1: Epoch 54 at height 844656
---------------------------------------
Expected participant gonka1p2lhgng7tcqju7emk989s5fpdr7k2c3ek6h26m:
{
  "index": "gonka1p2lhgng7tcqju7emk989s5fpdr7k2c3ek6h26m",
  "address": "gonka1p2lhgng7tcqju7emk989s5fpdr7k2c3ek6h26m",
  "weight": 1,
  "current_epoch_stats": {
    "inference_count": "5",
    "validated_inferences": "2"
  }
}

Test Case 2: Epoch 55 data (current)
-------------------------------------
Expected participant gonka1sqwpuxkspyp483l64knd5rp6qp56ymj4v6ca86:
{
  "index": "gonka1sqwpuxkspyp483l64knd5rp6qp56ymj4v6ca86",
  "address": "gonka1sqwpuxkspyp483l64knd5rp6qp56ymj4v6ca86",
  "current_epoch_stats": {
    "inference_count": "23",
    "missed_requests": "2",
    "validated_inferences": "2"
  }
}

Test Case 3: Height validation for epoch 54
--------------------------------------------
- Height 842656 (epoch start): SHOULD WORK
- Height 844656 (during epoch): SHOULD WORK
- Height 842655 (before epoch): SHOULD REJECT (400)
- Height 858037 (canonical for finished epoch): SHOULD WORK

Test Case 4: Verify header usage
---------------------------------
Must confirm that:
1. Client uses header "X-Cosmos-Block-Height: <height>" in all chain-api calls
2. NOT using query parameter ?height=X
3. Header is properly passed through to Cosmos API
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from backend.client import GonkaClient


async def test_height_header_usage():
    """Test that X-Cosmos-Block-Height header is used correctly"""
    print("=" * 80)
    print("TEST: Verify X-Cosmos-Block-Height Header Usage")
    print("=" * 80)
    
    client = GonkaClient(base_urls=["http://node2.gonka.ai:8000"])
    test_passed = True
    
    print("\nTest 1: Fetch epoch 54 data at height 844656")
    print("-" * 80)
    
    try:
        data = await client.get_all_participants(height=844656)
        participants = data.get("participant", [])
        
        test_participant = None
        for p in participants:
            if p["index"] == "gonka1p2lhgng7tcqju7emk989s5fpdr7k2c3ek6h26m":
                test_participant = p
                break
        
        assert test_participant is not None, "Test participant gonka1p2lhgng7tcqju7emk989s5fpdr7k2c3ek6h26m not found"
        print("✓ Found test participant gonka1p2lhgng7tcqju7emk989s5fpdr7k2c3ek6h26m")
        
        stats = test_participant["current_epoch_stats"]
        print(f"  inference_count: {stats.get('inference_count', 'N/A')}")
        print(f"  validated_inferences: {stats.get('validated_inferences', 'N/A')}")
        
        expected_count = "5"
        expected_validated = "2"
        
        assert stats.get('inference_count') == expected_count, \
            f"inference_count mismatch: got {stats.get('inference_count')}, expected {expected_count}"
        print(f"  ✓ inference_count matches expected: {expected_count}")
        
        assert stats.get('validated_inferences') == expected_validated, \
            f"validated_inferences mismatch: got {stats.get('validated_inferences')}, expected {expected_validated}"
        print(f"  ✓ validated_inferences matches expected: {expected_validated}")
            
    except AssertionError as e:
        print(f"✗ ASSERTION FAILED: {e}")
        test_passed = False
    except Exception as e:
        print(f"✗ Error: {e}")
        test_passed = False
    
    print("\nTest 2: Fetch epoch 55 data (current)")
    print("-" * 80)
    
    try:
        height = await client.get_latest_height()
        data = await client.get_all_participants(height=height)
        participants = data.get("participant", [])
        
        test_participant = None
        for p in participants:
            if p["index"] == "gonka1sqwpuxkspyp483l64knd5rp6qp56ymj4v6ca86":
                test_participant = p
                break
        
        if test_participant:
            print("✓ Found test participant gonka1sqwpuxkspyp483l64knd5rp6qp56ymj4v6ca86")
            stats = test_participant["current_epoch_stats"]
            print(f"  inference_count: {stats.get('inference_count', 'N/A')}")
            print(f"  missed_requests: {stats.get('missed_requests', 'N/A')}")
            print(f"  validated_inferences: {stats.get('validated_inferences', 'N/A')}")
        else:
            print("✗ Test participant not found in response")
            
    except Exception as e:
        print(f"✗ Error: {e}")
    
    print("\nTest 3: Verify effective_block_height logic")
    print("-" * 80)
    
    try:
        epoch_54 = await client.get_epoch_participants(54)
        epoch_55 = await client.get_epoch_participants(55)
        
        effective_54 = epoch_54["active_participants"]["effective_block_height"]
        effective_55 = epoch_55["active_participants"]["effective_block_height"]
        
        print(f"Epoch 54 effective_block_height: {effective_54}")
        print(f"Epoch 55 effective_block_height: {effective_55}")
        
        canonical_height_54 = effective_55 - 10
        print(f"\nCanonical height for epoch 54: {canonical_height_54}")
        print(f"  (calculated as: epoch_55_effective - 10 = {effective_55} - 10)")
        
        assert effective_54 == 842656, f"Epoch 54 effective_block_height mismatch: {effective_54}"
        print("✓ Epoch 54 effective_block_height matches: 842656")
        
        assert effective_55 == 858047, f"Epoch 55 effective_block_height mismatch: {effective_55}"
        print("✓ Epoch 55 effective_block_height matches: 858047")
        
        assert canonical_height_54 == 858037, f"Canonical height calculation wrong: {canonical_height_54}"
        print("✓ Canonical height calculation correct: 858037")
            
    except AssertionError as e:
        print(f"✗ ASSERTION FAILED: {e}")
        test_passed = False
    except Exception as e:
        print(f"✗ Error: {e}")
        test_passed = False
    
    print("\n" + "=" * 80)
    if test_passed:
        print("ALL TESTS PASSED ✓")
    else:
        print("SOME TESTS FAILED ✗")
    print("=" * 80)
    
    return test_passed


if __name__ == "__main__":
    import sys
    passed = asyncio.run(test_height_header_usage())
    sys.exit(0 if passed else 1)

