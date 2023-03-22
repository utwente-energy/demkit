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

import copy
import math


# TimeShiftable controller
class TsCtrl(DevCtrl):
	#Make some init function that requires the host to be provided
	def __init__(self,  name,  dev,  ctrl,  host):
		DevCtrl.__init__(self,   name,  dev,  ctrl,  host)

		self.devtype = "TimeshiftableController"
		self.cachedProfile = []
		
		self.jobCache = {}
		self.jobCacheTime = -1
		
		self.nextStart = None
		self.staticDevice = False

	def doPlanning(self, signal, requireImprovement = True):
		self.lockPlanning.acquire()
		# Prepare the result dictionary
		result = {}

		profileResult = self.genZeroes(signal.planHorizon)

		# Update the device status
		self.updateDeviceProperties()

		# Take the intersection of both lists of commodities
		commodities = list(set.intersection(set(self.commodities), set(signal.commodities)))

		# Prepare the data
		s = self.preparePlanningData(signal, copy.deepcopy(self.candidatePlanning[self.name]))

		# Obtain the predicted jobs that have to be scheduled
		if self.jobCacheTime != signal.time:
			self.jobCache = self.doPrediction(signal.time-(signal.time%signal.timeBase),
											  signal.time+signal.timeBase*signal.planHorizon)
			self.jobCacheTime = signal.time
		jobs = copy.deepcopy(self.jobCache)

		# Now plan all jobs
		# NOTE profileResult is a pointer-style dictionary that is iteratively updated in the process!
		for job in jobs:
			profileResult = self.doJobPlanning(s, job[0], job[1], profileResult, self.devDataPlanning)

			# For curtailment, adjust the signal limits here for the second partial planning
			for c in commodities:
				if c in s.upperLimits:
					for i in range(0, len(s.upperLimits[c])):
						s.upperLimits[c][i] -= profileResult[c][i]
				if c in s.lowerLimits:
					for i in range(0, len(s.lowerLimits[c])):
						s.lowerLimits[c][i] -= profileResult[c][i]

		#now add the local realized profile to the result
		if self.useEventControl:
			for c in self.commodities:
				if c not in self.realized:
					self.realized[c] = {}
				for i in range(0,  signal.planHorizon):
					t = int((signal.time - (signal.time%signal.timeBase)) +i*self.timeBase)
					if t in self.realized[c]:
						profileResult[c][i] += self.realized[c][t]

		# For timeshifters, we need to check if a job is still running
		if 'profile' in self.devData: # This way we can separate between TS and BTS devices
			if len(self.cachedProfile) == 0:
				self.cachedProfile = self.zCall(self.dev, 'getProfile', self.timeBase)

			timeBaseRatio = self.timeBase/self.devData['timeBase']
			if self.devData['available'] and self.devData['jobProgress'] > 0 and self.devData['jobProgress'] < len(self.cachedProfile)*timeBaseRatio:
				for c in commodities:
					progress = int(self.devData['jobProgress']/timeBaseRatio)
					i = 0
					while progress < len(self.cachedProfile):
						profileResult[c][i] = self.cachedProfile[progress]
						i+=1
						progress+=1


		# calculate the improvement
		improvement = 0.0
		boundImprovement = 0.0
		if requireImprovement:
			improvement = self.calculateImprovement(signal.desired, copy.deepcopy(self.candidatePlanning[self.name]), profileResult)
			boundImprovement = self.calculateBoundImprovement(copy.deepcopy(self.candidatePlanning[self.name]), profileResult, signal.upperLimits, signal.lowerLimits, norm=2)

			if signal.allowDiscomfort:
				improvement = max(improvement, boundImprovement)

			if improvement < 0.0 or boundImprovement < 0.0:
				improvement = 0.0
				profileResult = copy.deepcopy(self.candidatePlanning[self.name])

		result['boundImprovement'] = boundImprovement
		result['improvement'] = max(0.0, improvement)
		result['profile'] = copy.deepcopy(profileResult)

		# Local bookkeeping
		self.candidatePlanning[self.name] = copy.deepcopy(result['profile'])
		self.lockPlanning.release()

		return result

	def doEventPlanning(self, signal):
		# Synchronize the device state:
		self.lockPlanning.acquire()
		self.updateDeviceProperties()

		profileResult = self.genZeroes(signal.planHorizon)

		# Plan this job
		job = self.devData['currentJob']
		profileResult = self.doJobPlanning(signal, job, 1.0, profileResult)

		# Find the next starttime as it may be useful for end-users :) Quite hacky code tho, should be replaced by the timestamped profile class
		t = signal.time
		timeset = False
		for p in profileResult[self.commodities[0]]:
			if p.real < 1 and not timeset:
				t += signal.timeBase
			else:
				self.nextStart = t
				timeset = True
		
		#Set the plan
		self.setPlan(copy.deepcopy(profileResult), signal.time, signal.timeBase)

		self.lockPlanning.release()

		#Send back our profile to the controller
		self.zCall(self.parent, 'updateRealized', copy.deepcopy(profileResult))

	def doJobPlanning(self, signal, job, weight, profileResult, devData=None):
		assert(len(self.commodities)==1)
		self.updateDeviceProperties()

		c = self.commodities[0]

		# Select the right section of the desired profile and limits based on the job times
		startIdx = max(0, int(math.ceil((job['startTime']-signal.time)/signal.timeBase)))
		endIdx = max(0,  int(math.floor((job['endTime']-signal.time)/signal.timeBase)))

		# Need to alter the steering signal as this is an iterative process where jobs may overlap
		# We need to take care of the result generated so far to allow for proper power limits
		# Important that we add the negative profileResult:
		s = self.preparePlanningData(signal, profileResult)

		upperLimits = []
		lowerLimits = []
		if len(s.upperLimits) > 0:
			upperLimits = s.upperLimits[c][startIdx:endIdx]
		if len(s.lowerLimits) > 0:
			lowerLimits = s.lowerLimits[c][startIdx:endIdx]

		#get and scale the profile of the TS accordingly
		if len(self.cachedProfile) == 0:
			self.cachedProfile = self.zCall(self.dev, 'getProfile', self.timeBase)

		devProfile = list(self.cachedProfile)
		devProfile[:] = [ val*weight for val in devProfile ]

		#call the algorithm
		opt = OptAlg()
		p = opt.timeShiftablePlanning(s.desired[c][startIdx:endIdx], devProfile, lowerLimits, upperLimits, s.prices[c][startIdx:endIdx], s.profileWeight)

		#now add the profile to the result vector
		for i in range(0,  len(p)):
			profileResult[c][i+startIdx] += p[i]

		return profileResult
		

	def requestCancelation(self):
		assert(False) # Unimplemented at this moment, placeholder
		# Some example code as inspiration for this function
		# result = {}
		# profile = []
		#
		# endIdx = max(0,  int(math.floor((self.devData['currentJob['endTime']-self.host.time()/self.timeBase))))
		#
		# for i in range(0, endIdx):
		# 	time = (self.host.time() - (self.host.time()%self.timeBase)) + i*self.timeBase
		# 	profile.append(self.plan[time])
		#
		# result['profile'] = list(profile)
		# self.parent.requestCancelation(self, result)


#### PREDICTION FUNCTION
	def doPrediction(self,  startTime,  endTime):
		result = []

		#first check if we need to add a running job:
		if not self.useEventControl:
			#also add the current job if it applies:
			if self.devDataPlanning['available'] and self.devDataPlanning['jobProgress'] == 0:
				j = {}
				j['startTime'] = self.host.time()
				j['endTime'] = self.devDataPlanning['currentJob']['endTime']
				d = (j,  1) #add weight
				result.append(d)

		if self.perfectPredictions:
			#Since we use predictions, we may have overlap with already scheduled (realized) jobs
			#Hence we need to change the start time if a current job is running:
			if self.devDataPlanning['available']:
				startTime = self.devDataPlanning['currentJob']['endTime']


			for job in self.devDataPlanning['jobs']:
				if(job[1]['startTime'] >= startTime and job[1]['endTime'] <= endTime):
					#Need to create a new job for the sake of time in the controller
					j = {}
					j['startTime'] = job[1]['startTime']
					j['endTime'] = job[1]['endTime']
					d = (j,  1) #add weight
					result.append(d)

				if(job[1]['startTime'] > endTime):
					break

		#real predictions
		else:
			#Since we use predictions, we may have overlap with already scheduled (realized) jobs
			#Hence we need to change the start time if a current job is running:
			if self.devDataPlanning['available']:
				startTime = self.devDataPlanning['currentJob']['endTime']

			for job in self.devDataPlanning['jobs']:
				for week in range(1,  5):
					w = 0.125
					if week == 1:
						w = 0.5
					if week == 2:
						w = 0.25

					offset = 3600*24*7*week
					if(job[1]['startTime'] >= startTime-offset and min(job[1]['endTime'], job[1]['startTime']+24*3600)  < endTime-offset):
						#Need to create a new job for the sake of time in the controller
						j = {}
						j['startTime'] = job[1]['startTime']+offset
						j['endTime'] = job[1]['endTime']+offset
						d = (j,  w)
						result.append(d)

					if(job[1]['startTime'] > endTime-offset):
						break

		return result
