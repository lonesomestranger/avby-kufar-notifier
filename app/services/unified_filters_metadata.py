UNIFIED_FILTERS = {
    "body_type": {
        "name_ru": "Тип кузова",
        "av_key": "body_type",
        "kufar_key": "crt",
        "options": [
            {"name": "Седан", "id": "sedan", "platform_values": {"av": 13, "kufar": 1}},
            {
                "name": "Универсал",
                "id": "wagon",
                "platform_values": {"av": 15, "kufar": 2},
            },
            {
                "name": "Хэтчбек",
                "id": "hatchback",
                "platform_values": {"av": [16, 17], "kufar": 3},
            },
            {
                "name": "Внедорожник",
                "id": "suv",
                "platform_values": {"av": [1, 2], "kufar": 5},
            },
            {
                "name": "Минивэн",
                "id": "minivan",
                "platform_values": {"av": 10, "kufar": 4},
            },
            {"name": "Купе", "id": "coupe", "platform_values": {"av": 4, "kufar": 6}},
        ],
    },
    "engine_type": {
        "name_ru": "Тип двигателя",
        "av_key": "engine_type",
        "kufar_key": "cre",
        "options": [
            {
                "name": "Бензин",
                "id": "petrol",
                "platform_values": {"av": 1, "kufar": 1},
            },
            {
                "name": "Дизель",
                "id": "diesel",
                "platform_values": {"av": 2, "kufar": 2},
            },
            {
                "name": "Электро",
                "id": "electro",
                "platform_values": {"av": 5, "kufar": 5},
            },
            {
                "name": "Гибрид",
                "id": "hybrid",
                "platform_values": {"av": [3, 4], "kufar": 3},
            },
        ],
    },
    "transmission_type": {
        "name_ru": "Коробка передач",
        "av_key": "transmission_type",
        "kufar_key": "crg",
        "options": [
            {
                "name": "Автоматическая",
                "id": "automatic",
                "platform_values": {"av": 1, "kufar": 1},
            },
            {
                "name": "Механическая",
                "id": "manual",
                "platform_values": {"av": 2, "kufar": 2},
            },
        ],
    },
    "drive_type": {
        "name_ru": "Привод",
        "av_key": "drive_type",
        "kufar_key": "crd",
        "options": [
            {
                "name": "Передний",
                "id": "front",
                "platform_values": {"av": 1, "kufar": 1},
            },
            {"name": "Задний", "id": "rear", "platform_values": {"av": 2, "kufar": 2}},
            {
                "name": "Полный",
                "id": "awd",
                "platform_values": {"av": [3, 4], "kufar": 3},
            },
        ],
    },
    "condition": {
        "name_ru": "Состояние",
        "av_key": "condition",
        "kufar_key": "cnd",
        "options": [
            {
                "name": "С пробегом",
                "id": "used",
                "platform_values": {"av": 1, "kufar": 1},
            },
            {"name": "Новый", "id": "new", "platform_values": {"av": 5, "kufar": 2}},
        ],
    },
}
