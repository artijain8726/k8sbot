from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import os
from .kubernetes_client import KubernetesClient

class SlackBot:
    def __init__(self):
        self.app = App(token=os.environ["SLACK_BOT_TOKEN"])
        self.k8s = KubernetesClient()
        self.setup_handlers()
        self.socket_mode_handler = None

    def setup_handlers(self):
        @self.app.command("/pods")
        def list_pods(ack, respond, command):
            ack()
            try:
                namespace = command.get("text", "default").strip()
                pods = self.k8s.list_pods(namespace)
                
                if not pods:
                    respond(f"No pods found in namespace '{namespace}'")
                    return
                
                blocks = [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"📦 Pods in namespace: {namespace}"
                        }
                    }
                ]
                
                for pod in pods:
                    status_emoji = "🟢" if pod['status'] == "Running" else "🔴" if pod['status'] == "Failed" else "🟡"
                    text = f"{status_emoji} *{pod['name']}*\n"
                    text += f"• Status: {pod['status']}\n"
                    text += f"• Containers: {', '.join(pod['containers'])}"
                    
                    # Add conditions if pod is not running
                    if pod['status'] != "Running" and pod.get('conditions'):
                        text += "\n• Conditions:"
                        for condition in pod['conditions']:
                            if condition.get('message'):
                                text += f"\n  - {condition['type']}: {condition['message']}"
                    
                    blocks.append({
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": text
                        }
                    })
                
                respond(blocks=blocks)
            except Exception as e:
                respond(f"Error: {str(e)}")

        @self.app.command("/deployments")
        def list_deployments(ack, respond, command):
            ack()
            try:
                namespace = command.get("text", "default").strip()
                deployments = self.k8s.list_deployments(namespace)
                
                if not deployments:
                    respond(f"No deployments found in namespace '{namespace}'")
                    return
                
                blocks = [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"🚀 Deployments in namespace: {namespace}"
                        }
                    }
                ]
                
                for dep in deployments:
                    status_emoji = "🟢" if dep['available'] == dep['replicas'] else "🟡"
                    blocks.append({
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"{status_emoji} *{dep['name']}*\n"
                                   f"• Replicas: {dep['replicas']}\n"
                                   f"• Available: {dep['available'] or 0}/{dep['replicas']}"
                        }
                    })
                
                respond(blocks=blocks)
            except Exception as e:
                respond(f"Error: {str(e)}")

        @self.app.command("/podlogs")
        def get_pod_logs(ack, respond, command):
            ack()
            try:
                args = command.get("text", "").strip().split()
                if not args:
                    respond("Please provide a pod name: `/podlogs <pod-name> [namespace]`")
                    return
                
                pod_name = args[0]
                namespace = args[1] if len(args) > 1 else "default"
                
                logs = self.k8s.get_pod_logs(pod_name, namespace)
                if not logs:
                    respond(f"No information available for pod '{pod_name}' in namespace '{namespace}'")
                    return
                
                # Split long logs into multiple messages if needed
                max_length = 3000  # Slack has a message length limit
                if len(logs) > max_length:
                    chunks = [logs[i:i + max_length] for i in range(0, len(logs), max_length)]
                    for i, chunk in enumerate(chunks, 1):
                        respond(f"```\n{chunk}\n```" + (f" (Part {i}/{len(chunks)})" if len(chunks) > 1 else ""))
                else:
                    respond(f"```\n{logs}\n```")
            except Exception as e:
                respond(f"Error: {str(e)}")

        @self.app.command("/cluster")
        def get_cluster_info(ack, respond, command):
            ack()
            try:
                context_info = self.k8s.get_current_context()
                blocks = [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": "☸️ Current Kubernetes Context"
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Context:* {context_info['current_context']}\n"
                                   f"*Cluster:* {context_info['cluster']}\n"
                                   f"*Default Namespace:* {context_info['namespace']}"
                        }
                    }
                ]
                respond(blocks=blocks)
            except Exception as e:
                respond(f"Error: {str(e)}")

        @self.app.command("/contexts")
        def list_contexts(ack, respond, command):
            ack()
            try:
                contexts = self.k8s.list_available_contexts()
                blocks = [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": "☸️ Available Kubernetes Contexts"
                        }
                    }
                ]
                
                for ctx in contexts:
                    blocks.append({
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Context:* {ctx['name']}\n"
                                   f"• Cluster: {ctx['cluster']}\n"
                                   f"• Default Namespace: {ctx['namespace']}"
                        }
                    })
                
                respond(blocks=blocks)
            except Exception as e:
                respond(f"Error: {str(e)}")

    def start(self):
        """Start the Slack bot using Socket Mode"""
        try:
            self.socket_mode_handler = SocketModeHandler(
                app_token=os.environ["SLACK_APP_TOKEN"],
                app=self.app
            )
            print("Starting Slack bot in Socket Mode...")
            self.socket_mode_handler.start()
        except Exception as e:
            print(f"Error starting Slack bot: {e}")

    def stop(self):
        """Stop the Slack bot"""
        if self.socket_mode_handler:
            self.socket_mode_handler.close()
