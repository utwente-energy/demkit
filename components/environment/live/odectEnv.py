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
import copy
import datetime
import dateutil.parser

from util.influxdbReader import InfluxDBReader

# NOTE: This class is also suitable as a electricity price class
class OdectEnv(Co2Env):
	def __init__(self,  name,  host):
		Co2Env.__init__(self,  name, host)

		self.timeBase = 60

		# ODECT API credentials
		self.username = ""
		self.password = ""

		# ODECT URL
		self.odecturl = ""

		self.co2Real =    0.0 	# gCO2eq/kWh - Real value (2 hours behind)
		self.co2RealTime = -1	# Timestamp of this datapoint

		self.co2Estimate = 0.0 	# gCO2eq/kWh - Estimate (current moment)
		self.co2EstimateTime = -1  # Timestamp of this datapoint

		# Note: This class will use the estimate to set the current variable

		# This class also provides prices
		self.price = 0.08  # €/kWh excluding tax
		self.priceVAT = 0.0  # €/kWh including tax

		self.taxEnergy = 0.1088  # Dutch Energy tax (Energiebelasting in Netherlands)
		self.handlingFee = 0.02  # Handling fee of dynamic contracts (default ZonnePlan energy supplier)
		self.taxVAT = 1.21  # VAT multiplier (Netherlands)



		self.lastUpdate = -1
		self.updateInterval = 900 # No need to update faster

		self.lastPrediction = -1
		self.predictionCache = None
		self.retrieving = False

		self.supportsForecast = True

		# Mapping of variables to names in InfluxDB. Should become the standard for new classes to access data from InfluxDB easily
		self.varMapping = {
			"gCO2eq_per_kWh-emissions.c.ELECTRICITY": "co2emissions",
		}

	def startup(self):
		# Initialize the values
		self.retrieveData()
		self.preTick(self.host.time())

		if self.host != None:
			self.host.addEnv(self)

	def preTick(self, time, deltatime=0):
		if (self.host.time() - self.lastUpdate) > self.updateInterval and not self.retrieving:
			self.retrieving = True
			self.runInThread('retrieveData')

	def logStats(self, time):
		# Perform some logging
		self.lockState.acquire()
		data = copy.deepcopy(self.predictionCache)
		self.lockState.release()

		self.logValue("gCO2eq_per_kWh-emissions.c.ELECTRICITY", self.co2Real, self.co2RealTime)
		self.logValue("EUR_per_kWh-price.c.ELECTRICITY", self.price, self.co2EstimateTime)
		self.logValue("EUR_per_kWh-price_with_VAT.c.ELECTRICITY", self.priceVAT, self.co2EstimateTime)



#### HELPER FUNCTIONS
	def retrieveData(self):
		# Here we will retrieve the  data from the API
		if (self.host.time() - self.lastUpdate)  > self.updateInterval:
			try:
				# First we obtain the lastmix data
				r = requests.get(self.odecturl + "/lastmix", auth=(self.username, self.password))
				if r.status_code != 200:
					self.logWarning("Could not connect to ODECT. Errorcode: " + str(r.status_code) + "\t\t" + r.text)
					self.retrieving = False
					return

				# Update the current state
				data = r.json()

				self.lockState.acquire()
				self.co2Real = data[0]['values'][0][1]
				self.co2RealTime = int(dateutil.parser.parse(data[0]['values'][0][0]).timestamp())
				self.lockState.release()

			except:
				self.logWarning("ODECT service error")

			try:
				dataCache = None
				# Then we retrieve and handle the forecasts
				r = requests.get(self.odecturl+"/forecast", auth=(self.username, self.password))
				if r.status_code != 200:
					self.logWarning("Could not connect to ODECT. Errorcode: "+str(r.status_code)+ "\t\t" + r.text)
					self.retrieving = False
					return

				dataCache = r.json()['values']

				self.lockState.acquire()
				self.predictionCache = dataCache

				self.price = dataCache[0][1]
				self.priceVAT = (self.price + self.taxEnergy + self.handlingFee) * self.taxVAT
				self.co2Estimate = dataCache[0][2]
				self.co2EstimateTime = int(dateutil.parser.parse(dataCache[0][0]).timestamp())

				self.lastUpdate = self.host.time()
				self.lockState.release()

			except:
				self.logWarning("ODECT service error")

		self.retrieving = False

		# Perform forward logging
		self.logForward()

		return copy.deepcopy(self.predictionCache)


	def doPrediction(self, startTime, endTime, timeBase=None):
		# Here we process it (we should also store it!)
		if timeBase is None:
			timeBase = self.timeBase

		result = []
		# Note here the data was retrieved
		self.lockState.acquire()
		data = copy.deepcopy(self.predictionCache)
		self.lockState.release()

		time = startTime
		try:
			while time < endTime:
				# Retrieve the correct value:
				for element in data:
					dt = int(dateutil.parser.parse(element[0]).timestamp())
					if dt <= time and dt+3600 > time: # 10800 seconds = 3 hours, the interval length of openweathermap
						d = {}
						d['co2'] = element[2]
						d['price'] = element[1]
						d['time'] = time

						result.append(dict(d))
						break

				time += timeBase
		except:
			result = []
			
		return result

	def logForward(self):
		# This could be made more elegant using the doPrediction though....
		self.lockState.acquire()
		data = copy.deepcopy(self.predictionCache)
		self.lockState.release()

		try:
			for element in data:
				dt = int(dateutil.parser.parse(element[0]).timestamp())
				priceVAT = (element[1] + self.taxEnergy + self.handlingFee) * self.taxVAT

				self.logValue("gCO2eq_per_kWh-emissions.forecast.c.ELECTRICITY", element[2], dt)
				self.logValue("EUR_per_kWh-price.c.ELECTRICITY", element[1], dt)
				self.logValue("EUR_per_kWh-price_with_VAT.c.ELECTRICITY", priceVAT, dt)
		except:
			self.logWarning("Error in the forward logging of ODECT forecasts")


	def doCo2Prediction(self, startTime, endTime=None, timeBase=60, perfect=False):
		if endTime is None:
			co2emissions = self.doPrediction(startTime)[0]['co2']
			return co2emissions

		else:
			result = []
			time = startTime
			# This is horribly inefficient though, but I do not wanna break the system
			while time < endTime:
				# Recursive call to itself
				result.append(self.doCo2Prediction(time, None, timeBase, perfect))
				time += timeBase

			return result

	def doPricePrediction(self, startTime, endTime=None, timeBase=60, perfect=False):
		if endTime is None:
			price = self.doPrediction(startTime)[0]['price']
			return price

		else:
			result = []
			time = startTime
			# This is horribly inefficient though, but I do not wanna break the system
			while time < endTime:
				# Recursive call to itself
				result.append(self.doPricePrediction(time, None, timeBase, perfect))
				time += timeBase

			return result

