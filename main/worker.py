#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import json
import logging
import os
import signal
import sys
import time
import uuid
from datetime import datetime

import aio_pika
import socket
from dotenv import load_dotenv

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.config_class import get_config
from telegram.client_manager import TelegramClientManager
from telegram.task_handlers import (
    handle_send_message,
    handle_join_group,
    handle_leave_group,
    handle_add_contact,
    handle_check_account,
    handle_extract_members
)
from utils.logging_config import configure_logging
from utils.api_client import ApiClient

# Load environment variables
load_dotenv()

# Configure logging
logger = configure_logging(__name__)

class TelegramWorker:
    """
    Worker for processing Telegram tasks from RabbitMQ
    """
    def __init__(self):
        self.config = get_config()
        # Initialize with a temporary ID, will be updated after API registration
        self.worker_id = f"worker_{socket.gethostname()}_{uuid.uuid4().hex[:8]}"
        self.client_manager = TelegramClientManager(self.config.tdata_base_path)
        self.api_client = ApiClient(self.config.api_base_url)
        self.connection = None
        self.channel = None
        self.tasks_exchange = None
        self.results_exchange = None
        self.task_queue = None
        self.cancel_queue = None
        self.running = False
        self.heartbeat_task = None
        self.handlers = {
            "SEND_PRIVATE": handle_send_message,
            "SEND_GROUP": handle_send_message,
            "JOIN_GROUP": handle_join_group,
            "LEAVE_GROUP": handle_leave_group,
            "ADD_CONTACT": handle_add_contact,
            "CHECK_ACCOUNT": handle_check_account,
            "EXTRACT_MEMBERS": handle_extract_members
        }
        
    async def connect(self):
        """Connect to RabbitMQ"""
        logger.info(f"Connecting to RabbitMQ at {self.config.rabbitmq_url}")
        self.connection = await aio_pika.connect_robust(self.config.rabbitmq_url)
        self.channel = await self.connection.channel()
        
        # Declare exchanges
        self.tasks_exchange = await self.channel.declare_exchange(
            self.config.rabbitmq_task_exchange,
            aio_pika.ExchangeType.TOPIC,
            durable=True
        )
        
        self.results_exchange = await self.channel.declare_exchange(
            self.config.rabbitmq_result_exchange,
            aio_pika.ExchangeType.TOPIC,
            durable=True
        )
        
        # Declare task queue and bind to exchange
        self.task_queue = await self.channel.declare_queue(
            f"worker_{self.worker_id}_tasks",
            durable=True,
            auto_delete=True
        )
        
        # Bind queue to exchange with routing patterns for all task types
        for task_type in self.handlers.keys():
            await self.task_queue.bind(
                self.tasks_exchange,
                routing_key=f"task.{task_type}"
            )
        
        # Declare cancel queue and bind to exchange
        self.cancel_queue = await self.channel.declare_queue(
            f"worker_{self.worker_id}_cancels",
            durable=True,
            auto_delete=True
        )
        
        await self.cancel_queue.bind(
            self.tasks_exchange,
            routing_key="task.cancel"
        )
        
        logger.info("Connected to RabbitMQ")
        
    async def register_worker(self):
        """Register the worker with the API service"""
        try:
            # Using our API client to register the worker
            success, worker_id = await self.api_client.register_worker(
                max_tasks=self.config.max_concurrent_tasks,
                tags="telegram,python",
                version="1.0.0"
            )
            
            if success and worker_id:
                # Update the worker ID with the one assigned by the API
                self.worker_id = worker_id
                logger.info(f"Worker registered successfully with ID: {self.worker_id}")
                return True
            else:
                logger.error("Failed to register worker with API service")
                return False
                
        except Exception as e:
            logger.error(f"Failed to register worker: {e}")
            return False
            
    async def start_heartbeat(self):
        """Start sending periodic heartbeats to the API"""
        async def heartbeat_loop():
            while self.running:
                try:
                    success = await self.api_client.send_heartbeat(self.worker_id)
                    if not success:
                        logger.warning("Failed to send heartbeat")
                    await asyncio.sleep(self.config.heartbeat_interval)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in heartbeat loop: {e}")
                    await asyncio.sleep(self.config.heartbeat_interval)
                    
        self.heartbeat_task = asyncio.create_task(heartbeat_loop())
        logger.info("Started heartbeat loop")
            
    async def start_consuming(self):
        """Start consuming messages from RabbitMQ"""
        # Start consuming task messages
        await self.task_queue.consume(self.process_task)
        
        # Start consuming cancel messages
        await self.cancel_queue.consume(self.process_cancel)
        
        logger.info("Started consuming messages")
        
    async def process_task(self, message):
        """Process a task message"""
        async with message.process():
            try:
                body = message.body.decode()
                task_data = json.loads(body)
                
                task_id = task_data.get("task_id")
                task_type = task_data.get("task_type")
                account_id = task_data.get("account_id")
                params = task_data.get("params", {})
                worker_id = task_data.get("worker_id")
                
                logger.info(f"Received task: {task_id} of type {task_type}")
                
                # Check if this task is for this worker
                if worker_id != self.worker_id:
                    logger.warning(f"Task {task_id} was not assigned to this worker")
                    return
                
                # Update task status to processing
                await self.send_status_update(task_id, account_id, "processing")
                
                # Get the handler for this task type
                handler = self.handlers.get(task_type)
                if not handler:
                    error_msg = f"Unknown task type: {task_type}"
                    logger.error(error_msg)
                    await self.send_task_result(task_id, account_id, "failed", None, error_msg)
                    return
                
                # Get telegram client for this account
                client = await self.client_manager.get_client(account_id)
                if not client:
                    error_msg = f"Failed to get telegram client for account {account_id}"
                    logger.error(error_msg)
                    await self.send_task_result(task_id, account_id, "failed", None, error_msg)
                    return
                
                # Process the task
                try:
                    start_time = time.time()
                    result = await handler(client, params)
                    execution_time = time.time() - start_time
                    
                    # Send successful result
                    await self.send_task_result(
                        task_id, 
                        account_id, 
                        "completed", 
                        result, 
                        None,
                        execution_time
                    )
                    
                    logger.info(f"Task {task_id} completed successfully in {execution_time:.2f}s")
                except Exception as e:
                    logger.exception(f"Error processing task {task_id}: {e}")
                    await self.send_task_result(task_id, account_id, "failed", None, str(e))
                finally:
                    # Release the client
                    await self.client_manager.release_client(account_id)
                    
            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode message: {e}")
            except Exception as e:
                logger.exception(f"Error processing message: {e}")
                
    async def process_cancel(self, message):
        """Process a cancel message"""
        async with message.process():
            try:
                body = message.body.decode()
                cancel_data = json.loads(body)
                
                task_id = cancel_data.get("task_id")
                logger.info(f"Received cancel request for task: {task_id}")
                
                # TODO: Implement task cancellation logic
                # This would involve tracking active tasks and interrupting them
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode cancel message: {e}")
            except Exception as e:
                logger.exception(f"Error processing cancel message: {e}")
                
    async def send_status_update(self, task_id, account_id, status, progress=0, message=None):
        """Send a task status update to the results exchange"""
        try:
            status_update = {
                "task_id": task_id,
                "account_id": account_id,
                "worker_id": self.worker_id,
                "status": status,
                "progress": progress,
                "message": message,
                "updated_at": datetime.utcnow().isoformat()
            }
            
            await self.results_exchange.publish(
                aio_pika.Message(
                    body=json.dumps(status_update).encode(),
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT
                ),
                routing_key="task.status"
            )
            
        except Exception as e:
            logger.error(f"Failed to send status update for task {task_id}: {e}")
            
    async def send_task_result(self, task_id, account_id, status, result=None, error=None, execution_time=None):
        """Send the task result to the results exchange"""
        try:
            task_result = {
                "task_id": task_id,
                "account_id": account_id,
                "worker_id": self.worker_id,
                "status": status,
                "result": result or {},
                "error": error,
                "execution_time": int(execution_time * 1000) if execution_time else None,
                "completed_at": datetime.utcnow().isoformat()
            }
            
            await self.results_exchange.publish(
                aio_pika.Message(
                    body=json.dumps(task_result).encode(),
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT
                ),
                routing_key="task.result"
            )
            
        except Exception as e:
            logger.error(f"Failed to send result for task {task_id}: {e}")
            
    async def run(self):
        """Run the worker"""
        # Connect to RabbitMQ
        await self.connect()
        
        # Set the running flag
        self.running = True
        
        # Register worker with the API
        if not await self.register_worker():
            logger.error("Failed to register worker, exiting")
            self.running = False
            return
            
        # Start heartbeat loop
        await self.start_heartbeat()
        
        # Start consuming messages
        await self.start_consuming()
        
        # Keep the worker running
        stop_event = asyncio.Event()
        
        def signal_handler():
            logger.info("Received shutdown signal")
            stop_event.set()
            
        # Register signal handlers
        loop = asyncio.get_running_loop()
        for s in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(s, signal_handler)
            
        # Wait for stop event
        await stop_event.wait()
        
        # Shutdown
        await self.shutdown()
        
    async def shutdown(self):
        """Shutdown the worker"""
        logger.info("Shutting down worker")
        
        # Set running flag to false
        self.running = False
        
        # Cancel heartbeat task
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass
        
        # Close RabbitMQ connection
        if self.connection:
            await self.connection.close()
            
        # Close telegram clients
        await self.client_manager.close_all()
        
        # Close API client
        await self.api_client.close()
        
        logger.info("Worker shutdown complete")
        
async def main():
    """Main entry point"""
    worker = TelegramWorker()
    await worker.run()
    
if __name__ == "__main__":
    asyncio.run(main())
