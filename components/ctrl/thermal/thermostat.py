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


from ctrl.thermal.thermalDevCtrl import ThermalDevCtrl
from util.windowPredictor import WindowPredictor

class Thermostat(ThermalDevCtrl):
	def __init__(self, name, zone, ctrl, host):
		assert(ctrl == None) # This device does not support an external controller

		ThermalDevCtrl.__init__(self, name, zone, ctrl, host)
		# Note that the zone is actually the attached device!

		self.timeOffset = 0
		if host != None:
			self.timeOffset = host.timeOffset

		self.devtype = 'Thermostat'

		# Type of control
		self.simpleMode = False # Simple is more "deadband"-like. Set to false and the thermostat will use the zone model to determine the heat needed.

		# Signal
		self.setpointChanged = False # Flag to signal setpoint changes, controller must check this

		# Parameters
		self.temperatureSetpointHeating = 17.0 # Current setpoint temperature for the zone
		self.temperatureSetpointCooling = 25.0 # Current setpoint temperature for the zone

		# Deadband control
		self.temperatureDeadband = [-0.1, 0.0, 0.5, 0.6]	# allowed deviation before turning on/off the demand
		# Explanation: [turn on heating when below, turn off heating when above, turn off cooling when below, turn on cooling when above]
		# All in celsius relative to the setpoint

		self.temperatureMax = 25.0 # Maximum temperature when noone is home
		self.temperatureMin = 17.0 # Minimum temperature when noone is home

		self.preheatingTime = 0 # Seconds to start heating early on

		# Variables for the heating job system:
		self.currentJobIdx = -1
		self.currentJob = {}
		self.available = False
		self.jobs = []

		# Heat demand, must be in [-1, 1], can be a fraction (modulating thermostat)
		self.heatDemand = 0
		
		# Option to have binary valve control
		self.binaryValve = False

		# Setpoint predictors
		self.predictorLower = None
		self.predictorUpper = None

		# persistence
		if self.persistence != None:
			self.watchlist += ["jobs", "currentJobIdx", "currentJob", "available", "predictorLower", "predictorUpper", "heatDemand", "temperatureSetpointHeating", "temperatureSetpointCooling"]
			self.persistence.setWatchlist(self.watchlist)

	def preTick(self, time, deltatime=0):
		self.thermostatCtrl(time)

	def timeTick(self, time, deltatime=0):
		pass
			
	def startup(self):
		self.temperatureSetpointHeating = self.temperatureMin
		self.temperatureSetpointCooling = self.temperatureMax

		# Skip to the current job according to the dataset
		self.jobs.sort()
		i = -1
		for job in self.jobs:
			if job[1]['startTime'] >= self.host.time():
				break
			else:
				i += 1
		self.currentJobIdx = i

		# Initialize predictors
		if not self.perfectPredictions:
			self.predictorLower = WindowPredictor(self.timeBase)
			self.predictorUpper = WindowPredictor(self.timeBase)
			self.initializePredictors()

		ThermalDevCtrl.startup(self)

	def doPlanning(self,  signal,  requireImprovement = True):
		assert(False) # This device does not support an external controller

	def thermostatCtrl(self, time):
		# synchronize zone state:
		self.updateDeviceProperties()
		zoneTemperature = self.devData['temperature']

		# Change the setpoint if required
		if self.currentJobIdx+1 < len(self.jobs):
			j = self.jobs[self.currentJobIdx+1][1]
			if j['startTime']-self.preheatingTime <= self.host.time() and j['setpoint'] > self.temperatureMin: # Setpoint above idletemp, preheat/precool
				self.temperatureSetpointHeating = j['setpoint']
				self.temperatureSetpointCooling = j['setpoint']
				self.setpointChanged = True
				self.currentJobIdx += 1
			elif j['startTime'] <= self.host.time():
				self.temperatureSetpointHeating = self.temperatureMin
				self.temperatureSetpointCooling = self.temperatureMax
				self.setpointChanged = True
				self.currentJobIdx += 1

		if self.simpleMode:
			#Simple control based on the deadband
			if zoneTemperature < self.temperatureSetpointHeating + self.temperatureDeadband[0]:
				self.heatDemand = self.dev.maxHeat
			# Check if there is cooling demand instead
			elif zoneTemperature > self.temperatureSetpointCooling + self.temperatureDeadband[3]:
				self.heatDemand = self.dev.minHeat
			# Check if we reached the deadband zone, turn off heating/cooling
			elif zoneTemperature > self.temperatureSetpointHeating + self.temperatureDeadband[1] and zoneTemperature < self.temperatureSetpointCooling + self.temperatureDeadband[2]:
				self.heatDemand = 0
		else:
			#Fancy mode, using the zone model to calculate heat demand
			if zoneTemperature > self.temperatureSetpointHeating + self.temperatureDeadband[1] and zoneTemperature < self.temperatureSetpointCooling + self.temperatureDeadband[2]:
				self.heatDemand = 0
			else:
				self.heatDemand = self.dev.doPrediction(time, time+self.timeBase, [self.temperatureSetpointHeating], [self.temperatureSetpointCooling], self.dev.minHeat, self.dev.maxHeat, self.timeBase)[0]

		# now set the valve
		if self.binaryValve:
			if self.heatDemand > 0.001:
				self.heatDemand = self.dev.maxHeat
			elif self.heatDemand < -0.001:
				self.heatDemand = self.dev.minxHeat

		self.dev.valveHeat = self.heatDemand

		# Add the current state to the predictor
		if not self.perfectPredictions:
			self.predictorLower.addSample(self.temperatureSetpointHeating, time)
			self.predictorUpper.addSample(self.temperatureSetpointCooling, time)


	def logStats(self, time):
		self.logValue("b-heatdemand", self.heatDemand)
		self.logValue("C-temperature.heating.setpoint", self.temperatureSetpointHeating)
		self.logValue("C-temperature.cooling.setpoint", self.temperatureSetpointCooling)

#### LOCAL HELPERS
	# Note, we use the Job system to define heating intervals
	# In between, when no heating "job" is "running" we can set the idle temperature
	# This system also allows us to dynamically change starttimes, e.g. to perform preheating
	def addJob(self, startTime, setpoint):
		# For now we apply the offset upon loading jobs:
		startTime -= self.timeOffset

		j = {}
		j['startTime'] = int(startTime)
		j['setpoint'] = setpoint

		if len(self.jobs) > 0 and j['startTime'] <= self.jobs[-1][1]['startTime']:
			assert(False) #This may not happen, jobs must be provided in order!

		job = (len(self.jobs),  dict(j))
		self.jobs.append(job)

	def initializePredictors(self):
		time = self.host.time() - ( 4*7*24*60*60)

		# Find the starting index for the jobs for the predictor
		idx = -1
		for job in self.jobs:
			if job[1]['startTime'] >= time:
				break
			else:
				idx += 1

		# Set the initial temperature
		if self.jobs[idx][1]['setpoint'] < self.temperatureMin:
			temperatureSetpointHeating = self.temperatureMin
			temperatureSetpointCooling = self.temperatureMax
		else:
			temperatureSetpointHeating = self.jobs[idx][1]['setpoint']
			temperatureSetpointCooling = self.jobs[idx][1]['setpoint']

		# Fill the predictor
		while time < self.host.time():
			j = self.jobs[idx+1][1]
			if j['startTime']-self.preheatingTime <= time and j['setpoint'] > self.temperatureMin: # Setpoint above idletemp, preheat/precool
				temperatureSetpointHeating = j['setpoint']
				temperatureSetpointCooling = j['setpoint']
				idx += 1
			elif j['startTime'] <= time:
				temperatureSetpointHeating = self.temperatureMin
				temperatureSetpointCooling = self.temperatureMax
				idx += 1

			# Add a prediction sample
			self.predictorLower.addSample(temperatureSetpointHeating, time)
			self.predictorUpper.addSample(temperatureSetpointCooling, time)

			# Advance time
			time += self.timeBase

	def doPrediction(self, startTime, endTime, producingPowers = None, timeBase = None):
		if timeBase is None:
			timeBase = self.timeBase

		if producingPowers is None:
			self.updateDeviceProperties()
			producingPowers = [ self.dev.minHeat,  self.dev.maxHeat ]

		lowerSetpoints = self.doLowerPrediction(startTime,  endTime)
		upperSetpoints = self.doUpperPrediction(startTime,  endTime)

		result = self.zCall(self.dev, 'doPrediction', startTime, endTime, lowerSetpoints, upperSetpoints, producingPowers[0], producingPowers[-1], timeBase)

		return result

	def doUpperPrediction(self,  startTime,  endTime):
		result = []
		if not self.perfectPredictions:
			samples = int( (endTime - startTime) / self.timeBase )
			result =  list(self.predictorUpper.predictValues(startTime, samples, self.timeBase) )
		else:
			# Use perfect predictions of the temperature setpoint
			idx = self.currentJobIdx
			setpoint = self.temperatureSetpointCooling

			time = startTime
			while time < endTime and idx-1 < len(self.jobs):
				j = self.jobs[idx+1][1]
				if j['startTime']-self.preheatingTime <= time and j['setpoint'] > self.temperatureMin: # Setpoint above idletemp, preheat/precool
					setpoint= j['setpoint']
					idx += 1
				elif j['startTime'] <= time:
					setpoint = self.temperatureMax
					idx += 1

				# add the sample
				result.append(setpoint)

				# Advance time
				time += self.timeBase

		return result

	def doLowerPrediction(self,  startTime,  endTime):
		result = []
		if not self.perfectPredictions:
			samples = int( (endTime - startTime) / self.timeBase )
			result = list(self.predictorLower.predictValues(startTime, samples, self.timeBase) )
		else:
			# Use perfect predictions of the temperature setpoint
			idx = self.currentJobIdx
			setpoint = self.temperatureSetpointHeating

			time = startTime
			while time < endTime and idx-1 < len(self.jobs):
				j = self.jobs[idx+1][1]
				if j['startTime']-self.preheatingTime <= time and j['setpoint'] > self.temperatureMin: # Setpoint above idletemp, preheat/precool
					setpoint = j['setpoint']
					idx += 1
				elif j['startTime'] <= time:
					setpoint = self.temperatureMin
					idx += 1

				# add the sample
				result.append(setpoint)

				# Advance time
				time += self.timeBase

		return result
