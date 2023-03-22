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
#Note that the buffer level is based on the secondary side!

class HeatPumpDev(ThermalBufConvDev):
	def __init__(self,  name,  host):
		ThermalBufConvDev.__init__(self,  name,  host)
		self.devtype = "BufferConverter"

		self.commodities = ['ELECTRICITY', 'HEAT'] # INPUT, OUTPUT
		self.producingPowers = [-4500, 4500] # Output power of the source, in HEAT

		# Commodity wise cop, converted from HEAT:
		self.cop = {'ELECTRICITY': 4.0} # Pretty common CoP, each unit of electricity consumed produces 4 units of heat

		self.heatProduction = 0.0 # This variable holds the heat production internally of the device

		self.capacity = 	0.0
		self.soc = 			0.0
		self.initialSoC = 	0.0

		self.lowMark = 0
		self.highMark = 0

		self.producingTemperatures = [0.0, 35.0]	# Output temperature of the source

	def startup(self):
		ThermalBufConvDev.startup(self)

		assert(len(self.commodities) == 2)