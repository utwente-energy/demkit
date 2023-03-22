# DEMKit software
# Copyright (C) 2021 CAES and MOR Groups, University of Twente, Enschede, The Netherlands

# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NON
# INFRINGEMENT; IN NO EVENT SHALL LICENSOR BE LIABLE FOR ANY
# CLAIM, DAMAGES OR ANY OTHER LIABILITY ARISING FROM OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE THEREOF.


# Permission is hereby granted, non-exclusive and free of charge, to any person,
# obtaining a copy of the DEMKit-software and associated documentation files,
# to use the Software for NON-COMMERCIAL SCIENTIFIC PURPOSES only,
# subject to the conditions mentioned in the DEMKit License:

# You should have received a copy of the DEMKit License
# along with this program.  If not, contact us via email:
# demgroup-eemcs@utwente.nl.


import numpy as np
import math
from collections import OrderedDict
import threading
import copy

from ctrl.optCtrl import OptCtrl
from data.psData import PSData
from util.funcReader import FuncReader

class VirtualGroupCtrl(OptCtrl):
	def __init__(self, name, host, parent=None, congestionPoint=None, dev=None):
		OptCtrl.__init__(self, name, host)
		self.devtype = "GroupController"

		self.parent = parent

		# Link to a smart meter (device) for details
		self.dev = dev

		# This boolean can be used in the future to check whether the connection to the parent is still active
		self.parentConnected = False
		self.enabled = True  # Is the controller connected?

		# Planning parameters
		self.maxIters = None				# None will result in: len(self.children)
		self.planHorizon = 192
		self.planInterval = 96

		# Algorithms speedup through simultaneous commits:
		# Use these functions with care! MultipleCommits usually leads to better results
		self.multipleCommitsDivisor = 1  	# Divisor to reduce the number of selected commits for each iteration
		self.simultaneousCommits = 1 	# The number of simultaneous commits in the first iteration.
											# Default: None will result in len(self.children)

		# Objectives
		self.desired = None
		self.prices = None
		self.profileWeight = 1  	# Beta in the work by Thijs van der Klauw, should be between 0-1. 1 = normal profile steering, 0 = prices only
		self.congestionPoint = congestionPoint

		self.localWeight = {'ELECTRICITY': 0, 'EL1': 0, 'EL2': 0, 'EL3': 0, 'HEAT': 0, 'NATGAS': 0}
		self.localDesired = None

		# Local bookkeeping:
		self.nextPlan = -1
		self.alignNextPlan = host.startTime  # To align plannings with day starts from a config
		self.allowDiscomfort = False

		# Event based PS Parametrs
		self.isFleetController = False  # We need to set this explicitly, however, rootnodes become fleet controllers automatically in the startup!
		self.minProblem = 5000  # if this controller is a fleet controller, this is used to determine whether the parents problem should be used instead.
								# If the problem is too small, the higher level controller will be asked

		self.lockSyncPlanning = threading.Lock()

		# persistence
		if self.persistence != None:
			self.watchlist = self.watchlist + ['nextPlan', 'alignNextPlan']
			self.persistence.setWatchlist(list(self.watchlist))

	def preTick(self, time, deltatime=0):
		if (self.parent == None or self.parentConnected == False) and time >= self.nextPlan:  # or self.parentConnected == False
			if self.nextPlan == -1:  # First time
				# Run a first planning in the same thread
				self.initiatePlanning()
			else:
				# Start the planning in a separate thread
				self.runInThread('initiatePlanning')

	def logStats(self, time):
		# logging:
		t = time - time % self.timeBase
		try:
			for c in self.commodities:
				self.logValue("W-power.plan.real.c." + c, self.plan[c][t].real)
				if self.host.extendedLogging:
					self.logValue("W-power.plan.imag.c." + c, self.plan[c][t].imag)
					self.logValue("W-power.target.real.c." + c, self.desired[c].readValue(t).real)
					self.logValue("W-power.target.imag.c." + c, self.desired[c].readValue(t).imag)

				if self.useEventControl:
					self.logValue("W-power.realized.real.c." + c, self.realized[c][t].real)
					if self.host.extendedLogging:
						self.logValue("W-power.realized.imag.c." + c, self.realized[c][t].imag)


				self.logValue("n-price.signal.real.c." + c, self.prices[c].readValue(t).real)

		except:
			pass

		if self.host.extendedLogging:
			for c in self.commodities:
				try:
					# Objective of the plan
					obj = self.desired[c].readValue(time)
					self.logValue("n-obj-planning." + c, abs(self.plan[c][t] - obj))
					self.logValue("n-obj-planning-squared." + c, pow(abs(self.plan[c][t] - obj), 2))
					if self.useEventControl:
						self.logValue("n-obj-realized." + c, abs(self.realized[c][t] - obj))
						self.logValue("n-obj-realized-squared." + c, pow(abs(self.realized[c][t] - obj), 2))

					if self.dev != None:
						# Compare planning to real usage
						if c in self.dev:
							try:
								self.dev[c].measure(time)
								val = self.dev[c].consumption.real
								obj = obj.real
								self.logValue("n-obj-measured." + c, abs(val - obj))
								self.logValue("n-obj-measured-squared." + c, pow(abs(val - obj), 2))

								self.logValue("n-deviation-planning." + c, abs(self.plan[c][t] - val))
								self.logValue("n-deviation-planning-squared." + c, pow(abs(self.plan[c][t] - val), 2))
								if self.useEventControl:
									self.logValue("n-deviation-realized." + c, abs(self.realized[c][t] - val))
									self.logValue("n-deviation-realized-squared." + c, pow(abs(self.realized[c][t] - val), 2))

								self.logValue("n-costs.c." + c, val * self.prices[c].readValue(time).real)
							except:
								pass
				except:
					pass





	# Start and end-functions for system/sim startup and shutdown
	def startup(self):
		assert (self.enabled is True)
		# Disconnected group controllers are not officially supported, only some code is in place.
		# Disconnection / reconnection and synchronization upon these events must still be implemented!

		# Establish Controller <-> groupController connection
		if self.parent is not None:
			if not isinstance(self.parent, str):
				self.parent.appendChild(self)
			else:
				self.zCall(self.parent, 'appendChild', self.name)
			self.parentConnected = True

		# Preparing steering signals
		else:  # No parent, thus rootnode = fleet controller:
			self.isFleetController = True
			self.parentConnected = False
		if self.desired is None:
			self.desired = {}
			for c in self.commodities:
				self.desired[c] = FuncReader(timeOffset=self.host.timeOffset)  	# Setting the desired profile

		if (self.prices == None):
			self.prices = {}
			for c in self.commodities:
				self.prices[c] = FuncReader(timeOffset=self.host.timeOffset) 	# Set the market prices

		if self.localDesired is None:
			self.localDesired = {}
			for c in self.commodities:
				self.localDesired[c] = FuncReader(timeOffset=self.host.timeOffset)  # Set an optional local desired profile for local objectives

		# Optionally, align plans with a market based on a clearing moment timestamp
		if self.alignNextPlan is None:
			self.alignNextPlan = 0
		else:
			self.alignNextPlan = self.alignNextPlan % (self.planInterval * self.timeBase)

		OptCtrl.startup(self)

	def shutdown(self):
		pass






	def initiatePlanning(self, lock=False):
		if not lock:
			self.lockSyncPlanning.acquire()

			if self.zCall(self.host, 'time') < self.nextPlan:
				# Planning already being performed
				self.lockSyncPlanning.release()
				return

		s = PSData()
		s.copyFrom(self)
		s.time = self.host.time() - (self.host.time() % self.timeBase)
		s.timeBase = self.timeBase

		# Stimuli:
		desired = {}
		for c in self.commodities:
			desired[c] = self.desired[c].readValues(s.time, s.time + s.planHorizon * s.timeBase, timeBase=s.timeBase)
		prices = {}
		for c in self.commodities:
			prices[c] = self.prices[c].readValues(s.time, s.time + s.planHorizon * s.timeBase, timeBase=s.timeBase)

		s.desired = copy.deepcopy(desired)
		s.prices = copy.deepcopy(prices)

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

	#### PROFILE STEERING ALGORITHM
	# Initial planning to obtain the total power profile for the horizon
	def doInitialPlanning(self, signal, parents=[]):
		# Initializing vars
		self.allowDiscomfort = False
		time = signal.time
		result = {}
		self.planningWinners = []
		parents = copy.deepcopy(parents)
		parents.append(self.name)

		# Preparing the dictionaries
		for c in signal.commodities:
			if c not in self.plan:
				self.plan[c] = {}

		# Resetting the intermediate vectors for the new planning
		self.candidatePlanning[self.name] = self.genZeroes(signal.planHorizon)
		for p in parents:
			self.candidatePlanning[p] = self.genZeroes(signal.planHorizon)

		s = copy.deepcopy(signal)

		# Initialization of all children by requesting theur planning
		results = self.zCall(self.children, 'doInitialPlanning', s, list(parents))

		for k, r in results.items():
			for c in self.commodityIntersection(r['profile'].keys()):
				self.candidatePlanning[self.name][c] = copy.deepcopy(list(np.array(self.candidatePlanning[self.name][c]) + np.array(r['profile'][c])))
		self.planning = copy.deepcopy(self.candidatePlanning[self.name])

		# Bookkeeping
		for p in parents:
			self.candidatePlanning[p] = copy.deepcopy(self.planning)

		# Set the timestamped plan vector. To be removed when a profile-steering datatype+function class is introduced which does so by default
		for c in self.commodities:
			for i in range(0, len(self.planning[c])):
				self.plan[c][int(time + i * self.timeBase)] = self.planning[c][i]

		# Communicate the results back according to the PS interface
		result['boundImprovement'] = 0.0
		result['improvement'] = 0.0
		result['profile'] = dict(self.candidatePlanning[self.name])

		return result

	def doPlanning(self, signal):
		# This will trigger the core Profile Steering algorithm a few times. The structure follows the ISGT EU 2020 paper ( #FIXME Unpublished yet, reference follows later)
		# We need to reset if we are planning, reset = False during initial planning to establish a feasible starting point!

		result = {}
		result['profile'] = copy.deepcopy(self.candidatePlanning[self.name])
		s = copy.deepcopy(signal)

		# FIXME congestionpoints should have the option to provide a vector of bounds instead. T211
		if self.congestionPoint is not None and not self.allowDiscomfort: # DOn't know the usage of the latter part
			for c in self.commodities:
				if not self.checkBoundViolations(c, self.candidatePlanning[self.name][c]):
					# Adapt the steering signal to steer towards a feasible solution
					for i in range(0, len(s.desired[c])):
						s.desired[c][i] = max(self.congestionPoint.getLowerLimit(c).real, min(s.desired[c][i].real, self.congestionPoint.getUpperLimit(c).real))

		# Perform a normal planning with bounds imposed when applicable
		if self.parent is None:
			self.logMsg("Executing a normal iterative planning phase.")
		result = self.iterativePlanning(s)

		if self.congestionPoint is not None and not self.strictComfort: # and not self.allowDiscomfort
			withinLimits = True
			for c in self.commodities:
				if not self.checkBoundViolations(c, self.candidatePlanning[self.name][c]):
					withinLimits = False
					# Adapt the steering signal to steer towards a feasible solution
					for i in range(0, len(s.desired[c])):
						s.desired[c][i] = max(self.congestionPoint.getLowerLimit(c).real, min(s.desired[c][i].real, self.congestionPoint.getUpperLimit(c).real))

			if not withinLimits:
				s = copy.deepcopy(signal)
				s.allowDiscomfort = True
				self.allowDiscomfort = True
				if self.parent is None:
					self.logMsg("No feasible solution proposed, performing load-shedding and curtailment.")
				result = self.iterativePlanning(s)


		# Bookkeeping of the planning
		self.lastPlannedTime = (signal.planHorizon * signal.timeBase) + signal.time
		self.nextPlan = (signal.time - (signal.time % (self.planInterval * self.timeBase))) + (self.planInterval * self.timeBase) + self.alignNextPlan
		if self.nextPlan - signal.time > (self.planInterval * self.timeBase):
			self.nextPlan -= self.planInterval * self.timeBase

		return result


	def iterativePlanning(self, signal):
		# This is the basic Profile Steering algorithm
		# Version 2.0 -> Using multiple commits to enhance performance, also configuration free (by default)

		# Setting up the variables
		result = {}
		time = signal.time
		timeBase = signal.timeBase
		signal = copy.deepcopy(signal)

		iterationPlanning = copy.deepcopy(self.candidatePlanning[self.name])

		# Preparing steering data and local variables
		participatingChildren = list(self.children)
		simultaneousCommits = 1 #len(self.children)
		if self.simultaneousCommits is not None:
			simultaneousCommits = 1 #self.simultaneousCommits

		# Setting the maximum number of iterations. Defaulting to len(self.children)
		maxIters = self.maxIters
		if maxIters is None:
			maxIters = math.ceil(math.sqrt(len(self.children))*2)

		#####################################
		#  Preparation of the local steering signal
		#####################################
		# Adjust the desired profile and local profile into the desired profile (signal) and limits
		if self.parent is not None and self.parentConnected:
			for c in self.commodities:
				signal.desired[c] = list(np.array(signal.desired[c]) + np.array(list(iterationPlanning[c])))

				# Add limits:
				if c in signal.upperLimits:
					assert (len(signal.upperLimits[c]) == signal.planHorizon)
					signal.upperLimits[c] = list(np.array(signal.upperLimits[c]) + np.array(list(iterationPlanning[c])))
				if c in signal.lowerLimits:
					assert (len(signal.lowerLimits[c]) == signal.planHorizon)
					signal.lowerLimits[c] = list(np.array(signal.lowerLimits[c]) + np.array(list(iterationPlanning[c])))

		signal = copy.deepcopy(signal)

		#####################################
		#  Iterative Profile Steering algorithm
		#####################################
		for i in range(0, maxIters):
			if self.parent == None or self.parentConnected == False:
				self.logMsg("Planning iteration: " + str(i))
				# Peform a reset on all children
				self.resetPlanning([])

			assert (simultaneousCommits > 0)

			# Adapting the local steering signal
			s = copy.deepcopy(signal)
			s.source = self.name
			s.upperLimits = copy.deepcopy(signal.upperLimits)
			s.lowerLimits = copy.deepcopy(signal.lowerLimits)

			for c in self.commodities:
				# Add in the local objective
				s.desired[c] = list(np.array(signal.desired[c]) * (1 - self.localWeight[c]) + np.array(self.localDesired[c].readValues(s.time, s.time + s.planHorizon * s.timeBase, timeBase=s.timeBase)) * (self.localWeight[c]))
				s.desired[c] = list(np.array(s.desired[c]) - np.array(iterationPlanning[c]))

				# Determining the sctricter bounds
				if self.congestionPoint is not None:
					ub = {}
					lb = {}
					if self.congestionPoint.hasLowerLimit(c):
						lb[c] = list(np.array(([self.congestionPoint.getLowerLimit(c)] * s.planHorizon)))
					if self.congestionPoint.hasUpperLimit(c):
						ub[c] = list(np.array(([self.congestionPoint.getUpperLimit(c)] * s.planHorizon)))

					if self.congestionPoint.hasLowerLimit(c):
						if c in signal.lowerLimits and len(signal.lowerLimits[c]) == signal.planHorizon:
							for j in range(0, signal.planHorizon):
								s.lowerLimits[c][j] = complex(min(ub[c][j].real, max(lb[c][j].real, signal.lowerLimits[c][j].real)), min(ub[c][j].imag, max(lb[c][j].imag, signal.lowerLimits[c][j].imag)))
						else:
							s.lowerLimits[c] = list(lb[c])

					if self.congestionPoint.hasUpperLimit(c):
						if c in signal.upperLimits and len(signal.upperLimits[c]) == signal.planHorizon:
							for j in range(0, signal.planHorizon):
								s.upperLimits[c][j] = complex(max(lb[c][j].real, min(ub[c][j].real, signal.upperLimits[c][j].real)), max(lb[c][j].imag, min(ub[c][j].imag, signal.upperLimits[c][j].imag)))
						else:
							s.upperLimits[c] = list(ub[c])




				# Determining the steering signals that should be sent to the children.
				if simultaneousCommits > 0:
					for j in range(0, len(s.desired[c])):
						s.desired[c][j] = (s.desired[c][j] / simultaneousCommits)

					if c in s.upperLimits and len(s.upperLimits[c]) == s.planHorizon:
						for j in range(0, len(s.upperLimits[c])):
							s.upperLimits[c][j] = (s.upperLimits[c][j].real / simultaneousCommits) - (iterationPlanning[c][j] / simultaneousCommits)

					if c in s.lowerLimits and len(s.lowerLimits[c]) == s.planHorizon:
						for j in range(0, len(s.lowerLimits[c])):
							s.lowerLimits[c][j] = (s.lowerLimits[c][j].real / simultaneousCommits) - (iterationPlanning[c][j] / simultaneousCommits)

			improvements = {}
			boundImprovements = {}
			winners = []
			bestImprovement = 0.0


			#####################################
			#  Sending the signals and selecting the iteration winners
			#####################################
			# Ask all children to perform a planning
			looping = True

			while looping:
				#looping = False
				bestImprovement = 0.0

				for vBuffer in participatingChildren:
					self.zCall(vBuffer, "resetIteration", self.name)
					val = self.zCall(vBuffer, 'doPlanning', s)
					improvement = val['improvement']


					# Select the children (winners) with the highest contribution
					# FIXME ADD THIS PART AGAIN
					# if signal.allowDiscomfort:
					# 	for child, val in results.items():
					# 		boundImprovements[child] = val['boundImprovement']
					# 	sortedBoundImprovements = OrderedDict(sorted(boundImprovements.items(), key=lambda k: k[1], reverse=True))
					#
					# 	for child, improvement in sortedBoundImprovements.items():
					# 		if len(winners) < simultaneousCommits and winners.count(child) == 0:
					# 			if improvement > 0.0 or i == 0:
					# 				winners.append(child)
					# 				if self.planningWinners.count(child) == 0:
					# 					self.planningWinners.append(child)
					#
					# 				if improvement > bestImprovement:
					# 					bestImprovement = improvement
					#
					# 				# Perform bookkeeping and updating profiles
					# 				childData = self.zCall(child, 'setIterationWinner', self.name, None)
					# 				for c in self.commodityIntersection(childData['profile'].keys()):
					# 					iterationPlanning[c] = list(np.array(iterationPlanning[c]) + np.array(childData['profile'][c]))
					#
					# 				# Finalize the planning when we are the root controller
					# 				if self.parent is None or self.parentConnected == False:
					# 					self.zCall(child, 'setPlanningWinner', time, timeBase, self.name, [])

					# Select the children (winners) with the highest contribution
					if improvement > 0.0 or i == 0:
						winners.append(vBuffer)
						if self.planningWinners.count(vBuffer) == 0:
							self.planningWinners.append(vBuffer)

						if improvement > bestImprovement:
							bestImprovement = improvement

						# Perform bookkeeping and updating profiles
						childData = self.zCall(vBuffer, 'setIterationWinner', self.name, None)
						for c in self.commodityIntersection(childData['profile'].keys()):
							iterationPlanning[c] = list(np.array(iterationPlanning[c]) + np.array(childData['profile'][c]))

						# Finalize the planning when we are the root controller
						if self.parent is None or self.parentConnected == False:
							self.zCall(vBuffer, 'setPlanningWinner', time, timeBase, self.name, [])


					# Change desired profile
					for c in self.commodities:
					# Add in the local objective
						s.desired[c] = list(np.array(signal.desired[c]) * (1 - self.localWeight[c]) + np.array(self.localDesired[c].readValues(s.time, s.time + s.planHorizon * s.timeBase, timeBase=s.timeBase)) * (self.localWeight[c]))
						s.desired[c] = list(np.array(s.desired[c]) - np.array(iterationPlanning[c]))

					# Determining the sctricter bounds
					if self.congestionPoint is not None:
						ub = {}
						lb = {}
						if self.congestionPoint.hasLowerLimit(c):
							lb[c] = list(np.array(([self.congestionPoint.getLowerLimit(c)] * s.planHorizon)))
						if self.congestionPoint.hasUpperLimit(c):
							ub[c] = list(np.array(([self.congestionPoint.getUpperLimit(c)] * s.planHorizon)))

						if self.congestionPoint.hasLowerLimit(c):
							if c in signal.lowerLimits and len(signal.lowerLimits[c]) == signal.planHorizon:
								for j in range(0, signal.planHorizon):
									s.lowerLimits[c][j] = complex(min(ub[c][j].real, max(lb[c][j].real, signal.lowerLimits[c][j].real)), min(ub[c][j].imag, max(lb[c][j].imag, signal.lowerLimits[c][j].imag)))
							else:
								s.lowerLimits[c] = list(lb[c])

						if self.congestionPoint.hasUpperLimit(c):
							if c in signal.upperLimits and len(signal.upperLimits[c]) == signal.planHorizon:
								for j in range(0, signal.planHorizon):
									s.upperLimits[c][j] = complex(max(lb[c][j].real, min(ub[c][j].real, signal.upperLimits[c][j].real)), max(lb[c][j].imag, min(ub[c][j].imag, signal.upperLimits[c][j].imag)))
							else:
								s.upperLimits[c] = list(ub[c])



				if bestImprovement <= 0.00001:
					looping = False




			# self.zCall(participatingChildren, "resetIteration", self.name)
			# results = self.zCall(participatingChildren, 'doPlanning', s)
			#
			# # Sort the contribution of all devices
			# for child, val in results.items():
			# 	improvements[child] = val['improvement']
			# sortedImprovements = OrderedDict(sorted(improvements.items(), key=lambda k: k[1], reverse=True))
			#
			# # Select the children (winners) with the highest contribution
			# if signal.allowDiscomfort:
			# 	for child, val in results.items():
			# 		boundImprovements[child] = val['boundImprovement']
			# 	sortedBoundImprovements = OrderedDict(sorted(boundImprovements.items(), key=lambda k: k[1], reverse=True))
			#
			# 	for child, improvement in sortedBoundImprovements.items():
			# 		if len(winners) < simultaneousCommits and winners.count(child) == 0:
			# 			if improvement > 0.0 or i == 0:
			# 				winners.append(child)
			# 				if self.planningWinners.count(child) == 0:
			# 					self.planningWinners.append(child)
			#
			# 				if improvement > bestImprovement:
			# 					bestImprovement = improvement
			#
			# 				# Perform bookkeeping and updating profiles
			# 				childData = self.zCall(child, 'setIterationWinner', self.name, None)
			# 				for c in self.commodityIntersection(childData['profile'].keys()):
			# 					iterationPlanning[c] = list(np.array(iterationPlanning[c]) + np.array(childData['profile'][c]))
			#
			# 				# Finalize the planning when we are the root controller
			# 				if self.parent is None or self.parentConnected == False:
			# 					self.zCall(child, 'setPlanningWinner', time, timeBase, self.name, [])
			#
			# # Select the children (winners) with the highest contribution
			# for child, improvement in sortedImprovements.items():
			# 	if len(winners) < simultaneousCommits and winners.count(child) == 0:
			# 		if improvement > 0.0 or i == 0:
			# 			winners.append(child)
			# 			if self.planningWinners.count(child) == 0:
			# 				self.planningWinners.append(child)
			#
			# 			if improvement > bestImprovement:
			# 				bestImprovement = improvement
			#
			# 			# Perform bookkeeping and updating profiles
			# 			childData = self.zCall(child, 'setIterationWinner', self.name, None)
			# 			for c in self.commodityIntersection(childData['profile'].keys()):
			# 				iterationPlanning[c] = list(np.array(iterationPlanning[c]) + np.array(childData['profile'][c]))
			#
			# 			# Finalize the planning when we are the root controller
			# 			if self.parent is None or self.parentConnected == False:
			# 				self.zCall(child, 'setPlanningWinner', time, timeBase, self.name, [])

			#####################################
			#  Stopping conditions
			#####################################
			improvementThreshold = (self.minImprovement * len(participatingChildren)) / math.sqrt(float(simultaneousCommits))

			if bestImprovement < improvementThreshold:
				if simultaneousCommits <= 1:
					break
				else:
					simultaneousCommits = 1
			else:
				# Update the number of simultaneous commits for the next iteration
				simultaneousCommits = max(1, int(simultaneousCommits / self.multipleCommitsDivisor))


		#####################################
		#  Finalizing and returning results
		#####################################
		boundImprovement = 0.0
		improvement = self.calculateImprovement(signal.desired, self.candidatePlanning[self.name], iterationPlanning)
		if signal.allowDiscomfort:
			boundImprovement = self.calculateBoundImprovement(self.candidatePlanning[self.name], iterationPlanning, signal.upperLimits, signal.lowerLimits, norm=2)
			improvement = max(improvement, boundImprovement)

			if improvement < 0.0 or boundImprovement < 0.0:
				improvement = 0.0

		# Returning the result
		self.candidatePlanning[self.name] = copy.deepcopy(iterationPlanning)
		result['boundImprovement'] = boundImprovement
		result['improvement'] = improvement
		result['profile'] = dict(iterationPlanning)

		return result



	# Trigger a new planning
	def doReplanning(self):
		if self.parent is None or self.parentConnected == False:
			self.initiatePlanning(True)  # We already acquired the lock
		else:
			self.zCall(self.parent, 'doReplanning')











	#### EVENT BASED PROFILE STEERING
	def sendIncentive(self):
		s = PSData()
		s.copyFrom(self)
		self.lockPlanning.acquire()

		# Selecting hte timeframe
		intervals = int((self.lastPlannedTime - (self.host.time() - (self.host.time() % self.timeBase))) / self.timeBase)
		startTime = int(self.lastPlannedTime - (self.host.time() % self.timeBase))
		s.planHorizon = intervals

		# build the desired profile
		desiredPlan = {}
		prices = {}

		time = (self.host.time() - (self.host.time() % self.timeBase))
		for c in self.commodities:
			# Preparing the vectors to be sent to the child
			desiredPlan[c] = []
			prices[c] = self.prices[c].readValues(time, time + intervals * self.timeBase, timeBase=self.timeBase)

			if self.congestionPoint is not None:
				if self.congestionPoint.hasUpperLimit(c):
					s.upperLimits[c] = []
				if self.congestionPoint.hasLowerLimit(c):
					s.lowerLimits[c] = []

			# Now fill the vectors with the steering signal and the limits
			# FIXME: HAVE ANOTHER LOOK AT THE TRY-EXCEPT STATEMENTS. THEY SHOULD NOT BE REQUIRED
			for i in range(0, intervals):
				try:
					desiredPlan[c].append(complex(0, 0))
					time = (self.host.time() - (self.host.time() % self.timeBase)) + i * self.timeBase
					desiredPlan[c][i] = (self.plan[c][time] - self.realized[c][time])

					try:
						# Add limits:
						if self.congestionPoint is not None:
							if self.congestionPoint.hasUpperLimit(c):
								s.upperLimits[c].append(complex(self.congestionPoint.getUpperLimit(c).real - self.realized[c][time].real, self.congestionPoint.getUpperLimit(c).imag - self.realized[c][time].imag))
							if self.congestionPoint.hasLowerLimit(c):
								s.lowerLimits[c].append(complex(self.congestionPoint.getLowerLimit(c).real - self.realized[c][time].real, self.congestionPoint.getLowerLimit(c).imag - self.realized[c][time].imag))

							# Make sure that the steering signal obeys the bounds
							if desiredPlan[c][i].real > s.upperLimits[c][i].real or desiredPlan[c][i].real < s.lowerLimits[c][i].real:
								desiredPlan[c][i] = (s.lowerLimits[c][i].real + s.upperLimits[c][i].real) / 2.0
					except:
						pass
				except:
					# Interval probably doesn't exist (anymore)
					desiredPlan[c][i] = complex(0, 0)

			assert (len(prices[c]) == len(desiredPlan[c]))

		# Send the steering signal
		self.lockPlanning.release()
		s.desired = desiredPlan
		s.prices = prices
		s.time = int(self.host.time() - (self.host.time() % self.timeBase))
		s.originalTimestamp = self.host.time()

		return s

	def doEventCancelation(self, childData):
		# in case a device quits its job early:
		assert (False)  # NOTE: UNTESTED!!!
		self.lockPlanning.acquire()
		for c in self.commodities:
			for i in range(0, childData['realized'][c]):
				time = (self.host.time() - (self.host.time() % self.timeBase)) + i * self.timeBase
				self.realized[c][time] -= childData['realized'][c][i]
		self.lockPlanning.release()

	def requestCancelation(self, childData):
		assert (False)  # UNTESTED
		if self.parent == None or self.parentConnected == False:
			self.doEventCancelation(childData)
		else:
			self.zCall(self.parent, 'requestCancelation', childData)

	def requestIncentive(self, timestamp):
		# FIXME: Warning, original (v3) code had statements regarding multithreading and time (de-) synchronization
		# This probably has to do with cases where processes (on different machines) run unsynchronized, and hence time issues may arise
		# For now we do not use such functionality

		# Check whether we are the root of this tree and need to send the incentive:
		if (self.parent == None or self.parentConnected == False):
			if self.host.time() >= self.nextPlan and self.lockSyncPlanning.acquire(blocking=False):
				self.doReplanning()
				self.lockSyncPlanning.release()

			return self.sendIncentive()

		# Otherwise, check if we are a fleet controller and should send the incentive on behalf of the root controller:
		# This is only done if the local problem is still large enough
		elif self.isFleetController:
			self.lockPlanning.acquire()
			# Check the difference between realized and agreed planning.
			# If they are too close (small diff) then we should pass the request to a higher level to see if error persist there
			intervals = int((self.lastPlannedTime - (self.host.time() - (self.host.time() % self.timeBase))) / self.timeBase)
			diff = 0
			for c in self.commodities:
				for i in range(0, intervals):
					time = (self.host.time() - (self.host.time() % self.timeBase)) + i * self.timeBase
					diff += self.weights[c] * abs(self.realized[c][time] - self.plan[c][time])
			self.lockPlanning.release()

			# The local problem (i.e. difference between planning and realization) is large enough
			# Hence, we send the current problem to the devices
			if (diff / intervals) > self.minProblem:
				return self.sendIncentive()

		# Otherwise, we have not ran into a return statement, so we should ask the higher level controller to return the incentive
		signal = self.zCall(self.parent, 'requestIncentive', timestamp)

		self.lockPlanning.acquire()
		s = copy.deepcopy(signal)

		# add in local limits if they apply
		if self.congestionPoint is not None:
			for c in signal.commodities:
				# Prepare vectors
				if self.congestionPoint.hasUpperLimit(c):
					s.upperLimits[c] = []
				if self.congestionPoint.hasLowerLimit(c):
					s.lowerLimits[c] = []

				# Fill vectors
				for i in range(0, s.planHorizon):
					time = (self.host.time() - (self.host.time() % self.timeBase)) + i * self.timeBase
					# Check the strictness of bounds and correct them if applicable
					if self.congestionPoint.hasUpperLimit(c):
						s.upperLimits[c].append(self.congestionPoint.getUpperLimit(c))
						try:
							if c in signal.upperLimits:
								# The else clause is the original (v3) code. Event based with limits must be tested!
								if self.congestionPoint.hasLowerLimit(c):
									s.upperLimits[c][i] = complex(min((self.congestionPoint.getUpperLimit(c).real - self.realized[c][time].real), max(self.congestionPoint.getLowerLimit(c).real - self.realized[c][time].real), signal.upperLimits[c][i].real),
																  min((self.congestionPoint.getUpperLimit(c).imag - self.realized[c][time].imag), max(self.congestionPoint.getLowerLimit(c).imag - self.realized[c][time].imag), signal.upperLimits[c][i].imag))
								else:
									s.upperLimits[c][i] = complex(min(signal.upperLimits[c][i].real, (self.congestionPoint.getUpperLimit(c).real - self.realized[c][time].real)),
															  	   min(signal.upperLimits[c][i].imag, (self.congestionPoint.getUpperLimit(c).imag - self.realized[c][time].imag)))
							else:
								s.upperLimits[c][i] = complex(self.congestionPoint.getUpperLimit(c).real - self.realized[c][time].real, self.congestionPoint.getUpperLimit(c).imag - self.realized[c][time].imag)
						except:
							pass

					if self.congestionPoint.hasLowerLimit(c):
						s.lowerLimits[c].append(self.congestionPoint.getLowerLimit(c))
						try:
							if c in signal.lowerLimits:
								# The else clause is the original (v3) code. Event based with limits must be tested!
								if self.congestionPoint.hasUpperLimit(c):
									s.lowerLimits[c][i] = complex(max((self.congestionPoint.getLowerLimit(c).real - self.realized[c][time].real), min((self.congestionPoint.getUpperLimit(c).real - self.realized[c][time].real), signal.lowerLimits[c][i].real)),
																  max((self.congestionPoint.getLowerLimit(c).imag - self.realized[c][time].imag), min((self.congestionPoint.getUpperLimit(c).imag - self.realized[c][time].imag), signal.lowerLimits[c][i].imag)))
								else:
									s.lowerLimits[c][i] = complex(max(signal.lowerLimits[c][i].real, (self.congestionPoint.getLowerLimit(c).real - self.realized[c][time].real)),
																   max(signal.lowerLimits[c][i].imag, (self.congestionPoint.getLowerLimit(c).imag - self.realized[c][time].imag)))
							else:
								s.lowerLimits[c][i] = complex(self.congestionPoint.getLowerLimit(c).real - self.realized[c][time].real, self.congestionPoint.getLowerLimit(c).imag - self.realized[c][time].imag)
						except:
							pass

					if s.desired[c][i].real > s.upperLimits[c][i].real:
						s.desired[c][i] = s.upperLimits[c][i]
					elif s.desired[c][i].real < s.lowerLimits[c][i].real:
						s.desired[c][i] = s.lowerLimits[c][i]

		self.lockPlanning.release()

		return s

	# Push an update of a prediction that is considered to be a realized profile (e.g.static loads adjusted based on current measurements)
	def updateRealized(self, profile):
		self.lockPlanning.acquire()

		for c in self.commodityIntersection(profile.keys()):
			for i in range(0, len(profile[c])):
				time = (self.host.time() - (self.host.time() % self.timeBase)) + i * self.timeBase
				# FIXME: Check why this try is required here. Shouldn't be required (perhaps the profiles class will resolve this)
				try:
					if i == 0:
						# Weight for time elapsed:
						w = (self.timeBase - (self.host.time() % self.timeBase)) / self.timeBase
						profile[c][i] *= w

					self.realized[c][time] += profile[c][i]

					# Write the result for real-time tracking on a grafana dasboard
					if self.forwardLogging:
						self.logValue("W-power.realized.real.c." + c, self.realized[c][time].real, time)
						if self.host.extendedLogging:
							self.logValue("W-power.realized.imag.c." + c, self.realized[c][time].imag, time)
				except:
					pass

		self.lockPlanning.release()

		if self.parent != None and self.parentConnected == True:
			self.zCall(self.parent, 'updateRealized', profile)

	# Check whether a profile does meet the bounds set by a congestionpoint
	def checkBoundViolations(self, commodity, profile):
		if self.congestionPoint is not None:
			if self.congestionPoint.hasUpperLimit(commodity):
				for cons in profile:
					if cons.real - 0.00001 > self.congestionPoint.getUpperLimit(commodity).real:
						return False

			if self.congestionPoint.hasLowerLimit(commodity):
				for cons in profile:
					if cons.real + 0.00001 < self.congestionPoint.getLowerLimit(commodity).real:
						return False

		return True