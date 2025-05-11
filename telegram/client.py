#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
使用Telethon与Telegram API交互的Telegram客户端模块
"""

import asyncio
import logging
import os
from typing import Dict, Any, List, Optional, Union

from telethon import TelegramClient as TelethonClient
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty, User, Chat, Channel

from config import settings

logger = logging.getLogger(__name__)


class TelegramClient:
    """包裹Telethon客户端以处理Telegram API操作的封装类"""
    
    def __init__(self, api_id: int, api_hash: str):
        """
        初始化Telegram客户端
        
        参数:
            api_id: Telegram API ID
            api_hash: Telegram API哈希值
        """
        self.api_id = api_id
        self.api_hash = api_hash
        self.clients = {}  # Dictionary to store multiple client sessions
    
    async def get_client(self, phone: str, tdata_path: Optional[str] = None) -> TelethonClient:
        """
        获取或创建指定电话号码的Telethon客户端
        
        参数:
            phone: 账号的电话号码
            tdata_path: tdata目录的路径（可选）
            
        返回:
            Telethon客户端实例
        """
        if phone in self.clients and not self.clients[phone].is_connected():
            await self.clients[phone].disconnect()
            del self.clients[phone]
        
        if phone not in self.clients:
            # Create new session
            if tdata_path and os.path.exists(tdata_path):
                # Use tdata if available
                session = tdata_path
            else:
                # Otherwise use string session
                session = f"session_{phone}"
            
            client = TelethonClient(
                session=session,
                api_id=self.api_id,
                api_hash=self.api_hash,
                device_model="TG Marketing System",
                system_version="1.0",
                app_version="1.0.0",
                timeout=settings.TELEGRAM['session_timeout'],
                connection_retries=settings.TELEGRAM['connection_retries'],
                retry_delay=settings.TELEGRAM['retry_delay'],
                flood_sleep_threshold=settings.TELEGRAM['flood_sleep_threshold']
            )
            
            # Connect to Telegram
            await client.connect()
            self.clients[phone] = client
        
        return self.clients[phone]
    
    async def login(self, phone: str, code: str = None, password: str = None) -> Dict[str, Any]:
        """
        使用给定的电话号码登录Telegram
        
        参数:
            phone: 账号的电话号码
            code: 验证码（可选）
            password: 二次验证密码（可选）
            
        返回:
            包含登录状态和用户信息的字典
        """
        client = await self.get_client(phone)
        
        try:
            if not await client.is_user_authorized():
                # Request verification code if not already done
                if not code:
                    await client.send_code_request(phone)
                    return {
                        "success": False,
                        "requires_code": True,
                        "message": "Verification code sent to phone"
                    }
                
                # Try to sign in with code
                try:
                    await client.sign_in(phone, code)
                except SessionPasswordNeededError:
                    if not password:
                        return {
                            "success": False,
                            "requires_password": True,
                            "message": "Two-factor authentication required"
                        }
                    
                    # Try to sign in with password
                    await client.sign_in(password=password)
                except PhoneCodeInvalidError:
                    return {
                        "success": False,
                        "message": "Invalid verification code"
                    }
            
            # Get account info
            me = await client.get_me()
            return {
                "success": True,
                "message": "Login successful",
                "user_info": {
                    "id": me.id,
                    "first_name": me.first_name,
                    "last_name": me.last_name,
                    "username": me.username,
                    "phone": me.phone
                }
            }
        except Exception as e:
            logger.error(f"Login failed for phone {phone}: {str(e)}")
            return {
                "success": False,
                "message": f"Login failed: {str(e)}"
            }
    
    async def send_message(self, phone: str, target: str, message: str, 
                          add_contact: bool = False) -> Dict[str, Any]:
        """
        向用户或群组发送消息
        
        参数:
            phone: 发送者的电话号码
            target: 要发送的目标用户名、电话或群组ID
            message: 消息文本
            add_contact: 是否先将目标添加为联系人
            
        返回:
            包含发送状态和消息信息的字典
        """
        try:
            client = await self.get_client(phone)
            
            if not await client.is_user_authorized():
                return {
                    "success": False,
                    "message": "Account not authorized"
                }
            
            # Add contact if requested
            if add_contact and target.startswith('+'):
                contact = await client.add_contact(
                    phone=target,
                    first_name=f"Contact {target}",
                    last_name=""
                )
                logger.info(f"Added contact: {target}")
            
            # Find the entity (user, chat, channel)
            entity = await client.get_entity(target)
            
            # Send the message
            sent_message = await client.send_message(entity, message)
            
            return {
                "success": True,
                "message": "Message sent successfully",
                "message_id": sent_message.id,
                "date": sent_message.date.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to send message from {phone} to {target}: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to send message: {str(e)}"
            }
    
    async def join_group(self, phone: str, group_link: str) -> Dict[str, Any]:
        """
        加入Telegram群组或频道
        
        参数:
            phone: 账号的电话号码
            group_link: 群组的邀请链接或用户名
            
        返回:
            包含加入状态的字典
        """
        try:
            client = await self.get_client(phone)
            
            if not await client.is_user_authorized():
                return {
                    "success": False,
                    "message": "Account not authorized"
                }
            
            # Join the group
            if group_link.startswith('https://t.me/'):
                # Handle invite links
                result = await client(group_link)
            else:
                # Handle usernames
                result = await client.join_chat(group_link)
            
            return {
                "success": True,
                "message": "Joined group successfully",
                "group_info": {
                    "id": getattr(result, 'id', 0),
                    "title": getattr(result, 'title', group_link),
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to join group {group_link} with account {phone}: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to join group: {str(e)}"
            }
    
    async def leave_group(self, phone: str, group_id: Union[int, str]) -> Dict[str, Any]:
        """
        退出Telegram群组或频道
        
        参数:
            phone: 账号的电话号码
            group_id: 群组的ID或用户名
            
        返回:
            包含退出状态的字典
        """
        try:
            client = await self.get_client(phone)
            
            if not await client.is_user_authorized():
                return {
                    "success": False,
                    "message": "Account not authorized"
                }
            
            # Leave the group
            entity = await client.get_entity(group_id)
            await client.delete_dialog(entity)
            
            return {
                "success": True,
                "message": "Left group successfully",
            }
            
        except Exception as e:
            logger.error(f"Failed to leave group {group_id} with account {phone}: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to leave group: {str(e)}"
            }
    
    async def check_account(self, phone: str) -> Dict[str, Any]:
        """
        检查Telegram账号的状态
        
        参数:
            phone: 账号的电话号码
            
        返回:
            包含账号状态的字典
        """
        try:
            client = await self.get_client(phone)
            
            # Try connecting
            if not client.is_connected():
                await client.connect()
            
            # Check if authorized
            is_authorized = await client.is_user_authorized()
            
            if not is_authorized:
                return {
                    "success": True,
                    "status": "unauthorized",
                    "message": "Account requires login"
                }
            
            # Get account info
            me = await client.get_me()
            
            # Get dialog count (chats & channels)
            dialogs_count = 0
            try:
                dialogs = await client(GetDialogsRequest(
                    offset_date=None,
                    offset_id=0,
                    offset_peer=InputPeerEmpty(),
                    limit=1,
                    hash=0
                ))
                dialogs_count = dialogs.count
            except Exception as e:
                logger.warning(f"Failed to get dialogs count: {str(e)}")
            
            return {
                "success": True,
                "status": "active",
                "message": "Account active",
                "account_info": {
                    "id": me.id,
                    "first_name": me.first_name,
                    "last_name": me.last_name,
                    "username": me.username,
                    "phone": me.phone,
                    "dialogs_count": dialogs_count
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to check account {phone}: {str(e)}")
            return {
                "success": False,
                "status": "error",
                "message": f"Failed to check account: {str(e)}"
            }
    
    async def close_all(self):
        """关闭所有客户端连接"""
        for phone, client in self.clients.items():
            if client.is_connected():
                await client.disconnect()
        self.clients = {}
