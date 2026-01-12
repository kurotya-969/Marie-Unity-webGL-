"""
標準実験実行スクリプト

焼却なしの通常ポーカーで戦略の勝率・BB/100などを評価します。
"""

import argparse
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent / "src"))

from burn_knobs import BurnState


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description='Strategy Lab: 標準ポーカー戦略評価'
    )
    
    parser.add_argument(
        '--hands',
        type=int,
        default=10000,
        help='実行するハンド数（デフォルト: 10000）'
    )
    
    parser.add_argument(
        '--parallel',
        type=int,
        default=1,
        help='並列プロセス数（デフォルト: 1）'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        default='standard_results',
        help='出力ディレクトリ（デフォルト: standard_results）'
    )
    
    parser.add_argument(
        '--strategies',
        nargs='+',
        default=['gto_approx', 'loose_gto', 'heuristic', 'random'],
        help='テストする戦略（デフォルト: すべて）'
    )
    
    parser.add_argument(
        '--opponents',
        nargs='+',
        default=['gto_approx', 'loose_gto', 'random'],
        help='対戦相手（デフォルト: gto_approx loose_gto random）'
    )
    
    parser.add_argument(
        '--seed',
        type=int,
        default=42,
        help='乱数シード（デフォルト: 42）'
    )
    
    parser.add_argument(
        '--bb-size',
        type=float,
        default=2.0,
        help='ビッグブラインドサイズ（デフォルト: 2.0）'
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Strategy Lab: 標準ポーカー戦略評価")
    print("=" * 60)
    print(f"ハンド数: {args.hands}")
    print(f"並列プロセス数: {args.parallel}")
    print(f"出力ディレクトリ: {args.output}")
    print(f"戦略: {args.strategies}")
    print(f"対戦相手: {args.opponents}")
    print(f"乱数シード: {args.seed}")
    print(f"BBサイズ: {args.bb_size}")
    print("=" * 60)
    print()
    
    # 標準状態を生成（焼却なしのBurnStateを使用）
    # これにより、焼却は発生せず通常のポーカーとして動作
    # BurnState(range_distortion, action_entropy, ev_floor) の形式
    standard_state = BurnState(
        range_distortion=0.0,  # レンジ歪みなし
        action_entropy=0.0,     # アクションエントロピーなし
        ev_floor=0.0            # EV下限なし
    )
    
    standard_states = [standard_state]
    
    # 実験を実行
    from experiment_controller import ExperimentController
    
    controller = ExperimentController(
        output_dir=Path(args.output),
        num_processes=args.parallel,
        seed=args.seed
    )
    
    print("通常ポーカー（焼却確率0%）で実験を実行します...")
    print()
    
    controller.run_experiment(
        strategy_names=args.strategies,
        opponent_names=args.opponents,
        burn_states=standard_states,
        hands_per_state=args.hands
    )
    
    print()
    print("=" * 60)
    print("実験完了")
    print(f"結果: {args.output}")
    print("=" * 60)
    print()
    print("評価指標:")
    print("  - 勝率: 各対戦での勝利割合")
    print("  - BB/100: 100ハンドあたりのビッグブラインド獲得量")
    print("  - 期待値: ハンドあたりの平均利益")


if __name__ == "__main__":
    main()