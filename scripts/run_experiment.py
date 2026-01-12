"""
実験実行スクリプト

コマンドラインから実験を実行します。
"""

import argparse
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent / "src"))

from burn_knobs import generate_burn_states, generate_sobol_states
from experiment_controller import ExperimentController


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description='Strategy Burn Lab: 焼却実験の実行'
    )
    
    parser.add_argument(
        '--burn-states',
        type=int,
        default=100,
        help='焼却状態数（デフォルト: 100）'
    )
    
    parser.add_argument(
        '--hands',
        type=int,
        default=500,
        help='各状態でのハンド数（デフォルト: 500）'
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
        default='results',
        help='出力ディレクトリ（デフォルト: results）'
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
        '--sampling',
        type=str,
        default='sobol',
        choices=['random', 'sobol', 'grid'],
        help='サンプリング手法 (random/sobol/grid)'
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Strategy Burn Lab: 焼却実験")
    print("=" * 60)
    print(f"焼却状態数: {args.burn_states}")
    print(f"各状態のハンド数: {args.hands}")
    print(f"並列プロセス数: {args.parallel}")
    print(f"出力ディレクトリ: {args.output}")
    print(f"戦略: {args.strategies}")
    print(f"対戦相手: {args.opponents}")
    print(f"乱数シード: {args.seed}")
    print("=" * 60)
    print()
    
    # 焼却状態を生成
    if args.sampling == 'sobol':
        print(f"Sobol列を使用して {args.burn_states} 状態を生成")
        burn_states = generate_sobol_states(n_samples=args.burn_states, seed=args.seed)
    elif args.sampling == 'grid':
        all_states = generate_burn_states()
        burn_states = all_states
        print(f"グリッド全探索: {len(burn_states)} 状態")
    else: # random
        all_states = generate_burn_states()
        if args.burn_states < len(all_states):
            import random
            random.seed(args.seed)
            burn_states = random.sample(all_states, args.burn_states)
            print(f"ランダムサンプリング: {len(all_states)} → {len(burn_states)}")
        else:
            burn_states = all_states
            print(f"全状態使用: {len(burn_states)}")
    
    # 実験を実行
    controller = ExperimentController(
        output_dir=Path(args.output),
        num_processes=args.parallel,
        seed=args.seed
    )
    
    controller.run_experiment(
        strategy_names=args.strategies,
        opponent_names=args.opponents,
        burn_states=burn_states,
        hands_per_state=args.hands
    )
    
    print()
    print("=" * 60)
    print("実験完了")
    print(f"結果: {args.output}")
    print("=" * 60)


if __name__ == "__main__":
    main()
