
import random
from typing import Dict, List
from .base import Strategy, InfoSet, StateFeatures
from .equity_calculator import calculator
from burn_knobs import BurnState

class GTOApproxBot(Strategy):
    """
    Improved GTO Approx Strategy.
    Preflop: Realistic Ranges.
    Postflop: Equity + MDF based logic.
    """
    
    STRATEGY_NAME = "gto_approx"
    
    def __init__(self, equity_boost: float = 0.0, range_widen: float = 0.0):
        self.equity_boost = equity_boost
        self.range_widen = range_widen
        self.preflop_ranges = self._init_preflop_ranges()
        
    def _init_preflop_ranges(self) -> Dict:
        # Realistic HU Ranges (Simplified)
        # Top 80% for Open
        # Top 20% for 3Bet
        # Pairs, Suited Broadways, Suited Connectors, Offsuit Broadways + Aces
        base = {
            'raise_first': 0.80, # Open 80% of hands from BTN
            'call_vs_raise': 0.60, # Defend 60% vs Open
            '3bet': 0.15 # 3Bet top 15%
        }
        
        # Apply widening if requested
        if self.range_widen > 0:
            base['raise_first'] = min(1.0, base['raise_first'] + self.range_widen)
            base['call_vs_raise'] = min(1.0, base['call_vs_raise'] + self.range_widen)
            base['3bet'] = min(1.0, base['3bet'] + self.range_widen)
            
        return base
        
    def get_action(self, info: InfoSet, feats: StateFeatures, burn: BurnState) -> Dict[str, float]:
        if feats.street == 'preflop':
            return self._preflop_strategy(info, feats)
        else:
            return self._postflop_strategy(info, feats)

    def _preflop_strategy(self, info: InfoSet, feats: StateFeatures) -> Dict[str, float]:
        # Very simplified Preflop Logic based on "Rank High Card" heuristic roughly
        # simulating the top X% range.
        
        # Convert cards to rank value for estimation
        # A=14, K=13... 2=2
        ranks = '23456789TJQKA'
        h1 = info.hole_cards[0]; h2 = info.hole_cards[1]
        r1 = ranks.index(h1[0]) + 2
        r2 = ranks.index(h2[0]) + 2
        
        suited = (h1[1] == h2[1])
        pair = (r1 == r2)
        
        # Simple Score: High * 2 + Low + (2 if suited) + (5 if pair)
        high = max(r1, r2)
        low = min(r1, r2)
        score = high * 2 + low + (2 if suited else 0) + (5 if pair else 0)
        # Max score (AA): 14*2 + 14 + 5 = 47
        # Min score (32o): 3*2 + 2 = 8
        
        # Normalized score roughly 0-1
        # Thresholds tuned to approximate percentages
        hand_strength = (score - 8) / (47 - 8)
        
        valid = feats.valid_actions
        can_check = 'call' in valid and feats.to_call == 0
        
        if info.position == 'BTN':
            # We are first to act (or facing limp/raise)
            # If to_call == 0 (First action)
            if feats.to_call == 0:
                if hand_strength > (1.0 - self.preflop_ranges['raise_first']): # Top 80%
                    return {'raise': 1.0}
                else:
                    return {'fold': 1.0} # Limp? No, simplify to Raise/Fold
            else:
                # Facing re-raise
                if hand_strength > 0.7: # 4Bet/Call
                    return {'call': 0.5, 'raise': 0.5}
                elif hand_strength > 0.4:
                    return {'call': 1.0}
                return {'fold': 1.0}
                
        else: # BB
            # Facing Open
            if feats.to_call > 0:
                if hand_strength > 0.85: # 3Bet
                    return {'raise': 1.0}
                elif hand_strength > (1.0 - self.preflop_ranges['call_vs_raise']): # Defend
                    return {'call': 1.0}
                else:
                    return {'fold': 1.0}
            else:
                # Option (Limp pot)
                if hand_strength > 0.6:
                    return {'raise': 1.0}
                return {'call': 1.0} # Check
                
    def _postflop_strategy(self, info: InfoSet, feats: StateFeatures) -> Dict[str, float]:
        # Equity Calculation
        equity = calculator.calculate_equity(info.hole_cards, info.community_cards, iterations=500)
        
        # Apply Boost (Overconfidence)
        equity = min(1.0, equity + self.equity_boost)
        
        # Pot Odds
        # amount to call / (total pot after call)
        # if to_call = 10, current pot = 100. Total = 110. Odds = 10/110 = 0.09
        
        pot_odds = 0.0
        if feats.to_call > 0:
            pot_odds = feats.to_call / (feats.pot_size + feats.to_call)
        
        # MDF Logic (Minimum Defense Frequency)
        # MDF = 1 - (Bet / (Pot + Bet)) = Pot / (Pot + Bet) = 1 / (1 + Bet/Pot)
        # If opponent bets pot, MDF = 0.5. We should save top 50% of range.
        # But here we don't know our range rank perfectly.
        # We use Equity as proxy.
        
        valid = feats.valid_actions
        can_check = 'call' in valid and feats.to_call == 0
        
        if can_check:
            # We are aggressor or checked to.
            # Value Bet?
            if equity > 0.7: # Strong Value
                return {'raise': 1.0}
            elif equity > 0.5: # Marginal/Check
                return {'call': 1.0}
            elif equity < 0.2: # Bluff candidate (Draws are captured in equity somewhat, but pure trash low equity)
                if random.random() < 0.2: # Semi-bluff 20%
                     return {'raise': 1.0}
                return {'call': 1.0} # Check
            else:
                return {'call': 1.0}
        else:
            # Facing bet
            if equity >= pot_odds:
                # Positive EV call
                if equity > 0.7: # Raise for value
                    return {'raise': 0.3, 'call': 0.7}
                return {'call': 1.0}
            else:
                # Negative EV pure call?
                # Check for bluff raise?
                if random.random() < 0.05: # Occasional bluff raise
                    return {'raise': 1.0}
                return {'fold': 1.0}

