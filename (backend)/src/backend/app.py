import asyncio
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.router import router, set_inference_service
from backend.client import GonkaClient
from backend.database import CacheDB
from backend.service import InferenceService

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:     %(message)s'
)
logger = logging.getLogger(__name__)

POLL_CURRENT_EPOCH_INTERVAL = int(os.getenv("POLL_CURRENT_EPOCH_INTERVAL", "30"))
POLL_JAIL_STATUS_INTERVAL = int(os.getenv("POLL_JAIL_STATUS_INTERVAL", "120"))
POLL_NODE_HEALTH_INTERVAL = int(os.getenv("POLL_NODE_HEALTH_INTERVAL", "60"))
POLL_REWARDS_INTERVAL = int(os.getenv("POLL_REWARDS_INTERVAL", "60"))
POLL_WARM_KEYS_INTERVAL = int(os.getenv("POLL_WARM_KEYS_INTERVAL", "300"))
POLL_WARM_KEYS_BATCH_SIZE = int(os.getenv("POLL_WARM_KEYS_BATCH_SIZE", "10"))
POLL_HARDWARE_NODES_INTERVAL = int(os.getenv("POLL_HARDWARE_NODES_INTERVAL", "600"))
POLL_HARDWARE_NODES_BATCH_SIZE = int(os.getenv("POLL_HARDWARE_NODES_BATCH_SIZE", "10"))
POLL_EPOCH_TOTAL_REWARDS_INTERVAL = int(os.getenv("POLL_EPOCH_TOTAL_REWARDS_INTERVAL", "600"))
POLL_PARTICIPANT_INFERENCES_INTERVAL = int(os.getenv("POLL_PARTICIPANT_INFERENCES_INTERVAL", "1200"))
POLL_MODELS_API_INTERVAL = int(os.getenv("POLL_MODELS_API_INTERVAL", "300"))
POLL_TIMELINE_INTERVAL = int(os.getenv("POLL_TIMELINE_INTERVAL", "30"))

background_task = None
jail_polling_task = None
health_polling_task = None
rewards_polling_task = None
warm_keys_polling_task = None
hardware_nodes_polling_task = None
epoch_total_rewards_polling_task = None
participant_inferences_polling_task = None
models_api_polling_task = None
timeline_polling_task = None
inference_service_instance = None


async def poll_current_epoch():
    while True:
        try:
            if inference_service_instance:
                await inference_service_instance.get_current_epoch_stats(reload=True)
                logger.info("Background polling: fetched current epoch stats")
        except Exception as e:
            logger.error(f"Background polling error: {e}")
        
        await asyncio.sleep(POLL_CURRENT_EPOCH_INTERVAL)


async def poll_jail_status():
    await asyncio.sleep(10)
    
    while True:
        try:
            if inference_service_instance:
                epoch_data = await inference_service_instance.client.get_current_epoch_participants()
                epoch_id = epoch_data["active_participants"]["epoch_group_id"]
                height = await inference_service_instance.client.get_latest_height()
                active_participants = epoch_data["active_participants"]["participants"]
                
                await inference_service_instance.fetch_and_cache_jail_statuses(
                    epoch_id, height, active_participants
                )
                logger.info("Background polling: fetched jail statuses")
        except Exception as e:
            logger.error(f"Jail polling error: {e}")
        
        await asyncio.sleep(POLL_JAIL_STATUS_INTERVAL)


async def poll_node_health():
    await asyncio.sleep(5)
    
    while True:
        try:
            if inference_service_instance:
                epoch_data = await inference_service_instance.client.get_current_epoch_participants()
                active_participants = epoch_data["active_participants"]["participants"]
                
                await inference_service_instance.fetch_and_cache_node_health(active_participants)
                logger.info("Background polling: fetched node health")
        except Exception as e:
            logger.error(f"Node health polling error: {e}")
        
        await asyncio.sleep(POLL_NODE_HEALTH_INTERVAL)


async def poll_rewards():
    await asyncio.sleep(15)
    
    while True:
        try:
            if inference_service_instance:
                await inference_service_instance.poll_participant_rewards()
        except Exception as e:
            logger.error(f"Rewards polling error: {e}")
        
        await asyncio.sleep(POLL_REWARDS_INTERVAL)


async def poll_warm_keys():
    await asyncio.sleep(20)
    
    while True:
        try:
            if inference_service_instance:
                await inference_service_instance.poll_warm_keys(batch_size=POLL_WARM_KEYS_BATCH_SIZE)
        except Exception as e:
            logger.error(f"Warm keys polling error: {e}")
        
        await asyncio.sleep(POLL_WARM_KEYS_INTERVAL)


async def poll_hardware_nodes():
    await asyncio.sleep(25)
    
    while True:
        try:
            if inference_service_instance:
                await inference_service_instance.poll_hardware_nodes(batch_size=POLL_HARDWARE_NODES_BATCH_SIZE)
        except Exception as e:
            logger.error(f"Hardware nodes polling error: {e}")
        
        await asyncio.sleep(POLL_HARDWARE_NODES_INTERVAL)


async def poll_epoch_total_rewards():
    await asyncio.sleep(30)
    
    while True:
        try:
            if inference_service_instance:
                await inference_service_instance.poll_epoch_total_rewards()
        except Exception as e:
            logger.error(f"Epoch total rewards polling error: {e}")
        
        await asyncio.sleep(POLL_EPOCH_TOTAL_REWARDS_INTERVAL)


async def poll_participant_inferences():
    while True:
        try:
            if inference_service_instance:
                await inference_service_instance.poll_participant_inferences()
        except Exception as e:
            logger.error(f"Participant inferences polling error: {e}")
        
        await asyncio.sleep(POLL_PARTICIPANT_INFERENCES_INTERVAL)


async def poll_models_api():
    await asyncio.sleep(35)
    
    while True:
        try:
            if inference_service_instance:
                await inference_service_instance.poll_models_api_cache()
        except Exception as e:
            logger.error(f"Models API polling error: {e}")
        
        await asyncio.sleep(POLL_MODELS_API_INTERVAL)


async def poll_timeline():
    await asyncio.sleep(40)
    
    while True:
        try:
            if inference_service_instance:
                await inference_service_instance.get_timeline()
                logger.info("Background polling: fetched timeline data")
        except Exception as e:
            logger.error(f"Timeline polling error: {e}")
        
        await asyncio.sleep(POLL_TIMELINE_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global background_task, jail_polling_task, health_polling_task, rewards_polling_task, warm_keys_polling_task, hardware_nodes_polling_task, epoch_total_rewards_polling_task, participant_inferences_polling_task, models_api_polling_task, timeline_polling_task, inference_service_instance
    
    inference_urls = os.getenv("INFERENCE_URLS", "http://node2.gonka.ai:8000").split(",")
    inference_urls = [url.strip() for url in inference_urls]
    
    db_path = os.getenv("CACHE_DB_PATH", "cache.db")
    
    logger.info(f"Initializing with URLs: {inference_urls}")
    logger.info(f"Database path: {db_path}")
    logger.info(f"Polling intervals (s): epoch={POLL_CURRENT_EPOCH_INTERVAL}, jail={POLL_JAIL_STATUS_INTERVAL}, health={POLL_NODE_HEALTH_INTERVAL}, rewards={POLL_REWARDS_INTERVAL}")
    logger.info(f"Polling intervals (s): warm_keys={POLL_WARM_KEYS_INTERVAL}, hardware_nodes={POLL_HARDWARE_NODES_INTERVAL}, total_rewards={POLL_EPOCH_TOTAL_REWARDS_INTERVAL}, inferences={POLL_PARTICIPANT_INFERENCES_INTERVAL}, models_api={POLL_MODELS_API_INTERVAL}, timeline={POLL_TIMELINE_INTERVAL}")
    logger.info(f"Polling batch sizes: warm_keys={POLL_WARM_KEYS_BATCH_SIZE}, hardware_nodes={POLL_HARDWARE_NODES_BATCH_SIZE}")
    
    cache_db = CacheDB(db_path)
    await cache_db.initialize()
    
    client = GonkaClient(base_urls=inference_urls)
    inference_service_instance = InferenceService(client=client, cache_db=cache_db)
    
    set_inference_service(inference_service_instance)
    
    background_task = asyncio.create_task(poll_current_epoch())
    jail_polling_task = asyncio.create_task(poll_jail_status())
    health_polling_task = asyncio.create_task(poll_node_health())
    rewards_polling_task = asyncio.create_task(poll_rewards())
    warm_keys_polling_task = asyncio.create_task(poll_warm_keys())
    hardware_nodes_polling_task = asyncio.create_task(poll_hardware_nodes())
    epoch_total_rewards_polling_task = asyncio.create_task(poll_epoch_total_rewards())
    participant_inferences_polling_task = asyncio.create_task(poll_participant_inferences())
    models_api_polling_task = asyncio.create_task(poll_models_api())
    timeline_polling_task = asyncio.create_task(poll_timeline())
    logger.info("Background polling tasks started")
    
    yield
    
    if background_task:
        background_task.cancel()
        try:
            await background_task
        except asyncio.CancelledError:
            logger.info("Background polling task cancelled")
    
    if jail_polling_task:
        jail_polling_task.cancel()
        try:
            await jail_polling_task
        except asyncio.CancelledError:
            logger.info("Jail polling task cancelled")
    
    if health_polling_task:
        health_polling_task.cancel()
        try:
            await health_polling_task
        except asyncio.CancelledError:
            logger.info("Health polling task cancelled")
    
    if rewards_polling_task:
        rewards_polling_task.cancel()
        try:
            await rewards_polling_task
        except asyncio.CancelledError:
            logger.info("Rewards polling task cancelled")
    
    if warm_keys_polling_task:
        warm_keys_polling_task.cancel()
        try:
            await warm_keys_polling_task
        except asyncio.CancelledError:
            logger.info("Warm keys polling task cancelled")
    
    if hardware_nodes_polling_task:
        hardware_nodes_polling_task.cancel()
        try:
            await hardware_nodes_polling_task
        except asyncio.CancelledError:
            logger.info("Hardware nodes polling task cancelled")
    
    if epoch_total_rewards_polling_task:
        epoch_total_rewards_polling_task.cancel()
        try:
            await epoch_total_rewards_polling_task
        except asyncio.CancelledError:
            logger.info("Epoch total rewards polling task cancelled")
    
    if participant_inferences_polling_task:
        participant_inferences_polling_task.cancel()
        try:
            await participant_inferences_polling_task
        except asyncio.CancelledError:
            logger.info("Participant inferences polling task cancelled")
    
    if models_api_polling_task:
        models_api_polling_task.cancel()
        try:
            await models_api_polling_task
        except asyncio.CancelledError:
            logger.info("Models API polling task cancelled")
    
    if timeline_polling_task:
        timeline_polling_task.cancel()
        try:
            await timeline_polling_task
        except asyncio.CancelledError:
            logger.info("Timeline polling task cancelled")


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

