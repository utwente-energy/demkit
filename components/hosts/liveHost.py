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


from hosts.host import Host
import time as tm

class LiveHost(Host):
	def __init__(self, name = "host"):
		self.liveOperation = True

		Host.__init__(self, name)

		self.liveOperation = True
		self.useThreads = True
		self.tickInterval = 1  # 1/frequency for the tickrate

		# Enable persistence
		self.enablePersistence = True

		# Write logs by default
		self.writeMsg = True
		self.writeWarning = True
		self.writeError = True
		self.writeDebug = True

	def startSimulation(self):
		#startup all entities
		self.startTime = int(tm.time())
		Host.startSimulation(self)
		
		#simulate time
		old = int(tm.time())
		old = old - (old%self.timeBase)

		while True:
			now = int(tm.time())
			if now - old >= self.tickInterval:
				self.currentTime = now
				self.logMsg("Simulating at time: "+self.timeHumanReadable())

				self.timeTick(now)
				old = now
			else:
				tm.sleep(0.001)

		#do a soft shutdown
		self.shutdown()
			
	def timeTick(self,  time, absolute = True):
		self.executeCmdQueue()
		Host.timeTick(self, time, absolute)

		self.requestTickets(time)
		while (len(self.tickets) > 0):
			self.announceNextTicket(time)

		self.storeStates()
		self.postTickLogging(time, True)