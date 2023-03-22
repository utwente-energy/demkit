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

class BufAuctionCtrl(DevAuctionCtrl):
	def __init__(self, name, dev, parent, host):
		DevAuctionCtrl.__init__(self,  name, dev, parent, host)

		self.devtype = "BufferController"

	def createDemandFunction(self):
		# Synchronize the device state:
		deviceState = self.updateDeviceProperties()

		result = DemandFunction()
		assert(self.devData['discrete'] == False) # Discrete device options not supported currently

		maximum = min( (self.devData['capacity'] - self.devData['soc'])*(3600.0/self.timeBase) , self.devData['chargingPowers'][-1])
		minimum = max( -self.devData['soc']*(3600.0/self.timeBase), self.devData['chargingPowers'][0])

		assert(maximum >= minimum)
		assert(maximum >= 0)
		assert(minimum <= 0)

		realSoC = self.devData['soc'] / self.devData['capacity'] #Fraction of the fill level

		result.addLine(maximum, 0.0, result.minComfort, (result.minComfort + 100 + (1-realSoC)*400))
		result.addLine(0.0, minimum, (result.maxComfort - realSoC*400 - 100), result.maxComfort)

		return result
