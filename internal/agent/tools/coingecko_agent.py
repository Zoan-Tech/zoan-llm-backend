"""
Tools for the CoinGecko Agent.
Provides functionality to fetch global market trends, trending coins, and market cap data.
"""
from typing import Optional
from langchain.tools import tool
from config.logging import get_logger
import httpx

logger = get_logger()

COINGECKO_API_BASE_URL = "https://api.coingecko.com/api/v3"
DEFAULT_TIMEOUT = 30


def _make_coingecko_request(endpoint: str, params: Optional[dict] = None) -> dict:
    """
    Make a request to the CoinGecko API.
    
    Args:
        endpoint: API endpoint path
        params: Optional query parameters
        
    Returns:
        JSON response as dict
    """
    url = f"{COINGECKO_API_BASE_URL}/{endpoint}"
    
    try:
        response = httpx.get(url, params=params, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"CoinGecko API error: {e.response.status_code} - {e.response.text}")
        raise
    except Exception as e:
        logger.error(f"CoinGecko request failed: {str(e)}")
        raise


@tool
def get_global_market_data() -> str:
    """
    Get global cryptocurrency market data including total market cap, 
    total volume, bitcoin dominance, and market cap percentage changes.
    
    Returns:
        Global market overview including:
        - Total market cap across all cryptocurrencies
        - 24h trading volume
        - Bitcoin and Ethereum dominance percentages
        - Market cap change percentages (24h)
        - Number of active cryptocurrencies
        - Number of ongoing ICOs
    """
    try:
        data = _make_coingecko_request("global")
        global_data = data.get("data", {})
        
        # Format the response
        result = {
            "total_market_cap_usd": global_data.get("total_market_cap", {}).get("usd", 0),
            "total_volume_24h_usd": global_data.get("total_volume", {}).get("usd", 0),
            "market_cap_percentage": global_data.get("market_cap_percentage", {}),
            "market_cap_change_percentage_24h_usd": global_data.get("market_cap_change_percentage_24h_usd", 0),
            "active_cryptocurrencies": global_data.get("active_cryptocurrencies", 0),
            "ongoing_icos": global_data.get("ongoing_icos", 0),
            "ended_icos": global_data.get("ended_icos", 0),
            "markets": global_data.get("markets", 0),
            "updated_at": global_data.get("updated_at", 0),
        }
        
        # Format as readable string
        output = f"""📊 **Global Cryptocurrency Market Overview**

💰 **Total Market Cap**: ${result['total_market_cap_usd']:,.0f} USD
📈 **24h Volume**: ${result['total_volume_24h_usd']:,.0f} USD
📉 **24h Market Cap Change**: {result['market_cap_change_percentage_24h_usd']:.2f}%

🔝 **Market Dominance**:
- Bitcoin (BTC): {result['market_cap_percentage'].get('btc', 0):.2f}%
- Ethereum (ETH): {result['market_cap_percentage'].get('eth', 0):.2f}%

📊 **Market Stats**:
- Active Cryptocurrencies: {result['active_cryptocurrencies']:,}
- Active Markets: {result['markets']:,}
- Ongoing ICOs: {result['ongoing_icos']}
"""
        return output
        
    except Exception as e:
        logger.error(f"Failed to get global market data: {str(e)}")
        return f"Failed to fetch global market data: {str(e)}"


@tool
def get_trending_coins() -> str:
    """
    Get the top trending coins on CoinGecko based on user searches in the last 24 hours.
    
    Returns:
        List of trending coins with their details including:
        - Coin name and symbol
        - Market cap rank
        - Current price in BTC
        - Price change percentage (24h)
    """
    try:
        data = _make_coingecko_request("search/trending")
        coins = data.get("coins", [])
        
        if not coins:
            return "No trending coins found at the moment."
        
        output = "🔥 **Top Trending Coins (Last 24h)**\n\n"
        
        for idx, coin_data in enumerate(coins[:15], 1):
            coin = coin_data.get("item", {})
            name = coin.get("name", "Unknown")
            symbol = coin.get("symbol", "???").upper()
            market_cap_rank = coin.get("market_cap_rank", "N/A")
            price_btc = coin.get("price_btc", 0)
            score = coin.get("score", 0) + 1  # 0-indexed score
            
            # Get additional data if available
            data_info = coin.get("data", {})
            price_usd = data_info.get("price", "N/A")
            price_change_24h = data_info.get("price_change_percentage_24h", {}).get("usd", 0)
            
            output += f"{idx}. **{name}** ({symbol})\n"
            output += f"   📍 Rank: #{market_cap_rank} | "
            
            if isinstance(price_usd, (int, float)):
                output += f"💵 ${price_usd:,.6f}\n"
            else:
                output += f"💵 {price_usd}\n"
                
            if price_change_24h:
                change_emoji = "📈" if price_change_24h > 0 else "📉"
                output += f"   {change_emoji} 24h Change: {price_change_24h:.2f}%\n"
            
            output += "\n"
        
        return output
        
    except Exception as e:
        logger.error(f"Failed to get trending coins: {str(e)}")
        return f"Failed to fetch trending coins: {str(e)}"