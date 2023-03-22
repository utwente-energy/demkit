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

class WindTurbineDev(CurtDev):
	def __init__(self,  name,  host, wind):
		CurtDev.__init__(self,  name,  host)

		self.devtype = "Curtailable"
		self.wind = wind #D. #sun = sun

		#params
		self.dataSourceHeight = 0.0
		self.hubHeight = 0.0
		self.cutInSpeed = 0.0
		self.cutOutSpeed = 0.0
		self.roughnessLength = 0.9 #D. environment roughness length in m2 to scale wind speed at different height
		self.powerCurveWindSpeeds = []
		self.powerCurveValues = []

	def preTick(self, time, deltatime=0):
		self.lockState.acquire()
		for c in self.commodities:
			self.consumption[c] = self.calculateProduction()

		self.originalConsumption = dict(self.consumption)
		self.lockState.release()


#### INTERFACING
	def getProperties(self):
		r = CurtDev.getProperties(self) 	# Get the properties of the overall Device class, which already includes global properties

		self.lockState.acquire()
		# Populate the result dict
		r['hubHeight'] = self.hubHeight
		r['cutInSpeed'] = self.cutInSpeed
		r['cutOutSpeed'] = self.cutOutSpeed
		r['roughnessLength'] = self.roughnessLength
		r['powerCurveWindSpeeds'] = self.powerCurveWindSpeeds
		r['powerCurveValues'] = self.powerCurveValues
		# r['airDensity'] = self.airDensity
		r['onOffDevice'] = self.onOffDevice
		r['originalConsumption'] = self.originalConsumption
		self.lockState.release()

		return r

# HELPERS
	def calculateProduction(self, time = None):
		if time is None:
			production = self.wind.windTurbineYield(self.dataSourceHeight, self.hubHeight,self.cutInSpeed,self.cutOutSpeed,self.roughnessLength,self.powerCurveWindSpeeds,self.powerCurveValues)
		else:
			production = self.wind.windTurbineYield(self.dataSourceHeight, self.hubHeight,self.cutInSpeed,self.cutOutSpeed,self.roughnessLength,self.powerCurveWindSpeeds,self.powerCurveValues,time)

		return -1 * production #-1 * production * (self.efficiency/100.0) * self.size

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