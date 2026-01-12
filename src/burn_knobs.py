"""
焼却ノブ（Burn Knobs）の定義

戦略の前提を連続的に破壊するパラメータを定義します。
すべてのノブは [0.0, 1.0] に正規化されています。
"""

from dataclasses import dataclass
from typing import List, Tuple
import numpy as np
from scipy.stats import qmc


@dataclass
class BurnState:
    """
    焼却状態を表すデータクラス
    
    Attributes:
        range_distortion: レンジ歪み率 [0, 1]
            0.0 = 完全GTOレンジ
            1.0 = EV下限のみ満たす超ルースレンジ
        
        action_entropy: 行動温度 [0, 1]
            0.0 = 確定行動（argmax）
            1.0 = 一様ランダム
        
        ev_floor: EV下限制約 [0, 1] (内部的には [-10, 0] にマッピング)
            期待値がこの値以下の行動を禁止
    """
    range_distortion: float
    action_entropy: float
    ev_floor: float
    
    def __post_init__(self):
        """値の範囲チェック"""
        for field_name in ['range_distortion', 'action_entropy', 'ev_floor']:
            value = getattr(self, field_name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{field_name} must be in [0.0, 1.0], got {value}")
    
    def to_dict(self) -> dict:
        """辞書形式に変換"""
        return {
            'range_distortion': self.range_distortion,
            'action_entropy': self.action_entropy,
            'ev_floor': self.ev_floor
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'BurnState':
        """辞書から生成"""
        return cls(**data)
    
    def get_ev_floor_bb(self) -> float:
        """
        EV下限をbb単位に変換
        
        Returns:
            EV下限値（bb単位）[-10, 0]
        """
        return self.ev_floor * -10.0


def generate_burn_states(knob_values: List[float] = None) -> List[BurnState]:
    """
    焼却状態の組み合わせを生成
    
    Args:
        knob_values: 各ノブの取りうる値のリスト
                     デフォルト: [0.0, 0.25, 0.5, 0.75, 1.0]
    
    Returns:
        焼却状態のリスト（5³ = 125状態）
    """
    if knob_values is None:
        knob_values = [0.0, 0.25, 0.5, 0.75, 1.0]
    
    burn_states = []
    for r in knob_values:
        for t in knob_values:
            for e in knob_values:
                burn_states.append(BurnState(
                    range_distortion=r,
                    action_entropy=t,
                    ev_floor=e
                ))
    
    return burn_states


def generate_sobol_states(n_samples: int = 100, seed: int = 42) -> List[BurnState]:
    """
    Sobol列を使用して均一な焼却状態を生成
    
    Args:
        n_samples: 生成するサンプル数（デフォルト: 100）
        seed: 乱数シード（スクランブル用）
    
    Returns:
        焼却状態のリスト
    """
    # 3次元のSobol列生成器（レンジ歪み、行動温度、EV下限）
    # Scipy 1.7.0+ required
    sampler = qmc.Sobol(d=3, scramble=True, seed=seed)
    
    # 2の累乗個生成するのがSobol列の特性上望ましいが、指定数で切り取る
    # 少し多めに生成してクリップするのも手だが、ここではシンプルに
    sample = sampler.random(n=n_samples)
    
    burn_states = []
    for s in sample:
        # s は [0, 1) の範囲
        burn_states.append(BurnState(
            range_distortion=float(s[0]),
            action_entropy=float(s[1]),
            ev_floor=float(s[2])
        ))
        
    return burn_states


def apply_action_temperature(action_probs: dict, temperature: float) -> dict:
    """
    ソフトマックス温度でアクション分布を調整
    
    Args:
        action_probs: 元のアクション確率分布 {action: probability}
        temperature: 温度パラメータ [0, 1]
    
    Returns:
        温度調整後の確率分布
    """
    if not action_probs:
        return {}
    
    actions = list(action_probs.keys())
    probs = np.array(list(action_probs.values()))
    
    # 温度 = 0: argmax（最大確率のアクションのみ）
    if temperature == 0.0:
        max_idx = np.argmax(probs)
        result = {action: 0.0 for action in actions}
        result[actions[max_idx]] = 1.0
        return result
    
    # 温度 = 1: 一様分布
    if temperature == 1.0:
        uniform_prob = 1.0 / len(actions)
        return {action: uniform_prob for action in actions}
    
    # 中間: ソフトマックス温度スケーリング
    # 実効温度: T_effective = 1 / (1 - temperature + epsilon)
    epsilon = 1e-8
    T_effective = 1.0 / (1.0 - temperature + epsilon)
    
    # ログ確率を温度でスケーリング
    log_probs = np.log(probs + epsilon)
    scaled_log_probs = log_probs / T_effective
    
    # ソフトマックスで正規化
    exp_probs = np.exp(scaled_log_probs - np.max(scaled_log_probs))
    normalized_probs = exp_probs / np.sum(exp_probs)
    
    return {action: float(prob) for action, prob in zip(actions, normalized_probs)}


def apply_ev_floor(action_evs: dict, ev_floor_bb: float) -> dict:
    """
    EV下限を満たさないアクションをフィルタ
    
    Args:
        action_evs: 各アクションのEV {action: ev_in_bb}
        ev_floor_bb: EV下限値（bb単位）
    
    Returns:
        フィルタ後のアクション集合
    """
    if not action_evs:
        return {}
    
    # EV >= ev_floor のアクションのみ残す
    valid_actions = {
        action: ev 
        for action, ev in action_evs.items() 
        if ev >= ev_floor_bb
    }
    
    # すべてマスクされた場合はフォールバック（最もEVが高いアクション）
    if not valid_actions:
        best_action = max(action_evs, key=action_evs.get)
        return {best_action: action_evs[best_action]}
    
    return valid_actions


if __name__ == "__main__":
    # テスト実行
    print("焼却状態の生成テスト")
    states = generate_burn_states()
    print(f"生成された状態数: {len(states)}")
    print(f"最初の状態: {states[0]}")
    print(f"最後の状態: {states[-1]}")
    
    print("\n行動温度の適用テスト")
    test_probs = {"fold": 0.1, "call": 0.3, "raise": 0.6}
    for temp in [0.0, 0.5, 1.0]:
        result = apply_action_temperature(test_probs, temp)
        print(f"温度={temp}: {result}")
    
    print("\nEV下限フィルタのテスト")
    test_evs = {"fold": -2.0, "call": -0.5, "raise": 1.5}
    for floor in [-3.0, -1.0, 0.0]:
        result = apply_ev_floor(test_evs, floor)
        print(f"EV下限={floor}bb: {result}")
