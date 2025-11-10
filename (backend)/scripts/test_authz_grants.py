import asyncio
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from backend.client import GonkaClient


REQUIRED_PERMISSIONS = [
    "MsgStartInference",
    "MsgFinishInference",
    "MsgClaimRewards",
    "MsgValidation",
    "MsgSubmitPocBatch",
    "MsgSubmitPocValidation",
    "MsgSubmitSeed",
    "MsgBridgeExchange",
    "MsgSubmitTrainingKvRecord",
    "MsgJoinTraining",
    "MsgJoinTrainingStatus",
    "MsgTrainingHeartbeat",
    "MsgSetBarrier",
    "MsgClaimTrainingTaskForAssignment",
    "MsgAssignTrainingTask",
    "MsgSubmitNewUnfundedParticipant",
    "MsgSubmitHardwareDiff",
    "MsgInvalidateInference",
    "MsgRevalidateInference",
    "MsgSubmitDealerPart",
    "MsgSubmitVerificationVector",
    "MsgRequestThresholdSignature",
    "MsgSubmitPartialSignature",
    "MsgSubmitGroupKeyValidationSignature",
]


async def fetch_authz_grants(client: GonkaClient, granter: str):
    grants = []
    offset = 0
    limit = 100
    
    while True:
        try:
            params = {
                "pagination.limit": str(limit),
                "pagination.offset": str(offset)
            }
            
            data = await client._make_request(
                f"/chain-api/cosmos/authz/v1beta1/grants/granter/{granter}",
                params=params
            )
            
            batch_grants = data.get("grants", [])
            if not batch_grants:
                break
            
            grants.extend(batch_grants)
            print(f"Fetched {len(batch_grants)} grants (offset={offset})")
            
            if len(batch_grants) < limit:
                break
            
            offset += limit
            
        except Exception as e:
            print(f"Error fetching grants at offset {offset}: {e}")
            break
    
    return grants, data


async def main():
    client = GonkaClient(base_urls=["http://node2.gonka.ai:8000"])
    
    print("Fetching current epoch participants...")
    epoch_data = await client.get_current_epoch_participants()
    participants = epoch_data.get("active_participants", {}).get("participants", [])
    
    if not participants:
        print("No participants found!")
        return
    
    test_participant = participants[0]["index"]
    print(f"\nTesting with participant: {test_participant}")
    
    print("\nFetching authz grants...")
    grants, full_response = await fetch_authz_grants(client, test_participant)
    
    output_dir = Path(__file__).parent.parent / "test_data"
    output_dir.mkdir(exist_ok=True)
    
    output_file = output_dir / f"authz_grants_{test_participant[-8:]}.json"
    with open(output_file, "w") as f:
        json.dump(full_response, f, indent=2)
    
    print(f"\nTotal grants found: {len(grants)}")
    print(f"Saved to: {output_file}")
    
    if grants:
        print("\nAnalyzing grants structure...")
        print(f"First grant keys: {list(grants[0].keys())}")
        
        print("\nGrant structure:")
        print(json.dumps(grants[0], indent=2))
        
        grantee_perms = {}
        for grant in grants:
            grantee = grant.get("grantee", "unknown")
            authorization = grant.get("authorization", {})
            msg_url = authorization.get("msg", "")
            
            if grantee not in grantee_perms:
                grantee_perms[grantee] = {
                    "permissions": set(),
                    "expiration": grant.get("expiration")
                }
            
            for msg_type in REQUIRED_PERMISSIONS:
                if msg_type in msg_url:
                    grantee_perms[grantee]["permissions"].add(msg_type)
        
        print("\n" + "="*80)
        print("WARM KEY ANALYSIS")
        print("="*80)
        
        for grantee, info in grantee_perms.items():
            perms = info["permissions"]
            has_all = len(perms) >= 24
            
            print(f"\nGrantee: {grantee}")
            print(f"Expiration: {info['expiration']}")
            print(f"Permissions: {len(perms)}/24")
            print(f"Is Warm Key: {has_all}")
            
            if not has_all:
                missing = set(REQUIRED_PERMISSIONS) - perms
                print(f"Missing: {missing}")
    else:
        print("\nNo grants found for this participant")
        print("Trying a few more participants...")
        
        for i in range(1, min(5, len(participants))):
            test_addr = participants[i]["index"]
            print(f"\nTrying: {test_addr}")
            grants, resp = await fetch_authz_grants(client, test_addr)
            
            if grants:
                print(f"Found {len(grants)} grants!")
                output_file = output_dir / f"authz_grants_{test_addr[-8:]}.json"
                with open(output_file, "w") as f:
                    json.dump(resp, f, indent=2)
                print(f"Saved to: {output_file}")
                break


if __name__ == "__main__":
    asyncio.run(main())

