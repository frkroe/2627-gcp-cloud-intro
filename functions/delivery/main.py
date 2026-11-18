"""delivery-function: the delivery-app logic as a function (FaaS).

Instead of a VM that pulls messages in a loop, Google runs this function once per
message published to the topic order-events, and adds instances when many arrive.
"""
import base64
import datetime
import json
import logging
import os
import random
import time

import functions_framework
import google.auth
from google.cloud import pubsub_v1

# force=True: the Functions Framework already configured logging; without it, INFO lines are dropped
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s', force=True)

def get_project_id():
    """PROJECT_ID env var if set, otherwise the project the function runs in."""
    project_id = os.getenv('PROJECT_ID')
    if not project_id:
        _, project_id = google.auth.default()
    return project_id


publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(get_project_id(), os.getenv('DELIVERY_TOPIC', 'delivery-events'))

# Same simulation as delivery_app: (status, seconds to wait after publishing it)
DELIVERY_STEPS = [('processing', (2, 4)), ('delivering', (5, 10)), ('delivered', None)]


def publish(order_id, status):
    event = {'delivery_status': status, 'order_id': order_id,
             'event_at': datetime.datetime.now().isoformat(), 'source': 'delivery-function'}
    publisher.publish(topic_path, json.dumps(event).encode('utf-8')).result()


@functions_framework.cloud_event
def handle_order(cloud_event):
    """Triggered by a Pub/Sub message on order-events (delivered as a CloudEvent)."""
    message = json.loads(base64.b64decode(cloud_event.data['message']['data']))
    if 'order_id' not in message:
        logging.warning(f'Invalid message format, skipping: {message}')
        return
    order_id = message['order_id']
    logging.info(f'Delivering order {order_id}')
    for status, wait in DELIVERY_STEPS:
        publish(order_id, status)
        if wait:
            time.sleep(random.randint(*wait))
    logging.info(f'Order {order_id} delivered')
