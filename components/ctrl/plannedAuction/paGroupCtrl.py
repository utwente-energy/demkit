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



from ctrl.auction.demandFunction import DemandFunction

from ctrl.groupCtrl import GroupCtrl
from ctrl.auction.aggregatorCtrl import AggregatorCtrl

import math

class PaGroupCtrl(GroupCtrl, AggregatorCtrl):
	def __init__(self, name, host,parent = None, congestionPoint = None):
		AggregatorCtrl.__init__(self, name, None, None)
		GroupCtrl.__init__(self, name, host, parent, congestionPoint)

		self.useEventControl = False

		#params
		self.auctionTimeBase = 900
		self.nextAuction = 0			 #Timer for the next auction
		self.nextFunctionUpdate = 0	 	 #Timer for the next complete function update
		self.auctionInterval = 1		 #max discrete time intervals between auctions
		self.functionUpdateInterval = 1 #max discrete time intervals between full function updates

		self.commodities = ['ELECTRICITY']

		self.discreteClearing = True #Non-discrete clearing must be used with caution!

	def preTick(self, time, deltatime=0):
		GroupCtrl.preTick(self, time)

		if self.parent == None:
			if time >= self.nextFunctionUpdate:
				self.requestDemandFunction()
				self.nextAuction = time  # Make sure that a new auction is triggered after the prices are updated.
				self.nextFunctionUpdate = self.host.time() + self.functionUpdateInterval * self.auctionTimeBase

			if time >= self.nextAuction:
				self.clearMarket()

	# two types of events: Timeticks and events	(the latter not being implemented currently)
	def timeTick(self, time, deltatime=0):
		GroupCtrl.timeTick(self, time)

	def logStats(self, time):
		GroupCtrl.logStats(self, time)
		self.logValue("n-price.clearing",  self.currentPrice)
		self.logValue("W-power.clearing",  self.currentFunction.demandForPrice(self.currentPrice))

	# Start and end-functions for system/sim startup and shutdown
	def startup(self):
		GroupCtrl.startup(self)
		assert(len(self.commodities) == 1)# Support for single commodity with auctions only

	def shutdown(self):
		pass

	def clearMarket(self):
		# Create a new function with the virtual generator  based on the planned power:
		t = self.host.time() - (self.host.time() % self.timeBase)
		clearingFunction = DemandFunction(self.currentFunction.minPrice, self.currentFunction.maxPrice)

		c = self.commodities[0]

		if self.useEventControl:
			#Updated plans through event-based, try to follow the realized profile instead:
			target = self.realized[c][t].real
		else:
			#No event based control, so we need to use the plan
			target = self.plan[c][t].real

		if target >= 0:
			self.maxGeneration = -0.9*target
			self.minGeneration = -1.1*target
		else:
			self.maxGeneration = -1.1*target
			self.minGeneration = -0.9*target
		clearingFunction.addLine(self.maxGeneration, self.minGeneration, self.currentFunction.minPrice, self.currentFunction.maxPrice)

		# add the current active bid function:
		clearingFunction.addFunction(self.currentFunction)

		#And now clear the market at 0:
		price = clearingFunction.priceForDemand(0.0)

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
		self.nextAuction = self.host.time() + self.auctionInterval*self.auctionTimeBase

	def updateDemandFunction(self, oldFunction, newFunction):
		# called by children upon a demand function update
		# update the update function:
		self.updatedFunction.subtractFunction(oldFunction)
		self.updatedFunction.addFunction(newFunction)

		# Now determine that the change and see if we pass the threshold:
		if self.currentFunction.difference(self.updatedFunction) > self.updateThreshold:
			#Propagate the changes:
			self.zCall(self.parent, 'updateDemandFunction', self.currentFunction, self.updatedFunction)

		# For now, update the demand function anyways in the whole cluster
		if self.parent == None:
			self.requestDemandFunction()
			self.nextFunctionUpdate = self.host.time() + self.functionUpdateInterval * self.auctionTimeBase
			self.clearMarket()  # We might as well clear the market now that we have new bids
		else:
			AggregatorCtrl.updateDemandFunction(self, oldFunction, newFunction)
