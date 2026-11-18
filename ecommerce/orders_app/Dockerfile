# Build from the ecommerce/ folder:
#   docker build -f orders_app/Dockerfile -t orders-app .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY utils ./utils
COPY orders_app ./orders_app

CMD ["python", "-m", "orders_app.orders_to_db.main"]
