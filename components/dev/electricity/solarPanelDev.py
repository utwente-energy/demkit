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

class SolarPanelDev(CurtDev):
	def __init__(self,  name,  host, sun):
		CurtDev.__init__(self,  name,  host)

		self.devtype = "Curtailable"
		self.sun = sun

		# params
		self.size = 1.6*12					# Solar panel array in m2
		self.efficiency = 20				# Conversion efficiency in %

		# orientation
		self.inclination = 35 				# Elevation in degrees from horiontal plane on earth surface
		self.azimuth = 180					# Orientation in degrees, 0 = north, 90 = east, 180 = south

		# new style parameters based on the Wp specification of a panel, its size and number of panels
		self.wattPeak = None				# WP given in Watt per panel at 1000W/m2 irradiation
		self.panels = None					# Number of panels
		self.panelSize = 1.65				# Panel size in m2
		self.inverterEfficiency = 0.811 	# Panel efficiency != system efficiency after DC/AC conversion
											# Source: https://www.mdpi.com/201184

		# Apply local control, e.g. droop control based on voltage
		self.enableLocalControl = False

	def startup(self):
		CurtDev.startup(self)

		# Initialize default values, we intend to support both the classic (efficiency based) method and wattpeak method
		# Note that the behaviour is due to change for DEMKit v4.x
		if self.wattPeak is not None:
			self.efficiency = ( (self.wattPeak / self.panelSize) / 1000.0) * self.inverterEfficiency * 100

		if self.panels is not None:
			self.size = self.panels * self.panelSize

	def preTick(self, time, deltatime=0):
		self.lockState.acquire()
		if self.wattPeak is not None:
			self.efficiency = ( (self.wattPeak / self.panelSize) / 1000.0) * self.inverterEfficiency * 100

		if self.panels is not None:
			self.size = self.panels * self.panelSize

		for c in self.commodities:
			self.consumption[c] = self.calculateProduction()

		self.originalConsumption = dict(self.consumption)
		self.lockState.release()

	def timeTick(self, time, deltatime=0):
		CurtDev.timeTick(self, time)

		if self.enableLocalControl:
			self.localControl(time)

#### INTERFACING
	def getProperties(self):
		r = CurtDev.getProperties(self) 	# Get the properties of the overall Device class, which already includes global properties

		self.lockState.acquire()
		# Populate the result dict
		r['size'] = self.size
		r['efficiency'] = self.efficiency
		r['inclination'] = self.inclination
		r['azimuth'] = self.azimuth
		r['onOffDevice'] = self.onOffDevice
		r['originalConsumption'] = self.originalConsumption
		if self.wattPeak is not None:
			r['wattPeak'] = self.wattPeak
		if self.panels is not None:
			r['panels']= self.panels
		self.lockState.release()

		return r

# HELPERS
	def calculateProduction(self, time = None):
		# Do something with the irradiation here
		if time is None:
			production = self.sun.powerOnPlane(self.inclination, self.azimuth)
		else:
			production = self.sun.powerOnPlane(self.inclination, self.azimuth, time)

		return -1 * production * (self.efficiency/100.0) * self.size

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

### Local control (e..g Droop control)
	def localControl(self, time):
		# This will obtain the voltage
		# Note that it wil automatically give the value for the connected phase
		voltage = abs(self.getVoltage())
		# self.logMsg(str(abs(voltage)))

		# Obtaining the current maximum power (mppt)
		power = self.calculateProduction()

		# Just a very simple example, if we exceed the 250V, then we simply turn off the panel
		if voltage.real > 250:
			power = 0
			self.consumption['ELECTRICITY'] = complex(power, 0.0)	# Equally divide the power output