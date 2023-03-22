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

# In the future, this system should be modified such that it can make use of generic libraries, such as:
# https://github.com/chargeprice/open-ev-data


evTypes = {
	0 :
		{
			"name"				: "generic",
			"chargingPowers"	: [0, 150000], # Power in W
			"chargingPowersStep": [0, 1500, 150000], # Power in W
			"capacity"			: 100000, # Capacity in Wh
			"discrete"			: False,
			"step"				: False,
			"supportDcMode"		: True,
			"support3pMode"		: True,
			"hybrid"			: False
		},
}
