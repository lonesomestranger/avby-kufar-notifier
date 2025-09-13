import json
import logging
from datetime import datetime

from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession


class AvByFilterBuilder:
    def __init__(self, criteria: dict):
        self.criteria = criteria
        self.params = {"sort": "created_at.desc"}

    def build(self) -> dict:
        if self.criteria.get("brands[0][brand]"):
            self.params["brands[0][brand]"] = self.criteria["brands[0][brand]"]
            if self.criteria.get("brands[0][model]"):
                self.params["brands[0][model]"] = self.criteria["brands[0][model]"]

        if self.criteria.get("price_usd[min]"):
            self.params["price_usd[min]"] = self.criteria["price_usd[min]"]
        if self.criteria.get("price_usd[max]"):
            self.params["price_usd[max]"] = self.criteria["price_usd[max]"]

        multi_select_keys = [
            "body_type",
            "engine_type",
            "transmission_type",
            "drive_type",
        ]
        for key in multi_select_keys:
            if self.criteria.get(key):
                for i, value in enumerate(self.criteria[key]):
                    self.params[f"{key}[{i}]"] = value

        if self.criteria.get("condition"):
            self.params["condition"] = self.criteria["condition"]

        return self.params


class AvClient:
    def __init__(self):
        self.api_base_url = "https://api.av.by/offer-types/cars/catalog"
        self.search_url = "https://cars.av.by/filter"
        self.api_headers = {
            "accept": "application/json, text/plain, */*",
            "x-device-type": "web.desktop",
        }
        self.scrape_headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "accept-language": "ru-RU,ru",
        }

    async def get_brands(self):
        url = f"{self.api_base_url}/brand-items"
        try:
            async with AsyncSession(impersonate="chrome136") as session:
                response = await session.get(url, headers=self.api_headers)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logging.error(f"AV_CLIENT: FAILED to get brands. Error: {e}", exc_info=True)
            return []

    async def get_models(self, brand_id: int):
        url = f"{self.api_base_url}/brand-items/{brand_id}/models"
        try:
            async with AsyncSession(impersonate="chrome136") as session:
                response = await session.get(url, headers=self.api_headers)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logging.error(
                f"AV_CLIENT: FAILED to get models for brand {brand_id}. Error: {e}",
                exc_info=True,
            )
            return []

    async def find_ads(self, criteria: dict):
        builder = AvByFilterBuilder(criteria)
        params = builder.build()
        try:
            async with AsyncSession(impersonate="chrome136") as session:
                response = await session.get(
                    self.search_url, params=params, headers=self.scrape_headers
                )
                response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            next_data_script = soup.find("script", id="__NEXT_DATA__")
            if not next_data_script:
                logging.warning("AV_CLIENT: __NEXT_DATA__ script tag not found.")
                return []

            data = json.loads(next_data_script.string)
            adverts_data = (
                data.get("props", {})
                .get("initialState", {})
                .get("filter", {})
                .get("main", {})
                .get("adverts", [])
            )

            results = []
            for ad in adverts_data:
                try:

                    def get_prop(name):
                        for prop in ad.get("properties", []):
                            if prop.get("name") == name:
                                return prop.get("value")
                        return None

                    title_parts = [
                        get_prop("brand"),
                        get_prop("model"),
                        get_prop("generation"),
                    ]
                    title = " ".join(filter(None, title_parts))

                    param_parts = [
                        f"{ad.get('year', '')} г.",
                        get_prop("transmission_type"),
                        f"{get_prop('engine_capacity')} л."
                        if get_prop("engine_capacity")
                        else None,
                        get_prop("engine_type"),
                        get_prop("body_type"),
                        f"{get_prop('mileage_km'): ,} км".replace(",", " ")
                        if get_prop("mileage_km")
                        else None,
                    ]
                    params_text = ", ".join(filter(None, param_parts))

                    images = [
                        photo["big"]["url"]
                        for photo in ad.get("photos", [])
                        if photo.get("big") and photo["big"].get("url")
                    ]

                    results.append(
                        {
                            "url": ad.get("publicUrl"),
                            "ad_id": str(ad.get("id")),
                            "platform": "av",
                            "published_at": datetime.fromisoformat(
                                ad.get("refreshedAt")
                            ),
                            "data": {
                                "title": title,
                                "price_usd": ad.get("price", {})
                                .get("usd", {})
                                .get("amount", 0),
                                "price_byn": ad.get("price", {})
                                .get("byn", {})
                                .get("amount", 0),
                                "images": images,
                                "params": params_text,
                                "description": ad.get("description", ""),
                            },
                        }
                    )
                except Exception as e:
                    logging.warning(
                        f"AV_CLIENT: Could not parse an ad from JSON data. Ad ID: {ad.get('id')}. Error: {e}"
                    )
                    continue
            return results
        except Exception as e:
            logging.error(f"AV_CLIENT: FAILED to scrape ads. Error: {e}", exc_info=True)
            return []

    async def get_ad_details(self, url: str) -> dict | None:
        try:
            async with AsyncSession(impersonate="chrome136") as session:
                response = await session.get(url, headers=self.scrape_headers)
                response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            next_data_script = soup.find("script", id="__NEXT_DATA__")
            if not next_data_script:
                logging.warning(f"AV_CLIENT: __NEXT_DATA__ not found for url {url}")
                return None

            data = json.loads(next_data_script.string)
            ad = (
                data.get("props", {})
                .get("initialState", {})
                .get("advert", {})
                .get("advert")
            )
            if not ad:
                logging.warning(f"AV_CLIENT: Advert data not in JSON for url {url}")
                return None

            def get_prop(name):
                for prop in ad.get("properties", []):
                    if prop.get("name") == name:
                        return prop.get("value")
                return None

            title_parts = [
                get_prop("brand"),
                get_prop("model"),
                get_prop("generation"),
            ]
            title = " ".join(filter(None, title_parts))

            param_parts = [
                f"{ad.get('year', '')} г.",
                get_prop("transmission_type"),
                f"{get_prop('engine_capacity')} л."
                if get_prop("engine_capacity")
                else None,
                get_prop("engine_type"),
                get_prop("body_type"),
                f"{get_prop('mileage_km'): ,} км".replace(",", " ")
                if get_prop("mileage_km")
                else None,
            ]
            params_text = ", ".join(filter(None, param_parts))

            images = [
                photo["big"]["url"]
                for photo in ad.get("photos", [])
                if photo.get("big") and photo["big"].get("url")
            ]

            return {
                "url": ad.get("publicUrl"),
                "ad_id": str(ad.get("id")),
                "platform": "av",
                "published_at": datetime.fromisoformat(ad.get("refreshedAt")),
                "data": {
                    "title": title,
                    "price_usd": ad.get("price", {}).get("usd", {}).get("amount", 0),
                    "price_byn": ad.get("price", {}).get("byn", {}).get("amount", 0),
                    "images": images,
                    "params": params_text,
                    "description": ad.get("description", ""),
                    "options": [
                        opt["name"] for opt in ad.get("metadata", {}).get("options", [])
                    ],
                },
            }
        except Exception as e:
            logging.error(
                f"AV_CLIENT: FAILED to get ad details for {url}. Error: {e}",
                exc_info=True,
            )
            return None
