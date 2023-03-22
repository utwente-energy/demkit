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

# Note: USed to model US grids
class SinglePhaseMvNode(ElNode):
	def __init__(self,  name,  flowSim, host, connectedPhase=0):
		ElNode.__init__(self,  name,  flowSim, host)

		self.devtype = "SinglePhaseElectricityMediumVoltageNode"

		self.hasNeutral = True
		self.phases = 1

		# Specific to US grids, we need to indicate which phase is connected on the three phase system
		self.connectecPhase = connectedPhase

		# Bookkeeping:
		self.voltage = [complex(0.0, 0.0)] * self.phases
		self.prevVoltage = [complex(0.0, 0.0)] * self.phases
		self.lastUpdate = -1

		#params
		self.nominalVoltage = [0.0, 7200.0] # 12.47kV phase to phase
		self.angles = [0.0, 0.0]
		if connectedPhase == 1:
			self.angles = [0.0, 0.0]
		elif connectedPhase == 2:
			self.angles = [0.0, 120.0]
		elif connectedPhase == 3:
			self.angles = [0.0, -120.0]

		self.consumption = [0.0] * self.phases

		#limits
		self.maxVoltage = 7560.00	# ANSI C84.1 Range A
		self.minVoltage = 7020.		# ANSI C84.1 Range A
		self.maxVuf = 1000          # Does not apply

	def getUnbalance(self):
		return 0.0
