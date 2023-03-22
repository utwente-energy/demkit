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



from hosts.zhost import ZHost
import time as tm

class AsyncSimHost(ZHost):
	def __init__(self, name): 
		ZHost.__init__(self, name)

	def startSimulation(self):
		self.zInit()

		Host.startSimulation(self)
		self.asyncStartup()

		self.zSubscribe()
		self.connState = False

		# Start the socket loop
		while True:
			while not self.zGetConnectionState():
				connState = False
				tm.sleep(10)

			if connState == False:
				self.zCall("bus", "connectSlave")
				connState = True

			self.zPoll()


	def shutdown(self):
		Host.shutdown(self)

		# Properly disconnect from the Bus
		self.zCall("bus", "disconnectSlave")

	# Trick to provide async startup
	def startup(self):
		self.restoreStates()

	def asyncStartup(self):
		ZHost.startup(self)

	# Everything runs asynchronous, based on incoming data / events from elsewhere
	# Hence, one needs (small) custom made devices that handle a lot more stuff

	def postTickLogging(self, time):
		pass

	def time(self):
		#return system time instead:
		return int(tm.time())