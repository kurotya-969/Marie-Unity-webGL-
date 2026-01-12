
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from fast_evaluator import evaluate_hand
from match_engine import FastPokerEngine, card_to_int
from strategies.random import RandomBot
from burn_knobs import BurnState
import time
import random

def test_evaluator():
    print("Testing Evaluator...")
    # Royal Flush
    cards = [card_to_int(c) for c in ['As', 'Ks', 'Qs', 'Js', 'Ts', '2d', '3d']]
    score_rf = evaluate_hand(cards)
    type_rf = score_rf >> 20
    print(f"Royal Flush Type: {type_rf} (Expected 8)")
    
    # Quads
    cards = [card_to_int(c) for c in ['As', 'Ad', 'Ah', 'Ac', '2s', '3d', '4c']]
    score_q = evaluate_hand(cards)
    print(f"Quads Type: {score_q >> 20} (Expected 7)")
    
    # Full House
    cards = [card_to_int(c) for c in ['As', 'Ad', 'Ah', 'Ks', 'Kd', '3d', '4c']]
    score_fh = evaluate_hand(cards)
    print(f"Full House Type: {score_fh >> 20} (Expected 6)")
    
    # Verify Order
    assert score_rf > score_q > score_fh
    print("Evaluator Order OK")

def test_zero_sum():
    print("Searching for failing seed...")
    for seed in range(100):
        random.seed(seed)
        engine = FastPokerEngine()
        p1 = RandomBot()
        p2 = RandomBot()
        b = BurnState(0,0,0)
        
        for i in range(100):
            btn = i % 2
            # print(f"Playing hand {i}. Types: {type(p1)} {type(p2)}")
            engine.play_hand(p1, p2, b, b, i, btn)
            
            profit0 = engine.state.stacks[0] - 200.0
            profit1 = engine.state.stacks[1] - 200.0
            
            if abs(profit0 + profit1) > 0.0001:
                print(f"FAILED at Seed {seed}, Hand {i}: {profit0} + {profit1} != 0")
                return

    print("No failure found in first 100 seeds (100 hands each)")

if __name__ == "__main__":
    test_evaluator()
    test_zero_sum()
