"""
実験制御システム

焼却実験全体を制御し、並列実行を管理します。
"""

import multiprocessing as mp
from pathlib import Path
from typing import List, Dict, Optional
import logging
from datetime import datetime
import sys
import random

sys.path.append(str(Path(__file__).parent))

from burn_knobs import BurnState, generate_burn_states
from strategies.registry import StrategyRegistry
from match_engine import MatchEngine, GameConfig
from metrics import MetricsCalculator
from data_logger import DataLogger

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ExperimentController:
    """
    実験制御器
    
    焼却実験全体を制御し、並列実行を管理します。
    """
    
    def __init__(
        self,
        output_dir: Path,
        config_path: Optional[Path] = None,
        num_processes: int = 1,
        seed: int = 42
    ):
        """
        Args:
            output_dir: 出力ディレクトリ
            config_path: 戦略設定ファイルのパス
            num_processes: 並列プロセス数
            seed: 乱数シード
        """
        self.output_dir = Path(output_dir)
        self.config_path = config_path
        self.num_processes = num_processes
        self.seed = seed
        
        # レジストリを初期化
        self.registry = StrategyRegistry()
        self.registry.auto_discover()
        
        # ロガーを初期化
        self.logger = DataLogger(self.output_dir)
        
        logger.info(f"実験制御器を初期化: {self.registry.list_strategies()}")
    
    def run_experiment(
        self,
        strategy_names: List[str],
        opponent_names: List[str],
        burn_states: List[BurnState],
        hands_per_state: int = 2000
    ) -> None:
        """
        実験を実行
        
        Args:
            strategy_names: テストする戦略名のリスト
            opponent_names: 対戦相手の戦略名のリスト
            burn_states: 焼却状態のリスト
            hands_per_state: 各状態でのハンド数
        """
        experiment_id = f"burn_lab_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        logger.info(f"実験開始: {experiment_id}")
        logger.info(f"戦略数: {len(strategy_names)}")
        logger.info(f"対戦相手数: {len(opponent_names)}")
        logger.info(f"焼却状態数: {len(burn_states)}")
        logger.info(f"各状態のハンド数: {hands_per_state}")
        
        total_matches = len(strategy_names) * len(opponent_names) * len(burn_states)
        logger.info(f"総対戦数: {total_matches}")
        
        # タスクリストを生成
        tasks = []
        for strategy_name in strategy_names:
            for opponent_name in opponent_names:
                for burn_state in burn_states:
                    tasks.append({
                        'experiment_id': experiment_id,
                        'strategy_name': strategy_name,
                        'opponent_name': opponent_name,
                        'burn_state': burn_state,
                        'hands': hands_per_state,
                        'seed': self.seed
                    })
        
        # タスクをシャッフル（進捗が偏らないように）
        random.shuffle(tasks)
        
        # 並列実行
        if self.num_processes > 1:
            logger.info(f"並列実行開始: {self.num_processes}プロセス")
            with mp.Pool(self.num_processes) as pool:
                pool.map(self._run_single_match, tasks)
        else:
            logger.info("シーケンシャル実行開始")
            for task in tasks:
                self._run_single_match(task)
        
        logger.info(f"実験完了: {experiment_id}")
    
    def _run_single_match(self, task: Dict) -> None:
        """
        単一の対戦を実行（並列実行用）
        
        Args:
            task: タスク情報
        """
        try:
            # 戦略を生成
            registry = StrategyRegistry()
            registry.auto_discover()
            
            strategy = registry.create(task['strategy_name'])
            opponent = registry.create(task['opponent_name'])
            
            # 対戦を実行
            engine = MatchEngine(seed=task['seed'])
            
            # 対戦相手は焼却なし
            opponent_burn_state = BurnState(0.0, 0.0, 0.0)
            
            results = engine.run_match(
                strategy, opponent,
                task['burn_state'], opponent_burn_state,
                task['hands']
            )
            
            # 評価指標を計算
            metrics = MetricsCalculator.calculate_metrics(results)
            
            # ログ保存
            data_logger = DataLogger(self.output_dir)
            data_logger.log_match_result(
                task['experiment_id'],
                task['strategy_name'],
                task['opponent_name'],
                task['burn_state'],
                metrics,
                results
            )
            
            # CSV追記
            data_logger.append_to_summary_csv(
                task['strategy_name'],
                task['opponent_name'],
                task['burn_state'],
                metrics
            )
            
            logger.info(
                f"完了: {task['strategy_name']} vs {task['opponent_name']} "
                f"(R={task['burn_state'].range_distortion:.2f}, "
                f"T={task['burn_state'].action_entropy:.2f}, "
                f"E={task['burn_state'].ev_floor:.2f}) "
                f"→ {metrics.winrate_bb100:.2f} bb/100"
            )
            
        except Exception as e:
            logger.error(f"エラー: {task['strategy_name']} vs {task['opponent_name']}: {e}")


def run_simple_experiment(
    num_burn_states: int = 10,
    hands_per_state: int = 100,
    output_dir: str = "test_results"
) -> None:
    """
    簡易実験を実行（テスト用）
    
    Args:
        num_burn_states: 焼却状態数
        hands_per_state: 各状態でのハンド数
        output_dir: 出力ディレクトリ
    """
    # 焼却状態を生成（サンプリング）
    all_states = generate_burn_states()
    import random
    burn_states = random.sample(all_states, min(num_burn_states, len(all_states)))
    
    # 実験を実行
    controller = ExperimentController(
        output_dir=Path(output_dir),
        num_processes=1,
        seed=42
    )
    
    controller.run_experiment(
        strategy_names=['gto_approx', 'heuristic'],
        opponent_names=['random'],
        burn_states=burn_states,
        hands_per_state=hands_per_state
    )


if __name__ == "__main__":
    print("実験制御システムのテスト\n")
    
    # 小規模テスト（10状態 × 100ハンド）
    run_simple_experiment(
        num_burn_states=5,
        hands_per_state=50,
        output_dir="test_results"
    )
    
    print("\n実験完了。test_results を確認してください。")
