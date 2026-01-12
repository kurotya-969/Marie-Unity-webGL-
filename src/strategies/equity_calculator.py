
import random
import sys
from pathlib import Path

# Add src to path to import fast_evaluator
sys.path.append(str(Path(__file__).parent.parent))
from fast_evaluator import evaluate_hand

def card_str_to_int(card_str: str) -> int:
    """
    Convert card string (e.g. 'As', 'Th', '2c') to integer 0-51.
    0-12: Spades 2-A
    13-25: Hearts 2-A
    26-38: Diamonds 2-A
    39-51: Clubs 2-A
    """
    ranks = '23456789TJQKA'
    suits = 'shdc' # Note: fast_evaluator might use different order?
    # fast_evaluator doc:
    # 0-12: Spades
    # 13-25: Hearts
    # 26-38: Diamonds
    # 39-51: Clubs
    # Suit: card // 13 (0=S, 1=H, 2=D, 3=C)
    
    r_char = card_str[0]
    s_char = card_str[1]
    
    rank = ranks.index(r_char)
    if s_char == 's': suit = 0
    elif s_char == 'h': suit = 1
    elif s_char == 'd': suit = 2
    elif s_char == 'c': suit = 3
    else: raise ValueError(f"Invalid suit: {s_char}")
    
    return suit * 13 + rank

class EquityCalculator:
    """
    Lightweight Monte Carlo Equity Calculator.
    Shared across strategies for consistency.
    """
    
    def __init__(self):
        # Full deck
        self.full_deck = list(range(52))
        
    def calculate_equity(self, hole_cards: list, board: list, opponent_range=None, iterations: int = 1000) -> float:
        """
        Calculate equity of hole_cards against a random hand.
        Accepts integer or string cards.
        """
        # Convert to ints if strings
        if hole_cards and isinstance(hole_cards[0], str):
            hole_cards = [card_str_to_int(c) for c in hole_cards]
        if board and len(board) > 0 and isinstance(board[0], str):
            board = [card_str_to_int(c) for c in board]
            
        wins = 0
        splits = 0
        
        # Cards already visible (cannot be dealt to opponent or board)
        visible = set(hole_cards + board)
        
        # Available cards
        deck = [c for c in self.full_deck if c not in visible]
        
        needed_board = 5 - len(board)
        
        for _ in range(iterations):
            # Shuffle only what calls needed? 
            # Optimization: Just sample needed cards
            # We need: 2 for opponent + needed_board
            
            sample_size = 2 + needed_board
            drawn = random.sample(deck, sample_size)
            
            opp_cards = drawn[:2]
            runout = drawn[2:]
            
            full_board = board + runout
            
            my_score = evaluate_hand(hole_cards + full_board)
            opp_score = evaluate_hand(opp_cards + full_board)
            
            if my_score > opp_score:
                wins += 1
            elif my_score == opp_score:
                splits += 1
                
        return (wins + splits / 2.0) / iterations

# Singleton instance
calculator = EquityCalculator()
