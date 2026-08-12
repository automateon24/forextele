"""
Ollama Local AI Client
======================
Connects to local Ollama API (http://127.0.0.1:11434) for offline failure reviews,
clustering loss patterns, and feature ideation.

CRITICAL POLICY ENFORCEMENT:
Ollama is strictly prohibited from executing or blocking live orders directly.
"""

import json
import logging
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class OllamaClient:
    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            config_path = Path(__file__).resolve().parent.parent.parent / "config" / "ml_config.json"

        self.config = {}
        if Path(config_path).exists():
            with open(config_path, "r") as f:
                self.config = json.load(f)

        ollama_cfg = self.config.get("ollama", {})
        self.base_url                = ollama_cfg.get("base_url", "http://127.0.0.1:11434")
        self.model                   = ollama_cfg.get("model", "llama3.2:3b")
        self.enabled_for_reviews    = ollama_cfg.get("enabled_for_reviews", True)
        self.enabled_for_live_orders = False  # Hardcoded safety constraint

    def is_server_online(self) -> bool:
        try:
            url = f"{self.base_url}/api/tags"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status == 200
        except Exception:
            return False

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> Optional[str]:
        """
        Sends prompt to local Ollama API. Returns response string.
        """
        if not self.enabled_for_reviews:
            logger.warning("Ollama reviews are disabled in config.")
            return None

        if not self.is_server_online():
            logger.warning(f"Ollama server at {self.base_url} is offline.")
            return None

        url = f"{self.base_url}/api/chat"
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }

        try:
            data_bytes = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data_bytes, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return result.get("message", {}).get("content", "")
        except Exception as e:
            logger.error(f"Ollama API request failed: {e}")
            return None
