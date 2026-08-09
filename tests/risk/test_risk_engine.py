import pytest
import datetime
from src.risk.engine import RiskEvaluator

# Mock config for tests
TEST_CONFIG = {
    "max_risk_per_trade_pct": 0.006,
    "max_portfolio_heat_pct": 0.03,
    "max_daily_loss_pct": 0.02,
    "max_drawdown_pct": 0.06,
    "max_open_positions": 2,
    "max_positions_per_symbol": 1,
    "margin_buffer_mult": 1.5,
    "data_staleness_ms": 10000,
    "hard_lot_cap": 0.05
}

@pytest.fixture
def evaluator():
    ev = RiskEvaluator()
    ev.config = dict(TEST_CONFIG)
    ev.kill_switch = {"global": False, "symbols": {}}
    return ev

def test_re01_global_kill_switch(evaluator, mock_signal, mock_portfolio):
    evaluator.portfolio = mock_portfolio
    # Mocking load_config to preserve test config
    evaluator.load_config = lambda: None 
    
    evaluator.kill_switch["global"] = True
    decision = evaluator.evaluate(mock_signal)
    assert decision.decision == "BLOCK"
    assert decision.reason_code == "KILL_SWITCH_ACTIVE"

def test_re02_symbol_kill_switch(evaluator, mock_signal, mock_portfolio):
    evaluator.portfolio = mock_portfolio
    evaluator.load_config = lambda: None
    
    evaluator.kill_switch["symbols"]["USDCHF"] = True
    decision = evaluator.evaluate(mock_signal)
    assert decision.decision == "BLOCK"
    assert decision.reason_code == "KILL_SWITCH_ACTIVE_SYMBOL"

def test_re03_stale_portfolio(evaluator, mock_signal, mock_portfolio):
    evaluator.load_config = lambda: None
    
    # Portfolio is None
    evaluator.portfolio = None
    decision = evaluator.evaluate(mock_signal)
    assert decision.decision == "BLOCK"
    assert decision.reason_code == "DATA_STALE"
    
    # Portfolio is very old
    old_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=20)
    mock_portfolio.header.timestamp_utc = old_time.isoformat()
    evaluator.portfolio = mock_portfolio
    
    decision2 = evaluator.evaluate(mock_signal)
    assert decision2.decision == "BLOCK"
    assert decision2.reason_code == "DATA_STALE"

def test_re10_11_12_max_positions(evaluator, mock_signal, mock_portfolio):
    evaluator.load_config = lambda: None
    evaluator.portfolio = mock_portfolio
    
    # One position of USDCHF, max per symbol is 1. Should block new USDCHF
    from src.common.messages import OpenPosition
    mock_portfolio.open_positions.append(
        OpenPosition(symbol="USDCHF", side="BUY", volume=0.01, entry_price=1.1, current_price=1.1, sl=1.09, unrealised_pnl=0.0, risk_amount=10.0)
    )
    decision = evaluator.evaluate(mock_signal)
    assert decision.decision == "BLOCK"
    assert decision.reason_code == "MAX_SYMBOL_POSITIONS"
    
    # Two positions total, max is 2. Should block anything new
    mock_portfolio.open_positions.pop() # clear
    mock_portfolio.open_positions.append(
        OpenPosition(symbol="EURUSD", side="BUY", volume=0.01, entry_price=1.1, current_price=1.1, sl=1.09, unrealised_pnl=0.0, risk_amount=10.0)
    )
    mock_portfolio.open_positions.append(
        OpenPosition(symbol="GBPUSD", side="BUY", volume=0.01, entry_price=1.1, current_price=1.1, sl=1.09, unrealised_pnl=0.0, risk_amount=10.0)
    )
    decision2 = evaluator.evaluate(mock_signal)
    assert decision2.decision == "BLOCK"
    assert decision2.reason_code == "MAX_OPEN_POSITIONS"

def test_re13_daily_loss(evaluator, mock_signal, mock_portfolio):
    evaluator.load_config = lambda: None
    evaluator.portfolio = mock_portfolio
    
    # HWM = 1500, Daily Loss limit = 2% (30.0)
    mock_portfolio.high_water_mark_equity = 1500.0
    mock_portfolio.daily_realised_pnl = -20.0
    mock_portfolio.daily_unrealised_pnl = -11.0 # Total -31.0
    
    decision = evaluator.evaluate(mock_signal)
    assert decision.decision == "BLOCK"
    assert decision.reason_code == "DAILY_LOSS_LIMIT"

def test_re16_happy_path(evaluator, mock_signal, mock_portfolio):
    evaluator.load_config = lambda: None
    evaluator.portfolio = mock_portfolio
    
    # Set fresh timestamp
    mock_portfolio.header.timestamp_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    decision = evaluator.evaluate(mock_signal)
    assert decision.decision == "ALLOW"
    assert decision.approved_volume == 0.01 # Respects the default from the signal metadata

def test_hard_lot_cap(evaluator, mock_signal, mock_portfolio):
    evaluator.load_config = lambda: None
    evaluator.portfolio = mock_portfolio
    mock_portfolio.header.timestamp_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    # Request huge volume
    mock_signal.metadata["suggested_volume"] = 1.0
    decision = evaluator.evaluate(mock_signal)
    
    # Should cap at 0.05
    assert decision.decision == "ALLOW"
    assert decision.approved_volume == 0.05

def test_margin_buffer(evaluator, mock_signal, mock_portfolio):
    evaluator.load_config = lambda: None
    evaluator.portfolio = mock_portfolio
    mock_portfolio.header.timestamp_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    # Make margin used = 1000, free = 1000 (ratio 1.0, needs 1.5)
    mock_portfolio.margin_used = 1000.0
    mock_portfolio.margin_free = 1000.0
    
    decision = evaluator.evaluate(mock_signal)
    assert decision.decision == "BLOCK"
    assert decision.reason_code == "INSUFFICIENT_MARGIN"
