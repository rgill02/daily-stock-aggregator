################################################################################
###                                 Imports                                  ###
################################################################################
#Third party imports
import numpy as np
import matplotlib.pyplot as plt

#Our imports
from Abstract_Analyzer import Abstract_Analyzer

################################################################################
###                                Class Def                                 ###
################################################################################
class Example_Analyzer(Abstract_Analyzer):
	"""
	Example analyzer class that just plots the price data that we get
	"""
	############################################################################
	def analyze(self, ticker, prices, dates):
		plt.figure()
		plt.plot(prices[:,0], label="Open")
		plt.plot(prices[:,1], label="Close")
		plt.plot(prices[:,2], label="High")
		plt.plot(prices[:,3], label="Low")
		plt.xlabel("Day")
		plt.ylabel("Price ($)")
		plt.title(ticker)
		plt.grid()
		plt.legend(loc="upper right")
		plt.show()

################################################################################
###                                Test Code                                 ###
################################################################################
if __name__ == "__main__":
	analyzer = Example_Analyzer()
	print("Running example analyzer. Stop with 'ctrl-c'...")
	try:
		analyzer.run()
	except KeyboardInterrupt as e:
		pass

################################################################################
###                               End of File                                ###
################################################################################