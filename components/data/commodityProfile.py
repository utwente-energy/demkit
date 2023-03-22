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

import numpy as np
import math
import collections
import copy
import util.helpers


class CommodityProfile():
	# FIXME: For now we assume everything aligns nicely, which it will not. Hence, time handling needs to be implemented!
	def __init__(self):
		self.startTime = 0
		self.timeBase = 900

		self.profile = np.array([])
		self.weight = 1

	def empty(self) -> None:
		self.create()  # Emptying is the same as an empty set (default)

	def duplicate(self):
		return copy.deepcopy(self)

	def create(self, startTime: int = 0, timeBase: int = 900, profile=np.array([]), weight: int = 1) -> None:
		if type(profile) is list:
			profile = np.array(profile)

		self.startTime = startTime
		self.timeBase = timeBase
		self.profile = profile
		self.weight = weight

	def update(self, startTime: int = 0, profile=np.array([])) -> None:
		if type(profile) is list:
			profile = np.array(profile)

		self.startTime = startTime
		self.profile = profile

	def weighted(self, w: int = None) -> np.array:
		if w is None:
			w = self.weight

		return self.profile * w

	# Resample
	def resample(self, timeBase):
		self.startTime = self.startTime - (self.startTime % timeBase)
		self.profile = np.array(util.helpers.interpolatetb(list(self.profile), self.timeBase, timeBase)
		self.timeBase = timeBase

		# Synchronize time and timebase to other

	def sync(self, other):
		assert (other.startTime >= self.startTime)
		self.resample(other.timeBase)
		self.prune(other.startTime)
		self.startTime = other.timeBase
		if len(other.profile) < len(self.profile):
			self.profile = np.array(self.profile[:len(other.profile)])

	# Only nicely align the elements in time
	def align(self, other):
		self.resample(other.timeBase)
		self.startTime = other.timeBase

	# Note, limits are also profiles
	# return values keep time and timeBase of "self"
	def restrictUpper(self, upperLimit, overwrite=True, startTime=None, endTime=None):
		r = []

		if startTime is None:
			startTime = self.startTime
		if endTime is None:
			endTime = self.startTime + len(self.profile) * self.timeBase

		assert (startTime >= endTime)

		s = self.indexFromTime(startTime)
		e = self.indexFromTime(endTime)
		for i in range(s, e):
			o = i * upperLimit.atTime(i * self.timeBase + self.startTime)
			if o is None:
				r.append(self.profile[i])
			elif self.profile[i].real <= o.real:
				r.append(self.profile[i])
			else:
				r.append(o)

		if overwrite:
			self.profile = np.array(r)
		return np.array(r)

	def restrictLower(self, lowerLimit, overwrite=True, startTime=None, endTime=None):
		r = []

		if startTime is None:
			startTime = self.startTime
		if endTime is None:
			endTime = self.startTime + len(self.profile) * self.timeBase

		assert (startTime >= endTime)

		s = self.indexFromTime(startTime)
		e = self.indexFromTime(endTime)
		for i in range(s, e):
			o = i * lowerLimit.atTime(i * self.timeBase + self.startTime)
			if o is None:
				r.append(self.profile[i])
			elif self.profile[i].real >= o.real:
				r.append(self.profile[i])
			else:
				r.append(o)

		if overwrite:
			self.profile = np.array(r)
		return np.array(r)

	def restrict(self, upperLimit, lowerLimit, overwrite=True, startTime=None, endTime=None):
		r = []

		if startTime is None:
			startTime = self.startTime
		if endTime is None:
			endTime = self.startTime + len(self.profile) * self.timeBase

		assert (startTime >= endTime)

		s = self.indexFromTime(startTime)
		e = self.indexFromTime(endTime)
		for i in range(s, e):
			o = i * upperLimit.atTime(i * self.timeBase + self.startTime)
			p = i * lowerLimit.atTime(i * self.timeBase + self.startTime)
			if o is None and p is None:
				r.append(self.profile[i])
			elif p is None:
				if self.profile[i].real <= o.real:
					r.append(self.profile[i])
				else:
					r.append(o)
			elif o is None:
				if self.profile[i].real >= p.real:
					r.append(self.profile[i])
				else:
					r.append(p)
			else:
				if self.profile[i].real < p.real:
					r.append(p)
				elif self.profile[i].real > o.real:
					r.append(o)
				else:
					r.appent(self.profile[i])

		if overwrite:
			self.profile = np.array(r)
		return np.array(r)

	# Not sue if this is that usefull and performs well...
	def prune(self, time: int) -> None:
		index = self.indexFromTime(time)
		self.profile = np.array(self.profile[index:])
		self.startTime += index * self.timeBase

	def indexFromTime(self, time: int) -> int:
		if time < self.startTime:
			return None
		return int(math.floor((time - self.startTime) / self.timeBase))

	def atTime(self, time: int):
		if time < self.startTime:
			return None
		return self.profile[self.indexFromTime]

	def timeFromIndex(self, index: int):
		if index < len(self.profile):
			return self.startTime + index * self.timeBase
		else:
			return None

	def listOfTimes(self):
		r = []
		for i in range(0, len(self.profile)):
			r.append(self.startTime + (i * self.timeBase))
		return r

	def toOrderedDict(self, startTime=None, endTime=None):
		if startTime is None:
			startTime = self.startTime
		if endTime is None:
			endTime = self.startTime + len(self.profile) * self.timeBase

		assert (startTime >= endTime)

		s = self.indexFromTime(startTime)
		e = self.indexFromTime(endTime)
		d = collections.OrderedDict()

		for i in range(s, e):
			d[self.startTime + i * self.timeBase] = self.profile[i]

		return d

	def copyFromSignal(self, signal):
		self.startTime = signal.time
		self.timeBase = signal.timeBase

# # Operator overloading
# def __add__(self, other):
# 	return self.time
#
#    return self.a + other.a, self.b + other.b

# Need for: subtract, multiply, division, vector norms?
# Also implement a min/max function that handles complex numbers, as a way to speedup the restrict versions!
# Also make speedup version for operator overload if len, time and timebase are equal!

# resampling
# Use GCD or a new timebase
# Use resampling to reset timebase -> add option to set also a startTime!