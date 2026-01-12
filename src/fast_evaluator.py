
"""
High-Speed Hand Evaluator
Optimized for Heads-Up No-Limit Hold'em (7 cards).

Cards are integers 0-51:
0-12: Spades 2-A
13-25: Hearts 2-A
26-38: Diamonds 2-A
39-51: Clubs 2-A

Rank: card % 13 (0=2, 12=A)
Suit: card // 13 (0=S, 1=H, 2=D, 3=C)
"""

from typing import List, Tuple

# Precompute rank bitmasks for straights
# straights[i] = bitmask for straight ending at rank i
# A-5 straight (Wheel): A, 2, 3, 4, 5 -> bitmask for 12, 0, 1, 2, 3
STRAIGHT_MASKS = {}
for i in range(4, 13):
    mask = 0
    for j in range(5):
        mask |= (1 << (i - j))
    STRAIGHT_MASKS[mask] = i

# Wheel mask: A(12) and 0,1,2,3
WHEEL_MASK = (1 << 12) | (1 << 0) | (1 << 1) | (1 << 2) | (1 << 3)
STRAIGHT_MASKS[WHEEL_MASK] = 3  # Treated as 5-high straight (index 3 corresponds to rank 5 if 0 is 2)
# Wait, my ranks are 0=2... 3=5. So 5-high is (0,1,2,3,12). Correct.

def evaluate_hand(cards: List[int]) -> int:
    """
    Evaluate 7-card hand.
    Returns an integer score. Higher is better.
    Score format: (Type << 20) + (HighRank1 << 16) + ...
    Type:
    8: Straight Flush
    7: Quads
    6: Full House
    5: Flush
    4: Straight
    3: Trips
    2: Two Pair
    1: Pair
    0: High Card
    """
    
    ranks = [c % 13 for c in cards]
    suits = [c // 13 for c in cards]
    
    # 1. Check Flush
    suit_counts = [0, 0, 0, 0]
    flush_suit = -1
    for s in suits:
        suit_counts[s] += 1
        if suit_counts[s] >= 5:
            flush_suit = s
            break
            
    if flush_suit != -1:
        # Get ranks of flush cards
        flush_ranks = [r for r, s in zip(ranks, suits) if s == flush_suit]
        flush_ranks.sort(reverse=True)
        
        # Check Straight Flush
        # Create bitmask of flush ranks
        mask = 0
        for r in flush_ranks:
            mask |= (1 << r)
        
        # Check for straights in flush
        # Check normal straights
        for i in range(12, 3, -1): # A down to 6
             s_mask = 0
             for j in range(5):
                 s_mask |= (1 << (i - j))
             if (mask & s_mask) == s_mask:
                 return (8 << 20) | (i << 16)
        
        # Check Wheel
        if (mask & WHEEL_MASK) == WHEEL_MASK:
             return (8 << 20) | (3 << 16) # 5-high
             
        # Just Flush
        # Score = 5, then top 5 cards
        score = (5 << 20)
        for i in range(5):
            score |= (flush_ranks[i] << (16 - 4*i))
        return score

    # 2. Check Straight (non-flush)
    # Create rank bitmask
    mask = 0
    for r in ranks:
        mask |= (1 << r)
        
    # Check normal straights
    for i in range(12, 3, -1):
        s_mask = 0
        for j in range(5):
            s_mask |= (1 << (i - j))
        if (mask & s_mask) == s_mask:
            return (4 << 20) | (i << 16)
            
    if (mask & WHEEL_MASK) == WHEEL_MASK:
        return (4 << 20) | (3 << 16)

    # 3. Check Paired Hands (Quads, FH, Trips, 2Pair, Pair)
    rank_counts = [0] * 13
    for r in ranks:
        rank_counts[r] += 1
        
    quads = []
    trips = []
    pairs = []
    singles = []
    
    for r in range(12, -1, -1): # High to low
        c = rank_counts[r]
        if c == 4:
            quads.append(r)
        elif c == 3:
            trips.append(r)
        elif c == 2:
            pairs.append(r)
        elif c == 1:
            singles.append(r)
            
    if quads:
        kicker = 0
        # Find highest kicker
        for r in range(12, -1, -1):
            if r != quads[0] and rank_counts[r] > 0:
                kicker = r
                break
        return (7 << 20) | (quads[0] << 16) | (kicker << 12)
        
    if trips and (len(trips) >= 2 or pairs):
        # Full House
        high_trip = trips[0]
        # Find highest pair (or second trip)
        high_pair = 0
        if len(trips) >= 2:
            high_pair = trips[1]
        elif pairs:
            high_pair = pairs[0]
        
        # If pairs[0] > trips[1] (impossible if trips sorted, but logic is safe)
        if pairs and len(trips) >= 2 and pairs[0] > trips[1]:
            high_pair = pairs[0]
            
        return (6 << 20) | (high_trip << 16) | (high_pair << 12)
        
    if len(trips) == 1:
        # Trips
        kickers = []
        for r in range(12, -1, -1):
            if r != trips[0] and rank_counts[r] > 0:
                kickers.append(r)
                if len(kickers) == 2:
                    break
        return (3 << 20) | (trips[0] << 16) | (kickers[0] << 12) | (kickers[1] << 8)
        
    if len(pairs) >= 2:
        # Two Pair
        p1 = pairs[0]
        p2 = pairs[1]
        kicker = 0
        for r in range(12, -1, -1):
            if r != p1 and r != p2 and rank_counts[r] > 0:
                kicker = r
                break
        return (2 << 20) | (p1 << 16) | (p2 << 12) | (kicker << 8)
        
    if len(pairs) == 1:
        # One Pair
        p1 = pairs[0]
        kickers = []
        for r in range(12, -1, -1):
            if r != p1 and rank_counts[r] > 0:
                kickers.append(r)
                if len(kickers) == 3:
                    break
        return (1 << 20) | (p1 << 16) | (kickers[0] << 12) | (kickers[1] << 8) | (kickers[2] << 4)
        
    # High Card
    kickers = []
    for r in range(12, -1, -1):
        if rank_counts[r] > 0:
            kickers.append(r)
            if len(kickers) == 5:
                break
    
    score = 0
    for i, k in enumerate(kickers):
        score |= (k << (16 - 4*i))
    return score

