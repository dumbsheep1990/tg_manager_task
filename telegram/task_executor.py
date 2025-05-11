#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""用于处理Telegram任务的任务执行器模块"""

import asyncio
import json
import logging
import time
from typing import Dict, Any

from telegram.client import TelegramClient
from utils.rabbitmq_client import RabbitMQClient

logger = logging.getLogger(__name__)


class TaskExecutor:
    """用于处理Telegram任务的任务执行器"""
    
    def __init__(self, telegram_client: TelegramClient, rabbitmq_client: RabbitMQClient, worker_id: str):
        """
        初始化任务执行器
        
        参数:
            telegram_client: Telegram客户端实例
            rabbitmq_client: RabbitMQ客户端实例
            worker_id: 工作节点ID
        """
        self.telegram_client = telegram_client
        self.rabbitmq_client = rabbitmq_client
        self.worker_id = worker_id
        self.task_handlers = {
            'send_message': self._handle_send_message,
            'join_group': self._handle_join_group,
            'leave_group': self._handle_leave_group,
            'add_contact': self._handle_add_contact,
            'check_account': self._handle_check_account,
            'extract_members': self._handle_extract_members,
        }
    
    async def execute_task(self, task_data: bytes) -> bool:
        """
        执行任务
        
        参数:
            task_data: 以字节形式表示的任务数据
            
        返回:
            表示成功或失败的布尔值
        """
        start_time = time.time()
        
        try:
            # 解析任务数据
            task = json.loads(task_data)
            task_id = task.get('task_id')
            task_type = task.get('task_type')
            account_id = task.get('account_id')
            params = task.get('params', {})
            
            logger.info(f"Executing task {task_id} of type {task_type} for account {account_id}")
            
            # 验证任务
            if not task_id or not task_type or not account_id:
                logger.error(f"Invalid task format: {task}")
                await self._send_result(task_id, False, {}, "Invalid task format")
                return False
            
            # 获取任务处理器
            handler = self.task_handlers.get(task_type)
            if not handler:
                logger.error(f"Unsupported task type: {task_type}")
                await self._send_result(task_id, False, {}, f"Unsupported task type: {task_type}")
                return False
            
            # 从参数中获取账号信息
            phone = params.get('phone')
            if not phone:
                logger.error(f"Missing phone number in task parameters: {params}")
                await self._send_result(task_id, False, {}, "Missing phone number in task parameters")
                return False
            
            # 执行任务处理器
            success, result, error_message = await handler(phone, params)
            
            # 发送结果
            await self._send_result(task_id, success, result, error_message)
            
            # 记录执行时间
            execution_time = time.time() - start_time
            logger.info(f"Task {task_id} executed in {execution_time:.2f} seconds with result: {success}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error executing task: {str(e)}")
            # 尝试提取task_id（如果可能）
            task_id = None
            try:
                task = json.loads(task_data)
                task_id = task.get('task_id')
            except:
                pass
                
            if task_id:
                await self._send_result(task_id, False, {}, f"Error executing task: {str(e)}")
            
            return False
    
    async def _send_result(self, task_id: str, success: bool, result: Dict[str, Any], error_message: str = None) -> None:
        """
        将任务执行结果发送到结果队列
        
        参数:
            task_id: 任务ID
            success: 表示成功或失败的布尔值
            result: 任务结果数据
            error_message: 错误信息（如果有）
        """
        result_data = {
            'task_id': task_id,
            'worker_id': self.worker_id,
            'success': success,
            'result': result,
            'error_message': error_message if error_message else '',
            'completed_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        }
        
        routing_key = f"result.{'success' if success else 'failure'}.{task_id}"
        await self.rabbitmq_client.publish_result(routing_key, result_data)
    
    async def _handle_send_message(self, phone: str, params: Dict[str, Any]) -> tuple:
        """
        处理发送消息任务
        
        参数:
            phone: 账号的电话号码
            params: 任务参数
            
        返回:
            包含（成功状态，结果，错误信息）的元组
        """
        target = params.get('target')
        message = params.get('message')
        add_contact = params.get('add_contact', False)
        
        if not target or not message:
            return False, {}, "Missing target or message in task parameters"
        
        result = await self.telegram_client.send_message(phone, target, message, add_contact)
        success = result.get('success', False)
        
        return success, result, result.get('message') if not success else None
    
    async def _handle_join_group(self, phone: str, params: Dict[str, Any]) -> tuple:
        """
        处理加入群组任务
        
        参数:
            phone: 账号的电话号码
            params: 任务参数
            
        返回:
            包含（成功状态，结果，错误信息）的元组
        """
        group_link = params.get('group_link')
        
        if not group_link:
            return False, {}, "Missing group_link in task parameters"
        
        result = await self.telegram_client.join_group(phone, group_link)
        success = result.get('success', False)
        
        return success, result, result.get('message') if not success else None
    
    async def _handle_leave_group(self, phone: str, params: Dict[str, Any]) -> tuple:
        """
        处理退出群组任务
        
        参数:
            phone: 账号的电话号码
            params: 任务参数
            
        返回:
            包含（成功状态，结果，错误信息）的元组
        """
        group_id = params.get('group_id')
        
        if not group_id:
            return False, {}, "Missing group_id in task parameters"
        
        result = await self.telegram_client.leave_group(phone, group_id)
        success = result.get('success', False)
        
        return success, result, result.get('message') if not success else None
    
    async def _handle_add_contact(self, phone: str, params: Dict[str, Any]) -> tuple:
        """
        处理添加联系人任务
        
        参数:
            phone: 账号的电话号码
            params: 任务参数
            
        返回:
            包含（成功状态，结果，错误信息）的元组
        """
        contact_phone = params.get('contact_phone')
        first_name = params.get('first_name', f"Contact {contact_phone}")
        last_name = params.get('last_name', "")
        
        if not contact_phone:
            return False, {}, "Missing contact_phone in task parameters"
        
        try:
            client = await self.telegram_client.get_client(phone)
            
            if not await client.is_user_authorized():
                return False, {}, "Account not authorized"
            
            contact = await client.add_contact(
                phone=contact_phone,
                first_name=first_name,
                last_name=last_name
            )
            
            return True, {
                "success": True,
                "message": "Contact added successfully",
                "contact_id": getattr(contact, 'id', 0)
            }, None
            
        except Exception as e:
            logger.error(f"Failed to add contact {contact_phone} with account {phone}: {str(e)}")
            return False, {}, f"Failed to add contact: {str(e)}"
    
    async def _handle_check_account(self, phone: str, params: Dict[str, Any]) -> tuple:
        """
        处理检查账号任务
        
        参数:
            phone: 账号的电话号码
            params: 任务参数
            
        返回:
            包含（成功状态，结果，错误信息）的元组
        """
        result = await self.telegram_client.check_account(phone)
        success = result.get('success', False)
        
        return success, result, result.get('message') if not success else None
    
    async def _handle_extract_members(self, phone: str, params: Dict[str, Any]) -> tuple:
        """
        处理提取群成员任务
        
        参数:
            phone: 账号的电话号码
            params: 任务参数
            
        返回:
            包含（成功状态，结果，错误信息）的元组
        """
        group_id = params.get('group_id')
        limit = params.get('limit', 100)
        
        if not group_id:
            return False, {}, "Missing group_id in task parameters"
        
        try:
            client = await self.telegram_client.get_client(phone)
            
            if not await client.is_user_authorized():
                return False, {}, "Account not authorized"
            
            # Get entity
            entity = await client.get_entity(group_id)
            
            # Get participants
            participants = await client.get_participants(entity, limit=limit)
            
            # Extract member information
            members = []
            for participant in participants:
                member_info = {
                    "id": participant.id,
                    "username": participant.username,
                    "first_name": participant.first_name,
                    "last_name": participant.last_name,
                    "phone": participant.phone,
                    "is_bot": participant.bot,
                }
                members.append(member_info)
            
            return True, {
                "success": True,
                "message": f"Extracted {len(members)} members from group",
                "group_id": group_id,
                "members": members
            }, None
            
        except Exception as e:
            logger.error(f"Failed to extract members from group {group_id}: {str(e)}")
            return False, {}, f"Failed to extract members: {str(e)}"
