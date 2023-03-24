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


from environment.weatherEnv import WeatherEnv

import requests
import threading

from util.influxdbReader import InfluxDBReader

class OpenWeatherEnv(WeatherEnv):
	def __init__(self,  name,  host):
		WeatherEnv.__init__(self,  name, host)

		self.timeBase = 60

		# Openweathermap API key needs to be provided
		self.apiKey = ""

		# by default take the system location
		self.latitude = host.latitude
		self.longitude = host.longitude

		self.lastUpdate = -1
		self.updateInterval = 900 # They won't update any faster

		self.lastPrediction = -1
		self.predictionCache = None
		self.retrieving = False

		self.supportsForecast = True
		# Sample url= http://api.openweathermap.org/data/2.5/weather?lat=52.2215372&lon=6.8936619&units=metric&APPID=S0m3R4nd0mT0k3n

		self.reader = None

		# Mapping of variables to names in InfluxDB. Should become the standard for new classes to access data from InfluxDB easily
		self.varMapping = {
			"temperature": "C-temperature",
			"humidity": "p-humidity",
			"pressure": "hPa-pressure",
			"windspeed": "mps-wind.speed",
			"winddirection": "deg-wind.direction"
		}

	def startup(self):
		self.initializeReaders()

		# Initialize the values
		self.retrieveData()
		self.preTick(self.host.time())


		if self.host != None:
			self.host.addEnv(self)

	def preTick(self, time, deltatime=0):
		if (self.host.time() - self.lastUpdate) > self.updateInterval and not self.retrieving:
			self.retrieving = True
			self.runInThread('retrieveData') #self.retrieveData()


#### HELPER FUNCTIONS
	def retrieveData(self):
		# We should not be a bad citizen to the service

		if (self.host.time() - self.lastUpdate)  > self.updateInterval:
			try:
				url = "http://api.openweathermap.org/data/2.5/weather?lat="+str(self.latitude)+"&lon="+str(self.longitude)+"&units=metric&APPID="+self.apiKey
				r = requests.get(url)
				if r.status_code != 200:
					self.logWarning("Could not connect to OpenWeatherMap. Errorcode: "+str(r.status_code)+ "\t\t" + r.text)
					self.retrieving = False
					return

				data = r.json()

				self.lockState.acquire()
				self.temperature = data['main']['temp']
				self.humidity = data['main']['humidity']
				self.pressure = data['main']['pressure']
				self.windspeed = data['wind']['speed']
				if 'deg' in data['wind']:
					self.winddirection = data['wind']['deg']

				# If all succeeded:
				self.lastUpdate = self.host.time()
				self.retrieving = False
				self.lockState.release()
			except:
				self.logWarning("OpenWeatherMap service error")

		self.retrieving = False


	# FIXME make async
	def retrieveForecast(self):
		dataCache = None
		if self.lastPrediction < self.host.time():
			try:
				url = "http://api.openweathermap.org/data/2.5/forecast?lat="+str(self.latitude)+"&lon="+str(self.longitude)+"&units=metric&APPID="+self.apiKey
				r = requests.get(url)
				if r.status_code != 200:
					self.logWarning("Could not connect to OpenWeatherMap. Errorcode: "+str(r.status_code)+ "\t\t" + r.text)
					return

				dataCache = r.json()
			except:
				self.logWarning("OpenWeatherMap service error")
				return dict(self.predictionCache)

		if dataCache is not None:
			self.lockState.acquire()
			self.predictionCache = dataCache
			self.lastUpdate = self.host.time()
			self.lockState.release()
			
		return dict(self.predictionCache)

	def doPrediction(self, startTime, endTime, timeBase=None):
		if timeBase is None:
			timeBase = self.timeBase

		result = []
		data = self.retrieveForecast()

		time = startTime
		try:
			while time < endTime:
				# Retrieve the correct value:
				for element in data['list']:
					if element['dt'] <= time and element['dt']+10800 > time: # 10800 seconds = 3 hours, the interval length of openweathermap
						d = {}
						d['temperature'] = element['main']['temp']
						d['humidity'] = element['main']['humidity']
						d['pressure'] = element['main']['pressure']
						d['windspeed'] = element['wind']['speed']
						if 'deg' in element['wind']:
							d['winddirection'] = element['wind']['deg']
						else:
							d['winddirection'] = 0
						d['time'] = element['dt']

						result.append(dict(d))
						break

				time += timeBase
		except:
			result = []
			
		return result

	def doTemperaturePrediction(self, startTime, endTime = None, timeBase = 60, perfect = False):
		# FIXME IMPLEMENT

		if endTime is None:
			temperature = self.temperatureReader.readValue(startTime)
			if perfect is False:
				temperature = temperature -0.5 + random.random() # Just some randomization. Would be nice to retrieve a prediction dataset in the future, T194
			return temperature

		else:
			result = []
			time = startTime
			while time < endTime:
				# Recursive call to itself
				result.append(self.doTemperaturePrediction(time, None, timeBase, perfect))
				time += timeBase

			return result

	def initializeReaders(self):
		self.reader = InfluxDBReader(self.host.db.prefix + self.type, database=self.host.db.database, timeBase=self.timeBase, tags={"name": self.name}, value=self.varMapping["temperature"])

	def readValue(self, time, filename=None, timeBase=None, field=None):
		if field != None:
			filename = field

		r = self.reader.readValue(time, filename, timeBase)
		return r

	def readValues(self, startTime, endTime, filename="temperature", timeBase=None, field=None):
		if field != None:
			filename = field

		result = self.reader.readValues(startTime, endTime, self.varMapping[filename], timeBase)
		return result