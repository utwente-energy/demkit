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

class ClockHost(ZHost):
	def __init__(self, name): 
		ZHost.__init__(self, name)

		self.slaves = [] #List of slave hosts
		self.networkMaster = True

		self.tickInterval = 1 # 1/frequency for the tickrate
		
	def startSimulation(self):
		self.zInit()
		self.startup()

		self.logMsg("Clock is running")

		old = int(tm.time())
		while True:
			now = int(tm.time())
			if now - old >= self.tickInterval:
				self.currentTime = now
				self.timeTick(now)
				old = now
			else:
				tm.sleep(0.001)

		#do a soft shutdown
		self.shutdown()
	
	def startup(self):
		self.zCall("bus", "connectMaster")

		# retrieve list of connected slaves to the bus
		self.slaves = self.zCall('bus', 'listOfSlaves')

		Host.startup(self)

		# cast a startup to this list
		self.zCall(self.slaves, 'startup')
			
	def timeTick(self,  time, absolute = True):
		# Modify the state
		self.executeCmdQueue()
		Host.timeTick(self, time, absolute)

		# Update the time in other hosts for synchronization
		self.zCall(self.slaves, 'timeTick', self.currentTime, True)

		self.requestTickets(time)
		while (len(self.tickets) > 0):
			self.announceNextTicket(time)

		self.storeStates()
		self.postTickLogging(time)