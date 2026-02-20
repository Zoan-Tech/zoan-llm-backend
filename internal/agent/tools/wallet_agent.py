import httpx
from langchain_core.tools import tool
from privy import PrivyAPI
from config import Config

# Initialize once
client = PrivyAPI()

CHAINS_CONFIG = {
    "ethereum": {
        "caip2": "eip155:1",
        "chain_id": 1,
        "rpc": "https://ethereum-rpc.publicnode.com",
        "swap_provider": "0x",
        "tokens": {
            "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
            "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
            "ETH":  "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
            "WETH": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        },
        "bridge": {
            "orbiter": "0x80C67432656d59144cEFf962E8fAF8926599bCF8",
            "targets": ["arbitrum", "base", "bnb", "optimism", "polygon"],
        },
    },
    "polygon": {
        "caip2": "eip155:137",
        "chain_id": 137,
        "rpc": "https://polygon-rpc.com",
        "swap_provider": "0x",
        "tokens": {
            "USDC":  "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359",
            "USDT":  "0xc2132D05D31c914a87C6611C10748AEb04B58e8F",
            "MATIC": "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
            "WMATIC":"0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",
        },
        "bridge": {
            "orbiter": "0x80C67432656d59144cEFf962E8fAF8926599bCF8",
            "targets": ["arbitrum", "base", "bnb", "ethereum", "optimism"],
        },
    },
    "optimism": {
        "caip2": "eip155:10",
        "chain_id": 10,
        "rpc": "https://mainnet.optimism.io",
        "swap_provider": "0x",
        "tokens": {
            "USDC": "0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85",
            "USDT": "0x94b008aA00579c1307B0EF2c499aD98a8ce58e58",
            "ETH":  "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
            "WETH": "0x4200000000000000000000000000000000000006",
        },
        "bridge": {
            "orbiter": "0x80C67432656d59144cEFf962E8fAF8926599bCF8",
            "targets": ["arbitrum", "base", "bnb", "ethereum", "polygon"],
        },
    },
    "arbitrum": {
        "caip2": "eip155:42161",
        "chain_id": 42161,
        "rpc": "https://arb1.arbitrum.io/rpc",
        "swap_provider": "0x",
        "tokens": {
            "USDC": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
            "USDT": "0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9",
            "ETH":  "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
            "WETH": "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",
        },
        "bridge": {
            "orbiter": "0x80C67432656d59144cEFf962E8fAF8926599bCF8",
            "targets": ["base", "bnb", "eni", "ethereum", "optimism", "polygon"],
        },
    },
    "base": {
        "caip2": "eip155:8453",
        "chain_id": 8453,
        "rpc": "https://mainnet.base.org",
        "swap_provider": "0x",
        "tokens": {
            "USDC": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
            "ETH":  "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
            "WETH": "0x4200000000000000000000000000000000000006",
        },
        "bridge": {
            "orbiter": "0x80C67432656d59144cEFf962E8fAF8926599bCF8",
            "targets": ["arbitrum", "bnb", "eni", "ethereum", "optimism", "polygon"],
        },
    },
    "bnb": {
        "caip2": "eip155:56",
        "chain_id": 56,
        "rpc": "https://bsc-dataseed.binance.org",
        "swap_provider": "0x",
        "tokens": {
            "USDC": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
            "USDT": "0x55d398326f99059fF775485246999027B3197955",
            "BNB":  "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
            "WBNB": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
        },
        "bridge": {
            "orbiter": "0x80C67432656d59144cEFf962E8fAF8926599bCF8",
            "targets": ["arbitrum", "base", "eni", "ethereum", "optimism", "polygon"],
        },
    },
    "eni": {
        "caip2": "eip155:173",
        "chain_id": 173,
        "rpc": "https://rpc.eniac.network",
        "swap_provider": "router",
        "swap_router": "",  # TODO: EGAS Swap router address
        "tokens": {
            "USDC": "",  # TODO: USDC address on ENI
            "ENI":  "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
        },
        "bridge": {
            "orbiter": "",  # TODO: Orbiter Finance address on ENI
            "targets": ["arbitrum", "base", "bnb"],
        },
    },
}

ZERO_X_ENDPOINTS = {
    1:     "https://api.0x.org",
    137:   "https://polygon.api.0x.org",
    10:    "https://optimism.api.0x.org",
    42161: "https://arbitrum.api.0x.org",
    8453:  "https://base.api.0x.org",
    56:    "https://bsc.api.0x.org",
}

TOKEN_DECIMALS = {
    "ETH": 18, "WETH": 18,
    "MATIC": 18, "WMATIC": 18,
    "BNB": 18, "WBNB": 18,
    "ENI": 18,
    "USDC": 6, "USDT": 6,
}


def _privy_send_tx(wallet_id: str, caip2: str, to: str, data: str = None, value: int = 0) -> dict:
    """Send transaction via Privy Python SDK."""
    transaction = {"to": to, "value": value}
    if data:
        transaction["data"] = data

    tx = client.wallets.rpc(
        wallet_id=wallet_id,
        method="eth_sendTransaction",
        caip2=caip2,
        params={
            "transaction": transaction,
        },
    )
    return {"hash": tx.data.hash, "caip2": tx.data.caip2}

def build_egas_swap_calldata():
    # TODO: Implement calldata builder for EGAS router on ENI
    pass

def _get_0x_quote(config: dict, token_in: str, token_out: str, amount: str, taker_address: str | None = None) -> dict:
    """Fetch a swap quote from the 0x API."""
    endpoint = ZERO_X_ENDPOINTS[config["chain_id"]]
    params = {
        "sellToken": token_in.lower(),
        "buyToken": token_out.lower(),
        "sellAmount": amount,
    }
    if taker_address:
        params["takerAddress"] = taker_address
    response = httpx.get(
        f"{endpoint}/swap/v1/quote",
        params=params,
        headers={"0x-api-key": Config.ZERO_X_API_KEY},
    )
    response.raise_for_status()
    return response.json()


def _swap_via_0x(wallet_id, config, token_in, token_out, amount, taker_address: str | None = None):
    """Get quote from 0x API, then send tx via Privy."""
    quote = _get_0x_quote(config, token_in, token_out, amount, taker_address)

    return _privy_send_tx(
        wallet_id=wallet_id,
        caip2=config["caip2"],
        to=quote["to"],
        data=quote["data"],
        value=quote.get("value", "0"),
    )


def _swap_via_router(wallet_id, config, token_in, token_out, amount):
    """Build calldata for EGAS Swap router on ENI."""
    calldata = build_egas_swap_calldata(token_in, token_out, amount)

    return _privy_send_tx(
        wallet_id=wallet_id,
        caip2=config["caip2"],
        to=config["swap_router"],
        data=calldata,
    )

@tool
def review_swap(chain: str, token_in: str, token_out: str, amount: str, wallet_address: str) -> str:
    """
    Preview a swap quote without executing it.

    Returns the expected output amount, exchange rate, protocol fees, estimated
    gas cost, price impact, and liquidity sources so the user can confirm before
    calling swap_token.

    Args:
        chain: Chain name (e.g. "ethereum", "arbitrum", "base")
        token_in: Symbol of the token to sell (e.g. "ETH", "USDC")
        token_out: Symbol of the token to buy (e.g. "USDC", "ETH")
        amount: Sell amount in the token's smallest unit (e.g. "1000000" for 1 USDC)
        wallet_address: User's EVM wallet address (used as takerAddress for accurate quote)

    Returns:
        Human-readable swap summary with fees included, or an error message.
    """
    if chain not in CHAINS_CONFIG:
        return f"❌ Unsupported chain '{chain}'. Supported: {', '.join(CHAINS_CONFIG)}"

    config = CHAINS_CONFIG[chain]

    if config["swap_provider"] != "0x":
        return f"❌ Quote preview is not yet supported for {chain} (EGAS router)."

    if token_in not in config["tokens"] or token_out not in config["tokens"]:
        supported = ", ".join(config["tokens"])
        return f"❌ Unsupported token on {chain}. Supported tokens: {supported}"

    token_in_addr = config["tokens"][token_in]
    token_out_addr = config["tokens"][token_out]

    try:
        quote = _get_0x_quote(config, token_in_addr, token_out_addr, amount, taker_address=wallet_address)
    except Exception as e:
        return f"❌ Failed to fetch quote: {e}"

    if "code" in quote:  # 0x error envelope
        return f"❌ 0x API error: {quote.get('reason', quote)}"

    def _fmt(raw: str | int | None, symbol: str) -> str:
        """Format a raw token amount using known decimals."""
        if raw is None:
            return "N/A"
        decimals = TOKEN_DECIMALS.get(symbol, 18)
        value = int(raw) / 10 ** decimals
        return f"{value:,.6f} {symbol}".rstrip("0").rstrip(".")

    sell_display  = _fmt(quote.get("sellAmount"), token_in)
    buy_display   = _fmt(quote.get("buyAmount"), token_out)

    # Exchange rate: how much token_out per 1 token_in
    sell_dec = TOKEN_DECIMALS.get(token_in, 18)
    buy_dec  = TOKEN_DECIMALS.get(token_out, 18)
    try:
        rate = (int(quote["buyAmount"]) / 10 ** buy_dec) / (int(quote["sellAmount"]) / 10 ** sell_dec)
        rate_display = f"1 {token_in} ≈ {rate:,.6f} {token_out}"
    except (KeyError, ZeroDivisionError):
        rate_display = "N/A"

    # Protocol fee (ETH)
    protocol_fee_wei = quote.get("protocolFee", "0")
    try:
        protocol_fee_eth = int(protocol_fee_wei) / 10 ** 18
        fee_display = f"{protocol_fee_eth:.6f} ETH" if protocol_fee_eth else "None"
    except (ValueError, TypeError):
        fee_display = "N/A"

    # Gas estimate
    gas = quote.get("gas") or quote.get("estimatedGas")
    gas_price_wei = quote.get("gasPrice")
    try:
        gas_cost_eth = int(gas) * int(gas_price_wei) / 10 ** 18
        gas_display = f"~{int(gas):,} units (~{gas_cost_eth:.6f} ETH)"
    except (TypeError, ValueError):
        gas_display = f"~{gas} units" if gas else "N/A"

    # Price impact
    price_impact = quote.get("estimatedPriceImpact")
    impact_display = f"{float(price_impact):.4f}%" if price_impact is not None else "N/A"

    # Liquidity sources
    sources = quote.get("sources", [])
    active_sources = [s["name"] for s in sources if float(s.get("proportion", 0)) > 0]
    sources_display = ", ".join(active_sources) if active_sources else "N/A"

    return (
        f"🔍 Swap Preview on {chain.capitalize()}\n"
        f"  You sell : {sell_display}\n"
        f"  You get  : {buy_display}\n"
        f"  Rate     : {rate_display}\n"
        f"\n"
        f"💸 Fees\n"
        f"  Protocol fee : {fee_display}\n"
        f"  Gas estimate : {gas_display}\n"
        f"  Price impact : {impact_display}\n"
        f"\n"
        f"🏊 Liquidity sources: {sources_display}\n"
        f"\n"
        f"⚠️  This is a preview only. Call swap_token to execute."
    )


@tool
def swap_token(wallet_id: str, wallet_address: str, chain: str, token_in: str, token_out: str, amount: str) -> dict:
    """Swap tokens. Uses 0x on major chains, EGAS router on ENI."""
    config = CHAINS_CONFIG[chain]
    token_in_addr = config["tokens"][token_in]
    token_out_addr = config["tokens"][token_out]

    if config["swap_provider"] == "0x":
        return _swap_via_0x(wallet_id, config, token_in_addr, token_out_addr, amount, taker_address=wallet_address)
    else:
        return _swap_via_router(wallet_id, config, token_in_addr, token_out_addr, amount)
    
tools = [
    review_swap,
    swap_token,
]