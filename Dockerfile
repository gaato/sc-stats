FROM python:3.12-alpine

ENV TZ Asia/Tokyo

WORKDIR /app

RUN apk update && apk add git

COPY ./requirements.txt /app
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app /app

CMD ["python", "main.py"]
