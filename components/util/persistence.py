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

import pickle

import os
import copy

class Persistence():
	def __init__(self, entity, host, watchlist = None, format = "pickle", filename = None, append = None):
		self.entity = entity	# The entity to watch
		self.host = host		# The host it is attached to

		self.watchlist = watchlist		# list of variables to watch

		# Storage format
		self.format = format	# "pickle" , may add support for e.g. json in the future

		# Storage
		if filename is None:
			if append is None:
				self.filename = 'persistence/'+host.name+'/'+entity.name+'.dem'
			else:
				self.filename = 'persistence/'+host.name+'/'+entity.name+'/'+append+'.dem'
		else:
			self.filename = filename

		self.init()

	def init(self):
		try:
			os.makedirs(os.path.dirname(self.filename), exist_ok=True)
			if not os.path.exists(self.filename):
				# Write an empty shell
				data = { } # Write only the time of recording

				f = open(self.filename, 'wb')
				pickle.dump(data, f)
				f.close()
		except:
			self.host.logError("Could not find or create persistence file: "+self.filename)


	def load(self, maxAge = None):
		if self.watchlist != None:
			if os.path.exists(self.filename):
				try:
					f = open(self.filename, 'rb')
					data = pickle.load(f)
					f.close()

					# Now load the data
					# Checking the time first
					if maxAge != None and 'time' in data:
						if data['timestamp'] < self.host.time() - maxAge:
							# data is too old, return
							return False

					# now scroll through the watchlist and restore variables
					for var in self.watchlist:
						try:
							if var in data:
								setattr(self.entity, var, copy.deepcopy(data[var]) ) # Deepcopy to make sure that all data is preserved. Object references are not supported!
						except:
							self.host.logWarning("Could not restore variable: "+var)
					return True # Notify that the persistence is executed

				except:
					self.host.logWarning("Could not open persistence file: "+self.filename)
					return False

	def save(self):
		if self.watchlist != None:
			try:
				os.makedirs(os.path.dirname(self.filename), exist_ok=True)
				f = open(self.filename+'.tmp', 'wb')

				data = {}
				for var in self.watchlist:
					try:
						if hasattr(self.entity, var):
							data[var] = copy.deepcopy(getattr(self.entity, var))
						else:
							self.host.logWarning("Could not save variable: "+var)
					except:
						self.host.logWarning("Could not save variable: " + var)

				# Write data in the tmp file
				pickle.dump(data, f)
				f.close()

				# Now move (and overwrite) the old file to avoid corruption:
				os.remove(self.filename)
				os.rename(self.filename+'.tmp', self.filename)

			except:
				self.host.logWarning("Could not save persistence file: "+self.filename)
				return False

	def setWatchlist(self, watchlist):
		self.watchlist = list(watchlist)