import pytest
from pydantic import ValidationError
from src.common.messages import SignalMessage, MessageHeader

def test_signal_message_validation():
    # Valid
    sig = SignalMessage(
        header=MessageHeader(message_type="Signal", source_component="test"),
        symbol="USDCHF",
        side="BUY",
        strategy_id="TEST",
        suggested_entry_price=1.1,
        suggested_sl_price=1.09,
        suggested_tp_price=1.12
    )
    assert sig.symbol == "USDCHF"
    
    # Invalid side
    with pytest.raises(ValidationError):
        SignalMessage(
            header=MessageHeader(message_type="Signal", source_component="test"),
            symbol="USDCHF",
            side="INVALID",
            strategy_id="TEST",
            suggested_entry_price=1.1,
            suggested_sl_price=1.09,
            suggested_tp_price=1.12
        )
