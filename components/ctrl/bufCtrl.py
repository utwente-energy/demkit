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

import numpy as np
import random
import copy
import math

#Buffer vehicle controller
class BufCtrl(DevCtrl):
	#Make some init function that requires the host to be provided
	def __init__(self,  name,  dev,  ctrl,  host):
		DevCtrl.__init__(self,   name,  dev,  ctrl,  host)

		self.devtype = "BufferController"
		self.nextPlan = 0

		self.replanInterval = [4*900, 8*900]
		self.allowReplanning = True # Allow intermediate replanning for event-based planning

		# Deal with uncertainty through reduction
		self.planningCapacity = 0.8		# Fraction to use for planning, symmetric (i.e. it uses a Soc ranging from 0+x/2 - 1-x/2, where x is the variable
		self.planningPower = 0.6		# Fraction of the power to use, as above.
										# Note, does not work with discrete yet!
		self.eventPlanningCapacity = 0.9		# Fraction to use for planning, symmetric (i.e. it uses a Soc ranging from 0+x/2 - 1-x/2, where x is the variable
		self.eventPlanningPower = 0.8		# Fraction of the power to use, as above.
											# Note, does not work with discrete yet!
		self.plannedSoC = {}
		self.realizedSoC = {}

		# temporary test
		self.capacitylimits = None


	def timeTick(self, time, deltatime=0):
		if self.useEventControl:
			if time >= self.nextPlan:
				self.requestIncentive()
				
			#Check how much we deviate from the SoC and if required spawn an event to replan:
			elif time%self.timeBase == 0 and time in self.plannedSoC:
				# Synchronize the device state:
				self.updateDeviceProperties()
				if abs( self.devData['soc'] - self.plannedSoC[time] ) > 0.05*self.devData['capacity']:
					self.triggerEvent("stateOfChargeDeviation")

	def logStats(self, time):
		#logging:
		DevCtrl.logStats(self, time)

		self.lockPlanning.acquire()
		t = time - time%self.timeBase
		try:
			self.logValue("Wh-energy.soc.plan", self.plannedSoC[t])
			self.logValue("Wh-energy.soc.realized", self.realizedSoC[t])
		except:
			pass

		self.lockPlanning.release()

	def doPlanning(self, signal, requireImprovement = True):
		self.lockPlanning.acquire()

		consumption = [self.devDataPlanning['selfConsumption']] * signal.planHorizon
		result =  self.bufPlanning(signal, copy.deepcopy(self.candidatePlanning[self.name]), consumption, requireImprovement, self.devDataPlanning, self.planningCapacity, self.planningPower)
		self.candidatePlanning[self.name] = copy.deepcopy(result['profile'])

		self.lockPlanning.release()

		return result

	def doEventPlanning(self, signal):
		self.updateDeviceProperties()
		consumption = [self.devData['selfConsumption']] * signal.planHorizon
		return self.bufEventPlanning(signal, consumption)

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

		result = self.bufPlanning(signal, copy.deepcopy(currentPlan), consumption, False, None, self.eventPlanningCapacity, self.eventPlanningPower)
		plan = copy.deepcopy(result['profile'])

		result['realized'] = {}
		for c in self.commodities:
			result['realized'][c] = list(np.array(result['profile'][c]) - np.array(currentPlan[c]))

		self.setPlan(plan, signal.time, signal.timeBase, True)
		self.lockPlanning.release()
		self.zCall(self.parent, 'updateRealized', copy.deepcopy(result['realized']))

	# Buffer planning shared between buffers and buffer converters
	def bufPlanning(self, signal, currentPlanning, consumption=[], requireImprovement = True, devData = None, useableCapacity=1, useablePower=1):
		if devData is None:
			devData = self.updateDeviceProperties()

		# Prepare the resultVector
		result = {}

		# Synchronize the device state:
		self.updateDeviceProperties()

		# Checks
		assert(devData['soc'] <= devData['capacity']) #If this gets triggered, make sure you set dev.soc!!!
		if devData['discrete']:
			assert(useablePower > 0.99)

		# Prepare the steering signal
		s = self.preparePlanningData(signal, currentPlanning)

		# Now starts the real planning
		# Take the intersection of both lists of commodities
		commodities = list(set.intersection(set(self.commodities), set(signal.commodities)))

		# First we need to weave the input data:
		# The idea is to weave the different commodities to provide vectors to the buffer planning
		# This results in minor loss of options, but should give reasonable good results in little time
		desired = self.weaveDict(s.desired, commodities)
		prices = self.weaveDict(s.prices, commodities)

		upperLimits = []
		lowerLimits = []
		if len(signal.upperLimits) > 0:
			upperLimits = self.weaveDict(s.upperLimits, commodities)
		if len(signal.lowerLimits) > 0:
			lowerLimits = self.weaveDict(s.lowerLimits, commodities)
		cons = self.weaveMultiply(consumption, commodities)

		# Now we call Thijs vd Klauw's buffer planning magic
		opt = OptAlg()

		# Adjust the target SoC according to the desired profile
		# This automatically ensures that the buffers act based on powerlimits as well
		desiredEnergy = 0
		for d in desired:
			desiredEnergy += d

		# Now determine the target, adjusted by the demand
		targetSoC = max(0.0, min(self.devData['soc'] + (desiredEnergy / (3600.0 / signal.timeBase)), self.devData['capacity']))

		upperSoC = devData['capacity']*useableCapacity
		soc = self.devData['soc'] - (((1-useableCapacity)/2.0)*devData['capacity'])
		if soc < 0:
			targetSoC += -1*soc
		elif soc > upperSoC:
			targetSoC += (upperSoC - soc)

		targetSoC = max(0, min(targetSoC, upperSoC))
		targetSoC = targetSoC.real
		soc = max(0, min(soc,upperSoC))

		# preset the parameters for the
		capacity = devData['capacity'] * useableCapacity * (3600.0 / signal.timeBase) / devData['cop']
		soc = soc*(3600.0/signal.timeBase)/ devData['cop']
		target = targetSoC*(3600.0/signal.timeBase) / devData['cop']


		if devData['restrictedCapacity'] is not None:
			assert(len(self.commodities) == 1) # Not yet supported for multiple commodities
			capacity = []
			l = list(devData['restrictedCapacity'].keys())
			l.sort() # Not the most efficient manner yet
			for t in range(0,len(desired)):
				idx = 0	# on error, element [0] must be defined
				for i in l:
					if i <= (signal.time+(t*signal.timeBase)) % devData['restrictedCycleTime']:
						idx = i
					else:
						break
				capacity.append( (devData['restrictedCapacity'][idx] * (3600.0 / signal.timeBase) ) / devData['cop'] )

			for i in range(0, len(capacity)):
				capacity[i] = min(capacity[i], capacity[(i+1) % len(capacity) ] )

			assert(len(capacity) == len(desired)) # Only works for synchronized planning, not yet for event based
			if capacity[0] < soc:
				soc = capacity[0]
			if capacity[-1] < target:
				target = capacity[-1]



		# Check if we need to apply restricted charging powers
		if devData['restrictedChargingPowers'] is not None:
			assert(len(self.commodities) == 1) # Not yet supported for multiple commodities
			l = list(devData['restrictedChargingPowers'].keys())
			l.sort() # Not the most efficient manner yet
			for t in range(0,len(desired)):
				idx = 0	# on error, element [0] must be defined
				for i in l:
					if i <= (signal.time+(t*signal.timeBase)) % devData['restrictedCycleTime']:
						idx = i
					else:
						break
				if len(upperLimits >= t):
					# overwrite limits
					upperLimits[t] = min(upperLimits[t], devData['restrictedChargingPowers'][idx][-1])
					lowerLimits[t] = max(lowerLimits[t], devData['restrictedChargingPowers'][idx][0])
				else:
					upperLimits.append(devData['restrictedChargingPowers'][idx][-1])
					lowerLimits.append(devData['restrictedChargingPowers'][idx][0])



		# This is where the magic happens: Planning the buffer
		if devData['discrete']:
			p = opt.bufferPlanning(desired,
								   target,
								   soc,
								   capacity,
								   cons,
								   devData['internalPowers'], 0, 0,
								   lowerLimits, upperLimits,
								   self.useReactiveControl,
								   prices,
								   s.profileWeight,
								   intervalMerge = [1]*len(desired) )

			# Transform back using the efficiency vector
			internalPowers = devData['internalPowers']
			chargingEfficiency = devData['chargingEfficiency']

			# Discrete inefficiency planning
			if devData['useInefficiency']:
				for i in range(0, len(p)):
					try:
						idx = internalPowers.index(p[i].real)
						p[i] = p[i].real/chargingEfficiency[idx]
					except:
						# Not an exact value in the list, we need to interpolate
						idx = 0
						while idx < len(internalPowers) and internalPowers[idx] <= p[i].real+0.0001:
							idx +=  1
						eff = 1
						if idx >= len(internalPowers)-1:
							eff = chargingEfficiency[-1] # Reached the end of the list, take the last value
						else:
							d = (p[i].real - internalPowers[idx].real) / (internalPowers[idx+1].real - internalPowers[idx].real)
							assert(d <= 1.0001)
							eff = (d * chargingEfficiency[idx]) + ((1-d) * chargingEfficiency[idx+1])
						p[i] = p[i].real / eff

		else:
			p = opt.bufferPlanning(desired,
								   target,
								   soc, #devData['soc']*(3600.0/signal.timeBase)/devData['cop'],
								   capacity,
								   cons,
								   [], self.devData['chargingPowers'][0]*useablePower, devData['chargingPowers'][-1]*useablePower,
								   lowerLimits, upperLimits,
								   self.useReactiveControl,
								   prices,
								   s.profileWeight )

		# Sort back the result
		profileResult = self.unweaveVec(p, commodities)

		# select a random new plan interval
		self.nextPlan = self.host.time() + random.randint(self.replanInterval[0], self.replanInterval[1])

		#calculate the improvement
		improvement = 0.0
		boundImprovement = 0.0
		if requireImprovement:
			improvement = self.calculateImprovement(signal.desired,  copy.deepcopy(self.candidatePlanning[self.name]),  profileResult)
			boundImprovement = self.calculateBoundImprovement(copy.deepcopy(self.candidatePlanning[self.name]), profileResult, signal.upperLimits, signal.lowerLimits, norm=2)

			if signal.allowDiscomfort:
				improvement = max(improvement, boundImprovement)

			if improvement < 0.0 or boundImprovement < 0.0:
				improvement = 0.0
				profileResult = copy.deepcopy(self.candidatePlanning[self.name])

		result['boundImprovement'] = boundImprovement
		result['improvement'] = max(0.0, improvement)
		result['profile'] = copy.deepcopy(profileResult)

		return result


	#Override setPlan to include expected SoC:
	def setPlan(self, plan, time, timeBase, update=False):
		DevCtrl.setPlan(self, plan, time, timeBase)

		self.plannedSoC = {}
		commodities = list(plan.keys())

		# Synchronize the device state:
		self.updateDeviceProperties()
		soc = self.devData['soc']
		cop = self.devData['cop']

		for i in range(0, len(plan[commodities[0]])):
			t = int(time + i*timeBase)
			for c in commodities:
				soc += plan[c][i].real * cop * (timeBase/3600.0)

			self.plannedSoC[t] = max(0, min(soc, self.devData['capacity']))

			if self.forwardLogging and self.host.logControllers:
				if not update:
					self.logValue("Wh-energy.soc.plan", self.plannedSoC[t], t)
				else:
					self.logValue("Wh-energy.soc.realized", self.plannedSoC[t], t)