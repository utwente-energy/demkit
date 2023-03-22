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

class BtsAuctionCtrl(DevAuctionCtrl):
	def __init__(self, name, dev, parent, host):
		DevAuctionCtrl.__init__(self,  name, dev, parent, host)

		self.devtype = "BufferTimeshiftableController"

	def createDemandFunction(self):
		# Synchronize the device state:
		deviceState = self.updateDeviceProperties()

		result = DemandFunction()

		# Static load has no flex
		assert(self.devData['discrete'] == False) #FIXME: Discrete auction not supported currently! See T185

		remainingCharge = self.devData['capacity'] - self.devData['soc']

		if not self.devData['available'] or remainingCharge == 0:
			result.addLine(0,0,result.minComfort, result.maxComfort) #No car available, no other option!
		else:
			# First find out the charge bounds
			maximum = min( remainingCharge*(3600.0/self.host.timeBase), self.devData['chargingPowers'][-1])

			#minimum is a bit harder:
			minimum = self.devData['chargingPowers'][0]
			if (remainingCharge * 3600.0) / max(1, (self.devData['currentJob']['endTime'] - self.host.time() - self.host.timeBase)) >= self.devData['chargingPowers'][-1]:
				minimum = self.devData['chargingPowers'][-1] #deadline approaching, must charge!

			#now determine the preferred level based on SoC and deadline
			preferred = (remainingCharge * 3600.0) / max(1, (self.devData['currentJob']['endTime'] - self.host.time()))

			#Checks to make sure that the function will be concave
			minimum = min(maximum, minimum)
			if preferred > maximum:
				preferred = maximum
			if minimum > preferred:
				preferred = minimum

			#now construct the bid:
			result.addLine(maximum, preferred, result.minComfort+300, 0)
			result.addLine(preferred, minimum, 0, result.maxComfort-300)

			#curtailment zone:
			if minimum >= self.devData['chargingPowers'][0]:
				result.addLine(minimum, self.devData['chargingPowers'][0], result.maxComfort+1, result.maxPrice)

		return result;
