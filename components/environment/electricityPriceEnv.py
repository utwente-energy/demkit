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

class ElectricityPriceEnv(EnvEntity):
	def __init__(self,  name,  host):
		EnvEntity.__init__(self,  name, host)

		self.devtype = "Emissions"
		self.timeBase = 3600 # Default of most weather information sources

		#  Readable values:
		self.price = 0.0 			# €/kWh excluding tax
		self.priceVAT = 0.0			# €/kWh including tax


		self.taxEnergy = 0.1088 	# Dutch Energy tax (Energiebelasting in Netherlands)
		self.handlingFee = 0.02		# Handling fee of dynamic contracts (default ZonnePlan energy supplier)
		self.taxVAT = 1.21			# VAT multiplier (Netherlands)
		

		# Separate readers for each weather column
		self.pricereaderReader = None
		self.priceColumn = 0

		# Input files
		self.priceFile = None
		self.priceTimeBase = 3600		# Seconds per interval. Default 1 hour for KNMI weather data

		self.timeOffset = 
		if host != None:
			self.timeOffset = host.timeOffset 

	def startup(self):
		#initialize the readers
		self.priceReader = CsvReader(self.priceFile, self.priceTimeBase, self.priceColumn, self.timeOffset)
		
		# Initialize the values
		self.preTick(self.host.time())

		EnvEntity.startup(self)

	def preTick(self, time, deltatime=0):
		self.lockState.acquire()
		self.price = self.priceReader.readValue(time)
		self.priceVAT = (self.price + self.taxEnergy + self.handlingFee) * self.self.priceVAT

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
		self.logValue("EUR_per_kWh-price.c.ELECTRICITY", self.price)
		self.logValue("EUR_per_kWh-price_with_VAT.c.ELECTRICITY", self.priceVAT)
		self.lockState.release()

	def getProperties(self):
		# Get the properties of this device
		r = {}
		r = EnvEntity.getProperties(self)

		return r

	def dopricePrediction(self, startTime, endTime = None, timeBase = 60, perfect = False):
		if endTime is None:
			prices = self.priceReader.readValue(startTime)
			return prices

		else:
			result = []
			time = startTime
			while time < endTime:
				# Recursive call to itself
				result.append(self.dopricePrediction(time, None, timeBase, perfect))
				time += timeBase

			return result
