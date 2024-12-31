from posthog import Posthog
from .config import settings
import logging
import datetime

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Set to DEBUG level for more info

# Initialize PostHog client
try:
    logger.debug(f"Initializing PostHog with host: {settings.POSTHOG_HOST}")
    posthog = Posthog(
        project_api_key=settings.POSTHOG_API_KEY,  # Use explicit parameter name
        host=settings.POSTHOG_HOST
    )
    
    # Send a test event with more context
    test_properties = {
        'environment': 'initialization',
        'status': 'connected',
        'timestamp': datetime.datetime.now().isoformat(),
        'host': settings.POSTHOG_HOST,
        'api_key_length': len(settings.POSTHOG_API_KEY) if settings.POSTHOG_API_KEY else 0
    }
    
    logger.debug(f"Sending test event with properties: {test_properties}")
    posthog.capture(
        'test-id',
        'test-event',
        test_properties
    )
    
    # Force flush the event
    posthog.flush()
    logger.info("PostHog initialized successfully and test event sent")
    
except Exception as e:
    logger.error(f"Failed to initialize PostHog: {e}", exc_info=True)  # Include full traceback
    posthog = None

def capture_event(distinct_id: str, event_name: str, properties: dict = None):
    """
    Safely capture an event with PostHog
    """
    if posthog is None:
        return
        
    try:
        props = properties or {}
        # Add more default properties
        props.update({
            'environment': 'production',
            '$process_person_profile': True,
            '$time': datetime.datetime.now().isoformat(),  # Add timestamp
            '$lib': 'posthog-python',
            '$lib_version': posthog.__version__  # Track library version
        })
        
        # Add batch support for better performance
        posthog.capture(
            distinct_id=distinct_id,
            event=event_name,
            properties=props,
            timestamp=datetime.datetime.now()
        )
    except Exception as e:
        logger.error(f"Failed to capture PostHog event: {e}")
        
# Add a flush method to ensure events are sent
def flush_events():
    """
    Manually flush events to PostHog
    """
    if posthog is not None:
        try:
            posthog.flush()
        except Exception as e:
            logger.error(f"Failed to flush PostHog events: {e}")

def capture_pageview(distinct_id: str, url: str, properties: dict = None):
    """
    Capture a pageview event
    """
    if posthog is None:
        logger.warning("PostHog client is not initialized, skipping pageview capture")
        return
        
    try:
        props = properties or {}
        props.update({
            '$current_url': url,
            'event_type': 'pageview',
            '$time': datetime.datetime.now().isoformat(),
            'host': settings.POSTHOG_HOST,
            'distinct_id': distinct_id  # Include the ID for debugging
        })
        
        logger.debug(f"Capturing pageview with properties: {props}")
        posthog.capture(
            distinct_id=distinct_id,
            event='$pageview',
            properties=props
        )
        posthog.flush()  # Force flush after each pageview
        logger.debug("Pageview captured and flushed")
        
    except Exception as e:
        logger.error(f"Failed to capture pageview: {e}", exc_info=True)