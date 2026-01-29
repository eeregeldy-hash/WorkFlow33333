# predict.py

import os
import pandas as pd

from src.data_loader import load_historical_data, load_future_matches, load_team_strength
from src.calculator import CornerOddsCalculator
from src.validator import OddsValidator
from src.formatter import format_match_output


def load_form_history(path="data/history_5matches.csv"):
    """
    Твой формат:
      Date,HomeTeam,AwayTeam,FTHG,FTAG,HC,AC

    Мы приводим к внутреннему виду:
      Date,p1,p2,score_p1,score_p2
    где score_* = угловые.
    """
    df = pd.read_csv(path)
    df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")

    # нормализуем названия
    df["HomeTeam"] = df["HomeTeam"].astype(str).str.strip()
    df["AwayTeam"] = df["AwayTeam"].astype(str).str.strip()

    df["HC"] = pd.to_numeric(df["HC"], errors="coerce")
    df["AC"] = pd.to_numeric(df["AC"], errors="coerce")

    df = df.dropna(subset=["Date", "HomeTeam", "AwayTeam", "HC", "AC"])

    out = pd.DataFrame({
        "Date": df["Date"],
        "p1": df["HomeTeam"],
        "p2": df["AwayTeam"],
        "score_p1": df["HC"],
        "score_p2": df["AC"],
    })
    return out


def save_results(results, csv_path="reports/predictions.csv", excel_path="reports/predictions.xlsx"):
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)

    rows = []
    for r in results:
        odds = r["odds"]
        row = {
            "HomeTeam": r["home"],
            "AwayTeam": r["away"],
            "lambda_home": odds.get("lambda_home"),
            "lambda_away": odds.get("lambda_away"),
            "expected_total": odds.get("expected_total"),
            "favorite": odds.get("favorite", ""),

            "base_lambda_home": odds.get("base_lambda_home"),
            "base_lambda_away": odds.get("base_lambda_away"),
            "strength_home": odds.get("strength_home"),
            "strength_away": odds.get("strength_away"),
            "strength_ratio": odds.get("strength_ratio"),

            "form_home": odds.get("form_home"),
            "form_away": odds.get("form_away"),

            "anchor_line": odds.get("anchor_line"),
            "anchor_scale": odds.get("anchor_scale"),
        }

        # 1X2 corners
        o1x2 = odds.get("odds_1x2")
        if o1x2:
            row["Corners_P1"] = o1x2["P1"]
            row["Corners_X"] = o1x2["X"]
            row["Corners_P2"] = o1x2["P2"]

        # handicaps
        for team_key, team_data in odds.get("handicaps", {}).items():
            for subkey, subval in team_data.items():
                if subkey == "name":
                    row[f"Handicap_{team_key}_Group"] = subval
                else:
                    try:
                        row[f"Handicap_{team_key}_{subkey}"] = float(subval) if subval is not None else None
                    except (ValueError, TypeError):
                        row[f"Handicap_{team_key}_{subkey}"] = None

        # --- Тоталы ---
        for k, v in odds.get("totals", {}).items():
            try:
                row[f"Total_{k}"] = float(v) if v is not None else None
            except (ValueError, TypeError):
                row[f"Total_{k}"] = None

        # --- Индивидуальные тоталы дома ---
        for k, v in odds.get("individual_home", {}).items():
            try:
                row[f"Home_{k}"] = float(v) if v is not None else None
            except (ValueError, TypeError):
                row[f"Home_{k}"] = None

        # --- Индивидуальные тоталы гостей ---
        for k, v in odds.get("individual_away", {}).items():
            try:
                row[f"Away_{k}"] = float(v) if v is not None else None
            except (ValueError, TypeError):
                row[f"Away_{k}"] = None

        rows.append(row)

    df = pd.DataFrame(rows)
    df.to_csv(csv_path, index=False)
    print(f"\n💾 CSV: {csv_path}")

    try:
        df.to_excel(excel_path, index=False)
        print(f"💾 Excel: {excel_path}")
    except Exception as e:
        print(f"❌ Excel не сохранился: {e}")


def _safe_team(val) -> str:
    if val is None:
        return ""
    s = str(val).strip()
    if s.lower() == "nan":
        return ""
    return s


def main():
    print("=" * 80)
    print("         КАЛЬКУЛЯТОР КОЭФФИЦИЕНТОВ НА УГЛОВЫЕ")
    print("=" * 80)

    print("\n📂 Загрузка данных...")
    historical_df = load_historical_data("data/historical.csv")
    future_df = load_future_matches("data/future_matches.csv")
    print(f"✅ Загружено {len(historical_df)} исторических матчей")
    print(f"✅ Загружено {len(future_df)} будущих матчей")

    print("\n📌 Загрузка team_strength...")
    try:
        team_strength = load_team_strength("data/team_strength.csv")
        print(f"✅ team_strength: {len(team_strength)} команд")
    except Exception as e:
        team_strength = {}
        print(f"⚠️ team_strength отключен: {e}")

    print("\n📌 Загрузка формы (history_5matches)...")
    try:
        form_df = load_form_history("data/history_5matches.csv")
        print(f"✅ form_df: {len(form_df)} матчей")
    except Exception as e:
        form_df = None
        print(f"⚠️ форма отключена: {e}")

    calculator = CornerOddsCalculator()
    validator = OddsValidator()

    if len(future_df) == 0:
        print("⚠️ future_matches.csv пуст")
        return

    # определяем колонки
    if "HomeTeam" in future_df.columns and "AwayTeam" in future_df.columns:
        home_col, away_col = "HomeTeam", "AwayTeam"
    elif "p1" in future_df.columns and "p2" in future_df.columns:
        home_col, away_col = "p1", "p2"
    else:
        print(f"❌ В future_matches.csv нет колонок команд. Есть: {list(future_df.columns)}")
        return

    results = []
    total_matches = len(future_df)
    print(f"\n🔄 Обработка {total_matches} матч(ей)...\n")

    for idx, match in future_df.iterrows():
        home_team = _safe_team(match.get(home_col))
        away_team = _safe_team(match.get(away_col))

        if not home_team or not away_team:
            print(f"⚠️  Пропуск матча {idx+1}: пустые команды")
            continue

        print(f"[{idx+1}/{total_matches}] Расчёт: {home_team} vs {away_team}")

        try:
            match_odds = calculator.calculate_match_odds(
                historical_df,
                home_team,
                away_team,
                team_strength=team_strength,
                form_df=form_df,
            )
            warnings = validator.validate(match_odds)
            format_match_output(home_team, away_team, match_odds, warnings)

            results.append({
                "home": home_team,
                "away": away_team,
                "odds": match_odds,
                "warnings": warnings
            })
        except Exception as e:
            print(f"❌ ошибка матча {idx+1}: {e}")

    if results:
        print("\n" + "=" * 80)
        print(f"✅ Успешно обработано матчей: {len(results)}/{total_matches}")
        save_results(results, "reports/predictions.csv", "reports/predictions.xlsx")
        print("=" * 80)
    else:
        print("\n⚠️  Не удалось обработать ни одного матча")


if __name__ == "__main__":
    main()
