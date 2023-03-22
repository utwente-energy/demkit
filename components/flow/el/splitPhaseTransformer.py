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
from flow.el.mvCable import MvCable
from flow.el.mvNode import MvNode

import math

# Dyn5 MV-LV Distribution Transformer
# Convention: attributes without suffix are from the LV/secondary side, attributes with suffix 'primary' are from the MV side.
# Only logs values and checks violations from secondary side (LV).

class SplitPhaseTransformer(ElNode):
	def __init__(self,  name,  flowSim, host):
		ElNode.__init__(self,  name,  flowSim, host)
		
		self.devtype = "ElectricitySplitPhaseTransformer"

		# Bookkeeping
		self.load = 0.0  # VA

		self.hasNeutral = True
		self.phases = 2	# secondary side

		# Bookkeeping:
		self.voltage = [complex(0.0, 0.0)] * self.phases
		self.prevVoltage = [complex(0.0, 0.0)] * self.phases
		self.lastUpdate = -1

		# Parameters
		self.nominalVoltage = [0.0, 120.0, 120.0]
		self.angles = [0.0, 0.0, -180.0]
		
		self.nominalVoltagePrimary = [0.0, 7200.0]  # =10.5kV line-to-line
		self.anglesPrimary = [0.0, 0.0]

		self.turnRatio = max(self.nominalVoltagePrimary) / max(self.nominalVoltage)

		# Taps
		self.taps = [2, 1, 0, -1, -2]  # positive implies higher LV voltage
		self.tapStep = 250.0 / 10500.0
		self.tap = 0

		# Limits
		self.maxVoltage = 126.0  # ANSI C84.1 Range A
		self.minVoltage = 114.0  # ANSI C84.1 Range A
		self.maxVuf = 100.0  # Does not apply

		self.maxVoltagePrimary = 7560.0  # ANSI C84.1 Range A -> Line to Neutral
		self.minVoltagePrimary = 7020.0  # ANSI C84.1 Range A -> Line to Neutral
		self.maxVufPrimary = 100.0  # Does not apply
	
		# Reference: "Netten voor distributie van electriciteit" by Phase to Phase, 2012, section 8.3 onwards
		# https://phasetophase.nl/boek/index.html
        # Proper values can be obtained through the Types.xlsx file provided with the Gaia Demo download

		# These are some example values
		self.ratedLoad = 50000.0  # VA
		self.noLoadLosses = 350.0  # W
		self.ratedLoadLosses = 2200.0  # W

	@property
	def tap(self):
		return self.__tap

	@tap.setter
	def tap(self, val):
		# Update turn ratio
		defaultTurnRatio = max(self.nominalVoltagePrimary) / max(self.nominalVoltage)
		self.turnRatio = (1. - self.taps[val] * self.tapStep) * defaultTurnRatio

		self.__tap = val

	def conductors(self):
		# Convention used here is that the first index is always the neutral conductor, even for nodes without a neutral conductor.
		return range(0,3)

	def conductorsPrimary(self):
		return range(0,2)
		
	def doForwardSweep(self, previousNode, cable):
		#assert(isinstance(cable, MvCable))
		#assert(isinstance(previousNode, MvNode))

		# Save the previous voltage
		self.prevVoltage = list(self.voltage)

		# Calculate the voltage on the primary side
		voltagePrimary = [complex(0.0, 0.0)] * 2
		for conductor in self.conductorsPrimary():
			voltagePrimary[conductor] = previousNode.voltage[conductor] - cable.voltageDrop(conductor)

		# Transform voltages to the secondary side
		assert(len(self.voltage) == 3 and len(self.nominalVoltagePrimary) == 2)
		self.voltage[0] = complex(0.0, 0.0) # Grounded
		self.voltage[1] = (voltagePrimary[1]-voltagePrimary[0]) / self.turnRatio
		self.voltage[2] = (voltagePrimary[0]-voltagePrimary[1]) / self.turnRatio

		# Now use the impedance to calculate the losses which cause an additional voltage drop on the secondary side
		# OLD CODE FROM C++, Still doubting the structure of US grids..
		# voltage[1] = ((z1 + (1/pow(turnsRatio,2)*z0)) * getCurrent(1)) +
		# 				((-1/pow(turnsRatio,2)*z0) * getCurrent(2));
	
	def doBackwardSweep(self, cable):
		current = [complex(0.0, 0.0)] * 3
		currentPrimary = [complex(0.0, 0.0)] * 2
		
		#assert(isinstance(cable, MvCable))

		# Add the losses of the transformer
		losses = self.getLosses()
		for i in range(1, len(self.voltage)):
			current[i] += ( (losses/2) / self.getLNVoltage(i)).conjugate()
		
		# Sum the currents from all LV cables:
		for outCable in self.edges:
			if outCable != cable:
				for conductor in self.conductors():
					current[conductor] += outCable.current[conductor]

		# Transform the current to the primary side
		current[0] = (-current[1] + -current[2])
		currentPrimary[1] = (current[1] - current[2]) / self.turnRatio
		currentPrimary[0] = -currentPrimary[1]

		
		# Set the result on the MV cable
		cable.current = list(currentPrimary)
		
		# Store load
		self.load = 0.0
		for i in range(1, len(self.voltage)):
			self.load += abs(self.getLNVoltage(i)*current[i].conjugate())
		
	def getLosses(self):
		# Simple losses model according to IEEE Std C57.91
		# Note: does not compensate for different tap positions
		K = self.load/self.ratedLoad

		result = self.noLoadLosses
		result += K*K * self.ratedLoadLosses
		
		return result

	def logStats(self, time):
		self.logValue("W-power.", self.load)
		self.logValue("W-losses", self.getLosses())

		ElNode.logStats(self, time)
