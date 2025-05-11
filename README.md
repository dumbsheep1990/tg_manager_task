# TG Marketing System - Python Worker Component

## Overview

This is the Python Worker component of the TG Marketing System, responsible for executing Telegram operations via the Telethon library. The worker communicates with the Golang API backend through RabbitMQ, receiving tasks and sending back results.

## Features

- **Task Processing**: Handles various Telegram operations including sending messages, joining/leaving groups, adding contacts, etc.
- **Distributed Architecture**: Can be scaled horizontally to handle multiple tasks in parallel
- **RabbitMQ Integration**: Communicates with the Golang backend via message queues
- **Telegram Integration**: Uses Telethon to interact with Telegram's API

## Directory Structure

```
tg_manager_task/
├── config/               # Configuration settings
│   └── settings.py       # System configuration
├── telegram/             # Telegram operations
│   ├── client.py         # Telegram client wrapper
│   └── task_executor.py  # Task execution logic
├── utils/                # Utility modules
│   ├── api_client.py     # HTTP client for API communication
│   └── rabbitmq_client.py # RabbitMQ client
├── main.py               # Main entry point
└── requirements.txt      # Python dependencies
```

## Supported Task Types

1. **send_message**: Send a message to an individual or group
2. **join_group**: Join a Telegram group or channel
3. **leave_group**: Leave a Telegram group or channel
4. **add_contact**: Add a contact to the address book
5. **check_account**: Check account status/health
6. **extract_members**: Extract members from a group

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure environment variables or edit `config/settings.py`:
```bash
# Required Telegram API credentials
export TELEGRAM_API_ID=your_api_id
export TELEGRAM_API_HASH=your_api_hash

# RabbitMQ connection
export RABBITMQ_URL=amqp://guest:guest@localhost:5672/

# API connection
export API_BASE_URL=http://localhost:8080/api/v1
```

3. Run the worker:
```bash
python main.py
```

## Worker Registration Process

1. The worker registers with the API on startup
2. It receives a unique worker_id
3. It begins sending heartbeats to the API
4. It starts consuming tasks from RabbitMQ
5. Task results are sent back to the API via RabbitMQ

## Integration with Golang Backend

The worker integrates with the Golang backend through:

1. RabbitMQ for task distribution and result reporting
2. REST API calls for worker registration and heartbeats
3. Shared task status via task records in the database

## Deployment

The worker can be deployed using Docker for easy scaling:

```bash
# Build Docker image
docker build -t tg-worker .

# Run container
docker run -d --name tg-worker-1 \
  -e TELEGRAM_API_ID=your_api_id \
  -e TELEGRAM_API_HASH=your_api_hash \
  -e RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/ \
  -e API_BASE_URL=http://api:8080/api/v1 \
  tg-worker
```
