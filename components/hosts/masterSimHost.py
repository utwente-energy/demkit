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
from hosts.host import Host
import time as tm

class MasterSimHost(ZHost):
	def __init__(self, name, res = None):
		ZHost.__init__(self, name, res)

		self.enableFlowSim = False
		self.slaves = [] #List of slave hosts

		self.networkMaster = True
		self.liveOperation = True

		self.connState = False
		
	def startSimulation(self):
		self.zInit()
		self.zSubscribe()

		#startup all entities
		self.startup()
		
		#simulate time
		for t in range(0,  self.intervals):
			self.timeTick(self.currentTime)
			self.currentTime = self.currentTime + self.timeBase

		#do a soft shutdown
		self.shutdown()
	
	def startup(self):
		import threading
		newThread = threading.Thread(target=self.zPoll, args=[])
		newThread.start()

		while not self.zGetConnectionState():
			self.connState = False
			tm.sleep(10)

		if self.connState is False:
			self.zCall("bus", "connectMaster")
			self.connState = True

		if True: #try:
			print("starting")
			self.slaves = self.zCall('bus', 'listOfSlaves')
			print(self.slaves)

			Host.startup(self)

			self.zCall(self.slaves, 'startup')

		else: #except:
			print("error")
			exit()


	def shutdown(self):
		Host.shutdown(self)

		try:
			self.zCall(self.slaves, 'shutdown')
			self.zCall("bus", "disconnectMaster")
		except:
			pass

			
	def timeTick(self,  time, absolute = True):
		while not self.zGetConnectionState():
			self.connState = False
			time.sleep(10)

		if self.connState == False:
			self.zCall("bus", "connectMaster")
			self.connState = True

		try:
			self.executeCmdQueue()
			Host.timeTick(self, time, absolute)

			#Update the time in other hosts for synchronization
			self.zCall(self.slaves, 'timeTick', self.currentTime)

			#Now simulate the time
			self.requestTickets(time)
			while (len(self.tickets) > 0):
				self.announceNextTicket(time)

			self.storeStates()
			self.postTickLogging(time)
		except:
			pass