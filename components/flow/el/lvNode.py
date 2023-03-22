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

class LvNode(ElNode):
	def __init__(self,  name,  flowSim, host):
		ElNode.__init__(self,  name,  flowSim, host)

		self.devtype = "ElectricityLowVoltageNode"

		self.hasNeutral = True
		self.phases = 3

		# Bookkeeping:
		self.voltage = [complex(0.0, 0.0)] * (self.phases+1)
		self.prevVoltage = [complex(0.0, 0.0)] * (self.phases+1)
		self.lastUpdate = -1

		#params
		self.nominalVoltage = [0.0, 230.0, 230.0, 230.0]
		self.angles = [0.0, -150.0, 90.0, -30.0]
		self.consumption = [0.0] * (self.phases+1)

		#limits
		self.maxVoltage = 230.0*1.1
		self.minVoltage = 230.0*0.9
		self.maxVuf = 2
