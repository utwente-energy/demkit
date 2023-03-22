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


from ctrl.thermal.thermalOptCtrl import ThermalOptCtrl
from ctrl.devCtrl import DevCtrl

# Thermal device controller basis
# For now identical to the normal device controller.
# This class is added to make sure that thermal specific changes for thermal models can be implemented easily
class ThermalDevCtrl(DevCtrl, ThermalOptCtrl):
	#Make some init function that requires the host to be provided
	def __init__(self,  name, dev,  ctrl,  host):
		ThermalOptCtrl.__init__(self,  name, None)
		DevCtrl.__init__(self, name, dev, ctrl, host)