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


import util.helpers

import os
import sys
from datetime import datetime
from cyclonedds.core import Listener, WaitSet, ReadCondition, ViewState, SampleState, InstanceState, Qos, Policy
from cyclonedds.domain import DomainParticipant
from cyclonedds.topic import Topic
from cyclonedds.sub import Subscriber, DataReader
from cyclonedds.util import duration
import logging.handlers as handlers
import logging

from util.influxdbReader import InfluxDBReader

from dev.loadDev import LoadDev
from dev.device import Device

class LoadDdsDev(LoadDev):
	# FIXME: Load Device could use a slight cleanup to rely on instantiated readers in the config itself instead
	# FIXME: Readers themselves could also have a cleanup in the interface to make it easier to use
	def __init__(self,  name,  host, influx=False, reader=None):
		LoadDev.__init__(self,  name,  host)
		
		self.devtype = "Load"

		self.opendds_domain_participant = None
		self.opendds_topic = None
		self.opendds_subscriber = None
		self.opendds_reader = None

		self.reader = reader
		self.readerReactive = None
		self.influx = influx
		self.infuxTags = None

	def startup(self):
		# Subscribe to OpenDDS topics, etc
		self.opendds_domain_participant = DomainParticipant(0)
		self.opendds_topic = Topic(domain_participant, 'Smartdevice', Flyopen, qos=qos)
		self.opendds_subscriber = Subscriber(domain_participant)
		self.opendds_reader = DataReader(domain_participant, topic, listener=listener)

		self.lockState.acquire()
		if self.reader == None:
			if self.influx:
				self.reader = InfluxDBReader(self.host.db.prefix + self.type, timeBase=self.timeBase, host=self.host, database=self.host.db.database, value="W-power.real.c." + self.commodities[0])
				self.readerReactive = InfluxDBReader(self.host.db.prefix + self.type, timeBase=self.timeBase, host=self.host, database=self.host.db.database, value="W-power.imag.c." + self.commodities[0])
				if self.infuxTags is None:
					self.reader.tags = {"name": self.name}
					self.readerReactive.tags = {"name": self.name}
				else:
					self.reader.tags = self.infuxTags
					self.readerReactive.tags = self.infuxTags

		self.lockState.release()

		Device.startup(self)

		# Kickstart the thread to read out the data
		self.runInThread(self, 'rxThread')

	def preTick(self, time, deltatime=0):
		pass

	def timeTick(self, time, deltatime=0):
		self.prunePlan()


	def rxThread(self):
		for rx_data in self.opendds_reader.take_iter(timeout=duration(seconds=2)):
			# Parsing the rx dds data
			MAC_address = rx_data.smartdevice_MAC_Addr
			power = rx_data.Power

			self.logMsg("OpenDDS power: "+str(power))

			self.lockState.acquire()
			self.consumption['ELECTRICITY'] = complex(power, 0.0)
			self.lockState.release()

			# current = rx_data.Current
			# voltage = rx_data.Voltage
			# energy = rx_data.Energy
			# frequency = rx_data.Frequency
			# powerfact = rx_data.Powerfact
			# deviceId = rx_data.smartdevice_id
			# deviceName = rx_data.name

			# print("Received_DDS_data :: ", rx_data)
			# logger.info("Received_DDS_data :: {}".format(rx_data))
			# utcTime = datetime.utcnow()


#### INTERFACING
	def getProperties(self):
		r = Device.getProperties(self) 	# Get the properties of the overall Device class, which already includes global properties

		# self.lockState.acquire()
		# # Populate the result dict
		# r['filename'] = self.filename
		# r['filenameReactive'] = self.filenameReactive
		# r['scaling'] = self.scaling
		# r['column'] = self.column
		# self.lockState.release()

		return r
