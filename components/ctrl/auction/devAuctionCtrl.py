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

import copy

class DevAuctionCtrl(AggregatorCtrl):
	def __init__(self, name, dev, parent, host):
		AggregatorCtrl.__init__(self,  name,  parent, host)

		self.dev = dev
		if parent != None:
			self.parent = parent

		self.pushFunctions = False
		self.auctionEvents = False

		self.devtype = "DeviceController"

		# Variables storing local device data
		self.devData = None
		self.devDataUpdate = -1

	def setClearingPrice(self, price):
		# Round if we have discrete bids:
		if self.discreteBids:
			price = int(round(price))

		self.currentPrice = price

		#Control the device:

		self.setControlResult()

	def requestDemandFunction(self):
		# Function to request demand functions from the children
		self.currentFunction = self.createDemandFunction()
		self.updatedFunction = copy.deepcopy(self.currentFunction)
		return self.currentFunction

	def startup(self):
		# Establish device <-> controller connection
		if not isinstance(self.dev, str):
			self.dev.controller = self
		else:
			self.zSet(self.dev, 'controller', self.name)
		AggregatorCtrl.startup(self)

	def preTick(self, time, deltatime=0):
		#For now, always trigger an event to create a new demand function
		if self.pushFunctions:
			self.event("timeTick")

	def postTick(self, time, deltatime=0):
		pass

	def shutdown(self):
		pass

	def event(self, event):
		if self.auctionEvents:
			# Event handler
			# Don't care about the actual event at the moment, just construct a new demand function based on the current device state:
			self.updatedDemandFunction = self.createDemandFunction()

			if self.currentFunction.difference(self.updatedDemandFunction) > self.updateThreshold:
				#Propagate the changes:
				self.parent.updateDemandFunction(self.currentFunction, self.updatedDemandFunction)
				#update the local bookkeeping too
				self.currentDemandFunction = copy.deepcopy(self.updatedDemandFunction)

				#And the device will have to follow as well:
				self.setClearingPrice(self.currentPrice)

	def triggerEvent(self, event):
		if self.auctionEvents:#compatibility
			self.event(event)

	def createDemandFunction(self):
		print("this function must be overridden")
		assert(False)

	def setControlResult(self):
		result = {}
		result [self.commodities[0]] = []
		#Tuple {time_from, demand}
		tup = (self.host.time(), self.updatedFunction.demandForPrice(self.currentPrice))

		result[self.commodities[0]].append(tup)
		self.zCall(self.dev, 'setPlan', result)

	def updateDeviceProperties(self):
		if self.devDataUpdate < self.host.time():
			self.devData = self.zCall(self.dev, 'getProperties')

		return self.devData

	# Compatibility functions for PlannedAuctions
	# They introduce an event, which triggers an demand function
	# Which is the auction method of dealing with such events
	def requestPlanning(self):
		self.event("legacy")

	def requestCancelation(self):
		self.event("legacy")

	def doEventPlanning(self, desiredPlan, desiredGlobal, availability, time, timeBase):
		self.event("legacy")
