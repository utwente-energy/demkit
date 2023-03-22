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

class TsAuctionCtrl(DevAuctionCtrl):
	def __init__(self, name, dev, parent, host):
		DevAuctionCtrl.__init__(self,  name, dev, parent, host)

		self.devtype = "TimeshiftableController"
		self.comfortCutoff = 0

	def createDemandFunction(self):
		# Synchronize the device state:
		deviceState = self.updateDeviceProperties()

		result = DemandFunction()

		if not self.devData['available'] or self.devData['jobProgress'] == len(self.devData['profile']):
			#No job running or just finished, keep the device off
			result.addLine(0,0, result.minPrice, result.maxPrice)
		else:
			if self.devData['jobProgress'] == 0:
				#not running yet, so we have flex. Determine the last possible start, and based on this determine the turn-on point:
				lastStart = self.devData['currentJob']['endTime'] - len(self.devData['profile'])*self.devData['timeBase'] - self.timeBase;
				if lastStart >= self.host.time():
					result.addLine(self.devData['profile'][0].real, self.devData['profile'][0].real, result.minComfort, result.maxPrice-1)

					#load shedding
					result.addLine(0.0, 0.0, result.maxPrice, result.maxPrice)
				else:
					startPrice = max(result.minComfort, min(result.minComfort + ((result.maxComfort-result.minComfort) * (self.host.time() - self.devData['currentJob']['startTime']) / (lastStart - self.devData['currentJob']['startTime']) ) , result.maxComfort) )
					result.addLine(0.0 , 0.0, startPrice, result.maxPrice-1)
					result.addLine(self.devData['profile'][0].real, self.devData['profile'][0].real, result.minComfort, startPrice)

					#load shedding
					result.addLine(0.0, 0.0, result.maxPrice, result.maxPrice)
			else:
				#the device is running, simple approach for now is just too bid the current consumption:
				if self.commodities[0] in self.devData['consumption'] and self.devData['jobProgress'] < len(self.devData['profile']):
					result.addLine(self.devData['profile'][self.devData['jobProgress']].real, self.devData['profile'][self.devData['jobProgress']].real, result.minComfort, result.maxPrice-1)

					#load shedding
					result.addLine(0.0, 0.0, result.maxPrice, result.maxPrice)

				else:
					result.addLine(0.0, 0.0, result.minComfort, result.maxPrice-1)

		return result;
