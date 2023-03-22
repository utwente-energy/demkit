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


import requests
import time as tm
from usrconf import demCfg
import os
import sys
import threading
import copy

class InfluxDB():
	def __init__(self, host):
		self.processtime = 0
		self.host = host

		self.address = demCfg['db']['influx']['address']
		self.port = demCfg['db']['influx']['port']
		self.database = demCfg['db']['influx']['dbname']
		self.prefix = ""

		self.username = ""
		self.password = ""

		self.data = []
		self.maxBuffer = 100000

		self.storeBackup = False 	# Store data by default in a backup file
		self.restoreBackup = True	# Restore backup when connection to DB is restored
		self.autoCleanup = True 	# Cleanup text files when data is restored after a hiccup
		self.errorFlag = False
		
		self.filepath = demCfg['var']['databasebackup']+host.name+"/" # Location to store the backup

		self.useSysTime = False # Use system time instead of host time

		self.threadCountLock = threading.Lock()
		self.activeThreads = 0

		self.restoring = threading.Lock()

	def appendValue(self,  measurement, tags,  values,  time, deltatime=0):
		#create tags
		tagstr = ""
		for key,  value in tags.items():
			if not tagstr == "":
				tagstr += ","
			tagstr += key + "="+value

#		create vals
		valsstr = ""
		for key,  value in values.items():
			if not valsstr == "":
				valsstr += ","
			valsstr += key+ "="+str(value)

		# Check the time
		timestr = str(int(time * 1000000000.0) + (deltatime*1000) )
		if self.useSysTime:
			time = str(tm.time())
			timestr = time.replace('.', '')
			timestr += "000"

		s = self.prefix + measurement + ","
		s += tagstr + " "
		s += valsstr + " "
		s += timestr
		s += '\n'

		self.data.append(s)

	def appendValuePrepared(self,  data, time, deltatime=0):
		timestr = str(int(time * 1000000000.0) + (deltatime*1000) )
		if self.useSysTime:
			time = str(tm.time())
			timestr = time.replace('.', '')
			timestr += "000"
		dataToBeAdded = "%s%s %s" % (self.prefix, data, timestr)
		self.data.append(dataToBeAdded)

	def writeData(self,  force = False):
		if len(self.data) > self.maxBuffer or force:
			# Make a copy and clear

			self.threadCountLock.acquire()
			if self.activeThreads == 0: # For now we limit this to one thread for writing
				self.activeThreads += 1
				self.threadCountLock.release()

				d = copy.deepcopy(self.data)
				self.data = []

				# Write data in a thread:
				self.host.runInThread(self, 'writeDataThread', d)
			else:
				self.threadCountLock.release()


	def writeDataThread(self, data):
		success = self.writeToDatabase(data)
		if not success or self.storeBackup:
			self.writeTextFile()
			if not success:
				self.errorFlag = True

		if success:
			if self.errorFlag:
				# Connection to database is established again, lets load from the text files
				if self.restoring.acquire(blocking=False):
					self.host.runInThread(self, 'loadTextFiles') #self.loadTextFiles()

		self.threadCountLock.acquire()
		self.activeThreads -= 1
		self.threadCountLock.release()


	def writeToDatabase(self, data):
		result = True
		toSend = ("\n".join(data) + "\n")
		try:
			r = requests.post(self.address+ ':'+self.port+ '/write?db='+self.database,  auth=(self.username, self.password), data=toSend, timeout=5.0)
			if r.status_code != 204:
				self.host.logWarning("[InfluxDB] Could not write to database. Errorcode: "+str(r.status_code)+ "\t\t" + r.text)
				result = False

		except:
			self.host.logWarning("[InfluxDB] Could not connect to database, is it running?\n")
			result = False
		

		return result

	def clearDatabase(self):
		self.host.logMsg("[InfluxDB] Clearing database "+self.database)
		payload = {'q':"DROP DATABASE "+self.database}
		try:
			r = requests.post(self.address+ ':'+self.port+ '/query',  auth=(self.username, self.password), data=payload)
			if r.status_code != 200:
				self.host.logWarning("[InfluxDB] Could not drop the database. Check your InfluxDB. Errorcode: "+str(r.status_code)+ "\t\t" + r.text)
		except:
			self.host.logWarning("[InfluxDB] Could not connect to database, is it running?")
		

		self.host.logMsg("[InfluxDB] Removing backup files")
		self.cleanupTextFiles()
	
		self.host.logMsg("[InfluxDB] Creating database " + self.database)
		self.createDatabase()
		


	def createDatabase(self):
		payload = {'q': "CREATE DATABASE " + self.database}
		try:
			r = requests.post(self.address + ':' + self.port + '/query',  auth=(self.username, self.password), data=payload)
			if r.status_code != 200:
				self.host.logWarning("[InfluxDB] Could not create the database. make sure that it does not start with numbers and does not contain dashes. \nErrorcode: "+str(r.status_code)+ "\t\t" + r.text)
		except:
			self.host.logWarning("[InfluxDB] Could not connect to database, is it running?")
		





	def writeTextFile(self):
		# Writing into files based on the date, YYYYMMDD:
		name = self.host.timeObject().astimezone(demCfg['timezone']).strftime("%Y%m%d")
		self.filename = self.filepath+name+'.dem'

		try:
			os.makedirs(os.path.dirname(self.filename), exist_ok=True)
			f = open(self.filename, 'a')
			f.write(self.data)
			f.close()
		except:
			self.host.logWarning("[InfluxDB] Could not find or create backup file: "+self.filename)
			

	# FIXME Make async?
	def loadTextFiles(self):
		# First see if we have files to load
		if self.restoreBackup:
			self.createDatabase()

			self.host.logMsg("[InfluxDB] Connection available, restoring backups")

			try:
				# Open each file
				folder = os.listdir(self.filepath)
				for filename in folder:

					# Handle each file
					if os.path.isfile(self.filepath+filename):
						f = open(self.filepath+filename, 'r')

						# Read file and write when the size exceeds the size
						data = ""
						for line in f:
							data += line
							if len(data) > self.maxBuffer:
								self.writeToDatabase(data)
								data = ""

						# Flush the last part
						self.writeToDatabase(data)
						data = ""
						f.close()

						# After all data is written, let's delete the file if required
						if self.autoCleanup:
							os.remove(self.filepath+filename)

				# Finally, we can remove the error flag
				self.errorFlag = False

				self.host.logMsg("[InfluxDB] Backups restored")

				self.restoring.release()

			except:
				self.host.logWarning("[InfluxDB] Could not resore backups")

	def cleanupTextFiles(self):
		if self.autoCleanup:
			try:
				os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
			except:
				self.host.logWarning("[InfluxDB] Could not find or create backup file folder: " + self.filename)
				
			try:
				# Open each file
				folder = os.listdir(self.filepath)
				for filename in folder:
					if os.path.isfile(self.filepath+filename):
						os.remove(self.filepath+filename)
			except:
				self.host.logWarning("[InfluxDB] Could not remove files")