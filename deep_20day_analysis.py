import MetaTrader5 as mt5
import json
import os
import csv
from datetime import datetime, timedelta
import pandas as pd

BASE_DIR = r"c:\anlyzeforex\forextele"
CONFIG_PATH = os.path.join(BASE_DIR, "mt5_config.json")
AUDIT_CSV = os.path.join(BASE_DIR, "signals_audit.csv")

def connect():
    if not mt5.initialize():
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH) as f: cfg = json.load(f)
            mt5.initialize(login=cfg.get('login'), server=cfg.get('server'), password=cfg.get('password'))
    return mt5.terminal_info() is not None

def deep_analysis():
    if not connect():
        print("[ERROR] MT5 connection failed")
        return

    acc = mt5.account_info()
    print("=" * 80)
    print("  DEEP 20-DAY TRADING PERFORMANCE ANALYSIS  (July 10 - July 31, 2026)")
    print("=" * 80)
    print(f"\n LIVE ACCOUNT: {acc.login} | Server: {acc.server}")
    print(f" Current Balance : ${acc.balance:,.2f} USD")
    print(f" Current Equity  : ${acc.equity:,.2f} USD")
    print(f" Floating P&L    : ${acc.profit:,.2f} USD")
    print(f" Free Margin     : ${acc.margin_free:,.2f} USD")

    # Pull ALL history since July 10
    now = datetime.now()
    from_date = datetime(2026, 7, 10)
    deals = mt5.history_deals_get(from_date, now)

    if not deals:
        print("\n[WARN] No deal history found!")
        return

    all_deals = []
    for d in deals:
        if d.entry == mt5.DEAL_ENTRY_OUT:
            comment = d.comment or ""
            magic = d.magic
            pnl = d.profit + d.swap + d.commission
            is_tele = magic == 777777 or "Tele:" in comment
            is_strategy = (magic == 888888) or ("AI:" in comment)
            deal_date = datetime.fromtimestamp(d.time)
            all_deals.append({
                'ticket': d.ticket,
                'symbol': d.symbol,
                'type': 'BUY' if d.type == mt5.DEAL_TYPE_BUY else 'SELL',
                'volume': d.volume,
                'price': d.price,
                'profit': pnl,
                'comment': comment,
                'magic': magic,
                'time': deal_date,
                'date': deal_date.strftime('%Y-%m-%d'),
                'is_tele': is_tele,
                'is_strategy': is_strategy
            })

    df = pd.DataFrame(all_deals)

    # ---- SECTION 1: OVERALL SUMMARY ----
    print(f"\n{'='*80}")
    print("  SECTION 1: OVERALL 20-DAY SUMMARY")
    print(f"{'='*80}")
    total_trades = len(df)
    total_pnl = df['profit'].sum()
    wins = len(df[df['profit'] > 0])
    losses = len(df[df['profit'] < 0])
    win_rate = wins/total_trades*100 if total_trades > 0 else 0

    print(f"\n  Total Closed Trades   : {total_trades}")
    print(f"  Total Net P&L         : ${total_pnl:,.2f} USD")
    print(f"  Win Rate              : {win_rate:.1f}% ({wins} Wins / {losses} Losses)")
    print(f"  Starting Capital      : ~$1,500.00 USD (after drawdown from $10k)")
    print(f"  Net Return This Period: {(total_pnl/1500)*100:.1f}%")

    # ---- SECTION 2: BOT STRATEGIES vs TELEGRAM ----
    print(f"\n{'='*80}")
    print("  SECTION 2: STRATEGY BOT vs TELEGRAM CHANNEL BREAKDOWN")
    print(f"{'='*80}")

    strat_df = df[df['is_strategy']]
    tele_df = df[df['is_tele']]
    other_df = df[~df['is_strategy'] & ~df['is_tele']]

    for label, sub_df in [("41 AI Automated Strategies", strat_df), ("Telegram VIP Channels", tele_df), ("Manual / Other", other_df)]:
        if len(sub_df) == 0: continue
        s_wins = len(sub_df[sub_df['profit'] > 0])
        s_losses = len(sub_df[sub_df['profit'] < 0])
        s_pnl = sub_df['profit'].sum()
        s_wr = s_wins/len(sub_df)*100 if len(sub_df) > 0 else 0
        print(f"\n  [{label}]")
        print(f"    Trades: {len(sub_df)} | Wins: {s_wins} | Losses: {s_losses} | Win Rate: {s_wr:.1f}%")
        print(f"    Net P&L: ${s_pnl:,.2f} USD")

    # ---- SECTION 3: TELEGRAM CHANNEL DETAILS ----
    print(f"\n{'='*80}")
    print("  SECTION 3: TELEGRAM VIP CHANNEL PERFORMANCE (Per Channel)")
    print(f"{'='*80}")

    if len(tele_df) > 0:
        # Parse channel name from comment
        def parse_channel(comment):
            if "Tele:" in comment:
                return comment.split("Tele:")[1].strip().split(" 777777")[0].strip()[:20]
            return "Unknown"

        tele_df = tele_df.copy()
        tele_df['channel'] = tele_df['comment'].apply(parse_channel)
        ch_stats = tele_df.groupby('channel').agg(
            trades=('profit','count'),
            wins=('profit', lambda x: (x>0).sum()),
            losses=('profit', lambda x: (x<0).sum()),
            pnl=('profit','sum')
        ).sort_values('pnl', ascending=False)

        print(f"\n  {'Channel':<22} {'Trades':>7} {'Wins':>5} {'Losses':>7} {'Net P&L':>12}  Status")
        print(f"  {'-'*70}")
        for ch, row in ch_stats.iterrows():
            status = "PROFITABLE" if row['pnl'] > 0 else "LOSING"
            wr = row['wins']/row['trades']*100 if row['trades'] > 0 else 0
            print(f"  {ch:<22} {int(row['trades']):>7} {int(row['wins']):>5} {int(row['losses']):>7} ${row['pnl']:>10.2f}  {status} ({wr:.0f}%WR)")
    else:
        print("  No Telegram trades with clear channel attribution found in history.")

    # ---- SECTION 4: SYMBOL PERFORMANCE ----
    print(f"\n{'='*80}")
    print("  SECTION 4: PERFORMANCE PER TRADING PAIR (Best to Worst)")
    print(f"{'='*80}")

    sym_stats = df.groupby('symbol').agg(
        trades=('profit','count'),
        wins=('profit', lambda x: (x>0).sum()),
        pnl=('profit','sum')
    ).sort_values('pnl', ascending=False)

    print(f"\n  {'Symbol':<10} {'Trades':>7} {'Win Rate':>10} {'Net P&L':>12}")
    print(f"  {'-'*45}")
    for sym, row in sym_stats.iterrows():
        wr = row['wins']/row['trades']*100 if row['trades'] > 0 else 0
        print(f"  {sym:<10} {int(row['trades']):>7} {wr:>9.1f}% ${row['pnl']:>10.2f}")

    # ---- SECTION 5: WEEK-BY-WEEK PERFORMANCE ----
    print(f"\n{'='*80}")
    print("  SECTION 5: WEEK-BY-WEEK BREAKDOWN")
    print(f"{'='*80}")

    df['week'] = df['time'].dt.isocalendar().week
    weekly = df.groupby('week').agg(
        trades=('profit','count'),
        wins=('profit', lambda x: (x>0).sum()),
        pnl=('profit','sum')
    )

    for wk, row in weekly.iterrows():
        wr = row['wins']/row['trades']*100 if row['trades'] > 0 else 0
        print(f"\n  Week {wk}: {int(row['trades'])} trades | WR: {wr:.1f}% | P&L: ${row['pnl']:,.2f}")

    # ---- SECTION 6: AUDIT CSV CHANNEL ANALYSIS ----
    print(f"\n{'='*80}")
    print("  SECTION 6: TELEGRAM SIGNALS RECEIVED & PROCESSED (Audit Log)")
    print(f"{'='*80}")

    if os.path.exists(AUDIT_CSV):
        try:
            aud = pd.read_csv(AUDIT_CSV)
            if 'Status' in aud.columns and 'Channel' in aud.columns:
                print(f"\n  Total Signals Intercepted: {len(aud)}")
                status_cnt = aud['Status'].value_counts()
                for s, c in status_cnt.items():
                    print(f"    {s:<15}: {c} signals ({c/len(aud)*100:.1f}%)")

                print(f"\n  Top 10 Most Active Channels (by Signal Volume):")
                ch_cnt = aud['Channel'].value_counts().head(10)
                for ch, c in ch_cnt.items():
                    print(f"    {str(ch)[:35]:<35}: {c} signals")
        except Exception as e:
            print(f"  [ERROR] Reading audit CSV: {e}")

    # ---- SECTION 7: OPEN POSITIONS ----
    print(f"\n{'='*80}")
    print("  SECTION 7: CURRENTLY OPEN POSITIONS (Floating)")
    print(f"{'='*80}")
    positions = mt5.positions_get()
    if positions:
        total_floating = sum(p.profit + p.swap for p in positions)
        print(f"\n  {'Symbol':<8} {'Type':<5} {'Lot':<6} {'Open':<12} {'Current':<12} {'P&L':>10}  Source")
        print(f"  {'-'*70}")
        for p in positions:
            ptype = "BUY" if p.type == mt5.POSITION_TYPE_BUY else "SELL"
            src = "TELE" if p.magic == 777777 else ("BOT" if p.magic == 888888 else "MANUAL")
            print(f"  {p.symbol:<8} {ptype:<5} {p.volume:<6} {p.price_open:<12.4f} {p.price_current:<12.4f} ${p.profit:>8.2f}  {src}")
        print(f"\n  Total Floating P&L: ${total_floating:,.2f}")

    print(f"\n{'='*80}")
    print("  ANALYSIS COMPLETE")
    print(f"{'='*80}\n")

if __name__ == "__main__":
    deep_analysis()
