import math
import random
import struct
import os
import numpy as np
from pathlib import Path
from typing import Dict, List
from .base import Strategy
from .equity_calculator import calculator


# =====================
# Card Utils
# =====================
class CardUtils:
    RANKS = "AKQJT98765432"

    @classmethod
    def get_hand_label(cls, hole: List[str]) -> str:
        r1, s1 = hole[0][0], hole[0][1]
        r2, s2 = hole[1][0], hole[1][1]
        idx1, idx2 = cls.RANKS.index(r1), cls.RANKS.index(r2)
        if idx1 > idx2:
            r1, s1, r2, s2 = r2, s2, r1, s1
        if r1 == r2:
            return r1 + r2
        return r1 + r2 + ("s" if s1 == s2 else "o")

    @classmethod
    def get_hand_index(cls, label: str) -> int:
        idx = 0
        for r in cls.RANKS:
            if r + r == label:
                return idx
            idx += 1
        for i, r1 in enumerate(cls.RANKS):
            for r2 in cls.RANKS[i + 1:]:
                if r1 + r2 + "s" == label:
                    return idx
                idx += 1
                if r1 + r2 + "o" == label:
                    return idx
                idx += 1
        return 0


# =====================
# Strategy
# =====================
class RobustMashupStrategy(Strategy):
    STRATEGY_NAME = "robust_mashup_v8_2_multi_lut"

    def __init__(self, lut_path: str = "gto_output_all/preflop_v1.bin"):
        super().__init__()

        self.preflop_lut = {}
        self.total_hands_played = 0

        self.opp_sizing_history = {
            "preflop": [], "flop": [], "turn": [], "river": []
        }

        self.my_weights = np.ones(169) / 169.0
        self.opp_weights = np.ones(169) / 169.0

        self.canonical_labels = self._generate_all_labels()
        self.preflop_initialized = False

        p = Path(lut_path)
        if not p.is_absolute():
            p = (Path(__file__).parent / lut_path).resolve()

        if p.exists():
            print(f"[{self.STRATEGY_NAME}] load preflop LUT: {p}")
            self.preflop_lut = self._load_gtob_preflop_v1(str(p))
        else:
            print(f"[{self.STRATEGY_NAME}] WARNING: LUT not found")

    # =====================
    # LUT Loader
    # =====================
    def _load_gtob_preflop_v1(self, path: str):
        lut = {}
        try:
            with open(path, "rb") as f:
                if f.read(4) != b"GTOB":
                    return {}
                _version = struct.unpack("<H", f.read(2))[0]
                _type = f.read(1)
                count = struct.unpack("<H", f.read(2))[0]
                for _ in range(count):
                    hid, pf, pc, pr = struct.unpack("<HHHH", f.read(8))
                    total = pf + pc + pr
                    if total > 0:
                        lut[hid] = {
                            "fold": pf / total,
                            "call": pc / total,
                            "raise": pr / total
                        }
                    else:
                        lut[hid] = {"fold": 1.0, "call": 0.0, "raise": 0.0}
        except Exception:
            return {}
        return lut

    # =====================
    # Main Action
    # =====================
    def get_action(self, info_set, feats, burn) -> Dict[str, float]:
        street = getattr(feats, "street", "preflop")
        to_call = float(getattr(feats, "to_call", 0.0))
        pot = float(getattr(feats, "pot_size", 1.0))

        # ---- preflop range init ----
        if street == "preflop" and not self.preflop_initialized:
            self._initialize_preflop_weights()

        # =====================
        # PREFLOP (CFR as scale)
        # =====================
        if street == "preflop":
            self.total_hands_played += 1

            label = CardUtils.get_hand_label(info_set.hole_cards)
            hid = CardUtils.get_hand_index(label)

            base = self.preflop_lut.get(
                hid, {"fold": 1.0, "call": 0.0, "raise": 0.0}
            )

            return self._apply_lut_with_exploit(
                base,
                pot,
                to_call,
                "preflop",
                info_set,
                feats,
                burn
            )

        # =====================
        # POSTFLOP (heuristic untouched)
        # =====================
        return self._heuristic_action(info_set, feats, burn)

    # =====================
    # Exploit Wrapper
    # =====================
    def _apply_lut_with_exploit(
        self, base_dist: Dict[str, float],
        pot: float, to_call: float,
        street: str, info_set, feats, burn
    ) -> Dict[str, float]:

        dist = base_dist.copy()

        if to_call <= 0:
            return dist

        pot_before = pot - to_call
        bet_ratio = to_call / pot_before if pot_before > 0 else 0.0

        distortion = self._detect_sizing_distortion(bet_ratio)

        pattern_adjustment = 0.0
        if self.total_hands_played >= 100:
            pattern = self._analyze_sizing_pattern(street)
            if pattern["confidence"] > 0.7:
                pattern_adjustment = -0.15 if pattern["bias"] == "value" else 0.15

        if distortion > 0.5:
            adjustment = 0.2 if 0.4 < bet_ratio < 0.6 else -0.15
        else:
            adjustment = 0.0

        adjustment += pattern_adjustment

        f = max(0.0, dist.get("fold", 0.0) - adjustment)
        c = min(1.0, dist.get("call", 0.0) + adjustment)
        r = dist.get("raise", 0.0)

        s = f + c + r
        if s > 0:
            return {"fold": f / s, "call": c / s, "raise": r / s}

        return dist

    # =====================
    # Heuristic (UNCHANGED)
    # =====================
    def _heuristic_action(self, info_set, feats, burn):
        pot = float(getattr(feats, "pot_size", 1.0))
        to_call = float(getattr(feats, "to_call", 0.0))
        street = getattr(feats, "street", "preflop")
        stack = float(getattr(feats, "stack", 200.0))

        my_equity = calculator.calculate_equity(
            info_set.hole_cards,
            info_set.community_cards,
            iterations=600 if pot > 40 or street == "river" else 100
        )

        dist = {"fold": 0.0, "call": 0.0, "raise": 0.0}

        if to_call > 0:
            odds = to_call / (pot + to_call)
            if my_equity > odds:
                dist["call"] = 1.0
            else:
                dist["fold"] = 1.0
        else:
            if my_equity > 0.75:
                dist["raise"] = 1.0
            else:
                dist["call"] = 1.0

        return dist

    # =====================
    # Helpers
    # =====================
    def _detect_sizing_distortion(self, bet_ratio: float) -> float:
        buckets = [0.33, 0.5, 0.67, 1.0, 1.5, 2.0]
        d = min(abs(bet_ratio - b) for b in buckets)
        return min(d / 0.2, 1.0) if d > 0.1 else 0.0

    def _analyze_sizing_pattern(self, street: str):
        hist = self.opp_sizing_history.get(street, [])
        if len(hist) < 10:
            return {"confidence": 0.0, "bias": "neutral"}
        return {"confidence": 0.0, "bias": "neutral"}

    def _initialize_preflop_weights(self):
        for i, label in enumerate(self.canonical_labels):
            p = self.preflop_lut.get(i, {"call": 0.0, "raise": 0.0})
            self.my_weights[i] = p.get("call", 0.0) + p.get("raise", 0.0)
        s = np.sum(self.my_weights)
        if s > 0:
            self.my_weights /= s
        self.preflop_initialized = True

    def _generate_all_labels(self) -> List[str]:
        ranks = "AKQJT98765432"
        labels = []
        for i in range(12, -1, -1):
            for j in range(i, -1, -1):
                if i == j:
                    labels.append(ranks[i] + ranks[j])
                else:
                    labels.append(ranks[i] + ranks[j] + "s")
                    labels.append(ranks[i] + ranks[j] + "o")
        return labels
