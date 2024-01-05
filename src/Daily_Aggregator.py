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
import numpy as np
import zmq
import pytz

#Our imports
from Telegram_Handler import Telegram_Handler

################################################################################
###                                Constants                                 ###
################################################################################
TICKER_LIST_URL = "https://raw.githubusercontent.com/rreichel3/" \
				+ "US-Stock-Symbols/main/all/all_tickers.txt"

YAHOO_FINANCE_REQ_PER_HOUR = 2000
YAHOO_FINANCE_REQ_PER_SEC = YAHOO_FINANCE_REQ_PER_HOUR / 3600
YF_SEC_BETWEEN_REQS = math.ceil(1 / YAHOO_FINANCE_REQ_PER_SEC)

ROLLING_BUF_DAYS = 30

PUB_PORT = 21000

EASTERN_TZ = pytz.timezone("US/Eastern")
MARKET_CLOSE_TIME = datetime.time(hour=16, minute=0, second=0)

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

################################################################################
###                             Helper Functions                             ###
################################################################################
def get_ticker_list(ticker_list, logger=None):
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
	num_tickers = len(ticker_strs)
	if logger is not None:
		logger.debug("Found %d tickers in list" % num_tickers)

	#Return tickers
	return ticker_strs, num_tickers

################################################################################
###                                Class Def                                 ###
################################################################################
class Daily_Aggregator:
	"""
	Every weekday at market close this aggregator will fetch that days prices 
	(high, low, open, and close) for every ticker in a given list of tickers. 
	It will keep a rolling buffer of prices for every desired ticker 
	(encompassing about 1 month of time) that will be updated with new price 
	history and published over zmq daily (on days the market is open).

	Got default list of stock symbols from here: 
	https://github.com/rreichel3/US-Stock-Symbols/blob/main/all/all_tickers.txt

	:param ticker_list: list of tickers to pull data for. This can be a list of 
		strings, the path to a text file containing the tickers separated by a 
		newline character, or left as None to attempt to pull the list from the 
		internet
	:type ticker_list: list of strings or string
	:param zmq_ctx: zmq context to use, will create one if left as none
	:type zmq_ctx: zmq.Context
	"""
	############################################################################
	def __init__(self, ticker_list=None, zmq_ctx=None):
		self.ticker_strs, self.num_tickers = get_ticker_list(ticker_list, 
															 LOGGER)

		#Create ticker yfinance objects that we can use to fetch data with
		self.tickers = [None for x in self.ticker_strs]
		
		#Create parallel array to hold price data
		self.prices = np.zeros((self.num_tickers, ROLLING_BUF_DAYS, 5))

		#Create arrays of dates
		self.dates = np.zeros((self.num_tickers, ROLLING_BUF_DAYS, 3), 
							  dtype=int)

		#Setup zmq publisher
		if zmq_ctx is None:
			self.zmq_ctx = zmq.Context()
		else:
			self.zmq_ctx = zmq_ctx
		self.sock = self.zmq_ctx.socket(zmq.PUB)
		self.sock.bind("tcp://*:%d" % PUB_PORT)
		LOGGER.debug("Started zmq publisher on port %d" % PUB_PORT)

		#Now that we are all set up we need to loop through our tickers once to 
		#initialize everything
		LOGGER.debug("Looping through tickers to initialize data")
		self._loop_through_tickers()

	############################################################################
	def _publish(self, ticker_str, prices, dates):
		"""
		Publishes the given data over zmq

		:param ticker_str: ticker symbol
		:type ticker_str: str
		:param prices: Nx5 numpy array of prices and volumes
		:type prices: ndarray
		:param dates: Nx3 numpy array of dates
		:type dates: ndarray
		"""
		LOGGER.debug("Publishing data for ticker %s" % ticker_str)
		payload = (
			ticker_str,
			base64.b64encode(pickle.dumps(prices)).decode('ascii'),
			base64.b64encode(pickle.dumps(dates)).decode('ascii')
		)
		msg_str = "%s %s %s" % payload
		self.sock.send_string(msg_str)

	############################################################################
	def _update_ticker(self, idx):
		"""
		Fetches todays price data, stores it in our rolling buffer, and 
		publishes it
		
		:param idx: idx into the parallel arrays to indicate what ticker we are 
			fetching data for
		:type idx: int
		"""
		#Get current ticker
		cur_ticker_str = self.ticker_strs[idx]
		cur_ticker = self.tickers[idx]
		LOGGER.debug("Updating ticker %s" % cur_ticker_str)

		#Keep track if we got new information
		updated = False

		#Check if this is the first time calling this function on this ticker
		if cur_ticker is None:
			#This is the first time calling this function on this ticker so 
			#create the actual ticker object
			LOGGER.debug("First time calling update on this ticker so " \
						 + "initializing arrays")
			cur_ticker = yf.Ticker(cur_ticker_str)
			self.tickers[idx] = cur_ticker

			#Download a month of data to initialize the arrays
			data = cur_ticker.history(period="%dd" % (2 * ROLLING_BUF_DAYS))
			self.prices[idx,:,0] = data['Open'].to_numpy()[-ROLLING_BUF_DAYS:]
			self.prices[idx,:,1] = data['Close'].to_numpy()[-ROLLING_BUF_DAYS:]
			self.prices[idx,:,2] = data['High'].to_numpy()[-ROLLING_BUF_DAYS:]
			self.prices[idx,:,3] = data['Low'].to_numpy()[-ROLLING_BUF_DAYS:]
			self.prices[idx,:,4] = data['Volume'].to_numpy()[-ROLLING_BUF_DAYS:]
			self.dates[idx,:,:] = np.array([(x.year, x.month, x.day) for x in data.index.to_pydatetime()][-ROLLING_BUF_DAYS:])
			updated = True
		else:
			#This is not the first time calling this function on this ticker 
			#just the data for today and update the arrays if we have a new date
			data = cur_ticker.history(period="1d")
			cur_date = data.index.to_pydatetime()[0]
			if cur_date.year != self.dates[idx,-1,0] \
				or cur_date.month != self.dates[idx,-1,1] \
				or cur_date.day != self.dates[idx,-1,2]:

				#New date we don't have yet so update
				self.prices[idx,:,:] = np.roll(self.prices[idx,:,:], -1, 0)
				self.prices[idx,-1,0] = data['Open'].to_numpy()[0]
				self.prices[idx,-1,1] = data['Close'].to_numpy()[0]
				self.prices[idx,-1,2] = data['High'].to_numpy()[0]
				self.prices[idx,-1,3] = data['Low'].to_numpy()[0]
				self.prices[idx,-1,4] = data['Volume'].to_numpy()[0]
				self.dates[idx,:,:] = np.roll(self.dates[idx,:,:], -1, 0)
				self.dates[idx,-1,0] = cur_date.year
				self.dates[idx,-1,1] = cur_date.month
				self.dates[idx,-1,2] = cur_date.day
				updated = True

		#Publish update if needed
		if updated:
			self._publish(cur_ticker_str, self.prices[idx,:,:], 
						  self.dates[idx,:,:])

	############################################################################
	def _loop_through_tickers(self):
		"""
		Loops through the list of tickers and fetches/publishes their updates 
		while waiting enough time between each fetch to avoid hitting the yahoo 
		finance api limit
		"""
		for ii in range(self.num_tickers):
			self._update_ticker(ii)
			time.sleep(YF_SEC_BETWEEN_REQS)

	############################################################################
	def run(self):
		"""
		Runs main loop of aggregator (fetches and publishes data in infinite 
		loop)
		"""
		LOGGER.info("Running main loop")
		while True:
			#Get current time
			cur_time = datetime.datetime.now(EASTERN_TZ)

			#Compute time to next market close
			mkt_close_today = datetime.datetime(cur_time.year, cur_time.month, 
												cur_time.day, 16)
			next_mkt_close = EASTERN_TZ.localize(mkt_close_today) \
						   + datetime.timedelta(days=1)
			secs_to_next_close = (next_mkt_close - cur_time).total_seconds()
			#Add a few minutes to guarantee the data is available
			secs_to_next_close += 180

			#Wait until next market close
			str_vals = (secs_to_next_close / 3600, secs_to_next_close)
			msg = "Waiting %.2f hours (%d seconds) until next close" % str_vals
			LOGGER.info(msg)
			time.sleep(secs_to_next_close)

			#Check if today is a weekday
			if datetime.datetime.today().weekday() < 5:
				#Is weekday so market was open so run updates
				LOGGER.info("Is weekday so running through ticker list")
				self._loop_through_tickers()
			else:
				LOGGER.info("Is weekend so skipping updates")

################################################################################
###                          Main Helper Functions                           ###
################################################################################
def tg_error_cb(log_entry, status_code, resp_text):
		print("Could not log:")
		print("\t%s" % log_entry)
		print("Got status code %d and response text:" % status_code)
		print(resp_text)

################################################################################
def setup_logging(config_fname=None, log_lvl=logging.INFO):
	#Create console handler
	console_handler = logging.StreamHandler()
	console_handler.setLevel(log_lvl)

	#Create file handler
	src_dir = os.path.abspath(os.path.dirname(__file__))
	log_dir = os.path.join(src_dir, "..", "logs")
	if not os.path.exists(log_dir):
		os.makedirs(log_dir)
	datetime_str = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
	log_fname = os.path.join(log_dir, "daily_agg_%s.log" % datetime_str)
	print("Logging to file: %s" % log_fname)
	file_handler = logging.FileHandler(log_fname)
	file_handler.setLevel(logging.DEBUG)

	#Create telegram handler
	if config_fname is not None:
		telegram_handler = Telegram_Handler(config_fname=config_fname, 
											error_cb=tg_error_cb, 
											app_name="Daily Aggregator")
		telegram_handler.setLevel(logging.INFO)
		print("Logging to telegram")

	#Create formatter
	fmt_str = '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
	log_formatter = logging.Formatter(fmt_str)

	#Add formatter to handlers
	console_handler.setFormatter(log_formatter)
	file_handler.setFormatter(log_formatter)
	if config_fname is not None:
		telegram_handler.setFormatter(log_formatter)

	#Add handlers to loggers
	LOGGER.addHandler(console_handler)
	LOGGER.addHandler(file_handler)
	if config_fname is not None:
		LOGGER.addHandler(telegram_handler)

################################################################################
###                                  Main                                    ###
################################################################################
if __name__ == "__main__":
	#Get user arguments
	desc = "Aggregates and publishes stock data daily"
	parser = argparse.ArgumentParser(desc)
	help_str = "Config file containing telegram credentials"
	parser.add_argument("-c", "--config_fname", help=help_str)
	help_str = "Set console log output to verbose (useful for debugging)"
	parser.add_argument("-v", "--verbose", action="store_true", help=help_str)
	args = parser.parse_args()

	#Setup logging
	if args.verbose:
		setup_logging(config_fname=args.config_fname, log_lvl=logging.DEBUG)
	else:
		setup_logging(config_fname=args.config_fname, log_lvl=logging.INFO)

	#Define ticker list file location
	src_dir = os.path.abspath(os.path.dirname(__file__))
	ticker_list_fname = os.path.join("all_tickers.txt")

	#Create aggregator
	print("Creating daily aggregator and looping through tickers to " \
		  + "initialize data...")
	agg = Daily_Aggregator(ticker_list_fname)

	#Run aggregator
	print("Running daily aggregator. Stop with 'ctrl-c...")
	try:
		agg.run()
	except KeyboardInterrupt as e:
		pass

################################################################################
###                               End of File                                ###
################################################################################