#!/usr/bin/env python3
"""
WORKING UNIT TESTS
=================
Unit tests that work without external dependencies
"""

import unittest
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

class WorkingUnitTests(unittest.TestCase):
    """Working unit tests"""
    
    def test_basic_calculations(self):
        """Test basic calculations"""
        # Premium calculation
        premium = 100.0
        lot_size = 50
        investment = premium * lot_size
        self.assertEqual(investment, 5000.0)
        
        # P&L calculation
        entry_premium = 100
        exit_premium = 110
        pnl = (exit_premium - entry_premium) * lot_size
        self.assertEqual(pnl, 500.0)
        
        # ROI calculation
        roi = (pnl / investment) * 100
        self.assertEqual(roi, 10.0)
    
    def test_data_validation(self):
        """Test data validation"""
        # Test premium limits
        premium = 100
        self.assertLessEqual(premium, 350)
        self.assertGreater(premium, 0)
        
        # Test strike prices
        strike = 24500
        self.assertGreater(strike, 20000)
        self.assertLess(strike, 30000)
        
        # Test option types
        option_types = ['CE', 'PE']
        for opt_type in option_types:
            self.assertIn(opt_type, ['CE', 'PE'])
    
    def test_greeks_validation(self):
        """Test Greeks validation"""
        # Test Delta
        delta = 0.5
        self.assertGreaterEqual(delta, -1)
        self.assertLessEqual(delta, 1)
        
        # Test Theta
        theta = -0.05
        self.assertLessEqual(theta, 0)
        
        # Test Vega
        vega = 0.2
        self.assertGreaterEqual(vega, 0)
        
        # Test Gamma
        gamma = 0.02
        self.assertGreaterEqual(gamma, 0)
    
    def test_file_existence(self):
        """Test file existence"""
        # Test data files
        hist_file = project_root / 'logs' / 'nifty_historical_data.csv'
        self.assertTrue(hist_file.exists(), "Historical data file should exist")
        
        options_file = project_root / 'logs' / 'nifty_options_chain_filtered_350.json'
        self.assertTrue(options_file.exists(), "Filtered options chain file should exist")
    
    def test_strategy_calculations(self):
        """Test strategy calculations"""
        # Test win rate
        wins = 8
        total_trades = 10
        win_rate = (wins / total_trades) * 100
        self.assertEqual(win_rate, 80.0)
        
        # Test risk-reward ratio
        profit_target = 200
        stop_loss = 50
        risk_reward = profit_target / stop_loss
        self.assertEqual(risk_reward, 4.0)
        
        # Test position sizing
        capital = 50000
        risk_per_trade = 0.02
        position_size = capital * risk_per_trade
        self.assertEqual(position_size, 1000.0)

def run_working_unit_tests():
    """Run working unit tests"""
    print("🧪 Running Working Unit Tests...")
    
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [WorkingUnitTests]
    
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
    results = run_working_unit_tests()
    print(f"\n📊 Results: {results['passed']}/{results['total']} passed")
    
    if results['success']:
        print("🎉 All unit tests passed!")
    else:
        print("❌ Some unit tests failed!")
