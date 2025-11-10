import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from backend.client import GonkaClient


async def test_address_conversion():
    print("\n=== Address Conversion Test ===")
    
    test_addresses = [
        "gonka1qqyc9gsld2666kpunherra8rx2efwg4v8wafg3",
        "gonka14cu38xpsd8pz5zdkkzwf0jwtpc0vv309ake364",
        "gonka1sqwpuxk4fkfxk68lxvt74mnmwadq0k2uv2r5yt"
    ]
    
    for address in test_addresses:
        valoper = GonkaClient.convert_bech32_address(address, "gonkavaloper")
        print(f"  {address}")
        print(f"  -> {valoper}")
        print()


async def test_keybase_api():
    print("\n=== Keybase API Test ===")
    
    base_urls = [os.getenv("GONKA_API_URL", "http://node2.gonka.ai:8000")]
    client = GonkaClient(base_urls)
    
    test_identities = [
        "E23265A0E36FC128",
        "FBE25C30404E2123",
        "673C81B66A67ED67"
    ]
    
    for identity in test_identities:
        username, picture_url = await client.get_keybase_info(identity)
        print(f"  Identity: {identity}")
        print(f"  Username: {username or 'Not found'}")
        print(f"  Picture:  {picture_url or 'Not found'}")
        print()


async def test_validator_matching():
    print("\n=== Validator Matching Test ===")
    
    base_urls = [os.getenv("GONKA_API_URL", "http://node2.gonka.ai:8000")]
    client = GonkaClient(base_urls)
    
    print("  Fetching validators...")
    validators = await client.get_all_validators()
    validators_with_tokens = [v for v in validators if v.get("tokens") and int(v.get("tokens")) > 0]
    print(f"  Found {len(validators_with_tokens)} validators with tokens")
    
    print("\n  Fetching current epoch participants...")
    epoch_data = await client.get_current_epoch_participants()
    participants = epoch_data.get("active_participants", {}).get("participants", [])
    print(f"  Found {len(participants)} participants")
    
    validator_by_operator = {}
    for v in validators_with_tokens:
        operator_address = v.get("operator_address", "")
        if operator_address:
            validator_by_operator[operator_address] = v
    
    matched = 0
    mismatched_keys = 0
    
    print("\n  Matching participants to validators:")
    for participant in participants[:5]:
        participant_index = participant.get("index")
        participant_address = participant.get("address")
        participant_key = participant.get("validator_key")
        
        if not participant_address:
            continue
        
        valoper_address = GonkaClient.convert_bech32_address(participant_address, "gonkavaloper")
        validator = validator_by_operator.get(valoper_address)
        
        if validator:
            matched += 1
            consensus_pub = (
                (validator.get("consensus_pubkey") or {}).get("key")
                or (validator.get("consensus_pubkey") or {}).get("value")
                or ""
            )
            
            description = validator.get("description", {})
            moniker = description.get("moniker", "")
            identity = description.get("identity", "")
            website = description.get("website", "")
            
            key_match = "MATCH" if consensus_pub == participant_key else "MISMATCH"
            if key_match == "MISMATCH":
                mismatched_keys += 1
            
            print(f"\n    Participant: {participant_index[:20]}...")
            print(f"    Valoper:     {valoper_address[:25]}...")
            print(f"    Moniker:     {moniker or '-'}")
            print(f"    Identity:    {identity or '-'}")
            print(f"    Website:     {website or '-'}")
            print(f"    Key Match:   {key_match}")
    
    print(f"\n  Summary: {matched} matched out of {min(5, len(participants))} tested")
    if mismatched_keys > 0:
        print(f"  WARNING: {mismatched_keys} consensus key mismatches detected!")


async def test_description_extraction():
    print("\n=== Description Field Extraction Test ===")
    
    base_urls = [os.getenv("GONKA_API_URL", "http://node2.gonka.ai:8000")]
    client = GonkaClient(base_urls)
    
    validators = await client.get_all_validators()
    validators_with_tokens = [v for v in validators if v.get("tokens") and int(v.get("tokens")) > 0]
    
    print(f"  Extracting descriptions from {len(validators_with_tokens)} validators:")
    
    for validator in validators_with_tokens[:5]:
        description = validator.get("description", {})
        moniker = description.get("moniker", "").strip()
        identity = description.get("identity", "").strip()
        website = description.get("website", "").strip()
        
        if moniker and moniker.startswith("gonkavaloper"):
            filtered_moniker = ""
        else:
            filtered_moniker = moniker
        
        print(f"\n    Operator:        {validator.get('operator_address', '')[:30]}...")
        print(f"    Moniker:         {moniker or '-'}")
        print(f"    Filtered:        {filtered_moniker or '-'}")
        print(f"    Identity:        {identity or '-'}")
        print(f"    Website:         {website or '-'}")


async def test_integration():
    print("\n=== Integration Test ===")
    
    base_urls = [os.getenv("GONKA_API_URL", "http://node2.gonka.ai:8000")]
    client = GonkaClient(base_urls)
    
    print("  Running full pipeline...")
    
    validators = await client.get_all_validators()
    validators_with_tokens = [v for v in validators if v.get("tokens") and int(v.get("tokens")) > 0]
    
    epoch_data = await client.get_current_epoch_participants()
    participants = epoch_data.get("active_participants", {}).get("participants", [])
    
    validator_by_operator = {}
    for v in validators_with_tokens:
        operator_address = v.get("operator_address", "")
        if operator_address:
            validator_by_operator[operator_address] = v
    
    enriched_count = 0
    keybase_count = 0
    
    for participant in participants[:3]:
        participant_index = participant.get("index")
        participant_address = participant.get("address")
        participant_key = participant.get("validator_key")
        
        if not participant_address:
            continue
        
        valoper_address = GonkaClient.convert_bech32_address(participant_address, "gonkavaloper")
        validator = validator_by_operator.get(valoper_address)
        
        if not validator:
            continue
        
        consensus_pub = (
            (validator.get("consensus_pubkey") or {}).get("key")
            or (validator.get("consensus_pubkey") or {}).get("value")
            or ""
        )
        
        description = validator.get("description", {})
        moniker = description.get("moniker", "").strip()
        identity = description.get("identity", "").strip()
        website = description.get("website", "").strip()
        
        if moniker and moniker.startswith("gonkavaloper"):
            moniker = ""
        
        keybase_username = None
        keybase_picture_url = None
        if identity:
            keybase_username, keybase_picture_url = await client.get_keybase_info(identity)
            if keybase_username:
                keybase_count += 1
        
        enriched_count += 1
        
        print(f"\n    Participant: {participant_index[:25]}...")
        print(f"    Moniker:     {moniker or '-'}")
        print(f"    Identity:    {identity or '-'}")
        print(f"    Keybase:     {keybase_username or '-'}")
        print(f"    Picture:     {keybase_picture_url or '-'}")
        print(f"    Website:     {website or '-'}")
        print(f"    Key Match:   {'Yes' if consensus_pub == participant_key else 'No'}")
    
    print(f"\n  Successfully enriched {enriched_count} participants")
    print(f"  Found {keybase_count} Keybase profiles")


async def main():
    print("\n" + "="*60)
    print("Validator Info Pipeline Test")
    print("="*60)
    
    await test_address_conversion()
    await test_keybase_api()
    await test_validator_matching()
    await test_description_extraction()
    await test_integration()
    
    print("\n" + "="*60)
    print("Test Complete")
    print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())

