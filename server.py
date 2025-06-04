import asyncio
from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server
from pydantic import AnyUrl
from aiohttp import web
import os
import logging
from dotenv import load_dotenv
from .kubernetes_client import KubernetesClient
from .slack_bot import SlackBot

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize our clients
k8s_client = KubernetesClient()
slack_bot = SlackBot()

# Initialize server with capabilities
server = Server("k8s-slack-mcp")

@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    """
    List available Kubernetes resources.
    Each resource is exposed with a k8s:// URI scheme.
    """
    resources = []
    
    # Add pod resources
    for pod in k8s_client.list_pods():
        resources.append(types.Resource(
            uri=AnyUrl(f"k8s://pods/{pod['namespace']}/{pod['name']}"),
            name=f"Pod: {pod['name']}",
            description=f"Kubernetes pod in namespace {pod['namespace']}",
            mimeType="application/json",
        ))
    
    # Add deployment resources
    for dep in k8s_client.list_deployments():
        resources.append(types.Resource(
            uri=AnyUrl(f"k8s://deployments/{dep['namespace']}/{dep['name']}"),
            name=f"Deployment: {dep['name']}",
            description=f"Kubernetes deployment in namespace {dep['namespace']}",
            mimeType="application/json",
        ))
    
    return resources

@server.read_resource()
async def handle_read_resource(uri: AnyUrl) -> str:
    """
    Read a specific Kubernetes resource by its URI.
    """
    if uri.scheme != "k8s":
        raise ValueError(f"Unsupported URI scheme: {uri.scheme}")

    path_parts = uri.path.lstrip("/").split("/")
    if len(path_parts) != 3:
        raise ValueError(f"Invalid URI format: {uri}")

    resource_type, namespace, name = path_parts
    
    if resource_type == "pods":
        return k8s_client.get_pod_logs(name, namespace)
    elif resource_type == "deployments":
        return str(k8s_client.list_deployments(namespace))
    
    raise ValueError(f"Unsupported resource type: {resource_type}")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """
    List available tools for Kubernetes and Slack integration.
    """
    return [
        types.Tool(
            name="list_pods",
            description="List all pods in a namespace",
            inputSchema={
                "type": "object",
                "properties": {
                    "namespace": {"type": "string"},
                },
            },
        ),
        types.Tool(
            name="list_deployments",
            description="List all deployments in a namespace",
            inputSchema={
                "type": "object",
                "properties": {
                    "namespace": {"type": "string"},
                },
            },
        ),
        types.Tool(
            name="get_pod_logs",
            description="Get logs from a specific pod",
            inputSchema={
                "type": "object",
                "properties": {
                    "pod_name": {"type": "string"},
                    "namespace": {"type": "string"},
                },
                "required": ["pod_name"],
            },
        ),
        types.Tool(
            name="notify_slack",
            description="Send a message to a Slack channel",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel": {"type": "string"},
                    "message": {"type": "string"},
                },
                "required": ["channel", "message"],
            },
        ),
    ]

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """
    Handle tool execution requests for Kubernetes and Slack operations.
    """
    if not arguments:
        arguments = {}
    
    try:
        if name == "list_pods":
            namespace = arguments.get("namespace", "default")
            pods = k8s_client.list_pods(namespace)
            return [types.TextContent(
                type="text",
                text=str(pods)
            )]
        
        elif name == "list_deployments":
            namespace = arguments.get("namespace", "default")
            deployments = k8s_client.list_deployments(namespace)
            return [types.TextContent(
                type="text",
                text=str(deployments)
            )]
        
        elif name == "get_pod_logs":
            pod_name = arguments.get("pod_name")
            if not pod_name:
                raise ValueError("pod_name is required")
            namespace = arguments.get("namespace", "default")
            logs = k8s_client.get_pod_logs(pod_name, namespace)
            return [types.TextContent(
                type="text",
                text=logs
            )]
        
        elif name == "notify_slack":
            channel = arguments.get("channel")
            message = arguments.get("message")
            if not channel or not message:
                raise ValueError("channel and message are required")
            
            response = slack_bot.app.client.chat_postMessage(
                channel=channel,
                text=message
            )
            return [types.TextContent(
                type="text",
                text=f"Message sent to {channel}"
            )]
        
        raise ValueError(f"Unknown tool: {name}")
        
    except Exception as e:
        return [types.TextContent(
            type="text",
            text=f"Error: {str(e)}"
        )]

@server.list_prompts()
async def handle_list_prompts() -> list[types.Prompt]:
    """
    List available prompts for Kubernetes monitoring.
    """
    return [
        types.Prompt(
            name="monitor-pods",
            description="Monitor pods in a namespace",
            arguments=[
                types.PromptArgument(
                    name="namespace",
                    description="The Kubernetes namespace to monitor",
                    required=False,
                ),
            ],
        ),
    ]

@server.get_prompt()
async def handle_get_prompt(
    name: str, arguments: dict[str, str] | None
) -> types.GetPromptResult:
    """
    Generate prompts for Kubernetes monitoring.
    """
    if name != "monitor-pods":
        raise ValueError(f"Unknown prompt: {name}")

    namespace = (arguments or {}).get("namespace", "default")
    pods = k8s_client.list_pods(namespace)

    return types.GetPromptResult(
        description=f"Monitor pods in namespace {namespace}",
        messages=[
            types.PromptMessage(
                role="user",
                content=types.TextContent(
                    type="text",
                    text=f"Analyze the current state of pods in namespace {namespace}:\n\n"
                    + "\n".join(
                        f"- Pod {pod['name']} is {pod['status']}"
                        + f" with containers: {', '.join(pod['containers'])}"
                        for pod in pods
                    ),
                ),
            )
        ],
    )

async def main():
    try:
        logger.info("Starting K8s Slack MCP Server...")
        
        # Start the Slack bot in a separate thread
        import threading
        slack_thread = threading.Thread(target=slack_bot.start)
        slack_thread.daemon = True
        slack_thread.start()
        logger.info("Slack bot started in Socket Mode")

        # Create aiohttp web app
        app = web.Application()
        
        async def handle_mcp_request(request):
            data = await request.json()
            logger.info(f"Received MCP request: {data}")
            response = await server.handle_jsonrpc(data)
            return web.json_response(response)
        
        app.router.add_post('/', handle_mcp_request)
        
        # Run the HTTP server
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, 'localhost', 6274)
        await site.start()
        logger.info("MCP Server started on http://localhost:6274")
        
        # Keep the server running
        while True:
            await asyncio.sleep(1)
            
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
    finally:
        # Clean up the Slack bot
        slack_bot.stop()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())