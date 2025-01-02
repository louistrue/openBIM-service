from posthog import Posthog
from .config import settings
import logging
import sys

print("Loading analytics module...")

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    force=True,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Initialize PostHog client
try:
    posthog = Posthog(
        project_api_key=settings.POSTHOG_API_KEY,
        host=settings.POSTHOG_HOST,
        debug=True
    )
    
except Exception as e:
    print(f"PostHog Error: {e}")
    logger.error(f"PostHog Error: {e}", exc_info=True)
    posthog = None

print("Analytics module initialization complete")

def capture_event(distinct_id: str, event_name: str, properties: dict = None):
    """Capture any event with proper error handling and logging"""
    if posthog is None:
        logger.warning("PostHog client is not initialized, skipping event capture")
        return
        
    try:
        # Ensure properties is a dict
        props = properties or {}
        
        # Add distinct_id to properties as recommended
        props['distinct_id'] = distinct_id
        
        logger.debug(f"Capturing event {event_name}: {props}")
        
        # Capture the event
        posthog.capture(
            distinct_id=distinct_id,
            event=event_name,
            properties=props
        )
        
        # Ensure event is sent immediately in serverless environments
        posthog.flush()
        logger.info(f"Event {event_name} sent successfully")
        
    except Exception as e:
        logger.error(f"Failed to capture event {event_name}: {e}", exc_info=True)

def capture_pageview(distinct_id: str, url: str, properties: dict = None):
    """Capture a pageview event - wrapper around capture_event"""
    props = {
        '$current_url': url,
    }
    if properties:
        props.update(properties)
        
    capture_event(distinct_id, '$pageview', props)
