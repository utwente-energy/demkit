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


from dev.device import Device
from data.evTypes import evTypes

import math

class BtsDev(Device):	
	def __init__(self,  name,  host):
		Device.__init__(self,  name,  host)
		self.devtype = "BufferTimeshiftable"
		
		#params
		self.capacity = 12000
		self.chargingPowers = [0.0, 1380.0, 1610.0, 1840.0, 2070.0, 2300.0, 2530.0, 2760.0, 2990.0, 3220.0, 3450.0, 3680.0]
		self.discrete = False
		self.supportDcMode = False # Support DC Charging
		self.support3pMode = False # Support 3 phase charging

		#EVSE (Charging Pole) params are normally copied on startup, but placed in these vars:
		self.evseChargingPowers = None
		self.evseDiscrete = None
		self.evseSupportDcMode = None
		self.evseSupport3pMode = None
		self.evsePreferredPhase = [self.commodities[0]]

		#state
		self.soc = self.capacity
		self.currentJobIdx = 0
		self.currentJob = {}
		self.available = False
			
		#other
		self.jobs = []

		# TouchTable tests
		self.timeTillDeadline = 0

		# persistence
		if self.persistence != None:
			self.watchlist += ["capacity", "chargingPowers", "discrete", "supportDcMode", "support3pMode", "soc", "available", "jobs", "currentJob", "currentJobIdx"]
			self.persistence.setWatchlist(self.watchlist)

	def startup(self):
		self.lockState.acquire()

		self.soc = self.capacity

		self.jobs.sort()
		#find the current job
		i = -1
		for job in self.jobs:
			if job[1]['startTime'] >= self.host.time():
				break
			else:
				i += 1
		self.currentJobIdx = i

		for i in range(0, len(self.jobs)-1):
			if self.jobs[i][1]['endTime'] >= self.jobs[i+1][1]['startTime']:
				assert(False)

		self.chargingPowers.sort()

		# Copy the settings to the EVSE part of the model
		self.evseChargingPowers = list(self.chargingPowers)
		self.evseDiscrete = self.discrete
		self.evseSupportDcMode = self.supportDcMode
		self.evseSupport3pMode = self.support3pMode

		for c in self.commodities:
			self.consumption[c] = complex(0.0, 0.0)

		self.lockState.release()

		Device.startup(self)

	def preTick(self, time, deltatime=0):
		self.lockState.acquire()
		#first update the SoC
		consumption = 0
		for c in self.commodities:
			consumption += self.consumption[c].real
			
		self.soc = max(0,  min(self.capacity,  self.soc+consumption/(3600.0/self.host.timeBase)))

		#now check if we need to update the state
		if not self.available:
			if self.currentJobIdx+1 < len(self.jobs):
				if self.jobs[self.currentJobIdx+1][1]['startTime'] <= self.host.time():
					#new job to be triggered:
					self.currentJobIdx += 1
					self.currentJob = self.jobs[self.currentJobIdx][1]
					self.setProperties(self.currentJob['evType'])
					self.soc = max(0,  self.capacity - self.currentJob['charge'])
					self.available = True

					self.timeTillDeadline = self.currentJob['endTime'] - self.currentJob['startTime']

					#new job has to start, lets request a planning for it!
					if self.smartOperation and self.controller is not None:
						self.lockState.release()
						if self.controller.parent.devtype == "vfGroupAuctionController" or self.controller.parent.devtype == "vfGroupController":
							self.controller.triggerEvent("vfJobTrigger")
						else:
							self.zCast(self.controller, 'triggerEvent', "stateUpdate")
						self.lockState.acquire()

		else:
			if self.soc >= 0.9999*self.capacity:
				self.soc = self.capacity

			#Update the time:
			self.timeTillDeadline -= self.host.timeBase
			self.currentJob['endTime'] = self.host.time() + self.timeTillDeadline

			if self.currentJob['endTime'] <= self.host.time():
				self.available = False

		self.lockState.release()

		
	def timeTick(self, time, deltatime=0):
		self.prunePlan()

		self.lockState.acquire()

		#finally update the consumption
		for c in self.commodities:
			if self.available:
				if self.smartOperation and c in self.plan and len(self.plan[c]) > 0:
					self.consumption[c] = complex(max((-self.soc)/(self.host.timeBase/3600.0),  min(self.plan[c][0][1].real,  (self.capacity-self.soc)/(self.host.timeBase/3600.0))), 0.0)
				else:
					self.consumption[c] = complex(max((-self.soc)/(self.host.timeBase/3600.0),  min(self.chargingPowers[-1],  (self.capacity-self.soc)/(self.host.timeBase/3600.0))), 0.0)
			else:
				self.consumption[c] = complex(0.0, 0.0)
			
			#add optional reactive power
			try:
				if self.smartOperation and c in self.plan and len(self.plan[c]) > 0:
					if self.consumption[c].real < self.chargingPowers[-1]:
						qmax = math.sqrt((self.chargingPowers[-1]*self.chargingPowers[-1]) - (self.consumption[c].real*self.consumption[c].real))
						self.consumption[c] += complex(0.0, max(-1*qmax, min(self.plan[c][0][1].imag, qmax)))
			except:
				pass
				# Does not work yet with negative powers (Vehicle 2 Grid)

		if self.persistence != None:
			self.persistence.save()

		self.lockState.release()
	
	def logStats(self, time):
		self.lockState.acquire()

		try:
			for c in self.commodities:
				self.logValue("W-power.real.c."+c,  self.consumption[c].real)
				if self.host.extendedLogging:
					self.logValue("W-power.imag.c."+c, self.consumption[c].imag)

				if self.smartOperation and c in self.plan and len(self.plan[c]) > 0:
					self.logValue("W-power.plan.real.c."+c, self.plan[c][0][1].real)
					if self.host.extendedLogging:
						self.logValue("W-power.plan.imag.c."+c, self.plan[c][0][1].imag)
		except:
			pass

		self.logValue("Wh-energy.soc",  self.soc)

		if self.host.extendedLogging:
			if self.available:
				self.logValue("b-available",  1)
			else:
				self.logValue("b-available",  0)
			self.logValue("n-state-job", self.currentJobIdx)

		self.lockState.release()

#### INTERFACING
	def getProperties(self):
		r = Device.getProperties(self) 	# Get the properties of the overall Device class, which already includes global properties

		self.lockState.acquire()

		# Populate the result dict
		r['available'] = self.available
		r['soc'] = self.soc
		r['capacity'] = self.capacity
		r['chargingPowers'] = self.chargingPowers
		r['discrete'] = self.discrete

		r['jobs'] = self.jobs
		r['currentJobIdx'] = self.currentJobIdx
		r['currentJob'] = self.currentJob

		self.lockState.release()
		return r


#### LOCAL HELPERS
	def addJob(self, startTime, endTime, charge, ev=None):
		self.lockState.acquire()
		errorFlag = False

		# Apply the offset upon loading jobs:
		startTime -= self.timeOffset
		endTime -= self.timeOffset

		j = {}
		assert(startTime < endTime)
		assert(charge > 0)
		
		j['startTime'] = startTime
		j['endTime'] = min(endTime,  startTime + 24*3600)
		j['charge'] = min(charge, self.capacity)
		j['chargingPowers'] = self.chargingPowers
		j['evType'] = None

		# Modify parameters if an EVType is specified
		if ev is not None and ev in evTypes:
			j['evType'] = dict(evTypes[ev])

			# Set the correct charging powers
			j['chargingPowers'] = evTypes[ev]['chargingPowers']
			if evTypes[ev]['step']:
				j['chargingPowers'] = evTypes[ev]['chargingPowersStep']
				assert (j['chargingPowers'][-1] > j['chargingPowers'][1])

			# verification
			j['charge'] = min(charge, evTypes[ev]['capacity'])
			assert (j['chargingPowers'][-1] > j['chargingPowers'][0])


		
		#some checks on validity of the input:
		#NOTE: Not checking if charging is feasible! The rest should handle this imho
		if len(self.jobs) > 0 and j['startTime'] <= self.jobs[-1][1]['endTime']:
			errorFlag = True
			self.logError("Inconsistent job specification!")
		
		job = (len(self.jobs),  dict(j))
		if not errorFlag:
			self.jobs.append(job)

		self.lockState.release()


	def setProperties(self, evType):
		if evType is not None:
			# Set the parameters according to an EVType
			self.capacity = evType['capacity']
			self.discrete = self.evseDiscrete or evType['discrete'] 	# If either can accept continuous, then discrete is definitely possible
			self.supportDcMode = self.evseSupportDcMode and evType['supportDcMode']
			self.support3pMode = self.evseSupport3pMode and evType['support3pMode']

			# FIXME: Does not yet correctly include discrete and three-phase options, open for debate whether or not we would like to keep support for this
			# FIXME: I think this is now unused, test and remove.
			self.chargingPowers = evType['chargingPowers']  # ensure that correct charging power from session is copied here
			if evType['step']:
				self.chargingPowers = evType['chargingPowersStep']

			# Now select the charging powers:
			if not self.discrete or evType['step']:
				self.chargingPowers = [max(self.evseChargingPowers[0], evType['chargingPowers'][0]), min(self.evseChargingPowers[-1], evType['chargingPowers'][-1])]
			else:
				# We use the EVSE capabilities, in range of the EV (i.e. EVSE is LEADING)
				minimum = max(self.evseChargingPowers[0], evType['chargingPowers'][0])
				maximum = min(self.evseChargingPowers[-1], evType['chargingPowers'][-1])
				self.chargingPowers = []

				if evType['discrete']:
					for power in evType['chargingPowers']:
						if power >= minimum and power <= maximum:
							self.chargingPowers.append(power)

				elif evType['step']:
					for power in evType['chargingPowersStep']:
						if power >= minimum and power <= maximum:
							self.chargingPowers.append(power)
						elif power < minimum and minimum not in self.chargingPowers:
							self.chargingPowers.append(minimum)
						elif power > maximum and maximum not in self.chargingPowers:
							self.chargingPowers.append(maximum)
				else:
					for power in self.evseChargingPowers:
						if power >= minimum and power <= maximum:
							self.chargingPowers.append(power)

			if len(self.chargingPowers) < 2 or self.chargingPowers[0] >= self.chargingPowers[-1]:
				# Error, invalid values..
				self.chargingPowers = self.evseChargingPowers
				self.logError("Charging powers incorrect between EVSE and EV")

		else:
			# No EV Type, reset to the defaults:
			self.chargingPowers = list(self.evseChargingPowers)
			self.discrete = self.evseDiscrete
			self.supportDcMode = self.evseSupportDcMode
			self.support3pMode = self.evseSupport3pMode

		self.chargingPowers.sort() # Just to be sure


# Notes to consider when "upgrading" this model and the timeshiftables for real situations, see T205
# - with the EVSE integration, it may be wise to create a specific EVdev class instead to keep the bts-class abstract
# - The controller also needs an update
# - This type of support, e.g. using different washing schemes, should also be integrated in the TS device
# - This asks for an improved structure / job system / device model type for a future version of DEMKit
