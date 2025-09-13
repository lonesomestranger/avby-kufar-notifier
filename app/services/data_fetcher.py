import logging

from .av_client import AvClient
from .kufar_client import KufarClient

av_brands_cache = []
kufar_brands_cache = []
av_models_cache = {}
kufar_models_cache = {}


async def fetch_and_cache_data():
    global av_brands_cache, kufar_brands_cache
    av_client = AvClient()
    kufar_client = KufarClient()

    logging.info("FETCHER: Fetching AV.BY brands...")
    av_brands_raw = await av_client.get_brands()
    if av_brands_raw:
        av_brands_cache = sorted(av_brands_raw, key=lambda x: x["name"])
        logging.info(f"FETCHER: Cached {len(av_brands_cache)} AV.BY brands.")
    else:
        logging.error("FETCHER: CRITICAL - Failed to fetch AV.BY brands.")

    logging.info("FETCHER: Fetching Kufar brands...")
    kufar_brands_raw = await kufar_client.get_raw_brands()
    if kufar_brands_raw and av_brands_cache:
        av_brand_map = {b["name"].lower(): b for b in av_brands_cache}
        unified_kufar_brands = []
        for kufar_brand in kufar_brands_raw:
            name = kufar_brand.get("labels", {}).get("ru")
            if not name:
                continue

            av_brand = av_brand_map.get(name.lower())
            if av_brand:
                unified_kufar_brands.append(
                    {"id": av_brand["id"], "name": name, "slug": kufar_brand["value"]}
                )
        kufar_brands_cache = sorted(unified_kufar_brands, key=lambda x: x["name"])
        logging.info(
            f"FETCHER: Unified and cached {len(kufar_brands_cache)} Kufar brands."
        )
    else:
        logging.error("FETCHER: CRITICAL - Failed to fetch or unify Kufar brands.")


async def get_brands(platform: str):
    if not av_brands_cache or not kufar_brands_cache:
        await fetch_and_cache_data()

    if platform == "av":
        return av_brands_cache
    if platform == "kufar":
        return kufar_brands_cache
    if platform == "both":
        kufar_brand_ids = {b["id"] for b in kufar_brands_cache}
        return [b for b in av_brands_cache if b["id"] in kufar_brand_ids]
    return []


async def get_models_for_brand(platform: str, brand_id: int, brand_slug: str):
    if platform == "av":
        if brand_id in av_models_cache:
            return av_models_cache[brand_id]
        client = AvClient()
        models = await client.get_models(brand_id)
        if models:
            av_models_cache[brand_id] = models
        return models

    if platform == "kufar":
        if brand_slug in kufar_models_cache:
            return kufar_models_cache[brand_slug]
        client = KufarClient()
        raw_models = await client.get_raw_models(brand_slug)

        av_models_for_brand = await get_models_for_brand("av", brand_id, brand_slug)
        av_model_map = {m["name"].lower(): m for m in av_models_for_brand}

        unified_models = []
        for kufar_model in raw_models:
            name = kufar_model.get("labels", {}).get("ru")
            if not name:
                continue
            av_model = av_model_map.get(name.lower())
            if av_model:
                unified_models.append(
                    {"id": av_model["id"], "name": name, "slug": kufar_model["value"]}
                )
        if unified_models:
            kufar_models_cache[brand_slug] = unified_models
        return unified_models

    if platform == "both":
        av_models = await get_models_for_brand("av", brand_id, brand_slug)
        kufar_models = await get_models_for_brand("kufar", brand_id, brand_slug)
        if not (av_models and kufar_models):
            return av_models or kufar_models

        kufar_model_ids = {m["id"] for m in kufar_models}
        return [m for m in av_models if m["id"] in kufar_model_ids]

    return []
