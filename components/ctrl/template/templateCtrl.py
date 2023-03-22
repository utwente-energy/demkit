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

# Template to create a new profile steering controller.

# Some parts are mandatory to be configured, indicated by brackets "< ... >".
# Other parts are optional, but give some ideas.
# Furthermore, some code that should be included by default is given

# Note that creating a controller for profile steering requires considerable more time to create
# Some algorithm needs to be devised to optimize the device operation based on its constraints.
# Furthermore, algorithms are still in progress, so things may change
# Therefore, this template is not as detailed as the others.

# Check Chapter 4 from Hoogsteen - A Cyber-Physical Systems Perspective on Decentralized Energy Management

import util.helpers
from ctrl.devCtrl import DevCtrl

import linecache

class <controller_name>Ctrl(DevCtrl):
	#Make some init function that requires the host to be provided
	def __init__(self,  name,  dev, ctrl,  host):
		DevCtrl.__init__(self,  name,  dev,  ctrl,  host)

		self.devtype = '<controller_name>Ctrl'
		
		# Provide optional parameters:

		# Some useful, inherited, parameters are:
		#	self.parent = parent			# connected parent controller
		#	self.dev = dev					# connected device (to be controlled)
		# 	self.host = None				# the host to which this device is connected

		#	self.commodities = ['ELECTRICITY']	# commodities to be used, Note, Auction only supports one commodity
		#	self.weights = {'ELECTRICITY': 1}

		#	self.timeBase = 900
		# 	self.minImprovement = 100

		#	#Accounting
		# 	self.planning = {}
		# 	self.candidatePlanning = {}
		# 	self.iterationPlanning = {}
		#
		# 	self.confirmed = {}
		# 	self.candidateConfirmed ={}
		# 	self.iterationConfirmed = {}
		#
		# 	self.plan = {}
		# 	self.realized = {}

		#	self.useEventControl = True
		#	self.useReactiveControl = True # True #Enable reactive power control
		#	self.perfectPredictions = False

		# Provide local state variables:

	# PreTick Issued before the timeTick. May be used to handle event in event-based control
	def preTick(self, time, deltatime=0):
		# Synchronize the device state:
        deviceState = self.updateDeviceProperties(self)

		# Handle events if required

	# TimeTick() is issued before device TimeTicks, use it to set planning actions if required, such as a replanning
	def timeTick(self, time, deltatime=0):
		pass

	def logStats(self, time):
		# If
		self.logValue("W-power.plan.imag.c."+c, self.plan[c][0][1].imag)

		# But you can easily (and anywhere) log other data, such as:
		# self.logValue("n-state", self.state)

	 	# Logging is convenient using a tag and value: logValue(<tag>, <value>)
		# Convention here for tags is: unit-quantity.more.specific
		# units used:
		#	A = 	Ampere
		# 	V = 	Volt
		# 	W = 	Watt, also for reactive (.imag vs .real). In loadflow also VA (Volt-Ampere) and var (Volt-Ampere-reactive)
		# 	Wh = 	Energy in Watt-hours
		# 	n =		Number
		# 	p = 	percentage or probability
		# 	C = 	Celsius
		# 	b = 	Binary


#### ACTUAL FUNCTIONS FOR PROFILE STEERING
	# doInitialPlanning is usually not required as the normal doPlanning can be called with zeroes.
	# The default implementation in devCtrl is usually sufficient (setting the requireImprovement to true).
	# def doInitialPlanning(self,  signal, parents = []):


	# doPlanning() is requested by the Group Controller to plan the device
	def doPlanning(self,  signal,  requireImprovement = True):
		# Synchronize the device state:
		deviceState = self.updateDeviceProperties(self)

		# Mandatory and/or useful
		# Furthermore, refer to the pyDEM2/data/PSData.py - PSData class for more info on the data that is received with signal
		result = {}
		time = signal.time
		timeBase = signal.timeBase

		# Fill an empty dict for the planning
		p = {}
		for c in signal.commodities:
			p[c] = [complex(0.0, 0.0)] * signal.planHorizon
			
		# Do sometthing here to plan the device
		# That is, create a schedule per commodity for signal.planHorizon length
		# This is an part taken from the buffer controller as an example

		profileResult = planThisDeviceDummyFunction(some, parameters, that, are required)
		# Note, a planning function may be specified locally, or instead a prediction algorithm may be run

		# Split the output
		for c in self.commodities:
			offset = 0
			for c in self.commodities:
				if commodity == c:
					for i in range(0,  int(len(p))):
						profileResult[c][i+startIdx] += p[i]
				else:
					#fill zeroes:
					for i in range(0,  int(len(p))):
						profileResult[c][i+startIdx] += complex(0.0, 0.0)

		#calculate the improvement and set results
		improvement = 0.0
		if requireImprovement:
			improvement = self.calculateImprovement(desired,  dict(self.candidatePlanning[self.name]),  profileResult)
			if(improvement > 0.0):
				self.iterationPlanning = dict(profileResult)
				self.iterationConfirmed = dict(result['realized'])
		else:
			# Required for the initial planning
			self.iterationPlanning = dict(profileResult)
			self.iterationConfirmed = dict(result['realized'])

		# Format to return the results
		result['improvement'] = improvement
		result['profile'] = dict(p) #self.iterationPlanning)
		result['realized'] = dict(p) #self.iterationPlanning)

		return result


	# doEventPlanning() is called when the device requires a replanning
	# Some useful code snippets:
	def doEventPlanning(self, signal):
		# Synchronize the device state:
		deviceState = self.updateDeviceProperties()

		profileResult = {}
		desired = {}
		time = signal.time
		timeBase = signal.timeBase

		for c in signal.commodities:
			profileResult[c] = [complex(0.0, 0.0)] * signal.planHorizon
# 			desired[c] = list(np.array(signal.desired[c]) + np.array(list(self.candidatePlanning[self.name][c])))
			desired[c] = list(signal.desired[c])

		# Set the plan
		self.setPlan(dict(profileResult), time, timeBase)

		#Send back our profile to the controller
		if not self.process:
			self.parent.updateRealized(dict(profileResult))
		else:
			self.zCall(self.parent, 'updateRealized', dict(profileResult))


	# Future planned function for an aborted planning (e.g. leaving device)
	def requestCancelation(self):
		assert(False) #unimplemented and untested

		result['profile'] = list(profile)
		if not self.process:
			self.parent.requestCancelation(result)
		else:
			self.zCall(self.parent, 'requestCancelation', result)


	# Furthermore, usually there is a planning function and a separate prediction function

	# Some useful functions defined in the inherited classes.
	# Note that these usually do not require attention

	# in DevCtrl:
	# def triggerEvent(self, event):
	# def setPlan(self, plan, time, timeBase):

	# in OptCtrl:
	# def calculateImprovement(self,  desired,  old,  new):
	# def calculateCommodityImprovement(self,  desired,  old,  new):
	# def getPlan(self, time, commodity):
	# def getOriginalPlan(self, time, commodity = None):
	# def genZeroes(self, length):




