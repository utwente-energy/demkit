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


from dev.bufDev import BufDev
from dev.device import Device

import math
import copy

# Buffer device to merge virtual buffers
class BufDevMerger(BufDev):
	def __init__(self,  name,  host, meter = None, ctrl = None, congestionPoint = None):
		BufDev.__init__(self,  name,  host, meter, ctrl, congestionPoint)

		# Additional code
		self.virtualBuffers = [] # in order of priorities!


	# Changed
	def preTick(self, time, deltatime=0):
		# Pretick the virtual devices to have them update their SoC
		for vBuffer in self.virtualBuffers:
			self.zCall(vBuffer, 'preTick', time)

		# Using the previous set consumption of all the buffers, assuming this is also not changed for the virtual buffers above
		self.lockState.acquire()
		consumption = 0
		for c in self.commodities:
			# find associated efficiency
			if not self.useInefficiency:
				consumption += self.consumption[c].real
			else:
				consumption += self.chargeForConsumption(self.consumption[c].real)

		#First update the SoC
		self.soc += consumption * (self.host.timeBase / 3600.0)
		self.soc -= self.selfConsumption * (self.host.timeBase / 3600.0)
		
		#now make sure that we are still in the SoC constraints:
		self.soc = min(self.capacity, max(self.soc, 0))
		
		#avoid weird rounding stuff:
		if self.soc >= self.capacity*0.99999:
			self.soc = self.capacity

		self.lockState.release()

		self.checkFillMarks()

	# Changed!
	def timeTick(self, time, deltatime=0):
		oldConsumption = copy.deepcopy(self.consumption)
		consumption = {}
		for c in self.commodities:
			consumption[c] = 0.0 # Only using real values first

		maxPower = min(self.chargingPowers[1], ((self.capacity-self.soc) * (3600.0 / self.host.timeBase)))
		minPower = max(self.chargingPowers[0], (-self.soc * (3600.0 / self.host.timeBase)))

		for vBuffer in self.virtualBuffers:
			self.zCall(vBuffer, 'timeTick', time, deltatime)

		withinBounds = True
		for vBuffer in self.virtualBuffers:
			cons = self.zGet(vBuffer, 'consumption')
			for c in cons:
				if c in self.commodities:
					consumption[c] += cons[c].real

				if consumption[c] < minPower or consumption[c] > maxPower:
					withinBounds = False
					break

		# Now we need to fix the aggregated power with the prioritization
		if not withinBounds:
			consumption = {}
			for c in self.commodities:
				consumption[c] = 0.0  # Only using real values first

			desired = {}
			alloc = {}

			for vBuffer in self.virtualBuffers:
				# Get the resulting consumption
				cons = self.zGet(vBuffer, 'consumption')

				# bookkeeping
				desired[vBuffer] = {}
				alloc[vBuffer] = {}
				for c in cons:
					desired[vBuffer][c] = cons[c]
					alloc[vBuffer][c] = 0.0


			# Looping along all virtual buffers to allocate power headroom of the actual buffer devices
			looping = True
			while looping:
				for vBuffer in self.virtualBuffers:

					# Check the consumption
					# FIXME: Does not yet check afterwards if there is a capacity left (e.g. buf 2 likes to charge, but is limited, where buf 3 can discharge and creates headroom for buf 2)
					changeDetected = False

					for c in cons:
						if c in self.commodities:
							if desired[vBuffer][c] != alloc[vBuffer][c]:
								cons[c] = desired[vBuffer][c] - alloc[vBuffer][c]
								old = alloc[vBuffer][c].real

								# See if we can add some charge/discharge power to this vBuffer
								if minPower <= consumption[c].real + cons[c].real <= maxPower:
									consumption[c] += cons[c].real
								elif consumption[c].real + cons[c].real < minPower:
									cons[c] = minPower - consumption[c]
									consumption[c] = minPower
								elif consumption[c].real + cons[c].real > maxPower:
									cons[c] = maxPower - consumption[c]
									consumption[c] = maxPower

								cons[c] = complex(cons[c], 0.0)

								# Change the allocation
								alloc[vBuffer][c] += cons[c]

								if alloc[vBuffer][c].real != old:
									# change in allocation detected, re-run the loop
									changeDetected = True

						else:
							self.logError("For now we only support completely overlapping commodities")

					if changeDetected:
						looping = True
						break
					else:
						looping = False

			# Communicate back the result
			for vBuffer in self.virtualBuffers:
				self.zSet(vBuffer, 'consumption', alloc[vBuffer])

			# for vBuffer in self.virtualBuffers:
			# 	# Get the resulting consumption
			# 	cons = self.zGet(vBuffer, 'consumption')
			#
			# 	# Check the consumption
			# 	# FIXME: Does not yet check afterwards if there is acapacity left (e.g. buf 2 likes to charge, but is limited, where buf 3 can discharge and creates headroom for buf 2)
			# 	for c in cons:
			# 		if c in self.commodities:
			# 			if minPower <= consumption[c] + cons[c].real <= maxPower:
			# 				consumption[c] += cons[c].real
			# 			elif consumption[c] + cons[c] < minPower:
			# 				cons[c] = minPower - consumption[c]
			# 				consumption[c] = minPower
			# 			elif consumption[c] + cons[c] > maxPower:
			# 				cons[c] = maxPower - consumption[c]
			# 				consumption[c] = maxPower
			# 			cons[c] = complex(cons[c], 0.0)
			# 		else:
			# 			self.logError("For now we only support completely overlapping commodities")
			#
			# 	# Communicate back the result
			# 	self.zSet(vBuffer, 'consumption', cons)

		self.lockState.acquire()
		# Set the resulting consumption
		for c in self.commodities:
			self.consumption[c] = complex(consumption[c], 0.0)
		self.prunePlan()

		# FIXME: I think we can do without this code
		# Add the self-consumption properly
		assert(self.lossOverTime == 0) # Unsupported
		self.selfConsumption = self.lossOverTime

		# From here on we have the old code to ensure that the consumption stays within bounds. Normally, this should be fine!

		totalConsumption = 0
		# Perform consistency checks.
		for c in self.commodities:
			totalConsumption += self.consumption[c].real

		# buffer underrun / overflow check and make the device fix this!
		if ((self.soc * (3600.0 / self.host.timeBase) + totalConsumption + self.selfConsumption) * (self.host.timeBase / 3600.0)) > self.capacity:
			#We have a buffer overflow:
			reduceBy = (((self.soc * (3600.0 / self.host.timeBase) + totalConsumption + self.selfConsumption) * (self.host.timeBase / 3600.0)) - self.capacity) / (self.host.timeBase / 3600.0) / len(self.commodities)
			for c in self.commodities:
				self.consumption[c] = max(self.chargingPowers[0]/self.chargingEfficiency[0], min(self.consumption[c].real-self.consumptionForCharge(reduceBy), self.chargingPowers[-1]/self.chargingEfficiency[-1]))

		elif ((self.soc * (3600.0 / self.host.timeBase) + totalConsumption + self.selfConsumption) * (self.host.timeBase / 3600.0)) < 0.0:
			#We have a buffer underflow:
			increaseBy = ((abs(self.soc * (3600.0 / self.host.timeBase) + totalConsumption + self.selfConsumption) * (self.host.timeBase / 3600.0))) / (self.host.timeBase / 3600.0) / len(self.commodities)
			for c in self.commodities:
				self.consumption[c] = max(self.chargingPowers[0]/self.chargingEfficiency[0], min(self.consumption[c].real+self.consumptionForCharge(increaseBy), self.chargingPowers[-1]/self.chargingEfficiency[-1]))


		for c in self.commodities:
			self.consumption[c] = complex(int(self.consumption[c].real), 0.0)


		# Check if we should receive control again:
		if oldConsumption != self.consumption:
			# Change detected, request a new interval for control
			if self.parent is not None:
				self.registerTicket(deltatime+100, 'timeTick')
			elif self.controller is not None:
				pass
			elif self.meter is not None:
				self.registerTicket(deltatime+100, 'timeTick')

		self.lockState.release()








	def localControl(self, time):
		assert(False)
		consumption = {}
		for c in self.commodities:
			consumption[c] = 0.0  # Only using real values first

		maxPower = min(self.chargingPowers[1], ((self.capacity - self.soc) * (3600.0 / self.host.timeBase)))
		minPower = max(self.chargingPowers[0], (-self.soc * (3600.0 / self.host.timeBase)))

		# Apply online control only to the first virtual buffer
		# Reconsider the consumption of all other buffers as the real-time control may change what is possible!
		for vBuffer in self.virtualBuffers:
			if self.virtualBuffers[0] == vBuffer and self.virtualBuffers[0].meter is not None:
				# This is the highest prioritized buffer
				self.zCall(vBuffer, 'onlineControl')
				# FIXME: We may allow other controllers to do similar things by supplying a list, but I am not sure what works better
			else:
				self.zCall(vBuffer, 'virtualTimeTick',self.host.time())

		# Same code as before:
		withinBounds = True
		for vBuffer in self.virtualBuffers:
			cons = self.zGet(vBuffer, 'consumption')
			for c in cons:
				if c in self.commodities:
					consumption[c] += cons[c].real

				if consumption[c] < minPower or consumption[c] > maxPower:
					withinBounds = False
					break

		# Now we need to fix the aggregated power with the prioritization
		if not withinBounds:
			consumption = {}
			for c in self.commodities:
				consumption[c] = 0.0  # Only using real values first

			desired = {}
			alloc = {}

			for vBuffer in self.virtualBuffers:
				# Get the resulting consumption
				cons = self.zGet(vBuffer, 'consumption')

				# bookkeeping
				desired[vBuffer] = {}
				alloc[vBuffer] = {}
				for c in cons:
					desired[vBuffer][c] = cons[c]
					alloc[vBuffer][c] = 0.0


			looping = True
			while looping:
				for vBuffer in self.virtualBuffers:

					# Check the consumption
					# FIXME: Does not yet check afterwards if there is a capacity left (e.g. buf 2 likes to charge, but is limited, where buf 3 can discharge and creates headroom for buf 2)
					changeDetected = False

					for c in cons:
						if c in self.commodities:
							if desired[vBuffer][c] != alloc[vBuffer][c]:
								cons[c] = desired[vBuffer][c] - alloc[vBuffer][c]
								old = alloc[vBuffer][c].real

								# See if we can add some charge/discharge power to this vBuffer
								if minPower <= consumption[c].real + cons[c].real <= maxPower:
									consumption[c] += cons[c].real
								elif consumption[c].real + cons[c].real < minPower:
									cons[c] = minPower - consumption[c]
									consumption[c] = minPower
								elif consumption[c].real + cons[c].real > maxPower:
									cons[c] = maxPower - consumption[c]
									consumption[c] = maxPower

								cons[c] = complex(cons[c], 0.0)

								# Change the allocation
								alloc[vBuffer][c] += cons[c]

								if alloc[vBuffer][c].real != old:
									# change in allocation detected, re-run the loop
									changeDetected = True

						else:
							self.logError("For now we only support completely overlapping commodities")

					if changeDetected:
						looping = True
						break
					else:
						looping = False

			# Communicate back the result
			for vBuffer in self.virtualBuffers:
				self.zSet(vBuffer, 'consumption', alloc[vBuffer])

			# consumption = {}
			# for c in self.commodities:
			# 	consumption[c] = 0.0  # Only using real values first
			#
			# for vBuffer in self.virtualBuffers:
			# 	# Get the resulting consumFor now we only support completely overlapping commoditiesption
			# 	cons = self.zGet(vBuffer, 'consumption')
			#
			# 	# Check the consumption
			# 	for c in cons:
			# 		if c in self.commodities:
			# 			if minPower <= consumption[c] + cons[c].real <= maxPower:
			# 				consumption[c] += cons[c].real
			# 			elif consumption[c] + cons[c] < minPower:
			# 				cons[c] = minPower - consumption[c]
			# 				consumption[c] = minPower
			# 			elif consumption[c] + cons[c] > maxPower:
			# 				cons[c] = maxPower - consumption[c]
			# 				consumption[c] = maxPower
			#
			# 			cons[c] = complex(cons[c], 0.0)
			# 		else:
			# 			self.logError("For now we only support completely overlapping commodities")
			#
			# 	# Communicate back the result
			# 	self.zSet(vBuffer, 'consumption', cons)

		# Updating the local control rule
		self.lockState.acquire()
		# Set the resulting consumption
		for c in self.commodities:
			self.consumption[c] = complex(int(self.consumption[c].real), 0.0)


		# Check if we should receive control again:
		if oldConsumption != self.consumption:
			self.registerTicket(deltatime+100, 'timeTick')

		self.lockState.release()
