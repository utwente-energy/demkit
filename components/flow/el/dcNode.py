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

class DcNode(ElNode):
	def __init__(self,  name,  flowSim, host):
		ElNode.__init__(self,  name,  flowSim, host)

		self.devtype = "ElectricityDirectCurrentNode"

		self.hasNeutral = True
		self.phases = 1

		# Bookkeeping:
		self.voltage = [complex(0.0, 0.0)] * (self.phases+1)
		self.prevVoltage = [complex(0.0, 0.0)] * (self.phases+1)
		self.lastUpdate = -1

		#params
		self.nominalVoltage = [0.0, 380.0]
		self.angles = [0.0, 180.0]
		self.consumption = [0.0] * (self.phases+1)

		#limits
		self.maxVoltage = 380.0*1.1
		self.minVoltage = 380.0*0.9
		self.maxVuf = 100 #N/A


	def reset(self, restoreGrid = True):
		for conductor in self.conductors():
			self.voltage[conductor] = self.nominalVoltage[conductor]

		#Set the previous voltage, avoid instant convergence..
		self.prevVoltage = list(self.voltage)

		if restoreGrid:
			self.powered = [True] * (self.phases+1)


	def doForwardSweep(self, previousNode, cable):
		# save the previous voltage
		self.prevVoltage = list(self.voltage)

		# calculate the voltage drop
		for conductor in self.conductors():
			self.voltage[conductor] = previousNode.voltage[conductor].real - cable.voltageDrop(conductor).real

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
				current[i] += (self.consumption[i].real / self.getLNVoltage(i).real)
		else:
			for i in range(1, (self.phases+1)):
				current[i] += (self.consumption[i].real / self.getLLVoltage(i).ral)
				current[(i%self.phases)+1] += (-1 * (self.consumption[i].real / self.getLLVoltage(i).real))

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

	def getLNVoltage(self, phase):
		assert (self.hasNeutral)
		assert (phase < len(self.voltage) and phase > 0 and phase <= self.phases)
		result = self.voltage[phase].real - self.voltage[0].real
		return result


	def getUnbalance(self):
		return 0

	def getFrequency(self):
		return 0
