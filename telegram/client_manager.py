#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import logging
import asyncio
import json
from typing import Dict, Optional, Tuple
import aiohttp

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    PhoneNumberInvalidError,
    SessionPasswordNeededError,
    AuthKeyUnregisteredError,
    PhoneCodeInvalidError
)

# Configure logger
logger = logging.getLogger(__name__)

class TelegramClientManager:
    """
    Manages Telegram client instances for different accounts
    """
    def __init__(self, tdata_base_path: str):
        self.tdata_base_path = tdata_base_path
        self.clients: Dict[int, Tuple[TelegramClient, asyncio.Lock]] = {}
        self.api_id = int(os.getenv('TELEGRAM_API_ID', '0'))
        self.api_hash = os.getenv('TELEGRAM_API_HASH', '')
        
        if not self.api_id or not self.api_hash:
            logger.warning("TELEGRAM_API_ID or TELEGRAM_API_HASH not set")
            
    async def get_client(self, account_id: int) -> Optional[TelegramClient]:
        """
        Get or create a Telegram client for the given account ID
        
        Args:
            account_id: Telegram account ID
            
        Returns:
            TelegramClient instance or None if client creation fails
        """
        # Check if client already exists
        if account_id in self.clients:
            client, lock = self.clients[account_id]
            
            # Acquire the lock to ensure only one task uses the client at a time
            await lock.acquire()
            
            # Check if client is connected
            if not client.is_connected():
                try:
                    await client.connect()
                except Exception as e:
                    logger.error(f"Failed to reconnect client for account {account_id}: {e}")
                    lock.release()
                    return None
                    
            return client
            
        # Client doesn't exist, create a new one
        try:
            # Fetch account info from API
            account_info = await self._fetch_account_info(account_id)
            if not account_info:
                logger.error(f"Failed to fetch account info for account {account_id}")
                return None
                
            # Get tdata path
            tdata_path = account_info.get('tdata_path')
            if not tdata_path:
                logger.error(f"No tdata path found for account {account_id}")
                return None
                
            # Create full tdata path
            full_tdata_path = os.path.join(self.tdata_base_path, tdata_path)
            if not os.path.exists(full_tdata_path):
                logger.error(f"Tdata directory not found at {full_tdata_path}")
                return None
                
            # Create session name
            session_name = f"account_{account_id}"
            
            # Create client
            client = TelegramClient(
                session=os.path.join(full_tdata_path, session_name),
                api_id=self.api_id,
                api_hash=self.api_hash,
                device_model="TGManager",
                system_version="1.0",
                app_version="1.0",
                lang_code="en",
                system_lang_code="en"
            )
            
            # Connect to Telegram
            await client.connect()
            
            # Check if the client is authorized
            if not await client.is_user_authorized():
                logger.error(f"Client for account {account_id} is not authorized")
                await client.disconnect()
                return None
                
            # Create a lock for this client
            lock = asyncio.Lock()
            
            # Acquire the lock
            await lock.acquire()
            
            # Store the client and lock
            self.clients[account_id] = (client, lock)
            
            return client
            
        except Exception as e:
            logger.exception(f"Error creating client for account {account_id}: {e}")
            return None
            
    async def release_client(self, account_id: int) -> None:
        """
        Release a client after use
        
        Args:
            account_id: Telegram account ID
        """
        if account_id in self.clients:
            _, lock = self.clients[account_id]
            lock.release()
            
    async def close_client(self, account_id: int) -> None:
        """
        Close and remove a client
        
        Args:
            account_id: Telegram account ID
        """
        if account_id in self.clients:
            client, lock = self.clients[account_id]
            
            # Wait for lock to be available
            async with lock:
                # Disconnect client
                try:
                    await client.disconnect()
                except Exception as e:
                    logger.error(f"Error disconnecting client for account {account_id}: {e}")
                    
            # Remove client from dict
            del self.clients[account_id]
            
    async def close_all(self) -> None:
        """Close all clients"""
        account_ids = list(self.clients.keys())
        for account_id in account_ids:
            await self.close_client(account_id)
            
    async def _fetch_account_info(self, account_id: int) -> Optional[Dict]:
        """
        Fetch account information from the API
        
        Args:
            account_id: Telegram account ID
            
        Returns:
            Account info dict or None if fetch fails
        """
        # In a production system, this would make an API call to the Go backend
        # For now, we'll simulate this with a local lookup
        # TODO: Replace with actual API call
        
        try:
            # Placeholder for API call
            # In a real implementation, this would use aiohttp to make a request to the API
            # api_url = f"{API_BASE_URL}/api/v1/accounts/{account_id}"
            # async with aiohttp.ClientSession() as session:
            #     async with session.get(api_url) as response:
            #         if response.status == 200:
            #             return await response.json()
            
            # For demonstration, just return a mock account
            return {
                'id': account_id,
                'phone': f"+1234567890{account_id}",
                'tdata_path': f"account_{account_id}",
                'status': 'active'
            }
            
        except Exception as e:
            logger.exception(f"Error fetching account info for account {account_id}: {e}")
            return None
