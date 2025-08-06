# 控制台和网络日志 Playwright MCP 服务器

基于下面的项目二次开发
[![smithery badge](https://smithery.ai/badge/@Lumeva-AI/playwright-consolelogs-mcp)](https://smithery.ai/server/@Lumeva-AI/playwright-consolelogs-mcp)

这个MCP（模型上下文协议）服务器使用Playwright来打开浏览器，监控控制台日志，并跟踪网络请求。将这些功能作为工具暴露出来，供MCP客户端使用。

## 功能

- 在指定URL打开浏览器
- 监控和获取控制台日志
- 跟踪和获取网络请求
- 使用完毕后关闭浏览器



## 本机电脑环境要求
- Python 3.8+

注意这个python环境是你本机的环境，非其他地方的虚拟环境
安装 uv
```shell
pip install uv
```


## 在Cursor中安装

在中cursor 打开MCP servers。 File->Preferences->Cursor Settings->MCP， 点击添加
image.png


添加以下内容：

```json
{
  "mcpServers": {
    "playwright-monitoring": {
      "type": "stdio",
      "command": "uv",
      "args": [
        "--directory",
        "E:\\code\\playwright-consolelogs-mcp\\mcp_playwright\\",
        "run",
        "main.py"
      ]
    }
  }
}
```

（将`E:\\code\\playwright-consolelogs-mcp\\mcp_playwright\\`替换你本地仓库的绝对路径）


## 工作原理

该服务器使用Playwright的事件监听器捕获控制台消息和网络活动。当客户端请求这些信息时，服务器以结构化格式返回，供LLM使用。


## 一杯咖啡
你的一杯奶茶，我的一行Bug~🍗🍗🍗
1b3b89d6e1a5c5ab9603ddaccedbbda7.png