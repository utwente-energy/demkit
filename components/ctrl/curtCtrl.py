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


from ctrl.loadCtrl import LoadCtrl
import util.helpers
import copy


class CurtCtrl(LoadCtrl):
	def __init__(self, name, dev, parent, host):
		LoadCtrl.__init__(self, name, dev, parent, host)

		self.devtype = "CurtailableCtrl"

	def doPlanning(self, signal, requireImprovement=True):
		self.lockPlanning.acquire()
		result = {}

		# Retrieve device details
		devData = self.updateDeviceProperties()

		assert (self.timeBase >= devData['timeBase'])  # The other direction is untested and probably broken!
		assert (self.timeBase % devData['timeBase'] == 0)  # Again, otherwise things are very likely to break

		time = signal.time
		timeBase = signal.timeBase
		signal = copy.deepcopy(signal)

		s = self.preparePlanningData(signal, copy.deepcopy(self.candidatePlanning[self.name]))

		if self.predictionPlanningTime < time:
			p = {}

			# Obtain the profile from a prediction. There is no flex to change this anyways
			for c in self.commodities:
				p[c] = self.doPrediction(time - (time % timeBase), time - (time % timeBase) + (timeBase * len(s.desired[c])))
				if len(p[c]) != s.planHorizon:
					p[c] = util.helpers.interpolate(p[c], s.planHorizon)

			# Condirm bookkeeping
			self.predictionPlanning = copy.deepcopy(p)
			self.predictionPlanningTime = time

		p = copy.deepcopy(self.predictionPlanning)

		# Just obtain the profile from a prediction. There is no flex to change this anyways
		for c in self.commodities:
			# Perform load shedding or curtailment, keeping the sign of the load however.
			# E.g. producers can only curtail and are <= 0 W, loads will only shed and are >= 0 W

			# Real part
			if signal.allowDiscomfort and not devData['strictComfort']:
				for i in range(0, len(p[c])):
					if c in s.upperLimits:
						if p[c][i].real > s.upperLimits[c][i].real:
							if devData['onOffDevice']:
								p[c][i] = complex(0.0, 0.0)
							else:
								if p[c][i].real <= 0:
									p[c][i] = complex(min(0, max(p[c][i].real, s.upperLimits[c][i].real)), p[c][i].imag)
								else:
									p[c][i] = complex(max(0, min(p[c][i].real, s.upperLimits[c][i].real)), p[c][i].imag)

						if p[c][i].imag > s.upperLimits[c][i].imag and not devData['onOffDevice']:
							if p[c][i].imag <= 0:
								p[c][i] = complex(p[c][i].real, min(0, max(p[c][i].imag, s.upperLimits[c][i].imag)))
							else:
								p[c][i] = complex(p[c][i].real, max(0, min(p[c][i].imag, s.upperLimits[c][i].imag)))

					if c in s.lowerLimits:
						if p[c][i].real < s.lowerLimits[c][i].real:
							if devData['onOffDevice']:
								p[c][i] = complex(0.0, 0.0)
							else:
								if p[c][i].real <= 0:
									p[c][i] = complex(min(0, max(p[c][i].real, s.lowerLimits[c][i].real)), p[c][i].imag)
								else:
									p[c][i] = complex(max(0, min(p[c][i].real, s.lowerLimits[c][i].real)), p[c][i].imag)

						if p[c][i].imag < s.lowerLimits[c][i].imag and not devData['onOffDevice']:
							if p[c][i].imag <= 0:
								p[c][i] = complex(p[c][i].real, min(0, max(p[c][i].imag, s.lowerLimits[c][i].imag)))
							else:
								p[c][i] = complex(p[c][i].real, max(0, min(p[c][i].imag, s.lowerLimits[c][i].imag)))

		# calculate the improvement
		improvement = 0.0
		boundImprovement = 0.0
		if requireImprovement:
			improvement = self.calculateImprovement(signal.desired, copy.deepcopy(self.candidatePlanning[self.name]), p)
			boundImprovement = self.calculateBoundImprovement(copy.deepcopy(self.candidatePlanning[self.name]), p, signal.upperLimits, signal.lowerLimits, norm=2)

			if signal.allowDiscomfort:
				improvement = max(boundImprovement, improvement)

			if improvement < 0.0 or boundImprovement < 0.0:
				improvement = 0.0
			else:
				self.candidatePlanning[self.name] = copy.deepcopy(p)
		else:
			self.candidatePlanning[self.name] = copy.deepcopy(p)

		# send out the result
		result['improvement'] = max(0.0, improvement)
		result['boundImprovement'] = max(0.0, boundImprovement)
		result['profile'] = copy.deepcopy(self.candidatePlanning[self.name])

		self.lockPlanning.release()
		return result
