"""
可視化スクリプト

実験結果を可視化します。
"""

import argparse
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import numpy as np
import sys

sys.path.append(str(Path(__file__).parent.parent / "src"))

# 日本語フォント設定（Windows）
plt.rcParams['font.sans-serif'] = ['MS Gothic', 'Yu Gothic', 'Meiryo']
plt.rcParams['axes.unicode_minus'] = False

# スタイル設定
sns.set_style("whitegrid")
sns.set_palette("husl")


def load_summary_data(input_path: Path) -> pd.DataFrame:
    """
    集計CSVを読み込み
    
    Args:
        input_path: 結果ディレクトリまたは集計ファイルのパス
    
    Returns:
        集計データのDataFrame
    """
    if input_path.is_file():
        csv_path = input_path
    else:
        csv_path = input_path / "summary.csv"
    
    if not csv_path.exists():
        raise FileNotFoundError(f"集計ファイルが見つかりません: {csv_path}")
    
    print(f"読み込み中: {csv_path}")
    df = pd.read_csv(csv_path)
    
    # 数値型に変換
    numeric_cols = ['range_distortion', 'action_entropy', 'ev_floor', 
                    'winrate_bb100', 'exploitability', 'variance']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    return df


def plot_burn_map_heatmap(df: pd.DataFrame, output_dir: Path):
    """
    焼却マップのヒートマップを生成
    
    Args:
        df: 集計データ
        output_dir: 出力ディレクトリ
    """
    # 戦略ごとにプロット
    strategies = df['strategy_id'].unique()
    
    for strategy in strategies:
        strategy_df = df[df['strategy_id'] == strategy]
        
        # レンジ歪み率 vs 行動温度のヒートマップ
        pivot = strategy_df.pivot_table(
            values='winrate_bb100',
            index='action_entropy',
            columns='range_distortion',
            aggfunc='mean'
        )
        
        plt.figure(figsize=(10, 8))
        sns.heatmap(pivot, annot=True, fmt='.1f', cmap='RdYlGn', center=0)
        plt.title(f'焼却マップ: {strategy}\n(Winrate bb/100)', fontsize=14)
        plt.xlabel('レンジ歪み率', fontsize=12)
        plt.ylabel('行動温度', fontsize=12)
        plt.tight_layout()
        
        output_path = output_dir / f'burn_map_{strategy}.png'
        plt.savefig(output_path, dpi=150)
        plt.close()
        
        print(f"生成: {output_path}")


def plot_collapse_trajectory(df: pd.DataFrame, output_dir: Path):
    """
    崩壊軌跡をプロット
    
    Args:
        df: 集計データ
        output_dir: 出力ディレクトリ
    """
    strategies = df['strategy_id'].unique()
    
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    
    knobs = [
        ('range_distortion', 'レンジ歪み率'),
        ('action_entropy', '行動温度'),
        ('ev_floor', 'EV下限制約')
    ]
    
    for idx, (knob, label) in enumerate(knobs):
        ax = axes[idx]
        
        for strategy in strategies:
            strategy_df = df[df['strategy_id'] == strategy]
            
            # ノブごとに平均Winrateを計算
            trajectory = strategy_df.groupby(knob)['winrate_bb100'].mean().sort_index()
            
            ax.plot(trajectory.index, trajectory.values, marker='o', label=strategy)
        
        ax.set_xlabel(label, fontsize=11)
        ax.set_ylabel('Winrate (bb/100)', fontsize=11)
        ax.set_title(f'{label}の影響', fontsize=12)
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.axhline(y=0, color='red', linestyle='--', alpha=0.5)
    
    plt.tight_layout()
    output_path = output_dir / 'collapse_trajectory.png'
    plt.savefig(output_path, dpi=150)
    plt.close()
    
    print(f"生成: {output_path}")


def plot_strategy_vulnerability(df: pd.DataFrame, output_dir: Path):
    """
    戦略脆弱性プロファイルをプロット
    
    Args:
        df: 集計データ
        output_dir: 出力ディレクトリ
    """
    strategies = df['strategy_id'].unique()
    
    # 各戦略の統計量を計算
    stats = []
    for strategy in strategies:
        strategy_df = df[df['strategy_id'] == strategy]
        
        stats.append({
            'strategy': strategy,
            'mean_winrate': strategy_df['winrate_bb100'].mean(),
            'std_winrate': strategy_df['winrate_bb100'].std(),
            'min_winrate': strategy_df['winrate_bb100'].min(),
            'max_winrate': strategy_df['winrate_bb100'].max(),
            'mean_variance': strategy_df['variance'].mean()
        })
    
    stats_df = pd.DataFrame(stats)
    
    # プロット
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    # Winrateの分布
    ax1 = axes[0]
    x = np.arange(len(strategies))
    width = 0.6
    
    ax1.bar(x, stats_df['mean_winrate'], width, 
            yerr=stats_df['std_winrate'], capsize=5, alpha=0.7)
    ax1.set_xlabel('戦略', fontsize=11)
    ax1.set_ylabel('平均Winrate (bb/100)', fontsize=11)
    ax1.set_title('戦略別平均Winrate（±標準偏差）', fontsize=12)
    ax1.set_xticks(x)
    ax1.set_xticklabels(stats_df['strategy'], rotation=45, ha='right')
    ax1.axhline(y=0, color='red', linestyle='--', alpha=0.5)
    ax1.grid(True, alpha=0.3)
    
    # Winrateレンジ
    ax2 = axes[1]
    for i, row in stats_df.iterrows():
        ax2.plot([i, i], [row['min_winrate'], row['max_winrate']], 
                'o-', linewidth=2, markersize=8, label=row['strategy'])
    
    ax2.set_xlabel('戦略', fontsize=11)
    ax2.set_ylabel('Winrateレンジ (bb/100)', fontsize=11)
    ax2.set_title('戦略別Winrateレンジ（最小-最大）', fontsize=12)
    ax2.set_xticks(range(len(strategies)))
    ax2.set_xticklabels(stats_df['strategy'], rotation=45, ha='right')
    ax2.axhline(y=0, color='red', linestyle='--', alpha=0.5)
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    output_path = output_dir / 'strategy_vulnerability_profile.png'
    plt.savefig(output_path, dpi=150)
    plt.close()
    
    print(f"生成: {output_path}")
    
    return stats_df


def generate_summary_report(df: pd.DataFrame, stats_df: pd.DataFrame, output_dir: Path):
    """
    サマリーレポートを生成
    
    Args:
        df: 集計データ
        stats_df: 戦略統計データ
        output_dir: 出力ディレクトリ
    """
    report_path = output_dir / 'summary_report.txt'
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("=" * 60 + "\n")
        f.write("Strategy Burn Lab: 実験結果サマリー\n")
        f.write("=" * 60 + "\n\n")
        
        # 基本統計
        f.write("## 実験規模\n")
        f.write(f"総対戦数: {len(df)}\n")
        f.write(f"戦略数: {df['strategy_id'].nunique()}\n")
        f.write(f"対戦相手数: {df['opponent_id'].nunique()}\n")
        f.write(f"焼却状態数: {len(df) // (df['strategy_id'].nunique() * df['opponent_id'].nunique())}\n\n")
        
        # 戦略別統計
        f.write("## 戦略別統計\n\n")
        for _, row in stats_df.iterrows():
            f.write(f"### {row['strategy']}\n")
            f.write(f"  平均Winrate: {row['mean_winrate']:.2f} bb/100\n")
            f.write(f"  標準偏差: {row['std_winrate']:.2f}\n")
            f.write(f"  レンジ: [{row['min_winrate']:.2f}, {row['max_winrate']:.2f}]\n")
            f.write(f"  平均分散: {row['mean_variance']:.2f}\n\n")
        
        # 最良・最悪の焼却状態
        f.write("## 極端な焼却状態\n\n")
        best = df.loc[df['winrate_bb100'].idxmax()]
        worst = df.loc[df['winrate_bb100'].idxmin()]
        
        f.write("### 最良の状態\n")
        f.write(f"  戦略: {best['strategy_id']}\n")
        f.write(f"  Winrate: {best['winrate_bb100']:.2f} bb/100\n")
        f.write(f"  焼却状態: R={best['range_distortion']:.2f}, T={best['action_entropy']:.2f}, E={best['ev_floor']:.2f}\n\n")
        
        f.write("### 最悪の状態\n")
        f.write(f"  戦略: {worst['strategy_id']}\n")
        f.write(f"  Winrate: {worst['winrate_bb100']:.2f} bb/100\n")
        f.write(f"  焼却状態: R={worst['range_distortion']:.2f}, T={worst['action_entropy']:.2f}, E={worst['ev_floor']:.2f}\n\n")
    
    print(f"生成: {report_path}")


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description='Strategy Burn Lab: 結果の可視化'
    )
    
    parser.add_argument(
        '--input',
        type=str,
        default='results',
        help='結果ディレクトリ（デフォルト: results）'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        default='visualizations',
        help='出力ディレクトリ（デフォルト: visualizations）'
    )
    
    args = parser.parse_args()
    
    results_dir = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print("Strategy Burn Lab: 可視化")
    print("=" * 60)
    print(f"入力: {results_dir}")
    print(f"出力: {output_dir}")
    print("=" * 60)
    print()
    
    # データ読み込み
    print("データ準備中...")
    df = load_summary_data(results_dir)
    print(f"読み込み完了: {len(df)}行\n")
    
    # 出力先がデフォルトで入力がファイルの場合、入力ファイルの親ディレクトリを基準にする
    if results_dir.is_file() and args.output == 'visualizations':
        output_dir = results_dir.parent / 'visualizations'
        output_dir.mkdir(parents=True, exist_ok=True)
        print(f"出力先調整: {output_dir}")
    
    # 可視化生成
    print("可視化生成中...\n")
    
    plot_burn_map_heatmap(df, output_dir)
    plot_collapse_trajectory(df, output_dir)
    stats_df = plot_strategy_vulnerability(df, output_dir)
    generate_summary_report(df, stats_df, output_dir)
    
    print("可視化完了")
    print(f"出力: {output_dir}")


if __name__ == "__main__":
    main()
