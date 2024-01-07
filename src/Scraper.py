################################################################################
###                                 Imports                                  ###
################################################################################
#Standard imports
import math
import time
import datetime
import os
import logging
import argparse
import pickle
import base64

#Third party imports
import yfinance as yf
import requests
import zmq
import pytz
import numpy as np

################################################################################
###                                Constants                                 ###
################################################################################
MARKET_TICKER_LIST_URL = "https://raw.githubusercontent.com/rreichel3/" \
					   + "US-Stock-Symbols/main/all/all_tickers.txt"
DEFAULT_DAILY_TICKERS = [
	"BTC-USD",
	"ETH-USD",
	"USDT-USD",
	"BNB-USD",
	"SOL-USD",
	"XRP-USD",
	"USDC-USD",
	"STETH-USD",
	"ADA-USD",
	"AVAX-USD",
	"DOGE-USD",
	"TRX-USD",
	"DOT-USD",
	"WTRX-USD",
	"MATIC-USD",
	"LINK-USD",
	"TON11419-USD",
	"WBTC-USD",
	"SHIB-USD",
	"ICP-USD",
	"WEOS-USD",
	"DAI-USD",
	"LTC-USD",
	"BCH-USD",
	"UNI7083-USD"
]

YAHOO_FINANCE_REQ_PER_HOUR = 2000
YAHOO_FINANCE_REQ_PER_SEC = YAHOO_FINANCE_REQ_PER_HOUR / 3600
YF_SEC_BETWEEN_REQS = math.ceil(1 / YAHOO_FINANCE_REQ_PER_SEC)

PUB_PORT = 21000

EASTERN_TZ = pytz.timezone("US/Eastern")
MARKET_OPEN_TIME = datetime.time(hour=9, minute=30, second=0)
MARKET_CLOSE_TIME = datetime.time(hour=16, minute=0, second=0)
DT_FMT = "%Y-%m-%d_%H:%M:%S"

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

NP_LOCALIZE = np.vectorize(lambda x: x.astimezone(EASTERN_TZ))

################################################################################
###                                Class Def                                 ###
################################################################################
class Scraper:
	"""
	Scrapes desired security data from yahoo finance at the desired rate while 
	abiding by yahoo finance's rate limits and publishes said new data over zmq 
	for subscribers to consume. There are 2 kinds of data: market data (data 
	that only gets updated when the US markets are open, like regular stocks 
	such as AAPL) and daily data (data that gets updated all the time regardless 
	if the US market is open, like BTC). You must provide a list of both market 
	and daily tickers that you want to scrape. You can put any ticker in either 
	category. If you pull in data and it hasn't updated since your last pull it 
	will just ignore it, but it will eat up time and resources. So the goal of 
	separating the two types of data updates is to make things more efficient. 
	So for something like bitcoin (BTC) that you can trade on a Saturday you 
	may want to put that in the daily category. For something like AAPL, sure 
	there is pre-market and after hours data available, but if you only plan on 
	trading AAPL during market hours (by choice or by limitation of your 
	broker) then put it in the market category. There are a few timeframes you 
	can operate on: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1d. They pull in data 
	every 1/2/5/15/30/60/90 minutes and 1 day respectively. For the minute 
	scale data the first update will happen that many minutes after market open. 
	For the day scale data it will happen at 4 pm every day (market close). The 
	data pull will actually be delayed by 30 seconds from the previous time 
	mentioned so ensure the data is available.

	Got default list of stock symbols from here: 
	https://github.com/rreichel3/US-Stock-Symbols/blob/main/all/all_tickers.txt

	:param timeframe: how often to fetch data: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 
		or 1d
	:type timeframe: string
	:param market_tickers: list of market tickers to pull data for. This can be 
		a list of strings, the path to a text file containing the tickers 
		separated by a newline character, or left as None to attempt to pull 
		the list from the internet
	:type market_tickers: list of strings, string, or None
	:param daily_tickers: list of daily tickers to pull data for. This can be 
		a list of strings, the path to a text file containing the tickers 
		separated by a newline character, or left as is to use the default list
	:type market_tickers: list of strings, string
	:param zmq_ctx: zmq context to use, will create one if left as none
	:type zmq_ctx: zmq.Context
	"""
	############################################################################
	def __init__(self, timeframe="1d", market_tickers=None, 
				 daily_tickers=DEFAULT_DAILY_TICKERS, zmq_ctx=None):
		#Get market ticker symbols and allocate array for ticker objects and 
		#previous data
		LOGGER.debug("Loading market tickers")
		self.market_ticker_strs = self.get_ticker_list(market_tickers, LOGGER)
		self.market_tickers = [None for x in self.market_ticker_strs]
		self.market_prev_update = [None for x in self.market_ticker_strs]
		self.n_market_tickers = len(self.market_ticker_strs)
		secs_to_update_all = self.n_market_tickers * YF_SEC_BETWEEN_REQS
		LOGGER.info("Have %d market tickers. Will take about %d seconds (%.2f" \
					+ " hours) to update all", self.n_market_tickers, 
					secs_to_update_all, secs_to_update_all / 3600)

		#Get daily ticker symbols and allocate array for ticker objects and 
		#previous data
		LOGGER.debug("Loading daily tickers")
		self.daily_ticker_strs = self.get_ticker_list(daily_tickers, LOGGER)
		self.daily_tickers = [None for x in self.daily_ticker_strs]
		self.daily_prev_update = [None for x in self.market_ticker_strs]
		self.n_daily_tickers = len(self.daily_ticker_strs)
		secs_to_update_all = self.n_daily_tickers * YF_SEC_BETWEEN_REQS
		LOGGER.info("Have %d daily tickers. Will take about %d seconds (%.2f" \
					+ " hours) to update all", self.n_daily_tickers, 
					secs_to_update_all, secs_to_update_all / 3600)

		#Saving timing parameters
		valid_options = ['1m', '2m', '5m', '15m', '30m', '60m', '90m', '1d']
		if timeframe not in valid_options:
			raise ValueError("Invalid timeframe argument. Options are: " \
							 + "%s" % ", ".join(valid_options))
		self.timeframe = timeframe
		LOGGER.debug("Operating on %s timeframe" % self.timeframe)
		self.have_done_mkt_close_pull = False

		#Setup zmq publisher
		if zmq_ctx is None:
			self.zmq_ctx = zmq.Context()
		else:
			self.zmq_ctx = zmq_ctx
		self.sock = self.zmq_ctx.socket(zmq.PUB)
		self.sock.bind("tcp://*:%d" % PUB_PORT)
		LOGGER.info("Started zmq publisher on port %d" % PUB_PORT)

	############################################################################
	def get_ticker_list(self, ticker_list=None, logger=None):
		"""
		Loads a list of tickers from a file, from the internet, or from a list

		:param ticker_list: list of strings representing tickers, path to file 
			of tickers separated by newline to load, or left as None to 
			download list of stocks from the internet
		:type ticker_list: list, string, or None
		:param logger: logger to log to, won't log if left as None
		:type logger: logging.Logger
		:return: sorted list of strings representing tickers with any duplicates 
			removed
		:rtype: list
		"""
		#Load list of tickers
		if not isinstance(ticker_list, list):
			#Is either the path to a file or was left as None to pull from the 
			#internet
			if ticker_list is None:
				#Pull from the internet
				if logger is not None:
					logger.debug("Pulling ticker list from internet")
				resp = requests.get(TICKER_LIST_URL)
				contents = resp.text
			else:
				#Load from file
				if logger is not None:
					logger.debug("Loading ticker list from file")
				with open(ticker_list, 'r') as fh:
					contents = fh.read()

			#At this point we have a string containing all the tickers 
			#separated by newline characters so extract tickers into a list
			ticker_list = contents.strip().split("\n")
		else:
			if logger is not None:
				logger.debug("Ticker list provided as list of strings")

		#By this point we have a list of strings representing tickers. Cast it 
		#to a set and then back to a list to make sure there are no repeats
		ticker_strs = list(set(ticker_list))
		if logger is not None:
			logger.debug("Found %d tickers in list" % len(ticker_strs))

		#Return tickers
		return sorted(ticker_strs)

	############################################################################
	def _publish(self, ticker_str, dates, prices):
		"""
		Publishes the given data over zmq

		:param ticker_str: ticker symbol
		:type ticker_str: str
		:param dates: numpy array of datetimes or a single datetime
		:type dates: ndarray or datetime
		:param prices: Nx5 or 5 element numpy array of prices and volumes
		:type prices: ndarray
		"""
		#Check if we got a collection of data points or a single data point
		if isinstance(dates, datetime.datetime):
			#Got a single data point so publish that
			payload = (
				ticker_str,
				base64.b64encode(pickle.dumps(dates)).decode('ascii'),
				base64.b64encode(pickle.dumps(prices)).decode('ascii')
			)
			msg_str = "%s %s %s" % payload
			self.sock.send_string(msg_str)
		else:
			#Publish multiple data points
			for ii in range(dates.size):
				payload = (
					ticker_str,
					base64.b64encode(pickle.dumps(dates[ii])).decode('ascii'),
					base64.b64encode(pickle.dumps(prices[ii,:])).decode('ascii')
				)
				msg_str = "%s %s %s" % payload
				self.sock.send_string(msg_str)

	############################################################################
	def _update_tickers(self, market=True):
		"""
		Loops through the desired tickers and updates them if there is new data 
		available and publishes said update

		:param market: True to update market tickers, False to update daily 
			tickers
		:type market: bool
		"""
		#Determine what lists to use
		if market:
			LOGGER.debug("Updating market tickers")
			ticker_strs = self.market_ticker_strs
			tickers = self.market_tickers
			prev_updates = self.market_prev_update
			n = self.n_market_tickers
		else:
			LOGGER.debug("Updating daily tickers")
			ticker_strs = self.daily_ticker_strs
			tickers = self.daily_tickers
			prev_updates = self.daily_prev_update
			n = self.n_daily_tickers

		#Loop through all tickers
		LOGGER.debug("Looping through tickers")
		for ii in range(n):
			try:
				#Get current info
				cur_str = ticker_strs[ii]
				cur_ticker = tickers[ii]
				prev_update = prev_updates[ii]
				LOGGER.debug("Updating %s ticker" % cur_str)

				#Check if this is the first time calling this function on this 
				#ticker
				if cur_ticker is None:
					#This is the first time calling this function on this 
					#ticker so we need to initialize it
					LOGGER.debug("First time updating %s so initializing it", 
								 cur_str)
					cur_ticker = yf.Ticker(cur_str)
					time.sleep(YF_SEC_BETWEEN_REQS)
					tickers[ii] = cur_ticker

				#By this point we know we have an initialized ticker so get 
				#newest data
				LOGGER.debug("%s pulling data", cur_str)
				data = cur_ticker.history(period='2d', interval=self.timeframe)

				#Wait to update the next one so we don't violate the rate limit
				time.sleep(YF_SEC_BETWEEN_REQS)

				#Check if we got any data
				if data.empty:
					LOGGER.debug("Got no data so skipping %s", cur_str)
					continue

				#I hate working with pandas so convert to numpy
				d_dates = NP_LOCALIZE(data.index.to_pydatetime())
				d_prices = data.to_numpy()[:,:5]
				
				#Check if this is our first time pulling data for this ticker
				if prev_update is None:
					#This is our first time pulling data for this ticker so 
					#save the date and publish
					LOGGER.debug("First time updating %s so publishing " \
								 + "latest value", cur_str)
					prev_updates[ii] = d_dates[-1]
					self._publish(cur_str, d_dates[-1], d_prices[-1,:])
				else:
					#Not our first time so find all dates after the last one we 
					#published
					LOGGER.debug("Checking if we got any new data")
					new_data_present = prev_update < d_dates
					if np.all(new_data_present == False):
						#No new data present
						LOGGER.debug("No new data present so skipping")
						continue
					else:
						LOGGER.debug("New data present for %s so publishing", 
									 cur_str)
						new_data_idx = np.argmax(new_data_present)
						prev_updates[ii] = d_dates[-1]
						self._publish(cur_str, d_dates[new_data_idx:], 
									  d_prices[new_data_idx:,:])
			except Exception as e:
				LOGGER.exception(e)

	############################################################################
	def _pull_data(self):
		"""
		Pulls the data for both the market tickers (if applicable) and the 
		daily tickers
		"""
		#Check if we should pull the data for the market tickers by checking if 
		#market is open
		cur_time = datetime.datetime.now(EASTERN_TZ)
		cur_time_time = datetime.time(hour=cur_time.hour, 
									  minute=cur_time.minute, 
									  second=cur_time.second)
		if MARKET_OPEN_TIME <= cur_time_time <= MARKET_CLOSE_TIME \
				and cur_time.weekday() < 5:
			#Market is open so pull market data
			LOGGER.info("Market is open so pulling market data")
			self._update_tickers(True)
			self.have_done_mkt_close_pull = False
		elif not self.have_done_mkt_close_pull:
			#Market is closed but we havent done one final data pull after 
			#market close so do that
			LOGGER.info("Market is closed, but doing our single post close " \
						 + "pull")
			self._update_tickers(True)
			self.have_done_mkt_close_pull = True

		#Pull the data for the daily tickers
		LOGGER.info("Pulling daily data")
		self._update_tickers(False)

	############################################################################
	def run(self):
		"""
		Runs main loop of scraper (fetches and publishes data in infinite 
		loop)
		"""
		LOGGER.info("Running scraper")

		#Get current time
		cur_time = datetime.datetime.now(EASTERN_TZ)
		LOGGER.debug("Current time = %s" % cur_time.strftime(DT_FMT))

		#Determine start time
		if self.timeframe == '1d':
			#Run 1 minute after market close
			next_time = datetime.datetime(cur_time.year, cur_time.month, 
										  cur_time.day, 16, 1, 0)
		else:
			#Run x minutes after market open
			next_time = datetime.datetime(cur_time.year, cur_time.month, 
										  cur_time.day, 9, 30, 0)
			min_to_wait = int(self.timeframe[:-1])
			next_time += datetime.timedelta(minutes=min_to_wait)
		#Add 30 seconds to data pull time to ensure data is available
		next_time += datetime.timedelta(seconds=30)
		#Localize time
		next_time = EASTERN_TZ.localize(next_time)
		LOGGER.debug("Next pull data time = %s" % next_time.strftime(DT_FMT))

		#If we have already missed starttime today then keep computing next 
		#pull time until it is in the future
		while cur_time >= next_time:
			if self.timeframe == "1d":
				LOGGER.debug("Next pull data time %s is in the past. Adding " \
							 + "1 day to next pull data time", 
							 next_time.strftime(DT_FMT))
				next_time += datetime.timedelta(days=1)
			else:
				LOGGER.debug("Next pull data time %s is in the past. Adding " \
							 + "%d minutes to next pull data time", 
							 next_time.strftime(DT_FMT), min_to_wait)

				next_time += datetime.timedelta(minutes=min_to_wait)
			cur_time = datetime.datetime.now(EASTERN_TZ)

		#If made it here then we have the next time we should pull data so run 
		#our main loop
		LOGGER.info("Entering main loop of scraper")
		while True:
			#Wait until our next data pulling time comes
			LOGGER.info("Current time = %s. Waiting for next data pull " \
						 + "time = %s", cur_time.strftime(DT_FMT), 
						 next_time.strftime(DT_FMT))
			while cur_time < next_time:
				time.sleep(5)
				cur_time = datetime.datetime.now(EASTERN_TZ)

			#Pull data
			LOGGER.debug("Reached next data pull time so pulling data")
			try:
				self._pull_data()
			except Exception as e:
				LOGGER.exception(e)
			LOGGER.debug("Done pulling data")

			#Compute next time to pull data
			if self.timeframe == "1d":
				next_time += datetime.timedelta(days=1)
			else:
				next_time += datetime.timedelta(minutes=min_to_wait)
			LOGGER.debug("Next time to pull data = %s", 
						 next_time.strftime(DT_FMT))

			#Get current time
			cur_time = datetime.datetime.now(EASTERN_TZ)
			if cur_time > next_time:
				lag_time = (cur_time - next_time).total_seconds()
				LOGGER.warning("Falling behind by %d seconds" % lag_time)

################################################################################
###                                  Main                                    ###
################################################################################
if __name__ == "__main__":
	#Define default market list location
	src_dir = os.path.abspath(os.path.dirname(__file__))
	market_fname = os.path.join("all_tickers.txt")

	#Get user arguments
	desc = "Scrapes and publishes stock data"
	parser = argparse.ArgumentParser(desc)
	help_str = "Timeframe to operate on. Default = 1d"
	choices = ['1m', '2m', '5m', '15m', '30m', '60m', '90m', '1d']
	parser.add_argument("-t", "--timeframe", help=help_str, choices=choices, 
						default="1d")
	help_str = "Path to file containing market tickers. Default is default " \
			 + "market tickers"
	parser.add_argument("--market", help=help_str, default=market_fname)
	help_str = "Path to file containing daily tickers. Default is default " \
			 + "daily tickers"
	parser.add_argument("--daily", help=help_str, default=DEFAULT_DAILY_TICKERS)
	help_str = "Set console log output to verbose (useful for debugging)"
	parser.add_argument("-v", "--verbose", action="store_true", help=help_str)
	help_str = "Logs to file (verbose)"
	parser.add_argument("-l", "--log_to_file", action="store_true", help=help_str)
	args = parser.parse_args()

	#Setup logging
	log_lvl = logging.INFO
	if args.verbose:
		log_lvl = logging.DEBUG

	#Create console handler
	console_handler = logging.StreamHandler()
	console_handler.setLevel(log_lvl)

	#Create file handler
	if args.log_to_file:
		src_dir = os.path.abspath(os.path.dirname(__file__))
		log_dir = os.path.join(src_dir, "..", "logs")
		if not os.path.exists(log_dir):
			os.makedirs(log_dir)
		datetime_str = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
		log_fname = os.path.join(log_dir, "scraper_%s.log" % datetime_str)
		print("Logging to file: %s" % log_fname)
		file_handler = logging.FileHandler(log_fname)
		file_handler.setLevel(logging.DEBUG)

	#Create formatter
	fmt_str = '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
	log_formatter = logging.Formatter(fmt_str)

	#Add formatter to handlers
	console_handler.setFormatter(log_formatter)
	if args.log_to_file:
		file_handler.setFormatter(log_formatter)

	#Add handlers to loggers
	LOGGER.addHandler(console_handler)
	if args.log_to_file:
		LOGGER.addHandler(file_handler)

	#Create scraper
	scraper = Scraper(args.timeframe, args.market, args.daily)

	#Run scraper
	try:
		scraper.run()
	except KeyboardInterrupt as e:
		pass

################################################################################
###                               End of File                                ###
################################################################################