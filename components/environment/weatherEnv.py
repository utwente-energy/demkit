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


from environment.envEntity import EnvEntity
from util.csvReader import CsvReader

import random

class WeatherEnv(EnvEntity):
	def __init__(self,  name,  host):
		EnvEntity.__init__(self,  name, host)

		self.devtype = "Weather"
		self.timeBase = 3600 # Default of most weather information sources

		# NOTE: ONLY SUPPORTS TEMPERATURE AT THIS MOMENT

		#  Readable values:
		self.temperature = 0.0 # in degrees Celsius
		self.humidity = 0.0 # in %
		self.pressure = 0.0 # in hPa
		
		self.windspeed = 0.0 # in meters per second
		self.windspeedScaleFactor = 0.975
		self.windspeedHubHeight = 0.0
		self.winddirection = 0.0 # degrees
		

		self.weatherFile = None
		self.weatherTimeBase = 3600		# Seconds per interval. Default 1 hour for KNMI weather data

		# Separate readers for each weather column
		self.temperatureReaderReader = None
		self.temperatureColumn = 0

		self.windspeedReader = None
		self.windspeedColumn = 1

		self.timeOffset = -3600
		if host != None:
			self.timeOffset = host.timeOffset -3600 #KNMI data offset is in UTC

	def startup(self):
		#initialize the readers
		self.temperatureReader = CsvReader(self.weatherFile, self.weatherTimeBase, self.temperatureColumn, self.timeOffset)
		self.windspeedReader = CsvReader(self.weatherFile, self.weatherTimeBase, self.windspeedColumn, self.timeOffset)

		# Initialize the values
		self.preTick(self.host.time())

		EnvEntity.startup(self)

	def preTick(self, time, deltatime=0):
		self.lockState.acquire()
		self.temperature = self.temperatureReader.readValue(time)
		self.windspeed = self.windspeedReader.readValue(time)
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
		self.logValue("C-temperature", self.temperature)
		self.logValue("hPa-pressure", self.pressure)
		self.logValue("p-humidity", self.humidity)
		self.logValue("mps-wind.speed", self.windspeed)
		self.logValue("deg-wind.direction", self.winddirection)
		self.lockState.release()

	def getProperties(self):
		# Get the properties of this device
		r = {}
		r = EnvEntity.getProperties(self)

		return r

	def doTemperaturePrediction(self, startTime, endTime = None, timeBase = 60, perfect = False):
		if endTime is None:
			temperature = self.temperatureReader.readValue(startTime)
			if perfect is False and self.host.time() > startTime:
				temperature = 0.5*temperature + 0.5*self.temperatureReader.readValue(startTime - 3600*24)
			return temperature

		else:
			result = []
			time = startTime
			while time < endTime:
				# Recursive call to itself
				result.append(self.doTemperaturePrediction(time, None, timeBase, perfect))
				time += timeBase

			return result

	def doWindPrediction(self, startTime, endTime = None, timeBase = 60, perfect = False):
		if endTime is None:
			wind = self.windspeedReader.readValue(startTime)
			if perfect is False and self.host.time() > startTime:
				wind = 0.5*wind + 0.5*self.windspeedReader.readValue(startTime)
			return wind

		else:
			result = []
			time = startTime
			while time < endTime:
				# Recursive call to itself
				result.append(self.doWindPrediction(time, None, timeBase, perfect))
				time += timeBase

			return result