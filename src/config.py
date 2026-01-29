# src/config.py

CONFIG = {
    # общие
    "MARGIN": 0.085,
    "N_SIMULATIONS": 10000000,

    # strength
    "STRENGTH_POWER": 0.55,   # меньше = слабее влияние фаворита

    # form (последние N игр)
    "FORM_N_GAMES": 7,
    "FORM_BETA": 0.10,        # чувствительность формы
    "FORM_CLIP_LOW": 0.92,    # минимум фактора формы
    "FORM_CLIP_HIGH": 1.12,   # максимум фактора формы
    "FORM_DEBUG": False,

    # привязка к тоталу (мягкая)
    # если включишь ANCHOR_TOTAL_LINE, то модель слегка "подтягивает" общий λ к линии
    "ANCHOR_TOTAL_LINE": 9.5,     # например 9.5 или None чтобы выключить
    "ANCHOR_TARGET_OVER_PROB": 0.30,
    "ANCHOR_WEIGHT": 0.35,         # 0 = выкл влияние, 1 = жестко прибьёт линию

    # линии рынков (меняй как хочешь)
    "TOTAL_LINES": [8.5, 9.5, 10.5, 11.5],
    "IT_LINES": [3.5, 4.5, 5.5, 6.5],
    "HANDICAP_LINES": [0, 1.5, 2.5],  # для вывода: 0, +/-1.5, +/-2.5

    # защита λ
    "MIN_LAMBDA": 0.5,
    "MAX_LAMBDA": 20.0,
}
