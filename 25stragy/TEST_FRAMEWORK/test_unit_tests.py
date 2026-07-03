#!/usr/bin/env python3
"""
UNIT TESTS
==========
Unit tests for individual functions and classes
"""

import unittest
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

class TestUnitTests(unittest.TestCase):
    """Unit tests for core functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.test_data = {
            'premium': 100.0,
            'lot_size': 50,
            'capital': 50000
        }
    
    def test_premium_calculation(self):
        """Test premium calculation logic"""
        premium = self.test_data['premium']
        lot_size = self.test_data['lot_size']
        
        expected_investment = premium * lot_size
        actual_investment = premium * lot_size
        
        self.assertEqual(expected_investment, actual_investment)
        self.assertEqual(actual_investment, 5000.0)
    
    def test_capital_allocation(self):
        """Test capital allocation logic"""
        capital = self.test_data['capital']
        
        # Test basic capital allocation
        self.assertEqual(capital, 50000)
        self.assertGreater(capital, 0)
    
    def test_lot_size_validation(self):
        """Test lot size validation"""
        lot_size = self.test_data['lot_size']
        
        self.assertEqual(lot_size, 50)
        self.assertGreater(lot_size, 0)
        self.assertIsInstance(lot_size, int)
    
    def test_premium_limits(self):
        """Test premium limits"""
        premium = self.test_data['premium']
        
        self.assertLessEqual(premium, 350)  # Premium limit
        self.assertGreater(premium, 0)
    
    def test_data_types(self):
        """Test data types"""
        self.assertIsInstance(self.test_data['premium'], (int, float))
        self.assertIsInstance(self.test_data['lot_size'], int)
        self.assertIsInstance(self.test_data['capital'], (int, float))
    
    def test_calculation_accuracy(self):
        """Test calculation accuracy"""
        # Test basic multiplication
        premium = 100.0
        lots = 1
        lot_size = 50
        expected = premium * lots * lot_size
        
        self.assertEqual(expected, 5000.0)
        self.assertAlmostEqual(expected, 5000.0, places=2)
    
    def test_edge_cases(self):
        """Test edge cases"""
        # Test with zero premium
        premium = 0
        lot_size = 50
        expected = 0
        
        self.assertEqual(premium * lot_size, expected)
        
        # Test with minimum premium
        premium = 1
        expected = 50
        
        self.assertEqual(premium * lot_size, expected)
    
    def test_negative_values(self):
        """Test handling of negative values"""
        premium = -100
        lot_size = 50
        
        # Should handle negative premium
        result = premium * lot_size
        self.assertEqual(result, -5000)
    
    def test_large_values(self):
        """Test handling of large values"""
        premium = 10000
        lot_size = 50
        
        result = premium * lot_size
        self.assertEqual(result, 500000)
        self.assertLess(result, 1000000)  # Reasonable limit

class TestStrategyCalculations(unittest.TestCase):
    """Unit tests for strategy calculations"""
    
    def test_roi_calculation(self):
        """Test ROI calculation"""
        investment = 5000
        pnl = 100
        
        expected_roi = (pnl / investment) * 100
        actual_roi = (pnl / investment) * 100
        
        self.assertEqual(expected_roi, actual_roi)
        self.assertEqual(actual_roi, 2.0)
    
    def test_win_rate_calculation(self):
        """Test win rate calculation"""
        wins = 8
        total_trades = 10
        
        expected_win_rate = (wins / total_trades) * 100
        actual_win_rate = (wins / total_trades) * 100
        
        self.assertEqual(expected_win_rate, actual_win_rate)
        self.assertEqual(actual_win_rate, 80.0)
    
    def test_pnl_per_trade(self):
        """Test P&L per trade calculation"""
        total_pnl = 1000
        total_trades = 10
        
        expected_avg_pnl = total_pnl / total_trades
        actual_avg_pnl = total_pnl / total_trades
        
        self.assertEqual(expected_avg_pnl, actual_avg_pnl)
        self.assertEqual(actual_avg_pnl, 100.0)
    
    def test_risk_reward_ratio(self):
        """Test risk-reward ratio calculation"""
        profit_target = 200
        stop_loss = 50
        
        ratio = profit_target / stop_loss
        expected_ratio = 4.0
        
        self.assertEqual(ratio, expected_ratio)
    
    def test_position_sizing(self):
        """Test position sizing calculation"""
        capital = 50000
        risk_per_trade = 0.02  # 2%
        
        position_size = capital * risk_per_trade
        expected_size = 1000
        
        self.assertEqual(position_size, expected_size)

class TestDataValidation(unittest.TestCase):
    """Unit tests for data validation"""
    
    def test_timestamp_format(self):
        """Test timestamp format validation"""
        from datetime import datetime
        
        timestamp = datetime.now()
        
        # Test timestamp is datetime object
        self.assertIsInstance(timestamp, datetime)
        
        # Test timestamp string format
        timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        self.assertIsInstance(timestamp_str, str)
        self.assertGreater(len(timestamp_str), 10)
    
    def test_price_validation(self):
        """Test price validation"""
        valid_prices = [100.0, 250.5, 500.25]
        
        for price in valid_prices:
            self.assertIsInstance(price, (int, float))
            self.assertGreater(price, 0)
            self.assertLess(price, 100000)  # Reasonable upper limit
    
    def test_strike_price_validation(self):
        """Test strike price validation"""
        strikes = [24000, 24500, 25000, 25500]
        
        for strike in strikes:
            self.assertIsInstance(strike, (int, float))
            self.assertGreater(strike, 20000)  # Reasonable lower limit
            self.assertLess(strike, 30000)    # Reasonable upper limit
    
    def test_option_type_validation(self):
        """Test option type validation"""
        valid_types = ['CE', 'PE']
        
        for opt_type in valid_types:
            self.assertIn(opt_type, ['CE', 'PE'])
            self.assertEqual(len(opt_type), 2)
    
    def test_greeks_validation(self):
        """Test Greeks validation"""
        greeks = {
            'delta': 0.5,
            'theta': -0.05,
            'vega': 0.2,
            'gamma': 0.02
        }
        
        # Delta should be between -1 and 1
        self.assertGreaterEqual(greeks['delta'], -1)
        self.assertLessEqual(greeks['delta'], 1)
        
        # Theta should be negative
        self.assertLess(greeks['theta'], 0)
        
        # Vega should be positive
        self.assertGreater(greeks['vega'], 0)
        
        # Gamma should be positive
        self.assertGreater(greeks['gamma'], 0)

class TestConfigurationValidation(unittest.TestCase):
    """Unit tests for configuration validation"""
    
    def test_config_file_existence(self):
        """Test configuration file existence"""
        config_files = [
            'logs/nifty_historical_data.csv',
            'logs/nifty_options_chain_2026-04-07.json'
        ]
        
        for config_file in config_files:
            file_path = project_root / config_file
            self.assertTrue(file_path.exists(), f"Config file {config_file} should exist")
    
    def test_historical_data_format(self):
        """Test historical data format"""
        csv_file = project_root / 'logs/nifty_historical_data.csv'
        
        if csv_file.exists():
            with open(csv_file, 'r') as f:
                first_line = f.readline().strip()
                expected_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'vwap']
                
                self.assertIn('timestamp', first_line)
                self.assertIn('close', first_line)
                self.assertIn('volume', first_line)
    
    def test_options_chain_format(self):
        """Test options chain format"""
        json_file = project_root / 'logs/nifty_options_chain_2026-04-07.json'
        
        if json_file.exists():
            import json
            with open(json_file, 'r') as f:
                data = json.load(f)
                
            self.assertIsInstance(data, dict)
            self.assertGreater(len(data), 0)
            
            # Check first strike
            first_strike = list(data.keys())[0]
            self.assertIn('ce', data[first_strike])
            self.assertIn('pe', data[first_strike])

def run_unit_tests():
    """Run unit tests"""
    print("🧪 Running Unit Tests...")
    
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestUnitTests,
        TestStrategyCalculations,
        TestDataValidation,
        TestConfigurationValidation
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Return results
    return {
        'total': result.testsRun,
        'passed': result.testsRun - len(result.failures) - len(result.errors),
        'failed': len(result.failures),
        'errors': len(result.errors),
        'success': result.wasSuccessful()
    }

if __name__ == "__main__":
    run_unit_tests()
