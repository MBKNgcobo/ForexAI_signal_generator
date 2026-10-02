import pandas as pd


FILE = "data/historical/EURUSD_15m.csv"


def main():
    df = pd.read_csv(FILE)

    df["datetime"] = pd.to_datetime(
        df["datetime"],
        utc=True,
    )

    print("========== DATASET ==========")
    print(f"Rows: {len(df)}")
    print(f"Columns: {list(df.columns)}")

    print("\n========== DATE RANGE ==========")
    print(f"Start: {df['datetime'].min()}")
    print(f"End:   {df['datetime'].max()}")

    print("\n========== NULLS ==========")
    print(df.isnull().sum())

    print("\n========== DUPLICATES ==========")
    print(
        df["datetime"].duplicated().sum()
    )

    print("\n========== DATA TYPES ==========")
    print(df.dtypes)

    print("\n========== PRICE SUMMARY ==========")
    print(
        df[
            ["open", "high", "low", "close"]
        ].describe()
    )


if __name__ == "__main__":
    main()