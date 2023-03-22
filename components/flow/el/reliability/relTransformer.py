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

from flow.el.mvLvtransformer import MvLvTransformer
from util.csvReader import CsvReader

import math

# Specific parameters can be found in the MSc thesis of Marius Groen, University of Twente, 2018
# Title: Assessing the Effect of Smart Reinforcement Alternatives on the Expected Asset Lifetime of Low Voltage Networks
# Download: http://essay.utwente.nl/74878/1/Groen_MA_EEMCS.pdf
# And references therein

class RelTransformer(MvLvTransformer):
	def __init__(self,  name,  flowSim, host):
		MvLvTransformer.__init__(self,  name,  flowSim, host)
		
		self.devtype = "ElectricityTransformer"

		# Bookkeeping
		self.hottestSpotTemperature = 0.0
		self.lossOfLife = 0.0
		self.lossOfLifeFactor = 0.0
		self.reliability = 1.0
		self.topOilRise = None
		self.hottestSpotRiseTopOil = None
		self.ambientTemperature = 25

		self.topOilRiseOverAmbientRated = 40.26  # Celsius
		self.windingHotSpotRiseOverAmbientRated = 56.11  # Celsius

		self.weightCoreCoils = 787.0  # kg
		self.weightTankFittings = 103.0  # kg
		self.oilVolume = 180.0 / 0.8883  # L

		self.ratedLife = 180.0e3 * 3600.0  # IEEE Loading Guide
		self.ratedHotSpotTemperature = 273.15 + 110.0  # IEEE Loading Guide

		# Ambient Temperature CSV (takes the default temperature if left blank)
		self.ambientTempFileName = None
		self.ambientTempTimeBase = 60
		self.ambientTempReader = None

		# Precalculated Values
		self.oilTimeConstantRated = None
		self.lifeScaleParameter = None

	def startup(self):
		# CSV Reader for Ambient Temperature
		if self.ambientTempFileName is not None:
			self.ambientTempReader = CsvReader(self.ambientTempFileName, self.ambientTempTimeBase)

		# Calculate oil time constant under rated conditions (valid for ONAN and ONAF)
		thermalCapacity = 1440.0 * (0.1323*self.weightCoreCoils + 0.0882*self.weightTankFittings + 0.3513*self.oilVolume)
		self.oilTimeConstantRated = thermalCapacity * self.topOilRiseOverAmbientRated / (self.noLoadLosses + self.ratedLoadLosses)

		# Calculate Life Scale Parameter (C)
		self.lifeScaleParameter = self.ratedLife * math.exp(-15000.0/self.ratedHotSpotTemperature)

	def preTick(self, time, deltatime=0):
		if self.ambientTempFileName is not None:
			self.ambientTemperature = self.ambientTempReader.readValue(time, self.ambientTempTimeBase)

	def estimateHottestSpotTemperature(self):
		# Calculates the hottest spot temperature of the transformer based on IEEE Std. C57.91 Clause 7

		# Calculate some helpful intermediate values
		K = self.load / self.ratedLoad
		R = self.ratedLoadLosses / self.noLoadLosses

		# Initialize 'previous' values if necessary
		if self.topOilRise is None:
			self.topOilRise = self.topOilRiseOverAmbientRated * ((K*K*R + 1.0)/(R + 1.0))**0.8  # only valid for ONAN/ONAF

		if self.hottestSpotRiseTopOil is None:
			self.hottestSpotRiseTopOil = (self.windingHotSpotRiseOverAmbientRated-self.topOilRiseOverAmbientRated) * K**1.6  # only valid for ONAN/ONAF

		# Previous and Ultimate/Infinity Values
		previousTopOilRise = self.topOilRise
		previousHottestSpotRiseTopOil = self.hottestSpotRiseTopOil

		infinityTopOilRise = self.topOilRiseOverAmbientRated * ((K*K*R + 1.0)/(R + 1.0))**0.8  # only valid for ONAN/ONAF
		infinityHottestSpotRiseTopOil = (self.windingHotSpotRiseOverAmbientRated-self.topOilRiseOverAmbientRated) * K**1.6  # only valid for ONAN/ONAF

		timeStep = self.host.timeInterval()

		# Calculate oil time constant (only valid for ONAN/ONAF)
		if abs(infinityTopOilRise - previousTopOilRise) > 1.0e-10:
			oilTimeConstant = self.oilTimeConstantRated * (((infinityTopOilRise/self.topOilRiseOverAmbientRated) - (previousTopOilRise/self.topOilRiseOverAmbientRated)) / ((infinityTopOilRise/self.topOilRiseOverAmbientRated)**1.25 - (previousTopOilRise/self.topOilRiseOverAmbientRated)**1.25))
		else:
			oilTimeConstant = self.oilTimeConstantRated
		
		# Top-Oil Rise over Ambient
		self.topOilRise = previousTopOilRise + (infinityTopOilRise-previousTopOilRise) * (1.0 - math.exp(-timeStep/oilTimeConstant))

		# Hottest Spot Rise over Top-Oil
		windingTimeConstant = 300.0  # 5min
		self.hottestSpotRiseTopOil = previousHottestSpotRiseTopOil + (infinityHottestSpotRiseTopOil-previousHottestSpotRiseTopOil) * (1.0 - math.exp(-timeStep/windingTimeConstant))

		# Result
		self.hottestSpotTemperature = self.ambientTemperature + self.topOilRise + self.hottestSpotRiseTopOil

	def estimateReliability(self):
		# Estimates the reliability of the insulation up to this time interval.

		# Get Hottest Spot Temperature in K
		self.estimateHottestSpotTemperature()
		hotSpotT = 273.15 + self.hottestSpotTemperature

		# Calculate Loss of Life
		timeStep = self.host.timeInterval()
		self.lossOfLifeFactor = math.exp(15000.0/self.ratedHotSpotTemperature - 15000.0/hotSpotT)
		self.lossOfLife = self.lossOfLife + timeStep * self.lossOfLifeFactor

		# Calculate Reliability
		weibullBeta = 5.8718
		self.reliability = math.exp(-(self.lossOfLife / (self.lifeScaleParameter * math.exp(15000.0/self.ratedHotSpotTemperature))) ** weibullBeta)

	def getRelativeLossOfLife(self):
		# Small helper method
		if self.host.currentTime == self.host.startTime:
			return self.lossOfLife/self.host.timeInterval()

		return self.lossOfLife/(self.host.currentTime - self.host.startTime)

	def logStats(self, time):

		self.logValue("C-temperature.transformer.ambient", self.ambientTemperature)
		self.logValue("C-temperature.transformer.topoilriseoverambient", self.topOilRise)
		self.logValue("C-temperature.transformer.hotspot", self.hottestSpotTemperature)

		self.logValue("p-lossoflifefactor.transformer", self.lossOfLifeFactor)
		self.logValue("p-lossoflife.transformer.relative", self.getRelativeLossOfLife())
		self.logValue("p-reliability.transformer", self.reliability)
		self.logValue("p-failureprobability.transformer", 1.0 - self.reliability)

		Transformer.logStats(self, time)
