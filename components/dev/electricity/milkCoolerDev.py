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

from dev.loadDev import LoadDev
from dev.device import Device
import math
from datetime import datetime
from util.influxdbReader import InfluxDBReader


class MilkCoolerDev(LoadDev):
    # Instantiation of the device object
    def __init__(self, name, host,startTime, influx=False, reader=None):
        LoadDev.__init__(self, name, host, influx, reader)

        self.devtype = "MilkCooler"


        self.beta = 0.328
        self.delta = -0.064
        self.gamma = 0.009
        self.tou = 0.218
        self.lambada = -0.643
        self.alpha = 23.726

        self.beta1 = -1.532
        self.delta1 = -0.299
        self.gamma1 = 0.007
        self.tou1 = 2.214
        self.lambada1 = 0.615
        self.alpha1 = -11.997
        self.t_amb1 = 23
        self.t_room1 = 25
        self.V1 = 700

        self. milk_start_time = 4
        self.milk_cool_time = 5
        self.startTime=startTime
        self.t_amb = 9

        self.RH = 70
        self.V = 500
        self.t_rm = 30
        self.t_room = 14
        self.reader =None

        self.strictComfort = False

    def startup(self):

        self.logMsg("Hello World1!")

        # Execute a generic startup from the base class
        Device.startup(self)

    def preTick(self, time, deltatime=0):
        #self.logMsg("MilkDevice simulating at timestamp " + str(time))
        self.lockState.acquire()


        dt_object = datetime.fromtimestamp(time)
        current_hour=((dt_object.hour*60*60)+(dt_object.minute*60)+(dt_object.second))/(60*60)
        a = math.sin(math.radians(360 * (1 / (2*self.milk_cool_time) ) * (current_hour - self.milk_start_time)))

        if current_hour<12:
            e = self.alpha + self.beta * self.t_amb + self.delta * self.RH + self.gamma * self.V + self.tou * self.t_rm + self.lambada * self.t_room
        else:
            e = self.alpha1 + self.beta1 * self.t_amb1 + self.delta1 * self.RH + self.gamma1 * self.V + self.tou1 * self.t_rm + self.lambada1 * self.t_room1

        peak = e * 2 * 3.14 * (1 / (2 *self. milk_cool_time))*1000

        if a<0:
            self.consumption['ELECTRICITY'] = complex(0.5, 0.0)
        else:
            self.consumption['ELECTRICITY'] = complex(a*peak, 0.0)
            if 'ELECTRICITY' in self.plan and len(self.plan['ELECTRICITY']) > 0:
                p = self.plan['ELECTRICITY'][0][1]

                if self.consumption['ELECTRICITY'].real > 0.0001:
                    self.consumption['ELECTRICITY'] = complex(
                        max(0.0, min(self.consumption['ELECTRICITY'].real, p.real)), 0.0)
                else:
                    self.consumption['ELECTRICITY'] = complex(
                        min(0.0, max(self.consumption['ELECTRICITY'].real, p.real)), 0.0)


		# GERWIN: 	Here I added code to "overwrite" the consumption value if a controller has planned a different value 
		#			this planned value is stored in self.plan['ELECTRICITY'][0][1]


        self.lockState.release()


    def timeTick(self, time, deltatime=0):
        # for now, we need nothing here except the pruneplan
        self.prunePlan()

    def logStats(self, time):
        self.lockState.acquire()

        # Here you can log values, also parameters over time.
        # However, you could also do it anywhere else, e.g. for debug
        # Note that only here they are "final" for the simulation interval
        # You are free to log things like the temperature
        self.logValue("W-power.real.c.ELECTRICITY", self.consumption['ELECTRICITY'].real)

        # I just keep the original as a reference
        # try:
        # 	for c in self.commodities:
        # 		self.logValue("W-power.real.c." + c, self.consumption[c].real)
        # 		if self.host.extendedLogging:
        # 			self.logValue("W-power.imag.c." + c, self.consumption[c].imag)
        #
        # 		if self.smartOperation and c in self.plan and len(self.plan[c]) > 0:
        # 			self.logValue("W-power.plan.real.c."+c, self.plan[c][0][1].real)
        # 			if self.host.extendedLogging:
        # 				self.logValue("W-power.plan.imag.c."+c, self.plan[c][0][1].imag)
        # except:
        # 	pass

        self.lockState.release()

    #### INTERFACING
    def getProperties(self):
        # No need to adapt
        r = Device.getProperties(self) # Get the properties of the overall Device class, which already includes global properties
        r['onOffDevice'] = False
        r['strictComfort'] = self.strictComfort
        return r

		
		
#### LOCAL HELPERS
# Here you can define your own local functions to split up logic and make it easier to maintain
    def readValue(self, time, filename=None, timeBase=None):
        if timeBase is None:
            timeBase = self.timeBase

        dt_object = datetime.fromtimestamp(time)
        current_hour = ((dt_object.hour * 60 * 60) + (dt_object.minute * 60) + (dt_object.second)) / (60 * 60)
        a = math.sin(math.radians(360 * (1 / (2 * self.milk_cool_time)) * (current_hour - self.milk_start_time)))

        if current_hour < 12:
            e = self.alpha + self.beta * self.t_amb + self.delta * self.RH + self.gamma * self.V + self.tou * self.t_rm + self.lambada * self.t_room
        else:
            e = self.alpha1 + self.beta1 * self.t_amb1 + self.delta1 * self.RH + self.gamma1 * self.V + self.tou1 * self.t_rm + self.lambada1 * self.t_room1

        peak = e * 2 * 3.14 * (1 / (2 * self.milk_cool_time))*1000

        if a < 0:
            r = complex(0.5, 0.0)
        else:
            r = complex(a * peak, 0.0)
        # This can be overridden to return the correct value


        return r

    def readValues(self, startTime, endTime, filename=None, timeBase=None):
        if timeBase is None:
            timeBase = self.timeBase

        result = []
        time = startTime
        while time < endTime:
            result.append(self.readValue(time, None, timeBase))
            time += timeBase

        return result
