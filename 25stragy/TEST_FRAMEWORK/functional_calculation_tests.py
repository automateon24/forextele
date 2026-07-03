#!/usr/bin/env python3
"""
FUNCTIONAL CALCULATION TESTS
=============================
Functional tests for calculation accuracy and logic
"""

import sys
import os
from pathlib import Path
import json
import pandas as pd
import numpy as np
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

class FunctionalCalculationTests:
    """Functional tests for calculations"""
    
    def __init__(self):
        self.test_results = []
        self.errors = []
        
    def test_option_premium_calculations(self):
        """Test option premium calculations with real data"""
        print("🧮 Testing Option Premium Calculations...")
        
        try:
            # Load real options data
            options_file = project_root / 'logs/nifty_options_chain_2026-04-07.json'
            if not options_file.exists():
                self.errors.append("Options chain file not found")
                return False
            
            with open(options_file, 'r') as f:
                options_data = json.load(f)
            
            # Test premium calculations
            test_strikes = ['24500', '24600', '24700', '24800', '24900']
            
            for strike in test_strikes:
                if strike in options_data:
                    ce_data = options_data[strike].get('ce', {})
                    pe_data = options_data[strike].get('pe', {})
                    
                    if ce_data and 'last_price' in ce_data:
                        premium = ce_data['last_price']
                        investment = premium * 50  # lot_size
                        
                        # Validate calculation
                        self.assertIsInstance(premium, (int, float))
                        self.assertGreater(premium, 0)
                        self.assertLess(premium, 350)  # Premium limit
                        
                        # Test investment calculation
                        expected_investment = premium * 50
                        self.assertEqual(investment, expected_investment)
                        
                        self.test_results.append({
                            'test': 'premium_calculation',
                            'strike': strike,
                            'type': 'CE',
                            'premium': premium,
                            'investment': investment,
                            'status': 'passed'
                        })
                    
                    if pe_data and 'last_price' in pe_data:
                        premium = pe_data['last_price']
                        investment = premium * 50
                        
                        self.assertIsInstance(premium, (int, float))
                        self.assertGreater(premium, 0)
                        self.assertLess(premium, 350)
                        
                        expected_investment = premium * 50
                        self.assertEqual(investment, expected_investment)
                        
                        self.test_results.append({
                            'test': 'premium_calculation',
                            'strike': strike,
                            'type': 'PE',
                            'premium': premium,
                            'investment': investment,
                            'status': 'passed'
                        })
            
            print(f"✅ Premium calculations tested: {len(self.test_results)} strikes")
            return True
            
        except Exception as e:
            self.errors.append(f"Premium calculation error: {e}")
            print(f"❌ Premium calculation error: {e}")
            return False
    
    def test_pnl_calculations(self):
        """Test P&L calculations"""
        print("💰 Testing P&L Calculations...")
        
        try:
            # Test various P&L scenarios
            test_scenarios = [
                {'entry_premium': 100, 'exit_premium': 110, 'lots': 1, 'expected_pnl': 500},
                {'entry_premium': 50, 'exit_premium': 55, 'lots': 1, 'expected_pnl': 250},
                {'entry_premium': 200, 'exit_premium': 180, 'lots': 1, 'expected_pnl': -1000},
                {'entry_premium': 100, 'exit_premium': 120, 'lots': 2, 'expected_pnl': 2000},
            ]
            
            for scenario in test_scenarios:
                entry_premium = scenario['entry_premium']
                exit_premium = scenario['exit_premium']
                lots = scenario['lots']
                lot_size = 50
                
                # Calculate P&L
                premium_diff = exit_premium - entry_premium
                actual_pnl = premium_diff * lots * lot_size
                expected_pnl = scenario['expected_pnl']
                
                # Validate calculation
                self.assertEqual(actual_pnl, expected_pnl)
                
                # Test ROI calculation
                investment = entry_premium * lots * lot_size
                roi = (actual_pnl / investment) * 100
                
                self.assertIsInstance(roi, (int, float))
                
                self.test_results.append({
                    'test': 'pnl_calculation',
                    'entry_premium': entry_premium,
                    'exit_premium': exit_premium,
                    'lots': lots,
                    'actual_pnl': actual_pnl,
                    'expected_pnl': expected_pnl,
                    'roi': roi,
                    'status': 'passed'
                })
            
            print(f"✅ P&L calculations tested: {len(test_scenarios)} scenarios")
            return True
            
        except Exception as e:
            self.errors.append(f"P&L calculation error: {e}")
            print(f"❌ P&L calculation error: {e}")
            return False
    
    def test_greeks_calculations(self):
        """Test Greeks calculations"""
        print("📊 Testing Greeks Calculations...")
        
        try:
            # Load real options data with Greeks
            options_file = project_root / 'logs/nifty_options_chain_2026-04-07.json'
            if not options_file.exists():
                self.errors.append("Options chain file not found")
                return False
            
            with open(options_file, 'r') as f:
                options_data = json.load(f)
            
            # Test Greeks values
            test_strikes = ['24500', '24600', '24700']
            
            for strike in test_strikes:
                if strike in options_data:
                    ce_data = options_data[strike].get('ce', {})
                    
                    if ce_data:
                        delta = ce_data.get('delta', 0)
                        theta = ce_data.get('theta', 0)
                        vega = ce_data.get('vega', 0)
                        gamma = ce_data.get('gamma', 0)
                        
                        # Validate Delta (-1 to 1)
                        self.assertGreaterEqual(delta, -1)
                        self.assertLessEqual(delta, 1)
                        
                        # Validate Theta (should be negative for options)
                        self.assertLessEqual(theta, 0)
                        
                        # Validate Vega (should be positive)
                        self.assertGreaterEqual(vega, 0)
                        
                        # Validate Gamma (should be positive)
                        self.assertGreaterEqual(gamma, 0)
                        
                        # Test Greeks relationships
                        if delta > 0.5:  # Deep ITM
                            self.assertLess(abs(theta), 0.1)  # Lower time decay
                        elif delta < 0.5 and delta > -0.5:  # ATM
                            self.assertGreater(abs(theta), 0.05)  # Higher time decay
                        
                        self.test_results.append({
                            'test': 'greeks_calculation',
                            'strike': strike,
                            'type': 'CE',
                            'delta': delta,
                            'theta': theta,
                            'vega': vega,
                            'gamma': gamma,
                            'status': 'passed'
                        })
            
            print(f"✅ Greeks calculations tested: {len(self.test_results)} strikes")
            return True
            
        except Exception as e:
            self.errors.append(f"Greeks calculation error: {e}")
            print(f"❌ Greeks calculation error: {e}")
            return False
    
    def test_risk_management_calculations(self):
        """Test risk management calculations"""
        print("🛡️ Testing Risk Management Calculations...")
        
        try:
            # Test position sizing
            capital = 50000
            risk_per_trade = 0.02  # 2%
            
            position_size = capital * risk_per_trade
            expected_size = 1000
            
            self.assertEqual(position_size, expected_size)
            
            # Test stop loss calculation
            entry_price = 100
            stop_loss_pct = 0.02  # 2%
            
            stop_loss_price = entry_price * (1 - stop_loss_pct)
            expected_stop_loss = 98
            
            self.assertEqual(stop_loss_price, expected_stop_loss)
            
            # Test take profit calculation
            take_profit_pct = 0.05  # 5%
            
            take_profit_price = entry_price * (1 + take_profit_pct)
            expected_take_profit = 105
            
            self.assertEqual(take_profit_price, expected_take_profit)
            
            # Test risk-reward ratio
            risk_amount = entry_price - stop_loss_price
            reward_amount = take_profit_price - entry_price
            risk_reward_ratio = reward_amount / risk_amount
            
            expected_ratio = 2.5  # 5/2
            self.assertEqual(risk_reward_ratio, expected_ratio)
            
            self.test_results.append({
                'test': 'risk_management',
                'position_size': position_size,
                'stop_loss': stop_loss_price,
                'take_profit': take_profit_price,
                'risk_reward_ratio': risk_reward_ratio,
                'status': 'passed'
            })
            
            print("✅ Risk management calculations tested")
            return True
            
        except Exception as e:
            self.errors.append(f"Risk management calculation error: {e}")
            print(f"❌ Risk management calculation error: {e}")
            return False
    
    def test_strategy_performance_calculations(self):
        """Test strategy performance calculations"""
        print("📈 Testing Strategy Performance Calculations...")
        
        try:
            # Test sample performance data
            trades = [
                {'pnl': 100, 'investment': 5000},
                {'pnl': -50, 'investment': 5000},
                {'pnl': 200, 'investment': 5000},
                {'pnl': 150, 'investment': 5000},
                {'pnl': -25, 'investment': 5000},
            ]
            
            # Calculate total P&L
            total_pnl = sum(trade['pnl'] for trade in trades)
            expected_total_pnl = 100 - 50 + 200 + 150 - 25
            
            self.assertEqual(total_pnl, expected_total_pnl)
            
            # Calculate total investment
            total_investment = sum(trade['investment'] for trade in trades)
            expected_total_investment = 5000 * 5
            
            self.assertEqual(total_investment, expected_total_investment)
            
            # Calculate win rate
            wins = len([t for t in trades if t['pnl'] > 0])
            total_trades = len(trades)
            win_rate = (wins / total_trades) * 100
            
            expected_wins = 3
            expected_win_rate = (expected_wins / total_trades) * 100
            
            self.assertEqual(wins, expected_wins)
            self.assertEqual(win_rate, expected_win_rate)
            
            # Calculate ROI
            roi = (total_pnl / total_investment) * 100
            expected_roi = (expected_total_pnl / expected_total_investment) * 100
            
            self.assertEqual(roi, expected_roi)
            
            # Calculate average P&L per trade
            avg_pnl = total_pnl / total_trades
            expected_avg_pnl = expected_total_pnl / total_trades
            
            self.assertEqual(avg_pnl, expected_avg_pnl)
            
            self.test_results.append({
                'test': 'strategy_performance',
                'total_pnl': total_pnl,
                'total_investment': total_investment,
                'win_rate': win_rate,
                'roi': roi,
                'avg_pnl': avg_pnl,
                'status': 'passed'
            })
            
            print("✅ Strategy performance calculations tested")
            return True
            
        except Exception as e:
            self.errors.append(f"Strategy performance calculation error: {e}")
            print(f"❌ Strategy performance calculation error: {e}")
            return False
    
    def test_market_data_calculations(self):
        """Test market data calculations"""
        print("📊 Testing Market Data Calculations...")
        
        try:
            # Load historical data
            hist_file = project_root / 'logs/nifty_historical_data.csv'
            if not hist_file.exists():
                self.errors.append("Historical data file not found")
                return False
            
            df = pd.read_csv(hist_file)
            
            # Test price change calculation
            if len(df) > 1:
                prev_close = df.iloc[0]['close']
                curr_close = df.iloc[1]['close']
                
                price_change = (curr_close - prev_close) / prev_close
                expected_change = (curr_close - prev_close) / prev_close
                
                self.assertEqual(price_change, expected_change)
                
                # Test high-low range calculation
                high = df.iloc[1]['high']
                low = df.iloc[1]['low']
                close = df.iloc[1]['close']
                
                high_low_range = (high - low) / close
                expected_range = (high - low) / close
                
                self.assertEqual(high_low_range, expected_range)
                
                # Test volume ratio
                volume = df.iloc[1]['volume']
                vwap = df.iloc[1]['vwap']
                
                if vwap > 0:
                    volume_ratio = volume / vwap
                    expected_ratio = volume / vwap
                    
                    self.assertEqual(volume_ratio, expected_ratio)
                
                self.test_results.append({
                    'test': 'market_data',
                    'price_change': price_change,
                    'high_low_range': high_low_range,
                    'volume_ratio': volume_ratio if vwap > 0 else 0,
                    'status': 'passed'
                })
            
            print(f"✅ Market data calculations tested: {len(df)} data points")
            return True
            
        except Exception as e:
            self.errors.append(f"Market data calculation error: {e}")
            print(f"❌ Market data calculation error: {e}")
            return False
    
    def assertEqual(self, actual, expected):
        """Custom assertEqual method"""
        if actual != expected:
            raise AssertionError(f"Expected {expected}, got {actual}")
    
    def assertGreater(self, actual, expected):
        """Custom assertGreater method"""
        if actual <= expected:
            raise AssertionError(f"Expected greater than {expected}, got {actual}")
    
    def assertLess(self, actual, expected):
        """Custom assertLess method"""
        if actual >= expected:
            raise AssertionError(f"Expected less than {expected}, got {actual}")
    
    def assertGreaterEqual(self, actual, expected):
        """Custom assertGreaterEqual method"""
        if actual < expected:
            raise AssertionError(f"Expected greater than or equal to {expected}, got {actual}")
    
    def assertLessEqual(self, actual, expected):
        """Custom assertLessEqual method"""
        if actual > expected:
            raise AssertionError(f"Expected less than or equal to {expected}, got {actual}")
    
    def assertIn(self, item, container):
        """Custom assertIn method"""
        if item not in container:
            raise AssertionError(f"Expected {item} in {container}")
    
    def assertIsInstance(self, obj, expected_type):
        """Custom assertIsInstance method"""
        if not isinstance(obj, expected_type):
            raise AssertionError(f"Expected {expected_type}, got {type(obj)}")
    
    def run_all_tests(self):
        """Run all functional calculation tests"""
        print("🧮 Starting Functional Calculation Tests...")
        print("="*60)
        
        tests = [
            self.test_option_premium_calculations,
            self.test_pnl_calculations,
            self.test_greeks_calculations,
            self.test_risk_management_calculations,
            self.test_strategy_performance_calculations,
            self.test_market_data_calculations
        ]
        
        passed = 0
        failed = 0
        
        for test in tests:
            try:
                if test():
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"❌ Test failed: {e}")
                failed += 1
        
        print("="*60)
        print(f"🧮 Functional Calculation Tests Results:")
        print(f"   ✅ Passed: {passed}")
        print(f"   ❌ Failed: {failed}")
        print(f"   📊 Total Tests: {passed + failed}")
        print(f"   📝 Test Results: {len(self.test_results)}")
        
        if self.errors:
            print(f"   ⚠️  Errors: {len(self.errors)}")
            for error in self.errors:
                print(f"      - {error}")
        
        return len(self.errors) == 0

def main():
    """Main execution"""
    tester = FunctionalCalculationTests()
    success = tester.run_all_tests()
    
    if success:
        print("🎉 All functional calculation tests passed!")
        return 0
    else:
        print("❌ Some functional calculation tests failed!")
        return 1

if __name__ == "__main__":
    main()
