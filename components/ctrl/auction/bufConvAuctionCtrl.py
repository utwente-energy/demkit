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
from ctrl.auction.devAuctionCtrl import DevAuctionCtrl

class BufConvAuctionCtrl(DevAuctionCtrl):
	def __init__(self, name, dev, parent, host):
		DevAuctionCtrl.__init__(self,  name, dev, parent, host)

		self.devtype = "BufferConverterController"

	def createDemandFunction(self):
		# Synchronize the device state:
		deviceState = self.updateDeviceProperties()

		result = DemandFunction()
		assert(self.devData['discrete'] == False) # Discrete options not supported currently

		#Not so clever bid: Just put the current measured consumption at 0 and possible min and max on both ends

		#determine the bounds and preferred
		#Note that we use the current consumption for the outflow!
		if self.devData['selfConsumption'] is not None:
			consumption = self.devData['selfConsumption']
		else:
			consumption = 0.0

		maximum = min( ( (self.devData['capacity'] - self.devData['soc']) * (3600.0/self.host.timeBase) + consumption) / self.devData['cop'], self.devData['chargingPowers'][-1])
		minimum = 0.0
		if self.devData['soc']*(3600.0/self.host.timeBase) < consumption:
			minimum = (consumption/self.devData['cop']) - (self.devData['soc']*(3600.0/self.host.timeBase)/self.devData['cop'])
		if minimum >= maximum:
			#We cannot make the heatdemand
			minimum = maximum
		preferred = min(maximum, max(minimum, consumption/self.devData['cop']))

		#checks:
		assert(maximum >= minimum)
		assert(maximum >= preferred)
		assert(minimum <= preferred)

		result.addLine(maximum, preferred, result.minComfort, 0)
		result.addLine(preferred, minimum, 0, result.maxComfort)

		#curtailment and "burning"
		if minimum >= self.devData['chargingPowers'][0]:
			result.addLine(minimum, self.devData['chargingPowers'][0], result.maxComfort+1, result.maxPrice)
		if maximum <= self.devData['chargingPowers'][-1]:
			result.addLine(self.devData['chargingPowers'][-1], maximum, result.minPrice, result.minComfort-1)

		return result
