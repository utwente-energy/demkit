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

from dev.curtDev import CurtDev
from pyModbusTCP.client import ModbusClient
import pandas as pd
import time

class SunspecPvDev(CurtDev):
	def __init__(self,  name,  host, ipAddress, port, influx=True, reader=None):
		CurtDev.__init__(self,  name,  host, influx, reader)
		
		self.devtype = "Curtailable"
		self.ipAddress = ipAddress
		self.port = port

		# Update rate:
		self.lastUpdate = -1
		self.updateInterval = 1
		self.retrieving = False

		self.data = {}

		self.runInThread("readSolarEdge")


	def readSolarEdge(self):
		while True:
			try:
				c = ModbusClient(host=self.ipAddress, port=self.port, auto_open=True, auto_close=True, timeout=5)

				response = c.read_holding_registers(40069, 40)
				address = list(range(40069, 40109))

				table = pd.DataFrame()
				table['Address'] = address
				table['Value'] = response
				table['Response'] = response

				for i in table.index:
					if table['Value'].iloc[i] == 65535:
						table['Value'].iloc[i] = -1

					if table['Value'].iloc[i] == 65534:
						table['Value'].iloc[i] = -2

					if table['Value'].iloc[i] == 65533:
						table['Value'].iloc[i] = -3

					if table['Value'].iloc[i] == 65532:
						table['Value'].iloc[i] = -4

					if table['Value'].iloc[i] == 65531:
						table['Value'].iloc[i] = -5

				scaleFactorCurrent = table[table['Address'] == 40075]['Value'].iloc[0].astype(float)
				scaleFactorVoltage = table[table['Address'] == 40082]['Value'].iloc[0].astype(float)
				scaleFactorACPower = table[table['Address'] == 40084]['Value'].iloc[0].astype(float)
				scaleFactorFrequency = table[table['Address'] == 40086]['Value'].iloc[0].astype(float)
				scaleFactorApparentPower = table[table['Address'] == 40088]['Value'].iloc[0].astype(float)
				scaleFactorReactivePower = table[table['Address'] == 40090]['Value'].iloc[0].astype(float) - 1.0
				scaleFactorPowerFactor = table[table['Address'] == 40092]['Value'].iloc[0].astype(float) - 1.0
				# scaleFactorEnergyWh         = table[table['Address'] == 40095]['Value'].iloc[0].astype(float)
				scaleFactorDCCurrent = table[table['Address'] == 40097]['Value'].iloc[0].astype(float)
				scaleFactorDCVoltage = table[table['Address'] == 40099]['Value'].iloc[0].astype(float)
				scaleFactorDCPower = table[table['Address'] == 40101]['Value'].iloc[0].astype(float)
				scaleFactorTemperature = table[table['Address'] == 40106]['Value'].iloc[0].astype(float)

				# Write data
				self.lockState.acquire()
				self.data['A-current.L1'] = self.scaleData(table[table['Address'] == 40072]['Value'].iloc[0], scaleFactorCurrent)
				self.data['A-current.L2'] = self.scaleData(table[table['Address'] == 40073]['Value'].iloc[0], scaleFactorCurrent)
				self.data['A-current.L3'] = self.scaleData(table[table['Address'] == 40074]['Value'].iloc[0], scaleFactorCurrent)

				self.data['V-voltage.L1L2'] = self.scaleData(table[table['Address'] == 40076]['Value'].iloc[0], scaleFactorVoltage)
				self.data['V-voltage.L2L3'] = self.scaleData(table[table['Address'] == 40077]['Value'].iloc[0], scaleFactorVoltage)
				self.data['V-voltage.L3L1'] = self.scaleData(table[table['Address'] == 40078]['Value'].iloc[0], scaleFactorVoltage)

				self.data['V-voltage.L1N'] = self.scaleData(table[table['Address'] == 40079]['Value'].iloc[0], scaleFactorVoltage)
				self.data['V-voltage.L2N'] = self.scaleData(table[table['Address'] == 40080]['Value'].iloc[0], scaleFactorVoltage)
				self.data['V-voltage.L3N'] = self.scaleData(table[table['Address'] == 40081]['Value'].iloc[0], scaleFactorVoltage)

				self.data['W-power.P'] = self.scaleData(table[table['Address'] == 40083]['Value'].iloc[0], scaleFactorACPower)  # real
				self.data['H-frequency.AC'] = self.scaleData(table[table['Address'] == 40085]['Value'].iloc[0], scaleFactorFrequency)
				self.data['VA-power.S'] = self.scaleData(table[table['Address'] == 40087]['Value'].iloc[0], scaleFactorApparentPower)  # apparent
				self.data['VAR-power.Q'] = self.scaleData(table[table['Address'] == 40089]['Value'].iloc[0], scaleFactorReactivePower)  # reactive

				self.data['PF-powerfactor.PF'] = self.scaleData(table[table['Address'] == 40091]['Value'].iloc[0], scaleFactorPowerFactor)

				self.data['A-current.DC'] = self.scaleData(table[table['Address'] == 40096]['Value'].iloc[0], scaleFactorDCCurrent)
				# throw out DC current because this throws a -inf error on InfluxDB database
				self.data['V-voltage.DC'] = self.scaleData(table[table['Address'] == 40098]['Value'].iloc[0], scaleFactorDCVoltage)
				self.data['P-power.DC'] = self.scaleData(table[table['Address'] == 40100]['Value'].iloc[0], scaleFactorDCPower)

				self.data['T-temperature.HS'] = self.scaleData(table[table['Address'] == 40103]['Value'].iloc[0], scaleFactorTemperature)
				self.lockState.release()

				for c in self.commodities:
					self.consumption[c] = complex(-1 * self.data['W-power.P'] / len(self.commodities), 0.0)

				# If all succeeded:
				self.lastUpdate = self.host.time()

			except:
				self.logWarning("SolarEdge Modbus error")

			time.sleep(1)




	def preTick(self, time, deltatime=0):
		# We should not be a bad citizen to the service
		# self.lockState.acquire()
		# if (self.host.time() - self.lastUpdate)  > self.updateInterval and not self.retrieving:
		return


	def scaleData(self, value, scaleFactor):
		try:
			res = round(value *10 ** scaleFactor, 2)
			if abs(res) == float('inf'):
				res = 0.0
			if res != res:  # Check for Not a number
				res = 0.0
		except:
			res = 0.0

		return res



	# LogStats() is called at the end of a time interval
	# This is your chance to log data
	def logStats(self, time):
		self.lockState.acquire()
		# Default data to log is the power consumption for each commodity
		# The try-except is in place to ensure that a demonstration does not crash due to small time synchronization errors
		try:
			for c in self.commodities:
				self.logValue("W-power.real.c." + c, self.consumption[c].real)
				self.logValue("W-power.imag.c." + c, self.consumption[c].imag)
				if c in self.plan and len(self.plan[c]) > 0:
					self.logValue("W-power.plan.real.c."+c, self.plan[c][0][1].real)
					self.logValue("W-power.plan.imag.c."+c, self.plan[c][0][1].imag)

			for key in self.data:
				self.logValue(key + "." + c, self.data[key])

		except:
			pass

		self.lockState.release()
