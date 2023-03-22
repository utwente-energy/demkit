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


from dev.loadDev import LoadDev

import numpy as np
import util.helpers
import copy

class MeterDev(LoadDev):	
	def __init__(self,  name,  host, commodities = ['ELECTRICITY'], flowNode = None, phase = 1, controller = None):
		LoadDev.__init__(self,  name,  None)
		self.devtype = "Meter"
		
		self.host = host
		self.host.addEntity(self)
		
		#params
		self.timeBase = self.host.timeBase
		
		#links
		self.devices = []
		self.controller = controller

		#link with the loadflow sim
		self.flowNode = flowNode
		self.phase = phase
		
		#Note a meter can only measure one commodity (it is close to the old Pools by Molderink and Bakker)
		self.commodities = commodities
		self.consumption = {}
		self.selfConsumption = 0.0	# Internal use of energy

		self.costs = 0.0
		self.costPerWh = 0.0002
		self.costsConnection = (224.27 + 54.01) # Enexis + Nuon costs for delivery in 2018
		self.costsConnectionInterval = 0.0

		self.imported = 0.0
		self.exported = 0.0

		# indicate whether the grid connection is active
		self.activeConnection = True

		# self.costStorage = {}
		# self.planStorage = {}
		# self.costCounter = 0
		# self.costInterval = 3600*24 #24 hours
		# self.costTimeBase = 900 # Align with controller

		# persistence
		if self.persistence != None:
			self.watchlist += ["costs", "imported", "exported"]
			self.persistence.setWatchlist(self.watchlist)

	def requestTickets(self, time):
		# self.host.registerTicket(30000) # preTick
		# self.host.registerTicket(101000) # timeTick
		self.ticketCallback.clear()
		self.registerTicket(self.host.staticTicketMeasure, 'measure', register=False)
		self.registerTicket(self.host.staticTicketRTMeasure, 'measure', register=False)

	# def announceTicket(self, time, number):
	# 	self.measure(time)

	def startup(self):
		self.lockState.acquire()
		for c in self.commodities:
			self.consumption[c] = complex(0.0, 0.0)

		if self.flowNode != None:
			if not isinstance(self.flowNode, str):
				self.flowNode.addMeter(self, self.phase)
			else:
				self.zCall(self.flowNode, "addMeter", self.name, self.phase)

		self.costsConnectionInterval = self.costsConnection / (365 * 24 * (3600.0/self.timeBase))

		self.lockState.release()

		#append the meter to the host
		self.host.addMeter(self)

	def timeTick(self, time, deltatime=0):
		pass
			
	def logStats(self, time):
		self.lockState.acquire()
		for c in self.commodities:
			self.logValue('W-power.real.c.'+c,self.consumption[c].real)
			self.logValue('Wh-energy.c.'+c, self.consumption[c].real / (3600.0 / self.timeBase))
			if self.host.extendedLogging:
				self.logValue("W-power.imag.c."+c, self.consumption[c].imag)

		if self.host.extendedLogging:
			self.logValue("W-power-imported", self.imported.real) # Smart meter readings
			self.logValue("W-power-exported", self.exported)
			self.logValue("W-power-self-consumed", self.selfConsumption.real)

			self.logValue("Wh-energy-imported", self.imported / (3600.0 / self.timeBase)) # Smart meter readings
			self.logValue("Wh-energy-exported", self.exported / (3600.0 / self.timeBase))
			self.logValue("Wh-energy-self-consumed", self.selfConsumption / (3600.0 / self.timeBase))

			# self.logValue("M-costs-cumulative", self.costs + self.costsConnectionInterval)

		self.lockState.release()

	def shutdown(self):
		LoadDev.shutdown(self)

#### INTERFACING
	def getProperties(self):
		r = LoadDev.getProperties(self) 	# Get the properties of the overall Device class, which already includes global properties

		return r


#### LOCAL HELPERS
	def measure(self,  time, deltatime=None):
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

		for c in self.commodities:
			total[c] = complex(int(total[c].real), int(total[c].imag))

		self.lockState.acquire()

		# Detect change:
		if deltatime is not None and self.consumption != total:
			# Change detected, request another delta-control iteration to evaluate whether the system is stable:
			self.registerTicket(deltatime+100, 'measure')
			# Also, since there is a change, we should execute a new load-flow simulation:
			if self.flowNode is not None:
				self.zCall(self.flowNode, "registerTicket", deltatime+1, 'simulate') # FIXME: Would be nicer to request a new loadflow through a specific function that is more descriptive

		for c in self.commodities:
			self.consumption[c] = total[c]

			# Costs:
			self.costs += (self.consumption[c].real / (3600.0 / self.timeBase)) * self.costPerWh

			# Import export counters:
			if self.consumption[c].real > 0:
				self.imported += self.consumption[c].real
			elif self.consumption[c].real < 0:
				self.exported -= self.consumption[c].real

			# Self consumption:
			self.selfConsumption += min(consumption[c], production[c])

		self.lockState.release()

	def addDevice(self, device, attachFlow=True):
		self.devices.append(device)
		if attachFlow: # NOTE: This is not the flow interface, just an option to have the device access measurement data
			if not isinstance(device, str):
				device.addMeter(self)
			else:
				self.zCall(device, "addMeter", self.name)

	def addController(self, ctrl):
		self.controller = ctrl

	def getVoltage(self, phase = None):
		if self.flowNode is not None:
			if phase is None:
				phase = self.phase
			return self.zCall(self.flowNode, "getLNVoltage", phase)
			
		else:
			assert(False)

	def getFrequency(self):
		if self.flowNode is not None:
			return self.zCall(self.flowNode, "getFrequency")
		else:
			assert(False)

	def unPowered(self):
		# Set the device consumption to zero
		for c in self.commodities:
			self.zCast(self.devices, 'unPowered', c)

		# Update the total consumption
		# FIXME: Actually we should update all meters to have the correct values for other energy carriers, but for now we are only interested in electricity
		# This may be fixed in the future with a more advanced, dependency based, simulation flow
		self.measure(None)
