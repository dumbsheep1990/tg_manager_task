#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
与TG Manager API通信的API客户端
"""

import json
import logging
from typing import Dict, Any, Optional, Union

import aiohttp

logger = logging.getLogger(__name__)


class ApiClient:
    """用于与TG Manager API交互的客户端"""
    
    def __init__(self, base_url: str, token: str = None):
        """
        初始化API客户端
        
        参数:
            base_url: API的基础URL
            token: 认证令牌（可选）
        """
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.session = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建HTTP会话"""
        if self.session is None or self.session.closed:
            # Create a new session with default headers
            headers = {}
            if self.token:
                headers['Authorization'] = f'Bearer {self.token}'
            self.session = aiohttp.ClientSession(headers=headers)
        return self.session
    
    async def close(self) -> None:
        """关闭HTTP会话"""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None
    
    async def request(self, method: str, endpoint: str, 
                     params: Optional[Dict[str, Any]] = None,
                     data: Optional[Dict[str, Any]] = None,
                     json: Optional[Dict[str, Any]] = None,
                     headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Make an HTTP request to the API
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint
            params: Query parameters
            data: Form data
            json: JSON request body
            headers: Custom headers
            
        Returns:
            JSON response data
        """
        session = await self._get_session()
        url = f"{self.base_url}{endpoint}"
        
        logger.debug(f"{method} {url}")
        
        try:
            async with session.request(
                method=method,
                url=url,
                params=params,
                data=data,
                json=json,
                headers=headers
            ) as response:
                # Read response data
                response_data = await response.text()
                
                # Parse JSON response
                try:
                    result = json.loads(response_data)
                except:
                    # If parsing fails, return the raw text
                    return {
                        "success": response.status < 400,
                        "status_code": response.status,
                        "data": response_data
                    }
                
                # Check for errors
                if response.status >= 400:
                    logger.error(f"API error: {response.status} - {result.get('message', 'Unknown error')}")
                    return {
                        "success": False,
                        "status_code": response.status,
                        "message": result.get("message", "Unknown error"),
                        "data": result.get("data")
                    }
                
                return result
                
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error: {str(e)}")
            return {
                "success": False,
                "message": f"HTTP error: {str(e)}",
                "status_code": 0
            }
    
    async def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make a GET request to the API
        
        Args:
            endpoint: API endpoint
            params: Query parameters
            
        Returns:
            JSON response data
        """
        return await self.request("GET", endpoint, params=params)
    
    async def post(self, endpoint: str, json: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make a POST request to the API
        
        Args:
            endpoint: API endpoint
            json: JSON request body
            
        Returns:
            JSON response data
        """
        return await self.request("POST", endpoint, json=json)
    
    async def put(self, endpoint: str, json: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make a PUT request to the API
        
        Args:
            endpoint: API endpoint
            json: JSON request body
            
        Returns:
            JSON response data
        """
        return await self.request("PUT", endpoint, json=json)
    
    async def delete(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make a DELETE request to the API
        
        Args:
            endpoint: API endpoint
            params: Query parameters
            
        Returns:
            JSON response data
        """
        return await self.request("DELETE", endpoint, params=params)
