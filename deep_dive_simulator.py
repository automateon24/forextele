import asyncio
import json
from swarm_engine import OllamaSwarmEngine

class MockEngine(OllamaSwarmEngine):
    def __init__(self):
        super().__init__()
        class MockMT5:
            def execute_trade(self, payload):
                return True
            def get_available_symbols(self):
                return ['GOLD', 'EURUSD', 'BTCUSD', 'ETHUSD', 'LINKUSDT', 'BCHUSDT', 'WLDUSDT', 'AEROUSDT', 'ICPUSDT']
        self.mt5_engine = MockMT5()

async def main():
    with open("raw_signals_today.txt", "r", encoding="utf-8") as f:
        content = f.read()
        
    blocks = content.split("--- Channel: ")
    
    md = "# Deep Dive: Swarm Pipeline Analysis\n\n"
    md += "| Channel | Signal Snippet | Watcher | Trigger | Governor | Reason/Status |\n"
    md += "|---------|----------------|---------|---------|----------|---------------|\n"
    
    engine = MockEngine()
    print("Simulating Swarm Engine on raw signals...")
    
    for block in blocks[1:]:
        lines = block.strip().split("\n")
        channel = lines[0].strip(" -")
        msg = "\n".join(lines[1:]).strip()
        if not msg: continue
        
        snippet = msg.replace("\n", " ")[:30] + "..."
        
        try:
            result = await engine.process_telegram_signal(msg)
            
            status = result.get("status", "UNKNOWN")
            reason = result.get("reason", "N/A")
            
            watcher_status = "JUNK" if status == "REJECTED" and "JUNK" in reason else "PASSED"
            if status == "UPDATE_REQUIRED": watcher_status = "UPDATE"
            
            trigger_status = "FAILED" if "hallucinated" in reason else "PASSED"
            if watcher_status != "PASSED": trigger_status = "SKIPPED"
            
            gov_status = "VETOED" if status == "REJECTED" and "JUNK" not in reason else "APPROVED"
            if trigger_status != "PASSED": gov_status = "SKIPPED"
            if status == "UNKNOWN": gov_status = "UNKNOWN"
            
            if status == "APPROVED":
                reason = f"Trade Valid! Action: {result.get('action')} Symbol: {result.get('symbol')} SL: {result.get('final_sl')} R:R: {result.get('risk_reward_ratio')}"
                
            md += f"| {channel} | `{snippet}` | {watcher_status} | {trigger_status} | {gov_status} | {reason} |\n"
        except Exception as e:
            print(f"Failed to process {channel}: {e}")
        
    with open("deep_dive_report.md", "w", encoding="utf-8") as f:
        f.write(md)
        
    print("Report generated: deep_dive_report.md")

if __name__ == "__main__":
    asyncio.run(main())
