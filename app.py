# app.py
import os
import io
from contextlib import redirect_stdout

import pandas as pd
import streamlit as st

from src.data_loader import load_historical_data, load_future_matches, load_team_strength
from src.calculator import CornerOddsCalculator
from src.validator import OddsValidator
from src.formatter import format_match_output
from src.config import CONFIG


# ---------- Helpers ----------

def load_form_history_any(path: str) -> pd.DataFrame | None:
    """
    Поддерживает 2 формата:

    A) ТВОЙ СЕЙЧАС:
       Date,HomeTeam,AwayTeam,...,HC,AC
       (берем именно угловые HC/AC)

    B) СТАРЫЙ:
       Date,p1,p2,score_p1,score_p2

    Возвращаем унифицированный df:
       Date,p1,p2,score_p1,score_p2
    """
    if not path or not os.path.exists(path):
        return None

    df = pd.read_csv(path)

    # дата
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
    else:
        return None

    cols = set(df.columns)

    # Формат B
    if {"p1", "p2", "score_p1", "score_p2"}.issubset(cols):
        out = df[["Date", "p1", "p2", "score_p1", "score_p2"]].copy()
        out["p1"] = out["p1"].astype(str).str.strip()
        out["p2"] = out["p2"].astype(str).str.strip()
        out["score_p1"] = pd.to_numeric(out["score_p1"], errors="coerce")
        out["score_p2"] = pd.to_numeric(out["score_p2"], errors="coerce")
        out = out.dropna(subset=["Date", "p1", "p2", "score_p1", "score_p2"])
        return out

    # Формат A (твоя лига-таблица сезона)
    # Нужны HomeTeam, AwayTeam, HC, AC
    if {"HomeTeam", "AwayTeam", "HC", "AC"}.issubset(cols):
        out = df[["Date", "HomeTeam", "AwayTeam", "HC", "AC"]].copy()
        out = out.rename(
            columns={
                "HomeTeam": "p1",
                "AwayTeam": "p2",
                "HC": "score_p1",
                "AC": "score_p2",
            }
        )
        out["p1"] = out["p1"].astype(str).str.strip()
        out["p2"] = out["p2"].astype(str).str.strip()
        out["score_p1"] = pd.to_numeric(out["score_p1"], errors="coerce")
        out["score_p2"] = pd.to_numeric(out["score_p2"], errors="coerce")
        out = out.dropna(subset=["Date", "p1", "p2", "score_p1", "score_p2"])
        return out

    return None


def safe_team(x) -> str:
    if x is None:
        return ""
    s = str(x).strip()
    if s.lower() == "nan":
        return ""
    return s


def run_and_capture_output(home_team, away_team, calculator, validator, historical_df, team_strength, form_df):
    """
    Вызывает твой formatter и возвращает:
      - текст вывода
      - match_odds dict
      - warnings list
    """
    match_odds = calculator.calculate_match_odds(
        historical_df,
        home_team,
        away_team,
        team_strength=team_strength,
        form_df=form_df
    )
    warnings = validator.validate(match_odds)

    buf = io.StringIO()
    with redirect_stdout(buf):
        format_match_output(home_team, away_team, match_odds, warnings)
    return buf.getvalue(), match_odds, warnings


def markets_to_table(match_odds: dict) -> pd.DataFrame:
    """
    Собираем рынки в табличку (чтобы было удобно глазами смотреть).
    """
    rows = []

    # 1X2
    if match_odds.get("odds_1x2"):
        o = match_odds["odds_1x2"]
        rows.append({"market": "1X2", "line": "P1", "odds": o.get("P1")})
        rows.append({"market": "1X2", "line": "X", "odds": o.get("X")})
        rows.append({"market": "1X2", "line": "P2", "odds": o.get("P2")})

    # handicaps
    h = match_odds.get("handicaps", {})
    for side in ["HomeTeam", "AwayTeam"]:
        if side not in h:
            continue
        for k, v in h[side].items():
            if k == "name":
                continue
            rows.append({"market": f"AH ({side})", "line": k, "odds": v})

    # totals
    t = match_odds.get("totals", {})
    for k, v in t.items():
        rows.append({"market": "Totals", "line": k, "odds": v})

    # IT
    ih = match_odds.get("individual_home", {})
    ia = match_odds.get("individual_away", {})
    for k, v in ih.items():
        rows.append({"market": "IT Home", "line": k, "odds": v})
    for k, v in ia.items():
        rows.append({"market": "IT Away", "line": k, "odds": v})

    df = pd.DataFrame(rows)
    if not df.empty:
        df["odds"] = pd.to_numeric(df["odds"], errors="coerce")
        df = df.sort_values(["market", "line"], kind="stable").reset_index(drop=True)
    return df


# ---------- Streamlit UI ----------

st.set_page_config(page_title="Corners Odds App", layout="wide")

st.title("⚽ Corners Odds Calculator — App")

with st.sidebar:
    st.header("📂 Файлы данных")
    historical_path = st.text_input("historical.csv", "data/historical.csv")
    future_path = st.text_input("future_matches.csv", "data/future_matches.csv")
    strength_path = st.text_input("team_strength.csv", "data/team_strength.csv")
    form_path = st.text_input("history_5matches.csv", "data/history_5matches.csv")

    st.divider()
    st.header("⚙️ Параметры расчёта")
    margin = st.slider("Маржа", 0.0, 0.20, float(CONFIG.get("MARGIN", 0.085)), 0.005)
    n_sim = st.slider("Симуляции (Monte Carlo)", 1000, 200000, int(CONFIG.get("N_SIMULATIONS", 100000)), 1000)

    st.divider()
    st.header("🧩 Form / Anchor / Lines")

    # FORM
    form_n = st.slider("FORM_N_GAMES", 1, 20, int(CONFIG.get("FORM_N_GAMES", 5)), 1)
    form_beta = st.slider("FORM_BETA", 0.0, 0.50, float(CONFIG.get("FORM_BETA", 0.10)), 0.01)
    form_clip_low = st.slider("FORM_CLIP_LOW", 0.5, 1.0, float(CONFIG.get("FORM_CLIP_LOW", 0.92)), 0.01)
    form_clip_high = st.slider("FORM_CLIP_HIGH", 1.0, 2.0, float(CONFIG.get("FORM_CLIP_HIGH", 1.10)), 0.01)

    # TOTAL / IT LINES
    total_lines_str = st.text_input("TOTAL_LINES (через запятую)", ",".join(map(str, CONFIG.get("TOTAL_LINES", [8.5, 9.5, 10.5, 11.5]))))
    it_lines_str = st.text_input("IT_LINES (через запятую)", ",".join(map(str, CONFIG.get("IT_LINES", [3.5, 4.5, 5.5, 6.5]))))

    # Anchor (если используешь)
    anchor_weight = st.slider("ANCHOR_WEIGHT", 0.0, 1.0, float(CONFIG.get("ANCHOR_WEIGHT", 0.0)), 0.05)

    debug_form = st.checkbox("Печатать подробный Form debug (много текста)", value=False)

# применяем настройки в CONFIG (чтобы formatter использовал новые линии)
CONFIG["MARGIN"] = float(margin)
CONFIG["N_SIMULATIONS"] = int(n_sim)
CONFIG["FORM_N_GAMES"] = int(form_n)
CONFIG["FORM_BETA"] = float(form_beta)
CONFIG["FORM_CLIP_LOW"] = float(form_clip_low)
CONFIG["FORM_CLIP_HIGH"] = float(form_clip_high)
CONFIG["ANCHOR_WEIGHT"] = float(anchor_weight)

def parse_lines(s: str, fallback: list[float]) -> list[float]:
    try:
        vals = []
        for x in s.split(","):
            x = x.strip()
            if not x:
                continue
            vals.append(float(x))
        return vals if vals else fallback
    except Exception:
        return fallback

CONFIG["TOTAL_LINES"] = parse_lines(total_lines_str, [8.5, 9.5, 10.5, 11.5])
CONFIG["IT_LINES"] = parse_lines(it_lines_str, [3.5, 4.5, 5.5, 6.5])

# загружаем данные
load_error = None
historical_df = future_df = None
team_strength = {}
form_df = None

try:
    historical_df = load_historical_data(historical_path)
    future_df = load_future_matches(future_path)
except Exception as e:
    load_error = f"❌ Ошибка загрузки historical/future: {e}"

try:
    if strength_path and os.path.exists(strength_path):
        team_strength = load_team_strength(strength_path)
except Exception:
    team_strength = {}

try:
    form_df = load_form_history_any(form_path)
except Exception:
    form_df = None

if load_error:
    st.error(load_error)
    st.stop()

colA, colB = st.columns([1, 1], gap="large")

with colA:
    st.subheader("📋 Выбор матча")

    if future_df is None or future_df.empty:
        st.warning("future_matches.csv пустой или не загрузился.")
        st.stop()

    # определяем колонки команд
    if "HomeTeam" in future_df.columns and "AwayTeam" in future_df.columns:
        home_col, away_col = "HomeTeam", "AwayTeam"
    elif "p1" in future_df.columns and "p2" in future_df.columns:
        home_col, away_col = "p1", "p2"
    else:
        st.error(f"В future_matches.csv нет колонок команд. Есть: {list(future_df.columns)}")
        st.stop()

    future_df["_match"] = future_df.apply(
        lambda r: f"{safe_team(r.get(home_col))} vs {safe_team(r.get(away_col))}", axis=1
    )
    idx = st.selectbox("Матч", list(range(len(future_df))), format_func=lambda i: future_df.loc[i, "_match"])

    home_team = safe_team(future_df.loc[idx, home_col])
    away_team = safe_team(future_df.loc[idx, away_col])

    manual = st.checkbox("Ввести команды вручную", value=False)
    if manual:
        home_team = st.text_input("HomeTeam", home_team)
        away_team = st.text_input("AwayTeam", away_team)

    run_btn = st.button("✅ Рассчитать", type="primary")

with colB:
    st.subheader("ℹ️ Статус данных")
    st.write(f"Исторических матчей: **{len(historical_df)}**")
    st.write(f"Будущих матчей: **{len(future_df)}**")
    st.write(f"team_strength команд: **{len(team_strength)}**")
    st.write(f"form_df матчей: **{0 if form_df is None else len(form_df)}**")

if run_btn:
    if not home_team or not away_team:
        st.error("Не указаны команды.")
        st.stop()

    # калькулятор
    calculator = CornerOddsCalculator(margin=float(margin), n_simulations=int(n_sim))
    validator = OddsValidator()

    # если хочешь form debug в UI — включим его прямо в калькулятор
    # (работает только если в твоем calculator.py debug_print берется из CONFIG или аргумента;
    #  если нет — просто игнорируется)
    try:
        CONFIG["FORM_DEBUG_PRINT"] = bool(debug_form)
    except Exception:
        pass

    text, match_odds, warnings = run_and_capture_output(
        home_team, away_team,
        calculator, validator,
        historical_df, team_strength, form_df
    )

    st.divider()
    st.subheader("🖨️ Вывод (как в консоли)")
    st.code(text, language="text")

    st.subheader("📊 Таблица рынков")
    tbl = markets_to_table(match_odds)
    st.dataframe(tbl, use_container_width=True)

    st.subheader("🧠 Debug (лямбды/формы/сила)")
    st.json({
        "lambda_home": match_odds.get("lambda_home"),
        "lambda_away": match_odds.get("lambda_away"),
        "expected_total": match_odds.get("expected_total"),
        "favorite": match_odds.get("favorite"),
        "strength_home": match_odds.get("strength_home"),
        "strength_away": match_odds.get("strength_away"),
        "strength_ratio": match_odds.get("strength_ratio"),
        "form_home": match_odds.get("form_home"),
        "form_away": match_odds.get("form_away"),
        "anchor_line": match_odds.get("anchor_line"),
        "anchor_scale": match_odds.get("anchor_scale"),
    })
