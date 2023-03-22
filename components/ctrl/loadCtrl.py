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

import util.helpers
from ctrl.devCtrl import DevCtrl
from util.windowPredictor import WindowPredictor
from util.csvReader import CsvReader

from util.clientCsvReader import ClientCsvReader

import copy
import random

class LoadCtrl(DevCtrl):
	#Make some init function that requires the host to be provided
	def __init__(self,  name,  dev, ctrl,  host):
		DevCtrl.__init__(self,  name,  dev,  ctrl,  host)

		self.devtype = "LoadCtrl"

		self.history = []
		self.lastPredictionUpdate = -1

		# Provide prediction data instead
		self.givenPrediction = None
		self.intradayPrediction = None
		self.givenPredictionReader = None
		self.intradayPredictionReader = None

		self.predictor = None

		# Bookkeeping of predictions for synchronized planning
		self.predictionPlanning = None
		self.predictionPlanningTime = -1

		# Update predictions in case of event-based control
		self.predictionUpdateInterval = [3600, 7200]
		self.updateTime = 12*3600 # Update the prediction 12hrs in advance
		self.updatingPrediction = False

		# Use current measurement to improve short term predictions, useful for event-based control
		self.predictionAdaption = False

		# Deviation logging
		self.predictionDeviation = []
		self.predictionDeviationWindow = 48 #samples
		self.deviation = 0
		self.deviationSamples = 0

		# persistence
		if self.persistence != None:
			self.watchlist += ["devData", "devDataUpdate", "predictor", "lastPredictionUpdate", "history", "predictionPlanning", "predictionDeviation"]
			self.persistence.setWatchlist(self.watchlist)

	def startup(self):
		DevCtrl.startup(self)

		# Initialize predictors the first time
		if self.lastPredictionUpdate == -1:
			self.initializePredictors()

		self.timeOffset = self.host.timeOffset

		self.predictionDeviation = [complex(1, 0)] * self.predictionDeviationWindow

	def timeTick(self, time, deltatime=0):
		self.updateDeviceProperties()
		if (self.predictor != None):
			try:
				self.predictor.addSample(self.devData['consumption'][self.devData['commodities'][0]], time)
			except:
				pass # no data yet

		# Obtain the deviation from the planning, which can be used in the future for more robust predicitons
		planning = 0
		value = 0
		try:
			planning = self.getOriginalPlan(time, self.devData['commodities'][0])
			value = self.devData['consumption'][self.devData['commodities'][0]]
		except:
			pass

		try:
			self.deviation +=  1 + ((value - planning)/planning)
		except:
			self.deviation += 1
		self.deviationSamples += 1

		if time % self.timeBase == 0:
			# we are exactly at an interval
			i = int( (time - (time%self.timeBase) ) / ((self.predictionDeviationWindow * self.timeBase) / self.predictionDeviationWindow) ) % self.predictionDeviationWindow
			if self.deviationSamples > 0:
				self.predictionDeviation[i] = self.deviation / self.deviationSamples
			else:
				self.predictionDeviation[i] = complex(1,0)

			self.deviationSamples = 0
			self.deviation = 0
				
		if self.useEventControl and (self.lastPredictionUpdate+random.randint(self.predictionUpdateInterval[0], self.predictionUpdateInterval[1]) ) <= time and not self.updatingPrediction:
			self.updatingPrediction = True
			self.runInThread('updatePrediction')

	def doPlanning(self,  signal,  requireImprovement = True):
		self.lockPlanning.acquire()

		# Synchronize the device state:
		self.updateDeviceProperties()
		result = {}

		assert(self.timeBase >= self.devData['timeBase']) # The other direction is untested and probably broken!
		assert(self.timeBase % self.devData['timeBase'] == 0) # Again, otherwise things are very likely to break

		time = signal.time
		timeBase = signal.timeBase

		if self.predictionPlanningTime < time:
			p = {}

			#Obtain the profile from a prediction. There is no flex to change this anyways
			for c in self.commodities:
				p[c] = self.doPrediction(time-(time%timeBase),  time-(time%timeBase)+timeBase*len(signal.desired[c]))
				if len(p[c]) != signal.planHorizon:
					p[c] = util.helpers.interpolate(p[c], signal.planHorizon)

			# Confirm bookkeeping
			self.predictionPlanning = copy.deepcopy(p)
			self.predictionPlanningTime = time

		result['improvement'] = 0.0
		result['boundImprovement'] = 0.0
		result['profile'] = dict(self.predictionPlanning)
		self.setPlan(copy.deepcopy(result['profile']), time, timeBase)

		self.lockPlanning.release()

		return result



#### PREDICTION CODE
	def doPrediction(self,  startTime,  endTime, adapt=False):
		self.updateDeviceProperties()
		if self.perfectPredictions:
			return self.usePerfectPrediction(startTime,  endTime)

		elif self.givenPrediction != None:
			result = self.useGivenPrediction(startTime,  endTime)
		else:
			result = self.useHistoricPrediction(startTime,  endTime)

		# New adaption module which work more on a daily energy level instead of short term deviations
		# With robust battery optimization, this makes more sense as this level can be estimated more robust
		if self.predictionAdaption and not self.perfectPredictions and adapt:
			# Automatically check the sign
			sign = None
			for val in result:
				if sign == -1 and val.real > 1:
					sign = 0
					break
				elif sign is None and val.real < -1:
					sign = 0
					break
				elif sign is None:
					if val.real < -1:
						sign = -1
					elif val.real > 1:
						sign = 1

			if sign is None:
				sign = 0

			# Get the average deviation for the number of samples
			avg = 0
			for val in self.predictionDeviation:
				avg += val

			avg = avg / len(self.predictionDeviation)
			avg = max(0.5, min(avg.real, 1.5)) # For now we add bounds to make sure errors don't have too severe impacts

			# Now really adapt the prediction to divide the energy
			for i in range(0, self.predictionDeviationWindow):
				if sign == 0:
					result[i] = result[i]*avg
				elif (result[i]*avg).real*sign > 1:
					result[i] = result[i]*avg

		return result


#### PREDICTION HELPERS
	def useHistoricPrediction(self, startTime,  endTime):
		self.lastPredictionUpdate = self.host.time()
		return list(self.predictor.predictValues(startTime, int((endTime-startTime) / self.timeBase) ) )

	def useGivenPrediction(self, startTime,  endTime):
		self.lastPredictionUpdate = self.host.time()
		result = [complex(0.0, 0.0)] * int((endTime - startTime) / self.devData['timeBase'])

		t = startTime
		idx = 0
		while t < endTime:
			val = complex(0.0, 0.0)
			if self.intradayPrediction != None and t < startTime + self.updateTime:
				val = complex(self.intradayPredictionReader.readValue(t) * self.dev.scaling, 0.0)
			else:
				val = complex(self.givenPredictionReader.readValue(t) * self.dev.scaling, 0.0)

			result[idx] = val
			idx += 1
			t += self.devData['timeBase']
		return result


	def usePerfectPrediction(self, startTime,  endTime):
		self.lastPredictionUpdate = self.host.time()
		result = list(self.zCall(self.dev, 'readValues', startTime, endTime, None, self.timeBase) )
		return result


#### EVENT BASED PREDICTION UPDATE
	def updatePrediction(self):
		self.updatingPrediction = True
		if self.useEventControl and not self.perfectPredictions:

			startTime = self.host.time()
			if (startTime % self.timeBase) != 0:
				startTime = (startTime - (startTime % self.timeBase)) + self.timeBase
			prediction = self.doPrediction(startTime, startTime + self.updateTime, True)

			# Now create the update profile
			time = startTime
			idx = 0
			updateProfile = {}

			self.lockPlanning.acquire()
			for c in self.commodities:
				updateProfile[c] = []
				while idx < len(prediction):
					if idx == 0:
						updateProfile[c].append(complex(0.0, 0.0))
					else:
						try:
							updateProfile[c].append(prediction[idx] - self.realized[c][time])
						except:
							updateProfile[c].append(prediction[idx])
						self.realized[c][time] = prediction[idx]

					if self.forwardLogging and self.host.logControllers:
						self.logValue("W-power.realized.real.c." + c, self.realized[c][time].real, time)
						if self.host.extendedLogging:
							self.logValue("W-power.realized.imag.c." + c,self.realized[c][time].imag,time)

					idx += 1
					time += self.timeBase
			self.lockPlanning.release()

			self.zCall(self.parent, 'updateRealized', updateProfile)

		self.lastPredictionUpdate = self.host.time()
		self.updatingPrediction = False


	def initializePredictors(self):
		self.updateDeviceProperties()
		self.lastPredictionUpdate = self.host.time()

		if self.perfectPredictions:
			return

		elif self.givenPrediction != None:
			self.givenPredictionReader = ClientCsvReader(dataSource=self.givenPrediction, timeBase=self.devData['timeBase'], column=self.devData['column'], timeOffset=self.devData['timeOffset'], host=self.host)

			if self.intradayPrediction != None:
				self.intradayPredictionReader = ClientCsvReader(dataSource=self.intradayPrediction, timeBase=self.devData['timeBase'], column=self.devData['column'], timeOffset=self.devData['timeOffset'], host=self.host)
			return

		else:
			self.predictor = WindowPredictor(self.timeBase)
			time = self.host.time(self.timeBase) - (4*7*24*3600)
			data = list(self.zCall(self.dev, 'readValues', time , time + (4*7*24*3600), None, self.timeBase) )
			self.predictor.addSamples(data, time, self.timeBase)
			return
