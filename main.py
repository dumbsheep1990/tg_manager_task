#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""TG 营销系统任务工作器的主入口点"""

import asyncio
import logging
import logging.config
import signal
import sys
import time
import traceback
from typing import Dict, Any

from config import settings
from telegram.client import TelegramClient
from telegram.task_executor import TaskExecutor
from utils.api_client import ApiClient
from utils.rabbitmq_client import RabbitMQClient

# 配置日志记录
logging.config.dictConfig(settings.LOGGING)
logger = logging.getLogger(__name__)

# 全局关闭标志
shutdown_requested = False


async def register_worker(api_client: ApiClient) -> str:
    """向API注册此工作器并返回工作器ID"""
    worker_data = {
        "hostname": settings.WORKER_SETTINGS['hostname'],
        "ip": "127.0.0.1",    # 在生产环境中这将被动态确定
        "max_tasks": settings.WORKER_SETTINGS['max_tasks'],
        "tags": settings.WORKER_SETTINGS['tags'],
        "version": settings.WORKER_SETTINGS['version']
    }
    
    try:
        response = await api_client.post('/workers/register', json=worker_data)
        worker_id = response.get('data')
        logger.info(f"Worker registered successfully with ID: {worker_id}")
        return worker_id
    except Exception as e:
        logger.error(f"Failed to register worker: {str(e)}")
        raise


async def heartbeat_loop(api_client: ApiClient, worker_id: str):
    """定期向API发送心跳信号"""
    while not shutdown_requested:
        try:
            await api_client.post('/workers/heartbeat', json={"worker_id": worker_id})
            logger.debug(f"Heartbeat sent for worker: {worker_id}")
        except Exception as e:
            logger.error(f"Failed to send heartbeat: {str(e)}")
        
        # 等待30秒后发送下一次心跳
        await asyncio.sleep(30)


async def handle_signal(sig):
    """处理系统信号以实现优雅关闭"""
    global shutdown_requested
    logger.info(f"Received signal {sig}, initiating shutdown...")
    shutdown_requested = True


async def main():
    """工作器的主入口点"""
    # 设置信号处理器
    for sig in (signal.SIGINT, signal.SIGTERM):
        asyncio.get_event_loop().add_signal_handler(
            sig, lambda s=sig: asyncio.create_task(handle_signal(s))
        )
    
    logger.info("Starting TG Manager Task Worker")
    
    # 初始化API客户端
    api_client = ApiClient(settings.API['base_url'], settings.API['token'])
    
    try:
        # 注册工作器
        worker_id = await register_worker(api_client)
        
        # 初始化RabbitMQ客户端
        rabbitmq_client = RabbitMQClient(
            settings.RABBITMQ['url'],
            settings.RABBITMQ['exchanges']['tasks'],
            settings.RABBITMQ['exchanges']['results'],
        )
        await rabbitmq_client.connect()
        
        # 初始化Telegram客户端
        telegram_client = TelegramClient(
            settings.TELEGRAM['api_id'],
            settings.TELEGRAM['api_hash']
        )
        
        # 初始化任务执行器
        task_executor = TaskExecutor(
            telegram_client=telegram_client,
            rabbitmq_client=rabbitmq_client,
            worker_id=worker_id
        )
        
        # 启动心跳循环
        heartbeat_task = asyncio.create_task(heartbeat_loop(api_client, worker_id))
        
        # 启动任务消费者
        await rabbitmq_client.consume_tasks(
            settings.RABBITMQ['queues']['tasks'],
            settings.RABBITMQ['routing_keys']['tasks'],
            task_executor.execute_task
        )
        
        # 等待直到请求关闭
        while not shutdown_requested:
            await asyncio.sleep(1)
        
        # 清理资源
        logger.info("Shutting down worker...")
        heartbeat_task.cancel()
        await rabbitmq_client.close()
        
    except Exception as e:
        logger.error(f"Worker failed: {str(e)}")
        traceback.print_exc()
        return 1
    
    logger.info("Worker shutdown complete")
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
