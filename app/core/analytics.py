from posthog import Posthog
from .config import settings
import logging

logger = logging.getLogger(__name__)

# Initialize PostHog client
try:
    posthog = Posthog(
        settings.POSTHOG_API_KEY,
        host=settings.POSTHOG_HOST
    )
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
        posthog.capture(
            distinct_id=distinct_id,
            event=event_name,
            properties=properties or {}
        )
    except Exception as e:
        logger.error(f"Failed to capture PostHog event: {e}")

def capture_pageview(distinct_id: str, url: str, properties: dict = None):
    """
    Capture a pageview event
    """
    props = properties or {}
    props.update({'$current_url': url})
    capture_event(distinct_id, '$pageview', props)