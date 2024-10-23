# Copyright 2024 University of Twente

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

# http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from environment.envEntity import EnvEntity
from util.csvReader import CsvReader

import random

class Co2Env(EnvEntity):
	def __init__(self,  name,  host):
		EnvEntity.__init__(self,  name, host)

		self.devtype = "Emissions"
		self.timeBase = 3600 # Default of most weather information sources

		#  Readable values:
		self.co2emissions = 0.0 # gCO2eq/kWh 

		# Separate readers for each weather column
		self.co2readerReader = None
		self.co2Column = 0

		# Input files
		self.co2File = None
		self.co2TimeBase = 3600		# Seconds per interval. Default 1 hour for KNMI weather data

		self.timeOffset = 0
		if host != None:
			self.timeOffset = host.timeOffset 

	def startup(self):
		#initialize the readers
		self.co2Reader = CsvReader(self.co2File, self.co2TimeBase, self.co2Column, self.timeOffset)
		
		# Initialize the values
		self.preTick(self.host.time())

		EnvEntity.startup(self)

	def preTick(self, time, deltatime=0):
		self.lockState.acquire()
		self.co2emissions = self.co2Reader.readValue(time)
		self.lockState.release()
		# Only temperature supported for now. Additional readers make it possible to get other data in if required

	def timeTick(self, time, deltatime=0):
		pass

	def postTick(self, time, deltatime=0):
		pass

	def shutdown(self):
		pass

	def logStats(self, time):
		self.lockState.acquire()
		self.logValue("gCO2eq_per_kWh-emissions.c.ELECTRICITY", self.co2emissions)
		self.lockState.release()

	def getProperties(self):
		# Get the properties of this device
		r = {}
		r = EnvEntity.getProperties(self)

		return r

	def doCo2Prediction(self, startTime, endTime = None, timeBase = 60, perfect = False):
		if endTime is None:
			co2emissions = self.co2Reader.readValue(startTime)
			if perfect is False and self.host.time() > startTime:
				co2emissions = 0.5*co2emissions + 0.5*self.co2Reader.readValue(startTime - 3600*24)
			return co2emissions

		else:
			result = []
			time = startTime
			while time < endTime:
				# Recursive call to itself
				result.append(self.doCo2Prediction(time, None, timeBase, perfect))
				time += timeBase

			return result
