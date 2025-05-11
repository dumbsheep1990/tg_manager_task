#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
RabbitMQ client for communicating with the API
"""

import json
import logging
from typing import Dict, Any, Callable, Coroutine

import aio_pika

logger = logging.getLogger(__name__)


class RabbitMQClient:
    """Client for interacting with RabbitMQ"""
    
    def __init__(self, url: str, tasks_exchange: str, results_exchange: str):
        """
        Initialize the RabbitMQ client
        
        Args:
            url: RabbitMQ connection URL
            tasks_exchange: Exchange name for tasks
            results_exchange: Exchange name for results
        """
        self.url = url
        self.tasks_exchange_name = tasks_exchange
        self.results_exchange_name = results_exchange
        self.connection = None
        self.channel = None
        self.tasks_exchange = None
        self.results_exchange = None
    
    async def connect(self) -> None:
        """Connect to RabbitMQ and setup exchanges"""
        logger.info(f"Connecting to RabbitMQ at {self.url}")
        
        try:
            # Connect to RabbitMQ
            self.connection = await aio_pika.connect_robust(self.url)
            self.channel = await self.connection.channel()
            
            # Declare exchanges
            self.tasks_exchange = await self.channel.declare_exchange(
                self.tasks_exchange_name,
                aio_pika.ExchangeType.TOPIC,
                durable=True
            )
            
            self.results_exchange = await self.channel.declare_exchange(
                self.results_exchange_name,
                aio_pika.ExchangeType.TOPIC,
                durable=True
            )
            
            logger.info("Connected to RabbitMQ successfully")
        
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {str(e)}")
            raise
    
    async def publish_result(self, routing_key: str, result: Dict[str, Any]) -> None:
        """
        Publish task result to the results exchange
        
        Args:
            routing_key: Routing key for the message
            result: Result data to publish
        """
        if not self.results_exchange:
            await self.connect()
        
        try:
            # Convert result to JSON
            message_body = json.dumps(result).encode('utf-8')
            
            # Create message
            message = aio_pika.Message(
                body=message_body,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT
            )
            
            # Publish message
            await self.results_exchange.publish(
                message,
                routing_key=routing_key
            )
            
            logger.debug(f"Published result with routing key {routing_key}")
        
        except Exception as e:
            logger.error(f"Failed to publish result: {str(e)}")
            raise
    
    async def consume_tasks(self, queue_name: str, binding_key: str, 
                           callback: Callable[[bytes], Coroutine]) -> None:
        """
        Start consuming tasks from the tasks exchange
        
        Args:
            queue_name: Queue name to consume from
            binding_key: Binding key for the queue
            callback: Async callback function to process messages
        """
        if not self.tasks_exchange:
            await self.connect()
        
        try:
            # Declare queue
            queue = await self.channel.declare_queue(
                queue_name,
                durable=True
            )
            
            # Bind queue to exchange
            await queue.bind(
                exchange=self.tasks_exchange,
                routing_key=binding_key
            )
            
            # Start consuming
            await queue.consume(self._create_consumer_callback(callback))
            
            logger.info(f"Started consuming tasks from queue {queue_name} with binding {binding_key}")
        
        except Exception as e:
            logger.error(f"Failed to setup consumer: {str(e)}")
            raise
    
    def _create_consumer_callback(self, callback: Callable[[bytes], Coroutine]):
        """
        Create a message consumer callback function
        
        Args:
            callback: User callback function to process message body
            
        Returns:
            Consumer callback function
        """
        async def consumer_callback(message: aio_pika.IncomingMessage):
            async with message.process():
                try:
                    # Process message
                    logger.debug(f"Received message with routing key {message.routing_key}")
                    await callback(message.body)
                except Exception as e:
                    logger.error(f"Error processing message: {str(e)}")
                    # Reject message
                    await message.reject(requeue=True)
        
        return consumer_callback
    
    async def close(self) -> None:
        """Close connection to RabbitMQ"""
        if self.connection:
            await self.connection.close()
            logger.info("Closed RabbitMQ connection")
