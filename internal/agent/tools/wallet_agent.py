import httpx
from langchain_core.tools import tool
from privy import PrivyAPI
from config import Config
from config.logging import get_logger
from langchain_core.runnables.config import ensure_config

logger = get_logger()

# Initialize once
client = PrivyAPI(
    authorization_key=Config.PRIVY_SIGNER_KEY
)

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
            "targets": ["arbitrum", "base", "bnb", "optimism", "polygon", "eni"],
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
            "targets": ["arbitrum", "base", "bnb", "ethereum", "optimism", "eni"],
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
            "targets": ["arbitrum", "base", "bnb", "ethereum", "polygon", "eni"],
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
            "targets": ["base", "bnb", "eni", "ethereum", "optimism", "polygon", "eni"],
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
            "targets": ["arbitrum", "bnb", "eni", "ethereum", "optimism", "polygon", "eni"],
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
            "targets": ["arbitrum", "base", "eni", "ethereum", "optimism", "polygon", "eni"],
        },
    },
    "eni": {
        "caip2": "eip155:173",
        "chain_id": 173,
        "rpc": "https://rpc.eniac.network",
        "swap_provider": "router",
        "swap_router": "0x37CCd90ed5FA96207B41C4fBCB90b883e30e63DC",  # TODO: EGAS Swap router address
        "tokens": {
            "ENI-Peg USDT": "0xDC1a8A35b0BaA3229b13f348ED708a2fd50b5e3a",
            "USDT": "0x47c98f74dBC1acc4cf2e04C4a729E22379EF4373",
            "Orbiter USDT": "0x47c98f74dBC1acc4cf2e04C4a729E22379EF4373",
            "USDC": "0xaFF944b96c1BAEA587159ec446280E468B32ee15",
            "EGAS":  "0x0000000000000000000000000000000000000000",
        },
        "bridge": {
            "orbiter": "0x80C67432656d59144cEFf962E8fAF8926599bCF8",
            "targets": ["arbitrum", "base", "bnb", "ethereum"],
        },
    },
    "eni-testnet": {
        "caip2": "eip155:174",
        "chain_id": 174,
        "rpc": "https://rpc-testnet.eniac.network",
        "swap_provider": "router",
        "swap_router": "0x6741B16197ab5575d5A8C904159d4ef80ee1e6Bf",
        "tokens": {
            "ENI-Peg USDT": "0x605affcf6979afddabe6a050b182bdc390fc71ff",
            "Orbiter USDT": "0x98183dbB8E506F3276D2ae2D0d086c3B90F0E742",
            "EGAS":  "0x0000000000000000000000000000000000000000",
        },
        "bridge": {
            "orbiter": "0x80C67432656d59144cEFf962E8fAF8926599bCF8",
            "targets": ["arbitrum", "base", "bnb"],
        },
    }
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
    "EGAS": 18,
    "USDC": 6, 
    "USDT": 6,
    "ENI-Peg USDT": 18,
    "Orbiter USDT": 6,
}

ORBITER_API_BASE = "https://openapi.orbiter.finance"


def _privy_send_tx(
    wallet_id: str,
    caip2: str,
    to: str,
    data: str = None,
    value: str = "0x0",
) -> dict:
    """Send transaction using pre-created dashboard signer."""
    try:
        transaction = {"to": to, "value": value}
        if data:
            transaction["data"] = data

        # Privy SDK handles authorization with server-side signer
        tx = client.wallets.rpc(
            wallet_id=wallet_id,
            method="eth_sendTransaction",
            caip2=caip2,
            params={"transaction": transaction},
        )
        
        return {"hash": tx.data.hash, "caip2": tx.data.caip2}
    except Exception as e:
        return f"Privy transaction failed: {e}. Ensure user has set up KYA with Wallet Agent. Go the 'Explore' page > pair Wallet Agent > finish."

def _rpc_call(rpc_url: str, method: str, params: list) -> any:
    """Make a JSON-RPC call to an EVM node."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params,
    }
    response = httpx.post(rpc_url, json=payload, timeout=30.0)
    response.raise_for_status()
    result = response.json()
    if "error" in result:
        raise RuntimeError(f"RPC error: {result['error']}")
    return result["result"]


def _wait_for_tx_receipt(rpc_url: str, tx_hash: str, timeout: int = 60, poll_interval: float = 1.5) -> dict:
    """Poll eth_getTransactionReceipt until the tx is mined or timeout."""
    import time
    deadline = time.time() + timeout
    while time.time() < deadline:
        receipt = _rpc_call(rpc_url, "eth_getTransactionReceipt", [tx_hash])
        if receipt is not None:
            status = int(receipt.get("status", "0x0"), 16)
            if status == 1:
                logger.info(f"[WAIT_TX] tx {tx_hash} confirmed (status=1)")
                return receipt
            else:
                raise RuntimeError(f"Transaction {tx_hash} reverted (status=0)")
        time.sleep(poll_interval)
    raise RuntimeError(f"Transaction {tx_hash} not confirmed within {timeout}s")


def _privy_sign_and_broadcast(
    wallet_id: str,
    rpc_url: str,
    chain_id: int,
    sender_address: str,
    to: str,
    data: str,
    value: str = "0x0",
    gas_limit: int = 900000,
) -> dict:
    """
    Sign a transaction with Privy (eth_signTransaction) and broadcast it
    to the target chain RPC ourselves. This bypasses Privy's caip2 chain
    support requirement.
    """
    # 1. Fetch nonce from target chain
    nonce = _rpc_call(rpc_url, "eth_getTransactionCount", [sender_address, "latest"])

    # 2. Fetch gas price from target chain
    gas_price = _rpc_call(rpc_url, "eth_gasPrice", [])

    # 3. Build full transaction params for signing
    tx_params = {
        "to": to,
        "value": value,
        "data": data,
        "chain_id": chain_id,
        "nonce": nonce,
        "gas_limit": gas_limit,
        "gas_price": gas_price,
        "type": 0,  # Legacy transaction
    }

    logger.info(f"[SIGN_BROADCAST] Signing tx: wallet={wallet_id}, chain_id={chain_id}, to={to}, value={value}, nonce={nonce}, gas_price={gas_price}")

    # 4. Sign with Privy (no caip2 needed!)
    sign_result = client.wallets.rpc(
        wallet_id=wallet_id,
        method="eth_signTransaction",
        params={"transaction": tx_params},
    )

    signed_tx = sign_result.data.signed_transaction
    logger.info(f"[SIGN_BROADCAST] Got signed tx (encoding={sign_result.data.encoding})")

    # 5. Broadcast to target chain RPC
    tx_hash = _rpc_call(rpc_url, "eth_sendRawTransaction", [signed_tx])
    logger.info(f"[SIGN_BROADCAST] Broadcasted! tx_hash={tx_hash}")

    return {"hash": tx_hash, "chain_id": chain_id}


#### SWAP HELPER FUNCTIONS ####

def build_egas_swap_calldata(token_in: str, token_out: str, amount: str) -> str:
    """
    Build calldata for EGAS Swap router: exchange(address tokenIn, address tokenOut, uint256 amount)

    Function selector: 0x969e3756

    Args:
        token_in:  Token address to sell (use 0x0000...0000 for native EGAS)
        token_out: Token address to buy
        amount:    Amount in wei as a decimal string (e.g. "1000000000000000000" for 1 EGAS)

    Returns:
        Hex-encoded calldata string starting with "0x"
    """
    # Function selector for exchange(address,address,uint256)
    selector = "969e3756"

    # Pad addresses to 32 bytes (remove "0x" prefix, lowercase, zero-fill to 64 hex chars)
    token_in_padded = token_in[2:].lower().zfill(64)
    token_out_padded = token_out[2:].lower().zfill(64)

    # Pad uint256 amount to 32 bytes
    amount_padded = hex(int(amount))[2:].zfill(64)

    return f"0x{selector}{token_in_padded}{token_out_padded}{amount_padded}"


def _get_0x_quote(config: dict, token_in: str, token_out: str, amount: str, taker_address: str) -> dict:
    """Fetch a swap quote from the 0x API v2."""
    endpoint = ZERO_X_ENDPOINTS[config["chain_id"]]
    params = {
        "chainId": str(config["chain_id"]),
        "sellToken": token_in,
        "buyToken": token_out,
        "sellAmount": amount,
        "taker": taker_address,
    }

    headers = {"0x-version": "v2"}
    if Config.ZERO_X_API_KEY:
        headers["0x-api-key"] = Config.ZERO_X_API_KEY

    response = httpx.get(
        f"{endpoint}/swap/allowance-holder/quote",
        params=params,
        headers=headers,
    )
    response.raise_for_status()
    return response.json()


def _encode_erc20_approve(spender: str, amount: int) -> str:
    """Encode ERC-20 approve(spender, amount) calldata."""
    selector = "095ea7b3"
    spender_padded = spender[2:].lower().zfill(64)
    amount_padded = hex(amount)[2:].zfill(64)
    return f"0x{selector}{spender_padded}{amount_padded}"


def _swap_via_0x(
    wallet_id,
    config,
    token_in,
    token_out,
    amount,
    taker_address: str,
):
    """Get quote from 0x API v2, then send tx via Privy."""
    quote = _get_0x_quote(config, token_in, token_out, amount, taker_address)

    approval_tx = None
    
    # Handle allowance approval if needed
    allowance_issue = (quote.get("issues") or {}).get("allowance")
    if allowance_issue:
        spender = allowance_issue["spender"]
        sell_amount = int(quote["sellAmount"])
        approve_data = _encode_erc20_approve(spender, sell_amount)
        
        # ✅ Send approval tx
        approval_tx = _privy_send_tx(
            wallet_id=wallet_id,
            caip2=config["caip2"],
            to=token_in,
            data=approve_data,
            value="0x0",
        )
        
        # ⚠️ Don't return here! Continue to swap

    # ✅ Execute swap transaction
    tx = quote["transaction"]
    value = tx.get("value", "0")
    if not value.startswith("0x"):
        value = hex(int(value)) if value != "0" else "0x0"

    swap_tx = _privy_send_tx(
        wallet_id=wallet_id,
        caip2=config["caip2"],
        to=tx["to"],
        data=tx["data"],
        value=value,
    )
    
    # ✅ Return both transactions
    result = {
        "status": "swap_executed",
        "swap_tx": swap_tx,
    }
    
    if approval_tx:
        result["approval_tx"] = approval_tx
        result["message"] = f"Approval tx: {approval_tx['hash']}, Swap tx: {swap_tx['hash']}"
    else:
        result["message"] = f"Swap tx: {swap_tx['hash']}"
    
    return result


def _swap_via_router(
    wallet_id,
    config,
    token_in,
    token_out,
    amount,
    sender_address,
):
    """Build calldata for EGAS Swap router on ENI, sign with Privy, broadcast ourselves."""
    calldata = build_egas_swap_calldata(token_in, token_out, amount)

    # If swapping native token (EGAS), send value = amount with the tx
    NATIVE_ZERO = "0x0000000000000000000000000000000000000000"
    NATIVE_PLACEHOLDER = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"
    is_native = token_in.lower() in (NATIVE_ZERO.lower(), NATIVE_PLACEHOLDER.lower())
    value = hex(int(amount)) if is_native else "0x0"

    logger.info(f"[SWAP_ROUTER] wallet_id={wallet_id}, token_in={token_in}, token_out={token_out}, amount={amount}, value={value}, is_native={is_native}")

    result = {}

    # If tokenIn is ERC20 (not native), approve the router to spend it first
    if not is_native:
        approve_data = _encode_erc20_approve(config["swap_router"], int(amount))
        logger.info(f"[SWAP_ROUTER] Sending ERC20 approve: token={token_in}, spender={config['swap_router']}, amount={amount}")

        approval_tx = _privy_sign_and_broadcast(
            wallet_id=wallet_id,
            rpc_url=config["rpc"],
            chain_id=config["chain_id"],
            sender_address=sender_address,
            to=token_in,  # approve on the token contract
            data=approve_data,
            value="0x0",
        )
        result["approval_tx"] = approval_tx
        logger.info(f"[SWAP_ROUTER] Approval tx sent: {approval_tx}")

        # Wait for approval tx to be confirmed before sending swap tx
        logger.info(f"[SWAP_ROUTER] Waiting for approval tx to be confirmed...")
        _wait_for_tx_receipt(config["rpc"], approval_tx["hash"])

    # Execute the swap
    swap_tx = _privy_sign_and_broadcast(
        wallet_id=wallet_id,
        rpc_url=config["rpc"],
        chain_id=config["chain_id"],
        sender_address=sender_address,
        to=config["swap_router"],
        data=calldata,
        value=value,
    )
    result["swap_tx"] = swap_tx

    # Wait for swap tx confirmation and check status
    try:
        logger.info(f"[SWAP_ROUTER] Waiting for swap tx to be confirmed...")
        receipt = _wait_for_tx_receipt(config["rpc"], swap_tx["hash"])
        result["status"] = "✅ Swap confirmed successfully"
    except RuntimeError as e:
        result["status"] = f"❌ Swap failed on-chain: {e}"

    return result
    
@tool
def review_swap(
    chain: str,
    token_in: str,
    token_out: str,
    amount: str,
) -> str:
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

    Returns:
        Human-readable swap summary with fees included, or an error message.
    """
    config = ensure_config()
    wallet_address = config.get("configurable", {}).get("user_wallet_address")

    if not wallet_address:
        return "❌ Wallet address is required to preview swap quotes. Please ensure user_wallet_address is configured."

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
def swap_token(
    chain: str,
    token_in: str,
    token_out: str,
    amount: str,
) -> dict:
    """Swap tokens. Uses 0x on major chains, EGAS router on ENI.

    Args:
        chain: Chain name (e.g. "eni-testnet", "ethereum", "arbitrum")
        token_in: Symbol of the token to sell (e.g. "EGAS", "ENI-Peg USDT", "ETH", "USDC")
        token_out: Symbol of the token to buy (e.g. "ENI-Peg USDT", "EGAS", "USDC", "ETH")
        amount: Human-readable amount to swap (e.g. "1" for 1 token, "0.5" for 0.5 token)

    Returns:
        Transaction hash and details, or error message.
    """
    try:
        config = ensure_config()
        wallet_id = config.get("configurable", {}).get("user_wallet_id")
        wallet_address = config.get("configurable", {}).get("user_wallet_address")
        if not wallet_id:
            return {"error": "❌ Missing user_wallet_id in config. Please ensure Wallet Agent is paired."}

        chain_config = CHAINS_CONFIG[chain]

        token_in_addr = chain_config["tokens"][token_in]
        token_out_addr = chain_config["tokens"][token_out]

        # Convert human-readable amount to smallest unit (wei) using TOKEN_DECIMALS
        decimals = TOKEN_DECIMALS.get(token_in, 18)
        amount_wei = str(int(float(amount) * (10 ** decimals)))
        logger.info(f"[SWAP] Converting amount: {amount} {token_in} ({decimals} decimals) -> {amount_wei} wei")

        if chain_config["swap_provider"] == "0x":
            return _swap_via_0x(
                wallet_id,
                chain_config,
                token_in_addr,
                token_out_addr,
                amount_wei,
                taker_address=wallet_address,
            )
        else:
            return _swap_via_router(
                wallet_id,
                chain_config,
                token_in_addr,
                token_out_addr,
                amount_wei,
                sender_address=wallet_address,
            )
    except Exception as e:
        return {"error": f"❌ Swap failed: {e}"}


#### BRIDGE HELPER FUNCTIONS ####
def _normalize_token_for_bridge(token_address: str) -> str:
    """
    Convert token address to Orbiter-compatible format.
    Orbiter uses 0x0000... for native tokens, not 0xEeee...
    """
    NATIVE_TOKEN_PLACEHOLDER = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"
    ORBITER_NATIVE_TOKEN = "0x0000000000000000000000000000000000000000"
    
    if token_address.lower() == NATIVE_TOKEN_PLACEHOLDER.lower():
        return ORBITER_NATIVE_TOKEN
    
    return token_address

def _get_orbiter_quote(
    source_chain_id: int,
    dest_chain_id: int,
    source_token_address: str,
    dest_token_address: str,
    amount: str,
    user_address: str,
) -> dict:
    """Get a bridge quote from Orbiter Finance API."""
    source_token_normalized = _normalize_token_for_bridge(source_token_address)
    dest_token_normalized = _normalize_token_for_bridge(dest_token_address)
    
    payload = {
        "sourceChainId": str(source_chain_id),
        "destChainId": str(dest_chain_id),
        "sourceToken": source_token_normalized,
        "destToken": dest_token_normalized,
        "amount": amount,
        "userAddress": user_address,
        "targetRecipient": user_address,
    }

    response = httpx.post(
        f"{ORBITER_API_BASE}/quote",
        json=payload,
        timeout=30.0,
    )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        return f"Orbiter API HTTP error: {e.response.status_code} - {e.response.text}"
    data = response.json()
    
    if data.get("status") != "success":
        return f"Orbiter API error: {data.get('message', data)}"
    
    return data.get("result", {})

def _bridge_via_orbiter(
    wallet_id: str,
    source_chain_config: dict,
    dest_chain_config: dict,
    source_token_symbol: str,
    amount: str,
    user_address: str,
) -> dict:
    """Get quote from Orbiter and execute ALL steps (revoke, approve, bridge)."""
    
    source_token_addr = source_chain_config["tokens"][source_token_symbol]
    dest_token_addr = dest_chain_config["tokens"][source_token_symbol]

    logger.info(f"[BRIDGE] Starting bridge: token={source_token_symbol}, amount={amount}, source_token={source_token_addr}, dest_token={dest_token_addr}")
    logger.info(f"[BRIDGE] source_chain_id={source_chain_config['chain_id']}, dest_chain_id={dest_chain_config['chain_id']}")
    
    quote = _get_orbiter_quote(
        source_chain_id=source_chain_config["chain_id"],
        dest_chain_id=dest_chain_config["chain_id"],
        source_token_address=source_token_addr,
        dest_token_address=dest_token_addr,
        amount=amount,
        user_address=user_address,
    )

    logger.info(f"[BRIDGE] Orbiter quote response type={type(quote).__name__}")

    if isinstance(quote, str):
        logger.error(f"[BRIDGE] Quote returned error string: {quote}")
        return {"error": quote}

    if "steps" not in quote or len(quote["steps"]) == 0:
        logger.error(f"[BRIDGE] No steps in quote: {quote}")
        return {"error": "Invalid quote response from Orbiter"}

    steps = quote["steps"]
    logger.info(f"[BRIDGE] Got {len(steps)} steps: {[s.get('action') for s in steps]}")

    # Detect if source chain is ENI (needs sign-and-broadcast workaround)
    is_eni_chain = source_chain_config.get("swap_provider") == "router"
    result = {"steps_executed": []}

    def _send_step_tx(step_tx_data, step_action):
        """Send a single step's transaction."""
        raw_value = step_tx_data.get("value")
        if raw_value is None or raw_value == "":
            hex_value = "0x0"
        elif not str(raw_value).startswith("0x"):
            hex_value = hex(int(raw_value))
        else:
            hex_value = raw_value

        to_addr = step_tx_data.get("to")
        data = step_tx_data.get("data")

        logger.info(f"[BRIDGE] Sending step '{step_action}': to={to_addr}, value={hex_value}, data_len={len(data or '')}")

        if is_eni_chain:
            return _privy_sign_and_broadcast(
                wallet_id=wallet_id,
                rpc_url=source_chain_config["rpc"],
                chain_id=source_chain_config["chain_id"],
                sender_address=user_address,
                to=to_addr,
                data=data,
                value=hex_value,
            )
        else:
            return _privy_send_tx(
                wallet_id=wallet_id,
                caip2=source_chain_config["caip2"],
                to=to_addr,
                data=data,
                value=hex_value,
            )

    # Execute each step in order
    for i, step in enumerate(steps):
        action = step.get("action", f"step_{i}")
        tx_data = step.get("tx", {})

        if not tx_data:
            logger.warning(f"[BRIDGE] Step '{action}' has no tx data, skipping")
            continue

        logger.info(f"[BRIDGE] Executing step {i+1}/{len(steps)}: '{action}'")

        try:
            tx_result = _send_step_tx(tx_data, action)
            logger.info(f"[BRIDGE] Step '{action}' tx result: {tx_result}")
            result["steps_executed"].append({"action": action, "tx": tx_result})

            # Wait for confirmation before next step (ALL chains — needed for USDT revoke/approve sequence)
            tx_hash = tx_result.get("hash", "") if isinstance(tx_result, dict) else ""
            if tx_hash:
                rpc_url = source_chain_config["rpc"]
                logger.info(f"[BRIDGE] Waiting for step '{action}' tx {tx_hash} to confirm...")
                _wait_for_tx_receipt(rpc_url, tx_hash)
                logger.info(f"[BRIDGE] Step '{action}' confirmed!")

            # Track the bridge tx separately
            if action == "bridge":
                result["bridge_tx"] = tx_result

        except RuntimeError as e:
            logger.error(f"[BRIDGE] Step '{action}' failed: {e}")
            result["status"] = f"❌ Step '{action}' failed: {e}"
            return result

    # Final status
    if "bridge_tx" in result:
        result["status"] = "✅ Bridge completed successfully"
        logger.info(f"[BRIDGE] All steps completed successfully!")
    else:
        result["status"] = "⚠️ No bridge step was found in the quote"
        logger.warning(f"[BRIDGE] No bridge action found in steps")

    return result

@tool
def review_bridge(
    source_chain: str,
    dest_chain: str,
    token: str,
    amount: str,
) -> str:
    """
    Preview a bridge transaction without executing it.

    Returns the expected output amount, fees, estimated time, and other details
    so the user can confirm before calling bridge_token.

    Args:
        source_chain: Source chain name (e.g. "ethereum", "arbitrum", "base")
        dest_chain: Destination chain name (e.g. "arbitrum", "base", "polygon")
        token: Symbol of the token to bridge (e.g. "ETH", "USDC")
        amount: Amount in the token's smallest unit (e.g. "1000000" for 1 USDC)

    Returns:
        Human-readable bridge summary with fees and estimated time, or an error message.
    """
    config = ensure_config()
    wallet_address = config.get("configurable", {}).get("user_wallet_address")

    if not wallet_address:
        return "❌ Wallet address is required to preview bridge quotes. Please ensure user_wallet_address is configured."

    # Validate chains
    if source_chain not in CHAINS_CONFIG:
        return f"❌ Unsupported source chain '{source_chain}'. Supported: {', '.join(CHAINS_CONFIG)}"

    if dest_chain not in CHAINS_CONFIG:
        return f"❌ Unsupported destination chain '{dest_chain}'. Supported: {', '.join(CHAINS_CONFIG)}"

    source_config = CHAINS_CONFIG[source_chain]
    dest_config = CHAINS_CONFIG[dest_chain]

    # Validate token exists on BOTH chains
    if token not in source_config["tokens"]:
        return f"❌ Token {token} not supported on {source_chain}."
    
    if token not in dest_config["tokens"]:  # ✅ Check destination too
        return f"❌ Token {token} not supported on {dest_chain}."

    if not source_config.get("bridge", {}).get("orbiter"):
        return f"❌ Orbiter bridge not available on {source_chain}."

    if dest_chain not in source_config["bridge"].get("targets", []):
        return f"❌ Cannot bridge from {source_chain} to {dest_chain}."

    source_token_addr = source_config["tokens"][token]
    dest_token_addr = dest_config["tokens"][token]

    try:
        quote = _get_orbiter_quote(
            source_chain_id=source_config["chain_id"],
            dest_chain_id=dest_config["chain_id"],
            source_token_address=source_token_addr,
            dest_token_address=dest_token_addr,
            amount=amount,
            user_address=wallet_address,
        )
    except Exception as e:
        return f"❌ Failed to fetch bridge quote: {e}"

    def _fmt(raw: str | int | None, symbol: str) -> str:
        if raw is None:
            return "N/A"
        decimals = TOKEN_DECIMALS.get(symbol, 18)
        value = int(raw) / 10 ** decimals
        return f"{value:,.6f} {symbol}".rstrip("0").rstrip(".")

    details = quote.get("details", {})
    send_amount = details.get("sourceTokenAmount", amount)
    receive_amount = details.get("destTokenAmount", "0")

    send_display = _fmt(send_amount, token)
    receive_display = _fmt(receive_amount, token)

    fees = quote.get("fees", {})
    withholding_fee = fees.get("withholdingFee", "0")
    trade_fee = fees.get("tradeFee", "0")
    
    total_fee_value = float(withholding_fee) + float(trade_fee)
    total_fee_usd = float(fees.get("withholdingFeeUSD", "0")) + float(fees.get("tradeFeeUSD", "0"))

    fee_display = _fmt(int(total_fee_value * 10**TOKEN_DECIMALS.get(token, 18)), token)
    fee_usd_display = f"${total_fee_usd:.2f}" if total_fee_usd else "N/A"

    return (
        f"🌉 Bridge Preview: {source_chain.capitalize()} → {dest_chain.capitalize()}\n"
        f"  You send    : {send_display}\n"
        f"  You receive : {receive_display}\n"
        f"\n"
        f"💸 Fees\n"
        f"  Total fee      : {fee_display} ({fee_usd_display})\n"
        f"\n"
        f"⚠️  This is a preview only. Call bridge_token to execute."
    )

@tool
def bridge_token(
    source_chain: str,
    dest_chain: str,
    token: str,
    amount: str,
) -> dict:
    """
    Bridge tokens from one chain to another using Orbiter Finance.

    Args:
        source_chain: Source chain name (e.g. "eni-testnet", "ethereum", "arbitrum", "base")
        dest_chain: Destination chain name (e.g. "arbitrum", "base", "bnb")
        token: Symbol of the token to bridge (e.g. "ETH", "USDC", "EGAS", "Orbiter USDT")
        amount: Human-readable amount to bridge (e.g. "1" for 1 token, "0.5" for 0.5 token)

    Returns:
        Transaction hash and details, or error message.
    """
    try:
        config = ensure_config()
        wallet_address = config.get("configurable", {}).get("user_wallet_address")
        wallet_id = config.get("configurable", {}).get("user_wallet_id")
        if not wallet_id or not wallet_address:
            return {"error": "❌ Missing wallet config. Please ensure Wallet Agent is paired."}

        # Validate chains
        if source_chain not in CHAINS_CONFIG or dest_chain not in CHAINS_CONFIG:
            return {"error": f"❌ Invalid chain. Supported: {', '.join(CHAINS_CONFIG)}"}

        source_config = CHAINS_CONFIG[source_chain]
        dest_config = CHAINS_CONFIG[dest_chain]

        if token not in source_config["tokens"]:
            return {"error": f"❌ Token {token} not supported on {source_chain}"}
        
        if token not in dest_config["tokens"]:
            return {"error": f"❌ Token {token} not supported on {dest_chain}"}

        if not source_config.get("bridge", {}).get("orbiter"):
            return {"error": f"❌ Orbiter bridge not available on {source_chain}"}

        if dest_chain not in source_config["bridge"].get("targets", []):
            return {"error": f"❌ Cannot bridge from {source_chain} to {dest_chain}"}

        # Convert human-readable amount to smallest unit (wei) using TOKEN_DECIMALS
        decimals = TOKEN_DECIMALS.get(token, 18)
        amount_wei = str(int(float(amount) * (10 ** decimals)))
        logger.info(f"[BRIDGE] Converting amount: {amount} {token} ({decimals} decimals) -> {amount_wei} wei")

        return _bridge_via_orbiter(
            wallet_id=wallet_id,
            source_chain_config=source_config,
            dest_chain_config=dest_config,
            source_token_symbol=token,
            amount=amount_wei,
            user_address=wallet_address,
        )
    except Exception as e:
        return {"error": f"❌ Bridge failed: {e}"}
    
tools = [
    review_swap,
    swap_token,
    review_bridge,
    bridge_token,
]