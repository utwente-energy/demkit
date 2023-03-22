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
from opt.optAlg import OptAlg
import util.helpers

import copy
import numpy as np
import math

#Buffer converter controller
class ThermalBufConvCtrl(ThermalDevCtrl):
	def __init__(self,  name,  dev,  ctrl,  host):
		ThermalDevCtrl.__init__(self, name, dev, ctrl, host)

		self.devtype = "BufferConverterController"

		self.useReactiveControl = False #Heat pumps dont do this

		self.commodities = ['ELECTRICITY', 'HEAT']
		self.weights = {'ELECTRICITY': 1.0, 'HEAT': 0.0}

		self.lastPrediction = -1
		self.predictionCache = []

		# Bookkeeping of predictions for synchronized planning
		self.predictionPlanning = None
		self.predictionPlanningTime = -1

		if self.persistence != None:
			self.watchlist = self.watchlist + ["lastPrediction", "predictionCache"]
			self.persistence.setWatchlist(list(self.watchlist))

	def startup(self):
		ThermalDevCtrl.startup(self)

	def timeTick(self, time, deltatime=0):
		# Check if any of the thermostats has a new setpoint, this is a reason to replan with event based control
		if self.useEventControl:
			event = False
			for t in self.dev.thermostats:
				if t.setpointChanged:
					event = True
					t.setpointChanged = False #reset flag
			if event:
				self.requestIncentive()
			
	def doPlanning(self, signal, requireImprovement = True):
		# Perform a prediction on the energy demand drained from the buffer
		consumption = self.predictionPlanning
		if self.predictionPlanningTime < signal.time:
			consumption = self.doPrediction(signal.time-(signal.time%signal.timeBase),
											signal.time-(signal.time%signal.timeBase)+signal.timeBase*signal.planHorizon)

			self.predictionPlanning  = consumption
			self.predictionPlanningTime = signal.time

		if len(consumption) != signal.planHorizon:
			consumption = util.helpers.interpolate(consumption, signal.planHorizon)

		result =  self.bufPlanning(signal, copy.deepcopy(self.candidatePlanning[self.name]), consumption, requireImprovement, self.devDataPlanning)
		self.candidatePlanning[self.name] = copy.deepcopy(result['profile'])
		return result

	def doEventPlanning(self, signal):
		# Synchronize the device state:
		self.updateDeviceProperties()

		# Perform a prediction on the energy demand drained from the buffer
		consumption = self.doPrediction(signal.time-(signal.time%signal.timeBase),
										signal.time-(signal.time%signal.timeBase)+signal.timeBase*signal.planHorizon,
										True)

		if len(consumption) != signal.planHorizon:
			consumption = util.helpers.interpolate(consumption, signal.planHorizon)

		return self.bufEventPlanning(signal, consumption)


	def doPrediction(self,  startTime,  endTime, force = False):
		# Synchronize the device state:
		self.updateDeviceProperties()

		if self.lastPrediction < self.host.time() or force:
			result = [0.0] * int((endTime - startTime) / self.timeBase)

			if len(self.dev.thermostats) > 0:
				# Predict heat demand to heat zones
				producingPowers = [ self.dev.producingPowers[0] / float(len(self.dev.thermostats)), self.dev.producingPowers[-1] / float(len(self.dev.thermostats)) ]

				for thermostat in self.dev.thermostats:
					result = list(np.array(result) + np.array(thermostat.doPrediction(startTime, endTime, producingPowers, self.timeBase) ) )

			# Predict hot water demand for taps
			for dhw in self.dev.dhwTaps:
				result = list(np.array(result) + np.array(dhw.doPrediction(startTime, endTime, self.timeBase)) )

			self.predictionCache = list(result)
			self.lastPrediction = self.host.time()

		result = self.predictionCache

		return result

	def bufEventPlanning(self, signal, consumption):
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

		# for c in self.commodities:
		# 	for i in range(0,  len(signal.desired[c])):
		# 		t = int((signal.time - (signal.time%signal.timeBase)) + i*self.timeBase)
		# 		try:
		# 			signal.desired[c][i] = 0.5*self.plan[c][t] + 0.5*signal.desired[c][i]
		# 		except:
		# 			signal.desired[c][i] = 0.0



		result = self.bufPlanning(signal, copy.deepcopy(currentPlan), consumption, False)
		plan = copy.deepcopy(result['profile'])

		result['realized'] = {}
		for c in self.commodityIntersection(signal.commodities):
			result['realized'][c] = list(np.array(result['profile'][c]) - np.array(currentPlan[c]))

		self.setPlan(plan, signal.time, signal.timeBase)

		self.lockPlanning.release()

		# Communicate the realized profile
		self.zCall(self.parent, 'updateRealized', dict(result['realized']))


	# Bufferplanning shared between buffers and bufferconverters
	def bufPlanning(self, signal, currentPlanning, consumption=[], requireImprovement = True, devData = None):
		if devData is None:
			devData = self.updateDeviceProperties()

		# Prepare the resultVector
		result = {}

		# Synchronize the device state:
		self.updateDeviceProperties()

		# Checks
		assert(devData['soc'] <= devData['capacity']) #If this gets triggered, make sure you set dev.soc!!!

		# Fix the data
		s = self.preparePlanningData(signal, currentPlanning)

		# Now starts the real planning
		# Take the intersection of both lists of commodities
		commodities = list(set.intersection(set(self.commodities), set(signal.commodities)))

		# Check if there are bounds, and if so, translate them into heat, such that they can be used in the opimization
		upperLimits = []
		lowerLimits = []
		for c in commodities:
			cop = 1
			if c != 'HEAT':
				cop = self.devData['cop'][c]

			if c in signal.upperLimits and c in signal.lowerLimits and len(signal.upperLimits[c]) > 0 and len(signal.lowerLimits[c]) > 0:
				ul = list(signal.upperLimits[c])
				ll = list(signal.lowerLimits[c])
				if cop < 0:
					# inversion required
					ul = list(signal.lowerLimits[c])
					ll = list(signal.upperLimits[c])

				# Select the upper limits
				if len(upperLimits) == 0:
					for i in ul:
						upperLimits.append(i * cop)
				else:
					for i in range(0, len(ul)):
						if ul[i] * cop < upperLimits[i]:
							upperLimits[i] = ul[i]*cop

				# Select the lower limits
				if len(lowerLimits) == 0:
					for i in ul:
						lowerLimits.append(i * cop)
				else:
					for i in range(0, len(ul)):
						if ll[i] * cop < lowerLimits[i]:
							lowerLimits[i] = ll[i]*cop

		# Convert the desired profile into a desired profile in terms of heat
		desired = [0] * signal.planHorizon

		for c in commodities:
			for i in range(0, len(desired)):
				desired[i] += s.desired[c][i] * devData['cop'][c] * s.weights[c]

				if len(upperLimits) > 0 and len(lowerLimits) > 0:
					# Make the desired profile fit in the new bounds
					desired[i] = max(lowerLimits[i].real, max(desired[i].real, upperLimits[i].real))

		prices = [0] * signal.planHorizon
		if s.profileWeight < 1:
			for c in commodities:
				for i in range(0, len(desired)):
					prices[i] += s.prices[c][i].real * devData['cop'][c].real


		cons = list(consumption)

		# If we have load shedding, we can see if we can reduce the demand (e.g. cooling down the building a bit more) to reduce the energy consumption
		# We do so by checking by how much we need ot change the demand.
		if signal.allowDiscomfort and not self.strictComfort and len(upperLimits) > 0 and len(lowerLimits) > 0:
			# Obtain the total energy demand
			total = 0.0
			for val in cons:
				total += val.real

			if total > 0:
				# See what we can do with both bonds
				upper = 0
				lower = 0
				for val in upperLimits:
					upper += val.real
				for val in lowerLimits:
					lower += val.real

				# Add the headroom from the storage
				soc = devData['soc']*(3600.0/signal.timeBase)
				cap = devData['capacity']*(3600.0/signal.timeBase)
				upper += soc
				lower -= cap-soc

				# Find what is possible in terms of energy
				fraction = max(0, max(lower, min(total, upper)) / total )

				# Scale the consumption
				for i in range(0, len(cons)):
					cons[i] *= fraction


		# Now we call Thijs vd Klauw's buffer planning magic
		# But we scale all to Wtau instead of Wh
		opt = OptAlg()
		if devData['discrete']:
			p = opt.bufferPlanning(desired,
								   devData['soc']*(3600.0/signal.timeBase),
								   devData['soc']*(3600.0/signal.timeBase),
								   devData['capacity']*(3600.0/signal.timeBase),
								   cons,
								   devData['producingPowers'], 0, 0,
								   lowerLimits, upperLimits,
								   self.useReactiveControl,
								   prices,
								   s.profileWeight )
		else:
			p = opt.bufferPlanning(desired,
								   devData['soc']*(3600.0/signal.timeBase),
								   devData['soc']*(3600.0/signal.timeBase),
								   devData['capacity']*(3600.0/signal.timeBase),
								   cons,
								   [], devData['producingPowers'][0], devData['producingPowers'][-1],
								   lowerLimits, upperLimits,
								   self.useReactiveControl,
								   prices,
								   s.profileWeight )

		profileResult = {}
		# Now translate into commodities
		for c in self.commodities:
			if c != 'HEAT':
				profileResult[c] = [math.copysign(x/devData['cop'][c], devData['cop'][c]) for x in p]
			else:
				profileResult[c] = list(p)

		#calculate the improvement
		improvement = 0.0
		if requireImprovement:
			improvement = self.calculateImprovement(s.desired,  copy.deepcopy(self.candidatePlanning[self.name]),  profileResult)
			if(improvement <= 0.0):
				profileResult = copy.deepcopy(self.candidatePlanning[self.name])

		#send out the result
		result['improvement'] = max(0.0, improvement)
		result['profile'] = copy.deepcopy(profileResult)

		return result

	#Override setPlan to include expected SoC:
	def setPlan(self, plan, time, timeBase):
		ThermalDevCtrl.setPlan(self, plan, time, timeBase)

		self.plannedSoC = {}
		commodities = list(plan.keys())

		# Synchronize the device state:
		self.updateDeviceProperties()
		soc = self.devData['soc']
		cop = self.devData['cop'][self.commodities[0]]

		for i in range(0, len(plan[commodities[0]])):
			t = int(time + i*timeBase)

			for c in commodities:
				soc += plan[c][i].real * cop * (timeBase/3600.0)
			self.plannedSoC[t] = max(0, min(soc, self.devData['capacity']))
