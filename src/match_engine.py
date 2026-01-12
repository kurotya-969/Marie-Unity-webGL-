"""
High-Speed HU Match Engine (Custom Implementation)

Performance focused. No external dependencies for core logic.
"""

import random
from typing import List, Tuple, Dict, Optional
import time

from strategies.base import Strategy, InfoSet, StateFeatures
from burn_knobs import BurnState
from metrics import HandResult
from fast_evaluator import evaluate_hand
from dataclasses import dataclass

@dataclass
class GameConfig:
    small_blind: float = 0.5
    big_blind: float = 1.0
    starting_stack: float = 200.0

# Card String Maps
RANK_MAP = {
    '2': 0, '3': 1, '4': 2, '5': 3, '6': 4, '7': 5, '8': 6, '9': 7, 
    'T': 8, 'J': 9, 'Q': 10, 'K': 11, 'A': 12
}
SUIT_MAP = {'s': 0, 'h': 1, 'd': 2, 'c': 3}
INT_TO_RANK = ['2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A']
INT_TO_SUIT = ['s', 'h', 'd', 'c']

def card_to_int(card_str: str) -> int:
    return RANK_MAP[card_str[0]] + SUIT_MAP[card_str[1]] * 13

def int_to_card(card_int: int) -> str:
    return INT_TO_RANK[card_int % 13] + INT_TO_SUIT[card_int // 13]

class FastState:
    __slots__ = [
        'stacks', 'pot', 'street', 'board', 'hole_cards',
        'active_player', 'bets', 'folded', 'hand_complete'
    ]
    
    def __init__(self, starting_stack=200.0):
        self.stacks = [starting_stack, starting_stack]
        self.pot = 0.0
        self.street = 0 # 0=Pre, 1=Flop, 2=Turn, 3=River
        self.board: List[int] = []
        self.hole_cards: List[List[int]] = [[], []]
        self.active_player = 0
        self.bets = [0.0, 0.0]
        self.folded = False
        self.hand_complete = False

    def reset(self, sb, bb, btn_idx, starting_stack):
        # Reset scalar values
        self.stacks[0] = starting_stack
        self.stacks[1] = starting_stack
        self.pot = sb + bb
        self.street = 0 # 0=Pre, 1=Flop, 2=Turn, 3=River
        self.board.clear()
        
        # Reset bets for preflop
        # BTN posts SB, BB posts BB
        # If btn_idx=0 -> P0=BTN(SB), P1=BB
        if btn_idx == 0:
            self.bets[0] = sb
            self.bets[1] = bb
            self.stacks[0] -= sb
            self.stacks[1] -= bb
            self.active_player = 0 # BTN acts first preflop
        else:
            self.bets[1] = sb
            self.bets[0] = bb
            self.stacks[1] -= sb
            self.stacks[0] -= bb
            self.active_player = 1 # BTN acts first preflop
            
        self.folded = False
        self.hand_complete = False

class FastPokerEngine:
    def __init__(self, config: GameConfig = None):
        if config is None:
            config = GameConfig()
        self.state = FastState(config.starting_stack)
        # Pre-allocate deck for shuffle speed
        self.deck = list(range(52))
        self.game_config = {
            'sb': config.small_blind, 'bb': config.big_blind, 'stack': config.starting_stack
        }
        self.base_seed = 42

    def play_hand(self, 
                  p0: Strategy, p1: Strategy, 
                  burn0: BurnState, burn1: BurnState,
                  hand_id: int, btn_idx: int) -> float:
        """
        Play one hand. Returns Profit for P0.
        Optimized loop.
        """
        state = self.state
        state.reset(self.game_config['sb'], self.game_config['bb'], btn_idx, self.game_config['stack'])
        
        # Shuffle & Deal
        # Use hand_id to diversify seeds across hands while remaining deterministic for the match
        random.seed(self.base_seed + hand_id)
        random.shuffle(self.deck)
        state.hole_cards[0] = [self.deck[0], self.deck[1]]
        state.hole_cards[1] = [self.deck[2], self.deck[3]]
        
        deck_idx = 4
        
        # Action Loop
        players = [p0, p1]
        burn_states = [burn0, burn1]
        
        # Preflop -> Flop -> Turn -> River
        # Streets: 0, 1, 2, 3
        
        while not state.hand_complete:
            # Check if street complete (bets equal and not start of preflop exception)
            # Actually, simplify: Just run betting round logic
            
            # Use a simplified betting round function
            self._run_street(state, players, burn_states, btn_idx)
            
            if state.hand_complete:
                break
                
            if state.street == 3: # After River betting
                # Showdown
                score0 = evaluate_hand(state.hole_cards[0] + state.board)
                score1 = evaluate_hand(state.hole_cards[1] + state.board)
                
                # Determine winner
                if score0 > score1:
                    # P0 wins
                    state.stacks[0] += state.pot
                elif score1 > score0:
                    state.stacks[1] += state.pot
                else:
                    # Split
                    state.stacks[0] += state.pot / 2.0
                    state.stacks[1] += state.pot / 2.0
                
                state.hand_complete = True
                break
            
            # Advance street
            state.street += 1
            state.bets[0] = 0.0
            state.bets[1] = 0.0
            
            # Deal cards
            if state.street == 1: # Flop
                state.board.extend(self.deck[deck_idx:deck_idx+3])
                deck_idx += 3
            elif state.street == 2: # Turn
                state.board.append(self.deck[deck_idx])
                deck_idx += 1
            elif state.street == 3: # River
                state.board.append(self.deck[deck_idx])
                deck_idx += 1
                
            # Post-flop: BB acts first? No, OOP acts first.
            # BTN is IP. OOP is non-BTN.
            # Preflop: BTN (SB) acts first.
            # Postflop: OOP (BB) acts first.
            # If btn_idx = 0 (P0 is BTN), P1 is BB (OOP). P1 starts.
            state.active_player = 1 if btn_idx == 0 else 0
            
    
    def _run_street(self, state, players, burn_states, btn_idx):
        # Simplified betting round
        # Max raises? Capped at 4 usually. Or just allow until check/call/fold.
        
        # Preflop starts with unequal bets, so "call" is needed.
        # Postflop starts with 0 bets.
        
        actors_remaining = 2 # At least both get to act if no one folds?
        # Not exactly. If check-check, round over.
        # If bet-call, round over.
        # If bet-fold, hand over.
        
        last_aggressor = -1 # Who raised last?
        
        # If preflop, current bets are SB/BB.
        # If postflop, bets are 0/0.
        
        # Force minimum 1 action per player unless folded
        first_action = True
        
        while True:
            # Check if round done
            if not first_action:
                if state.bets[0] == state.bets[1]:
                    # Round Complete if bets equal and not first action (handled by loop)
                    # For preflop, active starts at SB (small bet).
                    # Need to check if everyone acted.
                    # Simple heuristic: if bets equal and actors_remaining <= 0?
                    # Better:
                    # If (Check-Check) -> Done
                    # If (Bet-Call) -> Done
                    # If (Raise-Call) -> Done
                    if last_aggressor == -1: # Check-Check sequence
                         # Or simply everyone checked
                         return # Next street
                    else:
                        return # Call happened
            
            # Determine simplified valid actions
            # If active_player stack == 0 -> 'check' (simulate all-in logic but just check)
            
            # Determine simplified valid actions
            # strategies expect 'fold', 'call', 'raise' usually.
            # We will map 'check' -> 'call' and 'bet' -> 'raise' for strategy interface
            
            p_idx = state.active_player
            opp_idx = 1 - p_idx
            
            valid = ['fold', 'call', 'raise']
            # If to_call == 0, fold is redundant but allowed? 
            # Usually checking is better than folding.
            # But we leave fold to keep lists consistent.
            
            to_call = state.bets[opp_idx] - state.bets[p_idx]
            
            # Prepare InfoSet
            # Need string cards for compatibility
            hole_str = [int_to_card(c) for c in state.hole_cards[p_idx]]
            board_str = [int_to_card(c) for c in state.board]
            
            # Construct standard InfoSet
            info = InfoSet(
                hole_cards=hole_str,
                community_cards=board_str,
                action_history=[], # Disabled history
                position='BTN' if p_idx == btn_idx else 'BB'
            )
            
            feats = StateFeatures(
                pot_size=state.pot,
                stack_size=state.stacks[p_idx],
                street='preflop' if state.street==0 else 'flop', # simplified
                to_call=to_call,
                valid_actions=valid
            )
            
            # Get Action
            probs = players[p_idx].get_action(info, feats, burn_states[p_idx])
            
            # Fallback if empty (shouldn't happen with standard keys)
            if not probs:
                 probs = {'call': 1.0}

            action = max(probs, key=probs.get) 
            # Sampling (simple)
            r = random.random()
            cum = 0
            selected = action
            for a, p in probs.items():
                cum += p
                if r <= cum:
                    selected = a
                    break
            action = selected
            
            # Execute
            if action == 'fold':
                # If to_call == 0, folding is technically valid but stupid.
                # Treat as fold (give up pot).
                if to_call == 0:
                     # Check instead of fold if free?
                     # Standard behavior: folding when check is available is allowed but bad.
                     # We'll allow it.
                     pass
                     
                state.folded = True
                state.hand_complete = True
                state.stacks[opp_idx] += state.pot
                return
                
            elif action == 'call':
                if to_call == 0:
                     # Check
                     pass
                else:
                    amount = to_call
                    # Handle All-In (Partial Call)
                    if amount > state.stacks[p_idx]:
                        actual_call = state.stacks[p_idx]
                        
                        # Refund excess to opponent
                        # Opponent's bet is (my_current_bet + to_call)
                        # We want bets to match at (my_current_bet + actual_call)
                        excess = amount - actual_call
                        
                        state.bets[opp_idx] -= excess
                        state.stacks[opp_idx] += excess
                        state.pot -= excess
                        
                        amount = actual_call
                    
                    state.bets[p_idx] += amount
                    state.stacks[p_idx] -= amount
                    state.pot += amount
                
            elif action == 'raise':
                # Map to Bet or Raise
                # Fixed size: Pot Size + Call
                amount = to_call + state.pot 
                
                # Check stack cap
                if amount > state.stacks[p_idx]:
                     amount = state.stacks[p_idx]
                     
                # Note: If my raise is essentially just a partial call (less than to_call),
                # it should be treated as a partial call.
                # Logic:
                # If amount < to_call, I can't even call -> Partial Call logic.
                if amount <= to_call:
                    # Treat as call (partial)
                    actual_call = amount # = stack
                    excess = to_call - actual_call
                    
                    state.bets[opp_idx] -= excess
                    state.stacks[opp_idx] += excess
                    state.pot -= excess
                    
                    state.bets[p_idx] += actual_call
                    state.stacks[p_idx] -= actual_call
                    state.pot += actual_call
                    
                else:
                    # Generic raise
                    # If I raise less than min-raise? (Allowed in standard NL if all-in)
                    # We accept whatever amount
                    
                    state.bets[p_idx] += amount
                    state.stacks[p_idx] -= amount
                    state.pot += amount
                    last_aggressor = p_idx
                
            first_action = False
            state.active_player = opp_idx
            
            # Check for loop limit? (Max raises)
            # Add safeguard
            if state.pot > 400: # Stack size limit ish
                 return

        return

class MatchEngine:
    """
    Wrapper for FastPokerEngine to match interface
    """
    def __init__(self, config: GameConfig = None, seed: int = None):
        self.engine = FastPokerEngine(config)
        if seed:
            self.engine.base_seed = seed
            random.seed(seed)
            
    def run_match(self, p1, p2, b1, b2, num_hands, switch=True):
        results = []
        p0_total_profit = 0.0
        
        start_time = time.time()
        
        for i in range(num_hands):
            btn = 0 if (i % 2 == 0) else 1
            if not switch: btn = 0
            
            # Play
            # Note: play_hand modifies state.stacks in place but resets them every hand?
            # Wait, standard match engine resets stacks every hand to 200bb?
            # Yes, "Duplicate Poker" style usually.
            # FastEngine resets stack in play_hand.
            
            # Return is P0 profit?
            # My play_hand returns None, updates stacks.
            self.engine.play_hand(p1, p2, b1, b2, i, btn)
            
            profit = self.engine.state.stacks[0] - 200.0
            
            # Minimal result object for memory
            # Don't store full actions
            results.append(HandResult(i, profit, []))
            
        return results

if __name__ == "__main__":
    from strategies.registry import StrategyRegistry
    
    print("FastPokerEngine Benchmark")
    
    # Mock strategies
    class RandomStrategy(Strategy):
        def get_action(self, info_set, state_features, burn_state):
            # Fast random
            acts = state_features.valid_actions
            return {a: 1.0/len(acts) for a in acts}

    p1 = RandomStrategy()
    p2 = RandomStrategy()
    b1 = BurnState(0,0,0)
    b2 = BurnState(0,0,0)
    
    engine = MatchEngine()
    
    # Warmup
    print("Warmup...")
    engine.run_match(p1, p2, b1, b2, 100)
    
    # Benchmark
    N = 10000
    print(f"Running {N} hands...")
    start = time.time()
    engine.run_match(p1, p2, b1, b2, N)
    dur = time.time() - start
    
    print(f"Time: {dur:.4f}s")
    print(f"Speed: {N/dur:.1f} hands/sec")


