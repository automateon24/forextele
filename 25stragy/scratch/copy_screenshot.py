import shutil
import os

src = r"C:\Users\Administrator\.gemini\antigravity\brain\c33d4c5e-29d9-47da-85ed-eedc8c379cc2\self_tuning_panel_1782414268825.png"
dst = r"C:\Users\Administrator\.gemini\antigravity\brain\c33d4c5e-29d9-47da-85ed-eedc8c379cc2\artifacts\self_tuning_panel.png"

shutil.copy(src, dst)
print("Copied successfully to artifacts/self_tuning_panel.png")
