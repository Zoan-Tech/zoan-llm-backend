"""
Tools for the DefiLlama Agent.
Provides DeFi market intelligence including TVL tracking, liquidity flows,
protocol growth, yield opportunities, stablecoin signals, narrative detection,
DEX volume analytics, bridge data, risk alerts, and alpha scoring.
"""

import time
from langchain.tools import tool
from config.logging import get_logger
import httpx

logger = get_logger()

CACHE = {}
CACHE_TTL = 300  # 5 minutes

DEFI_LLAMA_API = "https://api.llama.fi"
YIELD_API = "https://yields.llama.fi"
STABLECOIN_API = "https://stablecoins.llama.fi"

DEFAULT_TIMEOUT = 30
DEFAULT_HEADERS = {"User-Agent": "ZoanBot/1.0"}


def _safe_num(value, default=0) -> float:
    """Safely convert a value to a number, returning default if None or non-numeric."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _fetch_with_cache(url: str) -> dict:
    """
    Fetch data from a URL with caching support.

    Args:
        url: The API endpoint URL to fetch from.

    Returns:
        JSON response as dict.
    """
    now = time.time()

    if url in CACHE:
        data, ts = CACHE[url]
        if now - ts < CACHE_TTL:
            return data

    try:
        res = httpx.get(url, timeout=DEFAULT_TIMEOUT, headers=DEFAULT_HEADERS)
        res.raise_for_status()
        data = res.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"DefiLlama API error: {e.response.status_code} - {e.response.text}")
        raise
    except Exception as e:
        logger.error(f"DefiLlama request failed: {str(e)}")
        raise

    CACHE[url] = (data, now)
    return data


def _compute_growth_score(protocol: dict) -> float:
    """
    Compute a growth score for a protocol based on TVL and recent changes.

    Args:
        protocol: Protocol data dict from DefiLlama.

    Returns:
        Numeric growth score. Returns 0 for protocols with TVL < $5M.
    """
    tvl = _safe_num(protocol.get("tvl"))
    change_7d = _safe_num(protocol.get("change_7d"))
    change_1d = _safe_num(protocol.get("change_1d"))

    if tvl < 5_000_000:
        return 0  # filter noise

    score = (
        change_7d * 0.6
        + change_1d * 0.3
        + (tvl / 1_000_000_000) * 0.1
    )

    return score


# =============================================================================
# EXISTING TOOLS (fixed NoneType bugs)
# =============================================================================


@tool
def get_defi_global_overview() -> str:
    """
    Get a global overview of the DeFi market from DefiLlama,
    including total TVL, 1-day and 7-day changes.

    Returns:
        Global DeFi market overview including:
        - Total value locked (TVL) across all protocols
        - 1-day TVL change percentage
        - 7-day TVL change percentage
    """
    try:
        url = f"{DEFI_LLAMA_API}/v2/historicalChainTvl"
        data = _fetch_with_cache(url)

        # Get the latest day's data point for total TVL
        if isinstance(data, list) and len(data) > 0:
            latest = data[-1]
            prev_1d = data[-2] if len(data) > 1 else latest
            prev_7d = data[-8] if len(data) > 7 else latest

            total_tvl = _safe_num(latest.get("tvl"))
            prev_1d_tvl = _safe_num(prev_1d.get("tvl"), 1)
            prev_7d_tvl = _safe_num(prev_7d.get("tvl"), 1)

            change_1d = ((total_tvl - prev_1d_tvl) / max(prev_1d_tvl, 1)) * 100
            change_7d = ((total_tvl - prev_7d_tvl) / max(prev_7d_tvl, 1)) * 100
        else:
            total_tvl = 0
            change_1d = 0
            change_7d = 0

        return (
            f"📊 **Global DeFi Overview**\n\n"
            f"💰 **Total TVL**: ${total_tvl:,.0f}\n"
            f"📈 **1d Change**: {change_1d:.2f}%\n"
            f"📈 **7d Change**: {change_7d:.2f}%\n"
        )

    except Exception as e:
        logger.error(f"Failed to get DeFi global overview: {str(e)}")
        return f"Failed to fetch DeFi global overview: {str(e)}"


@tool
def get_chain_liquidity_flows(top_n: int = 10) -> str:
    """
    Detect liquidity rotation across blockchains by analyzing
    7-day TVL changes per chain, showing top inflow and outflow chains.

    Args:
        top_n: Number of top chains to return for inflows and outflows. Default 10.

    Returns:
        Top chains by liquidity inflow and outflow including:
        - Chain name and current TVL
        - 7-day TVL change percentage
    """
    try:
        url = f"{DEFI_LLAMA_API}/v2/chains"
        chains = _fetch_with_cache(url)

        chains_sorted = sorted(
            chains,
            key=lambda x: _safe_num(x.get("change_7d")),
            reverse=True,
        )

        inflows = chains_sorted[:top_n]
        outflows = chains_sorted[-top_n:]

        output = "🔄 **Chain Liquidity Flows (7d)**\n\n"
        output += "**Top Inflows:**\n"
        for c in inflows:
            name = c.get("name", "Unknown")
            change = _safe_num(c.get("change_7d"))
            tvl = _safe_num(c.get("tvl"))
            output += f"  📈 {name}: {change:+.2f}% (TVL: ${tvl:,.0f})\n"

        output += "\n**Top Outflows:**\n"
        for c in outflows:
            name = c.get("name", "Unknown")
            change = _safe_num(c.get("change_7d"))
            tvl = _safe_num(c.get("tvl"))
            output += f"  📉 {name}: {change:+.2f}% (TVL: ${tvl:,.0f})\n"

        return output

    except Exception as e:
        logger.error(f"Failed to get chain liquidity flows: {str(e)}")
        return f"Failed to fetch chain liquidity flows: {str(e)}"


@tool
def get_protocol_growth_ranked(limit: int = 20) -> str:
    """
    Rank DeFi protocols by growth using a composite score based on
    7-day change, 1-day change, and TVL size. Filters out protocols
    with TVL below $5M to reduce noise.

    Args:
        limit: Maximum number of top protocols to return. Default 20.

    Returns:
        Ranked list of fastest growing protocols with:
        - Protocol name, chain, and TVL
        - 1-day and 7-day change percentages
        - Composite growth score
    """
    try:
        url = f"{DEFI_LLAMA_API}/protocols"
        protocols = _fetch_with_cache(url)

        ranked = []

        for p in protocols:
            score = _compute_growth_score(p)
            if score > 0:
                ranked.append(
                    {
                        "name": p.get("name", "Unknown"),
                        "chain": p.get("chain", "Unknown"),
                        "tvl": _safe_num(p.get("tvl")),
                        "change_1d": _safe_num(p.get("change_1d")),
                        "change_7d": _safe_num(p.get("change_7d")),
                        "score": score,
                    }
                )

        ranked.sort(key=lambda x: x["score"], reverse=True)
        top = ranked[:limit]

        output = "🚀 **Fastest Growing Protocols**\n\n"
        for idx, p in enumerate(top, 1):
            output += (
                f"{idx}. **{p['name']}** ({p['chain']})\n"
                f"   💰 TVL: ${p['tvl']:,.0f} | "
                f"1d: {p['change_1d']:+.2f}% | "
                f"7d: {p['change_7d']:+.2f}% | "
                f"Score: {p['score']:.2f}\n"
            )

        return output

    except Exception as e:
        logger.error(f"Failed to get protocol growth rankings: {str(e)}")
        return f"Failed to fetch protocol growth rankings: {str(e)}"


@tool
def get_top_yield_opportunities(limit: int = 15) -> str:
    """
    Discover top yield farming opportunities across DeFi protocols.
    Filters for pools with APY > 20% and TVL > $1M to ensure quality.

    Args:
        limit: Maximum number of yield opportunities to return. Default 15.

    Returns:
        Top yield opportunities with:
        - Pool name, project, and chain
        - Current APY percentage
        - Pool TVL in USD
    """
    try:
        url = f"{YIELD_API}/pools"
        data = _fetch_with_cache(url)

        pools = data.get("data", [])

        filtered = [
            p
            for p in pools
            if _safe_num(p.get("apy")) > 20
            and _safe_num(p.get("tvlUsd")) > 1_000_000
        ]

        filtered.sort(key=lambda x: _safe_num(x.get("apy")), reverse=True)
        top = filtered[:limit]

        output = "💎 **Top Yield Opportunities**\n\n"
        for idx, p in enumerate(top, 1):
            symbol = p.get("symbol", "Unknown")
            project = p.get("project", "Unknown")
            chain = p.get("chain", "Unknown")
            apy = _safe_num(p.get("apy"))
            tvl = _safe_num(p.get("tvlUsd"))
            output += (
                f"{idx}. **{symbol}** ({project} on {chain})\n"
                f"   📈 APY: {apy:.2f}% | 💰 TVL: ${tvl:,.0f}\n"
            )

        return output

    except Exception as e:
        logger.error(f"Failed to get yield opportunities: {str(e)}")
        return f"Failed to fetch yield opportunities: {str(e)}"


@tool
def get_stablecoin_liquidity_signals() -> str:
    """
    Analyze stablecoin liquidity movements across chains to detect
    capital flow signals. Returns chains with > 5% change in
    stablecoin liquidity over 7 days.

    Returns:
        Stablecoin liquidity signals including:
        - Chain name
        - 7-day liquidity change percentage
        - Direction indicator (inflow/outflow)
    """
    try:
        url = f"{STABLECOIN_API}/stablecoinchains"
        data = _fetch_with_cache(url)

        chains = data if isinstance(data, list) else data.get("chains", [])

        signals = []

        for c in chains:
            change = _safe_num(c.get("change_7d"))
            if abs(change) > 5:
                signals.append(
                    {
                        "chain": c.get("name", "Unknown"),
                        "liquidity_change": change,
                    }
                )

        signals.sort(key=lambda x: abs(x["liquidity_change"]), reverse=True)
        top = signals[:10]

        output = "💵 **Stablecoin Liquidity Signals (7d)**\n\n"
        for s in top:
            emoji = "📈" if s["liquidity_change"] > 0 else "📉"
            output += f"  {emoji} {s['chain']}: {s['liquidity_change']:+.2f}%\n"

        return output

    except Exception as e:
        logger.error(f"Failed to get stablecoin liquidity signals: {str(e)}")
        return f"Failed to fetch stablecoin liquidity signals: {str(e)}"


@tool
def detect_emerging_narratives() -> str:
    """
    Detect emerging DeFi narratives by analyzing protocol category growth.
    Groups protocols by category and identifies sectors with average
    7-day growth exceeding 10%.

    Returns:
        Emerging DeFi narratives including:
        - Sector/category name
        - Average growth percentage across protocols
        - Total TVL in the sector
        - Number of protocols in the sector
    """
    try:
        url = f"{DEFI_LLAMA_API}/protocols"
        protocols = _fetch_with_cache(url)

        sector_map = {}

        for p in protocols:
            category = p.get("category") or "Other"
            change = _safe_num(p.get("change_7d"))

            if category not in sector_map:
                sector_map[category] = {
                    "tvl": 0.0,
                    "growth": 0.0,
                    "protocols": [],
                }

            sector_map[category]["tvl"] += _safe_num(p.get("tvl"))
            sector_map[category]["growth"] += change
            sector_map[category]["protocols"].append(p.get("name"))

        narratives = []

        for sector, sdata in sector_map.items():
            avg_growth = sdata["growth"] / max(len(sdata["protocols"]), 1)

            if avg_growth > 10:
                narratives.append(
                    {
                        "sector": sector,
                        "avg_growth": avg_growth,
                        "tvl": sdata["tvl"],
                        "protocol_count": len(sdata["protocols"]),
                    }
                )

        narratives.sort(key=lambda x: x["avg_growth"], reverse=True)
        top = narratives[:5]

        output = "🔮 **Emerging DeFi Narratives**\n\n"
        for idx, n in enumerate(top, 1):
            output += (
                f"{idx}. **{n['sector']}**\n"
                f"   📈 Avg Growth: {n['avg_growth']:.2f}% | "
                f"💰 TVL: ${n['tvl']:,.0f} | "
                f"📊 Protocols: {n['protocol_count']}\n"
            )

        return output

    except Exception as e:
        logger.error(f"Failed to detect emerging narratives: {str(e)}")
        return f"Failed to detect emerging narratives: {str(e)}"


# =============================================================================
# NEW TOOLS
# =============================================================================


@tool
def get_protocol_tvl_tracker(protocol_name: str = "") -> str:
    """
    Track protocol TVL with 1-hour, 24-hour, and 7-day change percentages.
    Can search for a specific protocol by name, or return the top protocols by TVL.

    Args:
        protocol_name: Optional protocol name to search for. If empty, returns top 15 by TVL.

    Returns:
        Protocol TVL details including:
        - Protocol name, chain, and category
        - Current TVL in USD
        - 1h, 24h, and 7d change percentages
    """
    try:
        url = f"{DEFI_LLAMA_API}/protocols"
        protocols = _fetch_with_cache(url)

        if protocol_name:
            # Search for matching protocols
            search = protocol_name.lower()
            matched = [
                p for p in protocols
                if search in (p.get("name", "")).lower()
                or search in (p.get("slug", "")).lower()
            ]
            if not matched:
                return f"No protocol found matching '{protocol_name}'."
            targets = matched[:10]
        else:
            # Top 15 by TVL
            sorted_protocols = sorted(
                protocols,
                key=lambda x: _safe_num(x.get("tvl")),
                reverse=True,
            )
            targets = sorted_protocols[:15]

        output = f"📊 **Protocol TVL Tracker**\n\n"
        for idx, p in enumerate(targets, 1):
            name = p.get("name", "Unknown")
            chain = p.get("chain", "Unknown")
            category = p.get("category") or "Unknown"
            tvl = _safe_num(p.get("tvl"))
            change_1h = _safe_num(p.get("change_1h"))
            change_1d = _safe_num(p.get("change_1d"))
            change_7d = _safe_num(p.get("change_7d"))

            output += (
                f"{idx}. **{name}** ({chain} | {category})\n"
                f"   💰 TVL: ${tvl:,.0f}\n"
                f"   ⏱️ 1h: {change_1h:+.2f}% | "
                f"24h: {change_1d:+.2f}% | "
                f"7d: {change_7d:+.2f}%\n\n"
            )

        return output

    except Exception as e:
        logger.error(f"Failed to get protocol TVL tracker: {str(e)}")
        return f"Failed to fetch protocol TVL data: {str(e)}"


@tool
def detect_early_tvl_spikes(
    max_tvl: int = 100_000_000,
    min_growth: float = 60.0,
    limit: int = 15,
) -> str:
    """
    Detect early-stage protocols with rapid TVL growth — potential alpha opportunities.
    Filters for protocols with TVL below a threshold but high growth rates.

    Args:
        max_tvl: Maximum TVL threshold in USD. Default $100M.
        min_growth: Minimum 7d growth percentage. Default 60%.
        limit: Maximum number of results. Default 15.

    Returns:
        Early TVL spike opportunities including:
        - Protocol name, chain, and category
        - Current TVL
        - 1d and 7d change percentages
    """
    try:
        url = f"{DEFI_LLAMA_API}/protocols"
        protocols = _fetch_with_cache(url)

        spikes = []

        for p in protocols:
            tvl = _safe_num(p.get("tvl"))
            change_7d = _safe_num(p.get("change_7d"))
            change_1d = _safe_num(p.get("change_1d"))

            # Filter: small protocol with big growth
            if 100_000 < tvl < max_tvl and change_7d > min_growth:
                spikes.append({
                    "name": p.get("name", "Unknown"),
                    "chain": p.get("chain", "Unknown"),
                    "category": p.get("category") or "Unknown",
                    "tvl": tvl,
                    "change_1d": change_1d,
                    "change_7d": change_7d,
                })

        spikes.sort(key=lambda x: x["change_7d"], reverse=True)
        top = spikes[:limit]

        if not top:
            return "No early TVL spikes detected with the current filters."

        output = "🚨 **Early TVL Spike Detection**\n\n"
        for idx, p in enumerate(top, 1):
            output += (
                f"{idx}. **{p['name']}** ({p['chain']} | {p['category']})\n"
                f"   💰 TVL: ${p['tvl']:,.0f}\n"
                f"   📈 1d: {p['change_1d']:+.2f}% | "
                f"7d: {p['change_7d']:+.2f}%\n"
                f"   ⚡ Early opportunity signal\n\n"
            )

        return output

    except Exception as e:
        logger.error(f"Failed to detect early TVL spikes: {str(e)}")
        return f"Failed to detect early TVL spikes: {str(e)}"


@tool
def get_dex_volume_analytics(limit: int = 15) -> str:
    """
    Get DEX (Decentralized Exchange) volume analytics including
    top DEXs by volume, volume changes, and spike detection.

    Args:
        limit: Maximum number of DEXs to return. Default 15.

    Returns:
        DEX volume analytics including:
        - DEX name and chains
        - 24h volume in USD
        - Volume change percentages (1d, 7d)
        - Volume spike alerts
    """
    try:
        url = f"{DEFI_LLAMA_API}/overview/dexs"
        data = _fetch_with_cache(url)

        protocols = data.get("protocols", [])

        dexs = []
        for d in protocols:
            vol_24h = _safe_num(d.get("total24h"))
            vol_change_1d = _safe_num(d.get("change_1d"))
            vol_change_7d = _safe_num(d.get("change_7d"))

            if vol_24h > 0:
                dexs.append({
                    "name": d.get("name", "Unknown"),
                    "chains": d.get("chains", []),
                    "volume_24h": vol_24h,
                    "change_1d": vol_change_1d,
                    "change_7d": vol_change_7d,
                })

        dexs.sort(key=lambda x: x["volume_24h"], reverse=True)
        top = dexs[:limit]

        # Detect volume spikes (>100% increase in 24h)
        spikes = [d for d in dexs if d["change_1d"] > 100]

        output = "📊 **DEX Volume Analytics**\n\n"

        if spikes:
            output += "🚨 **Volume Spikes Detected:**\n"
            for s in spikes[:5]:
                chains_str = ", ".join(s["chains"][:3]) if s["chains"] else "Multi"
                output += (
                    f"  ⚡ **{s['name']}** ({chains_str}): "
                    f"+{s['change_1d']:.0f}% volume spike!\n"
                )
            output += "\n"

        output += "**Top DEXs by 24h Volume:**\n\n"
        for idx, d in enumerate(top, 1):
            chains_str = ", ".join(d["chains"][:3]) if d["chains"] else "Multi"
            change_emoji = "📈" if d["change_1d"] > 0 else "📉"
            output += (
                f"{idx}. **{d['name']}** ({chains_str})\n"
                f"   💰 24h Vol: ${d['volume_24h']:,.0f}\n"
                f"   {change_emoji} 1d: {d['change_1d']:+.2f}% | "
                f"7d: {d['change_7d']:+.2f}%\n\n"
            )

        return output

    except Exception as e:
        logger.error(f"Failed to get DEX volume analytics: {str(e)}")
        return f"Failed to fetch DEX volume analytics: {str(e)}"


@tool
def get_bridge_crosschain_flows(limit: int = 15) -> str:
    """
    Get bridge and cross-chain capital flow data showing which
    bridges are most active and where capital is flowing.

    Args:
        limit: Maximum number of bridges to return. Default 15.

    Returns:
        Bridge cross-chain flow data including:
        - Bridge name and supported chains
        - 24h volume
        - Volume change percentages
    """
    try:
        url = f"{DEFI_LLAMA_API}/overview/bridges"
        data = _fetch_with_cache(url)

        bridges = data.get("protocols", [])

        results = []
        for b in bridges:
            vol_24h = _safe_num(b.get("total24h"))
            change_1d = _safe_num(b.get("change_1d"))

            if vol_24h > 0:
                results.append({
                    "name": b.get("name", "Unknown"),
                    "chains": b.get("chains", []),
                    "volume_24h": vol_24h,
                    "change_1d": change_1d,
                })

        results.sort(key=lambda x: x["volume_24h"], reverse=True)
        top = results[:limit]

        output = "🌉 **Cross-chain Bridge Flows**\n\n"
        for idx, b in enumerate(top, 1):
            chains_str = ", ".join(b["chains"][:5]) if b["chains"] else "Multi"
            change_emoji = "📈" if b["change_1d"] > 0 else "📉"
            output += (
                f"{idx}. **{b['name']}**\n"
                f"   🔗 Chains: {chains_str}\n"
                f"   💰 24h Vol: ${b['volume_24h']:,.0f}\n"
                f"   {change_emoji} 1d: {b['change_1d']:+.2f}%\n\n"
            )

        return output

    except Exception as e:
        logger.error(f"Failed to get bridge cross-chain flows: {str(e)}")
        return f"Failed to fetch bridge cross-chain flows: {str(e)}"


@tool
def get_protocol_health_score(limit: int = 20) -> str:
    """
    Calculate a composite health score for DeFi protocols based on
    TVL trend, chain growth, and category performance. Higher scores
    indicate stronger, more reliable protocols.

    Args:
        limit: Maximum number of protocols to return. Default 20.

    Returns:
        Protocol health scores (0-100) with breakdown:
        - TVL score (40% weight)
        - Growth momentum (30% weight)
        - Ecosystem strength (30% weight)
    """
    try:
        protocols_url = f"{DEFI_LLAMA_API}/protocols"
        chains_url = f"{DEFI_LLAMA_API}/v2/chains"

        protocols = _fetch_with_cache(protocols_url)
        chains_data = _fetch_with_cache(chains_url)

        # Build chain growth lookup
        chain_growth = {}
        for c in chains_data:
            chain_growth[c.get("name", "")] = _safe_num(c.get("change_7d"))

        # Build category avg growth
        category_tvls = {}
        for p in protocols:
            cat = p.get("category") or "Other"
            if cat not in category_tvls:
                category_tvls[cat] = {"total_growth": 0.0, "count": 0}
            category_tvls[cat]["total_growth"] += _safe_num(p.get("change_7d"))
            category_tvls[cat]["count"] += 1

        category_avg = {}
        for cat, info in category_tvls.items():
            category_avg[cat] = info["total_growth"] / max(info["count"], 1)

        scored = []

        for p in protocols:
            tvl = _safe_num(p.get("tvl"))
            if tvl < 5_000_000:
                continue

            change_1d = _safe_num(p.get("change_1d"))
            change_7d = _safe_num(p.get("change_7d"))
            chain = p.get("chain", "")
            category = p.get("category") or "Other"

            # TVL score (0-40): log scale for TVL size
            import math
            tvl_score = min(40, (math.log10(max(tvl, 1)) - 6) * 10)
            tvl_score = max(0, tvl_score)

            # Growth momentum (0-30): 1d and 7d changes
            growth_momentum = min(30, max(-10, (change_7d * 0.4 + change_1d * 0.6)))
            growth_momentum = max(0, growth_momentum)

            # Ecosystem strength (0-30): chain + category health
            chain_g = chain_growth.get(chain, 0)
            cat_g = category_avg.get(category, 0)
            eco_score = min(30, max(0, (chain_g * 0.5 + cat_g * 0.5)))

            health = tvl_score + growth_momentum + eco_score

            scored.append({
                "name": p.get("name", "Unknown"),
                "chain": chain,
                "category": category,
                "tvl": tvl,
                "health_score": round(health, 1),
                "tvl_score": round(tvl_score, 1),
                "growth_score": round(growth_momentum, 1),
                "eco_score": round(eco_score, 1),
            })

        scored.sort(key=lambda x: x["health_score"], reverse=True)
        top = scored[:limit]

        output = "🏥 **Protocol Health Scores**\n\n"
        for idx, p in enumerate(top, 1):
            output += (
                f"{idx}. **{p['name']}** ({p['chain']} | {p['category']})\n"
                f"   💯 Health: **{p['health_score']}/100**\n"
                f"   💰 TVL: ${p['tvl']:,.0f}\n"
                f"   📊 TVL: {p['tvl_score']} | "
                f"Growth: {p['growth_score']} | "
                f"Ecosystem: {p['eco_score']}\n\n"
            )

        return output

    except Exception as e:
        logger.error(f"Failed to get protocol health scores: {str(e)}")
        return f"Failed to calculate protocol health scores: {str(e)}"


@tool
def detect_tvl_dump_risk(
    min_tvl: int = 1_000_000,
    dump_threshold_1d: float = -20.0,
    dump_threshold_7d: float = -35.0,
    limit: int = 20,
) -> str:
    """
    Detect protocols experiencing significant TVL drops that may indicate risk.
    Flags protocols with large TVL decreases in 24h or 7d.

    Args:
        min_tvl: Minimum TVL to consider (filters tiny protocols). Default $1M.
        dump_threshold_1d: 24h TVL drop threshold percentage. Default -20%.
        dump_threshold_7d: 7d TVL drop threshold percentage. Default -35%.
        limit: Maximum number of alerts. Default 20.

    Returns:
        Risk alerts including:
        - Protocol name, chain, and TVL
        - 1d and 7d change percentages
        - Risk severity level
    """
    try:
        url = f"{DEFI_LLAMA_API}/protocols"
        protocols = _fetch_with_cache(url)

        alerts = []

        for p in protocols:
            tvl = _safe_num(p.get("tvl"))
            change_1d = _safe_num(p.get("change_1d"))
            change_7d = _safe_num(p.get("change_7d"))

            if tvl < min_tvl:
                continue

            is_dump_1d = change_1d < dump_threshold_1d
            is_dump_7d = change_7d < dump_threshold_7d

            if is_dump_1d or is_dump_7d:
                # Determine severity
                if change_1d < -50 or change_7d < -60:
                    severity = "🔴 CRITICAL"
                elif change_1d < -30 or change_7d < -45:
                    severity = "🟠 HIGH"
                else:
                    severity = "🟡 MODERATE"

                alerts.append({
                    "name": p.get("name", "Unknown"),
                    "chain": p.get("chain", "Unknown"),
                    "tvl": tvl,
                    "change_1d": change_1d,
                    "change_7d": change_7d,
                    "severity": severity,
                    "sort_key": min(change_1d, change_7d),
                })

        alerts.sort(key=lambda x: x["sort_key"])
        top = alerts[:limit]

        if not top:
            return "✅ **No TVL dump risks detected.** All monitored protocols are stable."

        output = "🚨 **TVL Dump Risk Alerts**\n\n"
        for idx, a in enumerate(top, 1):
            output += (
                f"{idx}. {a['severity']} **{a['name']}** ({a['chain']})\n"
                f"   💰 TVL: ${a['tvl']:,.0f}\n"
                f"   📉 1d: {a['change_1d']:+.2f}% | "
                f"7d: {a['change_7d']:+.2f}%\n\n"
            )

        return output

    except Exception as e:
        logger.error(f"Failed to detect TVL dump risks: {str(e)}")
        return f"Failed to detect TVL dump risks: {str(e)}"


@tool
def get_alpha_opportunities(limit: int = 15) -> str:
    """
    Generate a composite Alpha Score for DeFi opportunities by combining
    TVL growth, sector growth, chain growth, and yield signals.
    Higher alpha scores indicate stronger opportunity signals.

    Args:
        limit: Maximum number of alpha opportunities to return. Default 15.

    Returns:
        Alpha opportunities ranked by composite score including:
        - Protocol name, chain, and category
        - Alpha score breakdown
        - TVL and growth data
    """
    try:
        # Fetch all required data
        protocols = _fetch_with_cache(f"{DEFI_LLAMA_API}/protocols")
        chains_data = _fetch_with_cache(f"{DEFI_LLAMA_API}/v2/chains")

        # Try to fetch yield data, but don't fail if unavailable
        try:
            yield_data = _fetch_with_cache(f"{YIELD_API}/pools")
            yield_pools = yield_data.get("data", [])
        except Exception:
            yield_pools = []

        # Build chain growth lookup
        chain_growth = {}
        for c in chains_data:
            chain_growth[c.get("name", "")] = _safe_num(c.get("change_7d"))

        # Build category growth lookup
        category_growth_sum = {}
        category_count = {}
        for p in protocols:
            cat = p.get("category") or "Other"
            category_growth_sum[cat] = category_growth_sum.get(cat, 0.0) + _safe_num(p.get("change_7d"))
            category_count[cat] = category_count.get(cat, 0) + 1

        category_avg_growth = {}
        for cat in category_growth_sum:
            category_avg_growth[cat] = category_growth_sum[cat] / max(category_count[cat], 1)

        # Build yield lookup by project name
        yield_by_project = {}
        for pool in yield_pools:
            project = pool.get("project", "")
            apy = _safe_num(pool.get("apy"))
            pool_tvl = _safe_num(pool.get("tvlUsd"))
            if project and apy > 0 and pool_tvl > 500_000:
                if project not in yield_by_project or apy > yield_by_project[project]:
                    yield_by_project[project] = apy

        # Score protocols
        scored = []

        for p in protocols:
            tvl = _safe_num(p.get("tvl"))
            if tvl < 1_000_000:
                continue

            change_1d = _safe_num(p.get("change_1d"))
            change_7d = _safe_num(p.get("change_7d"))
            chain = p.get("chain", "")
            category = p.get("category") or "Other"
            slug = p.get("slug", "")

            # TVL growth score (0-30)
            tvl_growth_score = min(30, max(0, change_7d * 0.3 + change_1d * 0.5))

            # Sector growth score (0-25)
            sector_score = min(25, max(0, category_avg_growth.get(category, 0) * 0.5))

            # Chain growth score (0-25)
            chain_score = min(25, max(0, chain_growth.get(chain, 0) * 0.5))

            # Yield signal score (0-20)
            best_apy = yield_by_project.get(slug, 0)
            yield_score = min(20, best_apy * 0.3) if best_apy > 5 else 0

            alpha = tvl_growth_score + sector_score + chain_score + yield_score

            if alpha > 10:  # Minimum threshold
                scored.append({
                    "name": p.get("name", "Unknown"),
                    "chain": chain,
                    "category": category,
                    "tvl": tvl,
                    "change_7d": change_7d,
                    "alpha_score": round(alpha, 1),
                    "tvl_growth": round(tvl_growth_score, 1),
                    "sector": round(sector_score, 1),
                    "chain_signal": round(chain_score, 1),
                    "yield_signal": round(yield_score, 1),
                })

        scored.sort(key=lambda x: x["alpha_score"], reverse=True)
        top = scored[:limit]

        output = "🎯 **Alpha Opportunities Today**\n\n"
        for idx, p in enumerate(top, 1):
            output += (
                f"{idx}. **{p['name']}** ({p['chain']} | {p['category']})\n"
                f"   🎯 Alpha Score: **{p['alpha_score']}/100**\n"
                f"   💰 TVL: ${p['tvl']:,.0f} | 7d: {p['change_7d']:+.2f}%\n"
                f"   📊 Growth: {p['tvl_growth']} | "
                f"Sector: {p['sector']} | "
                f"Chain: {p['chain_signal']} | "
                f"Yield: {p['yield_signal']}\n\n"
            )

        return output

    except Exception as e:
        logger.error(f"Failed to get alpha opportunities: {str(e)}")
        return f"Failed to calculate alpha opportunities: {str(e)}"
