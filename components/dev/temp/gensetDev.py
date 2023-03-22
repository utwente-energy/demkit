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


from util.influxdbReader import InfluxDBReader
from util.clientCsvReader import ClientCsvReader
import util.helpers

from dev.device import Device

class GensetDev(Device):
	# GENSET Device modelling multiple gensets for the QuinteQ project
	# FIXME: Simple initial file that has an internal controller, no fancy control (if that would be possible at all)
	def __init__(self,  name,  host, meter = None):
		Device.__init__(self,  name,  host)
		
		self.devtype = "Genset"
		
		#params
		self.numOfGens = 3
		self.powerMax = -10000	# Negative, because we are generating, per generator
		self.powerLimit = -10000 # Set a power limit to reduce the capacity like in Mali, per generator
		self.scaleUp = 0.8*self.powerMax	# Power to start a new genset
		self.scaleDown = 0.2*self.powerMax	# Power to stop a genset
		self.minRuntime = 1
		self.minCoolDownTime = 1	# Not used, we will rotate based on the longest off generator

		self.targetPower = 0 # Striving for balance
		self.meter = meter

		assert(self.meter is not None)
		assert(self.scaleDown > 0.5*self.scaleUp)
		assert(self.powerLimit >= self.powerMax) # cannot supply more then the gen can deliver
		assert(self.powerMax < 0) # Negative = Production!
		assert(self.powerLimit < 0) # Negative = Production!
		assert(self.powerLimit < self.scaleUp) # Otherwise we would have bad inversion

		self.runningGens = []
		self.stateTimeGens = []

		self.commodities = ['ELECTRICITY', 'DIESEL']

		self.consumption['ELECTRICITY'] = complex(0.0)
		self.consumption['DIESEL'] = complex(0.0)
		# FIXME: Need to add power to litres diesel

	# DIESEL CONVERSION TABLE
		self.efficiency = [
			[0, 0.1, 0.2, 0.4, 0.6, 0.8, 1],
			[0, 64, 77, 87, 90, 91, 100]
		]

	def requestTickets(self, time):
		Device.requestTickets(self, time)
		self.registerTicket(100090, 'timeTick', register=True)  # timeTick

	def startup(self):
		for i in range(0, self.numOfGens):
			self.runningGens.append(False)
			self.stateTimeGens.append(0)

		# Start the first generator
		self.runningGens[0] = True

		Device.startup(self)

	def preTick(self, time, deltatime=0):
		self.lockState.acquire()

		# Increment off time
		for i in range(0, self.numOfGens):
			self.stateTimeGens[i] += self.host.timeBase

		self.lockState.release()

	def timeTick(self, time, deltatime=0):
		self.prunePlan()
		self.localControl(time, deltatime)
				
	def logStats(self, time):
		# FIXME ADD number of gens running, efficiency, diesel consumption
		self.lockState.acquire()

		try:
			for c in self.commodities:
				self.logValue("W-power.real.c." + c, self.consumption[c].real)
				if self.host.extendedLogging:
					self.logValue("W-power.imag.c." + c, self.consumption[c].imag)

			for gen in range(0, self.numOfGens):
				if self.runningGens[gen]:
					self.logValue("n-generator-running."+str(gen), 1)
				else:
					self.logValue("n-generator-running." + str(gen), 0)
		except:
			pass

		# Figure out the diesel
		try:
			efficiency = self.calculateDiesel()
			dieselPower = 1/efficiency * self.consumption['ELECTRICITY'].real

			# Litres of diesel (https://nl.wikipedia.org/wiki/Energiedichtheid)
			litres = (-1*dieselPower*self.host.timeBase)/36000000

			self.logValue("W-power.real.c.DIESEL", dieselPower)
			self.logValue("L-litres.DIESEL", litres)
		except:
			pass

		self.lockState.release()

	def calculateDiesel(self):
		# Get the running gens
		runninggens = 0
		for gen in range(0, self.numOfGens):
			if self.runningGens[gen]:
				runninggens +=1

		# Obtain the efficiency
		if runninggens > 0:
			loadpergen = self.consumption['ELECTRICITY'].real / runninggens
			loading = min(1, max(0, loadpergen / self.powerMax))

			# see if we have a hit:
			if loading in self.efficiency[0]:
				idx = self.efficiency[0].index(loading)
				if loading == 0:
					efficiency = 1
				else:
					efficiency = self.efficiency[1][idx]

			else:
			# No direct hit, interpolate between the points:
				idx = 1
				while self.efficiency[0][idx] < loading:  # loop through the list to find the two corresponding indices
					idx += 1
					assert (idx < len(self.efficiency[0]))

				# print(idx)

				# now we should have the correct index, get left and right:
				left = idx - 1
				right = idx

				effDelta = self.efficiency[1][left] - self.efficiency[1][right]
				stepDelta = self.efficiency[0][right] - self.efficiency[0][left]
				assert (effDelta < 0)

				efficiency = self.efficiency[1][left] - ((effDelta / stepDelta) * (loading - self.efficiency[0][left]))
				efficiency = (efficiency/100)

			return efficiency

		else:
			return 0




#### INTERFACING
	def getProperties(self):
		r = Device.getProperties(self) 	# Get the properties of the overall Device class, which already includes global properties

		# self.lockState.acquire()
		# self.lockState.release()

		return r

# Local control
	def localControl(self, time, deltatime=0):
		# Obtaining the external measurement (externalize?)
		measuredPower = complex(0.0, 0.0)
		# Obtain the current power consumption of all meters
		if type(self.meter) is list:
			for m in self.meter:
				m.measure(self.host.time())
				cons = self.zGet(m, 'consumption')
				for c in self.commodities:
					try:
						measuredPower += cons[c]
					except:
						pass
		else:
			self.meter.measure(self.host.time())
			for c in self.commodities:
				cons = self.zGet(self.meter, 'consumption')
				try:
					measuredPower += cons[c]
				except:
					pass

		# Calculate the settings
		measuredPower = measuredPower.real
		currentPower = self.consumption['ELECTRICITY'].real
		diff = self.targetPower - measuredPower.real
		newPower = min(0, currentPower + diff)

		# Now determine if we need to start/stop a gen
		runningGens = 0
		for i in range(0, self.numOfGens):
			if self.runningGens[i]:
				runningGens += 1

		avgPower = newPower / runningGens

		# Add as much generators as needed (note the sign!)
		if avgPower < self.scaleUp:
			while avgPower < self.scaleUp and runningGens < self.numOfGens:
				candidate = -1
				offtime = -1
				for i in range(0, self.numOfGens):
					if not self.runningGens[i] and self.stateTimeGens[i] > offtime:
						if self.stateTimeGens[i] >= self.minCoolDownTime:
							candidate = i
							offtime = self.stateTimeGens[i]

				# Start the candidate generator
				self.runningGens[candidate] = True
				self.stateTimeGens[candidate] = 0
				runningGens += 1

				avgPower = newPower / runningGens

		# Stop as much generators as needed (note the sign!)
		elif avgPower > self.scaleDown:
			while avgPower > self.scaleDown and runningGens> 1:
				candidate = -1
				ontime = -1
				for i in range(0, self.numOfGens):
					if self.runningGens[i] and self.stateTimeGens[i] > ontime:
						if self.stateTimeGens[i] >= self.minRuntime:
							candidate = i
							ontime = self.stateTimeGens[i]

				# Start the candidate generator
				self.runningGens[candidate] = False
				self.stateTimeGens[candidate] = 0
				runningGens -= 1

				avgPower = newPower / runningGens

		# print(runningGens)
		self.consumption['ELECTRICITY'] = complex(max(newPower, max(self.powerLimit*runningGens, self.powerMax*runningGens)), 0.0)


	# HACK!

	def getAvgLoad(self):
		runningGens = 0
		for i in range(0, self.numOfGens):
			if self.runningGens[i]:
				runningGens += 1

		avgPower = self.consumption['ELECTRICITY'].real / runningGens
		avgLoad = abs((avgPower/self.powerMax)/runningGens)

		return avgLoad

	def getGensRunning(self):
		runningGens = 0
		for i in range(0, self.numOfGens):
			if self.runningGens[i]:
				runningGens += 1
		return runningGens











