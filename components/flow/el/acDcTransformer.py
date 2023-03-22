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
from flow.el.lvCable import LvCable
from flow.el.lvNode import LvNode

import math

# TODO implement checkViolations(). See T199

# Dyn5 MV-LV Distribution Transformer
# Convention: attributes without suffix are from the LV/secondary side, attributes with suffix 'primary' are from the MV side.
# Only logs values and checks violations from secondary side (LV).

class AcDcTransformer(ElNode):
	def __init__(self,  name,  flowSim, host):
		ElNode.__init__(self,  name,  flowSim, host)
		self.devtype = "ElectricityAcDcTransformer"

		self.phases = 1

		# Bookkeeping:
		self.voltage = [complex(0.0, 0.0)] * (self.phases+1)
		self.prevVoltage = [complex(0.0, 0.0)] * (self.phases+1)
		self.lastUpdate = -1

		# params
		self.consumption = [complex(0.0, 0.0)] * (self.phases+1)

		# Bookkeeping
		self.load = 0.0  # VA
		
		# Parameters
		self.nominalVoltage = [0.0, 380] # 760V is an option too, used in GridShield
		self.angles = [0.0, 0.0]
		
		self.nominalVoltagePrimary = [0.0, 230.0, 230.0, 230.0]  # =10.5kV line-to-line
		self.voltagePrimary = list(self.nominalVoltagePrimary)
		self.anglesPrimary = [0.0, -150.0, 90.0, -30.0]

		# self.turnRatio = max(self.nominalVoltagePrimary) / max(self.nominalVoltage)
		#
		# # Taps
		# self.taps = [0]  # positive implies higher LV voltage
		# self.tapStep = 0
		# self.tap = 0
		
		# Limits
		self.maxVoltage = 1.1*self.nominalVoltage[-1]
		self.minVoltage = 0.9*self.nominalVoltage[-1]
		self.maxVuf = 100 # %, N/A
		
		self.maxVoltagePrimary = 253.0
		self.minVoltagePrimary = 207.0
		self.maxVufPrimary = 2.0 # %

		# Specific inverter tricks
		self.balancingCable = None

		self.balancingPowers = [0, 0, 0, 0]
		self.balancingDivisor = 1 # Divide the currents if needed, such as in Gridshield.


		# Reference: "Netten voor distributie van electriciteit" by Phase to Phase, 2012, section 8.3 onwards
		# https://phasetophase.nl/boek/index.html
        # Proper values can be obtained through the Types.xlsx file provided with the Gaia Demo download

		# These are some example values
		self.ratedLoad = 640000.0  # VA
		self.noLoadLosses = 350.0  # W
		self.ratedLoadLosses = 2200.0  # W

		# In GridShield: FerroAMP EnergieHubXL: efficiency max ~98%

	def conductors(self):
		# Convention used here is that the first index is always the neutral conductor, even for nodes without a neutral conductor.
		return range(0, len(self.voltage))

	def conductorsPrimary(self):
		return range(1, len(self.voltagePrimary))
		
	def doForwardSweep(self, previousNode, cable):
		assert(isinstance(cable, LvCable))
		assert(isinstance(previousNode, LvNode))

		# Save the previous voltage
		self.prevVoltage = list(self.voltage)

		# Calculate the voltage on the primary side
		for conductor in self.conductorsPrimary():
			self.voltagePrimary[conductor] = previousNode.voltage[conductor] - cable.voltageDrop(conductor)

			# set the flow direction in the cable
			try:
				if abs(self.voltagePrimary[conductor]) - abs(previousNode.voltage[conductor]) < 0:
					cable.flowDirection[conductor] = 1
				else:
					cable.flowDirection[conductor] = -1
			except:
				pass

		# Transform voltages
		assert(len(self.voltage) == 2 and len(self.nominalVoltagePrimary) == 4)
		self.voltage[0] = complex(self.nominalVoltage[0], 0.0) # Voltage is static on DC side
		self.voltage[1] = complex(self.nominalVoltage[1], 0.0) # Voltage is static on DC side
	
	def doBackwardSweep(self, cable):
		current = [complex(0.0, 0.0)] * 2
		currentPrimary = [complex(0.0, 0.0)] * 4

		#assert(isinstance(cable, LvCable))
		
		# Devices connected directly to the transformer

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

		current[1] += self.consumption[1].real / self.voltage[1].real
		
		# Add the losses of the transformer
		losses = self.getLosses().real
		for i in range(1, len(self.voltage)):
			current[i] += losses / self.voltage[1].real

		# Sum the currents from all DC cables:
		for outCable in self.edges:
			if outCable != cable:
				for conductor in self.conductors():
					current[conductor] += outCable.current[conductor]

		current[0] = -current[1]


		# Now apply the currents to the primary side. This depends on whether we can balance the currents or not.
		if self.balancingCable is None:
			currentPrimary[1] = ((current[1]*self.nominalVoltage[1]) / 3) / ( (self.voltagePrimary[1]-self.voltagePrimary[0]).conjugate() )
			currentPrimary[2] = ((current[1]*self.nominalVoltage[1]) / 3) / ( (self.voltagePrimary[2]-self.voltagePrimary[0]).conjugate() )
			currentPrimary[3] = ((current[1]*self.nominalVoltage[1]) / 3) / ( (self.voltagePrimary[3]-self.voltagePrimary[0]).conjugate() )

		# Try to balance the LV side phases
		elif self.balancingCable is not None:
			# In the first iteration, reset all values:
			if self.flowSim.currentIteration == 0:
				self.balancingPowers = [0, 0, 0, 0]

			# Only measure the unbalance in the first iteration
			# FIXME: This is a trick to make it work for now, but not perfect. continuously changing the balancing currents will result in a load flow that fails to converge!
			if self.flowSim.currentIteration == 1:
				balancingCurrent = [0.0, 0.0, 0.0, 0.0]
				for conductor in range(1, self.balancingCable.phases + 1):
					balancingCurrent[conductor] += self.balancingCable.flowDirection[conductor] * abs(self.balancingCable.current[conductor])

				self.balancingPowers[1] = ((balancingCurrent[1] / self.balancingDivisor ) * abs((self.voltagePrimary[1] - self.voltagePrimary[0]).conjugate())).real
				self.balancingPowers[2] = ((balancingCurrent[2] / self.balancingDivisor ) * abs((self.voltagePrimary[2] - self.voltagePrimary[0]).conjugate())).real
				self.balancingPowers[3] = ((balancingCurrent[3] / self.balancingDivisor ) * abs((self.voltagePrimary[3] - self.voltagePrimary[0]).conjugate())).real

			# Try to apply the balan
			fillLevel = self.balancingPowers[1] + self.balancingPowers[2] + self.balancingPowers[3] + (current[1] * self.nominalVoltage[1])


			currentPrimary[1] = ((fillLevel / 3) - self.balancingPowers[1]) / ((self.voltagePrimary[1] - self.voltagePrimary[0]).conjugate())
			currentPrimary[2] = ((fillLevel / 3) - self.balancingPowers[2]) / ((self.voltagePrimary[2] - self.voltagePrimary[0]).conjugate())
			currentPrimary[3] = ((fillLevel / 3) - self.balancingPowers[3]) / ((self.voltagePrimary[3] - self.voltagePrimary[0]).conjugate())


		else:
			self.logError("Invalid configuration")

		currentPrimary[0] = -currentPrimary[1] - currentPrimary[2] - currentPrimary[3]

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

		# FIXME: Need to add more detail here perhaps to incorporate the inverter efficiency at different loadings. Usually, a higher load would mean improved efficiency...
		
		return result

	def logStats(self, time):
		self.logValue("W-power.", self.load)
		self.logValue("W-losses", self.getLosses())

		ElNode.logStats(self, time)
