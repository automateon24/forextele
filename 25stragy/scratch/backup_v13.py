import os
import shutil

def main():
    dest = "C:\\25stragy\\backups\\backup_v13_post_opt"
    os.makedirs(dest, exist_ok=True)
    
    shutil.copy("C:\\25stragy\\BACKTEST_V8_AI.py", os.path.join(dest, "BACKTEST_V8_AI.py"))
    shutil.copy("C:\\25stragy\\config.json", os.path.join(dest, "config.json"))
    shutil.copy("C:\\25stragy\\strategy_dna.json", os.path.join(dest, "strategy_dna.json"))
    print("V13 current optimized files successfully backed up to backups/backup_v13_post_opt.")

if __name__ == "__main__":
    main()
