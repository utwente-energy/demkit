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
from ctrl.auction.thermal.thermalDevAuctionCtrl import ThermalDevAuctionCtrl

import math
import random

class ThermalBufConvAuctionCtrl(ThermalDevAuctionCtrl):
	def __init__(self, name, dev, parent, host):
		ThermalDevAuctionCtrl.__init__(self,  name, dev, parent, host)

		self.devtype = "BufferConverterController"

		self.heatRequest = 0.0
		self.coolRequest = 0.0

	def createDemandFunction(self):
		# Synchronize the device state:
		deviceState = self.updateDeviceProperties()

		result = DemandFunction()
		assert(self.devData['discrete'] == False) # Discrete options not supported currently
		assert(self.commodities[0] == 'ELECTRICITY')

		# FIXME: We use references to the device here, such that networking does not work yet
		# Fetch the total heat request
		self.heatRequest = 0.0
		for t in self.dev.dhwTaps:
			self.heatRequest += t.consumption['HEAT'].real
		for z in self.dev.thermostats:
			if z.heatDemand.real > 0:
				self.heatRequest += z.heatDemand.real
			else:
				self.coolRequest += z.heatDemand.real

		# Based on this, check the heat that we should ideally deliver based on the capabilities of the device
		desiredHeat = 0.0
		if self.heatRequest >= 0: # Heating has priority over cooling for now.
			# Heating
			desiredHeat = min(self.heatRequest, self.dev.producingPowers[-1])
		elif self.coolRequest < 0:
			# Cooling request, negative heat
			desiredHeat = -1 * max(self.coolRequest, self.dev.producingPowers[0])

		# Now check what we can do based on the current SoC:
		maximum = min( ( (self.devData['capacity'] - self.devData['soc']) * (3600.0/self.host.timeBase) + desiredHeat), self.devData['producingPowers'][-1])
		minimum = 0.0
		if self.devData['soc']*(3600.0/self.host.timeBase) < desiredHeat:
			minimum = desiredHeat - self.devData['soc']*(3600.0/self.host.timeBase)

		# Scale for CoP
		maximum = maximum / self.devData['cop'][self.commodities[0]]
		minimum = minimum / self.devData['cop'][self.commodities[0]]
		desiredHeat = desiredHeat / self.devData['cop'][self.commodities[0]]
		
		# Now,all values are expressed in heat
		# to obtain the relation wrt the commodity used in the auction (normally POWER (Electricity)), we need to divide this through the CoP.
		# Furthermore, we need to find out whether we our CoP is positive (e.g. for a heat pump) or negative (e.g. a CHP) to create the correct function.
		if self.dev.cop[self.commodities[0]] < 0:
			# Negative CoP, we will produce electricity given a certain demand. Hence we need to invert minumum and maximum:
			temp = minimum
			minimum = maximum
			maximum = temp
		
		if minimum >= maximum:
			#We cannot make the heatdemand
			minimum = maximum
		preferred = min(maximum, max(minimum, desiredHeat) )
		
		assert(maximum >= minimum)
		assert(preferred >= minimum)
		assert(maximum >= preferred)

		# If we have a buffer, we can play with the priority based on the SoC:
		if self.devData['capacity'] > 0:
			realSoC = self.devData['soc'] / self.devData['capacity'] #Fraction of the fill level

			# Now we create a demand function  based on the SoC, considering the battery deadband
			result.addLine(maximum, maximum, result.minComfort, result.minComfort + 200 + (1-realSoC)*300)
			result.addLine(maximum, preferred, result.minComfort + 200 + (1-realSoC)*300, 0)
			result.addLine(preferred, minimum, 0, result.maxComfort - realSoC*300 - 200)
			result.addLine(minimum, minimum, result.maxComfort - realSoC*300 - 200, result.maxComfort)
		else:
			# No buffer, just fulfill the demand
			result.addLine(preferred, preferred, result.minComfort, result.maxComfort)
			if preferred > 0:
				result.addLine(preferred, 0, result.maxComfort+1, result.maxPrice)
			else:
				result.addLine(0, preferred, result.minPrice, result.minComfort-1)

		# Now add the curtailment zones
		maxcurt = self.devData['producingPowers'][-1] / self.devData['cop'][self.commodities[0]]
		mincurt = self.devData['producingPowers'][0] / self.devData['cop'][self.commodities[0]]
		if maxcurt < mincurt:
			# swap
			temp = maxcurt
			maxcurt = mincurt
			mincurt = temp

		result.addLine(maxcurt, maximum, result.minPrice, result.minComfort-1)
		result.addLine(minimum, mincurt, result.maxComfort+1, result.maxPrice)

		return result;
