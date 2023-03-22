#!/usr/bin/python3

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


import zmq
import pickle
import sys
import time

import threading

sys.path.insert(0, '../conf')
from usrconf import demCfg

context = zmq.Context()

print("using socket ip/port or path:")
print(demCfg['network']['sockPath'])

rx = context.socket(zmq.SUB)
rx.bind("tcp://127.0.0.1:3011")
# rx.bind(demCfg['network']['sockPath']+"rsub")

tx = context.socket(zmq.PUB)
tx.bind("tcp://127.0.0.1:3010")
# tx.bind(demCfg['network']['sockPath']+"rpub")

# Subscribe on everything
rx.setsockopt(zmq.SUBSCRIBE, b'')

#List of slaves and the name of the master
slaves = []
master = ""
nodes = {}

#List of controllers
controllers = []

#Here we go!
print("Message bus is up and running")

lock = threading.RLock()
		

def h(data):
	receiver = data[0].decode()

	lock.acquire()
	
	try:
		#See if there is something we need to do with it:
		if(receiver == "bus#"):
			sender = data[1].decode()
			snd = sender+"#"
			msgid = data[2].decode()
			what = data[5].decode()
			args = pickle.loads(data[6])
			ret = pickle.loads(data[3])
			zContext = zmq.Context()
			
			#print(sender)
			
			results = zContext.socket(zmq.PUB)
			# if ret != None:
				# print(ret)
				# results.connect(ret)
				# time.sleep(0.05)


			if(what == "listOfSlaves"):
				#print("list of slaves wanted")
				#results.send(pickle.dumps([b"listOfSlaves", receiver.encode(), msgid.encode(), sender.encode(), pickle.dumps(slaves)]) )
				tx.send_multipart([snd.encode(), receiver.encode(), msgid.encode(), pickle.dumps(None), 'retval'.encode(), pickle.dumps(None), pickle.dumps(slaves)]) 

			elif(what == "heartbeat"):
				print("receiving a heartbeat")
				#results.send(pickle.dumps([b"heartbeat", receiver.encode(), msgid.encode(), sender.encode(), pickle.dumps("alive")]) )
				results.send_multipart([snd.encode(), receiver.encode(), msgid.encode(), pickle.dumps(None), 'retval'.encode(), pickle.dumps(None), pickle.dumps("alive")]) 
				nodes[sender] = int(time.time())
				print(nodes)

			elif(what == "listOfNodes"):
				#print("list of slaves wanted")
				#results.send(pickle.dumps([b"listOfNodes", receiver.encode(), msgid.encode(), sender.encode(), pickle.dumps(nodes)]) )
				tx.send_multipart([snd.encode(), receiver.encode(), msgid.encode(), pickle.dumps(None), 'retval'.encode(), pickle.dumps(None), pickle.dumps(nodes)]) 

			elif(what == "nodesAlive"):
				#print("list of slaves wanted")
				r = []
				for k,v in nodes.items():
					if v > int(time.time()) - 60:
						r.append(k)
				print(r)
				#results.send(pickle.dumps([b"nodesAlive", receiver.encode(), msgid.encode(), sender.encode(), pickle.dumps(r)]) )
				tx.send_multipart([snd.encode(), receiver.encode(), msgid.encode(), pickle.dumps(None), 'retval'.encode(), pickle.dumps(None), pickle.dumps(r)]) 

			else:
				if(what == "connectSlave"):
					print("connecting slave: "+sender)
					if not sender in slaves:
						slaves.append(sender)
					nodes[sender] = int(time.time())
					print("send")
					#results.send(pickle.dumps([what.encode(), receiver.encode(), msgid.encode(), sender.encode(), pickle.dumps(None)]) )
					tx.send_multipart([snd.encode(), receiver.encode(), msgid.encode(), pickle.dumps(None), 'retval'.encode(), pickle.dumps(None), pickle.dumps(None)]) 
					#print([snd.encode(), receiver.encode(), msgid.encode(), pickle.dumps(None), 'retval'.encode(), pickle.dumps(None), pickle.dumps(None)])
					print("done")
				elif(what == "disconnectSlave"):
					print("disconnecting slave: "+sender)
					if sender in slaves:
						slaves.remove(sender)
					#results.send(pickle.dumps([what.encode(), receiver.encode(), msgid.encode(), sender.encode(), pickle.dumps(None)]) )
					tx.send_multipart([snd.encode(), receiver.encode(), msgid.encode(), pickle.dumps(None), 'retval'.encode(), pickle.dumps(None), pickle.dumps(None)]) 
				elif(what == "connectMaster"):
					print("connecting master: "+sender)
					master = sender
					nodes[sender] = int(time.time())
					#results.send(pickle.dumps([what.encode(), receiver.encode(), msgid.encode(), sender.encode(), pickle.dumps(None)]) )
					tx.send_multipart([snd.encode(), receiver.encode(), msgid.encode(), pickle.dumps(None), 'retval'.encode(), pickle.dumps(None), pickle.dumps(None)]) 
				elif(what == "disconnectMaster"):
					print("disconnecting master: "+sender)
					master = ""
					del nodes[sender]
					#results.send(pickle.dumps([what.encode(), receiver.encode(), msgid.encode(), sender.encode(), pickle.dumps(None)]) )
					tx.send_multipart([snd.encode(), receiver.encode(), msgid.encode(), pickle.dumps(None), 'retval'.encode(), pickle.dumps(None), pickle.dumps(None)]) 
				elif(what == "connectCtrl"):
					print("connecting controller: "+args[0])
					if not args[0] in controllers:
						controllers.append(args[0])
					#results.send(pickle.dumps([what.encode(), receiver.encode(), msgid.encode(), sender.encode(), pickle.dumps(controllers)]) )
					tx.send_multipart([snd.encode(), receiver.encode(), msgid.encode(), pickle.dumps(None), 'retval'.encode(), pickle.dumps(None), pickle.dumps(controllers)]) 
				elif(what == "disconnectCtrl"):
					print("disconnecting controller: "+args[0])
					if args[0] in controllers:
						controllers.remove(args[0])
					#No ret value, this is a cast!
				elif(what == "timeoutChild"):
					print("disconnecting child: "+args[0])
					print(slaves)
					if args[0] in slaves:
						slaves.remove(args[0])
					del nodes[sender]
					print(slaves)
					
			# if ret != None:
				# time.sleep(2)
				# results.disconnect(ret)

		else:
			tx.send_multipart(data)
	except:
		print("Something went wrong..")
	
	lock.release()

# Shunt messages out to our own subscribers
while True:
	# Process all parts of the message
	try:
		data = rx.recv_multipart()
		# Uncomment the next line for debugging
		#print(data)
		
		h(data)
		
		#t = threading.Thread(target = h, args = [list(data)])
		#t.start()
		
		
	except:
		pass