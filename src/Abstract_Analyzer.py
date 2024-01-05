################################################################################
###                                 Imports                                  ###
################################################################################
#Standard imports
import pickle
import base64

#Third party imports
import zmq

#Our imports
from Daily_Aggregator import PUB_PORT, get_ticker_list

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

################################################################################
###                                Test Code                                 ###
################################################################################
if __name__ == "__main__":
	pass

################################################################################
###                               End of File                                ###
################################################################################