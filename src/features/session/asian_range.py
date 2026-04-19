import pandas as pd


def add_asian_range(
    df: pd.DataFrame,
    session_start_utc: str = "00:00",
    session_end_utc: str = "07:00",
) -> pd.DataFrame:
    """
    Calcula el rango de la sesión asiática y lo añade como columnas.
    El rango se calcula a partir de la sesión del día anterior y se propaga a las velas siguientes.
    """
    df = df.copy()
    df["_hour"] = df.index.hour
    df["_minute"] = df.index.minute
    df["_date"] = df.index.date

    start_h, start_m = map(int, session_start_utc.split(":"))
    end_h, end_m = map(int, session_end_utc.split(":"))

    def in_asian(row):
        total_mins = row["_hour"] * 60 + row["_minute"]
        start_mins = start_h * 60 + start_m
        end_mins = end_h * 60 + end_m
        return start_mins <= total_mins < end_mins

    df["_in_asian"] = df.apply(in_asian, axis=1)

    asian_data = df[df["_in_asian"]].groupby("_date").agg(
        asian_high=("high", "max"),
        asian_low=("low", "min"),
    )
    asian_data["asian_range"] = asian_data["asian_high"] - asian_data["asian_low"]
    asian_data["asian_mid"] = (asian_data["asian_high"] + asian_data["asian_low"]) / 2

    df = df.join(asian_data[["asian_high", "asian_low", "asian_range", "asian_mid"]], on="_date", how="left")
    df = df.drop(columns=["_hour", "_minute", "_date", "_in_asian"])

    return df.ffill()
