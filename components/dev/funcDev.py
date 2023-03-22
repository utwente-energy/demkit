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


import random
import math

from dev.device import Device

class FuncDev(Device):
	def __init__(self, name, host):
		Device.__init__(self, name, host)
		self.devtype = "Load"

		# params
		self.functionType = "block"  # choose: block, sin, sawtooth, const, noise
		self.period = 60*60
		self.amplitude = 1000.0
		self.dutyCycle = 0.5
		self.timeOffset = 0.0
		self.powerOffset = 0.0
		
		# Compatibility to couple to uncontrollable controller
		self.filename = None
		self.filenameReactive  = None
		self.column = 0


	def timeTick(self, time, deltatime=0):
		self.prunePlan()

		self.lockState.acquire()
		cons = self.readValue(time)

		for c in self.commodities:
			self.consumption[c] = complex(cons, 0.0)
		self.lockState.release()

	def logStats(self, time):
		self.lockState.acquire()
		try:
			for c in self.commodities:
				self.logValue("W-power.real.c." + c, self.consumption[c].real)
				if self.host.extendedLogging:
					self.logValue("W-power.imag.c." + c, self.consumption[c].imag)

				if c in self.plan and len(self.plan[c]) > 0:
					self.logValue("W-power.plan.real.c."+c, self.plan[c][0][1].real)
					if self.host.extendedLogging:
						self.logValue("W-power.plan.imag.c."+c, self.plan[c][0][1].imag)
		except:
			pass
		self.lockState.release()

	def shutdown(self):
		pass

#### INTERFACING
	def getProperties(self):
		r = Device.getProperties(self) 	# Get the properties of the overall Device class, which already includes global properties

		self.lockState.acquire()
		# Populate the result dict
		r['filename'] = None
		r['filenameReactive'] = None
		r['scaling'] = 1.0

		self.lockState.release()

		return r

#### LOCAL HELPERS
# Using the LoadDev structure to support uncontrollable controllers
	def readValueLineCache(self, time, filename=None):
		return self.readValue(time, filename)

	def readValue(self, time, filename=None):
		assert(filename == None)

		cons = 0.0
		relativeTime = (time + self.timeOffset) % self.period
		switchPoint = self.dutyCycle * self.period

		if self.functionType == "block":
			if relativeTime < switchPoint:
				cons = self.powerOffset + self.amplitude
			else:
				cons = self.powerOffset

		elif self.functionType == "sin":  # ignores dutyCycle
			cons = self.powerOffset + self.amplitude * math.sin(relativeTime * 2.0*math.pi/self.period)

		elif self.functionType == "sawtooth":
			if relativeTime < switchPoint:
				cons = self.powerOffset + self.amplitude * relativeTime/switchPoint
			else:
				cons = self.powerOffset

		elif self.functionType == "const":
			cons = self.powerOffset + self.amplitude

		elif self.functionType == "noise":
			cons = self.powerOffset + ((-0.5 + random.random()) * 2 * self.amplitude)

		else:
			assert(False)  # Unknown function type

		return cons

	def readValues(self, startTime, endTime, filename=None, timeBase=None):
		if timeBase is None:
			timeBase = self.timeBase

		result = []
		time = startTime
		while time < endTime:
			result.append(self.readValue(time, None))
			time += timeBase

		return result