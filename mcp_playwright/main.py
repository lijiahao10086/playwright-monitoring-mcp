#!/usr/bin/env python3

import asyncio
import json
import time
import logging
from logging.handlers import RotatingFileHandler
import os
from typing import Dict, List, Optional, Any

# MCP imports
from mcp.server.fastmcp import FastMCP

# Note: Before running this script, you need to install:
# pip install playwright
# pip install modelcontextprotocol
# playwright install

# 配置日志系统
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, 'playwright_monitor.log')

# 创建日志记录器
logger = logging.getLogger('playwright_monitor')
logger.setLevel(logging.DEBUG)  # 将日志级别设置为DEBUG

# 防止日志重复
if not logger.handlers:
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)  # 将控制台日志级别设置为DEBUG
    
    # 文件处理器，使用UTF-8编码，启用日志滚动
    # 设置最大文件大小为5MB，保留5个备份文件
    file_handler = RotatingFileHandler(
        log_file, 
        maxBytes=5*1024*1024,  # 5MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)  # 将文件日志级别设置为DEBUG
    
    # 日志格式
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)
    
    # 添加处理器
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

logger.info(f"日志系统初始化完成，日志文件路径: {os.path.abspath(log_file)}")
logger.info(f"已配置日志滚动，单个日志文件最大大小: 5MB，保留备份数: 5")

class PlaywrightBrowserManager:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.page = None
        self.console_logs = []
        self.network_requests = []
        self.is_initialized = False
        # 添加请求捕获配置
        self.request_capture_config = {
            "enabled": True,            # 是否启用网络请求捕获
            "include_patterns": [],     # 要包含的URL模式（正则表达式）
            "exclude_patterns": [],     # 要排除的URL模式（正则表达式）
            "include_types": [],        # 要包含的资源类型（如document, xhr, fetch, script等）
            "exclude_types": [],        # 要排除的资源类型
            "capture_post_data": True,  # 是否捕获POST数据
            "capture_response_body": True  # 是否捕获响应体
        }
        logger.info("PlaywrightBrowserManager 实例已创建")

    async def initialize(self, headless: bool = False) -> None:
        """Initialize the Playwright browser if not already initialized."""
        logger.info(f"开始初始化Playwright浏览器，headless模式: {headless}")
        self.headless = headless
        if self.is_initialized:
            logger.debug("浏览器已初始化，跳过初始化过程")
            return
        
        # Import here to avoid module import issues
        import asyncio
        from playwright.async_api import async_playwright

        logger.debug("正在启动Playwright实例")
        self.playwright = await async_playwright().start()
        launch_options = {"headless": False}
        if self.headless:
            launch_options["headless"] = True
        logger.debug(f"正在启动Chromium浏览器，配置选项: {launch_options}")
        self.browser = await self.playwright.chromium.launch(**launch_options)
        self.is_initialized = True
        logger.info("Playwright浏览器初始化完成")

    async def close(self) -> None:
        """Close the browser and Playwright instance."""
        logger.info("开始关闭浏览器实例")
        if self.page:
            logger.info("关闭活动页面")
            await self.page.close()
            self.page = None
            
        if self.browser:
            logger.info("关闭浏览器")
            await self.browser.close()
            self.browser = None
            
        if self.playwright:
            logger.info("停止Playwright")
            await self.playwright.stop()
            self.playwright = None
            
        self.is_initialized = False
        self.console_logs = []
        self.network_requests = []
        logger.info("浏览器资源已完全释放")

    async def open_url(self, url: str, headless: bool = False) -> str:
        """Open a URL in the browser and start monitoring console and network.
        The browser will stay open for user interaction."""
        logger.info(f"准备打开URL: {url}，headless模式: {headless}")
        if not self.is_initialized:
            logger.debug("浏览器未初始化，正在执行初始化")
            await self.initialize(headless=headless)
            
        # Close existing page if any
        if self.page:
            logger.debug("关闭已存在的页面")
            await self.page.close()
            
        # Clear previous logs and requests
        logger.debug("清除之前的日志和请求记录")
        self.console_logs = []
        self.network_requests = []
        
        # Create a new page
        logger.debug("创建新的浏览器页面")
        self.page = await self.browser.new_page()
        
        # Set up console log listener
        logger.debug("设置控制台日志监听器")
        self.page.on("console", self._handle_console_message)
        
        # Set up network request listener
        logger.debug("设置网络请求监听器")
        self.page.on("request", self._handle_request)
        self.page.on("response", self._handle_response)
        
        # Navigate to the URL
        logger.info(f"导航到URL: {url}")
        await self.page.goto(url, wait_until="networkidle")
        logger.info(f"页面加载完成: {url}")
        
        # Add a message to let the user know the browser will stay open
        
        return f"Opened {url} successfully. The browser window will remain open for you to interact with."

    def _handle_console_message(self, message) -> None:
        """Handle console messages from the page."""
        try:
            log_entry = {
                "type": message.type,
                "text": message.text,
                "location": message.location,
                "timestamp": asyncio.get_event_loop().time()
            }
            self.console_logs.append(log_entry)
            logger.debug(f"捕获到控制台消息: [{message.type}] {message.text}")
        except Exception as e:
            logger.error(f"处理控制台消息时出错: {str(e)}")
            # 创建一个简单记录
            self.console_logs.append({
                "type": "error",
                "text": f"处理控制台消息时出错: {str(e)}",
                "timestamp": asyncio.get_event_loop().time()
            })

    def _handle_request(self, request) -> None:
        """Handle network requests."""
        # 检查是否应该捕获此请求
        if not self._should_capture_request(request):
            return
        
        try:
            request_entry = {
                "url": request.url,
                "method": request.method,
                "headers": request.headers,
                "timestamp": asyncio.get_event_loop().time(),
                "resourceType": request.resource_type,
                "id": id(request)
            }
            
            # 根据配置决定是否捕获POST数据
            if self.request_capture_config["capture_post_data"] and request.post_data:
                request_entry["postData"] = request.post_data
                
                # 尝试获取JSON形式的负载数据
                if 'json' in request.headers.get('content-type', '').lower():
                    try:
                        import json
                        if isinstance(request.post_data, str):
                            request_entry["postDataJSON"] = json.loads(request.post_data)
                    except:
                        pass
                
            self.network_requests.append(request_entry)
            logger.debug(f"捕获到网络请求: {request.method} {request.url}")
        except Exception as e:
            logger.error(f"处理网络请求时出错: {str(e)}")
            # 简单记录错误
            self.network_requests.append({
                "url": request.url if hasattr(request, 'url') else "unknown",
                "method": request.method if hasattr(request, 'method') else "ERROR",
                "error": str(e),
                "timestamp": asyncio.get_event_loop().time()
            })

    def _handle_response(self, response) -> None:
        """Handle network responses."""
        # 检查对应的请求是否被捕获
        request_captured = False
        for request in self.network_requests:
            if request.get("url") == response.url and "response" not in request:
                request_captured = True
                break
        
        # 如果对应的请求没有被捕获，跳过处理
        if not request_captured:
            return
        
        try:
            # 基本响应数据
            response_data = {
                "status": response.status,
                "statusText": response.status_text,
                "headers": response.headers,
                "timestamp": asyncio.get_event_loop().time()
            }
            
            # 根据配置决定是否捕获响应体
            if self.request_capture_config["capture_response_body"]:
                content_type = response.headers.get('content-type', '')
                
                # 标记有JSON内容的响应，供后续处理
                if 'json' in content_type.lower() or response.url.endswith('.json'):
                    response_data["_is_json"] = True
                    response_data["_response_obj"] = response
                    logger.debug(f"标记JSON响应待处理: {response.url}")
                
            # 找到匹配的请求并更新
            for request in self.network_requests:
                if request.get("url") == response.url and "response" not in request:
                    request["response"] = response_data
                    logger.debug(f"捕获到网络响应: {response.status} {response.url}")
                    break
        except Exception as e:
            logger.error(f"处理网络响应时出错: {str(e)}")
            # 尝试添加基本响应记录
            try:
                for request in self.network_requests:
                    if request.get("url") == response.url and "response" not in request:
                        request["response"] = {
                            "status": response.status if hasattr(response, 'status') else 0,
                            "error": str(e),
                            "timestamp": asyncio.get_event_loop().time()
                        }
                        break
            except:
                pass

    async def get_console_logs(self, last_n: int) -> List[Dict]:
        """Get console logs collected so far with deduplication of repeated messages.
        
        Args:
            last_n: Number of log entries to return, prioritizing the most recent ones.
                   Use a large number to get all logs.
        
        Returns:
            A list of deduplicated console log entries
        """
        logger.info(f"获取控制台日志，请求最近的 {last_n} 条")
        if not self.console_logs:
            logger.info("没有控制台日志可供返回")
            return []
            
        # 创建一个安全的日志列表副本
        safe_logs = []
        for log in self.console_logs:
            try:
                import copy
                safe_log = copy.deepcopy(log)
                safe_logs.append(safe_log)
            except Exception as e:
                # 如果无法复制，创建一个简化版本
                logger.warning(f"无法复制日志条目: {str(e)}")
                simple_log = {
                    "type": log.get("type", "unknown"),
                    "text": log.get("text", "复制失败的日志"),
                    "timestamp": log.get("timestamp", 0),
                    "copy_error": str(e)
                }
                safe_logs.append(simple_log)
            
        # 创建一个去重版本的日志
        deduplicated_logs = []
        current_group = None
        
        # 按时间戳排序以确保分组正确
        sorted_logs = sorted(safe_logs, key=lambda x: x.get('timestamp', 0))
        logger.info(f"正在处理 {len(sorted_logs)} 条原始日志")
        
        for log in sorted_logs:
            # 如果没有当前组或当前日志与组不同
            if (current_group is None or 
                log.get('type') != current_group.get('type') or 
                log.get('text') != current_group.get('text')):
                
                # 开始一个新组
                current_group = {
                    'type': log.get('type'),
                    'text': log.get('text'),
                    'location': log.get('location'),
                    'timestamp': log.get('timestamp'),
                    'count': 1,
                    'timestamps': [log.get('timestamp')]
                }
                
                # 复制其他有用字段
                for key in ['stackTrace', 'args', 'page']:
                    if key in log:
                        current_group[key] = log[key]
                    
                deduplicated_logs.append(current_group)
            else:
                # 这是重复消息，增加计数并添加时间戳
                current_group['count'] += 1
                current_group['timestamps'].append(log.get('timestamp'))
                # 更新文本以显示重复计数
                if current_group['count'] > 1:
                    current_group['text'] = f"{log.get('text')} (重复 {current_group['count']} 次)"
        
        # 返回最后N条记录
        # 按时间戳排序（从新到旧）
        deduplicated_logs.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
        deduplicated_logs = deduplicated_logs[:last_n]
        # 按时间戳重新排序（从旧到新）
        deduplicated_logs.sort(key=lambda x: x.get('timestamp', 0))
        
        logger.info(f"返回 {len(deduplicated_logs)} 条去重后的日志")
        return deduplicated_logs

    async def _process_json_responses(self):
        """异步处理标记为需要获取JSON内容的响应"""
        processed_count = 0
        
        for request in self.network_requests:
            if "response" in request and request["response"].get("_is_json") and "_response_obj" in request["response"]:
                try:
                    response_obj = request["response"]["_response_obj"]
                    # 异步获取响应文本
                    text = await response_obj.text()
                    
                    # 尝试解析JSON
                    import json
                    try:
                        json_data = json.loads(text)
                        request["response"]["body"] = json_data
                        logger.debug(f"成功解析JSON响应: {request['url']}")
                    except json.JSONDecodeError:
                        # 如果不是有效的JSON，保存为文本
                        request["response"]["bodyText"] = text
                        logger.debug(f"响应不是有效的JSON，保存为文本: {request['url']}")
                    
                    processed_count += 1
                except Exception as e:
                    logger.error(f"处理JSON响应时出错: {str(e)}")
                    request["response"]["body_error"] = str(e)
                finally:
                    # 无论成功与否，都清理临时数据
                    if "_is_json" in request["response"]:
                        del request["response"]["_is_json"]
                    if "_response_obj" in request["response"]:
                        del request["response"]["_response_obj"]
        
        return processed_count

    async def get_network_requests(self, last_n: int) -> List[Dict]:
        """Get network requests collected so far.
        
        Args:
            last_n: Number of network request entries to return, prioritizing the most recent ones.
                   Use a large number to get all requests.
        
        Returns:
            A list of network request entries
        """
        logger.info(f"获取网络请求，请求最近的 {last_n} 条")
        if not self.network_requests:
            logger.info("没有网络请求可供返回")
            return []
        
        # 处理标记的JSON响应
        processed_count = await self._process_json_responses()
        if processed_count > 0:
            logger.info(f"成功处理了 {processed_count} 个JSON响应")
        
        # 复制一份请求列表，以避免序列化问题
        clean_requests = []
        for req in self.network_requests:
            try:
                # 创建一个干净的副本，移除任何可能的引用或不可序列化的对象
                clean_req = {}
                
                # 复制基本字段
                for key in ["url", "method", "headers", "timestamp", "resourceType", "id"]:
                    if key in req:
                        clean_req[key] = req[key]
                    
                # 如果有POST数据，复制它
                if "postData" in req:
                    clean_req["postData"] = req["postData"]
                if "postDataJSON" in req:
                    clean_req["postDataJSON"] = req["postDataJSON"]
                    
                # 如果有响应，复制它
                if "response" in req:
                    clean_response = {}
                    for resp_key in ["status", "statusText", "headers", "timestamp", "body", "bodyText"]:
                        if resp_key in req["response"]:
                            clean_response[resp_key] = req["response"][resp_key]
                    clean_req["response"] = clean_response
                
                clean_requests.append(clean_req)
            except Exception as e:
                logger.error(f"处理请求数据时出错: {str(e)}")
                # 添加一个简单的记录以防错误
                clean_requests.append({
                    "url": req.get("url", "unknown"),
                    "method": req.get("method", "unknown"),
                    "error": str(e)
                })
            
        # Sort by timestamp (descending) to get the most recent requests first
        sorted_requests = sorted(clean_requests, key=lambda x: x.get('timestamp', 0), reverse=True)
        # Take only the last N entries
        limited_requests = sorted_requests[:last_n]
        # Sort back by timestamp (ascending) for consistent output
        limited_requests.sort(key=lambda x: x.get('timestamp', 0))
        
        logger.info(f"返回 {len(limited_requests)} 条网络请求，共收集了 {len(self.network_requests)} 条")
        return limited_requests

    # 添加配置方法
    def configure_request_capture(self, config_updates):
        """更新网络请求捕获配置"""
        logger.info(f"更新网络请求捕获配置: {config_updates}")
        self.request_capture_config.update(config_updates)
        return self.request_capture_config

    def _should_capture_request(self, request):
        """根据配置决定是否捕获请求"""
        # 如果捕获被禁用，直接返回False
        if not self.request_capture_config["enabled"]:
            return False
            
        url = request.url
        resource_type = request.resource_type
        
        # 检查资源类型过滤器
        if self.request_capture_config["include_types"] and resource_type not in self.request_capture_config["include_types"]:
            return False
            
        if resource_type in self.request_capture_config["exclude_types"]:
            return False
            
        # 检查URL模式过滤器
        import re
        
        # 如果有包含模式，URL必须至少匹配一个
        if self.request_capture_config["include_patterns"]:
            matches_include = False
            for pattern in self.request_capture_config["include_patterns"]:
                if re.search(pattern, url):
                    matches_include = True
                    break
            if not matches_include:
                return False
                
        # 如果URL匹配任何排除模式，则排除它
        for pattern in self.request_capture_config["exclude_patterns"]:
            if re.search(pattern, url):
                return False
                
        return True

# Create the MCP server
mcp = FastMCP("browser-monitor")
logger.info("创建FastMCP服务器实例: browser-monitor")

# Create a browser manager instance
browser_manager = PlaywrightBrowserManager()

# Define MCP tools
@mcp.tool()
async def open_browser(url: str, headless: bool = False) -> str:
    """在指定URL打开浏览器并开始监控控制台日志和网络请求。
    
    参数:
        url: 字符串，要在浏览器中打开的URL
        headless: 布尔值，是否以无头模式运行浏览器
        
    返回:
        确认消息
    """
    logger.info(f"MCP工具调用: open_browser(url={url}, headless={headless})")
    result = await browser_manager.open_url(url, headless=headless)
    logger.info(f"open_browser工具执行完成，返回结果长度: {len(result)}")
    return result

@mcp.tool()
async def get_console_logs(last_n: int) -> List[Dict]:
    """获取当前打开的浏览器页面中的控制台日志。
    重复的消息会被去重并显示重复次数。
    
    参数:
        last_n: 要返回的日志条目数量，优先返回最近的条目。
               使用较大的数字可获取所有日志。
    
    返回:
        控制台日志条目列表，包含类型、文本、位置、时间戳和重复消息的计数
    """
    logger.info(f"MCP工具调用: get_console_logs(last_n={last_n})")
    result = await browser_manager.get_console_logs(last_n)
    logger.info(f"get_console_logs工具执行完成，返回日志条目数: {len(result)}")
    return result

@mcp.tool()
async def get_network_requests(last_n: int) -> List[Dict]:
    """获取当前打开的浏览器页面中的网络请求。
    
    参数:
        last_n: 要返回的网络请求条目数量，优先返回最近的条目。
               使用较大的数字可获取所有请求。
    
    返回:
        网络请求条目列表，包含URL、方法、头信息和响应数据
    """
    logger.info(f"MCP工具调用: get_network_requests(last_n={last_n})")
    result = await browser_manager.get_network_requests(last_n)
    logger.info(f"get_network_requests工具执行完成，返回网络请求条目数: {len(result)}")
    return result

@mcp.tool()
async def close_browser() -> str:
    """关闭浏览器并清理资源。
    
    返回:
        确认消息
    """
    logger.info("MCP工具调用: close_browser()")
    await browser_manager.close()
    logger.info("close_browser工具执行完成")
    return "浏览器已成功关闭"

@mcp.tool()
async def configure_network_capture(enabled: bool = None, 
                                  include_patterns: List[str] = None, 
                                  exclude_patterns: List[str] = None,
                                  include_types: List[str] = None,
                                  exclude_types: List[str] = None,
                                  capture_post_data: bool = None,
                                  capture_response_body: bool = None) -> Dict:
    """配置网络请求捕获参数，控制捕获哪些请求和响应。
    
    参数:
        enabled: 是否启用网络请求捕获
        include_patterns: 要包含的URL模式列表（正则表达式）
        exclude_patterns: 要排除的URL模式列表（正则表达式）
        include_types: 要包含的资源类型列表（如document, xhr, fetch, script等）
        exclude_types: 要排除的资源类型列表
        capture_post_data: 是否捕获POST数据
        capture_response_body: 是否捕获响应体
    
    返回:
        更新后的配置
    """
    logger.info(f"MCP工具调用: configure_network_capture")
    # 构建更新配置
    config_updates = {}
    if enabled is not None:
        config_updates["enabled"] = enabled
    if include_patterns is not None:
        config_updates["include_patterns"] = include_patterns
    if exclude_patterns is not None:
        config_updates["exclude_patterns"] = exclude_patterns
    if include_types is not None:
        config_updates["include_types"] = include_types
    if exclude_types is not None:
        config_updates["exclude_types"] = exclude_types
    if capture_post_data is not None:
        config_updates["capture_post_data"] = capture_post_data
    if capture_response_body is not None:
        config_updates["capture_response_body"] = capture_response_body
        
    # 更新配置
    result = browser_manager.configure_request_capture(config_updates)
    logger.info(f"网络请求捕获配置已更新: {result}")
    return result

@mcp.tool()
async def get_network_capture_config() -> Dict:
    """获取当前的网络请求捕获配置。
    
    返回:
        当前的网络请求捕获配置
    """
    logger.info("MCP工具调用: get_network_capture_config")
    result = browser_manager.request_capture_config.copy()
    logger.info(f"返回当前网络捕获配置")
    return result

def main():
    logger.info("启动MCP服务器...")
    try:
        logger.info("MCP服务器开始运行")
        mcp.run()
    except Exception as e:
        logger.error(f"MCP服务器运行出错: {str(e)}", exc_info=True)
        raise
    finally:
        logger.info("MCP服务器已停止")

# Run the server when the script is executed directly
if __name__ == "__main__":
    # This will automatically handle the server lifecycle and run it
    logger.info("启动Playwright浏览器监控服务")
    main()