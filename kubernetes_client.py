from kubernetes import client, config
from typing import Dict, List
import logging
from kubernetes.config import kube_config

logger = logging.getLogger(__name__)

class KubernetesClient:
    def __init__(self):
        try:
            config.load_kube_config()
            self._contexts, self._active_context = kube_config.list_kube_config_contexts()
        except:
            config.load_incluster_config()
            self._contexts = [{"name": "in-cluster"}]
            self._active_context = {"name": "in-cluster"}
        
        self.core_v1 = client.CoreV1Api()
        self.apps_v1 = client.AppsV1Api()

    def get_current_context(self) -> Dict:
        """Get information about the current Kubernetes context."""
        return {
            "current_context": self._active_context["name"],
            "cluster": self._active_context.get("context", {}).get("cluster", "unknown"),
            "namespace": self._active_context.get("context", {}).get("namespace", "default")
        }

    def list_available_contexts(self) -> List[Dict]:
        """List all available Kubernetes contexts."""
        return [{
            "name": ctx["name"],
            "cluster": ctx.get("context", {}).get("cluster", "unknown"),
            "namespace": ctx.get("context", {}).get("namespace", "default")
        } for ctx in self._contexts]

    def list_pods(self, namespace: str = "default") -> List[Dict]:
        pods = self.core_v1.list_namespaced_pod(namespace)
        return [{
            "name": pod.metadata.name,
            "namespace": pod.metadata.namespace,
            "status": pod.status.phase,
            "containers": [container.name for container in pod.spec.containers],
            "conditions": [
                {
                    "type": condition.type,
                    "status": condition.status,
                    "message": condition.message if hasattr(condition, 'message') else None
                }
                for condition in (pod.status.conditions or [])
            ] if pod.status.conditions else []
        } for pod in pods.items]

    def list_deployments(self, namespace: str = "default") -> List[Dict]:
        deployments = self.apps_v1.list_namespaced_deployment(namespace)
        return [{
            "name": dep.metadata.name,
            "namespace": dep.metadata.namespace,
            "replicas": dep.spec.replicas,
            "available": dep.status.available_replicas
        } for dep in deployments.items]

    def get_pod_info(self, pod_name: str, namespace: str = "default") -> Dict:
        """Get detailed information about a pod including its status and events."""
        try:
            pod = self.core_v1.read_namespaced_pod(pod_name, namespace)
            
            # Get pod events
            events = self.core_v1.list_namespaced_event(
                namespace,
                field_selector=f'involvedObject.name={pod_name}'
            )
            
            container_statuses = []
            if pod.status.container_statuses:
                for status in pod.status.container_statuses:
                    state = status.state
                    if state.waiting:
                        container_statuses.append({
                            "name": status.name,
                            "state": "waiting",
                            "reason": state.waiting.reason,
                            "message": state.waiting.message
                        })
                    elif state.running:
                        container_statuses.append({
                            "name": status.name,
                            "state": "running",
                            "started_at": state.running.started_at
                        })
                    elif state.terminated:
                        container_statuses.append({
                            "name": status.name,
                            "state": "terminated",
                            "reason": state.terminated.reason,
                            "message": state.terminated.message if hasattr(state.terminated, 'message') else None
                        })

            return {
                "name": pod.metadata.name,
                "namespace": pod.metadata.namespace,
                "status": pod.status.phase,
                "containers": [container.name for container in pod.spec.containers],
                "container_statuses": container_statuses,
                "conditions": [
                    {
                        "type": condition.type,
                        "status": condition.status,
                        "message": condition.message if hasattr(condition, 'message') else None
                    }
                    for condition in (pod.status.conditions or [])
                ],
                "events": [
                    {
                        "type": event.type,
                        "reason": event.reason,
                        "message": event.message,
                        "timestamp": event.last_timestamp
                    }
                    for event in events.items
                ]
            }
        except Exception as e:
            logger.error(f"Error getting pod info: {e}")
            return {"error": str(e)}

    def get_pod_logs(self, pod_name: str, namespace: str = "default") -> str:
        """Get pod logs or status information if logs are not available."""
        try:
            # First get pod info to check status
            pod_info = self.get_pod_info(pod_name, namespace)
            
            # If pod is not running, return status information
            if pod_info.get("status") != "Running":
                # Format the response with status and events
                response = [f"Pod Status: {pod_info['status']}"]
                
                # Add container status information
                response.append("\nContainer Statuses:")
                for container in pod_info.get("container_statuses", []):
                    status_msg = f"• {container['name']}: {container['state']}"
                    if container.get("reason"):
                        status_msg += f" ({container['reason']})"
                    if container.get("message"):
                        status_msg += f"\n  Message: {container['message']}"
                    response.append(status_msg)
                
                # Add recent events
                response.append("\nRecent Events:")
                for event in pod_info.get("events", [])[-5:]:  # Show last 5 events
                    response.append(f"• [{event['type']}] {event['reason']}: {event['message']}")
                
                return "\n".join(response)
            
            # If pod is running, get the logs
            return self.core_v1.read_namespaced_pod_log(pod_name, namespace)
        except Exception as e:
            logger.error(f"Error getting pod logs: {e}")
            return f"Error getting logs: {str(e)}"
