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

from flow.el.mvLvTransformer import MvLvTransformer


import math

# Placeholder as legacy support
class Transformer(MvLvTransformer):
	def __init__(self,  name,  flowSim, host):
		MvLvTransformer.__init__(self,  name,  flowSim, host)
		self.logWarning("The Transformer model as a name is deprecated, use the MvLvTransformer instead (equal functionality)")
