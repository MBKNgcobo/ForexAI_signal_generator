import asyncio


async def main():

    # ----------------------------------------------------------
    # This part depends on your existing MarketDataService.
    #
    # We are using it only to obtain real market data.
    # ----------------------------------------------------------

    print(
        "Quant Agent integration test"
    )

    print(
        "\nThe next step is to connect "
        "run_quant_agent() to your existing "
        "LangGraph market_data node."
    )


if __name__ == "__main__":
    asyncio.run(main())