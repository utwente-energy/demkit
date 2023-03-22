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

from core.entity import Entity

import numpy as np
import math
import threading
import copy

class OptCtrl(Entity):
	def __init__(self,  name,  host):
		Entity.__init__(self,  name,  host)

		self.minImprovement = 1
		self.type = "controllers"
		self.timeBase = 900
		self.timeOffset = 0

		#System
		self.commodities = ['ELECTRICITY']
		self.weights = {'ELECTRICITY': 1}
		self.profileWeight = 1 # Beta in the work by Thijs van der Klauw, should be between 0-1. 1 = normal profile steering, 0 = prices only

		#Accounting
		self.planning = {}
		self.candidatePlanning = {}

		self.plan = {}
		self.realized = {}
		self.planningTimestamp = -1

		self.planningWinners = []
		self.lastPlannedTime = -1 # Holds the start time of the last planned block

		#Type of control
		self.useEventControl = True
		self.useReactiveControl = False

		self.islanding = False
		self.strictComfort = True	# DEPRECATED -> Device level only setting

		#links to connected entities
		self.parent = None
		self.children = []

		#logging
		try:
			self.forwardLogging = host.liveOperation
		except:
			self.forwardLogging = False

		# Default persistence items
		self.watchlist = ["planning", "candidatePlanning", "plan", "realized", "planningWinners", "lastPlannedTime"]

		# Locks
		self.lockPlanning = threading.Lock()

	def requestTickets(self, time):
		self.ticketCallback.clear()
		self.registerTicket(self.host.staticTicketPreTickCtrl, 'preTick', register=False)  # preTick
		self.registerTicket(self.host.staticTicketTickCtrl, 'timeTick', register=False)  # timeTick

	def preTick(self, time, deltatime=0):
		pass

	def timeTick(self, time, deltatime=0):
		pass
		#self.prunePlan()

	def postTick(self, time, deltatime=0):
		pass

	def logStats(self, time):
		pass

	#Start and end-functions for system/sim startup and shutdown
	def startup(self):
		if self.host != None:
			self.host.addController(self)

		Entity.startup(self)

	def shutdown(self):
		pass

	#Planning announcements
	def startSynchronizedPlanning(self, signal):
		self.zCall(self.children, 'startSynchronizedPlanning', signal)

	def endSynchronizedPlanning(self, signal):
		self.lockPlanning.acquire()
		result = {}

		# Now change the signal:
		# FIXME Need to adapt the signal if time has passed by since the start of the planning!
		# Furthermore, we need to do MPC if we want to make the planning start in the future.
		# However, that is future work and somehow needs ot be incorporated in start Sync planning, probably.
		if self.useEventControl:
			# Adaption of an event to align all data after time has elapsed. This part ensures that everything keeps on working in a deployment
			currentTime = self.host.time()
			if signal.time < currentTime:
				# Calculate the difference in intervals:
				diff = math.floor((currentTime - signal.time) / signal.timeBase)

				# adapt the signal
				signal.planHorizon -= diff
				signal.time += signal.timeBase * diff

				for c in signal.commodities:
					signal.desired[c] = copy.deepcopy(signal.desired[c][diff:])
					if c in signal.upperLimits:
						signal.upperLimits[c] = list(signal.desired[c][diff:])
					if c in signal.lowerLimits:
						signal.lowerLimits[c] = list(signal.desired[c][diff:])

		# Call the children to finalize too
		r = self.zCall(self.children, 'endSynchronizedPlanning', signal)

		# Wrapping up, ensure that the local bookkeeping is up to date
		if self.useEventControl:
			for data in r.values():
				for c in data:
					if c not in result:
						result[c] = dict(data[c])
					else:
						for t in data[c].keys():
							if t in result[c]:
								result[c][t] += data[c][t]
							else:
								result[c][t] = data[c][t]
			self.realized = copy.deepcopy(result)

		# Perform forward logging to track the results
		if self.forwardLogging and self.host.logControllers:
			for c in signal.commodities:
				for i in range(0,  signal.planHorizon):
					self.logValue("W-power.plan.real.c."+c,  self.plan[c][int(signal.time + i*signal.timeBase)].real, int(signal.time + i*signal.timeBase))
					if self.host.extendedLogging:
						self.logValue("W-power.plan.imag.c." + c, self.plan[c][int(signal.time + i*signal.timeBase)].imag, int(signal.time + i * signal.timeBase))

					if self.useEventControl:
						self.logValue("W-power.realized.imag.c." + c,self.realized[c][int(signal.time + i * signal.timeBase)].imag,int(signal.time + i * signal.timeBase))
						if self.host.extendedLogging:
							self.logValue("W-power.realized.real.c." + c,self.realized[c][int(signal.time + i * signal.timeBase)].real,int(signal.time + i * signal.timeBase))

		self.lastPlannedTime = signal.time + (signal.planHorizon-1) * signal.timeBase
		self.planningTimestamp = self.host.time()

		self.lockPlanning.release()
		return result






	#Basic PS control flow functions
	def setIterationWinner(self, source, child=None, parents = []):
		result = {'profile': {}, 'realized': {} }

		if child is None:
			child = self.name

		for c in self.commodities:
			result['profile'][c] = copy.deepcopy(list(np.array(self.candidatePlanning[child][c]) - np.array(self.candidatePlanning[source][c])))
		self.candidatePlanning[source] = copy.deepcopy(self.candidatePlanning[child])

		self.zCall(self.planningWinners, 'setIterationWinner', source, child, list(parents))

		return result

	def setPlanningWinner(self, time,  timeBase, source, parents=[]):
		# Clean up datasets
		self.lockPlanning.acquire()
		self.planning = copy.deepcopy(self.candidatePlanning[source])
		self.prunePlan()

		# Create timestamped plan (FIXME to be removed with the new library)
		for c in self.commodities:
			if c not in self.plan:
				self.plan[c] = {}

			for i in range(0,  len(self.planning[c])):
				t = int((time - time%timeBase) +i*timeBase)
				self.plan[c][t] = self.planning[c][i]

				if self.forwardLogging and self.host.logControllers:
					self.logValue("W-power.plan.real.c." + c, self.plan[c][int(time + i * self.timeBase)].real,int(time + i * timeBase))
					if self.host.extendedLogging:
						self.logValue("W-power.plan.imag.c." + c, self.plan[c][int(time + i * self.timeBase)].imag,int(time + i * timeBase))

		# Synchronize all candidates profiles, should not be needed tho.
		for p in parents:
			self.candidatePlanning[p] = copy.deepcopy(self.planning)

		if not self.useEventControl:
			self.setPlan(self.planning, time, timeBase)

		self.lockPlanning.release()
		self.zCall(self.planningWinners, 'setPlanningWinner', time, timeBase, source, list(parents))

	def resetIteration(self, source, parents = []):
		self.candidatePlanning[self.name] = copy.deepcopy(self.candidatePlanning[source])

		parents = copy.deepcopy(parents)
		for p in parents:
			self.candidatePlanning[p] = self.candidatePlanning[source]

		parents.append(self.name)
		self.zCall(self.children, 'resetIteration', source, list(parents))

		self.candidatePlanning[self.name] = copy.deepcopy(self.candidatePlanning[source])

	def resetPlanning(self, parents = []):
		self.planningWinners = []
		parents = copy.deepcopy(parents)
		parents.append(self.name)
		self.zCall(self.children, 'resetPlanning', list(parents))

	def prunePlan(self):
		try:
			for c in self.commodities:
				l = list(self.plan[c].keys())
				for k in l:
					if k <= self.host.time()-self.timeBase:
						del self.plan[c][k]
					else:
						break
		except:
			pass # dict not filled yet, nothing to clean

		try:
			for c in self.commodities:
				l = list(self.realized[c].keys())
				for k in l:
					if k <= self.host.time()-self.timeBase:
						del self.realized[c][k]
					else:
						break
		except:
			pass # dict not filled yet, nothing to clean





	# Helper functions
	def calculateImprovement(self,  desired,  old,  new, norm=2):
		improvement = 0
		commodities = self.commodityIntersection(old.keys(), desired.keys())

		for c in commodities:
			delta = np.array(new[c]) - np.array(old[c])
			a = np.linalg.norm((np.array(desired[c]) - np.array(old[c])), ord=norm)
			b = np.linalg.norm((np.array(desired[c]) - (np.array(old[c]) + delta)), ord=norm)
			improvement += self.weights[c] * (a - b)

		return improvement

	def calculateBoundImprovement(self, old, new, upperBounds, lowerBounds, norm=2):
		improvement = 0
		commodities = new.keys()

		penaltyOld = {}
		penaltyNew = {}
		for c in commodities:
			penaltyOld[c] = []
			penaltyNew[c] = []

			# First check the upperbounds
			if c in old and (c in upperBounds or c in lowerBounds):
				# Determine the penalty for old on upperbound
				penaltyOld[c] = [0] * len(old[c])
				penaltyNew[c] = [0] * len(new[c])

			if c in old and c in upperBounds:
				# We expect things to be aligned
				assert(len(old[c]) == len(new[c]) == len(upperBounds[c]))

				for i in range(0, len(old[c])):
					if old[c][i].real > upperBounds[c][i].real + old[c][i].real:
						penaltyOld[c][i] = abs(old[c][i].real - (upperBounds[c][i].real + old[c][i].real))

				# Determine the penalty for new on upperbound:
				for i in range(0, len(new[c])):
					if new[c][i].real > upperBounds[c][i].real + old[c][i].real:
						penaltyNew[c][i] = abs(new[c][i].real - (upperBounds[c][i].real + old[c][i].real))

			# Now the lowerBounds
			if c in old and c in lowerBounds:
				assert (len(old[c]) == len(new[c]) == len(lowerBounds[c]))

				# Determine the penalty for old on upperbound
				for i in range(0, len(old[c])):
					if old[c][i].real < lowerBounds[c][i].real + old[c][i].real:
						penaltyOld[c][i] = abs(old[c][i].real - (lowerBounds[c][i].real + old[c][i].real))

				# Determine the penalty for new on upperbound:
				for i in range(0, len(new[c])):
					if new[c][i].real < lowerBounds[c][i].real + old[c][i].real:
						penaltyNew[c][i] =  abs(new[c][i].real - (lowerBounds[c][i].real + old[c][i].real))

			a = np.linalg.norm(np.array(penaltyOld[c]), ord=norm)
			b = np.linalg.norm(np.array(penaltyNew[c]), ord=norm)

			try:
				improvement += self.weights[c] * (a-b)
			except:
				improvement += (a - b)

		return improvement


	def commodityIntersection(self, a, b = None):
		if b is None:
			b = self.commodities
		return list(set.intersection(set(a), set(b)))

	def calculateCommodityImprovement(self,  desired,  old,  new, norm=2):
		delta = np.array(new) - np.array(old)
		a = np.linalg.norm((np.array(desired) - np.array(old)), ord=norm)
		b = np.linalg.norm((np.array(desired) - (np.array(old) + delta)), ord=norm)
		return a - b

	def genZeroes(self, length, real=False):
		r = {}
		for c in self.commodities:
			if real:
				r[c] = [0.0] * length
			else:
				r[c] = [complex(0.0, 0.0)] * length
		return r





	# Getters
	def getPlan(self, time, commodity):
		result = 0
		self.lockPlanning.acquire()

		try:
			t = time - time%self.timeBase
			if self.useEventControl:
				#use realized instead
				if t in self.realized[commodity]:
					result = self.realized[commodity][t]
			else:
				#use planning
				if t in self.plan[commodity]:
					result = self.plan[commodity][t]
		except:
			# In case there is no planning yet, e.g. in an async mode
			pass

		self.lockPlanning.release()
		return result

	def getOriginalPlan(self, time, commodity = None):
		r = 0
		self.lockPlanning.acquire()

		t = time - time%self.timeBase
		try:
			if commodity == None:
				result = 0.0
				for c in self.commodities:
					if t in self.plan[c]:
						result += self.plan[c][t]
				r =  result
			else:
				if t in self.plan[commodity]:
					r =  self.plan[commodity][t]
		except:
			pass

		self.lockPlanning.release()
		return r



	# Structure
	def appendChild(self, child):
		self.children.append(child)

	def logValue(self, measurement,  value, time=None, deltatime=None):
		# Generic variant (disabled, reference code)
# 		tags = {'ctrltype':self.devtype,  'name':self.name}
# 		values = {measurement:value}
# 		self.host.logValue(self.type,  tags,  values, time)

		# InfluxDB optimized
		data = self.type+",ctrltype="+self.devtype+",name="+self.name+" "+measurement+"="+str(value)
		self.host.logValuePrepared(data, time, deltatime)


	# Interface
	def doPlanning(self,  signal):
		print("this function must be overridden")
		assert(False)

	def doEventPlanning(self,  signal):
		print("this function must be overridden")
		assert(False)

	def doInitialPlanning(self,  signal, parents = []):
		print("this function must be overridden")
		assert(False)

	def requestIncentive(self, timestamp):
		print("this function must be overridden")
		assert(False)

	def requestCancelation(self, source, childData):
		print("this function must be overridden")
		assert(False)

	def setPlan(self, plan, time, timeBase):
		pass

