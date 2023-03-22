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


from ctrl.optCtrl import OptCtrl
from util.funcReader import FuncReader

import copy
import numpy as np

# Device controller base
class DevCtrl(OptCtrl):
	#Make some init function that requires the host to be provided
	def __init__(self, name, dev, parent, host):
		OptCtrl.__init__(self,  name,  host)

		self.dev = dev

		self.parentConnected = False
		if parent != None:
			self.parent = parent
			self.parentConnected = True

		self.perfectPredictions = False

		#Variables storing local device data
		self.devData = None
		self.devDataUpdate = -1
		self.devDataPlanning = None

		self.staticDevice = True # True if the device is always available

		self.localDesired = None
		self.localPrices = None

		self.localWeight = { 'ELECTRICITY':0, 'EL1': 0, 'EL2': 0, 'EL3': 0, 'HEAT': 0, 'NATGAS': 0 }
		self.localProfileWeight = None



		# persistence
		if self.persistence != None:
			self.watchlist += ["devData", "devDataUpdate", "devDataPlanning"]
			self.persistence.setWatchlist(self.watchlist)

	def startup(self):
		# Establish device <-> controller connection
		if not isinstance(self.dev, str):
			self.dev.controller = self
		else:
			self.zSet(self.dev, 'controller', self.name)

		# Establish controller <-> parent connection
		if self.parent is not None:
			if not isinstance(self.parent, str):
				self.parent.appendChild(self)
			else:
				self.zCall(self.parent, 'appendChild', self.name)

		if self.localDesired is None:
			self.localDesired = {}
			for c in self.commodities:
				self.localDesired[c] = FuncReader(timeOffset = self.host.timeOffset, timeBase = self.timeBase)
				# Infor as a reference to modify this. However, do so in your private workspace!
				# self.localDesired[c].functionType = "sin"
				# self.localDesired[c].period = 12*3600
				# self.localDesired[c].amplitude = 5000
				# self.localDesired[c].dutyCycle = 0.5
				# self.localDesired[c].offset = 0

		OptCtrl.startup(self)

	def logStats(self, time):
		t = time - time%self.timeBase
		self.lockPlanning.acquire()
		try:
			for c in self.commodities:
				self.logValue("W-power.plan.real.c." + c, self.plan[c][t].real)
				if self.host.extendedLogging:
					self.logValue("W-power.plan.imag.c." + c, self.plan[c][t].imag)

				if self.useEventControl:
					self.logValue("W-power.realized.real.c." + c, self.realized[c][t].real)
					if self.host.extendedLogging:
						self.logValue("W-power.realized.imag.c." + c, self.realized[c][t].imag)
		except:
			pass

		self.lockPlanning.release()


#### PROFILE STEERING ALGORITHM
	#Planning announcements
	def startSynchronizedPlanning(self, signal):
		self.devDataPlanning = copy.deepcopy( self.updateDeviceProperties() ) # FIXME: Unused?
		OptCtrl.startSynchronizedPlanning(self, signal)

	def endSynchronizedPlanning(self, signal):
		self.lockPlanning.acquire()
		if self.useEventControl:
			# USed to create a local planning in event based control to fix differences/infeasible schedules that may have emerged in the time since the planning started
			# Get the update device state
			self.devDataPlanning = copy.deepcopy( self.updateDeviceProperties() )

			# Creating an empty steering signal, this will force the device to stick to its own planning as much as possible
			d = {}
			for c in self.commodities:
				d[c] = [complex(0.0, 0.0)] * signal.planHorizon
			signal.desired = d

			self.lockPlanning.release()
			r = self.doPlanning(signal, False)
			self.lockPlanning.acquire()

			for c in self.commodities:
				self.realized[c] = {}
				for i in range(0,  len(r['profile'][c])):
					t = int(signal.time - (signal.time%self.timeBase) + i*self.timeBase)
					self.realized[c][t] = r['profile'][c][i]

			self.planningTimestamp = self.host.time()
			if self.staticDevice:
				self.setPlan(r['profile'], signal.time, signal.timeBase)

		# perform forward logging if desired to expose the planning to a user :)
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

		self.lockPlanning.release()
		return dict(self.realized)

	#planning functions
	def doInitialPlanning(self,  signal, parents = []):
		time = signal.time
		timeBase = signal.timeBase

		self.candidatePlanning[self.name] = self.genZeroes(signal.planHorizon)
		result = copy.deepcopy(self.doPlanning(signal,  False))
		self.candidatePlanning[self.name] = copy.deepcopy(result['profile'])
				
		self.setPlanningWinner(time, timeBase, self.name, parents)
		return result
			
	def doPlanning(self,  signal,  requireImprovement = True):
		print("this function must be overridden")	
		assert(False)




#### EVENT BASED PROFILE STEERING
	def requestIncentive(self):
		if self.useEventControl:
			time = self.host.time()
			s = self.zCall(self.parent, 'requestIncentive', time)

			# FIXME: Should be removed, async processes not allowed in PS itself. This should be resolved agent-side
			# FIXME: For now we keep a placeholder and test whether we get hre
			while s.originalTimestamp < self.planningTimestamp:
				assert(False)
				time = self.host.time()
				s = self.zCall(self.parent, 'requestIncentive', time)

			self.doEventPlanning(s)
		
	def requestCancelation(self):
		print("this function must be overridden")	
		assert(False)
		
	def doEventPlanning(self, signal):
		print("this function must be overridden")	
		assert(False)

	def executeValleyFillingJob(self):
		self.parent.executeValleyFillingJob()
		
	def triggerEvent(self, event):
		#all types of events:
		if event == "stateUpdate":
			self.requestIncentive()
		elif event == "predictionUpdate":
			self.updatePrediction()
		elif event == "cancelation":
			self.requestCancelation()
		elif event == "vfJobTrigger":
			self.executeValleyFillingJob()
		else:
			#default option
			self.requestIncentive()


	def doPrediction(self,  startTime,  endTime):
		print("this function must be overridden")	
		assert(False)
		
	def setPlan(self, plan, time, timeBase):
		assert(self.lockPlanning.acquire(blocking=False) == False)

		self.realized = {}
		result = {}

		for c in self.commodities:
			devPlan = []
			
			if c not in self.realized:
				self.realized[c] = {}
			if c not in self.plan:
				self.plan[c] = {}

			for i in range(0,  len(plan[c])):
				#create the local plan for the device. 
				t = int(time - (time%timeBase) + i*timeBase) #int(time + i*timeBase)
				tup = (t, plan[c][i])
				devPlan.append(tup)
				
				#create the plan for the controller, which has to synchronize with the timebase of the controller
				if self.useEventControl:
					t = int(time - (time%timeBase) + i*timeBase)
					self.realized[c][t] = plan[c][i]

					if self.forwardLogging:
						self.logValue("W-power.realized.imag.c." + c,self.realized[c][t].real,t)
						if self.host.extendedLogging:
							self.logValue("W-power.realized.real.c." + c,self.realized[c][t].imag,t)

			devPlan.sort()		
			result[c] = list(devPlan)

		self.lastPlannedTime = (len(plan[self.commodities[0]]) * timeBase) + time

		#send this profile to the device
		self.zCall(self.dev, 'setPlan', result)

	def updateDeviceProperties(self):
		if self.devDataUpdate < self.host.time():
			self.devData = self.zCall(self.dev, 'getProperties')

		return self.devData



#### HELPER FUNCTIONS
	# Prepare an incoming signal based on local data
	def preparePlanningData(self, signal, realized = None):
		s = copy.deepcopy(signal)

		# Fill the realized dict if required
		if realized is None:
			realized = {}
			for c in self.commodities:
				realized[c] = [complex(0.0, 0.0)] * len(signal.desired[c])

		for c in self.commodityIntersection(signal.commodities):
			if len(realized[c]) < len(signal.desired[c]):
				for i in range(0, (len(signal.desired[c]) - len(realized[c]))):
					realized[c].append(complex(0.0, 0.0))

		# Add the current profile
		for c in self.commodityIntersection(signal.commodities):
			s.desired[c] = list(np.array(signal.desired[c])*(1-self.localWeight[c]) + np.array(self.localDesired[c].readValues(s.time, s.time+s.planHorizon*s.timeBase, timeBase=s.timeBase))*(self.localWeight[c]) + np.array(list(realized[c][(len(realized[c])-len(s.desired[c])):])))
			#s.desired[c] = list(np.array(signal.desired[c]) + np.array(list(realized[c][(len(realized[c])-len(s.desired[c])):]))) # FIXME: Backup if above line does not work. Remove if no issues are found

		# Add the profile steering limits
		for c in self.commodityIntersection(signal.commodities):
			if c in signal.upperLimits:
				s.upperLimits[c] = list( np.array(signal.upperLimits[c]) + np.array(list(realized[c][(len(realized[c])-len(signal.desired[c])):])))
			if c in signal.lowerLimits:
				s.lowerLimits[c] = list( np.array(signal.lowerLimits[c]) + np.array(list(realized[c][(len(realized[c])-len(signal.desired[c])):])))

		# Check prices:
		for c in self.commodityIntersection(signal.commodities):
			if len(s.prices[c]) < len(s.desired[c]):
				s.prices[c] = [0] * len(s.desired[c])

		# Adapt prices if local prices exist
		if self.localPrices is not None:
			if c in self.localPrices:
				s.prices[c] = list(np.array(s.prices[c]) + np.array(self.localPrices[c].readValues(s.time, s.time+s.planHorizon*s.timeBase, timeBase=s.timeBase)) )

		if self.localProfileWeight is not None:
			s.profileWeight = self.localProfileWeight

		# Return the transformed steering signal
		return s


##### GENERAL HELPER FUNCTIONS
	# Weave a dict multiple commodities into one vector of a single commodity
	def weaveDict(self, d, commodities):
		result = []
		try:
			for i in range(0, len(d[commodities[0]])):
				for c in commodities:
					result.append(d[c][i])
		except:
			return []

		return result

	def weaveMultiply(self, v, commodities):
		result = []
		try:
			for i in range(0, len(v)):
				for c in commodities:
					result.append(v[i] / float(len(commodities)))
		except:
			return []

		return result

	def unweaveVec(self, v, commodities):
		result = {}
		for c in commodities:
			result[c] = []

		for i in range(0, len(v)):
			c = commodities[i%(len(commodities))]
			result[c].append(v[i])

		return result
