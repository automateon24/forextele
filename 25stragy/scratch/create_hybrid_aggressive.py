import os

src_path = r"C:\25stragy\BACKTEST_V15_AGGRESSIVE_100K.py"
dest_path = r"C:\25stragy\BACKTEST_V15_HYBRID_AGGRESSIVE.py"

if not os.path.exists(src_path):
    print(f"Source file {src_path} not found!")
    exit(1)

content = open(src_path, encoding='utf-8').read()

# 1. Update config file path
rep1_target = 'CONFIG_PATH = r"C:\\25stragy\\config_aggressive_100k.json"'
rep1_replacement = 'CONFIG_PATH = r"C:\\25stragy\\config_hybrid_aggressive.json"'
if rep1_target not in content:
    rep1_target = 'CONFIG_PATH = "config_aggressive_100k.json"'
    rep1_replacement = 'CONFIG_PATH = "config_hybrid_aggressive.json"'

content = content.replace(rep1_target, rep1_replacement)

# 2. Update build_dna_matrix index list
rep2_target = "for idx in ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'SENSEX']:"
rep2_replacement = "for idx in INDEX_CONFIGS.keys():"
content = content.replace(rep2_target, rep2_replacement)

# 3. Update gap, pcr_up, rsi_adj, rc_adj dictionaries for MIDCPNIFTY
rep3_target = """    gap = {'BANKNIFTY': 3.0, 'FINNIFTY': 3.0, 'SENSEX': 3.0}[idx]
    pcr_up = {'BANKNIFTY': 6.0, 'FINNIFTY': 20.0, 'SENSEX': 40.0}[idx]
    rsi_adj = {'BANKNIFTY': 3, 'FINNIFTY': 2, 'SENSEX': 3}[idx]
    rc_adj = {'BANKNIFTY': 0.0, 'FINNIFTY': 0.0, 'SENSEX': 0.0}[idx]"""

rep3_replacement = """    gap = {'BANKNIFTY': 3.0, 'FINNIFTY': 3.0, 'MIDCPNIFTY': 4.0, 'SENSEX': 3.0}[idx]
    pcr_up = {'BANKNIFTY': 6.0, 'FINNIFTY': 20.0, 'MIDCPNIFTY': 10.0, 'SENSEX': 40.0}[idx]
    rsi_adj = {'BANKNIFTY': 3, 'FINNIFTY': 2, 'MIDCPNIFTY': 3, 'SENSEX': 3}[idx]
    rc_adj = {'BANKNIFTY': 0.0, 'FINNIFTY': 0.0, 'MIDCPNIFTY': -0.05, 'SENSEX': 0.0}[idx]"""
content = content.replace(rep3_target, rep3_replacement)

# 4. Update sl_backstop check in execute_idx and execute_tsl_idx (two places)
rep4_target = """    if index_name == 'SENSEX':
        sl_backstop = min(sl_backstop, 0.20)
    elif index_name == 'BANKNIFTY':
        sl_backstop = min(sl_backstop, 0.25)
    elif index_name in ['NIFTY', 'FINNIFTY']:
        sl_backstop = min(sl_backstop, 0.25)"""

rep4_replacement = """    if index_name == 'SENSEX':
        sl_backstop = min(sl_backstop, 0.20)
    else:
        sl_backstop = min(sl_backstop, 0.25)"""
content = content.replace(rep4_target, rep4_replacement)

# 5. Update index loop in report_multi
rep5_target = "for idx_name in ['NIFTY','BANKNIFTY','FINNIFTY','SENSEX']:"
rep5_replacement = "for idx_name in sorted(results.keys()):"
content = content.replace(rep5_target, rep5_replacement)

# 6. Update calendar days print in report_multi
rep6_target = 'print(f"  4 indices × 36 strategies × Dynamic lot sizing")'
rep6_replacement = 'print(f"  {len(results)} indices × 36 strategies × Dynamic lot sizing")'
content = content.replace(rep6_target, rep6_replacement)

# Write to the destination path
with open(dest_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("BACKTEST_V15_HYBRID_AGGRESSIVE.py created successfully!")
