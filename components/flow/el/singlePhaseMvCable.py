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

from flow.el.elCable import ElCable

class SinglePhaseMvCable(ElCable):
	def __init__(self,  name,  flowSim, nodeFrom, nodeTo, host, connectedPhase=0):
		ElCable.__init__(self,  name, flowSim, nodeFrom, nodeTo, host)

		self.devtype = "ElectricitySinglePhaseMediumVoltageCable"
		self.hasNeutral = True
		self.phases = 1

		# Specific to US grids, we need to indicate which phase is connected on the three phase system
		self.connectecPhase = connectedPhase

		# bookkeeping
		self.current = [complex(0.0, 0.0)] * (self.phases+1)
		self.flowDirection = [1] * (self.phases+1)

		self.length = None  # in meters
		self.ampacity = None  # amperes
		self.fuse = 0  # additional limit

		self.enabled = True  # Option to disable the cable.
		self.burned = False
		self.powered = [True] * (self.phases+1)  # Option to indicate the cable is powered, in case of a fault towards the transformer

		# The following values are and example
		self.impedance = [complex(0.049113, 0.71673), complex(0.1754399, 0.80535)]
