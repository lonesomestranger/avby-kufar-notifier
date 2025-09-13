import hashlib
import json


def get_search_hash(platform: str, params: dict):
    sorted_params = sorted(params.items())
    params_string = f"{platform}:{json.dumps(sorted_params)}"
    return hashlib.sha256(params_string.encode()).hexdigest()
