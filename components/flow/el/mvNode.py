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

class MvNode(ElNode):
	def __init__(self,  name,  flowSim, host):
		ElNode.__init__(self,  name,  flowSim, host)

		self.devtype = "ElectricityMediumVoltageNode"

		self.hasNeutral = False
		self.phases = 3

		# Bookkeeping:
		self.voltage = [complex(0.0, 0.0)] * (self.phases+1)
		self.prevVoltage = [complex(0.0, 0.0)] * (self.phases+1)
		self.lastUpdate = -1

		#params
		self.nominalVoltage = [0.0, 6062.0, 6062.0, 6062.0] # 10.5kV phase to phase
		self.angles = [0.0, 0.0, -120, 120]

		#limits
		self.maxVoltage = 10500.0*1.1
		self.minVoltage = 10500.0*0.9
		self.maxVuf = 2.0 # %