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


from ctrl.bufCtrl import BufCtrl
import util.helpers
from util.windowPredictor import WindowPredictor

import copy

##### NOTICE #####
# Note that there is a better thermal model for heating in the thermal folder!

#Buffer converter controller
class BufConvCtrl(BufCtrl):
	def __init__(self,  name,  dev,  ctrl,  host):
		BufCtrl.__init__(self,   name,  dev,  ctrl,  host)

		self.devtype = "BufferConverterController"
		self.predictor = None

		self.useReactiveControl = False #Heat pumps dont do this

		# persistence
		if self.persistence != None:
			self.watchlist += ["devData", "devDataUpdate", "predictor"]
			self.persistence.setWatchlist(self.watchlist)

	def startup(self):
		BufCtrl.startup(self)

		# Initialize the predictions
		if self.predictor is None:
			self.predictor = WindowPredictor(self.timeBase)

			time = self.host.time(self.timeBase) - (4*7*24*3600)
			data = list(self.zCall(self.dev, 'readValues', time , time + (4*7*24*3600), None, self.timeBase) )
			self.predictor.addSamples(data, time, self.timeBase)

	def timeTick(self, time, deltatime=0):
		# Add a sample to the predictor
		if (time % self.timeBase == 0):
			self.updateDeviceProperties()
			self.predictor.addSample(self.devData['selfConsumption'], time)

		if self.useEventControl:
			if time >= self.nextPlan:
				self.requestIncentive()
			
	def doPlanning(self, signal, requireImprovement = True):
		self.lockPlanning.acquire()
		# Synchronize the device state:
		self.updateDeviceProperties()

		# Perform a prediction on the energy demand drained from the buffer
		consumption = self.doPrediction(signal.time-(signal.time%signal.timeBase),
										signal.time-(signal.time%signal.timeBase)+signal.timeBase*signal.planHorizon)

		if len(consumption) != signal.planHorizon:
			consumption = util.helpers.interpolate(consumption, signal.planHorizon)

		#Scale the consumption according to the COP
		consumption = [x/self.devDataPlanning['cop'] for x in consumption]

		# Call the buffer planning implementation from the buffer controller
		result = self.bufPlanning(signal, copy.deepcopy(self.candidatePlanning[self.name]), consumption, requireImprovement, self.devDataPlanning, self.planningCapacity, self.planningPower)
		self.candidatePlanning[self.name] = copy.deepcopy(result['profile'])

		self.lockPlanning.release()
		return result

	def doEventPlanning(self, signal):
		self.lockPlanning.acquire()
		self.updateDeviceProperties()

		# Synchronize the device state:
		self.updateDeviceProperties()

		# Perform a prediction on the energy demand drained from the buffer
		consumption = self.doPrediction(signal.time-(signal.time%signal.timeBase),
										signal.time-(signal.time%signal.timeBase)+signal.timeBase*signal.planHorizon)

		if len(consumption) != signal.planHorizon:
			consumption = util.helpers.interpolate(consumption, signal.planHorizon)

		#Scale the consumption according to the COP
		consumption = [x/self.devData['cop'] for x in consumption]

		self.lockPlanning.release()

		# Call the buffer planning implementation from the buffer controller
		return self.bufEventPlanning(signal, consumption)


	def doPrediction(self,  startTime,  endTime):
		if self.perfectPredictions:
			return list(self.zCall(self.dev, 'readValues', startTime , endTime, None, self.timeBase) )
		else:
			return list(self.predictor.predictValues(startTime, int((endTime-startTime) / self.timeBase) ) )