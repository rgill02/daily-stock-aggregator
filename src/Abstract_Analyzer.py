################################################################################
###                                 Imports                                  ###
################################################################################
#Standard imports
import pickle
import base64
import os
import random
import datetime

#Third party imports
import zmq
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

#Our imports
from Daily_Aggregator import PUB_PORT, get_ticker_list

################################################################################
###                                Constants                                 ###
################################################################################
UP_COLOR = "green"
DOWN_COLOR = "red"
CANDLE_WIDTH = 0.4
WICK_WIDTH = 0.05

################################################################################
###                                Class Def                                 ###
################################################################################
class Abstract_Analyzer:
	"""
	Abstract class meant to serve as a template for an analyzer that subscribes 
	to the daily aggregator and consumes data when published. It then analyzes 
	this data in some way and does something with it (which is class specific). 
	This architecture allows you to make different analyzers for different 
	strategies or to look for different indicators

	:param ticker_list: list of tickers to subscribe to. This can be a list of 
		strings, the path to a text file containing the tickers separated by a 
		newline character, or set as None to attempt to pull the list from the 
		internet. If left as an empty list then it will subscribe to all tickers
	:type ticker_list: list of strings or string
	:param zmq_ctx: zmq context to use, will create one if left as none
	:type zmq_ctx: zmq.Context
	"""
	############################################################################
	def __init__(self, ticker_list=[], ip_addr="localhost", zmq_ctx=None):
		#Get tickers
		self.ticker_strs, self.num_tickers = get_ticker_list(ticker_list)

		#Setup zmq subscriber
		if zmq_ctx is None:
			self.zmq_ctx = zmq.Context()
		else:
			self.zmq_ctx = zmq_ctx
		self.sock = self.zmq_ctx.socket(zmq.SUB)
		self.sock.connect("tcp://%s:%d" % (ip_addr, PUB_PORT))
		msg = "Started zmq subscriber listening to %s:%d" % (ip_addr, PUB_PORT)

		#Subscribe to given tickers
		if len(self.ticker_strs) == 0:
			#Subscribe to all tickers
			self.sock.setsockopt_string(zmq.SUBSCRIBE, "")
		else:
			#Subscribe to given tickers
			for ticker in self.ticker_strs:
				self.sock.setsockopt_string(zmq.SUBSCRIBE, ticker)

		#Create tmp folder for any temporary files
		self.tmp_folder = os.path.join(os.path.dirname(__file__), "tmp")
		if not os.path.exists(self.tmp_folder):
			os.makedirs(self.tmp_folder)

	############################################################################
	def analyze(self, ticker, prices, dates):
		"""
		Override this callback function with your analysis routine

		:param ticker: ticker symbol we have an update for
		:type ticker: str
		:param prices: Nx5 numpy array of prices and volume
		:type prices: ndarray
		:param dates: Nx3 numpy array of dates
		:type dates: ndarray
		"""
		#STUB
		raise NotImplementedError

	############################################################################
	def run(self):
		"""
		Main loop that listens for updates and executes analysis on them
		"""
		while True:
			msg = self.sock.recv_string()
			ticker, prices_enc, dates_enc = msg.split()
			prices = pickle.loads(base64.b64decode(prices_enc.encode("ascii")))
			dates = pickle.loads(base64.b64decode(dates_enc.encode("ascii")))
			self.analyze(ticker, prices, dates)

	############################################################################
	def plot_candlestick(self, ticker, prices, dates, action='save'):
		"""
		Plots a candlestick chart from the given data

		:param ticker: ticker symbol we have an update for
		:type ticker: str
		:param prices: Nx5 numpy array of prices and volume
		:type prices: ndarray
		:param dates: Nx3 numpy array of dates
		:type dates: ndarray
		:param action: options are 'save', 'plot', and 'show'. 'save' saves the 
			plot to an image file and then returns the path to said file. 
			'plot' returns the actual matplotlib figure. 'show' shows the plot 
			on the screen (which is blocking)
		:type action: str
		:return: path to image, matplotlib figure, or nothing
		:rtype: str, matplotlib figure, or None
		"""
		#Convert dates to datetime dates
		x_dates = np.array([datetime.datetime(x[0], x[1], x[2]) for x in dates.tolist()])

		#Determine which candles are up and down
		up_idxs = prices[:,1] >= prices[:,0]
		up_prices = prices[up_idxs,:]
		up_dates = x_dates[up_idxs]
		down_idxs = prices[:,1] < prices[:,0]
		down_prices = prices[down_idxs,:]
		down_dates = x_dates[down_idxs]

		x = np.arange(prices.shape[0])
		xup = x[up_idxs]
		xdown = x[prices[:,1] < prices[:,0]]

		#Create figure
		fig = plt.figure()
		plt.gcf().set_size_inches(6.4 * 3, 4.8 * 2)

		#Plot up candles
		plt.bar(up_dates, up_prices[:,1]-up_prices[:,0], CANDLE_WIDTH, 
				bottom=up_prices[:,0], color=UP_COLOR)
		plt.bar(up_dates, up_prices[:,2]-up_prices[:,1], WICK_WIDTH, 
				bottom=up_prices[:,1], color=UP_COLOR)
		plt.bar(up_dates, up_prices[:,3]-up_prices[:,0], WICK_WIDTH, 
				bottom=up_prices[:,0], color=UP_COLOR)

		#Plot down candles
		plt.bar(down_dates, down_prices[:,1]-down_prices[:,0], CANDLE_WIDTH, 
				bottom=down_prices[:,0], color=DOWN_COLOR)
		plt.bar(down_dates, down_prices[:,2]-down_prices[:,0], WICK_WIDTH, 
				bottom=down_prices[:,0], color=DOWN_COLOR)
		plt.bar(down_dates, down_prices[:,3]-down_prices[:,1], WICK_WIDTH, 
				bottom=down_prices[:,1], color=DOWN_COLOR)

		#Add labels
		#plt.xticks(rotation=90, ha="right")
		plt.xlabel("Date")
		plt.ylabel("Price (USD)")
		plt.title(ticker)

		#Do any last formatting
		plt.gca().xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
		plt.gca().xaxis.set_major_locator(mdates.DayLocator(interval=2))
		fig.autofmt_xdate(bottom=0.2, rotation=45, ha="right")
		#plt.gcf().autofmt_xdate()

		#Perform necessary action
		if action == 'save':
			#Save to tmp folder
			payload = (self.__class__.__name__, random.randint(0, 10000))
			img_fname = os.path.join(self.tmp_folder, "%s_%d.png" % payload)
			plt.savefig(img_fname, bbox_inches='tight')
			return img_fname
		elif action == 'show':
			plt.show()
		else:
			return fig

################################################################################
###                                Test Code                                 ###
################################################################################
if __name__ == "__main__":
	pass

################################################################################
###                               End of File                                ###
################################################################################