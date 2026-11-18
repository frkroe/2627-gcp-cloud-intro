# Build from the ecommerce/ folder:
#   docker build -f delivery_app/Dockerfile -t delivery-app .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY utils ./utils
COPY delivery_app ./delivery_app

CMD ["python", "-m", "delivery_app.main"]
