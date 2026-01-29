"""
Стандартная букмекерская сетка коэффициентов
Используется для нормализации коэффициентов к стандартным значениям
"""

from __future__ import annotations

# Букмекерская сетка: каждому коэффициенту соответствует обратный
BOOKMAKER_GRID = [
    (1.01, 11.56),
    (1.02, 10.28),
    (1.03, 9.25),
    (1.04, 8.41),
    (1.05, 7.71),
    (1.06, 7.12),
    (1.08, 6.61),
    (1.09, 6.17),
    (1.10, 5.78),
    (1.11, 5.44),
    (1.13, 5.14),
    (1.14, 4.87),
    (1.16, 4.63),
    (1.17, 4.40),
    (1.19, 4.20),
    (1.20, 4.02),
    (1.22, 3.85),
    (1.23, 3.70),
    (1.25, 3.56),
    (1.27, 3.43),
    (1.28, 3.30),
    (1.30, 3.19),
    (1.32, 3.08),
    (1.34, 2.98),
    (1.36, 2.89),
    (1.38, 2.80),
    (1.40, 2.72),
    (1.42, 2.64),
    (1.4453, 2.5694),
    (1.4683, 2.5000),
    (1.4919, 2.4342),
    (1.5164, 2.3718),
    (1.5417, 2.3125),
    (1.5678, 2.2561),
    (1.5948, 2.2024),
    (1.6228, 2.1512),
    (1.6518, 2.1023),
    (1.6818, 2.0556),
    (1.7130, 2.0109),
    (1.7453, 1.9681),
    (1.7788, 1.9271),
    (1.8137, 1.8878),
    (1.8500, 1.8500),
    (1.8878, 1.8137),
    (1.9271, 1.7788),
    (1.9681, 1.7453),
    (2.0109, 1.7130),
    (2.0556, 1.6818),
    (2.1023, 1.6518),
    (2.1512, 1.6228),
    (2.2024, 1.5948),
    (2.2561, 1.5678),
    (2.3125, 1.5417),
    (2.3718, 1.5164),
    (2.4342, 1.4919),
    (2.5000, 1.4683),
    (2.5694, 1.4453),
    (2.64, 1.42),
    (2.72, 1.40),
    (2.80, 1.38),
    (2.89, 1.36),
    (2.98, 1.34),
    (3.08, 1.32),
    (3.19, 1.30),
    (3.30, 1.28),
    (3.43, 1.27),
    (3.56, 1.25),
    (3.70, 1.23),
    (3.85, 1.22),
    (4.02, 1.20),
    (4.20, 1.19),
    (4.40, 1.17),
    (4.63, 1.16),
    (4.87, 1.14),
    (5.14, 1.13),
    (5.44, 1.11),
    (5.78, 1.10),
    (6.17, 1.09),
    (6.61, 1.08),
    (7.12, 1.06),
    (7.71, 1.05),
    (8.41, 1.04),
    (9.25, 1.03),
    (10.28, 1.02),
    (11.56, 1.01),
]


def normalize_to_grid(odds_value: float | None) -> float | None:
    """Нормализует коэффициент к ближайшему значению из букмекерской сетки."""
    if odds_value is None:
        return None
    odds_value = float(odds_value)
    if odds_value <= 1.0:
        return None

    all_odds = []
    for a, b in BOOKMAKER_GRID:
        all_odds.append(a)
        all_odds.append(b)

    all_odds = sorted(set(all_odds))
    return min(all_odds, key=lambda x: abs(x - odds_value))


def get_opposite_odds(odds_value: float | None) -> float | None:
    """Получает обратный коэффициент по букмекерской сетке."""
    norm = normalize_to_grid(odds_value)
    if norm is None:
        return None

    for o1, o2 in BOOKMAKER_GRID:
        if abs(o1 - norm) < 1e-6:
            return o2
        if abs(o2 - norm) < 1e-6:
            return o1
    return None


def _safe_prob(p) -> float:
    if p is None:
        return 0.0
    p = float(p)
    if p != p:  # NaN
        return 0.0
    return max(0.0, min(1.0, p))


def normalize_odds_pair(p1, p2, margin: float = 0.085, snap_to_grid: bool = True):
    """
    Нормализация 2 исходов (пара вероятностей) -> коэффициенты с маржой.
    По умолчанию ещё "снэпим" к сетке букмекера.
    """
    p1 = _safe_prob(p1)
    p2 = _safe_prob(p2)

    s = p1 + p2
    if s <= 0:
        return None, None

    # сумма вероятностей после маржи = 1 + margin
    k = (1.0 + float(margin)) / s
    p1n = p1 * k
    p2n = p2 * k

    eps = 1e-12
    o1 = 1.0 / max(p1n, eps)
    o2 = 1.0 / max(p2n, eps)

    if not snap_to_grid:
        return o1, o2

    o1g = normalize_to_grid(o1)
    if o1g is None:
        return None, None
    o2g = get_opposite_odds(o1g)
    if o2g is None:
        o2g = normalize_to_grid(o2)
    return o1g, o2g


def normalize_odds_triplet(p1, px, p2, margin: float = 0.085):
    """
    Нормализация 3 исходов (1X2) в коэффициенты с маржой.
    Здесь сетку НЕ применяем, потому что у сетки нет нормальной 1X2-структуры.
    """
    p1 = _safe_prob(p1)
    px = _safe_prob(px)
    p2 = _safe_prob(p2)

    s = p1 + px + p2
    if s <= 0:
        return None, None, None

    k = (1.0 + float(margin)) / s
    p1n = p1 * k
    pxn = px * k
    p2n = p2 * k

    eps = 1e-12
    o1 = 1.0 / max(p1n, eps)
    ox = 1.0 / max(pxn, eps)
    o2 = 1.0 / max(p2n, eps)
    return o1, ox, o2
