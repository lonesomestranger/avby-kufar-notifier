import logging
import time

from curl_cffi.requests import AsyncSession


class CurrencyConverter:
    _usd_rate: float = 3.0
    _last_update_timestamp: float = 0
    _cache_ttl_seconds: int = 3600

    @classmethod
    async def get_usd_rate(cls) -> float:
        current_time = time.time()
        if current_time - cls._last_update_timestamp > cls._cache_ttl_seconds:
            logging.info("USD rate cache expired or empty. Fetching new rate...")
            try:
                url = "https://api.nbrb.by/exrates/rates/431"
                async with AsyncSession() as session:
                    response = await session.get(url, timeout=5)
                    response.raise_for_status()

                rate_data = response.json()
                rate = rate_data.get("Cur_OfficialRate")
                if rate:
                    cls._usd_rate = float(rate)
                    cls._last_update_timestamp = current_time
                    logging.info(
                        f"Successfully fetched and cached USD rate: {cls._usd_rate}"
                    )
                else:
                    raise ValueError("Rate not found in response")
            except Exception as e:
                logging.error(
                    f"Failed to fetch USD rate from NBRB API: {e}. Using stale/fallback rate."
                )

        return cls._usd_rate
