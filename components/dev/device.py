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


from core.entity import Entity

import threading

class Device(Entity):
	def __init__(self,  name,  host):
		Entity.__init__(self,  name, host)

		self.timeOffset = 0

		if self.host != None:
			self.timeOffset = host.timeOffset

		self.devtype = "device"
		self.type = "devices"
		
		#state
		self.totalConsumption = 0.0
		self.commodities = ['ELECTRICITY']

		#bindings
		self.controller = None
		self.flowMeter = None
		
		self.plan = {}
		self.consumption = {}

		self.maxAgePlan = 900			# Used to prune plannings that are too old to be accurate
		self.maxFuturePlan = 7*24*3600 	# Used to prune a planning that is in the distant future
		# Control
		self.smartOperation = True 	# Indicates whether the device is being actively controlled. Can be used to disable control for e.g. cyber attacks or demonstrator simulations
		self.strictComfort = True

		self.lockPlanning = threading.Lock()
		self.lockState = threading.Lock()

		# Persistence
		self.watchlist = ["consumption", "plan"]

	def setPlan(self,  plan):
		self.lockPlanning.acquire()

		for c in self.commodities:
			self.plan[c] = list(plan[c])

		self.lockPlanning.release()

	def prunePlan(self):
		self.lockPlanning.acquire()

		for c in self.commodities:
			run = True
			while run and c in self.plan:
				if len(self.plan[c]) >= 1:
					if self.plan[c][0][0] <= self.host.time()-self.zGet(self.controller, "timeBase") or self.plan[c][0][0] < self.host.time()-self.maxAgePlan:
						self.plan[c].pop(0)
					elif self.maxFuturePlan is not None and self.plan[c][-1][0] > self.host.time()+self.maxFuturePlan:
						self.plan[c].pop(-1)
					else:
						run = False
				else:
					run = False

		self.lockPlanning.release()

	def requestTickets(self, time):
		self.ticketCallback.clear()
		self.registerTicket(self.host.staticTicketPreTickDevs, 'preTick', register=False)  # preTick
		self.registerTicket(self.host.staticTicketTickDevs, 'timeTick', register=False)  # timeTick

	def preTick(self, time, deltatime=0):
		Entity.preTick(self, time)
		
	def timeTick(self, time, deltatime=0):
		Entity.timeTick(self, time)
	
	def postTick(self, time, deltatime=0):
		Entity.postTick(self, time)
	
	def startup(self):
		if self.host != None:
			self.host.addDevice(self)

		Entity.startup(self)
		
	def shutdown(self):
		Entity.shutdown(self)
	
	def logStats(self, time):
		Entity.logStats(self, time)
	
	def addMeter(self, meter):
		self.flowMeter = meter # Used to obtain e.g. voltage measurements of the node and use these in the device
		
	def getVoltage(self):
		voltage = complex(0.0, 0.0)
		if self.flowMeter != None:
			voltage = self.zCall(self.flowMeter, "getVoltage")

		return voltage

	def getFrequency(self):
		frequency = 50.0
		if self.flowMeter != None:
			frequency = self.zCall(self.flowMeter, "getFrequency")

		return frequency
		
	def logValue(self, measurement,  value, time=None, deltatime=None):
# 		tags = {'devtype':self.devtype,  'name':self.name}
# 		values = {measurement:value}
# 		self.host.logValue(self.type,  tags,  values, time)

		data = self.type+",devtype="+self.devtype+",name="+self.name+" "+measurement+"="+str(value)
		self.host.logValuePrepared(data, time, deltatime)

	def requestPlanning(self):
		self.zCast(self.controller, "requestPlanning")

	def triggerEvent(self, event):
		if self.controller is not None:
			self.zCast(self.controller, "triggerEvent", event)

	def unPowered(self, commodity):
		for c in self.commodities:
			for c in self.commodities:
				self.consumption[c] = complex(0.0, 0.0)

	def getProperties(self):
		# Get the properties of this device
		self.lockState.acquire()

		r = {}

		# Populate the result dict
		r['name'] = self.name
		r['timeBase'] = self.timeBase
		r['timeOffset'] = self.timeOffset
		r['devtype'] = self.devtype

		r['commodities'] = self.commodities
		r['strictComfort'] = self.strictComfort

		r['consumption'] = self.consumption

		self.lockState.release()

		return r