"""
戦略基底クラスの定義

すべての戦略はこのクラスを継承して実装します。
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass
import sys
from pathlib import Path

# 親ディレクトリをパスに追加
sys.path.append(str(Path(__file__).parent.parent))

from burn_knobs import BurnState, apply_action_temperature, apply_ev_floor


@dataclass
class InfoSet:
    """
    情報集合（プレイヤーが観測できる情報）
    
    Attributes:
        hole_cards: ホールカード（例: ['As', 'Kh']）
        community_cards: コミュニティカード
        action_history: アクション履歴
        position: ポジション（'BTN', 'BB'など）
    """
    hole_cards: list
    community_cards: list
    action_history: list
    position: str


@dataclass
class StateFeatures:
    """
    状態特徴量（ゲーム状態の情報）
    
    Attributes:
        pot_size: ポットサイズ（bb単位）
        stack_size: スタックサイズ（bb単位）
        street: ストリート（'preflop', 'flop', 'turn', 'river'）
        to_call: コールに必要な額（bb単位）
        valid_actions: 有効なアクションのリスト
    """
    pot_size: float
    stack_size: float
    street: str
    to_call: float
    valid_actions: list


class Strategy(ABC):
    """
    戦略の基底クラス
    
    新しい戦略を追加する場合：
    1. このクラスを継承
    2. get_action() を実装
    3. STRATEGY_NAME クラス変数を定義（オプション）
    
    Example:
        class MyStrategy(Strategy):
            STRATEGY_NAME = "my_strategy"
            
            def get_action(self, info_set, state_features, burn_state):
                # 戦略ロジックを実装
                return {"fold": 0.3, "call": 0.5, "raise": 0.2}
    """
    
    STRATEGY_NAME: Optional[str] = None  # 戦略識別子（未定義時はクラス名を使用）
    
    @abstractmethod
    def get_action(
        self, 
        info_set: InfoSet, 
        state_features: StateFeatures, 
        burn_state: BurnState
    ) -> Dict[str, float]:
        """
        アクションを選択
        
        Args:
            info_set: 情報集合（カード、履歴など）
            state_features: 状態特徴量（ポット、スタックなど）
            burn_state: 焼却ノブの状態
        
        Returns:
            アクション分布 {action: probability}
            例: {"fold": 0.2, "call": 0.3, "raise": 0.5}
        """
        pass
    
    def get_name(self) -> str:
        """戦略名を取得"""
        return self.STRATEGY_NAME or self.__class__.__name__
    
    def apply_burn_state(
        self, 
        action_probs: Dict[str, float], 
        burn_state: BurnState,
        action_evs: Optional[Dict[str, float]] = None
    ) -> Dict[str, float]:
        """
        焼却ノブを適用してアクション分布を変換
        
        Args:
            action_probs: 元のアクション確率分布
            burn_state: 焼却状態
            action_evs: 各アクションのEV（オプション、EV下限制約に使用）
        
        Returns:
            焼却ノブ適用後のアクション分布
        """
        # EV下限制約を適用（EVが提供されている場合）
        if action_evs is not None and burn_state.ev_floor > 0:
            ev_floor_bb = burn_state.get_ev_floor_bb()
            valid_actions = apply_ev_floor(action_evs, ev_floor_bb)
            
            # 有効なアクションのみに確率を再分配
            valid_action_names = set(valid_actions.keys())
            action_probs = {
                action: prob 
                for action, prob in action_probs.items() 
                if action in valid_action_names
            }
            
            # 正規化
            total_prob = sum(action_probs.values())
            if total_prob > 0:
                action_probs = {
                    action: prob / total_prob 
                    for action, prob in action_probs.items()
                }
        
        # 行動温度を適用
        if burn_state.action_entropy > 0:
            action_probs = apply_action_temperature(
                action_probs, 
                burn_state.action_entropy
            )
        
        return action_probs
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.get_name()}')"


if __name__ == "__main__":
    # テスト用の簡易戦略
    class TestStrategy(Strategy):
        STRATEGY_NAME = "test_strategy"
        
        def get_action(self, info_set, state_features, burn_state):
            return {"fold": 0.2, "call": 0.3, "raise": 0.5}
    
    # テスト実行
    strategy = TestStrategy()
    print(f"戦略名: {strategy.get_name()}")
    
    # ダミーデータ
    info_set = InfoSet(
        hole_cards=['As', 'Kh'],
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
    burn_state = BurnState(
        range_distortion=0.0,
        action_entropy=0.5,
        ev_floor=0.0
    )
    
    action_probs = strategy.get_action(info_set, state_features, burn_state)



    print(f"アクション分布: {action_probs}")
