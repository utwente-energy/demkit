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


import numpy as np
from ctrl.groupCtrl import GroupCtrl
from data.psData import PSData

import copy

# ADMM Group controller
# Reading material for reference:
# Distributed Convex Optimization for Electric Vehicle Aggregators
# Rivera, Goebel, Jacobsen
# IEEE: https://ieeexplore.ieee.org/document/7372473

# Special thanks to Victor Reijnders for the first version of this implementation

# The ADMM algorithm, with gamma = 0 creates a system that is similar to profile steering on the local level
# Therefore, with this implementation, we share the device controllers as implemented with Profile Steering
# Furthermore, the current implementation inherits on the Profile Steering code
# As a result, ADMM and event-driven Profile Steering may be combined as well, similarly auctions may be used (when implemented) easily too

# FIXME
# Work in progress, we first extend
# Multiple levels of control not yet supported (pass-through nodes)
# Local limits should work, but intermediate stricter limits are not an option yet
# Cleanup needs to be considered later on
# In comparison to the implementation by Victor, we perform incentive transformations at the group controller (similar to Profile Steering)
# This leads to less operatiosn (less computation power) and allows us to use the same PS device controllers :)
# In the future, we may alter the PSData container for a generic data container using some smart inheritance. The way it was originally intended anyways.
# Also, it only works for a single commodity currently. I expect it will work for multiple commodities as well, similarly to PS!


# ADMM++
class AdmmGroupCtrl(GroupCtrl):
	def __init__(self,  name,  host, parent = None, congestionPoint = None, dev=None):
		GroupCtrl.__init__(self,  name,  host, parent, congestionPoint, dev)
		self.devtype = "GroupController"

		# ADMM++
		self.rho = 0.5
		self.mu = 10 # used for the penalty parameter rho
		self.tauIncr = 2 # used for the penalty parameter rho
		self.tauDecr = 2 # used for the penalty parameter rho
		self.epsPrimal = 100 # stopping criterium for the primal residual
		self.epsDual = 100 # stopping criterium for the dual residual
		self.delta = 1 # scaling parameter for aggregator's objective


	def initiatePlanning(self, lock=False):
		if not lock:
			self.lockSyncPlanning.acquire()

			if self.zCall(self.host, 'time') < self.nextPlan:
				# Planning already performed
				self.lockSyncPlanning.release()
				return

		s = PSData()
		s.copyFrom(self)
		s.time = self.host.time()-(self.host.time()%self.timeBase)
		s.timeBase = self.timeBase

		# Stimuli:
		desired = {}
		for c in self.commodities:
			desired[c] = self.desired[c].readValues(s.time, s.time+s.planHorizon*s.timeBase)
		prices = {}
		for c in self.commodities:
			prices[c] = self.prices[c].readValues(s.time, s.time+s.planHorizon*s.timeBase)

		s.desired = copy.deepcopy(desired)
		s.prices = copy.deepcopy(prices)

		s.averageProfile = self.genZeroes(s.planHorizon)
		s.scaledLagrangian = self.genZeroes(s.planHorizon)

		# Synchronize data used for planning
		self.startSynchronizedPlanning(s)

		# Perform the planning
		self.doInitialPlanning(s)
		self.doPlanning(s)
		self.planningWinners = []

		self.setPlanningWinner(s.time, s.timeBase, self.name)

		# Incorporate updates that happened in the meanwhile
		self.endSynchronizedPlanning(s)

		if not lock:
			# We need to release the lock ourselves (running in a separate thread)
			self.lockSyncPlanning.release()

	def doPlanning(self, signal):
		# Prepare the data and limits
		#self.resetIteration(signal.source, [])
		s = copy.deepcopy(signal)

		result = self.iterativePlanning(s)

		# Bookkeeping of the planning
		self.lastPlannedTime = (signal.planHorizon * signal.timeBase) + signal.time
		t = signal.time
		self.nextPlan = (t - t%(self.planInterval * self.timeBase)) + (self.planInterval * self.timeBase) + self.alignNextPlan

		return result


#### PROFILE STEERING ALGORITHM
	# Initial planning to obtain the total power profile == energy consumption production over the horizon
	def doInitialPlanning(self,  signal, parents = []):
		result = {}
		time = signal.time
		parents = copy.deepcopy(parents)

		#make sure all dicts are there:
		for c in signal.commodities:
			if c not in self.plan:
				self.plan[c] = {}

		self.candidatePlanning[self.name] = self.genZeroes(signal.planHorizon)
		for p in parents:
			self.candidatePlanning[p] = self.genZeroes(signal.planHorizon)

		parents.append(self.name)

		s = copy.deepcopy(signal)
		results = self.zCall(self.children, 'doInitialPlanning', s, list(parents))
		for k,r in results.items():
			for c in self.commodityIntersection(r['profile'].keys()):
				self.candidatePlanning[self.name][c] = copy.deepcopy(list(np.array(self.candidatePlanning[self.name][c]) + np.array(r['profile'][c])))

		#Bookkeeping
		self.planning = copy.deepcopy(self.candidatePlanning[self.name])

		for p in parents:
			self.candidatePlanning[p] = copy.deepcopy(self.planning)

		for c in self.commodities:
			for i in range(0,  len(self.planning[c])):
				self.plan[c][int(time + i*self.timeBase)] = self.planning[c][i]

		#Set the vars right
		t = self.host.time()
		self.nextPlan = (t - t%(self.planInterval * self.timeBase)) + (self.planInterval * self.timeBase) + self.alignNextPlan

		result['improvement'] = 0.0
		result['profile'] = dict(self.candidatePlanning[self.name])

		return result


	#Profile steering algorithm
	def iterativePlanning(self,  signal):
		result = {}
		time = signal.time
		timeBase = signal.timeBase

		# Adjust the desired profile and local profile into the desired profile (signal) and limits
		if self.parent is not None and self.parentConnected:
			for c in self.commodities:
				signal.desired[c] = list( np.array(signal.desired[c]) + np.array(list(self.candidatePlanning[self.name][c])))

		# Participating children list (may get pruned in the process)
		participatingChildren = list(self.children)

		# ADMM algorithm initialization
		residual = 2*self.epsPrimal
		dualResidual = 2*self.epsDual

		# Bookkeeping from previous iteration
		previousRho = self.rho
		rho = self.rho

		# We need to track all profiles of the children at this level (can this be hidden? privacy?)
		previousAverageProfile = signal.averageProfile.copy()
		previousScaledLagrangian = signal.scaledLagrangian.copy()
		previousGroupPlanning = self.genZeroes(signal.planHorizon)

		previousChildPlanning={}
		for i in participatingChildren:
			previousChildPlanning[i] = self.genZeroes(signal.planHorizon)

		# In contrast to Profile Steering, all children are involved in every iteration, so this is rather static:
		winners = []
		for child in participatingChildren:
			winners.append(child)
			self.planningWinners.append(child)

		s = copy.deepcopy(signal)
		s.source = self.name
		s.upperLimits = copy.deepcopy(signal.upperLimits)
		s.lowerLimits = copy.deepcopy(signal.lowerLimits)
		s.rho = rho

		iter = 0
		while iter < self.maxIters and (residual > self.epsPrimal or dualResidual > self.epsDual) and participatingChildren:
		# for i in range(0,  self.maxIters):
			if self.parent == None or self.parentConnected == False:
				self.logMsg("Planning iteration: "+str(iter))
				self.resetPlanning([])

			# We cannot support multiple commodities yet:
			assert(len(self.commodities) == 1)

			for c in self.commodities:
				# Preparing the steering signal:
				s.desired[c] = list(np.subtract(np.array([0]*len(s.averageProfile[c])),np.add(np.array(s.averageProfile[c]),np.array(s.scaledLagrangian[c]))))

			childPlanning = {}
			self.candidatePlanning[self.name] = {}
			for c in self.commodities:
				self.candidatePlanning[self.name][c] = [0] * s.planHorizon

			self.zCall(participatingChildren, "resetIteration", self.name)
			results = self.zCall(participatingChildren, 'doPlanning', s)
			for child, val in results.items():
				childPlanning[child] = {}
				for c in self.commodities:
					childPlanning[child][c] = val['profile'][c]
					self.candidatePlanning[self.name][c] = list(np.array(self.candidatePlanning[self.name][c]) + np.array(val['profile'][c]))

			# Bookkeeping on aggregator level
			groupPlanning = {}
			for c in self.commodities:
				groupPlanning[c] = (rho/2)*np.subtract(np.array(previousGroupPlanning[c]),np.add(np.array(s.averageProfile[c]),np.array(s.scaledLagrangian[c])))
				s.averageProfile[c] = list(np.mean(np.insert(np.array([childPlanning[i][c] for i in childPlanning.keys()]),0, groupPlanning[c], axis=0), axis=0))  # \bar{x}^{k+1}
				s.scaledLagrangian[c] = list(np.add(np.array(s.averageProfile[c]),np.array(previousScaledLagrangian[c])))  #u^{k+1}

				# Not sure how residuals should work for multiple commodities tho
				residual = np.linalg.norm(s.averageProfile[c], ord=2) # ||r^k||_2
				dualFeasibility = []
				for i in participatingChildren:
					tempDualFeasibility = list(np.add( np.subtract(np.array(childPlanning[i][c]), np.array(previousChildPlanning[i][c])), np.subtract(np.array(previousAverageProfile[c]), np.array(s.averageProfile[c])))) #s_i^k
					dualFeasibility += [-rho*(len(participatingChildren)+1)*j for j in tempDualFeasibility]
				dualResidual = np.linalg.norm(dualFeasibility, ord=2) # ||s^k||_2

			# Updating Rho
			if residual > self.mu * dualResidual:
				rho = self.tauIncr * previousRho
			elif dualResidual > self.mu * residual:
				rho = previousRho / self.tauDecr
			else:
				rho = previousRho

			self.planningWinners = list(winners)
			self.zCall(participatingChildren, 'setIterationWinner', self.name, None)
			self.zCall(participatingChildren, 'setPlanningWinner', time,  timeBase, self.name, [])

			# Further bookkeeping
			previousRho = rho
			previousChildPlanning = childPlanning.copy()
			previousAverageProfile = copy.deepcopy(s.averageProfile)
			previousScaledLagrangian = copy.deepcopy(s.scaledLagrangian)
			previousGroupPlanning = copy.deepcopy(groupPlanning)
			iter += 1

		result['profile'] = dict(self.candidatePlanning[self.name])
		return result
