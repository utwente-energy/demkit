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


from util.persistence import Persistence

import threading

class Entity:
	def __init__(self,  name,  host):
		self.host = host
		self.name = name

		self.persistence = None

		if self.host != None:
			self.host.addEntity(self)

			# Persistent data storage for recovery on a crash in demo sites
			if self.host.enablePersistence:
				self.persistence = Persistence(self, self.host)

		self.type = "entity"

		# ticket callbacks
		self.ticketCallback = {}

		#params
		self.timeBase = 60

		# Locking
		self.locks = {}
		self.accessLock = threading.Lock()

	def preTick(self, time, deltatime=0):
		pass

	def startup(self):
		pass
		
	def shutdown(self):
		pass

	def logStats(self, time):
		pass

	def requestTickets(self, time):
		self.ticketCallback.clear()

	def registerTicket(self, number, func, register=True):
		if number not in self.ticketCallback:
			self.ticketCallback[number] = func
			if register:
				self.host.registerTicket(number)

	def announceTicket(self, time, number):
		if number in self.ticketCallback:
			func = self.ticketCallback.pop(number)
			getattr(self, func)(time, number)


	def logValue(self, measurement,  value, time=None, deltatime=None):
		tags = {'name':self.name}
		values = {measurement:value}
		self.host.logValue(self.type,  tags,  values, time, deltatime)

	def storeState(self):
		try:
			if self.persistence is not None:
				self.accessLock.acquire()
				self.persistence.save()
				self.accessLock.release()
		except:
			try:
				self.accessLock.release()
			except:
				pass
			pass

	def restoreState(self):
		try:
			if self.persistence is not None:
				self.accessLock.acquire()
				self.persistence.load()
				self.accessLock.release()
		except:
			try:
				self.accessLock.release()
			except:
				pass
			pass


	def logMsg(self, msg):
		self.host.logMsg("["+self.name+"] "+msg)

	def logWarning(self, warning):
		self.host.logWarning("["+self.name+"] "+warning)

	def logError(self, error):
		self.host.logError("["+self.name+"] "+error)

	def logDebug(self, msg):
		self.host.logDebug("["+self.name+"] "+msg)


# Threading functions
	def acquireLock(self, var, obj=None, blocking=True, timeout=None):
		return self.host.acquireLock(vam, obj, blocking, timeout)

	def releaseLock(self, var, obj=None, timeout=None):
		return self.host.releaseLock(var, obj, timeout)

	def getLock(self, var, obj=None, timeout=None):
		return self.host.getLock(var, obj, timeout)

	def acquireNamedLock(self, name, obj=None, blocking=True, timeout=None):
		return self.host.acquireNamedLock(name, obj, blocking, timeout)

	def releaseNamedLock(self, name, obj=None, timeout=None):
		return self.host.releaseNamedLock(name, obj, timeout)

	def getNamedLock(self, name, obj=None, timeout=None):
		return self.host.getNamedLock(name, obj, timeout)

	def runInThread(self, func, *args):
		return self.host.runInThread(self, func, *args)



	def zCall(self, receivers, func, *args):
		return self.host.zCall(receivers, func, *args)
		
	def zCast(self, receivers, func, *args):
		self.host.zCast(receivers, func, *args)
		
	def zSet(self, receivers, var, val):
		self.host.zSet(receivers, var, val)
		
	def zGet(self, receivers, var):
		return self.host.zGet(receivers, var)

	def zRunInThread(self, receivers, func, *args):
		return self.host.zRunInThread(receivers, func, *args)