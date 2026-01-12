"""
データロガー

実験結果をJSON/CSV形式で保存します。
"""

import json
import csv
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
import sys

sys.path.append(str(Path(__file__).parent))

from burn_knobs import BurnState
from metrics import MatchMetrics, HandResult


class DataLogger:
    """
    実験データのロガー
    
    JSON形式でハンド履歴を含む詳細ログを保存し、
    CSV形式で集計結果を保存します。
    """
    
    def __init__(self, output_dir: Path):
        """
        Args:
            output_dir: 出力ディレクトリ
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def log_match_result(
        self,
        experiment_id: str,
        strategy_id: str,
        opponent_id: str,
        burn_state: BurnState,
        metrics: MatchMetrics,
        hand_results: List[HandResult]
    ) -> Path:
        """
        対戦結果をJSON形式でログ
        
        Args:
            experiment_id: 実験ID
            strategy_id: 戦略ID
            opponent_id: 対戦相手ID
            burn_state: 焼却状態
            metrics: 評価指標
            hand_results: ハンド結果のリスト
        
        Returns:
            保存したファイルのパス
        """
        # ファイル名を生成
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{strategy_id}_vs_{opponent_id}_{timestamp}.json"
        filepath = self.output_dir / filename
        
        # データを構築
        data = {
            "experiment_id": experiment_id,
            "strategy_id": strategy_id,
            "opponent_id": opponent_id,
            "burn_state": burn_state.to_dict(),
            "results": metrics.to_dict(),
            "timestamp": datetime.now().isoformat(),
            "hand_history": [
                {
                    "hand_id": r.hand_id,
                    "profit": r.profit,
                    "actions": r.actions
                }
                for r in hand_results
            ]
        }
        
        # JSON保存
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return filepath
    
    def append_to_summary_csv(
        self,
        strategy_id: str,
        opponent_id: str,
        burn_state: BurnState,
        metrics: MatchMetrics
    ) -> None:
        """
        集計結果をCSVに追記
        
        Args:
            strategy_id: 戦略ID
            opponent_id: 対戦相手ID
            burn_state: 焼却状態
            metrics: 評価指標
        """
        csv_path = self.output_dir / "summary.csv"
        
        # ヘッダー
        fieldnames = [
            'strategy_id', 'opponent_id',
            'range_distortion', 'action_entropy', 'ev_floor',
            'winrate_bb100', 'exploitability', 'variance',
            'hand_count', 'total_profit', 'min_profit', 'max_profit',
            'timestamp'
        ]
        
        # 新規作成時はヘッダーを書き込む
        write_header = not csv_path.exists()
        
        # データ行
        row = {
            'strategy_id': strategy_id,
            'opponent_id': opponent_id,
            'range_distortion': burn_state.range_distortion,
            'action_entropy': burn_state.action_entropy,
            'ev_floor': burn_state.ev_floor,
            'winrate_bb100': metrics.winrate_bb100,
            'exploitability': metrics.exploitability,
            'variance': metrics.variance,
            'hand_count': metrics.hand_count,
            'total_profit': metrics.total_profit,
            'min_profit': metrics.min_profit,
            'max_profit': metrics.max_profit,
            'timestamp': datetime.now().isoformat()
        }
        
        # CSV追記
        with open(csv_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if write_header:
                writer.writeheader()
            writer.writerow(row)
    
    def load_summary_csv(self) -> List[Dict[str, Any]]:
        """
        集計CSVを読み込み
        
        Returns:
            集計データのリスト
        """
        csv_path = self.output_dir / "summary.csv"
        
        if not csv_path.exists():
            return []
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            return list(reader)
    
    def load_match_result(self, filepath: Path) -> Dict[str, Any]:
        """
        対戦結果JSONを読み込み
        
        Args:
            filepath: JSONファイルのパス
        
        Returns:
            対戦結果データ
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)


if __name__ == "__main__":
    # テスト実行
    from burn_knobs import BurnState
    from metrics import MatchMetrics, HandResult
    
    print("データロガーのテスト\n")
    
    # テスト用ディレクトリ
    test_dir = Path("test_results")
    logger = DataLogger(test_dir)
    
    # ダミーデータ
    burn_state = BurnState(0.5, 0.25, 0.0)
    metrics = MatchMetrics(
        winrate_bb100=3.5,
        exploitability=0.12,
        variance=150.0,
        hand_count=100,
        total_profit=3.5,
        min_profit=-5.0,
        max_profit=10.0
    )
    hand_results = [
        HandResult(1, 2.5, ["raise", "call"]),
        HandResult(2, -1.0, ["fold"]),
    ]
    
    # JSON保存
    json_path = logger.log_match_result(
        experiment_id="test_exp_001",
        strategy_id="gto_approx",
        opponent_id="random",
        burn_state=burn_state,
        metrics=metrics,
        hand_results=hand_results
    )
    print(f"JSON保存: {json_path}")
    
    # CSV追記
    logger.append_to_summary_csv(
        strategy_id="gto_approx",
        opponent_id="random",
        burn_state=burn_state,
        metrics=metrics
    )
    print(f"CSV追記: {test_dir / 'summary.csv'}")
    
    # CSV読み込み
    summary = logger.load_summary_csv()
    print(f"\n集計データ: {len(summary)}行")
    if summary:
        print(f"最初の行: {summary[0]}")
