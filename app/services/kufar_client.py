import asyncio
import json
import logging
import os
import random
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession

from app.core.settings import settings

from .filter_builder import KufarFilterBuilder


class KufarClient:
    def __init__(self):
        self.paginated_url = (
            "https://api.kufar.by/search-api/v2/search/rendered-paginated"
        )
        self.poleposition_url = "https://api.kufar.by/search-api/v2/search/poleposition"
        self.nodes_url = "https://api.kufar.by/catalog/v1/nodes"
        self.ad_public_api_url = "https://api.kufar.by/ads-pub/ads/{ad_id}"
        self.headers = {
            "accept": "application/json",
            "accept-language": "ru-RU,ru",
            "origin": "https://auto.kufar.by",
            "referer": "https://auto.kufar.by/",
        }

    async def get_raw_brands(self):
        params = {"tag": "category_2010", "view": "taxonomy", "with-content": "true"}
        try:
            async with AsyncSession(impersonate="chrome136") as session:
                response = await session.get(
                    self.nodes_url, params=params, headers=self.headers
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logging.error(
                f"KUFAR_CLIENT: FAILED to get raw brands. Error: {e}", exc_info=True
            )
            return []

    async def get_raw_models(self, brand_slug: str):
        params = {"tag": brand_slug, "view": "taxonomy", "with-content": "true"}
        try:
            async with AsyncSession(impersonate="chrome136") as session:
                response = await session.get(
                    self.nodes_url, params=params, headers=self.headers
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logging.error(
                f"KUFAR_CLIENT: FAILED to get raw models for {brand_slug}. Error: {e}",
                exc_info=True,
            )
            return []

    async def get_ad_details_by_url(self, url: str) -> dict | None:
        match = re.search(r"/(?:item|vi)/(\d+)", url)
        if not match:
            logging.warning(f"KUFAR_CLIENT: Could not extract ad ID from URL: {url}")
            return None
        ad_id = match.group(1)

        try:
            async with AsyncSession(impersonate="chrome136") as session:
                ad_raw = None
                try:
                    api_url = self.ad_public_api_url.format(ad_id=ad_id)
                    response = await session.get(api_url, headers=self.headers)
                    response.raise_for_status()
                    ad_raw = response.json()
                except Exception:
                    logging.warning(
                        f"KUFAR_CLIENT: API call failed for ad {ad_id}. Falling back to HTML parsing."
                    )

                page_response = await session.get(url, impersonate="chrome136")
                page_response.raise_for_status()
                soup = BeautifulSoup(page_response.text, "html.parser")

                return await self.get_ad_details(session, ad_raw, soup, ad_id, url)
        except Exception as e:
            logging.error(
                f"KUFAR_CLIENT: FAILED to get ad details for {url}. Error: {e}",
                exc_info=True,
            )
            return None

    async def get_ad_details(
        self,
        session: AsyncSession,
        ad_raw: dict | None,
        soup: BeautifulSoup | None = None,
        ad_id_from_url: str | None = None,
        ad_link_from_url: str | None = None,
    ):
        ad_id = str(ad_raw.get("ad_id")) if ad_raw else ad_id_from_url
        ad_link = ad_raw.get("ad_link") if ad_raw else ad_link_from_url

        if not ad_id or not ad_link:
            return None

        try:
            if not soup:
                await asyncio.sleep(random.uniform(0.5, 1.5))
                page_response = await session.get(ad_link, impersonate="chrome136")
                page_response.raise_for_status()
                soup = BeautifulSoup(page_response.text, "html.parser")

            next_data_script = soup.find("script", id="__NEXT_DATA__")
            if next_data_script:
                data = json.loads(next_data_script.string)
                ad_data_json = (
                    data.get("props", {})
                    .get("initialState", {})
                    .get("adView", {})
                    .get("data", {})
                )
            else:
                ad_data_json = {}

            params_str = "Не удалось загрузить"
            if ad_data_json.get("adParams"):
                param_parts = [
                    p["vl"]
                    for p in ad_data_json["adParams"].values()
                    if p["pl"]
                    in ["Год", "Тип кузова", "Объем, л", "Тип двигателя", "Пробег, км"]
                ]
                params_str = ", ".join(filter(None, param_parts))

            description = ad_data_json.get("body", "")
            if not description:
                desc_block = soup.find("div", attrs={"data-name": "description-block"})
                if desc_block:
                    desc_content = desc_block.find(
                        "div", class_=lambda x: x and "description_content" in x
                    )
                    if desc_content:
                        description = desc_content.get_text(strip=True)

            phone_number = None
            if settings.kufar_bearer_tokens:
                token = random.choice(settings.kufar_bearer_tokens)
                phone_url = f"https://api.kufar.by/search-api/v2/item/{ad_id}/phone"
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Origin": "https://auto.kufar.by",
                    "Referer": ad_link,
                }
                await asyncio.sleep(random.uniform(0.5, 1.5))
                phone_response = await session.get(
                    phone_url, headers=headers, impersonate="chrome136"
                )
                if phone_response.status_code == 200:
                    phone_number = phone_response.json().get("phone")

            images = ad_data_json.get("images", {}).get("gallery", [])[:10]

            title = ad_data_json.get("subject", "Нет заголовка")
            price_usd = 0
            price_byn = 0

            if ad_raw:
                price_usd = int(ad_raw.get("price_usd", 0)) // 100
                price_byn = int(ad_raw.get("price_byn", 0)) // 100
            elif ad_data_json:
                price_usd_str = ad_data_json.get("priceUsd", "0")
                price_byn_str = ad_data_json.get("price", "0")
                price_usd = int("".join(filter(str.isdigit, price_usd_str)))
                price_byn = int("".join(filter(str.isdigit, price_byn_str)))
            else:
                price_usd_tag = soup.find(
                    "span", class_=lambda c: c and "secondary" in c
                )
                price_byn_tag = soup.find("span", class_=lambda c: c and "main" in c)
                if price_usd_tag:
                    price_usd = int(
                        "".join(filter(str.isdigit, price_usd_tag.get_text(strip=True)))
                    )
                if price_byn_tag:
                    price_byn = int(
                        "".join(filter(str.isdigit, price_byn_tag.get_text(strip=True)))
                    )

            published_at_str = ad_data_json.get("date")
            published_at = (
                datetime.fromisoformat(published_at_str.replace("Z", "+00:00"))
                if published_at_str
                else datetime.now(timezone.utc)
            )

            return {
                "url": ad_link,
                "ad_id": ad_id,
                "platform": "kufar",
                "published_at": published_at,
                "data": {
                    "title": title,
                    "price_usd": price_usd,
                    "price_byn": price_byn,
                    "images": images,
                    "params": params_str,
                    "description": description,
                    "phone": phone_number,
                },
            }
        except Exception as e:
            logging.error(
                f"KUFAR_CLIENT: Could not process ad {ad_id}. Error: {e}",
                exc_info=True,
            )
            return None

    async def _fetch_ads_from_endpoint(self, session, url, api_params, headers):
        try:
            response = await session.get(url, params=api_params, headers=headers)
            response.raise_for_status()
            return response.json().get("adverts") or response.json().get("ads", [])
        except Exception as e:
            logging.error(f"KUFAR_CLIENT: Failed to fetch from {url}. Error: {e}")
            return []

    async def find_ads_raw(self, params: dict):
        base_params = {
            "cat": "2010",
            "cur": "USD",
            "lang": "ru",
            "sort": "lst.d",
        }

        if params.get("brand_slug"):
            base_params["cbnd2"] = params["brand_slug"]
        if params.get("model_slug"):
            base_params["cmdl2"] = params["model_slug"]
        if params.get("price_usd[max]"):
            base_params["prc"] = f"r:0,{params['price_usd[max]']}"

        filter_builder = KufarFilterBuilder(params.get("filters", {}))
        base_params.update(filter_builder.build())

        request_headers = self.headers.copy()
        request_headers["x-searchid"] = os.urandom(18).hex()

        paginated_params = {**base_params, "size": 40}
        poleposition_params = {**base_params, "size": 5}

        try:
            async with AsyncSession(impersonate="chrome136") as session:
                tasks = [
                    self._fetch_ads_from_endpoint(
                        session, self.paginated_url, paginated_params, request_headers
                    ),
                    self._fetch_ads_from_endpoint(
                        session,
                        self.poleposition_url,
                        poleposition_params,
                        request_headers,
                    ),
                ]
                all_ads_raw_lists = await asyncio.gather(*tasks)

                unique_ads_raw = {}
                for ad_list in all_ads_raw_lists:
                    for ad_data in ad_list:
                        ad_id = ad_data.get("ad_id")
                        if ad_id:
                            unique_ads_raw[ad_id] = ad_data

                return list(unique_ads_raw.values())
        except Exception as e:
            logging.error(f"KUFAR_CLIENT: FAILED to get ads. Error: {e}", exc_info=True)
            return []
