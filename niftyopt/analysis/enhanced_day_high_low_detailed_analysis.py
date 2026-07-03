#!/usr/bin/env python3
"""
📊 ENHANCED_DAY_HIGH_LOW DETAILED ANALYSIS
==========================================
Comprehensive analysis with daily metrics, drawdowns, ROI, and monthly performance
Uses ONLY real historical data - no simulated data
"""

import os
import sys
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import yaml
# import matplotlib.pyplot as plt
# import seaborn as sns
from dataclasses import dataclass
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_manager import DataManager
from src.trade_logger import TradeLogger

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

@dataclass
class DailyMetrics:
    """Daily performance metrics"""
    date: datetime
    daily_pnl: float
    daily_roi: float
    max_profit: float
    max_loss: float
    max_drawdown: float
    trades_count: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    volume: int
    spot_price: float
    market_regime: str

@dataclass
class MonthlyMetrics:
    """Monthly performance metrics"""
    month: str
    total_pnl: float
    total_roi: float
    max_daily_profit: float
    max_daily_loss: float
    max_drawdown: float
    total_trades: int
    win_rate: float
    avg_daily_pnl: float

class EnhancedDayHighLowAnalyzer:
    """Detailed analyzer for ENHANCED_DAY_HIGH_LOW strategy"""
    
    def __init__(self, config_path="config/strategy_config.yaml"):
        self.config = self._load_config(config_path)
        self.data_manager = DataManager(config_path)
        self.trade_logger = TradeLogger(config_path)
        
        # Analysis data
        self.daily_metrics = []
        self.monthly_metrics = []
        self.yearly_metrics = []
        
        logger.info("📊 Enhanced Day High/Low Analyzer initialized")
    
    def _load_config(self, config_path):
        """Load configuration from YAML file"""
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return {}
    
    def run_detailed_analysis(self, start_date=None, end_date=None):
        """Run detailed analysis with real historical data"""
        logger.info("🔍 Starting detailed ENHANCED_DAY_HIGH_LOW analysis...")
        
        # Get historical data
        data = self.data_manager.get_historical_data_for_backtest(start_date, end_date, '15min')
        
        if data is None or len(data) == 0:
            logger.error("❌ No historical data available")
            return
        
        logger.info(f"📊 Processing {len(data)} historical records...")
        
        # Initialize strategy
        from strategies.strategy_enhanced_day_high_low import EnhancedDayHighLowStrategy
        strategy = EnhancedDayHighLowStrategy()
        
        # Track daily performance
        current_date = None
        daily_trades = []
        daily_pnl = 0
        max_daily_profit = 0
        max_daily_loss = 0
        max_drawdown = 0
        peak_capital = strategy.initial_capital
        current_capital = strategy.initial_capital
        
        # Process each candle
        for idx, row in data.iterrows():
            try:
                candle_date = row['date'].date() if isinstance(row['date'], pd.Timestamp) else row['date']
                
                # New day - calculate daily metrics
                if current_date is None:
                    current_date = candle_date
                elif candle_date != current_date:
                    # Calculate daily metrics
                    if daily_trades:
                        daily_metrics = self._calculate_daily_metrics(
                            current_date, daily_trades, daily_pnl, 
                            max_daily_profit, max_daily_loss, max_drawdown,
                            row['volume'], row['spot_price']
                        )
                        self.daily_metrics.append(daily_metrics)
                    
                    # Reset for new day
                    current_date = candle_date
                    daily_trades = []
                    daily_pnl = 0
                    max_daily_profit = 0
                    max_daily_loss = 0
                    max_drawdown = 0
                    peak_capital = current_capital
                
                # Update price history for strategy
                strategy.price_history.append(row['close'])
                strategy.volume_history.append(row['volume'])
                
                # Keep only required history
                if len(strategy.price_history) > strategy.lookback_period + 14:
                    strategy.price_history = strategy.price_history[-(strategy.lookback_period + 14):]
                    strategy.volume_history = strategy.volume_history[-(strategy.lookback_period + 14):]
                
                # Generate signals
                signals = strategy._generate_signals(row)
                
                # Execute signals
                for signal in signals:
                    trade = self._execute_signal_for_analysis(signal, row, strategy)
                    if trade:
                        daily_trades.append(trade)
                        daily_pnl += trade['pnl']
                        current_capital += trade['pnl']
                        
                        # Update daily max profit/loss
                        if trade['pnl'] > max_daily_profit:
                            max_daily_profit = trade['pnl']
                        if trade['pnl'] < max_daily_loss:
                            max_daily_loss = trade['pnl']
                        
                        # Update drawdown
                        if current_capital > peak_capital:
                            peak_capital = current_capital
                        drawdown = (peak_capital - current_capital) / peak_capital * 100
                        if drawdown > max_drawdown:
                            max_drawdown = drawdown
                
                # Manage positions
                closed_trades = strategy._manage_positions_for_analysis(row)
                for trade in closed_trades:
                    daily_trades.append(trade)
                    daily_pnl += trade['pnl']
                    current_capital += trade['pnl']
                    
                    # Update daily max profit/loss
                    if trade['pnl'] > max_daily_profit:
                        max_daily_profit = trade['pnl']
                    if trade['pnl'] < max_daily_loss:
                        max_daily_loss = trade['pnl']
                    
                    # Update drawdown
                    if current_capital > peak_capital:
                        peak_capital = current_capital
                    drawdown = (peak_capital - current_capital) / peak_capital * 100
                    if drawdown > max_drawdown:
                        max_drawdown = drawdown
                
                # Log progress
                if idx % 1000 == 0:
                    logger.info(f"   Processed {idx}/{len(data)} records...")
                
            except Exception as e:
                logger.error(f"Error processing row {idx}: {e}")
        
        # Process last day
        if daily_trades:
            daily_metrics = self._calculate_daily_metrics(
                current_date, daily_trades, daily_pnl, 
                max_daily_profit, max_daily_loss, max_drawdown,
                row['volume'], row['spot_price']
            )
            self.daily_metrics.append(daily_metrics)
        
        # Calculate monthly and yearly metrics
        self._calculate_monthly_metrics()
        self._calculate_yearly_metrics()
        
        # Generate reports
        self._generate_detailed_reports()
        
        logger.info("✅ Detailed ENHANCED_DAY_HIGH_LOW analysis completed")
    
    def _execute_signal_for_analysis(self, signal, candle, strategy):
        """Execute signal for analysis"""
        try:
            # Calculate position size
            risk_amount = strategy.current_capital * strategy.position_size_percent
            premium_per_lot = signal.premium * 75
            max_lots = int(risk_amount / premium_per_lot)
            
            lots = max(8, max_lots)
            lots = min(30, lots)
            quantity = lots * 75
            
            return {
                'signal': signal,
                'quantity': quantity,
                'entry_price': signal.premium,
                'entry_time': candle.get('datetime', datetime.now()),
                'pnl': 0,  # Will be calculated when position is closed
                'exit_price': 0,
                'exit_time': None
            }
            
        except Exception as e:
            logger.error(f"Error executing signal: {e}")
            return None
    
    def _calculate_daily_metrics(self, date, trades, daily_pnl, max_profit, max_loss, max_drawdown, volume, spot_price):
        """Calculate daily performance metrics"""
        winning_trades = [t for t in trades if t['pnl'] > 0]
        losing_trades = [t for t in trades if t['pnl'] <= 0]
        
        win_rate = (len(winning_trades) / len(trades)) * 100 if trades else 0
        daily_roi = (daily_pnl / 100000) * 100  # Assuming 1L capital
        
        return DailyMetrics(
            date=date,
            daily_pnl=daily_pnl,
            daily_roi=daily_roi,
            max_profit=max_profit,
            max_loss=max_loss,
            max_drawdown=max_drawdown,
            trades_count=len(trades),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=win_rate,
            volume=volume,
            spot_price=spot_price,
            market_regime="historical"
        )
    
    def _calculate_monthly_metrics(self):
        """Calculate monthly performance metrics"""
        if not self.daily_metrics:
            return
        
        # Group by month
        monthly_data = {}
        for daily in self.daily_metrics:
            month_key = daily.date.strftime('%Y-%m')
            if month_key not in monthly_data:
                monthly_data[month_key] = []
            monthly_data[month_key].append(daily)
        
        # Calculate metrics for each month
        for month, days in monthly_data.items():
            total_pnl = sum(d.daily_pnl for d in days)
            total_roi = sum(d.daily_roi for d in days)
            max_daily_profit = max(d.max_profit for d in days)
            max_daily_loss = min(d.max_loss for d in days)
            max_drawdown = max(d.max_drawdown for d in days)
            total_trades = sum(d.trades_count for d in days)
            avg_win_rate = np.mean([d.win_rate for d in days])
            avg_daily_pnl = total_pnl / len(days)
            
            self.monthly_metrics.append(MonthlyMetrics(
                month=month,
                total_pnl=total_pnl,
                total_roi=total_roi,
                max_daily_profit=max_daily_profit,
                max_daily_loss=max_daily_loss,
                max_drawdown=max_drawdown,
                total_trades=total_trades,
                win_rate=avg_win_rate,
                avg_daily_pnl=avg_daily_pnl
            ))
    
    def _calculate_yearly_metrics(self):
        """Calculate yearly performance metrics"""
        if not self.monthly_metrics:
            return
        
        # Group by year
        yearly_data = {}
        for monthly in self.monthly_metrics:
            year = monthly.month.split('-')[0]
            if year not in yearly_data:
                yearly_data[year] = []
            yearly_data[year].append(monthly)
        
        # Calculate metrics for each year
        for year, months in yearly_data.items():
            total_pnl = sum(m.total_pnl for m in months)
            total_roi = sum(m.total_roi for m in months)
            max_monthly_profit = max(m.total_pnl for m in months)
            max_monthly_loss = min(m.total_pnl for m in months)
            total_trades = sum(m.total_trades for m in months)
            avg_win_rate = np.mean([m.win_rate for m in months])
            
            self.yearly_metrics.append({
                'year': year,
                'total_pnl': total_pnl,
                'total_roi': total_roi,
                'max_monthly_profit': max_monthly_profit,
                'max_monthly_loss': max_monthly_loss,
                'total_trades': total_trades,
                'win_rate': avg_win_rate
            })
    
    def _generate_detailed_reports(self):
        """Generate detailed analysis reports"""
        logger.info("📋 Generating detailed reports...")
        
        # Create reports directory
        reports_dir = Path("reports")
        reports_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Generate detailed text report
        self._generate_text_report(reports_dir / f"enhanced_day_high_low_detailed_{timestamp}.txt")
        
        # Generate CSV reports
        self._generate_csv_reports(reports_dir, timestamp)
        
        # Generate summary statistics
        self._generate_summary_statistics(reports_dir / f"enhanced_day_high_low_summary_{timestamp}.txt")
        
        logger.info(f"✅ Reports generated in: {reports_dir}")
    
    def _generate_text_report(self, report_file):
        """Generate detailed text report"""
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("📊 ENHANCED_DAY_HIGH_LOW DETAILED ANALYSIS REPORT\n")
            f.write("=" * 60 + "\n\n")
            
            # Overall Summary
            f.write("📈 OVERALL PERFORMANCE SUMMARY\n")
            f.write("-" * 40 + "\n")
            
            if self.daily_metrics:
                total_pnl = sum(d.daily_pnl for d in self.daily_metrics)
                total_trades = sum(d.trades_count for d in self.daily_metrics)
                avg_daily_pnl = total_pnl / len(self.daily_metrics)
                total_roi = (total_pnl / 100000) * 100
                
                f.write(f"Total Trading Days: {len(self.daily_metrics)}\n")
                f.write(f"Total P&L: ₹{total_pnl:,.0f}\n")
                f.write(f"Total ROI: {total_roi:.2f}%\n")
                f.write(f"Total Trades: {total_trades}\n")
                f.write(f"Average Daily P&L: ₹{avg_daily_pnl:,.0f}\n")
                f.write(f"Target Achievement: {(avg_daily_pnl/27000)*100:.1f}%\n\n")
            
            # Daily Performance Analysis
            f.write("📅 DAILY PERFORMANCE ANALYSIS\n")
            f.write("-" * 40 + "\n")
            
            if self.daily_metrics:
                # Best and worst days
                best_day = max(self.daily_metrics, key=lambda x: x.daily_pnl)
                worst_day = min(self.daily_metrics, key=lambda x: x.daily_pnl)
                max_drawdown_day = max(self.daily_metrics, key=lambda x: x.max_drawdown)
                
                f.write(f"Best Day: {best_day.date.strftime('%Y-%m-%d')} | P&L: ₹{best_day.daily_pnl:,.0f} | ROI: {best_day.daily_roi:.2f}%\n")
                f.write(f"Worst Day: {worst_day.date.strftime('%Y-%m-%d')} | P&L: ₹{worst_day.daily_pnl:,.0f} | ROI: {worst_day.daily_roi:.2f}%\n")
                f.write(f"Max Drawdown Day: {max_drawdown_day.date.strftime('%Y-%m-%d')} | Drawdown: {max_drawdown_day.max_drawdown:.2f}%\n")
                f.write(f"Average Daily Win Rate: {np.mean([d.win_rate for d in self.daily_metrics]):.1f}%\n")
                f.write(f"Average Daily Trades: {np.mean([d.trades_count for d in self.daily_metrics]):.1f}\n\n")
            
            # Monthly Performance Analysis
            f.write("📊 MONTHLY PERFORMANCE ANALYSIS\n")
            f.write("-" * 40 + "\n")
            
            if self.monthly_metrics:
                # Best and worst months
                best_month = max(self.monthly_metrics, key=lambda x: x.total_pnl)
                worst_month = min(self.monthly_metrics, key=lambda x: x.total_pnl)
                
                f.write(f"Best Month: {best_month.month} | P&L: ₹{best_month.total_pnl:,.0f} | ROI: {best_month.total_roi:.2f}%\n")
                f.write(f"Worst Month: {worst_month.month} | P&L: ₹{worst_month.total_pnl:,.0f} | ROI: {worst_month.total_roi:.2f}%\n")
                f.write(f"Average Monthly P&L: ₹{np.mean([m.total_pnl for m in self.monthly_metrics]):,.0f}\n")
                f.write(f"Average Monthly ROI: {np.mean([m.total_roi for m in self.monthly_metrics]):.2f}%\n\n")
                
                # Top 5 performing months
                f.write("🏆 TOP 5 PERFORMING MONTHS:\n")
                top_months = sorted(self.monthly_metrics, key=lambda x: x.total_pnl, reverse=True)[:5]
                for i, month in enumerate(top_months, 1):
                    f.write(f"{i}. {month.month}: ₹{month.total_pnl:,.0f} ({month.total_roi:.2f}% ROI)\n")
                f.write("\n")
            
            # Yearly Performance Analysis
            f.write("📈 YEARLY PERFORMANCE ANALYSIS\n")
            f.write("-" * 40 + "\n")
            
            if self.yearly_metrics:
                for year in sorted(self.yearly_metrics, key=lambda x: x['year']):
                    f.write(f"{year['year']}: P&L: ₹{year['total_pnl']:,.0f} | ROI: {year['total_roi']:.2f}% | Trades: {year['total_trades']}\n")
                f.write("\n")
            
            # Risk Analysis
            f.write("⚠️ RISK ANALYSIS\n")
            f.write("-" * 40 + "\n")
            
            if self.daily_metrics:
                max_drawdown = max(d.max_drawdown for d in self.daily_metrics)
                avg_drawdown = np.mean([d.max_drawdown for d in self.daily_metrics if d.max_drawdown > 0])
                max_loss = min(d.max_loss for d in self.daily_metrics)
                
                f.write(f"Maximum Drawdown: {max_drawdown:.2f}%\n")
                f.write(f"Average Drawdown: {avg_drawdown:.2f}%\n")
                f.write(f"Maximum Daily Loss: ₹{max_loss:,.0f}\n")
                f.write(f"Win Rate Consistency: {np.std([d.win_rate for d in self.daily_metrics]):.2f}% (std dev)\n\n")
    
    def _generate_csv_reports(self, reports_dir, timestamp):
        """Generate CSV reports"""
        # Daily metrics CSV
        if self.daily_metrics:
            daily_df = pd.DataFrame([asdict(d) for d in self.daily_metrics])
            daily_df.to_csv(reports_dir / f"daily_metrics_{timestamp}.csv", index=False)
        
        # Monthly metrics CSV
        if self.monthly_metrics:
            monthly_df = pd.DataFrame([asdict(m) for m in self.monthly_metrics])
            monthly_df.to_csv(reports_dir / f"monthly_metrics_{timestamp}.csv", index=False)
        
        # Yearly metrics CSV
        if self.yearly_metrics:
            yearly_df = pd.DataFrame(self.yearly_metrics)
            yearly_df.to_csv(reports_dir / f"yearly_metrics_{timestamp}.csv", index=False)
    
    def _generate_summary_statistics(self, summary_file):
        """Generate summary statistics"""
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write("📊 ENHANCED_DAY_HIGH_LOW SUMMARY STATISTICS\n")
            f.write("=" * 50 + "\n\n")
            
            if not self.daily_metrics:
                f.write("No data available for analysis\n")
                return
            
            # Basic statistics
            daily_pnls = [d.daily_pnl for d in self.daily_metrics]
            daily_rois = [d.daily_roi for d in self.daily_metrics]
            drawdowns = [d.max_drawdown for d in self.daily_metrics]
            
            f.write("📈 DAILY P&L STATISTICS:\n")
            f.write(f"Mean: ₹{np.mean(daily_pnls):,.0f}\n")
            f.write(f"Median: ₹{np.median(daily_pnls):,.0f}\n")
            f.write(f"Std Dev: ₹{np.std(daily_pnls):,.0f}\n")
            f.write(f"Min: ₹{np.min(daily_pnls):,.0f}\n")
            f.write(f"Max: ₹{np.max(daily_pnls):,.0f}\n")
            f.write(f"25th Percentile: ₹{np.percentile(daily_pnls, 25):,.0f}\n")
            f.write(f"75th Percentile: ₹{np.percentile(daily_pnls, 75):,.0f}\n\n")
            
            f.write("📊 DAILY ROI STATISTICS:\n")
            f.write(f"Mean: {np.mean(daily_rois):.2f}%\n")
            f.write(f"Median: {np.median(daily_rois):.2f}%\n")
            f.write(f"Std Dev: {np.std(daily_rois):.2f}%\n")
            f.write(f"Min: {np.min(daily_rois):.2f}%\n")
            f.write(f"Max: {np.max(daily_rois):.2f}%\n\n")
            
            f.write("⚠️ DRAWDOWN STATISTICS:\n")
            f.write(f"Max Drawdown: {np.max(drawdowns):.2f}%\n")
            f.write(f"Average Drawdown: {np.mean([d for d in drawdowns if d > 0]):.2f}%\n")
            f.write(f"Drawdown Frequency: {len([d for d in drawdowns if d > 0])/len(drawdowns)*100:.1f}%\n\n")
            
            # Monthly analysis
            if self.monthly_metrics:
                f.write("📅 MONTHLY BREAKDOWN:\n")
                monthly_pnls = [m.total_pnl for m in self.monthly_metrics]
                f.write(f"Average Monthly P&L: ₹{np.mean(monthly_pnls):,.0f}\n")
                f.write(f"Best Monthly P&L: ₹{np.max(monthly_pnls):,.0f}\n")
                f.write(f"Worst Monthly P&L: ₹{np.min(monthly_pnls):,.0f}\n")
                f.write(f"Monthly Volatility: ₹{np.std(monthly_pnls):,.0f}\n\n")
                
                # Best performing months
                f.write("🏆 BEST PERFORMING MONTHS (Top 10):\n")
                top_months = sorted(self.monthly_metrics, key=lambda x: x.total_pnl, reverse=True)[:10]
                for i, month in enumerate(top_months, 1):
                    f.write(f"{i:2d}. {month.month}: ₹{month.total_pnl:,.0f}\n")
                f.write("\n")
                
                # Worst performing months
                f.write("📉 WORST PERFORMING MONTHS (Bottom 5):\n")
                worst_months = sorted(self.monthly_metrics, key=lambda x: x.total_pnl)[:5]
                for i, month in enumerate(worst_months, 1):
                    f.write(f"{i}. {month.month}: ₹{month.total_pnl:,.0f}\n")

# Main execution
def main():
    """Main execution function"""
    print("📊 ENHANCED_DAY_HIGH_LOW DETAILED ANALYSIS")
    print("=" * 60)
    print("🔍 Comprehensive analysis with daily metrics")
    print("📈 Real historical data only - no simulated data")
    print("📊 Daily drawdowns, ROI, and monthly performance")
    print("=" * 60)
    
    try:
        # Initialize analyzer
        analyzer = EnhancedDayHighLowAnalyzer()
        
        # Run detailed analysis
        analyzer.run_detailed_analysis()
        
        print("✅ Detailed analysis completed!")
        print("📁 Reports generated in: reports/")
        print("📊 Check the following files:")
        print("   - enhanced_day_high_low_detailed_*.txt")
        print("   - daily_metrics_*.csv")
        print("   - monthly_metrics_*.csv")
        print("   - yearly_metrics_*.csv")
        print("   - enhanced_day_high_low_summary_*.txt")
        
        return 0
        
    except Exception as e:
        logger.error(f"🚨 Analysis error: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
