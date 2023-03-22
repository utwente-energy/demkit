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
from core.entity import Entity

import copy

class AggregatorCtrl(Entity):
	def __init__(self, name, parent, host, congestionPoint=None):
		Entity.__init__(self,  name,  host)

		if self.host != None:
			self.host.addController(self)

		# Params
		self.children = []

		# Establish Controller <-> groupController connection
		self.parent = parent

		self.timeBase = 900

		self.useEventControl = False

		self.updateThreshold = 0.25 #amount of change in demand functions required to trigger an update
		self.discreteBids = False

		self.currentPrice = 0
		self.currentFunction = DemandFunction() #Note: currentFunction is the function that the parent knows / uses to clear the market
		self.updatedFunction = DemandFunction() #Note: updatedFunction is the function that used to trigger an update

		self.commodities = ['ELECTRICITY'] #Note, Auction only supports one commodity

		self.congestionPoint = congestionPoint

		self.type = "controllers"
		self.devtype = "AggregatorController"

	def setClearingPrice(self, price):
		if self.congestionPoint is not None:
			if self.congestionPoint.hasUpperLimit(self.commodities[0]):
				if self.currentFunction.demandForPrice(price) > self.congestionPoint.getUpperLimit(self.commodities[0]):
					price = self.currentFunction.priceForDemand(self.congestionPoint.getUpperLimit(self.commodities[0]))
			if self.congestionPoint.hasLowerLimit(self.commodities[0]):
				if self.currentFunction.demandForPrice(price) < self.congestionPoint.getLowerLimit(self.commodities[0]):
					price = self.currentFunction.priceForDemand(self.congestionPoint.getLowerLimit(self.commodities[0]))

		# Round if we have discrete bids:
		if self.discreteBids:
			price = int(round(price))

		self.currentPrice = price

		self.zCall(self.children, 'setClearingPrice', price)

	def requestDemandFunction(self):
		# Function to request demand functions from the children
		self.currentFunction.clear()

		results = self.zCall(self.children, 'requestDemandFunction')
		for r in results.values():
			self.currentFunction.addFunction(r)

		# Create function to send upwards in the tree
		self.updatedFunction = copy.deepcopy(self.currentFunction)

		if self.congestionPoint is not None:
			# If we have a congestion point, we need to alter the function we send upwards
			# However, advanced versions of the auction use the difference in current and updated functions to decide whether or not to propagate changes
			# Hence we make a copy which we can alter
			limitedFunction = copy.deepcopy(self.currentFunction)

			if self.congestionPoint.hasUpperLimit(self.commodities[0]):
				if limitedFunction.demandForPrice(limitedFunction.minPrice) > self.congestionPoint.getUpperLimit(self.commodities[0]):
					upperPowerLimit = self.congestionPoint.getUpperLimit(self.commodities[0])
					limitedFunction.priceForDemand(upperPowerLimit)
					limitedFunction.addLine(upperPowerLimit, upperPowerLimit, limitedFunction.minPrice, limitedFunction.priceForDemand(upperPowerLimit))
			if self.congestionPoint.hasLowerLimit(self.commodities[0]):
				if limitedFunction.demandForPrice(limitedFunction.maxPrice) < self.congestionPoint.getLowerLimit(self.commodities[0]):
					lowerPowerLimit = self.congestionPoint.getLowerLimit(self.commodities[0])
					limitedFunction.priceForDemand(lowerPowerLimit)
					limitedFunction.addLine(lowerPowerLimit, lowerPowerLimit, limitedFunction.priceForDemand(lowerPowerLimit), limitedFunction.maxPrice)

			return limitedFunction
		else:
			return self.updatedFunction

	def updateDemandFunction(self, oldFunction, newFunction):
		# called by children upon a demand function update
		# update the update function:
		self.updatedFunction.subtractFunction(oldFunction)
		self.updatedFunction.addFunction(newFunction)

		# Now determine that the change and see if we pass the threshold:
		if self.currentFunction.difference(self.updatedFunction) > self.updateThreshold:
			#Propagate the changes:
			self.zCall(self.parent, 'updateDemandFunction', self.currentFunction, self.updatedFunction)

	def requestTickets(self, time):
		# self.host.registerTicket(12000) # preTick
		# self.host.registerTicket(20000) # timeTick
		self.ticketCallback.clear()
		self.registerTicket(self.host.staticTicketPreTickCtrl, 'preTick', register=False)  # preTick
		self.registerTicket(self.host.staticTicketTickCtrl, 'timeTick', register=False)  # timeTick

	# def announceTicket(self, time, number):
	# 	if number == 12000:
	# 		self.preTick(time)
	# 	if number == 20000:
	# 		self.timeTick(time)

	def preTick(self, time, deltatime=0):
		pass

	def timeTick(self, time, deltatime=0):
		pass

	def postTick(self, time, deltatime=0):
		pass

	def logStats(self, time):
		self.logValue("n-price.clearing",  self.currentPrice)
		self.logValue("W-power.clearing",  self.currentFunction.demandForPrice(self.currentPrice))

	def startup(self):
		# Establish Controller <-> groupController connection
		if self.parent is not None:
			if not isinstance(self.parent, str):
				self.parent.appendChild(self)
			else:
				self.zCall(self.parent, 'appendChild', self.name)

		# Auctioneer has to send the request for a function update
		assert(len(self.commodities) == 1) #Only support for single commodity control with Auctions!
		Entity.startup(self)

	def shutdown(self):
		pass

	def logValue(self, measurement,  value, deltatime=None):
#         tags = {'ctrltype':self.devtype,  'name':self.name}
#         values = {measurement:value}
#         self.host.logValue(self.type,  tags,  values)
		data = self.type+",ctrltype="+self.devtype+",name="+self.name+" "+measurement+"="+str(value)
		self.host.logValuePrepared(data, deltatime)

	def appendChild(self, child):
		self.children.append(child)