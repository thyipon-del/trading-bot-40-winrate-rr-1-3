"""
INTERNAL FLOW STRATEGY
======================
Win Rate: 40-60%
Risk/Reward: 1:3 to 1:5
Timeframe: M15 (15 minutes)

Logic:
- H4 Trend Filter (Sovereign Bias)
- H1 EMA20 Pullback (Value Area)
- M15 CHoCH Trigger (Change of Character)
- TP: Next H1 Level OR 1:3 RR
- SL: Swing Low/High
- Hard 20:00 UTC Exit (No overnight)
"""

import numpy as np
from datetime import datetime, timedelta
import pytz

class InternalFlowStrategy:
    """Internal Flow Trading Strategy"""
    
    def __init__(self, wallet_name, initial_balance, risk_pct=0.01, min_lot=0.01):
        self.wallet_name = wallet_name
        self.balance = initial_balance
        self.initial_balance = initial_balance
        self.risk_pct = risk_pct
        self.min_lot = min_lot
        self.trades = []
        self.stats = {
            'total_trades': 0,
            'wins': 0,
            'losses': 0,
            'time_stops': 0,
            'total_pnl': 0,
            'avg_win': 0,
            'avg_loss': 0,
            'avg_rrr': 0,
            'win_rate': 0
        }
    
    def calculate_ema(self, prices, period=20):
        """Calculate EMA"""
        if len(prices) < period:
            return None
        ema = np.mean(prices[-period:])  # Simple for now
        return ema
    
    def find_swing_high(self, candles, lookback=20):
        """Find swing high"""
        if len(candles) < lookback:
            return None
        highs = [c['high'] for c in candles[-lookback:]]
        return max(highs)
    
    def find_swing_low(self, candles, lookback=20):
        """Find swing low"""
        if len(candles) < lookback:
            return None
        lows = [c['low'] for c in candles[-lookback:]]
        return min(lows)
    
    def detect_choch(self, candles_m15):
        """
        Detect Change of Character (CHoCH) on M15
        CHoCH = Break of previous swing high/low
        """
        if len(candles_m15) < 5:
            return None, None
        
        # Get last 50 candles
        recent = candles_m15[-50:]
        
        # Find HH/HL or LH/LL pattern
        swing_high = self.find_swing_high(recent, 20)
        swing_low = self.find_swing_low(recent, 20)
        
        last_close = recent[-1]['close']
        last_high = recent[-1]['high']
        last_low = recent[-1]['low']
        
        # Bullish CHoCH: Break above previous swing high
        if last_high > swing_high:
            return 'bullish', swing_high
        
        # Bearish CHoCH: Break below previous swing low
        if last_low < swing_low:
            return 'bearish', swing_low
        
        return None, None
    
    def detect_h4_trend(self, candles_h4):
        """
        Detect H4 Trend Filter
        Bullish: HH/HL (Higher High / Higher Low)
        Bearish: LH/LL (Lower High / Lower Low)
        """
        if len(candles_h4) < 5:
            return 'neutral'
        
        recent = candles_h4[-5:]
        
        # Compare last 2 swings
        swing_high_1 = max([c['high'] for c in recent[-3:-1]])
        swing_high_2 = max([c['high'] for c in recent[-5:-3]]) if len(recent) >= 5 else swing_high_1
        
        swing_low_1 = min([c['low'] for c in recent[-3:-1]])
        swing_low_2 = min([c['low'] for c in recent[-5:-3]]) if len(recent) >= 5 else swing_low_1
        
        # Bullish: HH and HL
        if swing_high_1 > swing_high_2 and swing_low_1 > swing_low_2:
            return 'bullish'
        
        # Bearish: LH and LL
        if swing_high_1 < swing_high_2 and swing_low_1 < swing_low_2:
            return 'bearish'
        
        return 'neutral'
    
    def detect_h1_pullback(self, candles_h1):
        """
        Detect H1 EMA20 Pullback
        Entry when price pulls back to EMA20
        """
        if len(candles_h1) < 25:
            return False, None
        
        # Calculate EMA20
        closes = np.array([c['close'] for c in candles_h1])
        ema20 = self.calculate_ema(closes, 20)
        
        if ema20 is None:
            return False, None
        
        last_close = closes[-1]
        last_high = candles_h1[-1]['high']
        last_low = candles_h1[-1]['low']
        
        # Pullback to EMA20 (within 10 pips)
        pullback_tolerance = ema20 * 0.001  # 0.1% tolerance
        
        if abs(last_close - ema20) < pullback_tolerance:
            return True, ema20
        
        return False, ema20
    
    def calculate_next_h1_level(self, candles_h1, direction):
        """Calculate next H1 resistance/support level"""
        if len(candles_h1) < 20:
            return None
        
        if direction == 'bullish':
            # Find resistance above current price
            highs = [c['high'] for c in candles_h1[-20:]]
            current = candles_h1[-1]['close']
            resistances = [h for h in highs if h > current]
            return max(resistances) if resistances else None
        else:
            # Find support below current price
            lows = [c['low'] for c in candles_h1[-20:]]
            current = candles_h1[-1]['close']
            supports = [l for l in lows if l < current]
            return min(supports) if supports else None
    
    def generate_signal(self, candles_h4, candles_h1, candles_m15, timestamp):
        """
        Generate trading signal based on Internal Flow logic
        
        Returns:
        {
            'direction': 'LONG' or 'SHORT',
            'entry': entry_price,
            'sl': stop_loss,
            'tp': take_profit,
            'rrr': risk_reward_ratio,
            'risk': risk_amount,
            'lot_size': lot_size,
            'h4_trend': trend,
            'target_type': 'H1_LEVEL' or 'RR_TARGET',
            'choch_level': choch_level,
            'ema20': ema20_value,
            'rejected': False/True,
            'reject_reason': reason
        }
        """
        
        # Step 1: Check H4 Trend Filter
        h4_trend = self.detect_h4_trend(candles_h4)
        if h4_trend == 'neutral':
            return None  # No signal if trend is neutral
        
        # Step 2: Check H1 EMA20 Pullback
        pullback_detected, ema20 = self.detect_h1_pullback(candles_h1)
        if not pullback_detected:
            return None  # No pullback to EMA20
        
        # Step 3: Check M15 CHoCH Trigger
        choch_direction, choch_level = self.detect_choch(candles_m15)
        if choch_direction is None:
            return None  # No CHoCH detected
        
        # Step 4: Align with H4 trend
        if h4_trend == 'bullish' and choch_direction != 'bullish':
            return None
        if h4_trend == 'bearish' and choch_direction != 'bearish':
            return None
        
        # Step 5: Calculate Entry, SL, TP
        entry_price = candles_m15[-1]['close']
        
        if choch_direction == 'bullish':
            direction = 'LONG'
            sl = self.find_swing_low(candles_m15, 20)
            risk = entry_price - sl
        else:
            direction = 'SHORT'
            sl = self.find_swing_high(candles_m15, 20)
            risk = sl - entry_price
        
        # Calculate TP: Use H1 level or 1:3 RR
        h1_target = self.calculate_next_h1_level(candles_h1, choch_direction)
        
        if direction == 'LONG':
            tp_rr = entry_price + (risk * 3)  # 1:3 RR
            if h1_target and h1_target > tp_rr:
                tp = h1_target
                target_type = 'H1_LEVEL'
            else:
                tp = tp_rr
                target_type = 'RR_TARGET'
        else:
            tp_rr = entry_price - (risk * 3)  # 1:3 RR
            if h1_target and h1_target < tp_rr:
                tp = h1_target
                target_type = 'H1_LEVEL'
            else:
                tp = tp_rr
                target_type = 'RR_TARGET'
        
        # Calculate Risk/Reward Ratio
        if risk > 0:
            reward = abs(tp - entry_price)
            rrr = reward / risk
        else:
            rrr = 0
        
        # Reject if RR < 1:1
        if rrr < 1.0:
            return {
                'rejected': True,
                'reject_reason': f'Low RR: {rrr:.2f}:1 (min 1:1)',
                'rrr': rrr
            }
        
        # Calculate lot size based on risk
        risk_amount = self.balance * self.risk_pct
        if risk > 0:
            lot_size = max(self.min_lot, risk_amount / (risk * 10))  # Assuming 10 points per pip
        else:
            lot_size = self.min_lot
        
        # Check if SL is too wide for wallet
        if risk_amount > (self.balance * 0.05):  # SL > 5% of balance
            return {
                'rejected': True,
                'reject_reason': f'SL too wide: {risk:.2f} points (risk > 5%)',
                'rrr': rrr
            }
        
        return {
            'direction': direction,
            'entry': entry_price,
            'sl': sl,
            'tp': tp,
            'rrr': rrr,
            'risk': risk,
            'lot_size': lot_size,
            'h4_trend': h4_trend,
            'target_type': target_type,
            'choch_level': choch_level,
            'ema20': ema20,
            'rejected': False,
            'reject_reason': None
        }
    
    def execute_trade(self, signal, timestamp):
        """Execute trade based on signal"""
        trade = {
            'timestamp': timestamp,
            'direction': signal['direction'],
            'entry': signal['entry'],
            'sl': signal['sl'],
            'tp': signal['tp'],
            'lot_size': signal['lot_size'],
            'risk': signal['risk'],
            'rrr': signal['rrr'],
            'outcome': None,
            'exit_time': None,
            'exit_price': None,
            'pnl': 0,
            'exit_reason': None
        }
        
        self.trades.append(trade)
        return trade
    
    def simulate_trade_outcome(self, trade, future_candles):
        """Simulate trade outcome against future candles"""
        if len(future_candles) == 0:
            trade['outcome'] = 'OPEN'
            return
        
        entry = trade['entry']
        sl = trade['sl']
        tp = trade['tp']
        direction = trade['direction']
        
        # Check against future candles
        for candle in future_candles:
            current_time = candle['time'] if isinstance(candle['time'], datetime) else datetime.fromtimestamp(candle['time'])
            
            # Hard stop at 20:00 UTC
            if current_time.hour == 20 and current_time.minute == 0:
                trade['outcome'] = 'TIME_STOP'
                trade['exit_time'] = current_time
                trade['exit_price'] = candle['close']
                trade['exit_reason'] = 'EOD 20:00 UTC'
                
                if direction == 'LONG':
                    trade['pnl'] = (trade['exit_price'] - entry) * trade['lot_size']
                else:
                    trade['pnl'] = (entry - trade['exit_price']) * trade['lot_size']
                break
            
            # Check for SL hit
            if direction == 'LONG':
                if candle['low'] <= sl:
                    trade['outcome'] = 'LOSS'
                    trade['exit_time'] = current_time
                    trade['exit_price'] = sl
                    trade['exit_reason'] = 'Stop Loss Hit'
                    trade['pnl'] = -(trade['risk'] * trade['lot_size'])
                    self.stats['losses'] += 1
                    break
            else:
                if candle['high'] >= sl:
                    trade['outcome'] = 'LOSS'
                    trade['exit_time'] = current_time
                    trade['exit_price'] = sl
                    trade['exit_reason'] = 'Stop Loss Hit'
                    trade['pnl'] = -(trade['risk'] * trade['lot_size'])
                    self.stats['losses'] += 1
                    break
            
            # Check for TP hit
            if direction == 'LONG':
                if candle['high'] >= tp:
                    trade['outcome'] = 'WIN'
                    trade['exit_time'] = current_time
                    trade['exit_price'] = tp
                    trade['exit_reason'] = 'Take Profit Hit'
                    trade['pnl'] = (trade['risk'] * trade['rrr'] * trade['lot_size'])
                    self.stats['wins'] += 1
                    break
            else:
                if candle['low'] <= tp:
                    trade['outcome'] = 'WIN'
                    trade['exit_time'] = current_time
                    trade['exit_price'] = tp
                    trade['exit_reason'] = 'Take Profit Hit'
                    trade['pnl'] = (trade['risk'] * trade['rrr'] * trade['lot_size'])
                    self.stats['wins'] += 1
                    break
        
        # Update balance
        self.balance += trade['pnl']
        
        # Update stats
        if trade['outcome'] in ['WIN', 'LOSS']:
            self.stats['total_trades'] += 1
            self.stats['total_pnl'] += trade['pnl']
        elif trade['outcome'] == 'TIME_STOP':
            self.stats['total_trades'] += 1
            self.stats['time_stops'] += 1
            self.stats['total_pnl'] += trade['pnl']
    
    def get_stats(self):
        """Get strategy statistics"""
        total = self.stats['total_trades']
        
        if total > 0:
            self.stats['win_rate'] = (self.stats['wins'] / total) * 100
            
            # Calculate average win/loss
            win_trades = [t for t in self.trades if t['outcome'] == 'WIN']
            loss_trades = [t for t in self.trades if t['outcome'] == 'LOSS']
            
            if win_trades:
                self.stats['avg_win'] = sum([t['pnl'] for t in win_trades]) / len(win_trades)
            if loss_trades:
                self.stats['avg_loss'] = sum([t['pnl'] for t in loss_trades]) / len(loss_trades)
            
            # Calculate average RRR
            valid_trades = [t for t in self.trades if t['rrr'] > 0]
            if valid_trades:
                self.stats['avg_rrr'] = sum([t['rrr'] for t in valid_trades]) / len(valid_trades)
        
        return self.stats
