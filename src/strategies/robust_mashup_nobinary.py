import math
import random
import itertools
from typing import Dict, List, Tuple
from .base import Strategy, InfoSet, StateFeatures
from .equity_calculator import calculator
from burn_knobs import BurnState

# =================================================================
# 1. EMレンジモデル (バイナリ不要版)
# =================================================================
class EMRangeModel:
    def __init__(self):
        self.ranks = '23456789TJQKA'
        # 169通りの正規化ハンド (AA, AKs, AKo...) の重み
        self.weights = self._init_weights()

    def _init_weights(self) -> Dict[str, float]:
        labels = []
        for i, r1 in enumerate(self.ranks):
            for j, r2 in enumerate(self.ranks[i:], i):
                if r1 == r2: labels.append(r1 + r2)
                else:
                    labels.append(self.ranks[j] + self.ranks[i] + "s")
                    labels.append(self.ranks[j] + self.ranks[i] + "o")
        return {label: 1.0 for label in labels}

    def update(self, action: str, street: str, to_call: float, pot: float):
        """相手のアクションからレンジをベイズ更新"""
        bet_ratio = to_call / pot if pot > 0 else 0
        for label in self.weights:
            # 簡易的な尤度関数: 強い手ほどベットし、弱い手ほどチェック/フォールドする
            strength = self._get_rough_strength(label)
            likelihood = 0.5
            if action in ["raise", "bet"]:
                # 両極化(Value or Bluff)
                likelihood = math.exp(-(strength - 0.8)**2 / 0.2) + 0.2 * math.exp(-(strength - 0.2)**2 / 0.1)
            elif action == "call":
                likelihood = math.exp(-(strength - 0.5)**2 / 0.15)
            elif action == "fold":
                likelihood = math.exp(-(strength - 0.1)**2 / 0.4)
            
            self.weights[label] *= likelihood

        # 正規化
        total = sum(self.weights.values())
        if total > 0:
            for k in self.weights: self.weights[k] /= total

    def _get_rough_strength(self, label: str) -> float:
        r1 = self.ranks.index(label[0])
        r2 = self.ranks.index(label[1])
        return (r1 + r2) / 24.0

# =================================================================
# 2. メイン戦略クラス
# =================================================================
class RobustMashupNoBinaryStrategy(Strategy):
    STRATEGY_NAME = "robust_mashup_nobinary"

    def __init__(self):
        super().__init__()
        self.opp_model = EMRangeModel()
        self.ranks = '23456789TJQKA'

    def get_action(self, info: InfoSet, feats: StateFeatures, burn: BurnState) -> Dict[str, float]:
        # 相手のアクションがあればEM更新 (featsにlast_opp_actionがある想定)
        last_action = getattr(feats, 'last_opp_action', None)
        if last_action:
            self.opp_model.update(last_action, feats.street, feats.to_call, feats.pot_size)

        if feats.street == 'preflop':
            return self._preflop_strategy(info, feats, burn)
        else:
            return self._postflop_strategy(info, feats, burn)

    def _preflop_strategy(self, info: InfoSet, feats: StateFeatures, burn: BurnState) -> Dict[str, float]:
        """GTOApproxのスコアリングをベースにした頑健プリフロップ"""
        h1, h2 = info.hole_cards[0], info.hole_cards[1]
        r1, r2 = self.ranks.index(h1[0]) + 2, self.ranks.index(h2[0]) + 2
        suited = (h1[1] == h2[1])
        pair = (r1 == r2)
        
        # スコア計算 (GTOApprox継承)
        high, low = max(r1, r2), min(r1, r2)
        score = high * 2 + low + (2 if suited else 0) + (5 if pair else 0)
        hand_strength = (score - 8) / (47 - 8)

        # 焼却ノブ(Entropy)によるレンジの歪み
        # Entropyが高いほど、本来降りるべき手でも参加(Bully)する
        open_threshold = 0.2 - (burn.action_entropy * 0.15) # 0.2 -> 0.05
        
        if feats.to_call == 0: # 自分が最初のアクション
            if hand_strength > open_threshold:
                return {'raise': 1.0}
            return {'fold': 1.0}
        else: # 相手のレイズに直面
            pot_odds = feats.to_call / (feats.pot_size + feats.to_call)
            if hand_strength > 0.8: return {'raise': 0.4, 'call': 0.6}
            if hand_strength > pot_odds: return {'call': 1.0}
            return {'fold': 1.0}

    def _postflop_strategy(self, info: InfoSet, feats: StateFeatures, burn: BurnState) -> Dict[str, float]:
        """EMレンジ推定とS字減衰を統合したポストフロップ"""
        
        # 1. 重み付きEquityの算出 (相手のレンジを考慮)
        # 本来はEM重みを用いたサンプリングが必要だが、ここでは簡易的に
        # calculator.calculate_equityの結果をEMモデルの平均強度で補正
        base_equity = calculator.calculate_equity(info.hole_cards, info.community_cards, iterations=400)
        
        # 相手のレンジの平均的な強さを算出
        avg_opp_strength = sum(self.opp_model._get_rough_strength(l) * w for l, w in self.opp_model.weights.items())
        # 相手が強いレンジを持っているほど、自分のEquityを割り引く(EM補正)
        equity = base_equity * (1.0 / (avg_opp_strength + 0.5))
        equity = max(0, min(1.0, equity))

        # 2. S字減衰によるAlpha（攻撃性）の決定
        # ポットが大きくなるほど(40bb変曲点)、Entropyの影響を消してGTO(数学)に戻る
        pot_bb = feats.pot_size
        decay = 1.0 - (1.0 / (1.0 + math.exp(0.2 * (pot_bb - 40.0))))
        alpha = (1.0 / (1.0 + math.exp(-12.0 * (burn.action_entropy - 0.55)))) * decay

        # 3. 数理指標
        pot_odds = feats.to_call / (feats.pot_size + feats.to_call) if feats.to_call > 0 else 0
        mdf = 1.0 / (1.0 + (feats.to_call / feats.pot_size)) if feats.pot_size > 0 and feats.to_call > 0 else 1.0

        # 4. アクション決定
        if feats.to_call > 0: # 防御局面
            # 基本はEV(Equity > PotOdds)だが、Alphaが高い時はMDFを意識してブラフキャッチ
            # 相手がノイズ（ブラフ）を混ぜていると判断する
            defense_threshold = pot_odds * (1.0 - alpha * 0.3)
            if equity > defense_threshold:
                return {'call': 1.0}
            return {'fold': 1.0}
        
        else: # 攻撃局面 (Check or Raise)
            # 幾何学的サイジングの思想: 強い時は大きく打つ
            if equity > 0.7:
                return {'raise': 1.0}
            # Bullyロジック: Equityが低くてもAlphaが高ければブラフ
            elif equity < 0.3 and random.random() < (0.25 * alpha):
                return {'raise': 1.0}
            else:
                return {'call': 1.0} # Check

    def _get_hand_label(self, hole: List[str]) -> str:
        r1, r2 = self.ranks.index(hole[0][0]), self.ranks.index(hole[1][0])
        if r1 < r2: r1, r2 = r2, r1
        label = self.ranks[r1] + self.ranks[r2]
        if hole[0][1] == hole[1][1]: label += "s"
        elif r1 != r2: label += "o"
        return label