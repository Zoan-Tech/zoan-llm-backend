"""
Tools for the Hyperliquid Trading Agent.
Provides functionality to open and close market trades on Hyperliquid testnet.
"""
from langchain.tools import tool
from model.completion import AgentKYA
from model.graph import Action, InterruptObject
from langchain_core.runnables.config import ensure_config
from langgraph.types import interrupt
from config.logging import get_logger
from typing import Optional, Literal

from hyperliquid.info import Info
from hyperliquid.exchange import Exchange
from hyperliquid.utils import constants

logger = get_logger()


# @tool
# def open_market_trade(
#     symbol: str,
#     is_buy: bool,
#     size: float,
#     reduce_only: bool = False,
#     limit_price: Optional[float] = None,
#     stop_loss_price: Optional[float] = None,
#     take_profit_price: Optional[float] = None,
# ):
#     """
#     Open a market trade position on Hyperliquid testnet.
    
#     This tool allows opening long or short positions with optional risk management parameters.
    
#     Args:
#         symbol: Trading pair symbol (e.g., "BTC", "ETH", "SOL")
#         is_buy: True for long position, False for short position
#         size: Position size in base currency units (e.g., 0.1 BTC)
#         reduce_only: If True, order can only reduce existing position (default: False)
#         limit_price: Optional limit price for the order. If None, market order is used
#         stop_loss_price: Optional stop loss price to automatically close losing positions
#         take_profit_price: Optional take profit price to automatically close profitable positions
    
#     Returns:
#         str: Result message indicating success or rejection
        
#     Examples:
#         - Open long 0.1 BTC at market: open_market_trade("BTC", True, 0.1)
#         - Open short 1 ETH with stop loss: open_market_trade("ETH", False, 1.0, stop_loss_price=3500)
#         - Open long with limit and TP/SL: open_market_trade("SOL", True, 10, limit_price=100, stop_loss_price=95, take_profit_price=110)
#     """
#     config = ensure_config()
#     configurable = config.get('configurable', {})
#     user_info: Optional[AgentKYA] = configurable.get('agent_kya', {}).get("Hyperliquid Trading Agent")
#     if not user_info:
#         return "Error: User information for Hyperliquid Trading Agent not found in configuration."
    
#     wallet_private_key = user_info.wallet_private_key.get_secret_value()
    
#     # Create user-friendly message
#     position_type = "long" if is_buy else "short"
#     order_type_str = f"limit order at ${limit_price}" if limit_price else "market order"
#     risk_mgmt = []
#     if stop_loss_price:
#         risk_mgmt.append(f"SL: ${stop_loss_price}")
#     if take_profit_price:
#         risk_mgmt.append(f"TP: ${take_profit_price}")
#     risk_mgmt_str = f" ({', '.join(risk_mgmt)})" if risk_mgmt else ""
    
#     message = (
#         f"Open {position_type} position on {symbol}\n"
#         f"Size: {size} {symbol}\n"
#         f"Order type: {order_type_str}{risk_mgmt_str}\n"
#         f"Platform: Hyperliquid Testnet\n\n"
#         f"Do you approve this trade?"
#     )
    
#     interrupt_obj = InterruptObject(
#         action_name="open_market_trade",
#         message=message,
#         requires_signature=False,
#     )
    
#     logger.info(f"[HyperliquidAgent] Requesting approval for open_market_trade: {interrupt_obj.model_dump(exclude_none=True)}")
    
#     # Request user approval with interrupt
#     response = interrupt(interrupt_obj.model_dump(exclude_none=True))
    
#     if response.get("action") == Action.REJECTED.value:
#         return f"User rejected the open {position_type} position request for {symbol}."
    
#     if response.get("action") == Action.APPROVED.value:
#         try:
#             # Initialize Hyperliquid Exchange with private key (testnet)
#             exchange = Exchange(
#                 wallet=None,
#                 base_url=constants.TESTNET_API_URL,
#                 account_address=None,
#             )
            
#             # Set the wallet from private key
#             from eth_account import Account
#             account = Account.from_key(wallet_private_key)
#             exchange.wallet = account
#             exchange.account_address = account.address
            
#             logger.info(f"[HyperliquidAgent] Executing trade on Hyperliquid testnet: {symbol} {position_type} {size}")
            
#             # Prepare order parameters
#             is_buy_order = is_buy
            
#             # Place the order
#             if limit_price:
#                 # Limit order with GTC (Good til Cancel)
#                 order_type = {"limit": {"tif": "Gtc"}}
#                 order_result = exchange.order(
#                     symbol,
#                     is_buy_order,
#                     size,
#                     limit_price,
#                     order_type,
#                     reduce_only=reduce_only,
#                 )
#             else:
#                 # Market order - use limit with IOC (Immediate or Cancel) and slippage price
#                 info = Info(constants.TESTNET_API_URL)
#                 mid_price = info.all_mids().get(symbol)
#                 if not mid_price:
#                     return f"Error: Could not fetch market price for {symbol}"
                
#                 # Convert to float as API returns string
#                 mid_price = float(mid_price)
                
#                 # Use a price with significant slippage tolerance for market order
#                 slippage_price = mid_price * 1.05 if is_buy else mid_price * 0.95
                
#                 # Round to 5 significant figures for price precision
#                 from math import log10, floor
#                 if slippage_price > 0:
#                     sig_figs = 5
#                     magnitude = floor(log10(abs(slippage_price)))
#                     slippage_price = round(slippage_price, sig_figs - int(magnitude) - 1)
                
#                 logger.info(f"[HyperliquidAgent] Market order: mid_price={mid_price}, slippage_price={slippage_price}")
                
#                 # Use IOC (Immediate or Cancel) for market-like behavior
#                 order_type = {"limit": {"tif": "Ioc"}}
#                 order_result = exchange.order(
#                     symbol,
#                     is_buy_order,
#                     size,
#                     slippage_price,
#                     order_type,
#                     reduce_only=reduce_only,
#                 )
            
#             logger.info(f"[HyperliquidAgent] Order result: {order_result}")
            
#             # Handle SL/TP if provided
#             if stop_loss_price or take_profit_price:
#                 # Note: Hyperliquid handles SL/TP via trigger orders
#                 # This is a simplified implementation
#                 logger.info(f"[HyperliquidAgent] SL/TP orders would be placed here")
            
#             # Return the raw order result
#             return str(order_result)
                
#         except Exception as e:
#             logger.error(f"[HyperliquidAgent] Error executing trade: {str(e)}", exc_info=True)
#             return f"❌ Error executing trade: {str(e)}"
    
#     if response.get("action") == Action.EDITED.value:
#         edited_size = response.get("size", size)
#         edited_limit_price = response.get("limit_price")
#         return f"User edited the order. New size: {edited_size}, New limit price: {edited_limit_price}. Please resubmit with updated parameters."
    
#     return f"Unexpected response action: {response.get('action')}"

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
    user_info: Optional[AgentKYA] = configurable.get('agent_kya', {}).get("Hyperliquid Trading Agent")
    if not user_info:
        return "Error: User information for Hyperliquid Trading Agent not found in configuration."
    
    wallet_private_key = user_info.wallet_private_key.get_secret_value()
    
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
            info = Info(constants.TESTNET_API_URL)
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
    user_info: Optional[AgentKYA] = configurable.get('agent_kya', {}).get("Hyperliquid Trading Agent")
    if not user_info:
        return "Error: User information for Hyperliquid Trading Agent not found in configuration."
    
    wallet_private_key = user_info.wallet_private_key.get_secret_value()
    
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
def close_trade(
    symbol: str,
    size: Optional[float] = None,
    close_type: Literal["market", "limit"] = "market",
    limit_price: Optional[float] = None,
):
    """
    Close an existing position on Hyperliquid testnet.
    
    This tool closes open positions (not pending orders). To cancel pending orders, use cancel_order instead.
    
    Args:
        symbol: Trading pair symbol (e.g., "BTC", "ETH", "SOL")
        size: Position size to close. If None, closes entire position
        close_type: "market" for immediate closure, "limit" for limit order closure
        limit_price: Required if close_type is "limit". Price at which to close the position
    
    Returns:
        str: Result message indicating success or rejection
        
    Examples:
        - Close entire BTC position at market: close_trade("BTC")
        - Close 0.5 ETH at market: close_trade("ETH", size=0.5)
        - Close SOL position with limit: close_trade("SOL", close_type="limit", limit_price=105)
    """
    config = ensure_config()
    configurable = config.get('configurable', {})
    user_info: Optional[AgentKYA] = configurable.get('agent_kya', {}).get("Hyperliquid Trading Agent")
    if not user_info:
        return "Error: User information for Hyperliquid Trading Agent not found in configuration."
    
    wallet_private_key = user_info.wallet_private_key.get_secret_value()
    
    # Validate limit_price if close_type is limit
    if close_type == "limit" and not limit_price:
        return "Error: limit_price is required when close_type is 'limit'"
    
    # Construct message strings
    size_str = f"{size} {symbol}" if size else f"entire {symbol} position"
    price_str = f" at limit price ${limit_price}" if limit_price else " at market price"
    
    # Create user-friendly message
    message = (
        f"Close {size_str}{price_str}\n"
        f"Platform: Hyperliquid Testnet\n\n"
        f"Do you approve closing this position?"
    )
    
    interrupt_obj = InterruptObject(
        action_name="close_trade",
        message=message,
        requires_signature=False,
    )
    
    # Request user approval with interrupt
    response = interrupt(interrupt_obj.model_dump(exclude_none=True))
    
    if response.get("action") == Action.REJECTED.value:
        return f"User rejected the close position request for {symbol}."
    
    if response.get("action") == Action.APPROVED.value:
        try:
            # Initialize Hyperliquid Exchange with private key (testnet)
            exchange = Exchange(
                wallet=None,
                base_url=constants.TESTNET_API_URL,
                account_address=None,
            )
            
            # Set the wallet from private key
            from eth_account import Account
            account = Account.from_key(wallet_private_key)
            exchange.wallet = account
            exchange.account_address = account.address
            
            # Get current position to determine close direction
            info = Info(constants.TESTNET_API_URL)
            user_state = info.user_state(account.address)
            
            # Find the position for this symbol
            position_info = None
            for position in user_state.get("assetPositions", []):
                if position.get("position", {}).get("coin") == symbol:
                    position_info = position.get("position")
                    break
            
            if not position_info:
                return f"❌ No open position found for {symbol}"
            
            current_size = float(position_info.get("szi", 0))
            if current_size == 0:
                return f"❌ No open position found for {symbol}"
            
            # Determine close size and direction
            close_size = abs(size) if size else abs(current_size)
            is_closing_long = current_size > 0
            is_buy_to_close = not is_closing_long  # Buy to close short, sell to close long
            
            # Execute close order
            if close_type == "limit" and limit_price:
                # Limit order to close with GTC
                order_type = {"limit": {"tif": "Gtc"}}
                order_result = exchange.order(
                    symbol,
                    is_buy_to_close,
                    close_size,
                    limit_price,
                    order_type,
                    reduce_only=True,
                )
            else:
                # Market order to close - use limit with IOC
                mid_price = info.all_mids().get(symbol)
                if not mid_price:
                    return f"Error: Could not fetch market price for {symbol}"
                
                # Convert to float as API returns string
                mid_price = float(mid_price)
                
                # Use a price with slippage tolerance for market order
                slippage_price = mid_price * 1.05 if is_buy_to_close else mid_price * 0.95
                
                # Round to 5 significant figures for price precision
                from math import log10, floor
                if slippage_price > 0:
                    sig_figs = 5
                    magnitude = floor(log10(abs(slippage_price)))
                    slippage_price = round(slippage_price, sig_figs - int(magnitude) - 1)
                
                # Use IOC (Immediate or Cancel) for market-like behavior
                order_type = {"limit": {"tif": "Ioc"}}
                order_result = exchange.order(
                    symbol,
                    is_buy_to_close,
                    close_size,
                    slippage_price,
                    order_type,
                    reduce_only=True,
                )
            
            # Return the raw order result
            return str(order_result)
                
        except Exception as e:
            logger.error(f"[HyperliquidAgent] Error closing position: {str(e)}", exc_info=True)
            return f"❌ Error closing position: {str(e)}"
    
    if response.get("action") == Action.EDITED.value:
        edited_size = response.get("size")
        edited_limit_price = response.get("limit_price")
        return f"User edited the close order. New size: {edited_size}, New limit price: {edited_limit_price}. Please resubmit with updated parameters."
    
    return f"Unexpected response action: {response.get('action')}"


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
    user_info: Optional[AgentKYA] = configurable.get('agent_kya', {}).get("Hyperliquid Trading Agent")
    if not user_info:
        return "Error: User information for Hyperliquid Trading Agent not found in configuration."
    
    wallet_private_key = user_info.wallet_private_key.get_secret_value()
    
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
