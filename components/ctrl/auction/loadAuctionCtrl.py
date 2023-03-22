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

class LoadAuctionCtrl(DevAuctionCtrl):
	def __init__(self, name, dev, parent, host):
		DevAuctionCtrl.__init__(self,  name, dev, parent, host)

		self.devtype = "LoadController"

	def createDemandFunction(self):
		# Synchronize the device state:
		deviceState = self.updateDeviceProperties()

		result = DemandFunction()

		# Static load has no flex
		if self.commodities[0] in self.devData['consumption']:
			consumption = self.devData['consumption'][self.commodities[0]].real
		else:
			consumption = 0.0

		if self.commodities[0] in self.devData['consumption']:
			result.addLine(consumption, consumption, result.minPrice, result.maxPrice)
		else:
			result.addLine(0.0, 0.0, result.minComfort, result.maxComfort)

		return result;
