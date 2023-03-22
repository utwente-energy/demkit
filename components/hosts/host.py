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


from core.core import Core
from usrconf import demCfg
from util.persistence import Persistence
import sys

import time
from datetime import datetime
import pytz
from pytz import timezone
import random

from util.serverCsvReader import ServerCsvReader

class Host(Core):
	def __init__(self, name="host"):
		# Type of simulation
		Core.__init__(self, name)

		# Time accounting, all in UTC! Use self.timezone to convert into local time
		self.timezone = demCfg['timezone']
		self.timeformat = "%d-%m-%Y %H:%M:%S %Z%z"

		self.timezonestr = 'Europe/Amsterdam'  # This is not a pytz object for Astral!
		self.latitude = 52.2215372
		self.longitude = 6.8936619

		# Setting the starttime and (default) offset for CSV files
		self.startTime = int(self.timezone.localize(datetime(2018, 1, 29)).timestamp())
		self.timeOffset = -1 * int(self.timezone.localize(datetime(2018, 1, 1)).timestamp())
			# Note that the offset will be added, so in general you want to have a negative sign, unless you have a crystal ball ;-)

		# Internal bookkeeping
		self.currentTime = 0
		self.deltatime = 0
		self.maxDeltaTime = 1000000
		self.previousTime = 0

		# Simulation settings
		self.timeBase = 60
		self.intervals = 7*1440
		self.extendedLogging = False

		self.randomSeed = 42
		self.executionTime = time.time()

		# Ticket queue
		self.tickets = []

		# Special devices
		self.localControlDevices = []

		# Persistence
		self.persistence = None
		self.watchlist = []
		self.enablePersistence = False

		# network master used to propagate ticks through the network.
		self.networkMaster = False
		self.slaves = []

		# Actions:
		self.executeControl = True
		self.executeLoadFlow = True

		# Live interactive mode
		self.pause = False

		# File servers
		self.csvServers = {}

		# Static ticket registration configuration

		# PreTick
		self.staticTicketPreTickEnvs = 10000
		self.staticTicketPreTickDevs = 11000
		self.staticTicketPreTickCtrl = 12000

		# TimeTick
		self.staticTicketTickCtrl = 20000
		self.staticTicketTickEnvs = 21000
		self.staticTicketTickDevs = 22000

		# Physical
		self.staticTicketMeasure = 30000
		self.staticTicketLoadFlow = 31000

		# Real time control
		self.staticTicketRTDevs = 100000
		self.staticTicketRTMeasure = 101000
		self.staticTicketRTLoadFlow = 102000


	def startSimulation(self):
		self.currentTime = self.startTime
		self.previousTime = self.startTime

		#inject a seed:
		random.seed(self.randomSeed)

		self.startup()

	def startup(self):
		self.currentTime = self.startTime
		self.previousTime = self.startTime

		# persistence
		if self.enablePersistence:
			self.persistence = Persistence(self, self)
			self.watchlist += ["currentTime", "previousTime"]
			self.persistence.setWatchlist(self.watchlist)

			self.restoreStates()

		self.logMsg("Starting")
		self.db.createDatabase()

		for e in self.entities:
			e.startup()

	def shutdown(self):
		self.logMsg("Shutting down")
		for e in self.entities:
			e.shutdown()

		if self.networkMaster:
			self.zCall(self.slaves, 'shutdown')

		#write data
		self.db.writeData(True)

		# Save the state
		self.storeStates()

		self.logMsg("Total execution time: "+str(time.time() - self.executionTime))
		#self.logCsvLine('stats/sim/time', self.name+";"+str(time.time() - self.executionTime) )

		# Do a hard exit
		exit()

	def timeTick(self, time, absolute = True):
		if absolute:
			self.currentTime = time
		else:
			self.currentTime += time

		self.previousTime = self.currentTime

		if (int(self.currentTime) % 3600) == 0:
			self.logMsg("Simulating: interval "+str(int((time - self.startTime)/self.timeBase))+" of "+str(self.intervals))

	# All times in UTC
	def time(self, timeBase = None):
		if timeBase is None:
			return self.currentTime
		else:
			return self.currentTime - (self.currentTime % timeBase)

	def getDeltatime(self):
		return self.deltatime

	def timems(self):
		return float(self.currentTime) # This function should provide the time with milliseconds (as float) in real applications

	def timeObject(self, time=None):
		if time is None:
			time = self.currentTime
		return datetime.fromtimestamp(time, tz=pytz.utc)

	def timeHumanReadable(self, local=True):
		if local:
			# Display local time
			return self.timeObject().astimezone(self.timezone).strftime(self.timeformat)
		else:
			# Display UTC
			return self.timeObject().astimezone(pytz.utc).strftime(self.timeformat)

	def timeInterval(self):
		if self.currentTime == self.previousTime:
			return self.timeBase

		return self.currentTime - self.previousTime





	# Ticket system to request the control
	def requestTickets(self, time):
		result = []
		self.tickets.clear()
		self.deltatime = 0

		# Inserting default tickets for objects to respond to:
		self.registerTicket(self.staticTicketPreTickEnvs )  # preTick Environment
		self.registerTicket(self.staticTicketPreTickDevs) 	# preTick Devices
		self.registerTicket(self.staticTicketPreTickCtrl)  	# preTick Control

		self.registerTicket(self.staticTicketTickCtrl)  	# timeTick Control
		self.registerTicket(self.staticTicketTickEnvs)  	# timeTick Environment
		self.registerTicket(self.staticTicketTickDevs)  	# timeTick Devices

		self.registerTicket(self.staticTicketMeasure)  		# Measure Meters
		self.registerTicket(self.staticTicketLoadFlow)  	# Execute LoadFlow

		# Local control of devices
		self.registerTicket(self.staticTicketRTDevs)  		# Online Control
		self.registerTicket(self.staticTicketRTMeasure)  	# Measure Meters
		self.registerTicket(self.staticTicketRTLoadFlow)  	# Execute LoadFlow

		# Local entities
		for e in self.entities:
			e.requestTickets(time)

		# External entities
		if self.networkMaster:
			self.zCall(self.slaves, 'requestTickets', time)

		return result


	def registerTicket(self, number):
		assert(0 <= number)
		if number > self.maxDeltaTime: # For now we only allow up to 1 million deltatimes per interval, this is equal to the higher resolution timestamp on Unix-systems
			self.logWarning("Ticket requested that will not be executed: ticker = "+str(number))
		assert(number > self.deltatime) 			# Ticket needs to be in the "future" for this time interval

		if number not in self.tickets:
			self.tickets.append(number)


	def announceNextTicket(self, time):
		# First obtain tickets from slaves
		if self.networkMaster:
			r = self.zCall(self.slaves, 'retrieveTicketList')
			for val in r.values():
				try:
					if isinstance(val, list):
						for number in val:
							self.registerTicket(number)
					else:
						self.registerTicket(val)
				except:
					pass

		# Obtain the next ticket in the queue
		self.tickets.sort()
		number = self.tickets.pop(0)

		# Announce the next ticket unless we have reached a predefined maximum
		if number <= self.maxDeltaTime:
			self.deltatime = number

			# Local entities:
			for e in self.entities:
				e.announceTicket(time, number)

			# External entities:
			if self.networkMaster:
				self.zCall(self.slaves, 'announceNextTicket', time, number)


		else:
			self.tickets.clear()




	def postTickLogging(self, time, force = False):
		if self.logDevices:
			for d in self.devices:
				d.logStats(self.currentTime)
			for e in self.environments:
				e.logStats(self.currentTime)

		# Always log meters
		for m in self.meters:
				m.logStats(self.currentTime)

		if self.logControllers:
			for c in self.controllers:
				c.logStats(self.currentTime)
		else:
			self.logControllerStats(self.currentTime)

		for f in self.flows:
			f.logStats(self.currentTime) # Overall stats for flow

			if self.logFlow:
				for node in f.nodes:
					node.logStats(self.currentTime)
				for edge in f.edges:
					edge.logStats(self.currentTime)

		if self.networkMaster:
			self.zCall(self.slaves, 'postTickLogging', time)

		# Overall stats
		self.logDeviceStats(self.currentTime)

		self.db.writeData(force)

	def logHostValue(self, measurement,  value, time=None, deltatime=None):
#         tags = {'devtype':self.devtype,  'name':self.name}
#         values = {measurement:value}
#         self.host.logValue(self.type,  tags,  values, time)
		data = "host,devtype="+self.devtype+",name="+self.name+" "+measurement+"="+str(value)
		self.host.logValuePrepared(data, time, deltatime)


	def logDeviceStats(self, time):
		totalPower = complex(0.0, 0.0)
		totalPowerC = {}
		totalSoC = 0
		power = {}
		soc = {}

		#collect all data
		for d in self.devices:
			try:
				# First check if all entries are there, otherwise, make em
				if d.devtype not in power:
					power[d.devtype] =  {}
					soc[d.devtype] = 0.0

				for c in d.commodities:
					if c not in totalPowerC:
						totalPowerC[c] = complex(0.0, 0.0)
					if c not in power[d.devtype]:
						power[d.devtype][c] = complex(0.0, 0.0)

					if hasattr(d, 'consumption'):
						#now add this device to the lists
						totalPower += d.consumption[c]
						totalPowerC[c] += d.consumption[c]
						power[d.devtype][c] += d.consumption[c]

				#now check if we are a buffer!
				if hasattr(d, 'soc'):
					totalSoC += d.soc
					soc[d.devtype] += d.soc

			except:
				pass
				# Some data may be missing, not a problem that should make the system crash

		#Push the data to the storage
		self.logValuePrepared("host,devtype=total,name="+self.name+" W-power.real="+str(totalPower.real))
		self.logValuePrepared("host,devtype=total,name="+self.name+" W-power.imag="+str(totalPower.imag))
		self.logValuePrepared("host,devtype=total,name="+self.name+" Wh-soc="+str(totalSoC))

		#now per commodity
		for k, v in totalPowerC.items():
			self.logValuePrepared("host,devtype=total,name="+self.name+" W-power.real.c."+k+"="+str(v.real))
			self.logValuePrepared("host,devtype=total,name="+self.name+" W-power.imag.c."+k+"="+str(v.imag))

		#now per devtype
		for key in power.keys():
			for k,v in power[key].items():
				self.logValuePrepared("host,devtype="+key+",name="+self.name+" W-power.real.c."+k+"="+str(v.real))
				self.logValuePrepared("host,devtype="+key+",name="+self.name+" W-power.imag.c."+k+"="+str(v.imag))

		for k,v in soc.items():
			self.logValuePrepared("host,devtype="+k+",name="+self.name+" Wh-soc="+str(v))


	def logControllerStats(self, time):
		for c in self.controllers:
			# First check if all entries are there, otherwise, make em
			if c.devtype == "groupController":
				c.logStats(time)


	def restoreStates(self):
		if self.persistence is not None:
			self.persistence.load()

		for e in self.entities:
			e.restoreState()

	def storeStates(self):
		if self.persistence is not None:
			self.persistence.save()

		for e in self.entities:
			e.storeState()

	def attachClientCsvReader(self, dataSource, timeBase, timeOffset):
		if dataSource in self.csvServers:
			server = self.csvServers[dataSource]
			assert(server.dataSource == dataSource)
			assert(server.timeBase == timeBase)
			assert(server.timeOffset == timeOffset)
			return self.csvServers[dataSource]

		# Does not exist yet
		else:
			server = ServerCsvReader(dataSource, timeBase, timeOffset, self)
			self.csvServers[dataSource] = server
			return server



