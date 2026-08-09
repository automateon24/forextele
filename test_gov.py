import asyncio
from swarm_engine import OllamaSwarmEngine
async def test():
    e = OllamaSwarmEngine()
    json_payload = '{"symbol": "XAUUSD", "action": "SELL", "entry": 4026.5, "sl": 4036.5, "tp1": 4006.5, "tp2": null, "tp3": null}'
    resp = await e._ask_ollama(e.prompts['GOVERNOR_PROMPT'], json_payload)
    print('GOVERNOR OUTPUT:')
    print(resp)
asyncio.run(test())
