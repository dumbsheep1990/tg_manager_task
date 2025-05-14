#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""TG营销系统任务工作器的配置设置"""

import os
from pathlib import Path
import logging
from typing import Dict, Any, NamedTuple, Optional

# 基础目录
BASE_DIR = Path(__file__).resolve().parent.parent
TDATA_DIR = os.path.join(BASE_DIR, 'tdata')
LOGS_DIR = os.path.join(BASE_DIR, 'logs')

# 确保目录存在
os.makedirs(TDATA_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

# 工作器设置
WORKER_SETTINGS = {
    'hostname': os.environ.get('WORKER_HOSTNAME', 'default-worker'),
    'max_tasks': int(os.environ.get('WORKER_MAX_TASKS', 10)),
    'tags': os.environ.get('WORKER_TAGS', 'telegram,task'),
    'version': '1.0.0',
    'heartbeat_interval': int(os.environ.get('WORKER_HEARTBEAT_INTERVAL', 30)),  # 心跳间隔（秒）
}

# RabbitMQ设置
RABBITMQ = {
    'url': os.environ.get('RABBITMQ_URL', 'amqp://guest:guest@localhost:5672/'),
    'exchanges': {
        'tasks': os.environ.get('RABBITMQ_TASKS_EXCHANGE', 'telegram.tasks'),
        'results': os.environ.get('RABBITMQ_RESULTS_EXCHANGE', 'telegram.results'),
        'system': os.environ.get('RABBITMQ_SYSTEM_EXCHANGE', 'telegram.system'),
    },
    'queues': {
        'tasks': os.environ.get('RABBITMQ_TASKS_QUEUE', 'telegram.tasks.queue'),
        'results': os.environ.get('RABBITMQ_RESULTS_QUEUE', 'telegram.results.queue'),
        'system': os.environ.get('RABBITMQ_SYSTEM_QUEUE', 'telegram.system.queue'),
    },
    'routing_keys': {
        'tasks': 'task.#',
        'results': 'result.#',
        'system': 'system.#',
    },
}
# API设置
API = {
    'base_url': os.environ.get('API_BASE_URL', 'http://localhost:8080/api/v1'),
    'token': os.environ.get('API_TOKEN', ''),
}

# Telegram设置
TELEGRAM = {
    'api_id': int(os.environ.get('TELEGRAM_API_ID', 0)),
    'api_hash': os.environ.get('TELEGRAM_API_HASH', ''),
    'session_timeout': 30,  # 秒
    'connection_retries': 5,
    'retry_delay': 5,  # 秒
    'flood_sleep_threshold': 60,  # 秒
}

# 任务设置
TASK_SETTINGS = {
    'default_timeout': 300,  # 秒
    'max_retries': 3,
    'retry_delay': 5,  # 秒
}

# 日志配置
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '%(asctime)s [%(levelname)s] [%(name)s] %(message)s'
        },
    },
    'handlers': {
        'console': {
            'level': os.environ.get('LOG_LEVEL', 'INFO'),
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'level': os.environ.get('LOG_LEVEL', 'INFO'),
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'verbose',
            'filename': os.path.join(LOGS_DIR, 'worker.log'),
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
        },
    },
    'loggers': {
        '': {
            'handlers': ['console', 'file'],
            'level': os.environ.get('LOG_LEVEL', 'INFO'),
            'propagate': True,
        },
    },
}
