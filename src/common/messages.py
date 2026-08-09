import uuid
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, Literal

class MessageHeader(BaseModel):
    schema_version: str = "1.0"
    message_type: str
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp_utc: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    source_component: str
    source_version: str = "1.0.0"

class SignalMessage(BaseModel):
    header: MessageHeader
    symbol: str
    side: Literal["BUY", "SELL"]
    strategy_id: str
    strategy_version: str = "1.0.0"
    signal_strength: float = 1.0
    entry_type: Literal["MARKET", "LIMIT", "STOP"] = "MARKET"
    suggested_entry_price: float
    suggested_sl_price: float
    suggested_tp_price: float
    time_in_force: Literal["GTC", "IOC", "DAY"] = "GTC"
    metadata: dict = {}

class RiskDecisionMessage(BaseModel):
    header: MessageHeader
    original_correlation_id: str
    decision: Literal["ALLOW", "BLOCK", "ALLOW_REDUCED"]
    reason_code: str
    approved_volume: float = 0.0
    approved_sl_price: float = 0.0
    approved_tp_price: float = 0.0
    risk_snapshot: dict = {}

class OrderRequestMessage(BaseModel):
    header: MessageHeader
    symbol: str
    side: Literal["BUY", "SELL"]
    order_type: Literal["MARKET", "LIMIT", "STOP"] = "MARKET"
    volume: float
    sl: float
    tp: float
    magic: int = 888888
    comment: str
    risk_decision_id: str

class FillReportMessage(BaseModel):
    header: MessageHeader
    broker_order_id: str
    broker_deal_id: str
    symbol: str
    side: Literal["BUY", "SELL"]
    volume: float
    fill_price: float
    sl: float
    tp: float
    commission: float = 0.0
    swap: float = 0.0
    status: Literal["FILLED", "PARTIAL", "REJECTED", "CANCELLED"]
    reject_reason: Optional[str] = None
    latency_ms: int = 0

class OpenPosition(BaseModel):
    symbol: str
    side: Literal["BUY", "SELL"]
    volume: float
    entry_price: float
    current_price: float
    sl: float
    unrealised_pnl: float
    risk_amount: float

class PortfolioSnapshotMessage(BaseModel):
    header: MessageHeader
    equity: float
    balance: float
    margin_used: float
    margin_free: float
    open_positions: list[OpenPosition]
    daily_realised_pnl: float
    daily_unrealised_pnl: float
    high_water_mark_equity: float
