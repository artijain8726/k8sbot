# k8s-slack-mcp MCP Server

A Kubernetes-integrated MCP server with Slack bot functionality that provides a bridge between your Kubernetes cluster and Slack workspace through MCP endpoints.

## Features

- Real-time Kubernetes cluster monitoring
- Slack bot integration with custom commands
- MCP server endpoints for managing both systems

## Components

### Kubernetes Integration
- List pods and deployments across namespaces
- Fetch pod logs
- Monitor cluster status

### Slack Bot Commands
- `/pods [namespace]` - List all pods in the specified namespace
- `/deployments [namespace]` - List all deployments in the specified namespace
- `/podlogs <pod-name> [namespace]` - Get logs from a specific pod

### MCP Endpoints
The server provides the following MCP commands:

- `list_pods` - List all pods in a namespace
  ```json
  {
    "command": "list_pods",
    "namespace": "default"
  }
  ```

- `list_deployments` - List all deployments in a namespace
  ```json
  {
    "command": "list_deployments",
    "namespace": "default"
  }
  ```

- `get_pod_logs` - Get logs from a specific pod
  ```json
  {
    "command": "get_pod_logs",
    "pod_name": "my-pod",
    "namespace": "default"
  }
  ```

- `notify_slack` - Send a message to a Slack channel
  ```json
  {
    "command": "notify_slack",
    "channel": "#my-channel",
    "message": "Hello from Kubernetes!"
  }
  ```

## Configuration

1. Create a `.env` file in the project root with your credentials:
```env
SLACK_BOT_TOKEN=your_slack_bot_token
SLACK_SIGNING_SECRET=your_slack_signing_secret
KUBECONFIG=path_to_your_kubeconfig
```

2. Set up your Slack App:
   - Create a new Slack App at https://api.slack.com/apps
   - Add the following bot token scopes:
     - `chat:write`
     - `commands`
   - Create the following slash commands:
     - `/pods`
     - `/deployments`
     - `/podlogs`
   - Install the app to your workspace
   - Copy the Bot User OAuth Token to `SLACK_BOT_TOKEN`
   - Copy the Signing Secret to `SLACK_SIGNING_SECRET`

3. Configure Kubernetes:
   - Ensure you have a valid kubeconfig file
   - Set the `KUBECONFIG` environment variable to point to your config file
   - The service account used must have permissions to list pods, deployments, and read logs

## Quickstart

### Install

#### Claude Desktop

On MacOS: `~/Library/Application\ Support/Claude/claude_desktop_config.json`
On Windows: `%APPDATA%/Claude/claude_desktop_config.json`

<details>
  <summary>Development/Unpublished Servers Configuration</summary>
  ```
  "mcpServers": {
    "k8s-slack-mcp": {
      "command": "uv",
      "args": [
        "--directory",
        "/Users/apple/Downloads/pythonbot",
        "run",
        "k8s-slack-mcp"
      ]
    }
  }
  ```
</details>

<details>
  <summary>Published Servers Configuration</summary>
  ```
  "mcpServers": {
    "k8s-slack-mcp": {
      "command": "uvx",
      "args": [
        "k8s-slack-mcp"
      ]
    }
  }
  ```
</details>

## Development

### Building and Publishing

To prepare the package for distribution:

1. Sync dependencies and update lockfile:
```bash
uv sync
```

2. Build package distributions:
```bash
uv build
```

This will create source and wheel distributions in the `dist/` directory.

3. Publish to PyPI:
```bash
uv publish
```

Note: You'll need to set PyPI credentials via environment variables or command flags:
- Token: `--token` or `UV_PUBLISH_TOKEN`
- Or username/password: `--username`/`UV_PUBLISH_USERNAME` and `--password`/`UV_PUBLISH_PASSWORD`

### Debugging

Since MCP servers run over stdio, debugging can be challenging. For the best debugging
experience, we strongly recommend using the [MCP Inspector](https://github.com/modelcontextprotocol/inspector).


You can launch the MCP Inspector via [`npm`](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm) with this command:

```bash
npx @modelcontextprotocol/inspector uv --directory /Users/apple/Downloads/pythonbot run k8s-slack-mcp
```


Upon launching, the Inspector will display a URL that you can access in your browser to begin debugging.