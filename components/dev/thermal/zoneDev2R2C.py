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


from util.clientCsvReader import ClientCsvReader
from dev.thermal.thermalDev import ThermalDevice
from util.windowPredictor import WindowPredictor

# Model for a temperature zone
class ZoneDev2R2C(ThermalDevice):
	def __init__(self,  name,  weather, sun, host):
		ThermalDevice.__init__(self,  name,  host)
		self.devtype = "Load"

		# Reference to weather and sun
		self.weather = weather
		self.sun = sun

		# State variables:
		self.temperature = 0.0 			# in Celsius. This variable will hold the actual indoor temperature
		self.floorTemperature = 0.0

		# Model parameters:
		self.initialTemperature = 19.0	# In Celcius
		self.heatSupply = {}
		self.heatTemperature = {}

		# Other gains/losses
		self.gainSupply = 0.0 		# W
		self.ventilationSupply = 0.0  # W
		self.ventilationFlow = 0.0 	# W/m3
		self.windowGain = 0.0 # W

		# Detached house (R.P. van Leeuwen)
		self.rFloor = 0.001		# K/W
		self.rEnvelope = 0.0064	# K/W
		self.cFloor = 5100 * 3600	# J/K
		self.cZone = 21100 * 3600	# J/K

		# Heating capacity
		self.maxHeat = 7500 # Zone can take maximum of 20000W worth of heat
		self.minHeat = -7500 # Zone minumum heat (or cooling) in W
		self.valveHeat = 0 # The valve opening

		# Internal gain file handling (OPTIONAL)
		self.gainFile = None
		self.gainTimeBase = 60
		self.gainColumn = -1
		self.gainReader = None

		# Ventilation file handling (OPTIONAL)
		self.ventilationFile = None # Provides the airflow in M3/h!
		self.ventilationTimeBase = 60
		self.ventilationColumn = -1
		self.ventilationReader = None

		# Predictors
		self.predictorVentilation = None
		self.predictorGain = None

		self.perfectPredictions = False

		self.windows = []

		if self.persistence != None:
			self.watchlist += ["temperature", "predictorGain", "predictorVentilation", "gainSupply", "ventilationSupply", "ventilationFlow", "windowGain", "floorTemperature"]
			self.persistence.setWatchlist(self.watchlist)

	# Startup is called to initialize the model
	def startup(self):
		assert(len(self.commodities) == 1) # Only one commodity supported for this device (Preferably HEAT)

		self.lockState.acquire()

		# Initialize the consumption and heat supply variables for the initial state
		self.consumption[self.commodities[0]] = 0.0
		self.heatSupply[self.commodities[0]] = 0.0 # Note: HeatSupply will be set by the heat source and should therefore be considered read only
		self.heatTemperature[self.commodities[0]] = 0.0

		# Initialize the file readers based on the configuration input
		self.gainReader = ClientCsvReader(self.gainFile, self.gainTimeBase, self.gainColumn, self.timeOffset, host=self.host)
		self.ventilationReader = ClientCsvReader(self.ventilationFile, self.ventilationTimeBase, self.ventilationColumn, self.timeOffset, host=self.host)

		# Make sure to initialize the initial state of the model:
		self.temperature = self.initialTemperature
		self.floorTemperature = self.initialTemperature

		if self.gainFile != None:
			self.gainSupply = self.gainReader.readValue(self.host.time())
		if self.ventilationFile != None:
			self.ventilationFlow = self.ventilationReader.readValue(self.host.time())
			self.ventilationSupply = (self.ventilationFlow / 3600.0) * 1.25 * 1005 * (self.weather.temperature - self.temperature)

		# Initialize predictors:
		initialize = False
		if not self.perfectPredictions:
			if self.gainFile != None and self.predictorGain is None:
				initialize = True
				self.predictorGain = WindowPredictor(self.timeBase)
			if self.ventilationFile != None and self.predictorVentilation is None:
				initialize = True
				self.predictorVentilation = WindowPredictor(self.timeBase)

			if initialize:
				self.initializePredictors()

		self.lockState.release()

		ThermalDevice.startup(self)

	# PreTick is called before the actual time simulation.
	# Use this to update the state based on the state selected in the previous interval
	def preTick(self, time, deltatime=0):
		newTemperature = 0.0

		# INFORMATION ON THIS MODEL
		# Model based on Richard P. van Leeuwen PhD thesis Chapter 2, 2R2C model (pp. 28)
		# More information on heat models (simple) https://learn.openenergymonitor.org/sustainable-energy/building-energy-model/dynamicmodel.md

		# Useful variables within this model:
		# self.temperature : This holds the current temperature (determined in the last interval) in the zone

		self.lockState.acquire()

		# This will hold the power (in W) and temperature at which the heat energy is supplied
		heatSupply = self.heatSupply[self.commodities[0]]
		heatTemperature = self.heatTemperature[self.commodities[0]]

		self.windowGain = 0.0
		for w in self.windows:
			self.windowGain += w['surface'] * w['shadingCoeff'] * 0.87 * self.sun.powerOnPlane(w['inclination'], w['azimuth'])
		# NOTE: 0.87 is the Shading Coefficient to SHGC conversion factor as per https://en.wikipedia.org/wiki/Shading_coefficient and ASHREA Fundamentals 2013

		# Determine the new floorheating temperature:
		newFloorTemperature = 	self.floorTemperature + ( \
								( (self.temperature - self.floorTemperature) / (self.rFloor * self.cFloor) ) + \
							  	( heatSupply / self.cFloor) \
								) * self.host.timeBase

		newTemperature = 		self.temperature + ( \
								( (self.weather.temperature - self.temperature) / (self.rEnvelope * self.cZone) ) + \
								( (self.floorTemperature - self.temperature) / (self.rFloor * self.cZone ) ) + \
							  	( ( self.ventilationSupply + self.gainSupply + self.windowGain ) / self.cZone) \
								) * self.host.timeBase

		# Update the temperature at the end of the preTick
		self.temperature = newTemperature
		self.floorTemperature = newFloorTemperature

		self.lockState.release()


	# TimeTick is called after all control actions
	def timeTick(self, time, deltatime=0):
		self.prunePlan() # there is no real plan (now?!) but it is good to throw away old data to avoid high memory usage

		self.lockState.acquire()

		# Supply and consumption should be in balance:
		self.consumption[self.commodities[0]] = self.heatSupply[self.commodities[0]]

		# Update the readout values for the next interval
		if self.gainFile != None:
			self.gainSupply = self.gainReader.readValue(self.host.time())
			if not self.perfectPredictions:
				self.predictorGain.addSample(self.gainSupply, time)

		if self.ventilationFile != None:
			self.ventilationFlow = self.ventilationReader.readValue(self.host.time())

			# Update the predictors
			if not self.perfectPredictions:
				self.predictorVentilation.addSample(self.ventilationFlow, time)

			# Determine the heatloss by the airflow of the ventilation
			# See 3.1 (pp. 48 of Richard van Leeuwen PhD Thesis
			# VentilationFlow given in M3/h! -> Conversion to M3/s
			self.ventilationSupply = (self.ventilationFlow / 3600.0) * 1.25 * 1005 * (self.weather.temperature - self.temperature)

		self.lockState.release()

	def logStats(self, time):
		self.lockState.acquire()
		self.logValue("C-temperature.inside", self.temperature)

		if self.host.extendedLogging:
			self.logValue("C-temperature.floor", self.floorTemperature)
			self.logValue("W-heatgain.internal", self.gainSupply)
			self.logValue("W-heatgain.solar", self.windowGain)
			self.logValue("W-heatgain.airflow", self.ventilationSupply)

		for c in self.commodities:
			self.logValue("W-power.real.c." + c, self.consumption[c].real)
		self.lockState.release()

# HELPER FUNCTIONS
	def addWindow(self, surface, azimuth = 180, inclination = 90, shadingCoeff = 0.81):
		# For those params, I guess these are the ones due to lack of sources
		# http://www.commercialwindows.org/shgc.php
		window = {'azimuth': azimuth, 'inclination' : inclination, 'surface' : surface, 'shadingCoeff': shadingCoeff}

		self.lockState.acquire()
		self.windows.append(dict(window))
		self.lockState.release()

#### INTERFACING TO READ THE STATE BY A CONTROLLER
	# E.G. this is used by a thermostat device to read the current temperature and see if heating is required
	def getProperties(self):
		r = ThermalDevice.getProperties(self) 	# Get the properties of the overall Device class, which already includes global properties
		return r

##### PREDICTIONS
	def initializePredictors(self):
		if not self.perfectPredictions:
			time = self.host.time() - (4*7*24*3600)
			if self.gainFile != None:
				while time < self.host.time():
					self.predictorGain.addSample(self.gainReader.readValue(time), time)
					time += self.timeBase

			time = self.host.time() - (4*7*24*3600)
			if self.ventilationFile != None:
				while time < self.host.time():
					self.predictorVentilation.addSample(self.ventilationReader.readValue(time), time)
					time += self.timeBase

	def doGainPrediction(self, startTime, endTime, timeBase = None):
		if self.gainFile != None:
			if timeBase == None:
				timeBase = self.timeBase

			result = []
			if not self.perfectPredictions:
				intervals = int((endTime - startTime) / timeBase)
				result = list(self.predictorGain.predictValues(startTime, intervals, timeBase))
			else:
				time = startTime
				while time < endTime:
					result.append(self.gainReader.readValue(time))
					time += timeBase

			return result

	def doVentilationPrediction(self, startTime, endTime, timeBase = None):
		if self.ventilationFile != None:
			if timeBase == None:
				timeBase = self.timeBase

			result = []
			if not self.perfectPredictions:
				intervals = int((endTime - startTime) / timeBase)
				result = list(self.predictorVentilation.predictValues(startTime, intervals, timeBase))
			else:
				time = startTime
				while time < endTime:
					result.append(self.ventilationReader.readValue(time))
					time += timeBase

			return result

	# The true prediction module to retrieve energy demand for planning of the heating device
	# Note that the controller needs to provide (predicted) thermostat setpoints and power properties (in heat)
	# The zone will call weather properties by itself, as well as the usage of historical heatgain
	# NOTE PROFILE STEERING IS ONLY USEFUL IF THERE IS A BUFFER ATTACHED TO THE CONVERTER!!!
	def doPrediction(self, startTime, endTime, lowerSetpoints, upperSetpoints, minPower, maxPower, timeBase = None):
		if timeBase == None:
			timeBase = self.timeBase

		demand =  [0.0] * int((endTime -  startTime)/timeBase)

		### FIRST WE NEED TO GATHER ALL DATA FOR THE PREDICTION IN (ALIGNED) VECTORS
		# Perform a weather prediction
		ambientTemperature = self.weather.doTemperaturePrediction(startTime, endTime, timeBase, self.perfectPredictions)

		# Calculate all gains
		gains = [0.0] * int((endTime -  startTime)/timeBase)

		# Heat gains from people and appliances
		if self.gainFile != None:
			gains = self.doGainPrediction(startTime, endTime, timeBase)

		# Heat gains from all the windows
		for w in self.windows:
			t = startTime
			idx = 0
			while t < endTime:
				gains[idx] = gains[idx] + (w['surface'] * w['shadingCoeff'] * 0.87 * self.sun.powerOnPlane(w['inclination'], w['azimuth'], t, self.perfectPredictions))
				t += timeBase
				idx += 1

		# Now obtain the ventilation flow, which is temperature dependent.
		ventilationFlow = [0.0] * int((endTime -  startTime)/timeBase)
		if self.ventilationFile != None:
			ventilationFlow = self.doVentilationPrediction(startTime, endTime, timeBase)

		### NOW WE CAN SIMULATE THE ZONE TO GET THE HEAT DEMAND
		floorTemperature = self.floorTemperature # Fetch current state
		zoneTemperature = self.temperature		 # Fetch current state

		# Simulate the zone
		for i in range(0, len(gains)):
			# Update the gain to include ventilation
			gains[i] = gains[i] + ( (ventilationFlow[i] / 3600.0) * 1.25 * 1005 * (ambientTemperature[i] - zoneTemperature) )

			# Calculate the loss in heat energy
			heatLoss =  ( ( ambientTemperature[i] - zoneTemperature) /  self.rEnvelope )  + gains[i]

			# Calculate how much heat we should add/subtract
			if zoneTemperature < lowerSetpoints[i]:
				heatLoss -=  ( ( floorTemperature - zoneTemperature ) * self.cFloor  ) / timeBase
				demand[i] = min(maxPower, max( 0.0, (( ( lowerSetpoints[i] - zoneTemperature ) * (self.cZone + self.cFloor ) ) / timeBase ) - heatLoss ) )
			elif zoneTemperature > upperSetpoints[i]:
				heatLoss +=  ( ( floorTemperature - zoneTemperature ) * self.cFloor  ) / timeBase
				demand[i] = max(minPower, min( 0.0, (( ( upperSetpoints[i] - zoneTemperature ) * (self.cZone + self.cFloor ) ) / timeBase ) - heatLoss ) )

			# Simulate the zone to determine the next state
			newFloorTemperature = 	floorTemperature + ( \
									( (zoneTemperature - floorTemperature) / (self.rFloor * self.cFloor) ) + \
									( demand[i] / self.cFloor) \
									) * timeBase

			newZoneTemperature = 	zoneTemperature + ( \
									( (ambientTemperature[i] - zoneTemperature) / (self.rEnvelope * self.cZone) ) + \
									( (floorTemperature - zoneTemperature) / (self.rFloor * self.cZone ) ) + \
									( ( gains[i] ) / self.cZone) \
									) * timeBase

			floorTemperature = newFloorTemperature
			zoneTemperature = newZoneTemperature

		return demand