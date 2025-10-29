# backend/chaos/chaos_manager.py
"""
Chaos Engineering Manager
Chaos Mesh integration for fault injection and resilience testing

Features:
- Pod failure injection
- Network latency injection
- Resource stress testing
- Automated chaos experiments
"""
import logging
import subprocess
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class ChaosManager:
    """Chaos Engineering マネージャー"""

    def __init__(self, namespace: str = "default"):
        self.namespace = namespace

    def inject_pod_failure(
        self,
        target_pod: str,
        duration: str = "30s",
        action: str = "pod-kill"
    ) -> Dict:
        """
        Pod障害注入

        Args:
            target_pod: ターゲットPod名（またはラベルセレクタ）
            duration: 障害持続時間（例: "30s", "1m"）
            action: 障害タイプ（pod-kill, pod-failure, container-kill）

        Returns:
            Experiment result
        """
        logger.info(f"[Chaos] Injecting pod failure: {target_pod}, action={action}")

        experiment = {
            "apiVersion": "chaos-mesh.org/v1alpha1",
            "kind": "PodChaos",
            "metadata": {
                "name": f"pod-failure-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "namespace": self.namespace
            },
            "spec": {
                "action": action,
                "mode": "one",
                "duration": duration,
                "selector": {
                    "namespaces": [self.namespace],
                    "labelSelectors": {
                        "app": target_pod
                    }
                }
            }
        }

        return self._apply_experiment(experiment)

    def inject_network_delay(
        self,
        target_pod: str,
        latency: str = "100ms",
        duration: str = "60s"
    ) -> Dict:
        """
        ネットワーク遅延注入

        Args:
            target_pod: ターゲットPod
            latency: 遅延時間（例: "100ms", "500ms"）
            duration: 障害持続時間

        Returns:
            Experiment result
        """
        logger.info(f"[Chaos] Injecting network delay: {target_pod}, latency={latency}")

        experiment = {
            "apiVersion": "chaos-mesh.org/v1alpha1",
            "kind": "NetworkChaos",
            "metadata": {
                "name": f"network-delay-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "namespace": self.namespace
            },
            "spec": {
                "action": "delay",
                "mode": "one",
                "duration": duration,
                "selector": {
                    "namespaces": [self.namespace],
                    "labelSelectors": {
                        "app": target_pod
                    }
                },
                "delay": {
                    "latency": latency,
                    "correlation": "0",
                    "jitter": "0ms"
                }
            }
        }

        return self._apply_experiment(experiment)

    def inject_stress(
        self,
        target_pod: str,
        cpu_cores: int = 2,
        duration: str = "60s"
    ) -> Dict:
        """
        CPUストレス注入

        Args:
            target_pod: ターゲットPod
            cpu_cores: 負荷をかけるCPUコア数
            duration: 障害持続時間

        Returns:
            Experiment result
        """
        logger.info(f"[Chaos] Injecting CPU stress: {target_pod}, cores={cpu_cores}")

        experiment = {
            "apiVersion": "chaos-mesh.org/v1alpha1",
            "kind": "StressChaos",
            "metadata": {
                "name": f"stress-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "namespace": self.namespace
            },
            "spec": {
                "mode": "one",
                "duration": duration,
                "selector": {
                    "namespaces": [self.namespace],
                    "labelSelectors": {
                        "app": target_pod
                    }
                },
                "stressors": {
                    "cpu": {
                        "workers": cpu_cores,
                        "load": 100
                    }
                }
            }
        }

        return self._apply_experiment(experiment)

    def run_chaos_scenario(self, scenario_name: str) -> List[Dict]:
        """
        事前定義されたChaosシナリオを実行

        Scenarios:
        - "cascade_failure": カスケード障害シミュレーション
        - "network_partition": ネットワーク分断
        - "resource_exhaustion": リソース枯渇

        Args:
            scenario_name: シナリオ名

        Returns:
            List of experiment results
        """
        logger.info(f"[Chaos] Running scenario: {scenario_name}")

        scenarios = {
            "cascade_failure": [
                ("engine", "pod-kill", "10s"),
                ("gateway", "pod-kill", "20s"),
            ],
            "network_partition": [
                ("engine", "partition", "60s"),
            ],
            "resource_exhaustion": [
                ("engine", "stress", "60s"),
                ("gateway", "stress", "60s"),
            ]
        }

        if scenario_name not in scenarios:
            raise ValueError(f"Unknown scenario: {scenario_name}")

        results = []
        for target, action, duration in scenarios[scenario_name]:
            if action == "pod-kill":
                result = self.inject_pod_failure(target, duration=duration, action=action)
            elif action == "stress":
                result = self.inject_stress(target, cpu_cores=2, duration=duration)
            elif action == "partition":
                result = self.inject_network_delay(target, latency="1000ms", duration=duration)

            results.append(result)

        return results

    def list_active_experiments(self) -> List[Dict]:
        """
        実行中のChaosエクスペリメントを一覧表示

        Returns:
            List of active experiments
        """
        try:
            result = subprocess.run([
                "kubectl", "get", "podchaos,networkchaos,stresschaos",
                "-n", self.namespace,
                "-o", "json"
            ], capture_output=True, text=True, check=True)

            data = json.loads(result.stdout)
            experiments = data.get("items", [])

            logger.info(f"[Chaos] Found {len(experiments)} active experiments")
            return experiments

        except subprocess.CalledProcessError as e:
            logger.error(f"[Chaos] Failed to list experiments: {e.stderr}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"[Chaos] Failed to parse kubectl output: {e}")
            return []

    def delete_experiment(self, experiment_name: str, kind: str) -> bool:
        """
        Chaosエクスペリメントを削除（停止）

        Args:
            experiment_name: エクスペリメント名
            kind: リソースタイプ（podchaos, networkchaos, stresschaos）

        Returns:
            True if successful
        """
        logger.info(f"[Chaos] Deleting experiment: {experiment_name}")

        try:
            subprocess.run([
                "kubectl", "delete", kind,
                experiment_name,
                "-n", self.namespace
            ], check=True, capture_output=True)

            logger.info(f"[Chaos] Experiment deleted: {experiment_name}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"[Chaos] Failed to delete experiment: {e.stderr}")
            return False

    def _apply_experiment(self, experiment: Dict) -> Dict:
        """
        ChaosエクスペリメントをKubernetesに適用

        Args:
            experiment: Chaos experiment spec

        Returns:
            Applied experiment metadata
        """
        # Write to temp file
        temp_file = Path("/tmp/chaos_experiment.yaml")
        with open(temp_file, "w") as f:
            json.dump(experiment, f)

        try:
            # Apply with kubectl
            result = subprocess.run([
                "kubectl", "apply", "-f", str(temp_file)
            ], capture_output=True, text=True, check=True)

            logger.info(f"[Chaos] Experiment applied: {experiment['metadata']['name']}")

            return {
                "name": experiment["metadata"]["name"],
                "kind": experiment["kind"],
                "status": "applied",
                "message": result.stdout
            }

        except subprocess.CalledProcessError as e:
            logger.error(f"[Chaos] Failed to apply experiment: {e.stderr}")
            return {
                "name": experiment["metadata"]["name"],
                "kind": experiment["kind"],
                "status": "failed",
                "error": e.stderr
            }

# Convenience functions
def inject_pod_failure_simple(pod_name: str, duration: str = "30s") -> Dict:
    """
    簡易Pod障害注入

    Usage:
        from backend.chaos.chaos_manager import inject_pod_failure_simple

        inject_pod_failure_simple("engine", "30s")
    """
    manager = ChaosManager()
    return manager.inject_pod_failure(pod_name, duration=duration)

def run_full_chaos_test() -> List[Dict]:
    """
    フルChaosテストスイートを実行

    Returns:
        List of all experiment results
    """
    manager = ChaosManager()
    all_results = []

    scenarios = ["cascade_failure", "network_partition", "resource_exhaustion"]

    for scenario in scenarios:
        logger.info(f"[Chaos] Running scenario: {scenario}")
        results = manager.run_chaos_scenario(scenario)
        all_results.extend(results)

    return all_results
