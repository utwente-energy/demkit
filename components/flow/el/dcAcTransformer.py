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
import cmath

# Dyn5 MV-LV Distribution Transformer
# Convention: attributes without suffix are from the LV/secondary side, attributes with suffix 'primary' are from the MV side.
# Only logs values and checks violations from secondary side (LV).

class DcAcTransformer(ElNode):
	def __init__(self,  name,  flowSim, host):
		ElNode.__init__(self,  name,  flowSim, host)

		self.phases = 3

		self.devtype = "ElectricityDcAcTransformer"

		# Bookkeeping
		self.load = 0.0  # VA
		
		# Parameters
		self.nominalVoltage = [0.0, 230.0, 230.0, 230.0]
		self.angles = [0.0, -150.0, 90.0, -30.0]
		
		self.nominalVoltagePrimary = [0.0, 380]  # =10.5kV line-to-line
		self.voltagePrimary = list(self.nominalVoltagePrimary)
		self.anglesPrimary = [0.0, 0.0]

		self.turnRatio = max(self.nominalVoltagePrimary) / max(self.nominalVoltage)

		# Taps
		self.taps = [0]  # positive implies higher LV voltage
		self.tapStep = 0
		self.tap = 0
		
		# Limits
		self.maxVoltage = 253.0
		self.minVoltage = 207.0
		self.maxVuf = 2 # %
		
		self.maxVoltagePrimary = self.nominalVoltagePrimary[-1] * 1.1
		self.minVoltagePrimary = self.nominalVoltagePrimary[-1] * 0.9
		self.maxVufPrimary = 2.0 # %
	
		# Reference: "Netten voor distributie van electriciteit" by Phase to Phase, 2012, section 8.3 onwards
		# https://phasetophase.nl/boek/index.html
        # Proper values can be obtained through the Types.xlsx file provided with the Gaia Demo download

		# These are some example values
		self.ratedLoad = 640000.0  # VA
		self.noLoadLosses = 350.0  # W
		self.ratedLoadLosses = 2200.0  # W

	def conductors(self):
		# Convention used here is that the first index is always the neutral conductor, even for nodes without a neutral conductor.
		return range(0, len(self.voltage))

	def conductorsPrimary(self):
		return range(1, len(self.voltage))
		
	def doForwardSweep(self, previousNode, cable):
		assert(isinstance(cable, MvCable))
		assert(isinstance(previousNode, MvNode))

		# Save the previous voltage
		self.prevVoltage = list(self.voltage)

		# Calculate the voltage on the primary side
		voltagePrimary = [complex(0.0, 0.0)] * 2
		for conductor in self.conductorsPrimary():
			voltagePrimary[conductor] = previousNode.voltage[conductor] - cable.voltageDrop(conductor)

			# set the flow direction in the cable
			try:
				if abs(self.voltagePrimary[conductor]) - abs(previousNode.voltage[conductor]) < 0:
					cable.flowDirection[conductor] = 1
				else:
					cable.flowDirection[conductor] = -1
			except:
				pass

		self.voltagePrimary = list(voltagePrimary)

		# Transform voltages
		# Voltage on secondary side is static
		for conductor in self.conductors():
			self.voltage[conductor] = cmath.rect(self.nominalVoltage[conductor], math.radians(self.angles[conductor]))
	
	def doBackwardSweep(self, cable):
		current = [complex(0.0, 0.0)] * 4
		currentPrimary = [complex(0.0, 0.0)] * 2
		
		assert(isinstance(cable, MvCable))
		
		# Devices connected to the transformer
		# FIXME
		for meter in self.meters:
			for i in range(1, len(self.voltage)):
				current[i] += ( (meter.consumption/3) / self.getLNVoltage(i)).conjugate()
		for meter in self.metersL1:
			current[1] += (meter.consumption / self.getLNVoltage(1)).conjugate()
		for meter in self.metersL2:
			current[2] += (meter.consumption / self.getLNVoltage(2)).conjugate()
		for meter in self.metersL3:
			current[3] += (meter.consumption / self.getLNVoltage(3)).conjugate()
		
		# Add the losses of the transformer
		losses = self.getLosses()
		for i in range(1, len(self.voltage)):
			current[i] += ( (losses/3) / self.getLNVoltage(i)).conjugate()
		
		# Sum the currents from all LV cables:
		for outCable in self.edges:
			if outCable != cable:
				for conductor in self.conductors():
					current[conductor] += outCable.current[conductor]

		current[0] = (-current[1] + -current[2] + -current[3])

		totalPower = current[1] * self.getLNVoltage(1).conjugate()
		totalPower += current[2] * self.getLNVoltage(2).conjugate()
		totalPower += current[3] * self.getLNVoltage(3).conjugate()

		# Transform to the primary side
		currentPrimary[1] = totalPower / (self.voltagePrimary[1]-self.voltagePrimary[0]).conjugate()
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
