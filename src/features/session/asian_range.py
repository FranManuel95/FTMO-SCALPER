import pandas as pd


def add_asian_range(
    df: pd.DataFrame,
    session_start_h: int = 0,
    session_end_h: int = 7,
) -> pd.DataFrame:
    """
    Calcula el rango de la sesión asiática en el horario del broker.

    session_start_h / session_end_h son horas en el timezone del dato (broker time).
    Ejemplo broker UTC+2: session_start_h=2, session_end_h=9
    """
    df = df.copy()
    hour = df.index.hour

    # Manejo de wrap midnight: si start < end, sesión normal; si start > end, cruza medianoche
    if session_start_h < session_end_h:
        in_asian = (hour >= session_start_h) & (hour < session_end_h)
    else:
        in_asian = (hour >= session_start_h) | (hour < session_end_h)

    df["_in_asian"] = in_asian
    df["_date"] = df.index.date

    asian_data = df[df["_in_asian"]].groupby("_date").agg(
        asian_high=("high", "max"),
        asian_low=("low", "min"),
    )
    asian_data["asian_range"] = asian_data["asian_high"] - asian_data["asian_low"]
    asian_data["asian_mid"] = (asian_data["asian_high"] + asian_data["asian_low"]) / 2

    df = df.join(asian_data[["asian_high", "asian_low", "asian_range", "asian_mid"]], on="_date", how="left")
    df = df.drop(columns=["_in_asian", "_date"])

    return df.ffill()
