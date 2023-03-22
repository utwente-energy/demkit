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

# Template to create a new auction controller.

# Some parts are mandatory to be configured, indicated by brackets "< ... >".
# Other parts are optional, but give some ideas.
# Furthermore, some code that should be included by default is given

# Mandatory import statemenet
from ctrl.auction.demandFunction import DemandFunction
from ctrl.auction.devAuctionCtrl import DevAuctionCtrl

# Give your controller a name, use the following convention:
class <controller_name>AuctionCtrl(DevAuctionCtrl): # Inherits by default from the DevAuctionCtrl
    def __init__(self, name, dev, parent, host):
        DevAuctionCtrl.__init__(self,  name, dev, parent, host)

        # Device type
        self.devtype = "<your_controller_name>Controller"

        # Provide optional parameters:

		# Some useful, inherited, parameters are:
		#	self.parent = parent			# connected parent controller
		#	self.dev = dev					# connected device (to be controlled)
		# 	self.host = None				# the host to which this device is connected
		#	self.commodities = ['ELECTRICITY']	# commodities to be used, Note, Auction only supports one commodity
		# 	self.discreteBids = False		# Whether to use discrete bids or not

		# Provide local state variables:

		# Some useful, inherited states are:
		# 	self.currentPrice = 0						# Current clearing price
        #	self.currentFunction = DemandFunction() 	# Note: currentFunction is the function that the parent knows / uses to clear the market
        #	self.updatedFunction = DemandFunction() 	# Note: updatedFunction is the function that used to trigger an update
		#	self.devData								# Last known device status


    # createDemandFunction() is called to request the demand function
    # Here you can specify the bidding function to be used by the device
    def createDemandFunction(self):
        # Synchronize the device state:
        deviceState = self.updateDeviceProperties()

        # Create an empty demand function
        result = DemandFunction()

        # Now populate the demand function
        # Check Chapter 5 from Hoogsteen - A Cyber-Physical Systems Perspective on Decentralized Energy Management (PhD thesis)

        # As an example, we create a linear line from the current consumption to its negative:
        # First obtain the consumption
        consumption = deviceState['consumption'][self.commodity].real

        # Check if the consumption is negative, as we need a declining line:
        if consumption < 0.0:
            consumption = -consumption

        # Now create the demandFunction by adding a line segment:
        # result.addLine(self, maxDemand, minDemand, minPrice, maxPrice)
        result.addLine(consumption, -consumption, result.minComfort, result.maxComfort)

        # Note, there is also an option to add a point:
        # result.addPoint(self, demand, price)
        # For more, check demandFunction.py

        # Useful values available to you when defining a function
        #   result.minPrice     (default -2000) CURTAILMENT
        #   result.minComfort   (default -1000) INCREASE CONSUMPTION
        #   -                   (default 0)     CENTER OF THE MARKET
        #   result.maxComfort   (default 1000)  DECREASE CONSUMPTION
        #   result.maxPrice     (default 2000)  LOAD SHEDDING

        # Notes about demand functions:
        # 1. It needs to be descending (assertions check for this on runtime)
        # 2. You are responsible, the system will simply overwrite points if deemed required! So think of your definitions!

        # Return the demand function
        return result;       

    # Note that all other functionality is already implemented in the DevAuctionCtrl class
    # So, there is no need to set the planning manually, trigger the creation of a demand function or whatsoever
    # Hence, implementing a controller for an auction is relatively simple! :-)
    # Yet, tweaking the demand function itself is black magic hand has severe drawbacks.


	# You are free to define more local functions if you wish to keep the code clean

	# Happy coding!