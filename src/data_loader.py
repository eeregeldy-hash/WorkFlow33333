import pandas as pd

def load_team_strength(path="data/team_strength.csv"):
    df = pd.read_csv(path)
    return dict(zip(df["Team"], df["Strength"]))

def load_form_history(path="data/history_5matches.csv"):
    """
    Поддерживаем формат:
    Date,HomeTeam,AwayTeam,FTHG,FTAG,HC,AC
    и приводим к:
    Date,p1,p2,score_p1,score_p2
    """
    import pandas as pd

    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]

    required = {"Date", "HomeTeam", "AwayTeam", "HC", "AC"}
    if not required.issubset(set(df.columns)):
        raise KeyError(f"Нет нужных колонок. Есть: {list(df.columns)}")

    # приводим к единому виду
    df = df.rename(columns={
        "HomeTeam": "p1",
        "AwayTeam": "p2",
        "HC": "score_p1",
        "AC": "score_p2"
    })

    df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
    df["p1"] = df["p1"].astype(str).str.strip()
    df["p2"] = df["p2"].astype(str).str.strip()
    df["score_p1"] = pd.to_numeric(df["score_p1"], errors="coerce")
    df["score_p2"] = pd.to_numeric(df["score_p2"], errors="coerce")

    df = df.dropna(subset=["Date", "p1", "p2", "score_p1", "score_p2"])
    return df


def load_historical_data(filepath):
    """
    Загрузка исторических данных
    """
    df = pd.read_csv(filepath)

    # Проверка обязательных колонок
    required_cols = ['HomeTeam', 'AwayTeam', 'HC', 'AC']
    missing = [col for col in required_cols if col not in df.columns]

    if missing:
        raise ValueError(f"Отсутствуют колонки: {missing}")

    return df


def load_future_matches(filepath):
    """
    Загрузка будущих матчей
    """
    df = pd.read_csv(filepath)

    # Поддержка разных форматов колонок
    if 'home' in df.columns and 'away' in df.columns:
        df['HomeTeam'] = df['home']
        df['AwayTeam'] = df['away']

    return df