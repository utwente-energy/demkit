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

import util.helpers

class WindowPredictor():
	def __init__(self, timeBase = 60, timeWindow = 604800):
		#params
		self.timeWindow = timeWindow
		self.timeBase = timeBase

		assert(timeWindow % timeBase == 0) # Ensure alignement

		# What historical samples to take?
		self.weights = {-604800*60 	: 0.75,  \
						-86400*60 	: 0.25}

		self.historyFactor = 0.5 # How much to keep of the previous sample

		self.data = [None] * int(timeWindow / timeBase)
		self.confidence = [None] * int(timeWindow / timeBase)
		self.deviation = [None] * int(timeWindow / timeBase)
		
		self.lastSample = -1

	# Add a single measurement sample to the predictor
	def addSample(self, sample, time):
		if sample != None and time >= self.lastSample + self.timeBase:
			t = time - (time % self.timeBase) #Ensure alignment
			self.lastSample = t
			
			index = int((t % self.timeWindow) / self.timeBase)
			# Determine the confidence based on historical statistics
			if self.data[index] != None and self.data[index].real > 0:
				if self.confidence[index] == None and self.data[index] != None:
					self.confidence[index] = max(0, 1 - abs( abs(sample.real - self.data[index].real) / self.data[index].real ))
				elif self.confidence[index] != None:
					self.confidence[index] = self.confidence[index] * self.historyFactor.real + max(0, (1 - abs( abs( sample.real -self.data[index].real ) / self.data[index].real) ) ) * (1-self.historyFactor)

			# Determine the deviation (how much the sample deviates from the predicted value)
			if self.deviation[index] == None and self.data[index] != None:
				self.deviation[index] = sample.real - self.data[index].real
			elif self.deviation[index] != None:
				self.deviation[index] = self.deviation[index] * self.historyFactor.real + ( (sample.real - self.data[index].real) * (1-self.historyFactor) )

			# Now add the sample
			if self.data[index] == None:
				self.data[index] = sample
			else:
				self.data[index] = self.data[index] * self.historyFactor + sample * (1-self.historyFactor)



	def addSamples(self, samples, startTime, timeBase):
		if timeBase != self.timeBase:
			# Align timebases
			s =  util.helpers.interpolatetb(samples, timeBase, self.timeBase)
		else:
			s = list(samples)

		# now add all samples one by one
		time = startTime
		for sample in s:
			if sample != None:
				self.addSample(sample, time)
			time += self.timeBase

	def predictValue(self, time, weights = None):
		t = time - (time % self.timeBase) #Ensure alignment

		if weights == None:
			weights = self.weights

		result = 0.0
		weight = 0.0
		for key, value in weights.items():
			index = int(((t + key) % self.timeWindow) / self.timeBase)
			if self.data[index] != None:
				result += self.data[index] * value
				weight += value

		if value >= 0.0001 and weight >= 0.0001:
			result = result / weight

		return result

	def predictConfidence(self, time, weights = None):
		t = time - (time % self.timeBase) #Ensure alignment

		if weights == None:
			weights = self.weights

		result = 0.0
		weight = 0.0
		for key, value in weights.items():
			index = int(((t + key) % self.timeWindow) / self.timeBase)
			if self.confidence[index] != None:
				result += self.confidence[index] * value
				weight += value

		if value >= 0.0001:
			result = result / weight

		return result

	def predictDeviation(self, time, weights = None):
		t = time - (time % self.timeBase) #Ensure alignment

		if weights == None:
			weights = self.weights

		result = 0.0
		weight = 0.0
		for key, value in weights.items():
			index = int(((t + key) % self.timeWindow) / self.timeBase)
			if self.deviation[index] != None:
				result += self.deviation[index] * value
				weight += value

		if value >= 0.0001:
			result = result / weight

		return result


	def predictValues(self, time, intervals = 1, timeBase = None):
		result = []

		if timeBase == None:
			timeBase = self.timeBase

		t = time
		for i in range(0, intervals):
			result.append(self.predictValue(t))
			t += timeBase

		return result

	def predictConfidences(self, time, intervals = 1, timeBase = None):
		result = []

		if timeBase == None:
			timeBase = self.timeBase

		t = time
		for i in range(0, intervals):
			result.append(self.predictConfidence(t))
			t += timeBase

		return result

	def predictDeviations(self, time, intervals = 1, timeBase = None):
		result = []

		if timeBase == None:
			timeBase = self.timeBase

		t = time
		for i in range(0, intervals):
			result.append(self.predictDeviation(t))
			t += timeBase

		return result
