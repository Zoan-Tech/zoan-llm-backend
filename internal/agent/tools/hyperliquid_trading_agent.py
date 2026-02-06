"""
Tools for the Hyperliquid Trading Agent.
Provides functionality to open and close market trades on Hyperliquid testnet.
"""
from langchain.tools import tool
from model.completion import AgentKYA
from langchain_core.runnables.config import ensure_config
from config.logging import get_logger
from typing import Optional, Literal

from hyperliquid.info import Info
from hyperliquid.exchange import Exchange
from hyperliquid.utils import constants

logger = get_logger()

info = Info(constants.TESTNET_API_URL, skip_ws=True)
AGENT_NAME = "Hyperliquid Trading Agent"

@tool
def place_limit_order(
    symbol: str,
    is_buy: bool,
    size: float,
    limit_price: Optional[float] = None,
    time_in_force: Literal["Alo", "Ioc", "Gtc"] = "Gtc",
    reduce_only: bool = False,
):
    """
    Place a limit order on Hyperliquid testnet.
    
    This is the primary tool for opening positions with limit orders. Supports different
    time-in-force options to control order behavior.
    
    Args:
        symbol: Trading pair symbol (e.g., "BTC", "ETH", "SOL")
        is_buy: True for long/buy, False for short/sell
        size: Position size in base currency units (e.g., 0.1 BTC)
        limit_price: Price at which to execute. If None and tif="Ioc", fetches market price with slippage
        time_in_force: Order duration type:
            - "Gtc" (Good til Cancel): Order stays until filled or cancelled
            - "Ioc" (Immediate or Cancel): Execute immediately, cancel unfilled portion (use for market orders)
            - "Alo" (Add Liquidity Only): Order must be maker (not taker)
        reduce_only: If True, order can only reduce existing position
    
    Returns:
        str: Result message with order status
        
    Examples:
        - Market order (IOC): place_limit_order("BTC", True, 0.1, time_in_force="Ioc")
        - Limit order: place_limit_order("ETH", True, 1.0, 3000, "Gtc")
        - Maker-only: place_limit_order("SOL", False, 10, 105, "Alo")
    """
    config = ensure_config()
    configurable = config.get('configurable', {})
    agent_wallet: Optional[AgentKYA] = configurable.get('agent_kya', {}).get(AGENT_NAME)
    if not agent_wallet:
        return "Error: User information for Hyperliquid Trading Agent not found in configuration."
    
    wallet_private_key = agent_wallet.wallet_private_key.get_secret_value()
    
    try:
        # Initialize Hyperliquid Exchange
        exchange = Exchange(
            wallet=None,
            base_url=constants.TESTNET_API_URL,
            account_address=None,
        )
        
        from eth_account import Account
        account = Account.from_key(wallet_private_key)
        exchange.wallet = account
        exchange.account_address = account.address
        
        # Handle market order case (IOC without price)
        if time_in_force == "Ioc" and not limit_price:
            mid_price = info.all_mids().get(symbol)
            if not mid_price:
                return f"❌ Could not fetch market price for {symbol}"
            
            mid_price = float(mid_price)
            # Apply slippage tolerance for market execution
            limit_price = mid_price * 1.05 if is_buy else mid_price * 0.95
            
            # Round to 5 significant figures
            from math import log10, floor
            if limit_price > 0:
                sig_figs = 5
                magnitude = floor(log10(abs(limit_price)))
                limit_price = round(limit_price, sig_figs - int(magnitude) - 1)
        
        if not limit_price:
            return "❌ limit_price is required when time_in_force is not 'Ioc'"
        
        position_type = "long" if is_buy else "short"
        order_type_desc = "market" if time_in_force == "Ioc" else "limit"
        
        # Build order type
        order_type = {"limit": {"tif": time_in_force}}
        
        order_result = exchange.order(
            symbol,
            is_buy,
            size,
            limit_price,
            order_type,
            reduce_only=reduce_only,
        )
        
        return f"✅ {order_type_desc.capitalize()} order placed: {order_result}"
        
    except Exception as e:
        logger.error(f"[HyperliquidAgent] Error placing limit order: {str(e)}", exc_info=True)
        return f"❌ Error placing order: {str(e)}"


@tool
def place_trigger_order(
    symbol: str,
    is_buy: bool,
    size: float,
    trigger_price: float,
    is_market: bool = True,
    order_type: Literal["tp", "sl"] = "tp",
    reduce_only: bool = True,
):
    """
    Place a trigger order (stop loss or take profit) on Hyperliquid testnet.
    
    Trigger orders execute automatically when price reaches the trigger level. Used for
    risk management and profit taking.
    
    Args:
        symbol: Trading pair symbol (e.g., "BTC", "ETH", "SOL")
        is_buy: True to buy, False to sell when triggered
        size: Position size to execute when triggered
        trigger_price: Price level that activates the order
        is_market: If True, executes at market when triggered. If False, executes as limit at trigger_price
        order_type: "tp" for take profit, "sl" for stop loss
        reduce_only: If True, order can only reduce existing position (default: True for TP/SL)
    
    Returns:
        str: Result message with order status
        
    Examples:
        - Stop loss for long: place_trigger_order("BTC", False, 0.1, 43500, True, "sl")
        - Take profit for short: place_trigger_order("ETH", True, 1.0, 3000, True, "tp")
        - Limit TP: place_trigger_order("SOL", False, 10, 110, False, "tp")
    """
    config = ensure_config()
    configurable = config.get('configurable', {})
    agent_wallet: Optional[AgentKYA] = configurable.get('agent_kya', {}).get(AGENT_NAME)
    if not agent_wallet:
        return "Error: User information for Hyperliquid Trading Agent not found in configuration."
    
    wallet_private_key = agent_wallet.wallet_private_key.get_secret_value()
    
    try:
        # Initialize Hyperliquid Exchange
        exchange = Exchange(
            wallet=None,
            base_url=constants.TESTNET_API_URL,
            account_address=None,
        )
        
        from eth_account import Account
        account = Account.from_key(wallet_private_key)
        exchange.wallet = account
        exchange.account_address = account.address
        
        order_type_str = "Take Profit" if order_type == "tp" else "Stop Loss"
        execution_type = "market" if is_market else "limit"
        
        # Build trigger order type
        trigger_order_type = {
            "trigger": {
                "triggerPx": float(trigger_price),
                "isMarket": is_market,
                "tpsl": order_type
            }
        }
        
        order_result = exchange.order(
            symbol,
            is_buy,
            size,
            trigger_price,
            trigger_order_type,
            reduce_only=reduce_only,
        )
        
        return f"✅ {order_type_str} set at ${trigger_price} ({execution_type}): {order_result}"
        
    except Exception as e:
        logger.error(f"[HyperliquidAgent] Error placing {order_type_str}: {str(e)}", exc_info=True)
        return f"❌ Failed to set {order_type_str}: {str(e)}"

@tool
def cancel_order(
    symbol: str,
    order_id: int,
):
    """
    Cancel a pending order on Hyperliquid testnet.
    
    This tool cancels open orders that haven't been filled yet (limit orders, trigger orders).
    To close existing positions, use close_trade instead.
    
    Args:
        symbol: Trading pair symbol (e.g., "BTC", "ETH", "SOL")
        order_id: The order ID (oid) of the order to cancel
    
    Returns:
        str: Result message indicating success or failure
        
    Examples:
        - Cancel order: cancel_order("BTC", 12345)
        - Cancel stop loss: cancel_order("ETH", 67890)
    """
    config = ensure_config()
    configurable = config.get('configurable', {})
    agent_wallet: Optional[AgentKYA] = configurable.get('agent_kya', {}).get(AGENT_NAME)
    if not agent_wallet:
        return "Error: User information for Hyperliquid Trading Agent not found in configuration."
    
    wallet_private_key = agent_wallet.wallet_private_key.get_secret_value()
    
    try:
        # Initialize Hyperliquid Exchange
        exchange = Exchange(
            wallet=None,
            base_url=constants.TESTNET_API_URL,
            account_address=None,
        )
        
        from eth_account import Account
        account = Account.from_key(wallet_private_key)
        exchange.wallet = account
        exchange.account_address = account.address
        
        # Cancel the order
        cancel_result = exchange.cancel(symbol, order_id)
        
        return f"✅ Order {order_id} canceled: {cancel_result}"
        
    except Exception as e:
        logger.error(f"[HyperliquidAgent] Error canceling order: {str(e)}", exc_info=True)
        return f"❌ Failed to cancel order: {str(e)}"


@tool
def get_user_state(
    symbol: Optional[str] = None,
):
    """
    Get user account state and positions on Hyperliquid testnet.
    
    Retrieves account information including margin, equity, and open positions.
    Can filter to show only a specific symbol's position.
    
    Args:
        symbol: Trading pair symbol (e.g., "BTC", "ETH", "SOL"). 
                If None, returns all positions and full account info.
                If provided, returns only that symbol's position.
    
    Returns:
        str: Account state information including positions, margin, and equity
        
    Examples:
        - Get all positions: get_user_state()
        - Get BTC position only: get_user_state("BTC")
    """
    config = ensure_config()
    configurable = config.get('configurable', {})
    # Get user main wallet address from configuration
    user_wallet_address = configurable.get('user_wallet_address')
    if not user_wallet_address:
        return "Error: User information for Hyperliquid Trading Agent not found in configuration."
    
    try:
        user_state = info.user_state(user_wallet_address)
        
        if symbol:
            # Filter for specific symbol
            positions = user_state.get("assetPositions", [])
            filtered_position = None
            for position in positions:
                if position.get("position", {}).get("coin") == symbol:
                    filtered_position = position.get("position")
                    break
            
            if not filtered_position:
                return f"📊 No open position found for {symbol}"
            
            # Format position info
            size = float(filtered_position.get("szi", 0))
            entry_price = filtered_position.get("entryPx", "N/A")
            unrealized_pnl = filtered_position.get("unrealizedPnl", "N/A")
            leverage = filtered_position.get("leverage", {})
            
            position_type = "Long" if size > 0 else "Short"
            
            return (
                f"📊 {symbol} Position:\n"
                f"  Type: {position_type}\n"
                f"  Size: {abs(size)}\n"
                f"  Entry Price: ${entry_price}\n"
                f"  Unrealized PnL: ${unrealized_pnl}\n"
                f"  Leverage: {leverage}"
            )
        else:
            # Return full account state
            margin_summary = user_state.get("marginSummary", {})
            account_value = margin_summary.get("accountValue", "N/A")
            total_margin_used = margin_summary.get("totalMarginUsed", "N/A")
            total_ntl_pos = margin_summary.get("totalNtlPos", "N/A")
            
            positions = user_state.get("assetPositions", [])
            active_positions = [p for p in positions if float(p.get("position", {}).get("szi", 0)) != 0]
            
            result = (
                f"📊 Account Overview:\n"
                f"  Account Value: ${account_value}\n"
                f"  Total Margin Used: ${total_margin_used}\n"
                f"  Total Notional Position: ${total_ntl_pos}\n\n"
            )
            
            if active_positions:
                result += f"📈 Open Positions ({len(active_positions)}):\n"
                for pos in active_positions:
                    p = pos.get("position", {})
                    coin = p.get("coin", "Unknown")
                    size = float(p.get("szi", 0))
                    entry_px = p.get("entryPx", "N/A")
                    unrealized_pnl = p.get("unrealizedPnl", "N/A")
                    pos_type = "Long" if size > 0 else "Short"
                    result += f"  • {coin}: {pos_type} {abs(size)} @ ${entry_px} (PnL: ${unrealized_pnl})\n"
            else:
                result += "📈 No open positions"
            
            return result
        
    except Exception as e:
        logger.error(f"[HyperliquidAgent] Error getting user state: {str(e)}", exc_info=True)
        return f"❌ Error getting user state: {str(e)}"


@tool
def get_open_orders(
    symbol: Optional[str] = None,
):
    """
    Get open (pending) orders on Hyperliquid testnet.
    
    Retrieves all unfilled orders including limit orders and trigger orders (TP/SL).
    Can filter to show only orders for a specific symbol.
    
    Args:
        symbol: Trading pair symbol (e.g., "BTC", "ETH", "SOL").
                If None, returns all pending orders.
                If provided, returns only orders for that symbol.
    
    Returns:
        str: List of open orders with details
        
    Examples:
        - Get all open orders: get_open_orders()
        - Get BTC orders only: get_open_orders("BTC")
    """
    config = ensure_config()
    configurable = config.get('configurable', {})
    user_wallet_address = configurable.get('user_wallet_address')
    if not user_wallet_address:
        return "Error: User information for Hyperliquid Trading Agent not found in configuration."
    
    try:
        open_orders = info.open_orders(user_wallet_address)
        
        if symbol:
            # Filter for specific symbol
            open_orders = [o for o in open_orders if o.get("coin") == symbol]
        
        if not open_orders:
            filter_msg = f" for {symbol}" if symbol else ""
            return f"📋 No open orders{filter_msg}"
        
        result = f"📋 Open Orders ({len(open_orders)}):\n"
        for order in open_orders:
            coin = order.get("coin", "Unknown")
            oid = order.get("oid", "N/A")
            side = "Buy" if order.get("side") == "B" else "Sell"
            size = order.get("sz", "N/A")
            limit_px = order.get("limitPx", "N/A")
            order_type = order.get("orderType", "Limit")
            
            result += (
                f"  • [{oid}] {coin}: {side} {size} @ ${limit_px} ({order_type})\n"
            )
        
        return result
        
    except Exception as e:
        logger.error(f"[HyperliquidAgent] Error getting open orders: {str(e)}", exc_info=True)
        return f"❌ Error getting open orders: {str(e)}"


@tool
def get_market_data(
    symbol: str,
):
    """
    Get current market data for a trading pair on Hyperliquid.
    
    Retrieves real-time market information including mid price, mark price,
    funding rate, and 24h volume.
    
    Args:
        symbol: Trading pair symbol (e.g., "BTC", "ETH", "SOL")
    
    Returns:
        str: Market data including price, funding rate, and volume
        
    Examples:
        - Get BTC market data: get_market_data("BTC")
        - Get ETH market data: get_market_data("ETH")
    """
    try:
        # Get mid price
        all_mids = info.all_mids()
        mid_price = all_mids.get(symbol)
        
        if not mid_price:
            return f"❌ Symbol {symbol} not found"
        
        # Get metadata for more details
        meta = info.meta()
        universe = meta.get("universe", [])
        
        asset_info = None
        for asset in universe:
            if asset.get("name") == symbol:
                asset_info = asset
                break
        
        # Get funding rate from user state context (publicly available)
        ctx = info.meta_and_asset_ctxs()
        asset_ctxs = ctx[1] if len(ctx) > 1 else []
        
        funding_rate = "N/A"
        mark_price = "N/A"
        open_interest = "N/A"
        volume_24h = "N/A"
        
        # Find the asset context for this symbol
        for i, asset in enumerate(universe):
            if asset.get("name") == symbol and i < len(asset_ctxs):
                asset_ctx = asset_ctxs[i]
                funding_rate = asset_ctx.get("funding", "N/A")
                mark_price = asset_ctx.get("markPx", "N/A")
                open_interest = asset_ctx.get("openInterest", "N/A")
                volume_24h = asset_ctx.get("dayNtlVlm", "N/A")
                break
        
        # Format funding rate as percentage
        if funding_rate != "N/A":
            funding_pct = float(funding_rate) * 100
            funding_display = f"{funding_pct:.4f}%"
        else:
            funding_display = "N/A"
        
        # Format volume
        if volume_24h != "N/A":
            vol = float(volume_24h)
            if vol >= 1_000_000_000:
                volume_display = f"${vol/1_000_000_000:.2f}B"
            elif vol >= 1_000_000:
                volume_display = f"${vol/1_000_000:.2f}M"
            else:
                volume_display = f"${vol:,.0f}"
        else:
            volume_display = "N/A"
        
        result = (
            f"📈 {symbol} Market Data:\n"
            f"  Mid Price: ${mid_price}\n"
            f"  Mark Price: ${mark_price}\n"
            f"  Funding Rate: {funding_display}\n"
            f"  Open Interest: ${open_interest}\n"
            f"  24h Volume: {volume_display}\n"
        )
        
        if asset_info:
            max_leverage = asset_info.get("maxLeverage", "N/A")
            result += f"  Max Leverage: {max_leverage}x\n"
        
        return result
        
    except Exception as e:
        logger.error(f"[HyperliquidAgent] Error getting market data: {str(e)}", exc_info=True)
        return f"❌ Error getting market data: {str(e)}"


@tool
def cancel_all_orders(
    symbol: Optional[str] = None,
):
    """
    Cancel all open orders on Hyperliquid testnet.
    
    Cancels all pending orders for a specific symbol or all symbols if not specified.
    
    Args:
        symbol: Trading pair symbol (e.g., "BTC", "ETH", "SOL").
                If None, cancels all orders across all symbols.
    
    Returns:
        str: Result message indicating success or failure
        
    Examples:
        - Cancel all BTC orders: cancel_all_orders("BTC")
        - Cancel all orders: cancel_all_orders()
    """
    config = ensure_config()
    configurable = config.get('configurable', {})
    agent_wallet: Optional[AgentKYA] = configurable.get('agent_kya', {}).get(AGENT_NAME)
    if not agent_wallet:
        return "Error: User information for Hyperliquid Trading Agent not found in configuration."
    
    wallet_private_key = agent_wallet.wallet_private_key.get_secret_value()
    
    try:
        from eth_account import Account
        account = Account.from_key(wallet_private_key)
        
        # Initialize Hyperliquid Exchange
        exchange = Exchange(
            wallet=None,
            base_url=constants.TESTNET_API_URL,
            account_address=None,
        )
        exchange.wallet = account
        exchange.account_address = account.address
        
        # Get all open orders
        open_orders = info.open_orders(account.address)
        
        if symbol:
            # Filter for specific symbol
            open_orders = [o for o in open_orders if o.get("coin") == symbol]
        
        if not open_orders:
            filter_msg = f" for {symbol}" if symbol else ""
            return f"📋 No open orders{filter_msg} to cancel"
        
        # Cancel each order
        cancelled_count = 0
        failed_count = 0
        
        for order in open_orders:
            coin = order.get("coin")
            oid = order.get("oid")
            try:
                exchange.cancel(coin, oid)
                cancelled_count += 1
            except Exception as e:
                logger.error(f"[HyperliquidAgent] Failed to cancel order {oid}: {str(e)}")
                failed_count += 1
        
        filter_msg = f" for {symbol}" if symbol else ""
        result = f"✅ Cancelled {cancelled_count} order(s){filter_msg}"
        if failed_count > 0:
            result += f"\n⚠️ Failed to cancel {failed_count} order(s)"
        
        return result
        
    except Exception as e:
        logger.error(f"[HyperliquidAgent] Error canceling all orders: {str(e)}", exc_info=True)
        return f"❌ Error canceling orders: {str(e)}"


@tool
def get_candles(
    symbol: str,
    timeframe: str = "1d",
    limit: int = 100,
):
    """
    Get historical candlestick (OHLCV) data for a trading pair on Hyperliquid.
    
    Retrieves historical price data in candlestick format for technical analysis.
    
    Args:
        symbol: Trading pair symbol (e.g., "BTC", "ETH", "SOL")
        timeframe: Candle interval. Options: "1m", "5m", "15m", "1h", "4h", "1d"
        limit: Number of candles to retrieve (default: 100, max: 5000)
    
    Returns:
        str: Candlestick data with OHLCV values
        
    Examples:
        - Get daily BTC candles: get_candles("BTC")
        - Get hourly ETH candles: get_candles("ETH", "1h", 50)
        - Get 15min SOL candles: get_candles("SOL", "15m", 200)
    """
    try:
        # Map timeframe to interval in seconds for time calculation
        timeframe_seconds = {
            "1m": 60,
            "5m": 300,
            "15m": 900,
            "1h": 3600,
            "4h": 14400,
            "1d": 86400,
        }
        
        interval_secs = timeframe_seconds.get(timeframe)
        if not interval_secs:
            return f"❌ Invalid timeframe '{timeframe}'. Valid options: 1m, 5m, 15m, 1h, 4h, 1d"
        
        # Limit the number of candles
        limit = min(limit, 5000)
        
        # Calculate start time based on limit and interval
        import time
        end_time = int(time.time() * 1000)  # Current time in milliseconds
        start_time = end_time - (limit * interval_secs * 1000)
        
        # Fetch candles from Hyperliquid - interval should be string like "1h", "1d"
        candles = info.candles_snapshot(symbol, timeframe, start_time, end_time)
        
        if not candles:
            return f"❌ No candle data found for {symbol}"
        
        # Format the response - show summary and recent candles
        total_candles = len(candles)
        
        # Calculate basic stats from candles
        closes = [float(c.get("c", 0)) for c in candles]
        highs = [float(c.get("h", 0)) for c in candles]
        lows = [float(c.get("l", 0)) for c in candles]
        volumes = [float(c.get("v", 0)) for c in candles]
        
        if closes:
            current_price = closes[-1]
            period_high = max(highs)
            period_low = min(lows)
            total_volume = sum(volumes)
            price_change = ((closes[-1] - closes[0]) / closes[0] * 100) if closes[0] > 0 else 0
        else:
            return f"❌ No valid candle data for {symbol}"
        
        # Format volume
        if total_volume >= 1_000_000_000:
            volume_display = f"${total_volume/1_000_000_000:.2f}B"
        elif total_volume >= 1_000_000:
            volume_display = f"${total_volume/1_000_000:.2f}M"
        else:
            volume_display = f"${total_volume:,.0f}"
        
        result = (
            f"📊 {symbol} Candles ({timeframe}, {total_candles} periods):\n\n"
            f"  Current Price: ${current_price:,.2f}\n"
            f"  Period High: ${period_high:,.2f}\n"
            f"  Period Low: ${period_low:,.2f}\n"
            f"  Price Change: {price_change:+.2f}%\n"
            f"  Total Volume: {volume_display}\n\n"
        )
        
        # Show last 5 candles
        result += "📈 Recent Candles (O/H/L/C/V):\n"
        recent_candles = candles[-5:] if len(candles) >= 5 else candles
        
        for candle in reversed(recent_candles):
            from datetime import datetime
            ts = candle.get("t", 0)
            dt = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M")
            o = float(candle.get("o", 0))
            h = float(candle.get("h", 0))
            l = float(candle.get("l", 0))
            c = float(candle.get("c", 0))
            v = float(candle.get("v", 0))
            
            change = "🟢" if c >= o else "🔴"
            result += f"  {change} {dt}: ${o:,.2f} / ${h:,.2f} / ${l:,.2f} / ${c:,.2f} (Vol: {v:,.2f})\n"
        
        return result
        
    except Exception as e:
        logger.error(f"[HyperliquidAgent] Error getting candles: {str(e)}", exc_info=True)
        return f"❌ Error getting candles: {str(e)}"


tools = [
    place_limit_order,
    place_trigger_order,
    cancel_order,
    get_user_state,
    get_open_orders,
    get_market_data,
    cancel_all_orders,
    get_candles,
]