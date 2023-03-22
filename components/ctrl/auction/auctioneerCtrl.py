# Copyright 2023 University of Twente

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

# http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from ctrl.auction.aggregatorCtrl import AggregatorCtrl
from ctrl.auction.demandFunction import DemandFunction
from util.funcReader import FuncReader

import math
import threading

class AuctioneerCtrl(AggregatorCtrl):
	def __init__(self,  name,  host, congestionPoint=None):
		AggregatorCtrl.__init__(self, name, None, host, congestionPoint) #Parent is empty

		if self.host != None:
			self.host.addController(self)

		#params
		self.maxGeneration = -35000     #Depends on the model, these two are used to construct a linear demand function for the virtual supply
		self.minGeneration = -45000     #The auctioneer will clear at 0. Such a virtual supply will create some "slack"
		self.maxEmergencyGeneration = -35000     #Similar, but now for emergency (islanding) cases
		self.minEmergencyGeneration = -45000

		self.useEventControl = False

		self.nextAuction = 0                #Timer for the next auction
		self.nextFunctionUpdate = 0         #Timer for the next complete function update
		self.auctionInterval = 1           #max discrete time intervals between auctions
		self.functionUpdateInterval = 1   #max discrete time intervals between full function updates
		# Note, best not to override the above defaults as the auctioneer only sets one planning interval at the device!
		# Otherwise, check the devAuctionCtrl implementation of setControllerResult!!

		self.islanding = False
		self.strictComfort = True
		self.discreteClearing = True #Non-discrete clearing must be used with caution!

		self.lockSyncAuction = threading.Lock()

		self.prices = None
		# Note, a reader can be used to fill the prices instead:
		# self.prices = FuncReader(timeOffset = self.host.timeOffset)

		self.devtype = "AuctioneerController"

	def clearMarket(self):
		# Create a new function with the virtual generator
		clearingFunction = DemandFunction(self.currentFunction.minPrice, self.currentFunction.maxPrice, self.currentFunction.minComfort, self.currentFunction.maxComfort)
		if not self.islanding:
			clearingFunction.addLine(self.maxGeneration, self.minGeneration, self.currentFunction.minComfort, self.currentFunction.maxComfort)
		else:
			assert(self.strictComfort == False) # Islanding requires load shedding/curtailment

		# add the current active bid function:
		clearingFunction.addFunction(self.currentFunction)

		if self.prices == None:
			#And now clear the market at 0:
			price = clearingFunction.priceForDemand(0.0)
		else:
			price = self.prices.getValue(self.host.time()).real

		if self.discreteClearing:
			if price > 0.0 or self.islanding:
				price = min(math.ceil(price), clearingFunction.maxPrice)
			elif price < 0.0:
				price = max(math.floor(price), clearingFunction.minPrice)

		if self.strictComfort:
			#cap the prices
			price = min(clearingFunction.maxComfort, max(clearingFunction.minComfort, price))

		self.setClearingPrice(price)

		#Set a next clearing timer:
		self.nextAuction = self.host.time() + self.auctionInterval*self.timeBase

	def updateDemandFunction(self, oldFunction, newFunction):
		# called by children upon a demand function update
		self.requestDemandFunction()
		self.nextFunctionUpdate = self.host.time() + self.functionUpdateInterval*self.timeBase
		self.clearMarket() #We might as well clear the market now that we have new bids

	def preTick(self, time, deltatime=0):
		if time >= self.nextFunctionUpdate:
			self.requestDemandFunction()
			self.nextAuction = time #Make sure that a new auction is triggered after the prices are updated.
			self.nextFunctionUpdate = self.host.time() + self.functionUpdateInterval*self.timeBase

		if time >= self.nextAuction:
			self.clearMarket()

	def timeTick(self, time, deltatime=0):
		pass

	def logStats(self, time):
		self.logValue("n-price.clearing",  self.currentPrice)
		self.logValue("W-power.clearing",  self.currentFunction.demandForPrice(self.currentPrice))

	def getOriginalPlan(self, time):
		return self.currentFunction.demandForPrice(self.currentPrice)

