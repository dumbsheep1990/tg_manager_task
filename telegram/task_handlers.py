#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import asyncio
import time
from datetime import datetime
from typing import Dict, Any, Optional, List, Union

from telethon import TelegramClient
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest
from telethon.tl.functions.contacts import ImportContactsRequest
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPhoneContact, ChannelParticipantsSearch, Channel, User, Chat, InputPeerEmpty
from telethon.errors import (
    ChatAdminRequiredError,
    ChannelPrivateError,
    FloodWaitError,
    UserNotMutualContactError,
    UserPrivacyRestrictedError
)

# Configure logger
logger = logging.getLogger(__name__)

async def handle_send_message(client: TelegramClient, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Send a message to a user or group
    
    Parameters:
    - client: TelegramClient instance
    - params: Dictionary with parameters including:
        - target: Username, phone number, or group/channel link
        - message: Text message to send
        - media_url: Optional URL to media file to send
        - reply_to: Optional message ID to reply to
    
    Returns:
    - Dictionary with result information
    """
    target = params.get('target')
    message_text = params.get('message')
    media_url = params.get('media_url')
    reply_to = params.get('reply_to')
    
    if not target:
        raise ValueError("Target parameter is required")
    
    if not message_text and not media_url:
        raise ValueError("Either message or media_url parameter is required")
    
    try:
        # Resolve the target entity
        if target.startswith('+'):
            # It's a phone number
            entity = await client.get_entity(target)
        elif target.startswith('https://t.me/') or target.startswith('@'):
            # It's a username or link
            username = target.split('/')[-1] if '/' in target else target.lstrip('@')
            entity = await client.get_entity(username)
        else:
            # Try to resolve as username
            entity = await client.get_entity(target)
        
        # Send the message
        if media_url:
            # Download the media file from the URL
            # In a real implementation, you might want to handle different media types differently
            result = await client.send_file(
                entity,
                media_url,
                caption=message_text,
                reply_to=reply_to
            )
        else:
            result = await client.send_message(
                entity,
                message_text,
                reply_to=reply_to
            )
        
        # Return the result
        return {
            'message_id': result.id,
            'sent_at': result.date.isoformat(),
            'entity_id': entity.id,
            'entity_type': 'user' if isinstance(entity, User) else 'chat' if isinstance(entity, Chat) else 'channel'
        }
        
    except FloodWaitError as e:
        logger.warning(f"FloodWaitError: Need to wait for {e.seconds} seconds")
        raise Exception(f"Rate limited: need to wait for {e.seconds} seconds")
    except Exception as e:
        logger.exception(f"Error sending message: {e}")
        raise

async def handle_join_group(client: TelegramClient, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Join a Telegram group or channel
    
    Parameters:
    - client: TelegramClient instance
    - params: Dictionary with parameters including:
        - group_link: Group or channel link or username
    
    Returns:
    - Dictionary with result information
    """
    group_link = params.get('group_link')
    
    if not group_link:
        raise ValueError("Group link parameter is required")
    
    try:
        # Resolve the group entity
        if group_link.startswith('https://t.me/'):
            # Extract username from link
            username = group_link.split('/')[-1].split('?')[0]
            entity = await client.get_entity(username)
        elif group_link.startswith('@'):
            # It's a username
            entity = await client.get_entity(group_link)
        else:
            # Try to resolve as username
            entity = await client.get_entity(group_link)
        
        if not isinstance(entity, Channel):
            raise ValueError("The provided link is not a group or channel")
        
        # Join the group
        result = await client(JoinChannelRequest(entity))
        
        # Return the result
        return {
            'group_id': entity.id,
            'title': entity.title,
            'joined_at': datetime.now().isoformat(),
            'participants_count': getattr(entity, 'participants_count', None)
        }
        
    except ChannelPrivateError:
        raise Exception("Cannot join private channel without an invite link")
    except FloodWaitError as e:
        logger.warning(f"FloodWaitError: Need to wait for {e.seconds} seconds")
        raise Exception(f"Rate limited: need to wait for {e.seconds} seconds")
    except Exception as e:
        logger.exception(f"Error joining group: {e}")
        raise

async def handle_leave_group(client: TelegramClient, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Leave a Telegram group or channel
    
    Parameters:
    - client: TelegramClient instance
    - params: Dictionary with parameters including:
        - group_id: Group or channel ID or username
    
    Returns:
    - Dictionary with result information
    """
    group_id = params.get('group_id')
    group_link = params.get('group_link')
    
    if not group_id and not group_link:
        raise ValueError("Either group_id or group_link parameter is required")
    
    try:
        # Resolve the group entity
        if group_link:
            if group_link.startswith('https://t.me/'):
                # Extract username from link
                username = group_link.split('/')[-1].split('?')[0]
                entity = await client.get_entity(username)
            elif group_link.startswith('@'):
                # It's a username
                entity = await client.get_entity(group_link)
            else:
                # Try to resolve as username
                entity = await client.get_entity(group_link)
        else:
            # Use the group ID
            entity = await client.get_entity(int(group_id))
        
        if not isinstance(entity, Channel):
            raise ValueError("The provided ID is not a group or channel")
        
        # Leave the group
        result = await client(LeaveChannelRequest(entity))
        
        # Return the result
        return {
            'group_id': entity.id,
            'title': entity.title,
            'left_at': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.exception(f"Error leaving group: {e}")
        raise

async def handle_add_contact(client: TelegramClient, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Add a contact to Telegram address book
    
    Parameters:
    - client: TelegramClient instance
    - params: Dictionary with parameters including:
        - phone: Phone number with country code
        - first_name: First name
        - last_name: Last name (optional)
    
    Returns:
    - Dictionary with result information
    """
    phone = params.get('phone')
    first_name = params.get('first_name')
    last_name = params.get('last_name', '')
    
    if not phone:
        raise ValueError("Phone parameter is required")
    
    if not first_name:
        raise ValueError("First name parameter is required")
    
    try:
        # Ensure phone number has correct format
        if not phone.startswith('+'):
            phone = '+' + phone
        
        # Create the contact
        contact = InputPhoneContact(
            client_id=0,  # Random ID
            phone=phone,
            first_name=first_name,
            last_name=last_name
        )
        
        # Add the contact
        result = await client(ImportContactsRequest([contact]))
        
        # Check the result
        if not result.users:
            raise Exception("No users were imported")
        
        user = result.users[0]
        
        # Return the result
        return {
            'user_id': user.id,
            'access_hash': user.access_hash,
            'username': user.username,
            'phone': phone,
            'first_name': first_name,
            'last_name': last_name,
            'added_at': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.exception(f"Error adding contact: {e}")
        raise

async def handle_check_account(client: TelegramClient, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check the status of a Telegram account
    
    Parameters:
    - client: TelegramClient instance
    - params: Dictionary with parameters (not used)
    
    Returns:
    - Dictionary with account status information
    """
    try:
        # Get the current user
        me = await client.get_me()
        
        # Get dialog count (chats and channels)
        dialogs = await client(GetDialogsRequest(
            offset_date=None,
            offset_id=0,
            offset_peer=InputPeerEmpty(),
            limit=1,
            hash=0
        ))
        
        # Return the account status
        return {
            'user_id': me.id,
            'username': me.username,
            'phone': me.phone,
            'first_name': me.first_name,
            'last_name': me.last_name,
            'is_premium': getattr(me, 'premium', False),
            'dialog_count': dialogs.count,
            'status': 'active',
            'check_time': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.exception(f"Error checking account: {e}")
        raise

async def handle_extract_members(client: TelegramClient, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract members from a Telegram group
    
    Parameters:
    - client: TelegramClient instance
    - params: Dictionary with parameters including:
        - group_id: Group or channel ID or username
        - limit: Maximum number of members to extract (default: 100)
        - search_query: Optional search query to filter members
    
    Returns:
    - Dictionary with extracted members
    """
    group_id = params.get('group_id')
    group_link = params.get('group_link')
    limit = int(params.get('limit', 100))
    search_query = params.get('search_query', '')
    
    if not group_id and not group_link:
        raise ValueError("Either group_id or group_link parameter is required")
    
    try:
        # Resolve the group entity
        if group_link:
            if group_link.startswith('https://t.me/'):
                # Extract username from link
                username = group_link.split('/')[-1].split('?')[0]
                entity = await client.get_entity(username)
            elif group_link.startswith('@'):
                # It's a username
                entity = await client.get_entity(group_link)
            else:
                # Try to resolve as username
                entity = await client.get_entity(group_link)
        else:
            # Use the group ID
            entity = await client.get_entity(int(group_id))
        
        if not isinstance(entity, Channel):
            raise ValueError("The provided ID is not a group or channel")
        
        # Check if we have the permission to get members
        if not entity.megagroup:
            raise Exception("Can only extract members from supergroups (megagroups)")
        
        # Get the participants
        participants = await client.get_participants(
            entity,
            limit=limit,
            search=search_query,
            filter=None
        )
        
        # Extract member information
        members = []
        for participant in participants:
            members.append({
                'user_id': participant.id,
                'username': participant.username,
                'first_name': participant.first_name,
                'last_name': participant.last_name,
                'phone': participant.phone,
                'is_bot': participant.bot,
                'is_premium': getattr(participant, 'premium', False),
                'access_hash': participant.access_hash
            })
        
        # Return the result
        return {
            'group_id': entity.id,
            'title': entity.title,
            'member_count': len(members),
            'members': members,
            'timestamp': datetime.now().isoformat()
        }
        
    except ChatAdminRequiredError:
        raise Exception("Admin rights are required to get the members")
    except Exception as e:
        logger.exception(f"Error extracting members: {e}")
        raise
