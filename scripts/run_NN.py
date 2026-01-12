import argparse
from pathlib import Path
import sys
import csv
import random
from typing import List, Dict, Tuple, Optional

# プロジェクトルートをパスに追加
sys.path.append(str(Path(__file__).parent))
sys.path.append(str(Path(__file__).parent.parent / "src"))

try:
    from burn_knobs import BurnState
    from strategies.registry import StrategyRegistry
    from strategies.base import InfoSet, StateFeatures
except ImportError as e:
    print(f"ImportError: {e}")
    print("PYTHONPATHを確認してください。")
    sys.exit(1)

# =================================================================
# カードユーティリティ
# =================================================================
def create_deck() -> List[str]:
    ranks = "23456789TJQKA"
    suits = "shdc"
    return [r + s for r in ranks for s in suits]

def deal_cards(deck: List[str], num: int) -> Tuple[List[str], List[str]]:
    return deck[:num], deck[num:]

# =================================================================
# ゲームシミュレーター
# =================================================================
def _sample_action(action_probs: Dict[str, float]) -> Dict:
    """確率分布からアクションをサンプリング"""
    if not action_probs:
        return {'action': 'fold', 'amount': 0.0}
    
    actions = list(action_probs.keys())
    # 確率が文字列で入っている可能性も考慮してfloat化
    probs = [float(p) for p in action_probs.values()]
    
    total = sum(probs)
    if total > 0:
        probs = [p / total for p in probs]
    else:
        probs = [1.0 / len(probs)] * len(probs)
    
    chosen = random.choices(actions, weights=probs, k=1)[0]
    return {'action': chosen, 'amount': 0.75}

def simulate_hand_until_turn(
    strategy1,
    strategy2,
    burn_state: BurnState,
    button_position: int,
    bb_size: float = 2.0,
    starting_stack: float = 100.0
) -> Optional[Dict]:
    """プリフロップ・フロップをシミュレートしターン開始時を返す"""
    
    deck = create_deck()
    random.shuffle(deck)
    
    p1_hole, deck = deal_cards(deck, 2)
    p2_hole, deck = deal_cards(deck, 2)
    
    # 型を確実にfloatにする
    p1_stack = float(starting_stack)
    p2_stack = float(starting_stack)
    pot = 0.0
    bb_size = float(bb_size)
    sb_size = bb_size / 2.0
    
    # ブラインド投入
    if button_position == 0: # P1=BTN/SB
        p1_stack -= sb_size; p2_stack -= bb_size
        p1_inv, p2_inv = sb_size, bb_size
    else: # P2=BTN/SB
        p2_stack -= sb_size; p1_stack -= bb_size
        p1_inv, p2_inv = bb_size, sb_size
    pot = p1_inv + p2_inv

    community = []

    # --- プリフロップ ---
    acting_player = 1 if button_position == 0 else 2
    for i in range(10): # 無限ループ回避
        # 全員が同じ額を出していて、かつ誰かがアクションした後は終了
        if abs(p1_inv - p2_inv) < 1e-6 and i > 0:
            break
            
        curr_strat = strategy1 if acting_player == 1 else strategy2
        curr_hole = p1_hole if acting_player == 1 else p2_hole
        curr_stack = p1_stack if acting_player == 1 else p2_stack
        
        # コールに必要な額
        opp_inv = p2_inv if acting_player == 1 else p1_inv
        curr_inv = p1_inv if acting_player == 1 else p2_inv
        to_call = float(max(0.0, opp_inv - curr_inv))
        
        pos = 'BTN' if (acting_player == 1 and button_position == 0) or (acting_player == 2 and button_position == 1) else 'BB'
        
        info = InfoSet(hole_cards=curr_hole, community_cards=community, position=pos, action_history=[])
        feat = StateFeatures(
            pot_size=float(pot),
            stack_size=float(curr_stack),
            to_call=float(to_call),
            street='preflop',
            valid_actions=['fold', 'call', 'raise']
        )
        
        # アクション取得
        action_res = _sample_action(curr_strat.get_action(info, feat, burn_state))
        
        if action_res['action'] == 'fold':
            return None
        elif action_res['action'] == 'call':
            call_amt = min(to_call, curr_stack)
            if acting_player == 1: p1_stack -= call_amt; p1_inv += call_amt
            else: p2_stack -= call_amt; p2_inv += call_amt
            pot += call_amt
            if abs(p1_inv - p2_inv) < 1e-6: break
        else: # raise
            raise_amt = to_call + bb_size
            total_in = min(to_call + raise_amt, curr_stack + to_call)
            if acting_player == 1: p1_stack -= total_in; p1_inv += total_in
            else: p2_stack -= total_in; p2_inv += total_in
            pot += total_in
        
        acting_player = 2 if acting_player == 1 else 1

    # --- フロップ ---
    flop, deck = deal_cards(deck, 3)
    community.extend(flop)
    
    # OOP (BB側) からアクション開始
    acting_player = 2 if button_position == 0 else 1
    p1_f_inv, p2_f_inv = 0.0, 0.0
    
    for i in range(10):
        if abs(p1_f_inv - p2_f_inv) < 1e-6 and i > 0:
            break
            
        curr_strat = strategy1 if acting_player == 1 else strategy2
        curr_hole = p1_hole if acting_player == 1 else p2_hole
        curr_stack = p1_stack if acting_player == 1 else p2_stack
        
        opp_f_inv = p2_f_inv if acting_player == 1 else p1_f_inv
        curr_f_inv = p1_f_inv if acting_player == 1 else p2_f_inv
        to_call_f = float(max(0.0, opp_f_inv - curr_f_inv))
        
        pos = 'BTN' if (acting_player == 1 and button_position == 0) or (acting_player == 2 and button_position == 1) else 'BB'
        
        info = InfoSet(hole_cards=curr_hole, community_cards=community, position=pos, action_history=[])
        feat = StateFeatures(
            pot_size=float(pot),
            stack_size=float(curr_stack),
            to_call=float(to_call_f), # ここがエラーの原因になりやすいので確実にfloat
            street='flop',
            valid_actions=['fold', 'call', 'raise']
        )
        
        action_res = _sample_action(curr_strat.get_action(info, feat, burn_state))
        
        if action_res['action'] == 'fold':
            return None
        elif action_res['action'] == 'call':
            call_amt = min(to_call_f, curr_stack)
            if acting_player == 1: p1_stack -= call_amt; p1_f_inv += call_amt
            else: p2_stack -= call_amt; p2_f_inv += call_amt
            pot += call_amt
            if abs(p1_f_inv - p2_f_inv) < 1e-6: break
        else: # bet / raise
            bet_amt = max(bb_size, pot * 0.5)
            total_in = min(to_call_f + bet_amt, curr_stack)
            if acting_player == 1: p1_stack -= total_in; p1_f_inv += total_in
            else: p2_stack -= total_in; p2_f_inv += total_in
            pot += total_in
            
        acting_player = 2 if acting_player == 1 else 1

    # --- ターン開始 ---
    turn_card, deck = deal_cards(deck, 1)
    community.extend(turn_card)
    
    return {
        'street': 'turn',
        'p1_hole': p1_hole,
        'p2_hole': p2_hole,
        'board': community,
        'pot': float(pot),
        'p1_stack': float(p1_stack),
        'p2_stack': float(p2_stack),
        'acting_player': 2 if button_position == 0 else 1 # ターンもOOP(BB)から
    }

# =================================================================
# データ収集
# =================================================================
def collect_turn_situations(s1_name: str, s2_name: str, num_hands: int, seed: int) -> List[Dict]:
    random.seed(seed)
    registry = StrategyRegistry()
    registry.auto_discover()
    
    print(f"戦略実体化: {s1_name} vs {s2_name}")
    strat1 = registry.create(s1_name)
    strat2 = registry.create(s2_name)
    
    burn_state = BurnState(0.0, 0.0, 0.0)
    situations = []
    
    for hand_id in range(num_hands):
        if (hand_id + 1) % 500 == 0:
            print(f"Progress: {hand_id+1}/{num_hands}")
            
        res = simulate_hand_until_turn(strat1, strat2, burn_state, hand_id % 2)
        if not res: continue
        
        act = res['acting_player']
        pos = 'BB' if (act == 2 and hand_id % 2 == 0) or (act == 1 and hand_id % 2 == 1) else 'BTN'
        hole = res['p1_hole'] if act == 1 else res['p2_hole']
        
        situations.append({
            'hand_id': hand_id,
            'hole_1': hole[0], 'hole_2': hole[1],
            'board_1': res['board'][0], 'board_2': res['board'][1],
            'board_3': res['board'][2], 'board_4': res['board'][3],
            'pot': res['pot'], 
            'stack': res['p1_stack'] if act == 1 else res['p2_stack'],
            'position': pos,
            'strategy_name': s1_name if act == 1 else s2_name
        })
    return situations

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--hands', type=int, default=1000)
    parser.add_argument('--s1', type=str, default='robust_mashup_v8_2_multi_lut')
    parser.add_argument('--s2', type=str, default='robust_mashup_v8_2_multi_lut')
    parser.add_argument('--output', type=str, default='turn_data.csv')
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    
    data = collect_turn_situations(args.s1, args.s2, args.hands, args.seed)
    
    if data:
        with open(args.output, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
        print(f"Saved {len(data)} lines to {args.output}")

if __name__ == "__main__":
    main()