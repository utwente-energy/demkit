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

from usrconf import demCfg
from core.core import Core

import time
import zmq
import pickle
import threading

import time
import random

class ZCore(Core):
	def __init__(self, name, res=None):
		Core.__init__(self, name)

		#Communication channels
		global demCfg
		if 'tcp' in demCfg['network']:
			assert (res is not None)
			self.zResultAddress = demCfg['network']['tcp']['ip']+":"+str(res)
			self.zPubAddress = demCfg['network']['tcp']['ip']+":"+str(demCfg['network']['tcp']['pub'])
			self.zSubAddress = demCfg['network']['tcp']['ip']+":"+str(demCfg['network']['tcp']['sub'])

		else:
			self.zResultAddress = demCfg['network']['sockPath'] + "res/" + self.name
			self.zPubAddress = demCfg['network']['sockPath'] + "rpub"
			self.zSubAddress = demCfg['network']['sockPath'] + "rsub"

		self.zPub = None
		self.zSub = None
		self.zRes = None

		self.zSubPoller = None
		self.zResPoller = None

		self.zMsgId = 0 # msg counter
		self.zSendLock = threading.RLock()
		self.zPubLock = threading.RLock()

		self.retData = {}

		# Polling threads
		self.retThread = None
		self.hbThread = None

		self.zConnected = False
		self.connectionLock = threading.Lock()

#        Normal ZMQ message format for DEMKit function calls:
#        [0]: topic / receiver
#        [1]: sending host
#		 [2]: Message ID
#        [3]: Pull socket listening for results (empty for unidirectional casts)
#        [4]: What? (func | setvar | getvar | retval)
#        [5]: function name
#        [6]: function arguments in a list

#        Normal ZMQ message format for DEMKit return values:
#        [0]: topic                 # should be the original function call
#        [1]: sender                # crosslink with recv[1]
#		 [2]: Message ID			# Copy of recv[2]
#        [3]: Intended receiver     # crosslink with recv[0]
#        [4]: return vals object


#        Note, all objects must connect to the Host system, which will subscribe to the topic of interest
#        As a result, all names must be unique for now (can easily be adapted in the future)
#        The host itself can be reached through the hostname
#        A system wide broadcast can be send using "cast"
#        All slave hosts must connect and subscribe to master for distribution of timeticks.

	def zDecodeFunc(self, data):
		sender = data[1].decode()
		receiver = data[0].decode()[:-1]
		ret = pickle.loads(data[3])

		msgid = data[2].decode()

		func = data[5].decode()
		args = pickle.loads(data[6])

		r = self.callFunction(receiver, func, *args)

		if ret != None:
			self.zReturn(ret, func, receiver, sender, msgid, r)

	def zDecodeBroadcast(self, data):
		sender = data[1].decode()
		ret = pickle.loads(data[3])
		receiver = data[0].decode()[:-1]

		msgid = data[2].decode()

		func = data[5].decode()
		args = pickle.loads(data[6])

		r = getattr(self, func)(*args)



		if ret != None:
			self.zReturn(ret, func, receiver, sender, msgid, r)

	def zDecodeGetVar(self, data):
		sender = data[1].decode()
		receiver = data[0].decode()[:-1]
		ret = pickle.loads(data[3])

		msgid = data[2].decode()

		var = data[5].decode()

		r = self.getVar(receiver, var)
		if ret != None:
			self.zReturn(ret, var, receiver, sender, msgid, r)

	def zDecodeSetVar(self, data):
		sender = data[1].decode()
		receiver = data[0].decode()[:-1]
		ret = pickle.loads(data[3])

		msgid = data[2].decode()

		var = data[5].decode()
		val = pickle.loads(data[6])

		r = self.setVar(receiver, var, val)
		if ret != None:
			self.zReturn(ret, var, receiver, sender, msgid, r)

	def zReturn(self, ret, func, receiver, sender, msgid, r):
		#print(r)
		# zContext = zmq.Context()
		# results = zContext.socket(zmq.PUSH)
		# results.connect(ret)
		# results.send(pickle.dumps([func.encode(), receiver.encode(), msgid.encode(), sender.encode(), pickle.dumps(r)]) )
		# zContext = zmq.Context()
		# results = zContext.socket(zmq.PUB)
		# results.connect(ret)
		# # time.sleep(0.05)
		# time.sleep(random.randint(200,500)/1000.0)
		# rcv = receiver+"#"
		# results.send(pickle.dumps([func.encode(), receiver.encode(), msgid.encode(), sender.encode(), pickle.dumps(r)]))
		# time.sleep(5)
		# results.disconnect(ret)

		what = "retval"
		snd = sender+'#'
		msg = [snd.encode(), receiver.encode(), str(msgid).encode(), pickle.dumps(None), what.encode(), func.encode(), pickle.dumps(r)]

		success = False
		retries = 2
		while not success and retries > 0:
			retries -= 1
			try:
				self.zPubLock.acquire()
				self.zPub.send_multipart(msg)
				self.zPubLock.release()

				success = True

			except KeyboardInterrupt:
				exit()
			except:
				self.logWarning("Data could not be published.")
				raise Warning("Data could not be published")


	#calls are blocking and expect a return values
	def zCall(self, receivers, func, *args):
		try:
			if isinstance(receivers, list):
				return self.zCallList(receivers, func, *args)
			else:
				return self.zCallSingle(receivers, func, *args)
		except:
			raise Warning("...") # No error handling implemented yet

	#call a function on the bus and get the result(s). Requires the objects as a list!
	def zCallList(self, receivers, func, *args):
		result = {}
		msgId = -1

		#cast out the function calls locally and over the bus
		for recv in receivers:
			if isinstance(recv, str):
				#first check if it lives locally....
				e = self.entityByName(recv)
				if e != None:
					result[recv] = getattr(e, func)(*args)
				else:
					msgId = self.zSendData(recv, "func", func, pickle.dumps(args), msgId, result)

			#assuming object here!
			else:
				result[recv] = getattr(recv, func)(*args)

		if msgId != -1:
			return self.zRetCollector(msgId, len(receivers), useDict = True)
		else:
			return result

	def zCallSingle(self, recv, func, *args):
		if isinstance(recv, str):
			e = self.entityByName(recv)
			if e != None:
				return getattr(e, func)(*args)
			else:
				result = {}
				msgId = self.zSendData(recv, "func", func, pickle.dumps(args), -1, result)
				return self.zRetCollector(msgId, 1)

		#assuming object here!
		else:
			return getattr(recv, func)(*args)

	#Casts are nonblocking and do not expect a return value, they will just drop
	def zCast(self, receivers, func, *args):
		try:
			if isinstance(receivers, list):
				return self.zCastList(receivers, func, *args)
			else:
				return self.zCastSingle(receivers, func, *args)
		except:
			raise Warning("...")  # No error handling implemented yet

	#call a function on the bus and get the result(s). Requires the objects as a list!
	def zCastList(self, receivers, func, *args):
		#cast out the function calls locally and over the bus
		for recv in receivers:
			if isinstance(recv, str):
				#first check if it lives locally....
				e = self.entityByName(recv)
				if e != None:
					getattr(e, func)(*args)
				else:
					self.zSendData(recv, "func", func, pickle.dumps(args))

			#assuming object here!
			else:
				getattr(recv, func)(*args)

	def zCastSingle(self, recv, func, *args):
		if isinstance(recv, str):
			e = self.entityByName(recv)
			if e != None:
				getattr(e, func)(*args)
			else:
				self.zSendData(recv, "func", func, pickle.dumps(args))

		#assuming object here!
		else:
			getattr(recv, func)(*args)

	#Variable setting is blocking:
	def zSet(self, receivers, var, val, lock=True):
		try:
			if isinstance(receivers, list):
				return self.zSetList(receivers, var, val, lock)
			else:
				return self.zSetSingle(receivers, var, val, lock)
		except:
			raise Warning("...")  # No error handling implemented yet

	#call a function on the bus and get the result(s). Requires the objects as a list!
	def zSetList(self, receivers, var, val, lock=True):
		result = {}
		msgId = -1

		#cast out the function calls locally and over the bus
		for recv in receivers:
			if isinstance(recv, str):
				#first check if it lives locally....
				e = self.entityByName(recv)
				if e != None:
					if hasattr(e, var):
						if self.useThreads and lock:
							self.acquireLock(var, e)

						setattr(e, var, val)

						if self.useThreads and lock:
							self.releaseLock(var, e)

						result[recv] = True
					else:
						result[recv] = False
				else:
					msgId = self.zSendData(recv, "setvar", var, pickle.dumps(val), msgId, result)

			#assuming object here!
			else:
				if hasattr(recv, var):
					if self.useThreads and lock:
						self.acquireLock(var, recv)

					setattr(recv, var, val)

					if self.useThreads and lock:
						self.releaseLock(var, recv)

					result[recv] = True
				else:
					result[recv] = False

		if msgId != -1:
			return self.zRetCollector(msgId, len(receivers), useDict = True)
		else:
			return result

	def zSetSingle(self, recv, var, val, lock=True):
		if isinstance(recv, str):
			e = self.entityByName(recv)
			if e != None:
				if hasattr(e, var):
					if self.useThreads and lock:
						self.acquireLock(var, e)

					setattr(e, var, val)

					if self.useThreads and lock:
						self.releaseLock(var, e)

					return True
				else:
					return False
			else:
				result = {}
				msgId = self.zSendData(recv, "setvar", var, pickle.dumps(val), -1, result)
				return self.zRetCollector(msgId, 1)
		else:
			if hasattr(recv, var):
				if self.useThreads and lock:
					self.acquireLock(var, recv)

				setattr(recv, var, val)

				if self.useThreads and lock:
					self.releaseLock(var, recv)

				return True
			else:
				return False

	#Variable getting is blocking:
	def zGet(self, receivers, var, lock=True):
		try:
			if isinstance(receivers, list):
				return self.zGetList(receivers, var, lock)
			else:
				return self.zGetSingle(receivers, var, lock)
		except:
			raise Warning("...")  # No error handling implemented yet

	#call a function on the bus and get the result(s). Requires the objects as a list!
	def zGetList(self, receivers, var, lock=True):
		result = {}
		msgId = -1

		#cast out the function calls locally and over the bus
		for recv in receivers:
			if isinstance(recv, str):
				#first check if it lives locally....
				e = self.entityByName(recv)
				if e != None:
					if hasattr(e, var):
						if self.useThreads and lock:
							self.acquireLock(var, e)

						result[recv] = getattr(e, var)

						if self.useThreads and lock:
							self.releaseLock(var, e)
					else:
						result[recv] = None
				else:
					msgId = self.zSendData(recv, "getvar", var, pickle.dumps(None), msgId, result)

			#assuming object here!
			else:
				if hasattr(recv, var):
					if self.useThreads and lock:
						self.acquireLock(var, recv)

					result[recv] = getattr(recv, var)

					if self.useThreads and lock:
						self.releaseLock(var, recv)
				else:
					result[recv] = None

		if msgId != -1:
			return self.zRetCollector(msgId, len(receivers), useDict = True)
		else:
			return result

	def zGetSingle(self, recv, var, lock=True):
		if isinstance(recv, str):
			e = self.entityByName(recv)
			if e != None:
				if hasattr(e, var):
					if self.useThreads and lock:
						self.acquireLock(var, e)

					r = getattr(e, var)

					if self.useThreads and lock:
						self.releaseLock(var, e)

					return r
				else:
					return None
			else:
				result = {}
				msgId = self.zSendData(recv, "getvar", var, pickle.dumps(None), -1, result)
				return self.zRetCollector(msgId, 1)

		#assuming object here!
		else:
			if hasattr(recv, var):
				if self.useThreads and lock:
					self.acquireLock(var, recv)

				r = getattr(recv, var)

				if self.useThreads and lock:
					self.releaseLock(var, recv)

				return r
			else:
				return None



	def zInit(self):
		#Connecting people.
		zContext = zmq.Context()

		# Host -> Bus connection
		self.zPub = zContext.socket(zmq.PUB)
		self.zPub.connect(self.zSubAddress)

		# Host <- Bus connection
		self.zSub = zContext.socket(zmq.SUB)
		self.zSub.connect(self.zPubAddress)
		self.zSub.RCVTIMEO = 100

		# Host <- Host return values connection
		# self.zRes = zContext.socket(zmq.PULL)
		# #self.zRes.setsockopt(zmq.SNDHWM, 10000000)
		# #self.zRes.setsockopt(zmq.RCVBUF, 10000000)
		# self.zRes.bind(self.zResultAddress)

		# self.zRes = zContext.socket(zmq.SUB)
		# # self.zRes.setsockopt(zmq.SNDHWM, 10000000)
		# self.zRes.setsockopt(zmq.RCVBUF, 1024*1024)
		# self.zRes.bind(self.zResultAddress)
		# self.zRes.RCVTIMEO = 10000
		# self.zRes.setsockopt(zmq.SUBSCRIBE, b'')
		# time.sleep(0.01)

		self.zSub.setsockopt_string(zmq.SUBSCRIBE, "broadcast#")
		self.zSub.setsockopt_string(zmq.SUBSCRIBE, self.name+"#")

		self.zSubPoller = zmq.Poller()
		self.zSubPoller.register(self.zSub, zmq.POLLIN)

		self.zResPoller = zmq.Poller()
		self.zResPoller.register(self.zRes, zmq.POLLIN)

		# self.retThread = threading.Thread(target=self.zRetData, args=[])
		# self.retThread.start()

		# self.hbThread = threading.Thread(target=self.zHeartBeat, args=[])
		# self.hbThread.start()
		self.zSetConnectionState(True) #debug

		deadline = time.time() + 10 #10 seconds of time
		while not self.zGetConnectionState() and time.time() < deadline:
			time.sleep(0.01)

		time.sleep(1)

	def zSubscribe(self):
		# Subscribe to all topics
		for e in self.entities:
			self.zSub.setsockopt_string(zmq.SUBSCRIBE, e.name+"#")

		# ZMQ does not provide a function to check whether the socket is properly connected, so we introduce a small delay
		time.sleep(0.01)

	def zSendData(self, recvh, what, func, data, msgId = -1, retdict = None):
		# Acquire a unique message identifier
		if msgId == -1:
			self.zSendLock.acquire()

			# Obtain a message ID
			self.zMsgId += 1
			msgId = self.zMsgId

			# release the lock
			self.zSendLock.release()

		if msgId not in self.retData:
			# Create a dictionary entry where return values can be stored
			if retdict is not None:
				self.retData[msgId] = retdict
			else:
				# No dict given for the results, so let's set a flag indicating whether response arrived
				self.retData[msgId] = False

		# Dispatch the data to the queue, such that it will be published and return values can be read out.
		recvh = recvh + "#"
		msg = [recvh.encode(), self.name.encode(), str(msgId).encode(), pickle.dumps(self.zResultAddress), what.encode(), func.encode(), data]


		success = False
		retries = 2
		while not success and retries > 0:
			retries -= 1
			try:
				self.zPubLock.acquire()
				self.zPub.send_multipart(msg)
				self.zPubLock.release()

				success = True

			except KeyboardInterrupt:
				exit()
			except:
				self.logWarning("Data could not be published.")
				raise Warning("Data could not be published")

			if not success:
				self.logWarning("Giving up on sending data")
				raise Warning("Giving up on sending data")

		# Return the message id, such that the results can be tracked
		return msgId # The message ID is the unique identifier to track the data

	def zRetData(self):
		if True: #try:
			while True:
				if True: #try:
					sock = dict(self.zResPoller.poll(1))
					if self.zRes in sock:
						data = pickle.loads(self.zRes.recv())
						# data = pickle.loads(self.zRes.recv())
						newThread = threading.Thread(target=self.zRetHandle, args=[list(data)])
						newThread.start()

				# except:
				# 	self.logWarning("Return result could not be handled")
				# 	raise Warning('Return result could not be handled')


		# except KeyboardInterrupt:
		# 	exit()

	# def zRetHandle(self, data):
	# 	if data[3].decode() == self.name:
	# 		msgId = int(data[2].decode())
	#
	# 		if msgId in self.retData:
	# 			if self.retData[msgId] == False:
	# 				self.retData[msgId] = True
	# 			else:
	# 				client = data[1].decode()
	# 				self.retData[msgId][client] = pickle.loads(data[4])

	def zRetHandle(self, data):
		msgId = int(data[2].decode())

		if msgId in self.retData:
			if self.retData[msgId] == False:
				self.retData[msgId] = True
			else:
				client = data[1].decode()
				self.retData[msgId][client] = pickle.loads(data[6])

	def zHeartBeat(self):
		while True:# heartbeat timeout
			try:
				self.zCall('bus', 'heartbeat')
				self.zSetConnectionState(True)
				time.sleep(10)
			except:
				self.zSetConnectionState(False)

	def zGetConnectionState(self):
		r = None
		self.connectionLock.acquire()
		r = self.zConnected
		self.connectionLock.release()
		return r

	def zSetConnectionState(self, state):
		self.connectionLock.acquire()
		self.zConnected = state
		self.connectionLock.release()


	def zRetCollector(self, msgId, answers, timeout = -1, useDict = False):
		# Timeout is the number of seconds to wait
		deadline = -1
		if timeout > -1:
			deadline = time.time() + timeout

		try:
			while (time.time() < deadline or deadline == -1) and len(self.retData[msgId]) < answers:
				time.sleep(0.1)

			if time.time() >= deadline and deadline > -1:
				del self.retData[msgId]
				self.logWarning('Timeout on receiving data')
				raise Warning('Timeout on receiving data')

			# Extract the relevant result data
			if answers == 1 and not useDict:
				result = list(self.retData[msgId].values())[0]
			else:
				result = dict(self.retData[msgId])
		except KeyboardInterrupt:
			exit()

		return result


	def zHandle(self, data):
		receiver = data[0].decode()[:-1]
		sender = data[1].decode()
		what = data[4].decode()

		if sender != self.name:
			if receiver == self.name or receiver == 'broadcast':
				if what == 'retval':
					self.zRetHandle(data)

				else:
					self.zDecodeBroadcast(data)

					# Clean way of stopping all processes
					if data[4].decode() == 'shutdown':
						time.sleep(0.01)





			#otherwise, we are not interested in the host, but rather in one of its entities
			else:
				if what == 'func':
					self.zDecodeFunc(data)

				elif what == 'getvar':
					self.zDecodeGetVar(data)

				elif what == 'setvar':
					self.zDecodeSetVar(data)

				elif what == 'retval':
					self.zRetHandle(data)

				else:
					self.logWarning("Incompatible message received, command:" +str(what))

	def zPoll(self):
		try:
			while True: #self.zGetConnectionState():
				try:
					sock = dict(self.zSubPoller.poll(1))
					if self.zSub in sock:
						data = self.zSub.recv_multipart()
						#print(data)
						if threading.active_count() > self.maxThreads:
							self.logWarning("Too many threads running. Total threads: "+str(threading.active_count()))
							while threading.active_count() > self.maxThreads:
								time.sleep(0.001) # Wait a little time

						newThread = threading.Thread(target=self.zHandle, args=[list(data)])
						newThread.start()

				except KeyboardInterrupt:
					exit()
				except:
					self.logWarning("Data could not be received.")

		except KeyboardInterrupt:
			exit()

		return False
