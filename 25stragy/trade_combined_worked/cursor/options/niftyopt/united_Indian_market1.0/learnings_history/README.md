# NIFTY Options Trading Framework

A comprehensive, probabilistic NIFTY options trading system integrating historical analysis, real-time flow, ML/AI predictions, and risk management.

## System Architecture

The system consists of 8 integrated modules:

1. **Module 1: Data & Event Layer** - Data ingestion, storage, and preprocessing
2. **Module 2: Historical Probability Engine** - 10-year seasonal/behavioral analysis
3. **Module 3: Live Flow Engine** - Real-time options flow, PCR, OI, skew analysis
4. **Module 4: Strike & Structure Engine** - Optimal strike selection and strategy construction
5. **Module 5: Risk & Portfolio Engine** - Position sizing, limits, drawdown management
6. **Module 6: ML/AI Prediction Engine** - Machine learning from backtest + live data
7. **Module 7: Fusion & Decision Engine** - Combines all probability sources
8. **Module 8: Feedback & Calibration Engine** - Continuous learning and optimization

## Key Features

- **Multi-Horizon Trading**: Intraday, positional (2-5 days), and swing (5-20 days)
- **Probabilistic Framework**: All engines output probabilities, not binary signals
- **Regime Awareness**: Adapts to volatility, trend, time-of-day, and event regimes
- **ML Integration**: ML sits alongside rules-based engines, not replacing them
- **Continuous Learning**: Feedback loop ensures probabilities stay calibrated

## Installation

**Important**: All operations must be performed from `C:\options\niftyopt` directory.

1. Navigate to project directory:
```bash
cd C:\options\niftyopt
```

2. Create a virtual environment:
```bash
python -m venv venv
venv\Scripts\activate  # On Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Verify project root setup:
```bash
python verify_project_root.py
```

5. Set up Dhan credentials:
   - Create `.env` file (see `env_template.txt`)
   - Or set environment variables:
     ```bash
     set DHAN_CLIENT_ID=your_client_id
     set DHAN_ACCESS_TOKEN=your_access_token
     ```

6. Test Dhan connection:
```bash
python scripts/test_dhan_connection.py
```

5. Set up configuration:
- Configuration files are in `config/` directory
- Update `config/system_config.yaml` with database credentials if needed
- Set environment variables for sensitive data

6. Set up database:
- PostgreSQL (recommended) or SQLite for development
- Run database migrations (TBD)

## Project Structure

```
niftyopt/
├── config/              # Configuration files
├── data/                # Data storage
│   ├── raw/            # Raw data files
│   ├── processed/      # Cleaned data
│   └── features/       # Engineered features
├── src/                # Source code
│   ├── module1_data/   # Data & Event Layer
│   ├── module2_historical/  # Historical Probability
│   ├── module3_flow/   # Live Flow Engine
│   ├── module4_strikes/    # Strike & Structure
│   ├── module5_risk/   # Risk & Portfolio
│   ├── module6_ml/     # ML/AI Engine
│   ├── module7_fusion/ # Decision Engine
│   ├── module8_calibration/ # Feedback & Calibration
│   └── utils/          # Shared utilities
├── models/             # Trained ML models
├── logs/               # System logs
├── backtests/          # Backtest results
├── tests/              # Unit tests
└── notebooks/          # Analysis notebooks
```

## Quick Start

1. **Data Collection** (Module 1):
```python
from src.module1_data.data_loader import DataLoader

loader = DataLoader()
loader.load_nifty_eod(start_date='2014-01-01')
loader.load_options_chain(date='2024-01-01')
```

2. **Historical Analysis** (Module 2):
```python
from src.module2_historical.historical_engine import HistoricalEngine

engine = HistoricalEngine()
probabilities = engine.get_probabilities(
    date='2024-12-20',
    horizon='intraday'
)
```

3. **Flow Analysis** (Module 3):
```python
from src.module3_flow.flow_engine import FlowEngine

flow = FlowEngine()
flow_score = flow.calculate_flow_score()
probabilities = flow.get_probabilities(horizon='intraday')
```

## Development Roadmap

### Quick Start
See `QUICK_START_GUIDE.md` for immediate next steps.

### Complete Plan
See `CONSOLIDATED_PLAN.md` for phase-by-phase, step-by-step implementation plan.

### Detailed Roadmap
See `IMPLEMENTATION_ROADMAP.md` for detailed task breakdown.

### Phase 1: Foundation (Weeks 1-2)
- Data infrastructure
- Basic historical and flow engines

### Phase 2: Decision & Risk (Weeks 3-4)
- Strike selection
- Risk management
- Backtesting framework

### Phase 3: ML Integration (Weeks 5-6)
- Feature engineering
- Model training
- ML prediction engine

### Phase 4: Calibration & Production (Weeks 7-8)
- Feedback and calibration
- Live data integration
- Production deployment

## Configuration

All configuration is in YAML files under `config/`:
- `system_config.yaml` - Main system configuration
- `ml_config.yaml` - ML/AI specific settings
- `risk_config.yaml` - Risk management parameters (TBD)

## Testing

Run tests:
```bash
pytest tests/
```

With coverage:
```bash
pytest tests/ --cov=src --cov-report=html
```

## Logging

The system uses structured JSON logging. Logs are stored in `logs/` directory.

## Contributing

1. Follow the modular architecture
2. Write unit tests for new modules
3. Update documentation
4. Follow PEP 8 style guide

## License

[Your License Here]

## Disclaimer

This is a trading system for educational and research purposes. Trading involves risk. Use at your own discretion.

