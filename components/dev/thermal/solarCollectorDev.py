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


from dev.curtDev import CurtDev

class SolarCollectorDev(CurtDev):
	def __init__(self,  name,  host, sun, weather):
		CurtDev.__init__(self,  name,  host)

		self.devtype = "sc"
		self.sun = sun
		self.weather = weather


		self.a = 0.66
		self.b = 2.3
		self.c = 0.009

		# Other possible parameters:
		# Heat Pipes:
		# 	a = 0.66
		# 	b = 2.3
		# 	c = 0.009
		#
		# Flat Plate Collectors:
		# 	a = 0.734
		# 	b = 4.05
		# 	c = 0.011
		#
		# Source: https://fenix.tecnico.ulisboa.pt/downloadFile/395143147845/Extended%20abstract-Tiago%20Os%C3%B3rio-46762.pdf


		#params
		self.size = 1.6*12		# Solar panel array in m2
		self.efficiency = 20	# Conversion efficiency in %
		self.inclination = 35 	# Elevation in degrees from horiontal plane on earth surface
		self.azimuth = 180		# Orientation in degrees, 0 = north, 90 = east, 180 = south

	def preTick(self, time, deltatime=0):
		for c in self.commodities:
			self.consumption[c] = self.calculateProduction()

		self.originalConsumption = dict(self.consumption)


#### INTERFACING
	def getProperties(self):
		r = CurtDev.getProperties(self) 	# Get the properties of the overall Device class, which already includes global properties

		# Populate the result dict
		r['size'] = self.size
		r['efficiency'] = self.efficiency
		r['inclination'] = self.inclination
		r['azimuth'] = self.azimuth
		r['onOffDevice'] = self.onOffDevice
		r['originalConsumption'] = self.originalConsumption
		r['a'] = self.a
		r['b'] = self.b
		r['c'] = self.c

		return r


# HELPERS
	def calculateProduction(self, time = None):
		# Do something with the irradiation here
		if time is None:
			production = self.sun.powerOnPlane(self.inclination, self.azimuth)
		else:
			production = self.sun.powerOnPlane(self.inclination, self.azimuth, time)

		if production > 0:
			self.efficiency = self.a - self.b*((50-self.weather.temperature)/production)-self.c*(pow(50-self.weather.temperature,2)/production)


		result = -1 * production * (self.efficiency) * self.size
		if result > 0:
			result = 0
		return result

	def readValue(self, time, filename=None, timeBase=None):
		return self.calculateProduction(time)

	def readValues(self, startTime, endTime, filename=None, timeBase=None):
		if timeBase is None:
			timeBase = self.timeBase

		# Function used for predictions
		result = []
		time = startTime
		while time < endTime:
			result.append(self.calculateProduction(time))
			time += timeBase

		return result