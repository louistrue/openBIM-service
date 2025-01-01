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
    
    # Test connection
    test_event = {
        'url': '/test',
        'environment': 'development',
        'test_id': 'startup-test'
    }
    
    print(f"Sending test event: {test_event}")
    posthog.capture(
        distinct_id='test-user',
        event='test-event',
        properties=test_event
    )
    posthog.flush()
    print("PostHog test event sent successfully")
    
except Exception as e:
    print(f"PostHog Error: {e}")
    logger.error(f"PostHog Error: {e}", exc_info=True)
    posthog = None

print("Analytics module initialization complete")

def capture_pageview(distinct_id: str, url: str, properties: dict = None, event_name: str = '$pageview'):
    """Capture an event"""
    if posthog is None:
        print("PostHog client is not initialized, skipping event capture")
        return
        
    try:
        props = {
            '$current_url': url,
            'distinct_id': distinct_id
        }
        
        if properties:
            props.update(properties)
            
        print(f"Capturing event {event_name}: {props}")
        posthog.capture(
            distinct_id=distinct_id,
            event=event_name,
            properties=props
        )
        posthog.flush()
        print(f"Event {event_name} sent")
        
    except Exception as e:
        print(f"Failed to capture event: {e}")
