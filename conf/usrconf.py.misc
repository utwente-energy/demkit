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


# This file is a template to setup DEMKit
# It is important to modify appropriate lines for your system
# Each config item should only appear once, comment the others
# Rename this file to userconf.py

demCfg = {}

# ENVIRONEMNT PARAMETERS
# Modify and adapt the following items

# DSM platform scripts location
demCfg['env'] = {}

# Uncomment and modify one of the following lines
# demCfg['env']['path'] = 'C:/users/yourname/demkitsim/demkit/components/'				# windows
# demCfg['env']['path'] = '/home/user/demkit/components/'			                    # linux
# demCfg['env']['path'] = '/Users/yourname/demkit/components/'                          # Mac OS X

# User models location
demCfg['workspace']= {}

# Uncomment and modify one of the following lines
# demCfg['workspace']['path'] = 'C:/users/yourname/demkitsim/workspace/example/'        # windows
# demCfg['workspace']['path']= '/home/user/python/workspace/example/'	                # linux
# demCfg['workspace']['path'] = '/Users/yourname/python/workspace/example/'             # Mac OS X


# Database settings
demCfg['db'] = {}

#Influxdb
demCfg['db']['influx'] = {}
demCfg['db']['influx']['address'] = "http://localhost"	# Address of the Influx instance
demCfg['db']['influx']['port'] = "8086"					# Port number of the Influx instance
demCfg['db']['influx']['dbname'] = "dem"				# Database name to writ to

# Preparation for Influx 2.0
demCfg['db']['influx']['username'] = "demkit"			# Username of Influx instance
demCfg['db']['influx']['password'] = "WZ5LE3nblOQwpWHrr3m5"					# Password for Influx
demCfg['db']['influx']['token'] = "-WF-JsrugNAZbl4mZJrfT3H6GNXdtNrRWXM-yzuECUJv8XiZqdan0tGq3MFnaEzDRIodcit3Sg0Qh6UiEKZsgg=="


# Variable output for logs ans backups (stored within the workspace folder of a model by default)
# Do not forget the traling slash!
demCfg['var'] = {}
demCfg['var']['backup'] = "var/backup/"
demCfg['var']['databasebackup'] = "var/backup/database/"
demCfg['var']['log'] = "var/log/"



# Timezone information
from pytz import timezone
demCfg['timezonestr'] = 'Europe/Amsterdam'
demCfg['timezone'] = timezone(demCfg['timezonestr'])




# OPTIONAL SETTINGS
# These settings are only required for certain cases and normally can remain unchanged

# Socket path for networked configurations
demCfg['network'] = {}
demCfg['network']['sockPath'] = 'ipc:///home/user/python/'			#linux

#Smart house config
demCfg['smarthouse'] = {}
demCfg['smarthouse']['usb'] = '/dev/ttyACM0'




# STATIC SETTINGS
# You should not modify lines below

# Version control, this config is valid for V4 of DEMKit
demCfg['ver'] = 4.1
