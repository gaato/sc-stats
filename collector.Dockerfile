FROM python:3.12-slim

ENV TZ Asia/Tokyo

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends git cmake build-essential libffi-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app
RUN pip install --no-cache-dir -r requirements.txt

COPY src /app

CMD ["python", "collector.py"]
