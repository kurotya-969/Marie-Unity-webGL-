import sys
import json
import random
import requests
from pathlib import Path

# =====================
# ロジック import
# =====================
sys.path.append(str(Path(__file__).parent.parent / "src"))
from strategies.base import InfoSet, StateFeatures
from burn_knobs import BurnState
from strategies.RMBALL import RobustMashupStrategy

# =====================
# CONFIG
# =====================
API_URL = "https://slumbot.com/slumbot/api"
BB = 100
STACK = 200 * BB

# =====================
# Action Parser
# =====================
class ActionState:
    def __init__(self):
        self.street = 0
        self.pot = 150  # SB 50 + BB 100
        self.wagers = [50, 100]
        self.to_act = 0  # 0=self, 1=opp

    def apply(self, action):
        if action == "":
            return

        i = 0
        while i < len(action):
            c = action[i]

            if c == "/":
                self.street += 1
                self.wagers = [0, 0]
                i += 1
                continue

            if c == "k":
                i += 1

            elif c == "c":
                diff = abs(self.wagers[0] - self.wagers[1])
                self.pot += diff
                self.wagers[0] += diff if self.wagers[0] < self.wagers[1] else 0
                self.wagers[1] += diff if self.wagers[1] < self.wagers[0] else 0
                i += 1

            elif c == "f":
                return "terminal"

            elif c == "b":
                j = i + 1
                while j < len(action) and action[j].isdigit():
                    j += 1
                amt = int(action[i+1:j])
                diff = amt - self.wagers[self.to_act]
                self.pot += diff
                self.wagers[self.to_act] = amt
                i = j

            self.to_act ^= 1

        return "continue"

    def to_call(self):
        return max(0, self.wagers[1] - self.wagers[0])

# =====================
# Slumbot Runner
# =====================
class SlumbotRunner:
    def __init__(self):
        self.session = requests.Session()
        self.strategy = RobustMashupStrategy()
        self.token = None

    def api(self, endpoint, payload):
        r = self.session.post(API_URL + endpoint, json=payload, timeout=10)
        r.raise_for_status()
        return r.json()

    def run_hand(self):
        print("\n--- NEW HAND ---")
        data = self.api("/new_hand", {})
        self.token = data["token"]

        hole = data["hole_cards"]
        board = data.get("board", [])

        state = ActionState()

        client_pos = data["client_pos"]  # 0=先手(BB), 1=後手(BTN)
        hero = 0 if client_pos == 0 else 1
        state.to_act = 1 if client_pos == 0 else 0

        # 相手初手
        if data.get("action"):
            state.apply(data["action"])

        while True:
            # street 判定
            street = ["preflop", "flop", "turn", "river"][min(state.street, 3)]

            info = InfoSet(
                hole_cards=hole,
                community_cards=board,
                position="BTN" if hero == 1 else "BB",
                action_history=[]
            )

            feats = StateFeatures(
                pot_size=state.pot / BB,
                stack_size=200.0,
                to_call=state.to_call() / BB,
                street=street,
                valid_actions=["fold", "call", "raise"]
            )

            burn = BurnState(0.0, 0.0, 0.0)

            probs = self.strategy.get_action(info, feats, burn)
            act = random.choices(list(probs), list(probs.values()))[0]

            # 翻訳（Slumbot最小安全ムーブ）
            if act == "fold" and state.to_call() > 0:
                send = "f"
            elif act == "raise":
                min_raise = max(state.wagers) + BB * 2
                send = f"b{min_raise}"
            else:
                send = "c" if state.to_call() > 0 else "k"

            print(f"[{street}] pot={state.pot} to_call={state.to_call()} -> {act} ({send})")

            data = self.api("/act", {"token": self.token, "incr": send})
            # 自分の行動でハンド終了する場合
            if state.apply(send) == "terminal":
                print("HAND END (by fold)")
                break

            # token は「あるときだけ」更新
            if "token" in data:
                self.token = data["token"]

            # 相手行動反映
            if state.apply(data.get("action", "")) == "terminal":
                print("HAND END (by opponent)")
                break

            board = data.get("board", board)

    def run(self, hands=1000):
        print(f"=== START {hands} HANDS ===")
        for i in range(hands):
            print(f"\n[HAND {i+1}]")
            try:
                self.run_hand()
            except Exception as e:
                print("ERROR:", e)
                break

# =====================
# main
# =====================
if __name__ == "__main__":
    SlumbotRunner().run(1000)
