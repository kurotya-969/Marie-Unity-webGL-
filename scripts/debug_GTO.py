"""
RobustMashupBot デバッグスクリプト
GTOB / pickle 両対応のプリフロップGTO読み込み・動作検証
"""

import sys
from pathlib import Path

# --- import path 設定 ---
ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT / "src"))

from strategies.RMBALL import RobustMashupStrategy
from strategies.base import InfoSet, StateFeatures
from burn_knobs import BurnState

# ============================================================
# GTOBプリフロップ読み込み関数
# ============================================================
def load_gtob_preflop(path):
    import struct
    lut = {}
    with open(path, "rb") as f:
        # ヘッダ確認
        assert f.read(4) == b"GTOB"
        version = struct.unpack("<H", f.read(2))[0]
        street = f.read(1).decode()
        n_rec = struct.unpack("<H", f.read(2))[0]

        for _ in range(n_rec):
            hid = struct.unpack("<H", f.read(2))[0]
            pf, pc, pr = struct.unpack("<HHH", f.read(6))
            lut[hid] = {
                "fold": pf / 65535,
                "call": pc / 65535,
                "raise": pr / 65535
            }
    return lut

# ============================================================
# プリフロップアクション確認テスト
# ============================================================
def test_preflop_action(bot):
    print("\n" + "=" * 60)
    print("プリフロップアクション決定テスト")
    print("=" * 60)

    from strategies.base import InfoSet, StateFeatures

    burn_state = BurnState(0.0, 0.0, 0.0)

    test_cases = [
        (["As", "Ah"], "BTN"),
        (["Ks", "Kh"], "BTN"),
        (["As", "Ks"], "BTN"),
        (["7s", "6s"], "BTN"),
        (["3h", "2d"], "BTN"),
    ]

    print("\nBTNポジションでの初回アクション:")
    for hole_cards, position in test_cases:

        info = InfoSet(
            hole_cards=hole_cards,
            community_cards=[],
            position=position,
            action_history=[]
        )

        feats = StateFeatures(
            pot_size=3.0,
            stack_size=200.0,
            street="preflop",
            to_call=0.0,
            valid_actions=["fold", "call", "raise"]
        )

        action = bot.get_action(info, feats, burn_state)
        print(f"{hole_cards} -> {action}")

# ============================================================
# hid 衝突テスト
# ============================================================
def test_hash_collision():
    print("\n" + "=" * 60)
    print("hid衝突テスト")
    print("=" * 60)

    # --- 169ハンドラベル ---
    RANKS = "AKQJT98765432"
    HAND_LABELS = [r+r for r in RANKS]
    for i, r1 in enumerate(RANKS):
        for r2 in RANKS[i+1:]:
            HAND_LABELS.append(r1+r2+"s")
            HAND_LABELS.append(r1+r2+"o")

    # --- 簡易 get_hid ---
    LABEL_TO_HID = {label: idx for idx, label in enumerate(HAND_LABELS)}
    def get_hid(label: str) -> int:
        """スート無視、169ハンド平均化用 hid"""
        return LABEL_TO_HID[label]

    seen = {}
    collisions = []

    for label in HAND_LABELS:
        hid = get_hid(label)
        if hid in seen:
            collisions.append((label, seen[hid], hid))
        else:
            seen[hid] = label

    print("総ハンド数:", len(HAND_LABELS))
    print("ユニークhid:", len(seen))
    print("衝突数:", len(collisions))

    if collisions:
        print("⚠️ 衝突例:")
        for a, b, hid in collisions[:5]:
            print(f"{a} / {b} -> hid={hid}")


# ============================================================
# メイン
# ============================================================
if __name__ == "__main__":
    print("RobustMashupBot デバッグ診断")
    print("=" * 60)

    # GTOBバイナリ読み込み
    lut_path = ROOT / "src" / "strategies" / "gto_output_all" / "preflop.bin"
    print(f"GTOBファイル: {lut_path}")
    gto_lut = load_gtob_preflop(str(lut_path))
    print(f"GTOBエントリ数: {len(gto_lut)}")

    # Bot生成 & LUTセット
    bot = RobustMashupStrategy(is_binary=False)
    bot.gto_lut = gto_lut

    # サンプルハンド戦略確認
    test_preflop_action(bot)

    # hid衝突確認
    test_hash_collision()

    print("\n" + "=" * 60)
    print("診断完了")
    print("=" * 60)
