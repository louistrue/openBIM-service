from posthog import Posthog
from .config import settings
import logging
import datetime

logger = logging.getLogger(__name__)

# Initialize PostHog client
try:
    posthog = Posthog(
        settings.POSTHOG_API_KEY,
        host=settings.POSTHOG_HOST
    )
    # Send a test event to verify the connection
    posthog.capture(
        'test-id',
        'test-event',
        {
            'environment': 'initialization',
            'status': 'connected'
        }
    )
    logger.info("PostHog initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize PostHog: {e}")
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
    props = properties or {}
    props.update({
        '$current_url': url,
        'event_type': 'pageview'
    })
    capture_event(distinct_id, '$pageview', props)