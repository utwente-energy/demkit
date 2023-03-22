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

from ctrl.auction.devAuctionCtrl import DevAuctionCtrl

import math

class ThermalDevAuctionCtrl(DevAuctionCtrl):
	def __init__(self, name, dev, parent, host):
		DevAuctionCtrl.__init__(self,  name, dev, parent, host)

	def setControlResult(self):
		result = {}

		# Get the desired consumption for the main commodity
		power = self.updatedFunction.demandForPrice(self.currentPrice)

		# Now populate the result:
		# We need to explicitly set the energy consumption for each commodity
		for c in self.dev.commodities:
			result[c] = []

			if c == self.commodities[0]:
				# This is the main commodity, directly set the result
				tup = (self.host.time(), power)
			else:
				# Translate the target into the other commodity using the CoP:
				# However, we first need to determine how much heat will be produced:

				heatPower = min(self.dev.producingPowers[-1], max(self.dev.producingPowers[0], power * self.dev.cop[self.commodities[0]] * math.copysign(1, self.heatRequest) ) )

				if c == 'HEAT':
					tup = (self.host.time(), heatPower)
					# Note that we need to consider limits of the device here as well
				else:
					tup = (self.host.time(), math.copysign( (heatPower / self.dev.cop[c]), self.dev.cop[c]) )

			result[c].append(tup)

		# Call the function to set the planning:
		self.zCall(self.dev, 'setPlan', result)
