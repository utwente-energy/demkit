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



from core.zCore import ZCore
from hosts.host import Host

from usrconf import *

import time
from datetime import datetime
from pytz import timezone

from util.serverCsvReader import ServerCsvReader

class ZHost(ZCore, Host):
	def __init__(self, name="host", res = None):
		self.liveOperation = False
		ZCore.__init__(self, name, res)

		# Time accounting, all in UTC! Use self.timezone to convert into local time
		self.timezone = timezone('Europe/Amsterdam')
		self.timeformat = "%d-%m-%Y %H:%M:%S %Z%z"

		# Setting the starttime and (default) offset for CSV files
		self.startTime = int(self.timezone.localize(datetime(2018, 1, 29)).timestamp())
		self.timeOffset = -1 * int(self.timezone.localize(datetime(2018, 1, 1)).timestamp())
			# Note that the offset will be added, so in general you want to have a negative sign, unless you have a crystal ball ;-)

		# Internal bookkeeping
		self.currentTime = 0
		self.previousTime = 0

		# Simulation settings
		self.timeBase = 60
		self.intervals = 7*1440
		self.randomSeed = 42
		self.executionTime = time.time()

		# Persistence
		self.persistence = None

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