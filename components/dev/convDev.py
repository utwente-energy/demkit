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

# FIXME: For now, this device is a dummy to test basic functionality for optimization ofy hybrid systems using Profile Steering

class ConvDev(Device):
	def __init__(self,  name,  host):
		Device.__init__(self,  name,  host)
		
		self.devtype = "Converter"
		
		self.commodities = ['ELECTRICITY', 'HEAT']
		# FIXME: We do not support multiple commodities on both sides yet
		self.commoditiesIn = ['ELECTRICITY']
		self.commoditiesOut = ['HEAT']
		self.cop = {'HEAT': -4}

		self.powers = [0, 4000] # Note, negative options

		# persistence
		if self.persistence != None:
			# self.watchlist += ["consumption", "plan"]
			self.persistence.setWatchlist(self.watchlist)

	def startup(self):
		assert(len(self.commoditiesIn) == 1) 	# For now we support only one input
		assert(len(self.powers) == 2) 	# For now we only support a continuous range

		Device.startup(self)


	def preTick(self, time, deltatime=0):
		# self.lockState.acquire()
		# self.prunePlan()
		#
		# for c in self.commodities:
		# 	if c in self.plan and len(self.plan[c]) > 0:
		# 		self.consumption[c] = self.plan[c][0][1].real
		# 	else:
		# 		self.consumption[c] = complex(0.0, 0.0)
		#
		# self.lockState.release()
		pass

	def timeTick(self, time, deltatime=0):
		self.lockState.acquire()
		self.prunePlan()

		for c in self.commodities:
			if self.smartOperation and c in self.plan and len(self.plan[c]) > 0:
				self.consumption[c] = self.plan[c][0][1].real
			else:
				self.consumption[c] = complex(0.0, 0.0)

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
		self.lockState.release()

#### INTERFACING
	def getProperties(self):
		r = Device.getProperties(self) 	# Get the properties of the overall Device class, which already includes global properties

		self.lockState.acquire()
		# Populate the result dict
		r['cop'] = self.cop
		r['powers'] = self.powers
		r['commoditiesIn'] = self.commoditiesIn
		r['commoditiesOut'] = self.commoditiesOut
		self.lockState.release()

		return r
