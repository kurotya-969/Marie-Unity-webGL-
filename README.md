# Marie

Unity/webGLで動く（かもしれない、世界は君たちの手の中）な超軽量CFR+ルールベースのポーカーbotです。

## 概要

本プロジェクトは、ポーカーソルバーを極限まで軽量にしながらある程度の精度を欲したモデルです。

### 中心仮説

> なんかプリフロだけ抽象CFR+でフロップからルールベースの方が計算資源が極限までない世界なら強くね？

GTO/CFRは「前提が成立している世界」でのみ最適であり、前提（計算資源）を連続的に破壊すると、戦略は非連続に崩壊します。

## 特徴
軽い！itaration=2000で回したバイナリまで無料！みんな使える！

#　動作環境
numpy>=1.24.0
scipy>=1.10.0
pandas>=2.0.0
matplotlib>=3.7.0
seaborn>=0.12.0
pyyaml>=6.0
pokerkit>=0.5.0
pytest>=7.4.0

## 実験規模（簡易版）

- **焼却ノブ**：3種（レンジ歪み率、行動温度、EV下限制約）
- **各ノブ**：5点（0, 0.25, 0.5, 0.75, 1.0）
- **組み合わせ**：5³ = 125状態
- **各状態**：2,000ハンド
- なんと各要素の焼却実験までできるんだこれが。

## クイックスタート

### 環境構築

```bash
# 依存ライブラリのインストール
pip install -r requirements.txt
```

### 戦略の追加

1. `src/strategies/` に新しい `.py` ファイルを作成
2. `Strategy` 基底クラスを継承
3. `config/strategies.yaml` に設定を追加

### 実験実行

```bash
# 小規模テスト（10状態 × 100ハンド）
python scripts/run_experiment.py --burn-states 10 --hands 100 --output test_results/

# フル実験（125状態 × 2,000ハンド）
python scripts/run_experiment.py --burn-states 125 --hands 2000 --parallel 8 --output results/
```
#普通に評価したい時（burn0)
python scripts/run.py(お好みで--opponentsとか--handsとか)

### 可視化

```bash
python scripts/visualize.py --input results/ --output visualizations/
```

## プロジェクト構造

```
burn-out/
├── src/                    # ソースコード
│   ├── strategies/         # 戦略実装（プラグイン形式）
│   ├── burn_knobs.py       # 焼却ノブ定義
│   ├── match_engine.py     # 対戦エンジン
│   └── metrics.py          # 評価指標
├── config/                 # 設定ファイル
│   └── strategies.yaml     # 戦略設定
├── scripts/                # 実行スクリプト
├── tests/                  # テストコード
└── results/                # 実験結果
```
（これが基本ですけど散らばってます、内容が動的に変更）
## ライセンス

MIT License

# fork/prについて
自由(PR通るかは気分。）ただし知的財産権は放棄せず、またforkに関してはfork先をこちらの改善に役立てる場合がある。（ただしデータが財産であることを鑑み、ここのライブラリ以外の改善に使う場合には作者に連絡、協議してから用いるものとする。）
また、一切の自作発言を被fork/forkに関わらず禁止する。

# 参考文献 / 論文リンク
https://www.science.org/doi/10.1126/science.aar6404(Mastering Chess and Shogi by Self‑Play with a General Reinforcement Learning Algorithm)

@incollection{2007-nips-cfr,
  title = {Regret Minimization in Games with Incomplete Information},
  author = {Zinkevich, M. and Johanson, M. and Bowling, M. and Piccione, C.},
  booktitle = {Advances in Neural Information Processing Systems 20 (NIPS)},
  year = {2008}
}
