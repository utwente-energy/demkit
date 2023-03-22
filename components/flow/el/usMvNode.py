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

# United states MV ndoe that supports connections to three/single phase MV cables
class UsMvNode(ElNode):
	def __init__(self,  name,  flowSim, host):
		ElNode.__init__(self,  name,  flowSim, host)

		self.devtype = "ElectricityMediumVoltageCable"

		self.hasNeutral = True
		self.phases = 3

		# Bookkeeping:
		self.voltage = [complex(0.0, 0.0)] * self.phases
		self.prevVoltage = [complex(0.0, 0.0)] * self.phases
		self.lastUpdate = -1

		#params
		self.nominalVoltage = [0.0, 7200.0, 7200.0, 7200.0] # 12.7kV phase to phase system
		self.angles = [0.0, 0.0, -120, 120]

		#limits
		self.maxVoltage = 7560.0  # ANSI C84.1 Range A -> Line to Neutral
		self.minVoltage = 7020.0  # ANSI C84.1 Range A -> Line to Neutral
		self.maxVuf = 100.0 		  # Does not apply


	# Override
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

		#now add the currents from all other cables:
		for outCable in self.edges:
			if outCable != cable:
				for conductor in self.conductors():
					try:
						if outCable.connectedPhase == conductor or conductor == 0:
							current[conductor] += outCable.current[conductor]
						else:
							current[conductor] += outCable.current[conductor]
					except:
						# No special cable with only one phase
						current[conductor] += outCable.current[conductor]

		# Calculate neutral current if neutral is available
		if self.hasNeutral:
			current[0] = complex(0.0,0.0)
			for i in range(1, (self.phases+1)):
				current[0] -= -current[i]

		cable.current = list(current)