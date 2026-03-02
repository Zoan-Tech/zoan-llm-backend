"""
Tools for the Aster Perp DEX Agent.
Provides functionality to open and close perpetual futures positions on BNB Chain and Arbitrum.
"""
from typing import Optional
from langchain.tools import tool
from model.graph import (
    Action,
    InterruptObject,
)
from model.completion import AgentKYA
from langchain_core.runnables.config import ensure_config
from langgraph.types import interrupt
import json
from web3 import Web3
from config.logging import get_logger

logger = get_logger()

def load_aster_abi():
    with open('data/aster_abi.json', 'r') as f:
        aster_abi = json.load(f)
        return aster_abi

ARBITRUM_RPC_URL='https://arb1.arbitrum.io/rpc'
ASTER_ABI = [
    {
        "inputs": [
        {
            "components": [
            {
                "internalType": "address",
                "name": "pairBase",
                "type": "address"
            },
            {
                "internalType": "bool",
                "name": "isLong",
                "type": "bool"
            },
            {
                "internalType": "address",
                "name": "tokenIn",
                "type": "address"
            },
            {
                "internalType": "uint96",
                "name": "amountIn",
                "type": "uint96"
            },
            {
                "internalType": "uint80",
                "name": "qty",
                "type": "uint80"
            },
            {
                "internalType": "uint64",
                "name": "price",
                "type": "uint64"
            },
            {
                "internalType": "uint64",
                "name": "stopLoss",
                "type": "uint64"
            },
            {
                "internalType": "uint64",
                "name": "takeProfit",
                "type": "uint64"
            },
            {
                "internalType": "uint24",
                "name": "broker",
                "type": "uint24"
            }
            ],
            "internalType": "struct IBook.OpenDataInput",
            "name": "data",
            "type": "tuple"
        }
        ],
        "name": "openMarketTradeCheck",
        "outputs": [],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
        {
            "internalType": "bytes32",
            "name": "tradeHash",
            "type": "bytes32"
        }
        ],
        "name": "closeTrade",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    }   
]
BSC_SMART_CONTRACT_ADDRESS = '0x1b6f2d3844c6ae7d56ceb3c3643b9060ba28feb0'
BSC_SMART_CONTRACT_ADDRESS_CHECKSUM = Web3.to_checksum_address(BSC_SMART_CONTRACT_ADDRESS) # BNB Chain address

w3 = Web3(Web3.HTTPProvider(ARBITRUM_RPC_URL))

# Aster contract address
aster_contract = w3.eth.contract(
    address=BSC_SMART_CONTRACT_ADDRESS_CHECKSUM,
    abi=ASTER_ABI
)

@tool
def open_market_trade(
    pair_base: str,
    is_long: bool,
    token_in: str,
    amount_in: int,
    qty: int,
    price: int,
    stop_loss: int,
    take_profit: int,
    broker: int = 0,
):
    """
    Open a position on Aster DEX.
    
    Args:
        pair_base: Address of the trading pair base token
        is_long: True for long position, False for short
        token_in: Address of input token (BUSD/USDT/USDC)
        amount_in: Amount in token decimals
        qty: Quantity with 1e10 precision
        price: Limit/worst acceptable price with 1e8 precision
        stop_loss: Stop loss price with 1e8 precision
        take_profit: Take profit price with 1e8 precision
        broker: Broker ID (default 0)
    
    Returns:
        Unsigned transaction object for user to sign
    """
    config = ensure_config()
    configurable = config.get('configurable', {})
    user_info: Optional[AgentKYA] = configurable.get('agent_kya', {}).get("Hyperliquid Trading Agent")
    if not user_info:
        return "Error: User information for Hyperliquid Trading Agent not found in configuration."
    
    user_address = user_info.wallet_address
    
    # Convert addresses to checksum format
    wallet_address_checksum = Web3.to_checksum_address(user_address)
    
    # Build transaction with OpenDataInput struct
    tx = aster_contract.functions.openMarketTrade(
        (
            pair_base,
            is_long,
            token_in,
            amount_in,
            qty,
            price,
            stop_loss,
            take_profit,
            broker
        )
    ).build_transaction({
        'from': wallet_address_checksum,
        'nonce': w3.eth.get_transaction_count(wallet_address_checksum),
        'gas': 500000,
        'gasPrice': w3.eth.gas_price
    })
    
    interrupt_object = InterruptObject(
        action_name="open_market_trade",
        transaction=tx,
        message=f"Please sign the transaction to open a {'long' if is_long else 'short'} position on the pair {pair_base}.",
        requires_signature=True,
    )
    
    response = interrupt(interrupt_object.model_dump(exclude_none=True))
    
    if response.get("action") == Action.REJECTED.value:
        return "User rejected the open position request."
    
    if response.get("action") == Action.APPROVED.value:
        tx_hash = response.get("tx_hash")
        if not tx_hash:
            return "Transaction approved but no transaction hash received."
        
        try:
            # Wait for transaction receipt
            logger.info(f"[AsterAgent] Waiting for transaction receipt: {tx_hash}")
            tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            if tx_receipt['status'] == 1:
                return f"✅ {'Long' if is_long else 'Short'} position opened successfully!\nTransaction hash: {tx_hash}\nBlock number: {tx_receipt['blockNumber']}"
            else:
                return f"❌ Transaction failed.\nTransaction hash: {tx_hash}\nBlock number: {tx_receipt['blockNumber']}"
        except Exception as e:
            logger.error(f"[AsterAgent] Error checking transaction status: {str(e)}")
            return f"Transaction submitted: {tx_hash}\nNote: Could not verify transaction status. Please check manually."
    
    return f"Unexpected response action: {response.get('action')}"

@tool
def close_trade(
    trade_hash: str,
):
    """
    Close an existing position on Aster DEX.
    
    Args:
        trade_hash: The trade hash (bytes32) of the position to close
    
    Returns:
        Transaction result message
    """
    config = ensure_config()
    configurable = config.get('configurable', {})
    user_info: Optional[AgentKYA] = configurable.get('agent_kya', {}).get("Hyperliquid Trading Agent")
    if not user_info:
        return "Error: User information for Hyperliquid Trading Agent not found in configuration."
    
    user_address = user_info.wallet_address
    
    # Convert addresses to checksum format
    wallet_address_checksum = Web3.to_checksum_address(user_address)
    
    # Build transaction to close trade
    tx = aster_contract.functions.closeTrade(
        trade_hash
    ).build_transaction({
        'from': wallet_address_checksum,
        'nonce': w3.eth.get_transaction_count(wallet_address_checksum),
        'gas': 500000,
        'gasPrice': w3.eth.gas_price
    })
    
    interrupt_object = InterruptObject(
        action_name="close_trade",
        transaction=tx,
        message=f"Please sign the transaction to close position {trade_hash}.",
        requires_signature=True,
    )
    
    response = interrupt(interrupt_object.model_dump(exclude_none=True))
    
    if response.get("action") == Action.REJECTED.value:
        return "User rejected the close position request."
    
    if response.get("action") == Action.APPROVED.value:
        tx_hash = response.get("tx_hash")
        if not tx_hash:
            return "Transaction approved but no transaction hash received."
        
        try:
            # Wait for transaction receipt
            logger.info(f"[AsterAgent] Waiting for transaction receipt: {tx_hash}")
            tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            if tx_receipt['status'] == 1:
                return f"✅ Position closed successfully!\nTransaction hash: {tx_hash}\nBlock number: {tx_receipt['blockNumber']}"
            else:
                return f"❌ Transaction failed.\nTransaction hash: {tx_hash}\nBlock number: {tx_receipt['blockNumber']}"
        except Exception as e:
            logger.error(f"[AsterAgent] Error checking transaction status: {str(e)}")
            return f"Transaction submitted: {tx_hash}\nNote: Could not verify transaction status. Please check manually."
    
    return f"Unexpected response action: {response.get('action')}"