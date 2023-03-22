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

from dev.loadDev import LoadDev

class HassLoadDev(LoadDev):
	def __init__(self,  name,  host, influx=False, reader=None):
		LoadDev.__init__(self, name, host, influx, reader)

		self.url = "https://localhost:8123"
		self.bearer = ""
		self.sensor = "sensor.total_power" # Sensor name as known to Home Assistant

		# Update rate:
		self.lastUpdate = -1
		self.updateInterval = 1 # Update every minute

		# see https://developers.home-assistant.io/docs/en/external_api_rest.html

	# Fixme make async
	def preTick(self, time, deltatime=0):
		# We should not be a bad citizen to the service
		self.lockState.acquire()
		if (self.host.time() - self.lastUpdate)  > self.updateInterval:
			try:
				value = 0.0 # Jus tto be sure if all fails

				# Try to get the sensor information
				url = self.url+"/api/states/"+self.sensor
				headers = {
					'Authorization': 'Bearer '+self.bearer,
					'content-type': 'application/json',
				}

				# Try to access the data
				r = requests.get(url, headers=headers)
				if r.status_code != 200:
					self.logWarning("Could not connect to Home Assistant. Errorcode: "+str(r.status_code)+ "\t\t" + r.text)

				data = r.json()

				# Now retrieve the data we'd like:
				value = data['state']
				value = value.replace("," , ".") # Fix decimals
				value = float(value) * self.scaling

				# Now, value contains the power production by the pv setup, now we can set it as consumption:
				for c in self.commodities:
					self.consumption[c] = complex(value / len(self.commodities), 0.0)

				# If all succeeded:
				self.lastUpdate = self.host.time()
			except:
				self.logWarning("Home Assistant service error")

		self.lockState.release()