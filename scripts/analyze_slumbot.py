
import pandas as pd
import sys

def analyze(log_file="slumbot_log.csv"):
    try:
        df = pd.read_csv(log_file)
    except Exception as e:
        print(f"Error reading {log_file}: {e}")
        return

    total_hands = len(df)
    if total_hands == 0:
        print("No hands found in log.")
        return

    won_hands = len(df[df['winnings'] > 0])
    lost_hands = len(df[df['winnings'] < 0])
    tied_hands = len(df[df['winnings'] == 0])

    win_rate = (won_hands / total_hands) * 100
    total_winnings = df['winnings'].sum()
    bb_100 = (total_winnings / 100.0) / (total_hands / 100.0)
    
    worst_loss = df['winnings'].min()
    best_win = df['winnings'].max()

    print(f"--- Slumbot Analysis Results ({total_hands} hands) ---")
    print(f"Total Winnings: {total_winnings} chips ({total_winnings/100.0:.2f} bb)")
    print(f"bb/100: {bb_100:.2f}")
    print(f"Win Rate: {win_rate:.2f}% ({won_hands} wins, {lost_hands} losses, {tied_hands} ties)")
    print(f"Worst Loss (Single Hand): {worst_loss} chips ({worst_loss/100.0:.1f} bb)")
    print(f"Best Win (Single Hand): {best_win} chips ({best_win/100.0:.1f} bb)")

if __name__ == "__main__":
    file = sys.argv[1] if len(sys.argv) > 1 else "slumbot_log.csv"
    analyze(file)
