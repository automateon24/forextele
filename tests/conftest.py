import pytest
from src.common.messages import SignalMessage, PortfolioSnapshotMessage, MessageHeader, OpenPosition

@pytest.fixture
def base_header():
    return MessageHeader(message_type="Test", source_component="test")

@pytest.fixture
def mock_signal(base_header):
    return SignalMessage(
        header=base_header,
        symbol="USDCHF",
        side="BUY",
        strategy_id="TEST_STRAT",
        suggested_entry_price=1.1,
        suggested_sl_price=1.09,
        suggested_tp_price=1.12,
        metadata={"suggested_volume": 0.01}
    )

@pytest.fixture
def mock_portfolio(base_header):
    return PortfolioSnapshotMessage(
        header=base_header,
        equity=1500.0,
        balance=1500.0,
        margin_used=100.0,
        margin_free=1400.0,
        open_positions=[],
        daily_realised_pnl=0.0,
        daily_unrealised_pnl=0.0,
        high_water_mark_equity=1500.0
    )
