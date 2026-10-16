"""
Read-only analysis script to inspect C:\\SepPro trading results, PnL, and performance.
DO NOT MODIFY ANYTHING IN C:\\SepPro.
"""
import os
import sys
import pandas as pd
import numpy as np

SEPPRO_DIR = r"C:\SepPro"

def analyze_trades():
    print("=" * 70)
    print("  DEEP DIVE PnL & PERFORMANCE AUDIT: C:\\SepPro")
    print("=" * 70)

    # 1. Inspect live_portfolio_paper_trades.csv (engine_v15 & GapAI)
    pt_csv = os.path.join(SEPPRO_DIR, "live_portfolio_paper_trades.csv")
    if os.path.exists(pt_csv):
        try:
            df_us = pd.read_csv(pt_csv)
            print(f"\n[1] US ENGINE (engine_v15 & Gap-AI) Trades: {len(df_us)} rows")
            print("Columns:", list(df_us.columns))
            if 'pnl_rs' in df_us.columns:
                df_us['pnl_clean'] = pd.to_numeric(df_us['pnl_rs'], errors='coerce').fillna(0)
                closed = df_us[df_us['status'].str.contains('CLOSED|EXIT|HIT|SL|TP', case=False, na=False)]
                open_pos = df_us[df_us['status'].str.contains('OPEN', case=False, na=False)]
                tot_pnl = df_us['pnl_clean'].sum()
                wins = df_us[df_us['pnl_clean'] > 0]
                losses = df_us[df_us['pnl_clean'] < 0]
                wr = (len(wins) / len(closed) * 100) if len(closed) > 0 else 0
                print(f"Total Rows: {len(df_us)} | Closed: {len(closed)} | Open: {len(open_pos)}")
                print(f"Closed Wins: {len(wins)} | Closed Losses: {len(losses)} | Win Rate: {wr:.1f}%")
                print(f"Net Realized PnL: Rs. {tot_pnl:,.2f}")
                
                # By strategy
                if 'strategy' in df_us.columns:
                    print("\nTop 10 Strategies by PnL:")
                    strat_grp = df_us.groupby('strategy')['pnl_clean'].agg(['count', 'sum']).sort_values('sum', ascending=False)
                    print(strat_grp.head(10))
        except Exception as e:
            print(f"Error reading {pt_csv}: {e}")

    # 2. Inspect option_writer_paper_trades.csv
    ow_csv = os.path.join(SEPPRO_DIR, "option_writer_paper_trades.csv")
    if os.path.exists(ow_csv):
        try:
            df_ow = pd.read_csv(ow_csv)
            print(f"\n[2] OPTION WRITER Trades: {len(df_ow)} rows")
            print("Columns:", list(df_ow.columns))
            if 'net_pnl' in df_ow.columns or 'pnl_rs' in df_ow.columns:
                p_col = 'net_pnl' if 'net_pnl' in df_ow.columns else 'pnl_rs'
                df_ow['pnl_clean'] = pd.to_numeric(df_ow[p_col], errors='coerce').fillna(0)
                tot_pnl_ow = df_ow['pnl_clean'].sum()
                print(f"Total OW Trades: {len(df_ow)} | Total Net PnL: Rs. {tot_pnl_ow:,.2f}")
        except Exception as e:
            print(f"Error reading {ow_csv}: {e}")

    # 3. Inspect telegram_signals.xlsx
    tg_xlsx = os.path.join(SEPPRO_DIR, "telegram_signals.xlsx")
    if os.path.exists(tg_xlsx):
        try:
            df_tg = pd.read_excel(tg_xlsx)
            print(f"\n[3] TELEGRAM SIGNALS Trades: {len(df_tg)} rows")
            print("Columns:", list(df_tg.columns[:15]))
            p_col = 'net_pnl' if 'net_pnl' in df_tg.columns else ('pnl_rs' if 'pnl_rs' in df_tg.columns else 'pnl')
            if p_col in df_tg.columns:
                df_tg['pnl_clean'] = pd.to_numeric(df_tg[p_col], errors='coerce').fillna(0)
                tot_tg = df_tg['pnl_clean'].sum()
                wins_tg = df_tg[df_tg['pnl_clean'] > 0]
                losses_tg = df_tg[df_tg['pnl_clean'] < 0]
                wr_tg = (len(wins_tg) / len(df_tg) * 100) if len(df_tg) > 0 else 0
                print(f"Total Telegram Trades: {len(df_tg)} | Wins: {len(wins_tg)} | Losses: {len(losses_tg)} | Win Rate: {wr_tg:.1f}%")
                print(f"Total Net PnL: Rs. {tot_tg:,.2f}")
                if 'channel' in df_tg.columns:
                    print("\nTop Channels by PnL:")
                    chan_grp = df_tg.groupby('channel')['pnl_clean'].agg(['count', 'sum']).sort_values('sum', ascending=False)
                    print(chan_grp.head(10))
        except Exception as e:
            print(f"Error reading {tg_xlsx}: {e}")

if __name__ == "__main__":
    analyze_trades()
