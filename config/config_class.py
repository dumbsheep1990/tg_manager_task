#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""TG营销系统任务工作器的配置类"""

from typing import NamedTuple, Optional

from .settings import (
    WORKER_SETTINGS, RABBITMQ, API, TELEGRAM, 
    TASK_SETTINGS, TDATA_DIR, LOGS_DIR
)


class Config(NamedTuple):
    """工作器配置"""
    # 工作器配置
    hostname: str
    max_concurrent_tasks: int
    tags: str
    version: str
    heartbeat_interval: int
    
    # RabbitMQ配置
    rabbitmq_url: str
    rabbitmq_task_exchange: str
    rabbitmq_result_exchange: str
    rabbitmq_system_exchange: str
    
    # API配置
    api_base_url: str
    api_token: Optional[str]
    
    # Telegram配置
    telegram_api_id: int
    telegram_api_hash: str
    telegram_session_timeout: int
    telegram_connection_retries: int
    telegram_retry_delay: int
    telegram_flood_sleep_threshold: int
    
    # 任务配置
    task_default_timeout: int
    task_max_retries: int
    task_retry_delay: int
    
    # 路径配置
    tdata_base_path: str
    logs_path: str


def get_config() -> Config:
    """获取配置"""
    return Config(
        # 工作器配置
        hostname=WORKER_SETTINGS['hostname'],
        max_concurrent_tasks=WORKER_SETTINGS['max_tasks'],
        tags=WORKER_SETTINGS['tags'],
        version=WORKER_SETTINGS['version'],
        heartbeat_interval=WORKER_SETTINGS['heartbeat_interval'],
        
        # RabbitMQ配置
        rabbitmq_url=RABBITMQ['url'],
        rabbitmq_task_exchange=RABBITMQ['exchanges']['tasks'],
        rabbitmq_result_exchange=RABBITMQ['exchanges']['results'],
        rabbitmq_system_exchange=RABBITMQ['exchanges']['system'],
        
        # API配置
        api_base_url=API['base_url'],
        api_token=API['token'],
        
        # Telegram配置
        telegram_api_id=TELEGRAM['api_id'],
        telegram_api_hash=TELEGRAM['api_hash'],
        telegram_session_timeout=TELEGRAM['session_timeout'],
        telegram_connection_retries=TELEGRAM['connection_retries'],
        telegram_retry_delay=TELEGRAM['retry_delay'],
        telegram_flood_sleep_threshold=TELEGRAM['flood_sleep_threshold'],
        
        # 任务配置
        task_default_timeout=TASK_SETTINGS['default_timeout'],
        task_max_retries=TASK_SETTINGS['max_retries'],
        task_retry_delay=TASK_SETTINGS['retry_delay'],
        
        # 路径配置
        tdata_base_path=TDATA_DIR,
        logs_path=LOGS_DIR
    )
