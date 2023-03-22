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

import util.helpers
import math

class TsDev(Device):	
	def __init__(self,  name,  host):
		Device.__init__(self,  name,  host)
		self.devtype = "Timeshiftable"
		
		#params
		#Washing machine profile by default, minute intervals!
		self.profile = [ complex(66.229735, 77.4311402954),complex(119.35574, 409.21968),complex(162.44595, 516.545199388),complex(154.744551, 510.671236335),
						 complex(177.089979, 584.413201848),complex(150.90621, 479.851164854),complex(170.08704, 540.84231703),complex(134.23536, 460.23552),
						 complex(331.837935, 783.490514121),complex(2013.922272, 587.393996),complex(2032.267584, 592.744712),complex(2004.263808, 584.576944),
						 complex(2023.32672, 590.13696),complex(2041.49376, 595.43568),complex(2012.8128, 587.0704),complex(2040.140352, 595.040936),
						 complex(1998.124032, 582.786176),complex(2023.459776, 590.175768),complex(1995.309312, 581.965216),complex(2028.096576, 591.528168),
						 complex(1996.161024, 582.213632),complex(552.525687, 931.898925115),complex(147.718924, 487.486021715),complex(137.541888, 490.4949133),
						 complex(155.996288, 534.844416),complex(130.246299, 464.477753392),complex(168.173568, 497.908089133),complex(106.77933, 380.79103735),
						 complex(94.445568, 323.813376),complex(130.56572, 317.819806804),complex(121.9515, 211.226194059),complex(161.905679, 360.175184866),
						 complex(176.990625, 584.085324519),complex(146.33332, 501.71424),complex(173.06086, 593.35152),complex(145.07046, 517.342925379),
						 complex(188.764668, 522.114985698),complex(88.4058, 342.394191108),complex(117.010432, 346.43042482),complex(173.787341, 326.374998375),
						 complex(135.315969, 185.177207573),complex(164.55528, 413.181298415),complex(150.382568, 515.597376),complex(151.517898, 540.335452156),
						 complex(154.275128, 509.122097304),complex(142.072704, 506.652479794),complex(171.58086, 490.815333752),complex(99.13293, 368.167736052),
						 complex(94.5507, 366.193286472),complex(106.020684, 378.085592416),complex(194.79336, 356.012659157),complex(239.327564, 302.865870739),
						 complex(152.75808, 209.046388964),complex(218.58576, 486.26562702),complex(207.109793, 683.481346289),complex(169.5456, 581.2992),
						 complex(215.87571, 712.409677807),complex(186.858018, 573.073382584),complex(199.81808, 534.79864699),complex(108.676568, 403.611655607),
						 complex(99.930348, 356.366544701),complex(151.759998, 358.315027653),complex(286.652289, 300.697988258),complex(292.921008, 266.244164873),
						 complex(300.5829, 265.089200586),complex(296.20425, 261.22759426),complex(195.74251, 216.883021899),complex(100.34136, 260.038063655),
						 complex(312.36975, 275.4842252),complex(287.90921, 261.688800332),complex(85.442292, 140.349851956),complex(44.8647, 109.208529515)]
		
		self.currentJobIdx = -1
		self.currentJob = {}
		self.available = False
		self.jobProgress = 0

		# TouchTable tests
		self.timeTillDeadline = 0

		#other
		self.jobs = []

		# persistence
		if self.persistence != None:
			self.watchlist += ["jobs", "currentJobIdx", "currentJob", "available", "jobProgress"]
			self.persistence.setWatchlist(self.watchlist)

	def startup(self):
		self.jobs.sort()

		self.lockState.acquire()
		#find the current job
		i = -1
		for job in self.jobs:
			if job[1]['startTime'] >= self.host.time():
				break
			else:
				i += 1
		self.currentJobIdx = i

		for c in self.commodities:
			self.consumption[c] = complex(0.0, 0.0)

		assert(len(self.commodities)==1) #
		self.commodity = self.commodities[0]

		if self.host.timeBase != self.timeBase:
			self.profile= util.helpers.interpolatetb(self.profile, self.timeBase, self.host.timeBase)
			self.timeBase = self.host.timeBase

		self.lockState.release()

		Device.startup(self)

	def preTick(self, time, deltatime=0):
		assert(len(self.commodities)==1)

		self.lockState.acquire()

		if self.available and self.consumption[self.commodity].real > 0:
			#Power usage, so yes, we're progressing
			assert(self.host.timeBase >= self.timeBase)
			assert(self.host.timeBase % self.timeBase == 0)
			self.jobProgress += math.ceil(self.host.timeBase / self.timeBase)
			self.jobProgress = min(self.jobProgress, len(self.profile))
		
		#now check if we need to update the state
		if not self.available:
			if self.currentJobIdx+1 < len(self.jobs):
				if self.jobs[self.currentJobIdx+1][1]['startTime'] <= self.host.time():
					#new job to be triggered:
					self.currentJobIdx += 1
					self.currentJob = self.jobs[self.currentJobIdx][1]
					self.jobProgress = 0

					self.available = True

					self.timeTillDeadline = self.currentJob['endTime'] - self.currentJob['startTime']
					
					#new job has to start, lets request a planning for it!
					if self.smartOperation and self.controller is not None:
						self.lockState.release()
						self.zCast(self.controller, 'triggerEvent', "stateUpdate")
						self.lockState.acquire()
		else:
			#Update the time:
			self.timeTillDeadline -= self.host.timeBase
			self.currentJob['endTime'] = self.host.time() + self.timeTillDeadline

			if self.jobProgress == len(self.profile) or self.currentJob['endTime'] <= self.host.time():
				self.available = False

		self.lockState.release()

	def timeTick(self, time, deltatime=0):
		self.prunePlan()
		c = self.commodity

		self.lockState.acquire()
		#NOTE: Currently no preemption is supported, but a forced shutdown is!
		if self.available and self.jobProgress < len(self.profile):

			#first check if we made progress already. If so, let it run as we cannot preemt the device
			if self.jobProgress > 0 and self.jobProgress < len(self.profile):
				if self.strictComfort:
					self.consumption[self.commodity] = self.profile[self.jobProgress]
				elif self.smartOperation and c in self.plan and len(self.plan[c]) > 0:
				# We can overrule the device by hard shutting it down :)
					if self.plan[self.commodity][0][1].real >= 1 or self.strictComfort:
						self.consumption[self.commodity] = self.profile[self.jobProgress]
					else:
						# Load shedding allowed
						self.consumption[self.commodity] = complex(0.0, 0.0)
						self.jobProgress = len(self.profile)

			elif self.smartOperation and c in self.plan and len(self.plan[c]) > 0:
				# a planning is available
				if self.plan[self.commodity][0][1].real >= 1:
					self.consumption[self.commodity] = self.profile[self.jobProgress] 	#the time shifter starts running:
				else:
					self.consumption[self.commodity] = complex(0.0, 0.0)	#if no consumption is planned, and the device was not started yet, keep it turned off

			else:
				#no plan, job just started:
				assert(self.jobProgress == 0)
				self.consumption[self.commodity] = self.profile[self.jobProgress]

		else:
			self.consumption[self.commodity] = complex(0.0, 0.0)

		self.lockState.release()

	def logStats(self, time):
		self.lockState.acquire()
		try:
			for c in self.commodities:
				self.logValue("W-power.real.c." + c, self.consumption[c].real)
				if self.host.extendedLogging:
					self.logValue("W-power.imag.c." + c, self.consumption[c].imag)

				if self.smartOperation and c in self.plan and len(self.plan[c]) > 0:
					self.logValue("W-power.plan.real.c."+c, self.plan[c][0][1].real)
					if self.host.extendedLogging:
						self.logValue("W-power.plan.imag.c."+c, self.plan[c][0][1].imag)
		except:
			pass

		if self.host.extendedLogging:
			self.logValue("n-state-progress", self.jobProgress)
			self.logValue("n-state-job", self.currentJobIdx)

			if (self.available):
				self.logValue("b-available", 1)
			else:
				self.logValue("b-available", 0)

		self.lockState.release()

	def shutdown(self):
		pass

#### INTERFACING
	def getProperties(self):
		r = Device.getProperties(self) 	# Get the properties of the overall Device class, which already includes global properties

		self.lockState.acquire()
		# Populate the result dict
		r['profile'] = self.profile
		r['available'] = self.available

		r['jobs'] = self.jobs
		r['currentJobIdx'] = self.currentJobIdx
		r['currentJob'] = self.currentJob
		r['jobProgress'] = self.jobProgress
		self.lockState.release()

		return r


#### LOCAL HELPERS
	def addJob(self, startTime, endTime):
		self.lockState.acquire()
		errorFlag = False

		startTime -= self.timeOffset
		endTime -= self.timeOffset

		j = {}
		assert(startTime < endTime)
		assert(endTime >= startTime + len(self.profile)*self.timeBase)

		j['startTime'] = startTime
		j['endTime'] = min(endTime,  startTime + 24*3600)

		if len(self.jobs) > 0 and j['startTime'] <= self.jobs[-1][1]['endTime']:
			errorFlag = True
			self.logError("Inconsistent job specification!")

		job = (len(self.jobs),  dict(j))

		if not errorFlag:
			self.jobs.append(job)

		self.lockState.release()

	#Device specific helpers:
	def getProfile(self, timeBase):
		r = self.profile
		if timeBase != self.timeBase:
			r = util.helpers.interpolatetb(r, self.timeBase, timeBase)
		return r
