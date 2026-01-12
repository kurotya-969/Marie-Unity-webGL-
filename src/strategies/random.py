"""
ランダム戦略

温度付きランダム戦略（対照群）。
ベースラインとして、完全にランダムな行動を取る。
"""

import random
from typing import Dict
from .base import Strategy, InfoSet, StateFeatures
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from burn_knobs import BurnState


class RandomBot(Strategy):
    """
    ランダム戦略
    
    温度付きランダム行動を取る対照群。
    戦略の性能を評価するためのベースライン。
    """
    
    STRATEGY_NAME = "random"
    
    def __init__(self, base_temperature: float = 0.8):
        """
        Args:
            base_temperature: 基本温度 [0, 1]
                             0.0 = 完全にランダム（一様分布）
                             1.0 = やや偏りのあるランダム
        """
        self.base_temperature = base_temperature
    
    def get_action(
        self, 
        info_set: InfoSet, 
        state_features: StateFeatures, 
        burn_state: BurnState
    ) -> Dict[str, float]:
        """
        ランダムアクションを選択
        """
        valid_actions = state_features.valid_actions
        
        if not valid_actions:
            return {}
        
        # 基本的に一様分布
        if self.base_temperature < 0.5:
            # 完全ランダム
            action_probs = {
                action: 1.0 / len(valid_actions) 
                for action in valid_actions
            }
        else:
            # やや偏りのあるランダム
            # ランダムな重みを生成
            weights = [random.random() for _ in valid_actions]
            total_weight = sum(weights)
            
            action_probs = {
                action: weight / total_weight 
                for action, weight in zip(valid_actions, weights)
            }
        
        # 焼却ノブを適用（特に行動温度）
        return self.apply_burn_state(action_probs, burn_state)


if __name__ == "__main__":
    # テスト実行
    from burn_knobs import BurnState
    
    bot = RandomBot()
    print(f"戦略名: {bot.get_name()}")
    
    # テストケース
    info_set = InfoSet(
        hole_cards=['7h', '2d'],
        community_cards=[],
        action_history=[],
        position='BTN'
    )
    state_features = StateFeatures(
        pot_size=3.0,
        stack_size=200.0,
        street='preflop',
        to_call=2.0,
        valid_actions=['fold', 'call', 'raise']
    )
    
    # 複数回実行して分布を確認
    print("\n10回のアクション分布:")
    for i in range(10):
        burn_state = BurnState(0.0, 0.0, 0.0)
        action = bot.get_action(info_set, state_features, burn_state)
        print(f"{i+1}: {action}")
