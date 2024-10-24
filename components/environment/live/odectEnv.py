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


from environment.co2Env import Co2Env

import requests
import threading

from util.influxdbReader import InfluxDBReader

class OdectEnv(Co2Env):
	def __init__(self,  name,  host):
		WeatherEnv.__init__(self,  name, host)

		self.timeBase = 60

		# ODECT API credentials
		self.username = ""
		self.password = ""

		# ODECT URL
		self.odecturl = ""

		self.co2emissionsReal = 	0.0 # gCO2eq/kWh - Real value (2 hours behind)
		self.co2emissionsEstimate = 0.0 # gCO2eq/kWh - Estimate (current moment)
		# Note: This class will use the estimate to set the current variable

		self.lastUpdate = -1
		self.updateInterval = 900 # No need to update faster

		self.lastPrediction = -1
		self.predictionCache = None
		self.retrieving = False

		self.supportsForecast = True

		self.reader = None

		# Mapping of variables to names in InfluxDB. Should become the standard for new classes to access data from InfluxDB easily
		self.varMapping = {
			"gCO2eq_per_kWh-emissions.c.ELECTRICITY": "co2emissions"
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
			self.runInThread('retrieveData') 


#### HELPER FUNCTIONS
	def retrieveData(self):
		# We should not be a bad citizen to the service

		if (self.host.time() - self.lastUpdate)  > self.updateInterval:
			try:
				r = requests.get(self.odecturl+"/forecast", auth=(self.username, self.password))
				if r.status_code != 200:
					self.logWarning("Could not connect to ODECT. Errorcode: "+str(r.status_code)+ "\t\t" + r.text)
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
		# NOTE: Here we retrieve data, need to do it a bit different, OWM has two api: now and forecast
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
		# Here we process it (we should also store it!)
		if timeBase is None:
			timeBase = self.timeBase

		result = []
		# Note here the data was retrieved
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

