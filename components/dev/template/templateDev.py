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
# Template to create a new device.

# Some parts are mandatory to be configured, indicated by brackets "< ... >".
# Other parts are optional, but give some ideas.
# Furthermore, some code that should be included by default is given


# Each device inherits from the Device class
from dev.device import Device

# Classname, convention to name it a SomeDeviceDev. By default inherits from the Device class
class <device_name>Dev(Device):
	def __init__(self,  name,  host):
		Device.__init__(self,  name,  host)

		# Give the device a type
		self.devtype = "<your_device_type>"

		# Provide optional parameters, an example:
		self.parameter = <default_value>

		# Some useful, inherited, parameters are:
		#	self.controller = None			# connected controller
		# 	self.host = None				# the host to which this device is connected
		#	self.commodities = ['ELECTRICITY']	# commodities to be used
		# 	self.timeBase = 60				# Length of a timeinterval for the device

		# Provide local state variables, an example:
		self.state = <default_initial_state>

		# Some useful, inherited states are:
		# 	self.consumption = {}			# current power consumption, populted by commodity and complex
		# 	self.plan = {}					# planning set by the controller

		# persistence
		if self.persistence != None:
			self.watchlist += ["consumption", "plan"]
			self.persistence.setWatchlist(self.watchlist)

	# Initialize the device when DEMKit starts
	# startup() is called before anything else
	def startup(self):
		# Perform initializations here:
		# example:
		# self.state = 0

		# Mandatory code
		for c in self.commodities:
			self.consumption[c] = complex(0.0, 0.0)




	# PreTick() is called before device controllers are invoked.
	# use this to determine the current state based on actions in the last interval.
	# Think of updating the state of charge, or load a new event.
	def preTick(self, time, deltatime=0):
		# Perform some state updates here
		# example
		if self.state > self.parameter:
			self.state = 0

		# Set the "desired" power consumption for each commodity accordingly
		for c in self.commodities:
			self.consumption[c] = complex(self.state, 0.0) # hardcoded 0.0, 0.0 consumption here


	# TimeTick() is called after control actions
	# Use this to select the final operation state for this device
	# This state may depend on the controller result, or the internal state of the device
	def timeTick(self, time, deltatime=0):
		# Mandatory, clean the planning to discard old intervals and make sure that the current action is on top
		self.prunePlan()

		# Then simulate the device behaviour, e.g. update the state based on conditions
		# This can depend on the the planning  / control action
		# An example

		# A note for the planning:
		# The planning is given in the power consumption (in W) for the device in this interval
		# The existence of a planning, and its value can be retrieved as follows:
		for c in self.commodities:
			#see if there is a planning
			if c in self.plan and len(self.plan[c]) > 0:
				planning = self.plan[c][0][1]
				# Now, planning is filled with the power consumption for this interval for commodity c (complex).
				# Lets use it:
				self.state = planning.real
			else:
				# No planning, so do something else (normal behaviour)
				self.state += 1

		# If required, update the consumption parameter
		for c in self.commodities:
			# an example:
			self.consumption[c] = complex(self.state, 0.0)


	# LogStats() is called at the end of a time interval
	# This is your chance to log data
	def logStats(self, time):
		# Default data to log is the power consumption for each commodity
		# The try-except is in place to ensure that a demonstration does not crash due to small time synchronization errors
		try:
			for c in self.commodities:
				self.logValue("W-power.real.c." + c, self.consumption[c].real)
				self.logValue("W-power.imag.c." + c, self.consumption[c].imag)
				if c in self.plan and len(self.plan[c]) > 0:
					self.logValue("W-power.plan.real.c."+c, self.plan[c][0][1].real)
					self.logValue("W-power.plan.imag.c."+c, self.plan[c][0][1].imag)
		except:
			pass


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


	# GetProperties is used by controllers to obtain the device state and properties
	# such the these can be used for control
	# Hence, the this is the interface that the device exposes for control
	def getProperties(self):
		r = Device.getProperties(self) 	# Get the properties of the overall Device class, which already includes global properties

		# Populate the result dict
		# The convention here is to use the same names as properties/variable
		# Parameters:
		# Example:
		# r['parameter'] = self.parameter

		# State:
		# Example:
		# r['state'] = self.state

		return r



	# You are free to define more local functions if you wish to keep the code clean

	# Happy coding!