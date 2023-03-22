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

from ctrl.groupCtrl import GroupCtrl
from data.psData import PSData
from util.funcReader import FuncReader

class VirtualBufCtrl(GroupCtrl):
	def __init__(self, name, host, parent=None, congestionPoint=None, dev=None):
		GroupCtrl.__init__(self, name, host, parent=None, congestionPoint=None, dev=None)
		self.devtype = "VirtualGroupController"

		self.multipleCommitsDivisor = 1  	# Divisor to reduce the number of selected commits for each iteration
		self.simultaneousCommits = 1	# The number of simultaneous commits in the first iteration.
											# Default: None will result in len(self.children)
		# FIXME ADD PRIORITIES IN ORIGINAL GROUP CTRL?

		assert(False) # If I am correct, this one is not used and could be deleted as well

	# Start and end-functions for system/sim startup and shutdown
	def startup(self):
		GroupCtrl.startup(self)

	def preTick(self, time, deltatime=0):
		pass

	def timeTick(selfself, time):
		pass

	def logStats(self, time):
		# logging:
		GroupCtrl.logStats(self, time)

		# Call the virtual devices




	def doPlanning(self, signal):
		# FIXME, for now I left the code in to make changes for the virtual devices

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
		# FIXME, for now I left the code in to make changes for the virtual devices

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
		simultaneousCommits = len(self.children)
		if self.simultaneousCommits is not None:
			simultaneousCommits = self.simultaneousCommits

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
			self.zCall(participatingChildren, "resetIteration", self.name)
			results = self.zCall(participatingChildren, 'doPlanning', s)

			# Sort the contribution of all devices
			for child, val in results.items():
				improvements[child] = val['improvement']
			sortedImprovements = OrderedDict(sorted(improvements.items(), key=lambda k: k[1], reverse=True))

			# Select the children (winners) with the highest contribution
			if signal.allowDiscomfort:
				for child, val in results.items():
					boundImprovements[child] = val['boundImprovement']
				sortedBoundImprovements = OrderedDict(sorted(boundImprovements.items(), key=lambda k: k[1], reverse=True))

				for child, improvement in sortedBoundImprovements.items():
					if len(winners) < simultaneousCommits and winners.count(child) == 0:
						if improvement > 0.0 or i == 0:
							winners.append(child)
							if self.planningWinners.count(child) == 0:
								self.planningWinners.append(child)

							if improvement > bestImprovement:
								bestImprovement = improvement

							# Perform bookkeeping and updating profiles
							childData = self.zCall(child, 'setIterationWinner', self.name, None)
							for c in self.commodityIntersection(childData['profile'].keys()):
								iterationPlanning[c] = list(np.array(iterationPlanning[c]) + np.array(childData['profile'][c]))

							# Finalize the planning when we are the root controller
							if self.parent is None or self.parentConnected == False:
								self.zCall(child, 'setPlanningWinner', time, timeBase, self.name, [])

			# Select the children (winners) with the highest contribution
			for child, improvement in sortedImprovements.items():
				if len(winners) < simultaneousCommits and winners.count(child) == 0:
					if improvement > 0.0 or i == 0:
						winners.append(child)
						if self.planningWinners.count(child) == 0:
							self.planningWinners.append(child)

						if improvement > bestImprovement:
							bestImprovement = improvement

						# Perform bookkeeping and updating profiles
						childData = self.zCall(child, 'setIterationWinner', self.name, None)
						for c in self.commodityIntersection(childData['profile'].keys()):
							iterationPlanning[c] = list(np.array(iterationPlanning[c]) + np.array(childData['profile'][c]))

						# Finalize the planning when we are the root controller
						if self.parent is None or self.parentConnected == False:
							self.zCall(child, 'setPlanningWinner', time, timeBase, self.name, [])

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
	# FIXME Removed for now

	# FIXME add additional code