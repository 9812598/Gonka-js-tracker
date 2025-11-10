import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from backend.client import GonkaClient


async def main():
    client = GonkaClient(base_urls=["http://node2.gonka.ai:8000"])
    
    output_dir = Path(__file__).parent.parent / "test_data"
    output_dir.mkdir(exist_ok=True)
    
    print("Fetching latest height...")
    try:
        height = await client.get_latest_height()
        print(f"Latest height: {height}")
        
        with open(output_dir / "latest_height.json", "w") as f:
            json.dump({"height": height, "source": "chain-rpc/status"}, f, indent=2)
    except Exception as e:
        print(f"Error fetching height: {e}")
        height = None
    
    print("\nFetching current epoch participants...")
    try:
        current_epoch = await client.get_current_epoch_participants()
        print(f"Found {len(current_epoch.get('active_participants', {}).get('participants', []))} active participants")
        print(f"Epoch ID: {current_epoch.get('active_participants', {}).get('epoch_id', 'N/A')}")
        
        with open(output_dir / "current_epoch_participants.json", "w") as f:
            json.dump(current_epoch, f, indent=2)
    except Exception as e:
        print(f"Error fetching current epoch: {e}")
        current_epoch = None
    
    if height:
        print(f"\nFetching all participants at height {height}...")
        try:
            all_participants = await client.get_all_participants(height=height)
            participant_count = len(all_participants.get("participant", []))
            print(f"Found {participant_count} total participants")
            
            with open(output_dir / f"all_participants_height_{height}.json", "w") as f:
                json.dump(all_participants, f, indent=2)
            
            if participant_count > 0:
                sample = all_participants["participant"][0]
                print("\nSample participant structure:")
                print(f"  Index: {sample.get('index', 'N/A')}")
                print(f"  Address: {sample.get('address', 'N/A')}")
                print(f"  Current epoch stats: {sample.get('current_epoch_stats', {})}")
        except Exception as e:
            print(f"Error fetching all participants: {e}")
    
    if current_epoch:
        print("\nTesting URL discovery...")
        try:
            discovered_urls = await client.discover_urls()
            print(f"Discovered {len(discovered_urls)} additional URLs")
            if discovered_urls:
                print(f"Sample: {discovered_urls[:3]}")
            
            with open(output_dir / "discovered_urls.json", "w") as f:
                json.dump({"urls": discovered_urls}, f, indent=2)
        except Exception as e:
            print(f"Error discovering URLs: {e}")
    
    print(f"\nAPI responses saved to: {output_dir}")


if __name__ == "__main__":
    asyncio.run(main())

