# DEMKit software
# Copyright (C) 2020 CAES and MOR Groups, University of Twente, Enschede, The Netherlands

# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NON
# INFRINGEMENT; IN NO EVENT SHALL LICENSOR BE LIABLE FOR ANY
# CLAIM, DAMAGES OR ANY OTHER LIABILITY ARISING FROM OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE THEREOF.


# Permission is hereby granted, non-exclusive and free of charge, to any person,
# obtaining a copy of the DEMKit-software and associated documentation files,
# to use the Software for NON-COMMERCIAL SCIENTIFIC PURPOSES only,
# subject to the conditions mentioned in the DEMKit License:

# You should have received a copy of the DEMKit License
# along with this program.  If not, contact us via email:
# demgroup-eemcs@utwente.nl.

# This file is a template to setup DEMKit
# It is important to modify appropriate lines for your system
# Each config item should only appear once, comment the others
# Rename this file to userconf.py

import os

demCfg = {}

# ENVIRONEMNT PARAMETERS
# Modify and adapt the following items

# DSM platform scripts location
demCfg['env'] = {}

# Uncomment and modify one of the following lines
demCfg['env']['path'] = '/app/demkit/components/'	

# User models location
demCfg['workspace']= {}

# Uncomment and modify one of the following lines
demCfg['workspace']['path'] = '/app/workspace/'


# Database settings
demCfg['db'] = {}

#Influxdb
demCfg['db']['influx'] = {}
demCfg['db']['influx']['address'] = str(os.environ['DEMKIT_INFLUXURL'])			# Address of the Influx instance
demCfg['db']['influx']['port'] = str(os.environ['DEMKIT_INFLUXPORT'])			# Port number of the Influx instance
demCfg['db']['influx']['dbname'] = str(os.environ['DEMKIT_INFLUXDB'])			# Database name to write to

# Preparation for Influx 2.0
demCfg['db']['influx']['username'] = str(os.environ['DEMKIT_INFLUXUSER'])		# Username of Influx instance
demCfg['db']['influx']['password'] = str(os.environ['DEMKIT_INFLUXPASSWORD'])	# Password for Influx
demCfg['db']['influx']['token'] = str(os.environ['DEMKIT_INFLUXTOKEN'])			# PInflux token



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
demCfg['network']['sockPath'] = 'ipc:///zmq/'			#linux
# demCfg['network']['tcp']['ip'] = "tcp://127.0.0.1"
# demCfg['network']['tcp']['pub'] = 3010
# demCfg['network']['tcp']['sub'] = 3011
# demCfg['network']['tcp']['res']	= 3012

#Smart house config
demCfg['smarthouse'] = {}
demCfg['smarthouse']['usb'] = '/dev/ttyACM0'




# STATIC SETTINGS
# You should not modify lines below

# Version control, this config is valid for V4 of DEMKit
demCfg['ver'] = 4.1
