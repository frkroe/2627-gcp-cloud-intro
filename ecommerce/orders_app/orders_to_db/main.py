import datetime
import logging
import os
import random
import sys
import time

import psycopg2

from orders_app.chatgpt_orders.orders_handler import get_limited_products, get_limited_users,\
                                          create_order
from utils.events_manager import EventsManager


def wait_for_db(retries=30, delay=2):
    """The database container may still be starting: retry before giving up."""
    for attempt in range(1, retries + 1):
        try:
            psycopg2.connect(**DB_CONFIG).close()
            logging.info("Database is ready")
            return
        except psycopg2.OperationalError:
            logging.info(f"Database not ready yet ({attempt}/{retries}), retrying in {delay}s...")
            time.sleep(delay)
    logging.error("Database never became ready. Exiting.")
    sys.exit(1)


def insert_data(order):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO customers (id, customer_name, email) VALUES (%s, %s, %s) ON CONFLICT (email) DO NOTHING RETURNING id;",
            (order['user']['id'], order['user']['name'], order['user']['email'])
        )
        customer_id = cursor.fetchone()
        if not customer_id:
            cursor.execute("SELECT id FROM customers WHERE email = %s;", (order['user']['email'],))
            customer_id = cursor.fetchone()[0]
        else:
            customer_id = customer_id[0]
        cursor.execute(
            "INSERT INTO orders (customer_id, created_at, total_price) VALUES (%s, %s, %s) RETURNING id;",
            (customer_id, order['timestamp'], order['totalPrice'])
        )
        order_id = cursor.fetchone()[0]
        for product in order['products']:
            cursor.execute(
                "INSERT INTO products (id, product_name, price) VALUES (%s, %s, %s) ON CONFLICT (id) DO NOTHING;",
                (product['productId'], product['name'], product['price'])
            )
            cursor.execute(
                "INSERT INTO order_products (order_id, product_id, quantity, price) VALUES (%s, %s, %s, %s);",
                (order_id, product['productId'], product['quantity'], product['price'])
            )
        conn.commit()
        logging.info(f"Order {order_id} inserted successfully\n")
        return order_id
    except Exception as e:
        logging.error(f"Error inserting data: {e}")
        sys.exit(1)
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


if __name__ == "__main__":
    logging.basicConfig(
                        level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        handlers=[
                            logging.StreamHandler()
                        ]
    )
    logger = logging.getLogger()
    DB_CONFIG = {
        "dbname": os.getenv('DB_NAME', 'ecommerce'),
        "user": os.getenv('DB_USER', 'user'),
        "password": os.getenv('DB_PASSWORD', 'password'),
        "host": os.getenv('HOST_IP', 'localhost'),
        "port": int(os.getenv('DB_PORT', '5432')),
    }
    wait_for_db()
    num_orders_generated = 1
    logging.info("Fetching products and users...")
    products_with_details = get_limited_products(limit=20)
    users = get_limited_users(limit=10)
    if not products_with_details or not users:
        logging.info("No products or users available. Exiting.")
        sys.exit(1)
    producer = EventsManager(os.getenv('ORDERS_TOPIC', 'order-events'))
    producer.create_publisher()
    while True:
        user = random.choice(users)
        logging.info(f"Creating new order for customer {user}\n")
        order = create_order(user, products_with_details, num_orders_generated)
        logging.info("Inserting new order in DataBase\n")
        order_id = insert_data(order)
        message = {'order_id': order_id, 'created_at': datetime.datetime.now().isoformat()}
        producer.send_message(message)
        num_orders_generated += 1
        time.sleep(random.randint(5, 20))
