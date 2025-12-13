# Fika Presence Manager

A Docker container manager that monitors player activity and starts/stops containers based on presence.

## Features

- Monitors fika-server logs for player login requests
- Starts `fika-headless` container when players start loading
- Stops container after specified inactivity period
- Async HTTP requests using aiohttp
- Docker SDK for container management
- Configurable via environment variables

## Quick Start

### Using Docker Compose

```yaml
version: '3.8'
services:
  presence_manager:
    build: .
    container_name: fika_presence_manager
    restart: unless-stopped
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - CONTAINER_NAME=fika-headless
      - FIKA_SERVER_CONTAINER=fika-server
      - SHUTDOWN_DELAY=300
      - LOG_LEVEL=INFO