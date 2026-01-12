using System;

namespace PokerProject.AI
{
    /// <summary>
    /// 最強AIの挙動を定義する重み設定
    /// </summary>
    [Serializable]
    public struct StrongestAIConfig
    {
        public string Name;

        // 評価関数の重み
        public float HandStrengthWeight;    // ハンド強度の序列
        public float HandPotentialWeight;   // 将来性（ドロー等）
        public float BoardAdvantageWeight;  // ボード有利度
        public float PositionWeight;        // ポジション補正
        public float SprWeight;             // SPR（スタック/ポット比）補正
        public float DangerPenaltyWeight;   // 危険度ペナルティ（Wet + Low SPR + OOP）

        // 戦術的傾向
        public float BluffFrequency;        // ブラフ頻度
        public float AggressionFactor;      // 積極性（レイズサイズや頻度）
        
        // MCTS設定
        public int DefaultDepth;            // 通常時の探索深さ
        public int ProfileIndex;            // ソルバープロファイルのインデックス (0-9)
    }
}
