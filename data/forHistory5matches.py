import pandas as pd

df = pd.read_csv("E1.csv")

df = df[["Date", "HomeTeam", "AwayTeam", "HC", "AC"]]

df.to_csv("history_5matches.csv", index=False, encoding="utf-8")

print(df.head())
