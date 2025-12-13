FROM python:3.14-alpine

WORKDIR /app

# Install system dependencies
RUN apk add --no-cache \
    curl \
    docker-cli \
    && pip install --no-cache-dir poetry

COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY app/ ./app/

CMD ["python", "-m", "app.main"]