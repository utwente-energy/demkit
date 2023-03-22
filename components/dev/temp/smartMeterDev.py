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


from dev.meterDev import MeterDev

import numpy as np
import util.helpers

class SmartMeterDev(MeterDev):
	def __init__(self,  name,  host, commodities = ['ELECTRICITY'], flowNode = None, phase = 1, controller = None):
		MeterDev.__init__(self,  name,  host, commodities, flowNode, phase, controller)
		self.devtype = "Meter"

		#params
		self.total = 0		# Bookkeeping to get the average consumption
		self.count = 0
		self.average = 0
		self.interval = 900	# Measuring interval in s
		self.lastTime = -1
		self.digits = 1


	# def startup(self):
	# 	self.lockState.acquire()
	# 	for c in self.commodities:
	# 		self.consumption[c] = complex(0.0, 0.0)
	#
	# 	if self.flowNode != None:
	# 		if not isinstance(self.flowNode, str):
	# 			self.flowNode.addMeter(self, self.phase)
	# 		else:
	# 			self.zCall(self.flowNode, "addMeter", self.name, self.phase)
	#
	# 	self.costsConnectionInterval = self.costsConnection / (365 * 24 * (3600.0/self.timeBase))
	#
	# 	# persistence
	# 	if self.persistence != None:
	# 		watchlist = ["consumption","costs", "imported", "exported",]
	# 		self.persistence.setWatchlist(watchlist)
	# 	self.lockState.release()

	# def timeTick(self, time, deltatime=0):
	# 	pass
			
	# def logStats(self, time):
	# 	self.lockState.acquire()
	# 	for c in self.commodities:
	# 		self.logValue('W-power.real.c.'+c,self.consumption[c].real)
	# 		self.logValue("W-power.imag.c."+c, self.consumption[c].imag)
	# 		self.logValue('Wh-energy.c.'+c, self.consumption[c].real / (3600.0 / self.timeBase))
	#
	# 	self.logValue("W-power-imported", self.imported.real) # Smart meter readings
	# 	self.logValue("W-power-exported", self.exported)
	# 	self.logValue("W-power-self-consumed", self.selfConsumption.real)
	#
	# 	self.logValue("Wh-energy-imported", self.imported / (3600.0 / self.timeBase)) # Smart meter readings
	# 	self.logValue("Wh-energy-exported", self.exported / (3600.0 / self.timeBase))
	# 	self.logValue("Wh-energy-self-consumed", self.selfConsumption / (3600.0 / self.timeBase))
	#
	# 	self.logValue("M-costs-cumulative", self.costs + self.costsConnectionInterval)
	#
	# 	self.lockState.release()

# 	def shutdown(self):
# 		LoadDev.shutdown(self)
#
# #### INTERFACING
# 	def getProperties(self):
# 		r = LoadDev.getProperties(self) 	# Get the properties of the overall Device class, which already includes global properties
#
# 		return r

#### LOCAL HELPERS
	def measure(self,  time):
		total = {}
		consumption = {}
		production = {}

		for c in self.commodities:
			total[c] = complex(0.0, 0.0)
			consumption[c] = 0.0
			production[c] = 0.0

		# Obtain all connected devices through zCall:
		r = self.zGet(self.devices, 'consumption')
		for val in r.values():
			for c in self.commodities:
				try:
					total[c] += val[c]
					if val[c].real > 0:
						consumption[c] += val[c].real

					else:
						production[c] += abs(val[c].real)
				except:
					pass

		self.lockState.acquire()

		# for c in self.commodities:
		# 	# if self.lastTime == -1:
		# 	# 	self.consumption[c] = total[c] # Initial state
		#
		# 	# Costs:
		# 	self.costs += (self.consumption[c].real / (3600.0 / self.timeBase)) * self.costPerWh
		#
		# 	# Import export counters:
		# 	if self.consumption[c].real > 0:
		# 		self.imported += self.consumption[c].real
		# 	elif self.consumption[c].real < 0:
		# 		self.exported -= self.consumption[c].real
		#
		# 	# Self consumption:
		# 	self.selfConsumption += min(consumption[c], production[c])



		# Smart meter magic:
		if self.lastTime < time:
			self.lastTime = time
			for c in self.commodities:
				self.total += total[c].real

			self.count += 1

			if time%self.interval == 0:
				self.average = (self.total / self.count)/len(self.commodities)
				self.average = int(self.average)
				self.average = round(self.average, -1)
				self.count = 0
				self.total = 0

				for c in self.commodities:
					self.consumption[c] = complex(self.average, 0.0)

		self.lockState.release()

	# def addDevice(self, device, attachFlow=True):
	# 	self.devices.append(device)
	# 	if attachFlow: # NOTE: This is not the flow interface, just an option to have the device access measurement data
	# 		if not isinstance(device, str):
	# 			device.addMeter(self)
	# 		else:
	# 			self.zCall(device, "addMeter", self.name)
	#
	# def addController(self, ctrl):
	# 	self.controller = ctrl
	#
	# def getVoltage(self, phase = None):
	# 	if self.flowNode is not None:
	# 		if phase is None:
	# 			phase = self.phase
	# 		return self.zCall(self.flowNode, "getLNVoltage", phase).real
	#
	# 	else:
	# 		print("No flow-node connected to this meter!")
	# 		assert(False)
