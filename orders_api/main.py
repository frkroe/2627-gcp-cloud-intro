"""orders-api: HTTP entry point that accepts new orders and publishes them to Pub/Sub.

Runs on Cloud Run (PaaS): we only provide the code and a Dockerfile; Google runs,
scales and patches everything underneath.
"""
import datetime
import json
import logging
import os
import uuid

import google.auth
import requests
from fastapi import FastAPI
from google.cloud import pubsub_v1
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def get_project_id():
    """PROJECT_ID env var if set, otherwise the project of the active credentials."""
    project_id = os.getenv('PROJECT_ID')
    if not project_id:
        _, project_id = google.auth.default()
    return project_id


def get_region():
    """Region this instance runs in, read from the metadata server (Cloud Run only)."""
    try:
        response = requests.get(
            'http://metadata.google.internal/computeMetadata/v1/instance/region',
            headers={'Metadata-Flavor': 'Google'}, timeout=1)
        return response.text.rsplit('/', 1)[-1]
    except requests.RequestException:
        return 'local'


app = FastAPI(title='orders-api')
publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(get_project_id(), os.getenv('ORDERS_TOPIC', 'order-events'))
REGION = get_region()


class Order(BaseModel):
    customer_id: int = Field(gt=0, examples=[3])
    total_price: float = Field(gt=0, examples=[59.9])


@app.get('/')
def info():
    return {'service': 'orders-api', 'region': REGION,
            'revision': os.getenv('K_REVISION', 'local')}


@app.get('/health')
def health():
    return {'status': 'ok'}


@app.post('/orders', status_code=201)
def create_order(order: Order):
    message = {
        'order_id': uuid.uuid4().hex[:12],
        'customer_id': order.customer_id,
        'total_price': order.total_price,
        'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'source': 'orders-api',
    }
    publisher.publish(topic_path, json.dumps(message).encode('utf-8')).result()
    logging.info(f"Order {message['order_id']} published")
    return message
