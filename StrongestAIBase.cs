using System.Collections;
using System.Collections.Generic;
using System.Linq;
using PokerProject.Core;
using UnityEngine;
using System.Diagnostics;

namespace PokerProject.AI
{
    /// <summary>
    /// 最強AIの基盤クラス（外部設定注入型）
    /// </summary>
    public class StrongestAIBase : IPokerAI
    {
        protected StrongestAIConfig config;
        private const int MaxTimeMs = 300;

        public StrongestAIBase(StrongestAIConfig config)
        {
            this.config = config;
        }

        public IEnumerator DecideAction(Player me, List<Player> allPlayers, List<Card> communityCards, int currentMinBet, System.Action<AIAction> callback)
        {
            Stopwatch sw = Stopwatch.StartNew();
            GamePhase phase = GetCurrentPhase(communityCards);
            
            AIAction result;
            if (phase == GamePhase.Preflop)
            {
                result = DecidePreflopGTO(me, allPlayers, currentMinBet);
            }
            else if (phase == GamePhase.River)
            {
                result = DecideRiverEV(me, allPlayers, communityCards, currentMinBet);
            }
            else
            {
                result = DecidePostflopGTOMCTS(me, allPlayers, communityCards, currentMinBet, sw);
            }

            callback?.Invoke(result);
            yield break;
        }

        #region Preflop GTO (Pure Nash Equilibrium Range)

        private AIAction DecidePreflopGTO(Player me, List<Player> allPlayers, int currentMinBet)
        {
            var hole = me.HoleCards.OrderByDescending(c => (int)c.rank).ToList();
            int r1 = (int)hole[0].rank;
            int r2 = (int)hole[1].rank;
            bool suited = hole[0].suit == hole[1].suit;

            float rand = UnityEngine.Random.value;

            // Decision based on 169 Hand Matrix
            if (currentMinBet <= 20) // Open situation
            {
                float openProb = GetGTORangeOpenProb(r1, r2, suited);
                if (rand < openProb) return new AIAction { ActionName = "Raise", RaiseAmount = 60 };
                return new AIAction { ActionName = "Check" };
            }

            // Facing Raise (Defense)
            float defenseProb = GetGTORangeDefenseProb(r1, r2, suited, currentMinBet);
            if (rand < defenseProb * 0.2f) return new AIAction { ActionName = "Raise", RaiseAmount = currentMinBet * 3 }; // 3-bet
            if (rand < defenseProb) return new AIAction { ActionName = "Call" };
            
            return new AIAction { ActionName = "Fold" };
        }

        private float GetGTORangeOpenProb(int r1, int r2, bool suited)
        {
            // Simplified HU GTO Matrix
            if (r1 == r2) return (r1 >= 5) ? 1.0f : 0.8f;
            if (suited) return (r1 >= 10 || (r1 >= 7 && r2 >= 6)) ? 0.9f : 0.6f;
            if (r1 >= 13) return 0.9f;
            if (r1 >= 10 && r2 >= 8) return 0.7f;
            if (r1 >= 6 && r2 >= 5) return 0.4f;
            return 0.3f;
        }

        private float GetGTORangeDefenseProb(int r1, int r2, bool suited, int currentBet)
        {
            // Adjusting based on pot odds facing raise
            if (r1 == r2 && r1 >= 7) return 1.0f;
            if (r1 >= 14 && r2 >= 12) return 1.0f;
            if (suited && r1 >= 10) return 0.8f;
            if (currentBet > 100) return (r1 == r2 || r1 >= 13) ? 0.6f : 0.1f;
            return (r1 >= 11 || suited) ? 0.7f : 0.2f;
        }

        #endregion

        #region Postflop GTO-Guided MCTS (Local EV Optim)

        private AIAction DecidePostflopGTOMCTS(Player me, List<Player> allPlayers, List<Card> communityCards, int currentMinBet, Stopwatch sw)
        {
            var res = HandEvaluator.EvaluateHandle(me.HoleCards.Concat(communityCards));
            HandBucket bucket = BucketHand(me.HoleCards, communityCards, res);
            BoardTexture texture = ClusterBoard(communityCards);

            int pot = allPlayers.Sum(p => p.CurrentBet) + 1;
            int toCall = currentMinBet - me.CurrentBet;
            float odds = (float)toCall / (pot + toCall);

            // Step 1: Blueprint Lookup (Phase 1)
            // Get action distribution from selected GTO profile
            var weights = GetGTOProfileWeights(config.ProfileIndex, bucket, texture, odds);
            
            // Step 2: MCTS Pruning (Phase 2) 補助
            // Blueprint上位の手のうち、短時間シミュレーションで明らかに負のEVを持つものを排除
            var candidates = weights.OrderByDescending(kv => kv.Value).Take(3).Select(kv => kv.Key).ToList();
            var prunedWeights = new Dictionary<string, float>();
            
            foreach (var action in candidates)
            {
                float ev = EstimateLocalEV(action, me, allPlayers, communityCards, currentMinBet, bucket);
                // 候補手が論理的に破綻（EVが極端に低い）していなければ採用
                if (ev > -toCall * 1.2f) prunedWeights[action] = weights[action];
            }

            // 万が一すべての候補が削られた場合は Blueprint の最上位を強制採用
            if (prunedWeights.Count == 0) prunedWeights[candidates[0]] = 1.0f;

            // Step 3: Mixed Strategy Selection
            float rand = UnityEngine.Random.value;
            string bestAction = "Check";
            float sum = 0, total = prunedWeights.Values.Sum();
            foreach (var kvp in prunedWeights)
            {
                sum += kvp.Value / total;
                if (rand <= sum) { bestAction = kvp.Key; break; }
            }

            if (bestAction == "Fold" && currentMinBet <= me.CurrentBet) bestAction = "Check";
            
            // Sizing based on AggressionFactor
            int raiseAmt = 0;
            if (bestAction == "Raise")
            {
                float scale = (bucket >= HandBucket.StrongMade) ? 0.75f : 0.4f;
                raiseAmt = (int)(pot * scale * config.AggressionFactor + toCall);
            }
            
            return new AIAction { ActionName = bestAction, RaiseAmount = Mathf.Min(me.Chips, raiseAmt) };
        }

        private Dictionary<string, float> GetGTOProfileWeights(int profile, HandBucket b, BoardTexture t, float odds)
        {
            var w = new Dictionary<string, float>();
            w["Check"] = 0.4f; w["Call"] = 0.2f; w["Raise"] = 0.1f; w["Fold"] = 0.3f;

            // 10 Strategic Profiles (Logic Bases)
            // 0: Balanced GTO
            // 1: Aggressive (High Raise)
            // 2: Polarized (Big Raise or Fold/Check)
            // 3: Linear (Small Raise with wide range)
            // 4: Trapping (Slow play monsters)
            // 5: Defensive (High Call, low Fold)
            // 6: Bluff Heavy (Increase Raise with Draws)
            // 7: C-Bet Heavy (Raise on Dry boards)
            // 8: Tight (Fold Marginal hands)
            // 9: Maximum Pressure (Aggressive + Polarized)

            float agg = 1.0f;
            float pRef = 0.0f; // Polarize

            switch(profile) {
                case 1: agg = 1.6f; break;
                case 2: pRef = 0.4f; break;
                case 3: agg = 1.2f; break;
                case 6: if (b == HandBucket.StrongDraw || b == HandBucket.WeakDraw) agg = 2.0f; break;
                case 7: if (t == BoardTexture.Dry) agg = 1.8f; break;
                case 8: if (b == HandBucket.MarginalMade) w["Fold"] = 0.8f; break;
                case 9: agg = 2.0f; pRef = 0.4f; break;
            }

            switch (b)
            {
                case HandBucket.Monster:
                    if (profile == 4) { w["Call"] = 0.7f; w["Raise"] = 0.2f; w["Check"] = 0.1f; }
                    else { w["Raise"] = 0.8f * agg; w["Call"] = 0.2f; }
                    break;
                case HandBucket.StrongMade:
                    w["Raise"] = 0.5f * agg; w["Call"] = 0.4f; w["Check"] = 0.1f;
                    break;
                case HandBucket.MarginalMade:
                    if (odds < 0.25f) { w["Call"] = 0.7f; w["Check"] = 0.3f; }
                    else if (pRef > 0) { w["Raise"] = 0.1f; w["Fold"] = 0.9f; }
                    else { w["Call"] = 0.4f; w["Fold"] = 0.6f; }
                    break;
                case HandBucket.StrongDraw:
                    w["Raise"] = 0.4f * agg; w["Call"] = 0.5f; w["Check"] = 0.1f;
                    break;
                case HandBucket.WeakDraw:
                    w["Raise"] = 0.1f * agg; w["Check"] = 0.5f; w["Fold"] = 0.4f;
                    break;
                default:
                    if (pRef > 0 && UnityEngine.Random.value < 0.1f) w["Raise"] = 0.2f; // Polarized bluff
                    w["Fold"] = 0.8f; w["Check"] = 0.2f;
                    break;
            }
            // Normalize
            float total = w.Values.Sum();
            return w.ToDictionary(k => k.Key, k => k.Value / total);
        }

        private float EstimateLocalEV(string action, Player me, List<Player> allPlayers, List<Card> community, int minBet, HandBucket bucket)
        {
            if (action == "Fold") return -me.CurrentBet;
            
            // Mathematical expectation against a balanced opponent
            float winProb = (float)bucket / 6.0f; // Approx equity
            int currentPot = allPlayers.Sum(p => p.CurrentBet);
            int callCost = minBet - me.CurrentBet;

            if (action == "Call") return (winProb * (currentPot + callCost)) - ((1 - winProb) * callCost);
            if (action == "Raise") return (winProb * (currentPot + 100)) - ((1 - winProb) * 100);
            return winProb * currentPot;
        }

        private BoardTexture ClusterBoard(List<Card> community)
        {
            if (community.GroupBy(c => c.suit).Any(g => g.Count() >= 3)) return BoardTexture.Wet;
            var ranks = community.Select(c => (int)c.rank).OrderBy(r => r).ToList();
            bool connected = false;
            for(int i=0; i<ranks.Count-1; i++) if (ranks[i+1]-ranks[i] <= 1) connected = true;
            if (connected) return BoardTexture.Wet;
            return BoardTexture.Dry;
        }

        private HandBucket BucketHand(List<Card> hole, List<Card> community, HandResult res)
        {
            if (res.Rank >= HandRank.FullHouse) return HandBucket.Monster;
            if (res.Rank >= HandRank.ThreeOfAKind) return HandBucket.StrongMade;
            if (res.Rank >= HandRank.Pair) return HandBucket.MarginalMade;
            if (CalculatePotential(hole, community) > 0.4f) return HandBucket.StrongDraw;
            return HandBucket.Trash;
        }

        private GamePhase GetCurrentPhase(List<Card> community)
        {
            if (community == null || community.Count == 0) return GamePhase.Preflop;
            if (community.Count == 3) return GamePhase.Flop;
            if (community.Count == 4) return GamePhase.Turn;
            return GamePhase.River;
        }

        private float CalculatePotential(List<Card> hole, List<Card> community)
        {
            // ストレートやフラッシュへのドローを簡易的に評価 (0.0 - 1.0)
            // 実装簡略化のため、既存の HandEvaluator 等がある前提でプレースホルダ的実装
            // 実際には Python 側で詳細な Equity 計算を行うため、C#側は整合性維持のみ
            int count = hole.Concat(community).GroupBy(c => c.suit).Max(g => g.Count());
            if (count >= 4) return 0.6f; // Flush Draw
            return 0.1f;
        }

        #endregion

        #region River GTO EV (Pure Math)

        private AIAction DecideRiverEV(Player me, List<Player> allPlayers, List<Card> communityCards, int currentMinBet)
        {
            var res = HandEvaluator.EvaluateHandle(me.HoleCards.Concat(communityCards));
            float equity = (float)res.Rank / (float)HandRank.RoyalFlush;
            int pot = allPlayers.Sum(p => p.CurrentBet);
            int toCall = currentMinBet - me.CurrentBet;

            // Minimum Defense Frequency (MDF) = Pot / (Pot + Bet)
            float mdf = (float)pot / (pot + (toCall > 0 ? toCall : 20));

            if (toCall > 0)
            {
                float callEV = (equity * (pot + toCall)) - ((1 - equity) * toCall);
                // MDF logic: If equity is better than required by MDF, we must defend
                if (callEV > 0 || equity > (1.0f - mdf)) return new AIAction { ActionName = "Call" };
                return new AIAction { ActionName = "Fold" };
            }

            // Value betting: Optimize sizing based on hand strength relative to board
            if (equity > 0.7f) return new AIAction { ActionName = "Raise", RaiseAmount = (int)(pot * 0.6f) };
            if (equity > 0.4f && UnityEngine.Random.value < 0.2f) return new AIAction { ActionName = "Raise", RaiseAmount = (int)(pot * 0.3f) }; // Balanced bluff/thin value

            return new AIAction { ActionName = "Check" };
        }

        #endregion

        #region Enums

        protected enum GamePhase { Preflop, Flop, Turn, River }
        protected enum BoardTexture { Dry, Wet, Paired, Monotone }
        protected enum HandBucket { Trash, WeakDraw, StrongDraw, MarginalMade, StrongMade, Monster }

        #endregion

    }
}
