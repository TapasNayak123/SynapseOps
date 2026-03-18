"""Lightweight Kubernetes client for pod and node status via kubectl or K8s API."""
import json
import subprocess
import structlog

logger = structlog.get_logger()


class K8sClient:
    def __init__(self, namespace: str = "default"):
        self.namespace = namespace

    def _run(self, args: list[str], timeout: int = 10) -> str:
        try:
            result = subprocess.run(
                ["kubectl"] + args,
                capture_output=True, text=True, timeout=timeout,
            )
            return result.stdout.strip()
        except FileNotFoundError:
            return ""
        except subprocess.TimeoutExpired:
            return ""
        except Exception as e:
            logger.warning("kubectl_failed", args=args, error=str(e))
            return ""

    def get_pod_status(self, label_selector: str = "") -> list[dict]:
        """Get pod status for pods matching a label selector."""
        args = ["get", "pods", "-n", self.namespace, "-o", "json"]
        if label_selector:
            args += ["-l", label_selector]
        raw = self._run(args)
        if not raw:
            return []
        try:
            data = json.loads(raw)
            pods = []
            for item in data.get("items", []):
                meta = item.get("metadata", {})
                spec = item.get("spec", {})
                status = item.get("status", {})
                containers = []
                for cs in status.get("containerStatuses", []):
                    containers.append({
                        "name": cs.get("name"),
                        "ready": cs.get("ready", False),
                        "restart_count": cs.get("restartCount", 0),
                        "state": list(cs.get("state", {}).keys())[0] if cs.get("state") else "unknown",
                        "image": cs.get("image", ""),
                    })
                # Resource requests/limits
                resources = {}
                for c in spec.get("containers", []):
                    res = c.get("resources", {})
                    resources[c.get("name", "unknown")] = {
                        "requests": res.get("requests", {}),
                        "limits": res.get("limits", {}),
                    }
                pods.append({
                    "name": meta.get("name"),
                    "namespace": meta.get("namespace"),
                    "phase": status.get("phase"),
                    "node": spec.get("nodeName", ""),
                    "pod_ip": status.get("podIP", ""),
                    "start_time": status.get("startTime", ""),
                    "containers": containers,
                    "resources": resources,
                })
            return pods
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("pod_parse_failed", error=str(e))
            return []

    def get_node_status(self) -> list[dict]:
        """Get node resource usage via kubectl top."""
        raw = self._run(["top", "nodes", "--no-headers"], timeout=15)
        if not raw:
            return []
        nodes = []
        for line in raw.strip().split("\n"):
            parts = line.split()
            if len(parts) >= 5:
                nodes.append({
                    "name": parts[0],
                    "cpu_usage": parts[1],
                    "cpu_percent": parts[2],
                    "memory_usage": parts[3],
                    "memory_percent": parts[4],
                })
        return nodes

    def get_pod_resource_usage(self, label_selector: str = "") -> list[dict]:
        """Get pod CPU/memory usage via kubectl top."""
        args = ["top", "pods", "-n", self.namespace, "--no-headers"]
        if label_selector:
            args += ["-l", label_selector]
        raw = self._run(args, timeout=15)
        if not raw:
            return []
        pods = []
        for line in raw.strip().split("\n"):
            parts = line.split()
            if len(parts) >= 3:
                pods.append({
                    "name": parts[0],
                    "cpu": parts[1],
                    "memory": parts[2],
                })
        return pods

    def get_all_pods_summary(self) -> dict:
        """Get a comprehensive summary: pods, nodes, services, deployments, cluster info."""
        pods = self.get_pod_status()
        usage = self.get_pod_resource_usage()
        usage_map = {p["name"]: p for p in usage}
        for pod in pods:
            u = usage_map.get(pod["name"], {})
            pod["cpu_usage"] = u.get("cpu", "N/A")
            pod["memory_usage"] = u.get("memory", "N/A")
        return {
            "cluster_info": self.get_cluster_info(),
            "total_pods": len(pods),
            "pods": pods,
            "nodes": self.get_node_status(),
            "services": self.get_services(),
            "deployments": self.get_deployments(),
        }
    def get_services(self) -> list[dict]:
        """Get Kubernetes services in the namespace."""
        raw = self._run(["get", "services", "-n", self.namespace, "-o", "json"])
        if not raw:
            return []
        try:
            data = json.loads(raw)
            svcs = []
            for item in data.get("items", []):
                meta = item.get("metadata", {})
                spec = item.get("spec", {})
                status = item.get("status", {})
                lb = status.get("loadBalancer", {}).get("ingress", [])
                external = lb[0].get("hostname", lb[0].get("ip", "")) if lb else ""
                svcs.append({
                    "name": meta.get("name"),
                    "type": spec.get("type"),
                    "cluster_ip": spec.get("clusterIP", ""),
                    "external": external,
                    "ports": [{"port": p.get("port"), "target": p.get("targetPort"), "protocol": p.get("protocol")} for p in spec.get("ports", [])],
                })
            return svcs
        except (json.JSONDecodeError, KeyError):
            return []

    def get_deployments(self) -> list[dict]:
        """Get Kubernetes deployments in the namespace."""
        raw = self._run(["get", "deployments", "-n", self.namespace, "-o", "json"])
        if not raw:
            return []
        try:
            data = json.loads(raw)
            deps = []
            for item in data.get("items", []):
                meta = item.get("metadata", {})
                spec = item.get("spec", {})
                status = item.get("status", {})
                deps.append({
                    "name": meta.get("name"),
                    "replicas": spec.get("replicas", 0),
                    "ready": status.get("readyReplicas", 0),
                    "available": status.get("availableReplicas", 0),
                    "updated": status.get("updatedReplicas", 0),
                    "image": spec.get("template", {}).get("spec", {}).get("containers", [{}])[0].get("image", ""),
                })
            return deps
        except (json.JSONDecodeError, KeyError):
            return []

    def get_cluster_info(self) -> dict:
        """Get basic cluster info (version, context)."""
        version_raw = self._run(["version", "--short", "-o", "json"], timeout=5)
        context_raw = self._run(["config", "current-context"], timeout=5)
        info = {"context": context_raw or "unknown"}
        if version_raw:
            try:
                v = json.loads(version_raw)
                info["server_version"] = v.get("serverVersion", {}).get("gitVersion", "")
                info["client_version"] = v.get("clientVersion", {}).get("gitVersion", "")
            except (json.JSONDecodeError, KeyError):
                pass
        return info
