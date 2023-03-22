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


from dev.thermal.thermalBufConvDev import ThermalBufConvDev

#Bufferconverter device
#Note that the buffer level is based on the secondary side, i.e. heat

class CombinedHeatPowerDev(ThermalBufConvDev):
	def __init__(self,  name,  host):
		ThermalBufConvDev.__init__(self,  name,  host)
		self.devtype = "BufferConverter"

		self.commodities = ['ELECTRICITY', 'NATGAS', 'HEAT'] # INPUT, OUTPUT
		self.producingPowers = [0, 13500] # Output power of the source, in HEAT

		# Commodity wise cop, converted from HEAT:
		self.cop = {'ELECTRICITY': (-13.5/6.0), 'NATGAS': (13.5/21.0)}
		# Values from https://gasengineering.nl/pdf/EC_POWER%20specs%20tijdelijk%20NL.pdf

		# How to read these values? Each 1 "quantity" of natural gas consumed produces 13.5/21.0 heat. Each 1 "quantity" of electricity consumed, produces -13.5/6.0 units of heat.
		# Note that electricity is produced, hence the negative sign, so each 1 produced electricity also produces 13.5/6.0 heat (obviously by consuming natural gas).

		self.heatProduction = 0.0 # This variable holds the heat production internally of the device

		self.capacity = 0.0
		self.soc = 0.0
		self.initialSoC = 0.0

		self.lowMark = 0
		self.highMark = 0

		self.producingTemperatures = [0.0, 60.0]	# Output power of the source

	def startup(self):
		ThermalBufConvDev.startup(self)

		assert(len(self.commodities) == 3)