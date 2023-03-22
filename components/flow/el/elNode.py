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
from flow.node import Node
from util.clientCsvReader import ClientCsvReader

import math
import cmath

class ElNode(Node):
	def __init__(self,  name,  flowSim, host):
		Node.__init__(self,  name,  flowSim, host)

		self.devtype = "ElectricityNode"

		self.hasNeutral = True
		self.phases = 3

		#Bookkeeping:
		self.voltage = [complex(0.0, 0.0)] * (self.phases+1)
		self.prevVoltage = [complex(0.0, 0.0)] * (self.phases+1)
		self.lastUpdate = -1

		#params
		self.nominalVoltage = [complex(0.0, 0.0)] * (self.phases+1)
		self.angles = [complex(0.0, 0.0)] * (self.phases+1)
		self.consumption = [complex(0.0, 0.0)]  * (self.phases+1)

		self.metersL1 = []
		self.metersL2 = []
		self.metersL3 = []
		self.meters = [] #Three phase balanced loads

		#limits
		self.maxVoltage = None
		self.minVoltage = None
		self.maxVuf = None

		self.powered = [True, True, True, True]

		#CSV reading parameters
		self.filename = None

		self.readers = []

		if self.host != None:
			self.timeOffset = host.timeOffset

	def startup(self):
		if self.filename is not None:
			for i in self.phases+1:
				self.readers.append(ClientCsvReader(dataSource=self.filenames[i], timeBase=self.timeBase, column=i, timeOffset=self.timeOffset, host=self.host))

	def shutdown(self):
		pass

	def conductors(self):
		# Convention used here is that the first index is always the neutral conductor, even for nodes without a neutral conductor.
		startIndex = 1
		if self.hasNeutral:
			startIndex = 0

		return range(startIndex, (self.phases+1))

	def reset(self, restoreGrid = True):
		if len(self.readers) == self.phases+1:
			for i in self.phases+1:
				self.voltage[i] = cmath.rect(self.readers[i].readValue(self.host.time(), None, self.timeBase), math.radians(self.angles[i]))

		else:
			for conductor in self.conductors():
				self.voltage[conductor] = cmath.rect(self.nominalVoltage[conductor], math.radians(self.angles[conductor]))

		#Set the previous voltage, avoid instant convergence..
		self.prevVoltage = list(self.voltage)

		if restoreGrid:
			self.powered = [True] * (self.phases+1)


	def doForwardSweep(self, previousNode, cable):
		#save the previous voltage
		self.prevVoltage = list(self.voltage)

		#calculate the voltage drop
		for conductor in self.conductors():
			self.voltage[conductor] = previousNode.voltage[conductor] - cable.voltageDrop(conductor)

			# set the flow direction in the cable
			try:
				if abs(self.voltage[conductor]) - abs(previousNode.voltage[conductor]) < 0:
					cable.flowDirection[conductor] = 1
				else:
					cable.flowDirection[conductor] = -1
			except:
				pass

	def doBackwardSweep(self, cable):
		current = [complex(0.0, 0.0)] * (self.phases+1)
		#Get all loads connected to this node

		#First obtain the load at meters, if not done so:
		if self.lastUpdate < self.host.time():
			self.lastUpdate = self.host.time()

		# Refresh self.consumptionLx
		self.getConsumption()

		# Calculate
		if self.hasNeutral:
			for i in range(1, (self.phases+1)):
				current[i] += (self.consumption[i] / self.getLNVoltage(i)).conjugate()
		else:
			for i in range(1, (self.phases+1)):
				current[i] += (self.consumption[i] / self.getLLVoltage(i)).conjugate()
				current[(i%self.phases)+1] += (-1 * (self.consumption[i] / self.getLLVoltage(i)).conjugate() )

		#now add the currents from all other cables:
		for outCable in self.edges:
			if outCable != cable:
				for conductor in self.conductors():
					current[conductor] += outCable.current[conductor]

		# Calculate neutral current if neutral is available
		if self.hasNeutral:
			current[0] = complex(0.0,0.0)
			for i in range(1, (self.phases+1)):
				current[0] += -current[i]

		cable.current = list(current)

	def getConsumption(self):
		self.consumption = [complex(0.0, 0.0)] * (self.phases+1)

		# Get the consumption
		if len(self.meters) > 0:
			results = self.zGet(self.meters, 'consumption')
			for r in results.values():
				for c in r:
					for i in range(1, (self.phases+1)):
						self.consumption[i] += r[c] / self.phases

		# Appending meters, this may crash upon errors in the model by an end user!
		if len(self.metersL1) > 0:
			assert(self.phases >= 1)
			results = self.zGet(self.metersL1, 'consumption')
			for r in results.values():
				for c in r:
					self.consumption[1] += r[c]

		if len(self.metersL2) > 0:
			assert (self.phases >= 2)
			results = self.zGet(self.metersL2, 'consumption')
			for r in results.values():
				for c in r:
					self.consumption[2] += r[c]

		if len(self.metersL3) > 0:
			assert (self.phases >= 3)
			results = self.zGet(self.metersL3, 'consumption')
			for r in results.values():
				for c in r:
					self.consumption[3] += r[c]

		# Check if we are powered
		for phase in range(1, (self.phases+1)):
			if not self.powered[phase]:
				self.consumption[phase] = complex(0.0, 0.0)

		consSum = complex(0.0,0.0)
		for i in range(1, (self.phases+1)):
			consSum += self.consumption[i]

		return consSum

	def getConvergenceError(self):
		result = 0.0
		for conductor in self.conductors():
			error = abs(abs(self.voltage[conductor]) - abs(self.prevVoltage[conductor]))
			if error > result:
				result = error

		return result

	def getLNVoltage(self, phase):
		assert(self.hasNeutral)
		assert(phase < len(self.voltage) and phase > 0 and phase <= self.phases)
		result = self.voltage[phase] - self.voltage[0]
		return result

	def getLLVoltage(self, phase):
		assert(phase < len(self.voltage) and phase > 0 and phase <= self.phases)
		otherPhase = phase + 1
		if otherPhase >= len(self.voltage):
			otherPhase = 1
		return self.voltage[phase] - self.voltage[otherPhase]

	def getUnbalance(self):
		a = complex(-0.5, math.sqrt(3)/2)
		aa = a*a

		try:
			normalComponent = (self.voltage[1] + self.voltage[2]*a + self.voltage[3]*aa) / 3.0
			negativeComponent = (self.voltage[1] + self.voltage[2]*aa + self.voltage[3]*a) / 3.0
			r = (abs(negativeComponent) / abs(normalComponent)) * 100.0
		except:
			# Not a three phase system or division by zero
			r = 0.0

		return r

	def getFrequency(self):
		return self.flowSim.frequency


	def updatePhysicalState(self, edge):
		p = True
		for phase in edge.conductors():
			self.powered[phase] = edge.powered[phase]
			if not self.powered[phase]:
				self.logWarning("Phase "+str(phase)+" not powered!")
				self.voltage[phase] = complex(0.0, 0.0)
				p = False

		# Now we'd like to set the meters according to whether they are powered
		# FIXME: Update the meter such that we can also set all attached device consumptions to 0!
		if not p:
			self.zCast(self.meters, 'unPowered')

		if self.phases >= 1 and not self.powered[1]:
			self.zCast(self.metersL1, 'unPowered')

		if self.phases >= 2 and not self.powered[2]:
			self.zCast(self.metersL2, 'unPowered')

		if self.phases >= 3 and not self.powered[3]:
			self.zCast(self.metersL3, 'unPowered')

	def estimateReliability(self):
		pass

	def checkViolations(self):
		violations = 0

		if self.hasNeutral:
			for i in range(1, len(self.voltage)):
				if abs(self.getLNVoltage(i)) > self.maxVoltage or abs(self.getLNVoltage(i)) < self.minVoltage:
					violations += 1
		else:
			for i in range(1, len(self.voltage)):
				if abs(self.getLLVoltage(i)) > self.maxVoltage or abs(self.getLLVoltage(i)) < self.minVoltage:
					violations += 1

		if self.getUnbalance() > self.maxVuf:
			violations += 1

		if violations > 0:
			self.logWarning(str(violations)+" voltage limits violated")

		self.logValue("n-violations.powerquality.voltage", violations)

	def logStats(self, time):
		if self.hasNeutral:
			for i in range(1, self.phases+1):
				self.logValue("V-voltage.c.L"+str(i)+"N", abs(self.getLNVoltage(i)))
		else:
			for i in range(1, self.phases+1):
				self.logValue("V-voltage.c.L"+str(i)+"-L"+str(((i)%self.phases)+1), abs(self.getLLVoltage(i)))

		if self.hasNeutral:
			self.logValue("V-voltage.c.NGnd", abs(self.voltage[0]))

		self.logValue("p-unbalance.VUF", abs(self.getUnbalance()))
		self.checkViolations()

	def addMeter(self, meter, phase=None):
		if(phase == 1 and self.phases >= 1):
			self.metersL1.append(meter)
		elif(phase == 2 and self.phases >= 2):
			self.metersL2.append(meter)
		elif(phase == 3 and self.phases >= 3):
			self.metersL3.append(meter)
		elif(phase is None):
			self.meters.append(meter)
		else:
			assert(False) #Impossible option

