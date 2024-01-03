# daily-stock-aggregator
Fetches the high, low, open, and close data for a given list of tickers after market close every week day. Keeps a rolling buffer of the most recent months data for every ticker and publishes this over zmq.
