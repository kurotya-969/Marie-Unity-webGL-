"""
戦略一覧表示スクリプト

登録済みの戦略を一覧表示します。
"""

import sys
from pathlib import Path

# パスを追加
sys.path.append(str(Path(__file__).parent.parent / "src"))

from strategies.registry import StrategyRegistry


def main():
    """戦略一覧を表示"""
    print("=== Strategy Burn Lab: 登録済み戦略 ===\n")
    
    # レジストリを初期化
    registry = StrategyRegistry()
    count = registry.auto_discover()
    
    print(f"検出された戦略数: {count}\n")
    
    # 戦略一覧を表示
    strategies = registry.list_strategies()
    
    if not strategies:
        print("戦略が見つかりませんでした。")
        return
    
    print("戦略名:")
    for i, name in enumerate(strategies, 1):
        print(f"  {i}. {name}")
    
    print("\n使用例:")
    print("  registry = StrategyRegistry()")
    print("  registry.auto_discover()")
    print(f"  strategy = registry.create('{strategies[0]}')")


if __name__ == "__main__":
    main()
