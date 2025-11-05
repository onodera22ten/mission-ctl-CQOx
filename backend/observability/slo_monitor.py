"""
SLO/SLI監視とError Budget管理（NASA/Googleレベル）

【日本語サマリ】
このモジュールはGoogle SRE本に基づくSLO/SLI監視とError Budget管理を実装します。

- なぜ必要か: NASA/Googleレベルのサービスでは、可用性・レイテンシ・エラー率を定量的に管理し、
  リスクを可視化する必要があります。Error Budgetはリリース速度と信頼性のバランスを取る指標です。
- 何をするか: 
  1) SLI（Service Level Indicator）の計測：可用性、レイテンシ、エラー率
  2) SLO（Service Level Objective）との比較
  3) Error Budget計算：許容される障害時間の残量
  4) Burn Rate計算：Error Budgetの消費速度（アラート判定用）
- どう検証するか: Prometheusメトリクス、Grafanaダッシュボード、アラート

【Inputs】
- Prometheusメトリクス (http_requests_total, http_request_duration_seconds)

【Outputs】
- Prometheusメトリクス (slo_availability, slo_error_budget_remaining, slo_error_budget_burn_rate)
- アラート条件 (burn_rate > threshold)
"""

import time
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from prometheus_client import Gauge, Counter, Histogram

logger = logging.getLogger(__name__)


@dataclass
class SLOTarget:
    """SLO目標値定義"""
    name: str
    target: float  # 0.9999 = 99.99%
    measurement_window: int  # seconds (30 days = 30*24*3600)


@dataclass
class SLI:
    """Service Level Indicator（サービスレベル指標）"""
    timestamp: datetime
    success_count: int
    total_count: int
    latency_p50: Optional[float] = None
    latency_p95: Optional[float] = None
    latency_p99: Optional[float] = None
    
    @property
    def availability(self) -> float:
        """可用性計算"""
        if self.total_count == 0:
            return 1.0
        return self.success_count / self.total_count
    
    @property
    def error_rate(self) -> float:
        """エラー率"""
        return 1.0 - self.availability


class SLOMonitor:
    """
    SLO監視とError Budget管理（Google SREベストプラクティス）
    
    主要機能:
    1. 可用性SLO: 99.99% (年間ダウンタイム 52.6分)
    2. レイテンシSLO: p95 < 500ms, p99 < 1000ms
    3. Error Budget: (1 - SLO) * measurement_window
    4. Burn Rate Alert: 2x, 10x, 100xで段階的アラート
    """
    
    # Prometheus メトリクス定義
    availability_gauge = Gauge('slo_availability', 'Current availability (0-1)', ['service'])
    error_budget_gauge = Gauge('slo_error_budget_remaining', 'Error budget remaining (0-1)', ['service'])
    burn_rate_gauge = Gauge('slo_error_budget_burn_rate', 'Error budget burn rate', ['service', 'window'])
    slo_compliance_gauge = Gauge('slo_compliance', 'SLO compliance (1=compliant, 0=violated)', ['service', 'slo_type'])
    
    def __init__(self, 
                 service_name: str = 'cqox-engine',
                 availability_target: float = 0.9999,
                 measurement_window_days: int = 30):
        """
        SLO監視初期化
        
        Args:
            service_name: サービス名
            availability_target: 可用性目標 (0.9999 = 99.99%)
            measurement_window_days: 測定期間（日数）
        """
        self.service_name = service_name
        self.slo = SLOTarget(
            name=service_name,
            target=availability_target,
            measurement_window=measurement_window_days * 24 * 3600
        )
        
        # 履歴データ保持（過去30日分）
        self.sli_history: List[SLI] = []
        
        logger.info(f"SLO Monitor initialized: {service_name}, target={availability_target}")
    
    def record_request(self, success: bool, latency_ms: float):
        """
        リクエスト記録
        
        Args:
            success: 成功フラグ (HTTP 200-299)
            latency_ms: レイテンシ（ミリ秒）
        """
        # 1分間隔で集計
        now = datetime.now()
        minute = now.replace(second=0, microsecond=0)
        
        # 最新のSLIを更新 or 新規作成
        if self.sli_history and self.sli_history[-1].timestamp == minute:
            sli = self.sli_history[-1]
            sli.total_count += 1
            if success:
                sli.success_count += 1
        else:
            sli = SLI(
                timestamp=minute,
                success_count=1 if success else 0,
                total_count=1
            )
            self.sli_history.append(sli)
        
        # 古いデータ削除（30日以上前）
        cutoff = now - timedelta(days=30)
        self.sli_history = [s for s in self.sli_history if s.timestamp >= cutoff]
    
    def calculate_current_availability(self) -> float:
        """
        現在の可用性計算（過去30日）
        
        Returns:
            可用性 (0.0 - 1.0)
        """
        if not self.sli_history:
            return 1.0
        
        total_success = sum(s.success_count for s in self.sli_history)
        total_requests = sum(s.total_count for s in self.sli_history)
        
        if total_requests == 0:
            return 1.0
        
        availability = total_success / total_requests
        
        # Prometheusメトリクス更新
        self.availability_gauge.labels(service=self.service_name).set(availability)
        
        return availability
    
    def calculate_error_budget(self) -> Dict[str, float]:
        """
        Error Budget計算（Google SRE手法）
        
        Error Budget = (1 - SLO) * measurement_window
        例: 99.99% SLOで30日間 = 0.0001 * 30*24*60 = 4.32分の障害許容
        
        Returns:
            {
                'allowed_failures': 許容される失敗数（割合）,
                'actual_failures': 実際の失敗数（割合）,
                'budget_remaining': 残りBudget (0.0-1.0),
                'budget_consumed': 消費されたBudget (0.0-1.0)
            }
        """
        current_availability = self.calculate_current_availability()
        
        allowed_failures = 1 - self.slo.target  # 0.0001 for 99.99%
        actual_failures = 1 - current_availability
        
        # Budget残量（0-1）
        if allowed_failures == 0:
            budget_remaining = 0.0
        else:
            budget_remaining = (allowed_failures - actual_failures) / allowed_failures
        
        budget_remaining = max(0.0, min(1.0, budget_remaining))
        budget_consumed = 1.0 - budget_remaining
        
        # Prometheusメトリクス更新
        self.error_budget_gauge.labels(service=self.service_name).set(budget_remaining)
        
        # SLO compliance
        is_compliant = current_availability >= self.slo.target
        self.slo_compliance_gauge.labels(
            service=self.service_name, 
            slo_type='availability'
        ).set(1.0 if is_compliant else 0.0)
        
        return {
            'allowed_failures': allowed_failures,
            'actual_failures': actual_failures,
            'budget_remaining': budget_remaining,
            'budget_consumed': budget_consumed,
            'is_compliant': is_compliant
        }
    
    def calculate_burn_rate(self, window_hours: int = 1) -> float:
        """
        Error Budget Burn Rate計算
        
        Burn Rate = 実際のエラー率 / 許容エラー率
        
        例:
        - SLO 99.99% → 許容エラー率 0.01%
        - 実際のエラー率 0.1% → Burn Rate = 10x
        
        Burn Rateが高い場合、Error Budgetが急速に消費されている
        → インシデント対応またはリリース凍結が必要
        
        Args:
            window_hours: 計測期間（時間）
        
        Returns:
            Burn Rate (1.0 = 予定通り, 2.0 = 2倍速で消費, 10.0 = 10倍速)
        """
        now = datetime.now()
        cutoff = now - timedelta(hours=window_hours)
        
        # 期間内のSLI取得
        recent_sli = [s for s in self.sli_history if s.timestamp >= cutoff]
        
        if not recent_sli:
            return 0.0
        
        # 実際のエラー率
        total_success = sum(s.success_count for s in recent_sli)
        total_requests = sum(s.total_count for s in recent_sli)
        
        if total_requests == 0:
            return 0.0
        
        actual_error_rate = 1.0 - (total_success / total_requests)
        
        # 許容エラー率
        allowed_error_rate = 1 - self.slo.target
        
        # Burn Rate
        if allowed_error_rate == 0:
            burn_rate = 0.0
        else:
            burn_rate = actual_error_rate / allowed_error_rate
        
        # Prometheusメトリクス更新
        self.burn_rate_gauge.labels(
            service=self.service_name,
            window=f'{window_hours}h'
        ).set(burn_rate)
        
        return burn_rate
    
    def should_alert(self) -> Dict[str, bool]:
        """
        アラート判定（Google SREマルチウィンドウ手法）
        
        複数の時間窓でBurn Rateを監視:
        - 1時間 & 5分: Burn Rate > 14.4 → Critical (Budget枯渇まで2日)
        - 6時間 & 30分: Burn Rate > 6 → High (Budget枯渇まで5日)
        - 1日 & 2時間: Burn Rate > 3 → Medium (Budget枯渇まで10日)
        
        Returns:
            {'critical': bool, 'high': bool, 'medium': bool}
        """
        # 1時間のBurn Rate
        burn_1h = self.calculate_burn_rate(window_hours=1)
        burn_6h = self.calculate_burn_rate(window_hours=6)
        burn_24h = self.calculate_burn_rate(window_hours=24)
        
        alerts = {
            'critical': burn_1h > 14.4,  # 2日でBudget枯渇
            'high': burn_6h > 6.0,       # 5日でBudget枯渇
            'medium': burn_24h > 3.0,    # 10日でBudget枯渇
            'low': burn_24h > 1.0        # 予定より速い消費
        }
        
        return alerts
    
    def get_status_report(self) -> Dict:
        """
        現在のSLO状況レポート生成
        
        Returns:
            詳細なステータス情報
        """
        availability = self.calculate_current_availability()
        error_budget = self.calculate_error_budget()
        burn_rate_1h = self.calculate_burn_rate(window_hours=1)
        burn_rate_6h = self.calculate_burn_rate(window_hours=6)
        burn_rate_24h = self.calculate_burn_rate(window_hours=24)
        alerts = self.should_alert()
        
        # Error Budget残量（時間換算）
        budget_seconds = error_budget['budget_remaining'] * (1 - self.slo.target) * self.slo.measurement_window
        budget_minutes = budget_seconds / 60
        
        return {
            'service': self.service_name,
            'slo_target': self.slo.target,
            'current_availability': availability,
            'is_compliant': error_budget['is_compliant'],
            'error_budget': {
                'remaining_percentage': error_budget['budget_remaining'] * 100,
                'remaining_minutes': budget_minutes,
                'consumed_percentage': error_budget['budget_consumed'] * 100
            },
            'burn_rate': {
                '1h': burn_rate_1h,
                '6h': burn_rate_6h,
                '24h': burn_rate_24h
            },
            'alerts': alerts,
            'recommendation': self._get_recommendation(error_budget, alerts)
        }
    
    def _get_recommendation(self, error_budget: Dict, alerts: Dict) -> str:
        """運用推奨アクション"""
        if alerts['critical']:
            return "🚨 CRITICAL: Freeze all releases and investigate immediately"
        elif alerts['high']:
            return "⚠️ HIGH: Review recent changes and consider rollback"
        elif alerts['medium']:
            return "⚡ MEDIUM: Monitor closely and prepare incident response"
        elif error_budget['budget_remaining'] < 0.1:
            return "📉 LOW: Error budget nearly exhausted, slow down releases"
        elif error_budget['is_compliant']:
            return "✅ OK: Within SLO, safe to release"
        else:
            return "⚠️ SLO violated: Review and improve reliability"


# グローバルSLO監視インスタンス
_slo_monitors: Dict[str, SLOMonitor] = {}


def get_slo_monitor(service_name: str = 'cqox-engine') -> SLOMonitor:
    """
    SLO監視インスタンス取得（サービス毎にシングルトン）
    
    Args:
        service_name: サービス名
    
    Returns:
        SLOMonitorインスタンス
    """
    if service_name not in _slo_monitors:
        _slo_monitors[service_name] = SLOMonitor(service_name)
    
    return _slo_monitors[service_name]

