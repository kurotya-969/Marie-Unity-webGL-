
import random
from typing import Dict
from .base import Strategy, InfoSet, StateFeatures
from .equity_calculator import calculator, card_str_to_int
from burn_knobs import BurnState

class HeuristicBot(Strategy):
    """
    Heuristic Bot (Odds-based).
    Calculates Equity vs Pot Odds.
    If +EV -> Bet/Raise for Value.
    If -EV -> Fold (unless Bluff).
    """
    
    STRATEGY_NAME = "heuristic"
    
    def get_action(self, info: InfoSet, feats: StateFeatures, burn: BurnState) -> Dict[str, float]:
        # Calculate Equity
        equity = calculator.calculate_equity(info.hole_cards, info.community_cards, iterations=500)
        
        # Calculate Pot Odds
        # Odds = Call Amount / (Pot + Call Amount)
        pot_odds = 0.0
        if feats.to_call > 0:
            pot_odds = feats.to_call / (feats.pot_size + feats.to_call)
            
        valid = feats.valid_actions
        can_check = 'call' in valid and feats.to_call == 0
        
        # Logic: Compare Equity to Pot Odds
        
        if can_check:
            # We are first to act or checked to.
            # Value Bet?
            if equity > 0.6: # Strong equity -> Value Bet
                return {'raise': 1.0}
            elif equity > 0.4: # Marginal -> Check/Call
                return {'call': 1.0}
            else: # Weak
                # Bluff?
                if random.random() < 0.15: # 15% Bluff frequency on check lines
                    return {'raise': 1.0}
                return {'call': 1.0} # Check
                
        else:
            # Facing Bet
            # Required Equity = Pot Odds
            
            # Add margin for "future streets" or "implied odds" conceptually?
            # Basic EV: Equity > Pot Odds -> Call
            
            if equity >= pot_odds:
                # +EV Call
                # Raise if very strong
                if equity > 0.75:
                    return {'raise': 0.8, 'call': 0.2} # Fast play strong hands
                return {'call': 1.0}
            else:
                # -EV Call
                # Fold unless Bluff Raise
                if random.random() < 0.05: # Rare bluff raise vs bet
                    return {'raise': 1.0}
                return {'fold': 1.0}

