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


from itertools import islice
from util.reader import Reader
import math

class FuncReader(Reader):
	def __init__(self,  dataSource=None, timeBase = 900, column = -1, timeOffset=0):
		Reader.__init__(self, timeBase, column, timeOffset)

		# params
		self.functionType = "const"  # choose: block, sin, sawtooth, const, noise
		self.period = 60*60
		self.amplitude = 0.0
		self.dutyCycle = 0.5
		self.timeOffset = timeOffset
		self.powerOffset = 0.0

	def retrieveValues(self, startTime, endTime = None, value = None, tags = None):
		result = []
		for i in range(startTime, endTime, self.timeBase):
			result.append(self.getValue(i))

		return result

	def getValue(self, time):
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

		return complex(cons, 0.0)