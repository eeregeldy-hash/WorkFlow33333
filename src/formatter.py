# src/formatter.py

from src.config import CONFIG


def _fmt_num(x, digits=2):
    """
    Безопасный формат чисел:
    - None -> '—'
    - нечисло/ошибка -> '—'
    """
    if x is None:
        return "—"
    try:
        return f"{float(x):.{digits}f}"
    except Exception:
        return "—"


def _fmt_num_g(x, sig=4):
    """
    Безопасный компактный формат (как 6.4g):
    - None -> '—'
    """
    if x is None:
        return "—"
    try:
        return f"{float(x):.{sig}g}"
    except Exception:
        return "—"


def format_match_output(home_team, away_team, match_odds, warnings):
    print("\n" + "=" * 80)
    print(f"Матч: {home_team} vs {away_team}")
    print(f"λ_home: {_fmt_num(match_odds.get('lambda_home'), 2)}  |  λ_away: {_fmt_num(match_odds.get('lambda_away'), 2)}")
    print(f"Ожидаемо углов: {_fmt_num(match_odds.get('expected_total'), 2)}")

    # фаворит
    favorite = match_odds.get("favorite", "draw")
    if favorite == "home":
        print(f"⭐ Фаворит: {home_team} (дома)")
    elif favorite == "away":
        print(f"⭐ Фаворит: {away_team} (гости)")
    else:
        print("⚖️  Примерно равные команды")

    # debug strength
    if "strength_home" in match_odds:
        print(
            f"🔧 Strength: {home_team}={_fmt_num(match_odds.get('strength_home', 1.0), 2)} | "
            f"{away_team}={_fmt_num(match_odds.get('strength_away', 1.0), 2)} | "
            f"ratio={_fmt_num(match_odds.get('strength_ratio', 1.0), 3)}"
        )
        print(
            f"   base λ: {_fmt_num(match_odds.get('base_lambda_home', 0.0), 2)} / "
            f"{_fmt_num(match_odds.get('base_lambda_away', 0.0), 2)}"
        )

    # debug form
    if "form_home" in match_odds:
        print(
            f"🧩 Form({CONFIG.get('FORM_N_GAMES', 5)}): {home_team}={_fmt_num(match_odds.get('form_home', 1.0), 3)} | "
            f"{away_team}={_fmt_num(match_odds.get('form_away', 1.0), 3)}"
        )

    # anchor debug (если используешь)
    if match_odds.get("anchor_line") is not None:
        print(
            f"🧷 Anchor total {match_odds.get('anchor_line')}  scale={_fmt_num(match_odds.get('anchor_scale', 1.0), 3)} "
            f"(weight={CONFIG.get('ANCHOR_WEIGHT', 0.0)})"
        )

    print("=" * 80)

    # 1X2 corners
    odds_1x2 = match_odds.get("odds_1x2")
    if odds_1x2:
        print("\n🎯 1X2 (угловые):")
        print(
            f"  P1: {_fmt_num(odds_1x2.get('P1'), 2)}   "
            f"X: {_fmt_num(odds_1x2.get('X'), 2)}   "
            f"P2: {_fmt_num(odds_1x2.get('P2'), 2)}"
        )

    # Форы (как ты хотел: 1-я команда / 2-я команда)
    print("\n📊 АЗИАТСКИЕ ФОРЫ:")
    handicaps = match_odds.get("handicaps", {})

    order = ["F(-2.5)", "F(-1.5)", "F(0)", "F(+1.5)", "F(+2.5)"]

    # ВАЖНО: фиксированный порядок: HomeTeam, AwayTeam
    for team_key in ["HomeTeam", "AwayTeam"]:
        if team_key not in handicaps:
            continue
        team_info = handicaps[team_key]
        team_title = team_info.get("name", team_key)

        print(f"\n  {team_title}:")
        for k in order:
            if k in team_info:
                v = team_info.get(k)
                # печатаем "—" если None
                out = _fmt_num(v, 2)
                print(f"    {k:<15} {out:>6}")

    # Totals
    print("\n📈 ТОТАЛЫ:")
    totals = match_odds.get("totals", {})
    for line in CONFIG.get("TOTAL_LINES", [8.5, 9.5, 10.5, 11.5]):
        over_key = f"Over_{line}"
        under_key = f"Under_{line}"
        if over_key in totals and under_key in totals:
            over_val = _fmt_num_g(totals.get(over_key), 4)
            under_val = _fmt_num_g(totals.get(under_key), 4)
            print(f"  {line:>4}  Больше: {over_val:>6}  |  Меньше: {under_val:>6}")

    # IT Home
    print(f"\n🏠 ИНДИВИДУАЛЬНЫЙ ТОТАЛ ({home_team}):")
    ind_home = match_odds.get("individual_home", {})
    for line in CONFIG.get("IT_LINES", [3.5, 4.5, 5.5, 6.5]):
        ok = f"IT_{line}_over"
        uk = f"IT_{line}_under"
        if ok in ind_home and uk in ind_home:
            over_val = _fmt_num_g(ind_home.get(ok), 4)
            under_val = _fmt_num_g(ind_home.get(uk), 4)
            print(f"  ИТ{line}  Больше: {over_val:>6}  |  Меньше: {under_val:>6}")

    # IT Away
    print(f"\n✈️  ИНДИВИДУАЛЬНЫЙ ТОТАЛ ({away_team}):")
    ind_away = match_odds.get("individual_away", {})
    for line in CONFIG.get("IT_LINES", [3.5, 4.5, 5.5, 6.5]):
        ok = f"IT_{line}_over"
        uk = f"IT_{line}_under"
        if ok in ind_away and uk in ind_away:
            over_val = _fmt_num_g(ind_away.get(ok), 4)
            under_val = _fmt_num_g(ind_away.get(uk), 4)
            print(f"  ИТ{line}  Больше: {over_val:>6}  |  Меньше: {under_val:>6}")

    # warnings
    if warnings:
        print("\n⚠️  ПРЕДУПРЕЖДЕНИЯ:")
        for w in warnings:
            print(f"  {w}")
    else:
        print("\n✅ Все коэффициенты прошли проверку")

    print("=" * 80)
