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

from flow.el.elNode import ElNode

# US Triplex LV node
class TriLvNode(ElNode):
	def __init__(self,  name,  flowSim, host):
		ElNode.__init__(self,  name,  flowSim, host)

		self.devtype = "ElectricityTriLowVoltageNode"

		self.hasNeutral = True
		self.phases = 2

		# Bookkeeping:
		self.voltage = [complex(0.0, 0.0)] * self.phases
		self.prevVoltage = [complex(0.0, 0.0)] * self.phases
		self.lastUpdate = -1

		self.metersCombined = []

		#params
		self.nominalVoltage = [0.0, 120.0, 120.0]
		self.angles = [0.0, -0.0, -180.0]
		self.consumption = [0.0] * self.phases+2

		#limits
		self.maxVoltage = 126.0 # ANSI C84.1 Range A
		self.minVoltage = 114.0	# ANSI C84.1 Range A
		self.maxVuf = 100		# Does not apply


	# FIXME: Check if we need to do something special with 240V devices that connect to both phases
	def doBackwardSweep(self, cable):
		current = [complex(0.0, 0.0)] * (self.phases+1)
		#Get all loads connected to this node

		#First obtain the load at meters, if not done so:
		if self.lastUpdate < self.host.time():
			self.lastUpdate = self.host.time()

		# Refresh self.consumption
		self.getConsumption()

		# Calculate the split phase currents
		if self.hasNeutral:
			for i in range(1, (self.phases+1)):
				current[i] += (self.consumption[i] / self.getLNVoltage(i)).conjugate()
		else:
			for i in range(1, (self.phases+1)):
				current[i] += (self.consumption[i] / self.getLLVoltage(i)).conjugate()

		# Calculate the two phase (240V) currents, for this we use the 3rd phase index
		combinedPhaseCurrent = (self.consumption[3] / self.getLLVoltage(1)).conjugate()
		current[1] += combinedPhaseCurrent
		current[2] -= combinedPhaseCurrent

		#now add the currents from all other cables:
		for outCable in self.edges:
			if outCable != cable:
				for conductor in self.conductors():
					current[conductor] += outCable.current[conductor]

		# Calculate neutral current if neutral is available
		if self.hasNeutral:
			current[0] = complex(0.0,0.0)
			for i in range(1, (self.phases+1)):
				current[0] -= -current[i]

		cable.current = list(current)


	def getConsumption(self):
		self.consumption = [complex(0.0, 0.0)] * self.phases+2

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

		if len(self.metersCombined) > 0:
			results = self.zGet(self.metersCombined, 'consumption')
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

	def addMeter(self, meter, phase=None):
		if(phase == 1 and self.phases >= 1):
			self.metersL1.append(meter)
		elif(phase == 2 and self.phases >= 2):
			self.metersL2.append(meter)
		# Using phase 3 as the combined 240V phase
		elif(phase == 3):
			self.metersCombined.append(meter)
		elif(phase is None):
			self.meters.append(meter)
		else:
			assert(False) #Impossible option