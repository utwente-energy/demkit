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


from dev.bufConvDev import BufConvDev
from dev.thermal.heatSourceDev import HeatSourceDev

import math

#Bufferconverter device
#Note that the buffer level is based on the secondary side!
class ThermalBufConvDev(HeatSourceDev, BufConvDev):
	def __init__(self,  name,  host):
		BufConvDev.__init__(self,  name,  None)
		HeatSourceDev.__init__(self,  name,  host)
		self.devtype = "BufferConverter"

		self.commodities = ['ELECTRICITY', 'HEAT'] # INPUT, OUTPUT
		self.producingPowers = [0, 20000]	# Output power of the source

		# Commodity wise cop:
		self.cop = {'ELECTRICITY': 4.0}

		self.heatProduction = 0.0 # This variable holds the heat production internally of the device

		self.producingTemperatures = [0, 60.0]	# Output power of the source

	def startup(self):
		BufConvDev.startup(self)

	def preTick(self, time, deltatime=0):
		# assert(self.discrete == False) # Discrete device functionality not implemented yet

		self.lockState.acquire()
		#First update the SoC
		self.soc += self.heatProduction * (self.host.timeBase / 3600.0)
		self.soc += self.consumption['HEAT'].real * (self.host.timeBase / 3600.0)
		
		#now make sure that we are still in the SoC constraints:
		self.soc = min(self.capacity, max(self.soc, 0))
		
		#avoid weird rounding stuff:
		if self.soc >= self.capacity*0.99999:
			self.soc = self.capacity
		self.lockState.release()

		#request for a replanning on marks and (re)set the flags accordingly
		if self.controller is not None:
			#test for marks and set flags accordingly
			if self.soc <= self.lowMark and self.flagLowMark == False:
				self.controller.triggerEvent("stateUpdate")
				self.flagLowMark = True
			if self.soc >= self.highMark and self.flagHighMark == False:
				self.controller.triggerEvent("stateUpdate")
				self.flagHighMark = True
				
			#Reset the flags	
			if self.flagHighMark == True and self.soc < self.highMark:
				self.flagHighMark = False
			if 	self.flagLowMark == True and self.soc > self.lowMark:
				self.flagLowMark = False


	def timeTick(self, time, deltatime=0):
		self.prunePlan()

		self.lockState.acquire()
		producingPowers = list(self.producingPowers)

		if self.smartOperation and not self.strictComfort and 'HEAT' in self.plan and len(self.plan['HEAT']) > 0:
			# If we have a planning without strict comfort, we follow the plan to produce energy
			producingPowers[0] = min(0, self.plan['HEAT'][0][1].real)
			producingPowers[-1] = max(0, self.plan['HEAT'][0][1].real)

			# In this case we need to take the current charge of the buffer into account to see how much we can add if the planning is low
			bufferEnergy = min(self.producingPowers[-1], self.soc / (self.host.timeBase / 3600.0) )
			producingPowers[1] = max(producingPowers[-1], bufferEnergy)

		# Now that we know how much we can produce / deliver, we can start the actual delivery:
		# First check how much demand we have in total for hot water
		self.dhwDemand = self.getDhwDemand(producingPowers)

		# Then supply the zones with heat
		producingPowers[0] = min(0, max(producingPowers[0], producingPowers[0]+abs(self.dhwDemand.real)))
		producingPowers[-1] = max(0, min(producingPowers[-1]-abs(self.dhwDemand.real), producingPowers[-1]))

		self.zoneDemand = self.getZoneDemand(producingPowers)

		# This gives us the total heat demand flowing out of the buffer
		self.consumption['HEAT'] = self.dhwDemand + self.zoneDemand

		# Determine the heat production,
		# WARNING: we assume that the planning is consistent with calculations here!
		# Note that we need to negate because of the internal heat production
		self.heatProduction = 0.0
		c = 'HEAT'
		if self.smartOperation and c in self.plan and len(self.plan[c]) > 0:
			self.heatProduction = self.plan[c][0][1].real
		else:
			if not self.discrete:
				self.heatProduction = -1 * self.consumption['HEAT']
			else:
				self.heatProduction = 0
				demand = -1 * self.consumption['HEAT']
				if self.soc * (3600.0 / self.host.timeBase) > demand and self.soc >= self.capacity*0.8:
					# Use the buffer
					self.heatProduction = 0
				elif self.soc * (3600.0 / self.host.timeBase) <= demand or self.soc <= self.capacity*0.5:
					for v in self.producingPowers:
						if v >= demand:
							self.heatProduction = v
							break
					if self.heatProduction == 0:
						self.heatProduction = self.producingPowers[-1]

		# buffer underrun / overflow check and make the device fix this!
		if (self.soc + (self.heatProduction + self.consumption['HEAT']) * (self.host.timeBase / 3600.0)) > self.capacity:
			#We have a buffer overflow, we need to produce less
			overflow = abs( ( self.soc + (self.heatProduction + self.consumption['HEAT']) * (self.host.timeBase / 3600.0)) - self.capacity) / (self.host.timeBase / 3600.0)

			# Detect whether we have a heating or cooling device (requires inversion):
			if self.producingPowers[-1] > 0:
				self.heatProduction = min(self.producingPowers[-1], max(self.heatProduction - overflow, self.producingPowers[0]))
			else:
				self.heatProduction = min(self.producingPowers[0], max(self.heatProduction - overflow, self.producingPowers[-1]))

			if self.controller is not None:
				self.lockState.release()
				self.controller.triggerEvent("stateUpdate")  # Replan for the sake of it
				self.lockState.acquire()

		elif (self.soc + (self.heatProduction + self.consumption['HEAT']) * (self.host.timeBase / 3600.0)) < 0.0:
			# We have a buffer under flow, we need to produce more
			underflow = 0.0
			if self.strictComfort:
				underflow = abs(self.soc + (self.heatProduction + self.consumption['HEAT']) * (self.host.timeBase / 3600.0) ) / (self.host.timeBase / 3600.0)

			# Detect whether we have a heating or cooling device (requires inversion):
			if self.producingPowers[-1] > 0:
				self.heatProduction = min(self.producingPowers[-1], max(self.heatProduction + underflow, self.producingPowers[0]))
			else:
				self.heatProduction = min(self.producingPowers[0], max(self.heatProduction + underflow, self.producingPowers[-1]))

			if self.controller is not None:
				self.lockState.release()
				self.controller.triggerEvent("stateUpdate") # Replan for the sake of it
				self.lockState.acquire()


		# Then we need to obtain the consumption of all other commodities based on the heat produced
		for c in self.commodities:
			if c != 'HEAT':
				self.consumption[c] = complex( math.copysign((self.heatProduction/self.cop[c]), self.cop[c]), 0.0)

		self.lockState.release()


	def logStats(self, time):
		self.lockState.acquire()
		try:
			for c in self.commodities:
				self.logValue("W-power.real.c." + c, self.consumption[c].real)
				if self.host.extendedLogging:
					self.logValue("W-power.imag.c." + c, self.consumption[c].imag)

				if self.smartOperation and c in self.plan and len(self.plan[c]) > 0:
					self.logValue("W-power.plan.real.c."+c, self.plan[c][0][1].real)
					if self.host.extendedLogging:
						self.logValue("W-power.plan.imag.c."+c, self.plan[c][0][1].imag)
		except:
			pass

		self.logValue("W-heat.supply.dhwtaps", self.dhwDemand.real )
		self.logValue("W-heat.supply.zones", self.zoneDemand.real )
		self.logValue("W-heat.production", self.heatProduction.real )
		self.logValue("Wh-energy.soc", self.soc)
		if self.host.extendedLogging:
			self.logValue("b-available", 1)

		self.lockState.release()
			
	def shutdown(self):
		pass	

#### INTERFACING
	def getProperties(self):
		r = BufConvDev.getProperties(self) 	# Get the properties of the overall Device class, which already includes global properties

		self.lockState.acquire()
		# Populate the result dict
		r['temperature'] = self.temperature
		r['cop'] = dict(self.cop)
		r['producingPowers'] = list(self.producingPowers)
		self.lockState.release()

		return r
