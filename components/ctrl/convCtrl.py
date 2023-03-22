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


from ctrl.devCtrl import DevCtrl
from opt.optAlg import OptAlg
from ctrl.optCtrl import OptCtrl

import numpy as np
import random
import copy

# FIXME: HAS NOT RECEIVED A MAJOR UPDATE AS EVALUATION REQUIRES MORE ADVANCED MODELS

#Buffer vehicle controller
class ConvCtrl(DevCtrl):
	#Make some init function that requires the host to be provided
	def __init__(self,  name,  dev,  ctrl,  host):
		DevCtrl.__init__(self,   name,  dev,  ctrl,  host)

		self.devtype = "ConverterController"
		self.nextPlan = 0
		self.replanInterval = [4*900, 8*900]
		self.allowReplanning = True # Allow intermediate replanning for event-based planning

		self.prioritizedCommodity = 'HEAT' # Default to none

			
	def timeTick(self, time, deltatime=0):
		if self.useEventControl:
			if time >= self.nextPlan:
				self.requestIncentive()

	def doPlanning(self, signal, requireImprovement = True):
		self.lockPlanning.acquire()

		result =  self.convPlanning(signal, copy.deepcopy(self.candidatePlanning[self.name]), requireImprovement)
		self.candidatePlanning[self.name] = copy.deepcopy(result['profile'])

		self.lockPlanning.release()
		return result

	def doEventPlanning(self, signal):
		return self.convEventPlanning(signal)

	def convEventPlanning(self, signal):
		assert(False) #Untested!
		self.lockPlanning.acquire()
		self.updateDeviceProperties()

		currentPlan = {}
		for c in self.commodityIntersection(signal.commodities):
			currentPlan[c] = []
			for i in range(0,  len(signal.desired[c])):
				t = int((signal.time - (signal.time%signal.timeBase)) + i*self.timeBase)
				try:
					currentPlan[c].append(self.realized[c][t])
				except:
					currentPlan[c].append(complex(0,0))


		result = self.convPlanning(signal, copy.deepcopy(currentPlan), False)
		plan = copy.deepcopy(result['profile'])

		result['realized'] = {}
		for c in self.commodities:
			result['realized'][c] = list(np.array(result['profile'][c]) - np.array(currentPlan[c]))

		self.setPlan(plan, signal.time, signal.timeBase, True)

		self.lockPlanning.release()

		self.zCall(self.parent, 'updateRealized', copy.deepcopy(result['realized']))

	# Buffer planning shared between buffers and buffer converters
	def convPlanning(self, signal, currentPlanning, requireImprovement = True):
		devData = self.updateDeviceProperties()

		# Prepare the resultVector
		result = {}

		# Fix the data
		s = self.preparePlanningData(signal, currentPlanning)

		profileResult = {} # This is the thing we need to fill.
		for c in self.commodities:
			profileResult[c] = []

		# Obtain the desired target profile converted in the primary commodity
		target = []
		for t in range(0, s.planHorizon):
			desired = complex(0.0, 0.0)
			if not s.allowDiscomfort:
				for c in self.commodities:
					desiredc = s.desired[c][t]

					if c in self.devData['cop']:
						desired += (desiredc * s.weights[c]) / self.devData['cop'][c]
					else:
						desired += desiredc * s.weights[c]

			if s.allowDiscomfort and self.prioritizedCommodity is not None:
				for c in [self.prioritizedCommodity]:
					if c in s.lowerLimits and c in s.upperLimits:
						desired = max(s.lowerLimits[c][t], min(s.desired[c][t], s.upperLimits[c][t]))
						desired = desired / self.devData['cop'][self.prioritizedCommodity]

			target.append(desired)

		# Now obtain the profiles for the other commodities
		power = 0
		for desired in target:
			for c in devData['commoditiesIn']:
				power = max(devData['powers'][0], min(desired, devData['powers'][-1]))
				profileResult[c].append(power)

			for c in devData['commoditiesOut']:
				profileResult[c].append(power * devData['cop'][c])

		#calculate the improvement
		improvement = 0.0
		boundImprovement = 0.0
		if requireImprovement:
			improvement = self.calculateImprovement(signal.desired,  copy.deepcopy(self.candidatePlanning[self.name]),  profileResult)
			boundImprovement =  self.calculateBoundImprovement(copy.deepcopy(self.candidatePlanning[self.name]), profileResult, signal.upperLimits, signal.lowerLimits, norm=2)

			if signal.allowDiscomfort and boundImprovement > 0.00:
				improvement = max(improvement, boundImprovement)

			if improvement < 0.0 or boundImprovement < 0.0:
				improvement = 0.0 	 
				profileResult = copy.deepcopy(self.candidatePlanning[self.name])

		#select a random new plan interval
		self.nextPlan = self.host.time() + random.randint(self.replanInterval[0], self.replanInterval[1])

		#send out the result
		result['boundImprovement'] = boundImprovement
		result['improvement'] = max(0.0, improvement)
		result['profile'] = copy.deepcopy(profileResult)

		return result