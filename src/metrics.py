"""
評価指標の計算

戦略の性能を評価するための指標を計算します。
"""

import numpy as np
from typing import List, Dict, Tuple
from dataclasses import dataclass


@dataclass
class HandResult:
    """
    1ハンドの結果
    
    Attributes:
        hand_id: ハンドID
        profit: 利益（bb単位）
        actions: アクション履歴
    """
    hand_id: int
    profit: float
    actions: List[str]


@dataclass
class MatchMetrics:
    """
    対戦の評価指標
    
    Attributes:
        winrate_bb100: Winrate（bb/100ハンド）
        exploitability: Exploitability（簡易版）
        variance: Winrateの分散
        hand_count: ハンド数
        total_profit: 総利益（bb単位）
        min_profit: 最小利益
        max_profit: 最大利益
    """
    winrate_bb100: float
    exploitability: float
    variance: float
    hand_count: int
    total_profit: float
    min_profit: float
    max_profit: float
    
    def to_dict(self) -> dict:
        """辞書形式に変換"""
        return {
            'winrate_bb100': self.winrate_bb100,
            'exploitability': self.exploitability,
            'variance': self.variance,
            'hand_count': self.hand_count,
            'total_profit': self.total_profit,
            'min_profit': self.min_profit,
            'max_profit': self.max_profit
        }


class MetricsCalculator:
    """評価指標の計算器"""
    
    @staticmethod
    def calculate_winrate(results: List[HandResult]) -> float:
        """
        Winrateを計算（bb/100ハンド）
        
        Args:
            results: ハンド結果のリスト
        
        Returns:
            Winrate（bb/100）
        """
        if not results:
            return 0.0
        
        total_profit = sum(r.profit for r in results)
        hand_count = len(results)
        
        # bb/100ハンド
        winrate = (total_profit / hand_count) * 100
        
        return winrate
    
    @staticmethod
    def calculate_variance(results: List[HandResult]) -> float:
        """
        Winrateの分散を計算
        
        Args:
            results: ハンド結果のリスト
        
        Returns:
            分散
        """
        if not results:
            return 0.0
        
        profits = [r.profit for r in results]
        return float(np.var(profits))
    
    @staticmethod
    def calculate_exploitability_simple(
        winrate_vs_gto: float,
        theoretical_max: float = 10.0
    ) -> float:
        """
        Exploitabilityを計算（簡易版）
        
        対GTO戦略での損失率を使用
        
        Args:
            winrate_vs_gto: 対GTO戦略でのWinrate
            theoretical_max: 理論的最大Winrate
        
        Returns:
            Exploitability [0, 1]
        """
        # 負のWinrateほどExploitabilityが高い
        if winrate_vs_gto >= 0:
            return 0.0
        
        exploitability = abs(winrate_vs_gto) / theoretical_max
        return min(1.0, exploitability)
    
    @staticmethod
    def calculate_metrics(
        results: List[HandResult],
        winrate_vs_gto: float = None
    ) -> MatchMetrics:
        """
        すべての評価指標を計算
        
        Args:
            results: ハンド結果のリスト
            winrate_vs_gto: 対GTO戦略でのWinrate（オプション）
        
        Returns:
            評価指標
        """
        if not results:
            return MatchMetrics(
                winrate_bb100=0.0,
                exploitability=0.0,
                variance=0.0,
                hand_count=0,
                total_profit=0.0,
                min_profit=0.0,
                max_profit=0.0
            )
        
        profits = [r.profit for r in results]
        
        winrate = MetricsCalculator.calculate_winrate(results)
        variance = MetricsCalculator.calculate_variance(results)
        
        # Exploitability（対GTOのWinrateが提供されている場合）
        if winrate_vs_gto is not None:
            exploitability = MetricsCalculator.calculate_exploitability_simple(
                winrate_vs_gto
            )
        else:
            # デフォルト：Winrateから推定
            exploitability = MetricsCalculator.calculate_exploitability_simple(
                winrate
            )
        
        return MatchMetrics(
            winrate_bb100=winrate,
            exploitability=exploitability,
            variance=variance,
            hand_count=len(results),
            total_profit=sum(profits),
            min_profit=min(profits),
            max_profit=max(profits)
        )
    
    @staticmethod
    def calculate_exploitability_range(
        metrics_list: List[MatchMetrics]
    ) -> Tuple[float, float]:
        """
        Exploitabilityレンジを計算
        
        Args:
            metrics_list: 評価指標のリスト
        
        Returns:
            (最小Exploitability, 最大Exploitability)
        """
        if not metrics_list:
            return (0.0, 0.0)
        
        exploitabilities = [m.exploitability for m in metrics_list]
        return (min(exploitabilities), max(exploitabilities))
    
    @staticmethod
    def detect_collapse_points(
        burn_trajectory: List[Tuple[float, float]],
        threshold: float = 5.0
    ) -> List[int]:
        """
        崩壊点を検出
        
        ノブを連続変化させたときの非連続な性能劣化点を検出
        
        Args:
            burn_trajectory: [(burn_value, winrate), ...]
            threshold: 崩壊判定の閾値（Winrateの変化量）
        
        Returns:
            崩壊点のインデックスリスト
        """
        if len(burn_trajectory) < 2:
            return []
        
        winrates = [wr for _, wr in burn_trajectory]
        
        # 1階微分で急激な変化を検出
        gradients = np.gradient(winrates)
        
        # 閾値を超える変化点
        collapse_points = np.where(np.abs(gradients) > threshold)[0]
        
        return collapse_points.tolist()


if __name__ == "__main__":
    # テスト実行
    print("評価指標計算のテスト\n")
    
    # ダミーデータ
    results = [
        HandResult(1, 2.5, ["raise", "call", "bet", "fold"]),
        HandResult(2, -1.0, ["call", "fold"]),
        HandResult(3, 5.0, ["raise", "raise", "call"]),
        HandResult(4, -0.5, ["fold"]),
        HandResult(5, 3.0, ["call", "raise", "call"]),
    ]
    
    # 評価指標を計算
    metrics = MetricsCalculator.calculate_metrics(results)
    
    print(f"Winrate: {metrics.winrate_bb100:.2f} bb/100")
    print(f"分散: {metrics.variance:.2f}")
    print(f"Exploitability: {metrics.exploitability:.3f}")
    print(f"ハンド数: {metrics.hand_count}")
    print(f"総利益: {metrics.total_profit:.2f} bb")
    print(f"利益レンジ: [{metrics.min_profit:.2f}, {metrics.max_profit:.2f}] bb")
    
    # 崩壊点検出のテスト
    print("\n崩壊点検出のテスト")
    trajectory = [
        (0.0, 5.0),
        (0.25, 4.8),
        (0.5, 4.5),
        (0.75, -2.0),  # 崩壊点
        (1.0, -3.0),
    ]
    
    collapse_points = MetricsCalculator.detect_collapse_points(trajectory)
    print(f"崩壊点: {collapse_points}")
