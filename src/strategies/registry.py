"""
戦略レジストリシステム

strategies/ ディレクトリから戦略クラスを自動検出し、
動的にインスタンス化するプラグインシステムを提供します。
"""

import inspect
import importlib
import logging
from pathlib import Path
from typing import Dict, Type, List, Any, Optional
import yaml

from .base import Strategy

logger = logging.getLogger(__name__)


class StrategyRegistry:
    """
    戦略のプラグインシステム
    
    機能：
    - strategies/ ディレクトリから自動検出
    - 設定ファイル（YAML）からの読み込み
    - 戦略の動的インスタンス化
    
    Example:
        registry = StrategyRegistry()
        registry.auto_discover()
        
        # 戦略インスタンスを生成
        strategy = registry.create("gto_approx", cfr_iterations=1000)
    """
    
    def __init__(self, strategies_dir: Optional[Path] = None):
        """
        Args:
            strategies_dir: 戦略ディレクトリのパス
                           デフォルト: このファイルと同じディレクトリ
        """
        if strategies_dir is None:
            strategies_dir = Path(__file__).parent
        
        self.strategies_dir = Path(strategies_dir)
        self._registry: Dict[str, Type[Strategy]] = {}
    
    def auto_discover(self) -> int:
        """
        strategies/ 内のすべての戦略クラスを自動検出
        
        Returns:
            検出された戦略の数
        """
        discovered_count = 0
        
        for py_file in self.strategies_dir.glob("*.py"):
            # 特殊ファイルをスキップ
            if py_file.name.startswith("_") or py_file.stem in ["base", "registry"]:
                continue
            
            try:
                # モジュールを動的インポート
                module_name = f"strategies.{py_file.stem}"
                module = importlib.import_module(module_name)
                
                # Strategy を継承したクラスを検出
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if issubclass(obj, Strategy) and obj is not Strategy:
                        self.register(obj)
                        discovered_count += 1
                        
            except Exception as e:
                logger.warning(f"Failed to import {py_file.name}: {e}")
        
        logger.info(f"Auto-discovered {discovered_count} strategies")
        return discovered_count
    
    def register(self, strategy_class: Type[Strategy]) -> None:
        """
        戦略クラスを登録
        
        Args:
            strategy_class: 登録する戦略クラス
        """
        name = strategy_class.STRATEGY_NAME or strategy_class.__name__
        
        if name in self._registry:
            logger.warning(f"Strategy '{name}' is already registered, overwriting")
        
        self._registry[name] = strategy_class
        logger.info(f"Registered strategy: {name}")
    
    def create(self, name: str, **kwargs) -> Strategy:
        """
        戦略インスタンスを生成
        
        Args:
            name: 戦略名
            **kwargs: 戦略のコンストラクタに渡すパラメータ
        
        Returns:
            戦略インスタンス
        
        Raises:
            ValueError: 未登録の戦略名が指定された場合
        """
        if name not in self._registry:
            available = ", ".join(self._registry.keys())
            raise ValueError(
                f"Unknown strategy: '{name}'. "
                f"Available strategies: {available}"
            )
        
        strategy_class = self._registry[name]
        
        try:
            return strategy_class(**kwargs)
        except TypeError as e:
            logger.error(f"Failed to instantiate {name}: {e}")
            raise
    
    def list_strategies(self) -> List[str]:
        """
        登録済み戦略の一覧を取得
        
        Returns:
            戦略名のリスト
        """
        return list(self._registry.keys())
    
    def load_from_config(self, config_path: Path) -> Dict[str, Strategy]:
        """
        YAML設定ファイルから戦略をロード
        
        Args:
            config_path: strategies.yaml のパス
        
        Returns:
            戦略インスタンスの辞書 {name: strategy}
        """
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        strategies = {}
        
        for strategy_config in config.get('strategies', []):
            # 無効化されている戦略はスキップ
            if not strategy_config.get('enabled', True):
                logger.info(f"Skipping disabled strategy: {strategy_config['name']}")
                continue
            
            name = strategy_config['name']
            class_name = strategy_config.get('class', name)
            params = strategy_config.get('params', {})
            
            # クラス名で検索（STRATEGY_NAMEではなくクラス名の場合に対応）
            strategy_class = None
            for registered_name, cls in self._registry.items():
                if cls.__name__ == class_name or registered_name == class_name:
                    strategy_class = cls
                    break
            
            if strategy_class is None:
                logger.warning(f"Strategy class '{class_name}' not found, skipping")
                continue
            
            try:
                strategies[name] = strategy_class(**params)
                logger.info(f"Loaded strategy '{name}' from config")
            except Exception as e:
                logger.error(f"Failed to create strategy '{name}': {e}")
        
        return strategies
    
    def get_opponents_from_config(self, config_path: Path) -> List[str]:
        """
        設定ファイルから対戦相手のリストを取得
        
        Args:
            config_path: strategies.yaml のパス
        
        Returns:
            対戦相手の戦略名リスト
        """
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        return config.get('opponents', [])


# グローバルレジストリインスタンス
_global_registry: Optional[StrategyRegistry] = None


def get_global_registry() -> StrategyRegistry:
    """
    グローバルレジストリインスタンスを取得
    
    Returns:
        グローバルレジストリ
    """
    global _global_registry
    
    if _global_registry is None:
        _global_registry = StrategyRegistry()
        _global_registry.auto_discover()
    
    return _global_registry


if __name__ == "__main__":
    # テスト実行
    logging.basicConfig(level=logging.INFO)
    
    registry = StrategyRegistry()
    count = registry.auto_discover()
    
    print(f"\n検出された戦略数: {count}")
    print(f"登録済み戦略: {registry.list_strategies()}")
