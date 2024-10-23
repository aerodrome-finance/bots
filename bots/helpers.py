import logging
import os
import sys
import urllib

from typing import List, Dict
from web3 import Web3
from async_lru import alru_cache


def is_address(value: str) -> bool:
    return Web3.is_address(value)


def cache_in_seconds(seconds: int):
    return alru_cache(ttl=seconds)


def normalize_address(address: str) -> str:
    return Web3.to_checksum_address(address.lower())


def load_local_json_as_string(relative_path: str) -> str:
    result = ""
    with open(
        os.path.join(os.path.dirname(os.path.realpath(__file__)), relative_path)
    ) as f:
        result = f.read()

    return result


def chunk(list_to_chunk: List, n: int):
    for i in range(0, len(list_to_chunk), n):
        yield list_to_chunk[i : i + n]


def amount_to_k_string(amount: float) -> str:
    """Turns 2000 to "2K" """
    return f"{round(amount/1000, 2)}K"


def format_currency(value: float, symbol: str = "$", prefix: bool = True) -> str:
    v = "{:0,.2f}".format(value)
    return f"{symbol}{v}" if prefix else f"{v} {symbol}"


def format_percentage(value: float) -> str:
    return "{:0,.2f} %".format(value)


def amount_to_m_string(amount: float) -> str:
    """Turns 2000000 to "2M" """
    return f"{round(amount/1000000, 2)}M"


def amount_to_string(amount: float) -> str:
    """Turns a large amount into a friendlier format"""
    if amount >= 1_000_000:
        return amount_to_m_string(amount)

    return amount_to_k_string(amount)


def make_app_url(base_url: str, path: str, params: Dict) -> str:
    return f"{base_url}{path}?{urllib.parse.urlencode(params)}"


# logging
LOGGING_LEVEL = os.getenv("LOGGING_LEVEL", "DEBUG")
LOGGING_HANDLER = logging.StreamHandler(sys.stdout)
LOGGING_HANDLER.setFormatter(
    logging.Formatter(
        "[{asctime}] [{levelname:<8}] {name}: {message}", "%Y-%m-%d %H:%M:%S", style="{"
    )
)
LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(LOGGING_HANDLER)
LOGGER.setLevel(LOGGING_LEVEL)
