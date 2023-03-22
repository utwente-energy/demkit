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


# REST API based on the EVE package
import calendar
import datetime
import time
# FIXME: including pytz would be awesome


from eve import Eve
from flask import jsonify, request, abort, make_response, Response
import json

import importlib


# FIXME: We need to remove this
from components.ctrl.auction.btsAuctionCtrl import BtsAuctionCtrl
from components.ctrl.auction.bufAuctionCtrl import BufAuctionCtrl
from components.ctrl.auction.bufConvAuctionCtrl import BufConvAuctionCtrl
from components.ctrl.auction.curtAuctionCtrl import CurtAuctionCtrl
from components.ctrl.auction.tsAuctionCtrl import TsAuctionCtrl


# FIXME: See if we can remove this. Security clutter that is not our main purpose for now to resolve
def _build_cors_prelight_response():
	pass
	# response = make_response()
	# response.headers.add("Access-Control-Allow-Origin", "*")
	# response.headers.add('Access-Control-Allow-Headers', "*")
	# response.headers.add('Access-Control-Allow-Methods', "*")
	# return response

def _corsify_actual_response(response):
	return response
	# response.headers.add("Access-Control-Allow-Origin", "*")
	# return response

class EveApi:
	def __init__(self, host, port, address="http://localhost"):
		self.host = host
		self.port = port
		self.address = address

		my_settings = {
			'X_DOMAINS': '*',
			'DOMAIN' : {'': {}}
		}
		self.app = Eve(settings = my_settings)

		#Now load all functions
		self.addRoutes()

		#start the API
		self.app.run(port=self.port, host='0.0.0.0', debug=False) #Note: Debug is NOT working because of my hacking skills (Gerwin)


### API INTERFACE FROM HERE ON ###
	def addRoutes(self):
		#call a function w/o params
		@self.app.route('/call/<entity>/<function>')
		def callfunc(entity, function):
			answer = self.host.callFunction(entity, function)
			if answer == None:
				return json.dumps("success")
			else:
				return json.dumps(answer)
			return json.dumps("error")

		#call a function w/ params
		@self.app.route('/callp/<entity>/<function>', methods=['PUT'])
		def callfuncp(entity, function):
			args = json.loads(request.data.decode("utf-8"))
			answer = self.host.callFunction(entity, function, args)
			if answer == None:
				return json.dumps("")
			else:
				return json.dumps(answer)
			return json.dumps("error")

		# set variables
		@self.app.route('/set/<entity>/<var>/<val>')
		def setvar(entity, var, val):
			answer = self.host.setVar(entity, var, val)
			if not answer:
				return json.dumps("error")
			else:
				return json.dumps(answer)
			return json.dumps("error")

		@self.app.route('/setp/<entity>/<var>', methods=['POST'])
		def setvarp(entity, var):
			val = json.loads(request.data.decode("utf-8"))
			answer = self.host.setVar(entity, var, val)
			if answer == None:
				return json.dumps("error")
			else:
				return json.dumps(answer)
			return json.dumps("error")

		@self.app.route('/setnp/<entity>', methods=['POST'])
		def setnvarp(entity):
			data = json.loads(request.data.decode("utf-8"))
			try:
				for k,v in data.items():
					self.host.setVar(entity, k,v)
			except:
				return json.dumps("error")
			return json.dumps("success")

		# set variables to an object reference
		@self.app.route('/setobj/<entity>/<var>/<val>')
		def setvarobj(entity, var, val):
			answer = self.host.setObj(entity, var, val)
			if not answer:
				return json.dumps("error")
			else:
				return json.dumps(answer)
			return json.dumps("error")

		@self.app.route('/setobjp/<entity>/<var>', methods=['POST'])
		def setvarobjp(entity, var):
			val = json.loads(request.data.decode("utf-8"))
			answer = self.host.setObj(entity, var, val)
			if answer == None:
				return json.dumps("error")
			else:
				return json.dumps(answer)
			return json.dumps("error")

		# get a variable
		@self.app.route('/get/<entity>/<var>')
		def getvar(entity, var):
			answer = self.host.getVar(entity, var)
			if answer == None:
				return json.dumps("error")
			else:
				return json.dumps(answer)
			return json.dumps("error")

		# create an object
		@self.app.route('/createobj/<entity>')
		def createobj(entity):
			answer = self.host.createObject(entity, None)
			if answer == None:
				return json.dumps("error")
			else:
				return json.dumps(answer)
			return json.dumps("error")

		# create an object
		@self.app.route('/createobjp/<entity>', methods=['POST'])
		def createobjp(entity):
			val = json.loads(request.data.decode("utf-8"))
			answer = self.host.createObject(entity, val)
			if answer == None:
				return json.dumps("error")
			else:
				return json.dumps(answer.name)
			return json.dumps("error")

		# Remove an object
		@self.app.route('/removeobj/<entity>')
		def removeobj(entity):
			answer = self.host.removeObject(entity)
			if answer == None:
				return json.dumps("error")
			else:
				return json.dumps("succes")
			return json.dumps("error")


# Sync calls, will be called synchronized to the simulation. Execution order equals input order.
# Always returns a true, however, the status cannot be really determined!
# Some callback may be implemented in the future to do so.
		#call a function w/o params
		@self.app.route('/synccall/<entity>/<function>')
		def synccallfunc(entity, function):
			call = {'cmd': 'callFunction', 'entity' : entity, 'func': function, 'args': None}
			self.host.cmdQueue.put(dict(call))
			# self.host.callFunction(entity, function)
			return json.dumps("success")

		#call a function w/ params
		@self.app.route('/synccallp/<entity>/<function>', methods=['POST'])
		def synccallfuncp(entity, function):
			args = json.loads(request.data.decode("utf-8"))
			call = {'cmd': 'callFunction', 'entity' : entity, 'func': function, 'args': args}
			self.host.cmdQueue.put(dict(call))
			return json.dumps("success")

		@self.app.route('/syncset/<entity>/<var>/<val>')
		def syncsetvar(entity, var, val):
			call = {'cmd': 'setVar', 'entity' : entity, 'var': var, 'val': val}
			self.host.cmdQueue.put(dict(call))
			return json.dumps("success")

		@self.app.route('/syncsetp/<entity>/<var>', methods=['POST'])
		def syncsetvarp(entity, var):
			val = json.loads(request.data.decode("utf-8"))
			call = {'cmd': 'setVar', 'entity' : entity, 'var': var, 'val': val}
			self.host.cmdQueue.put(dict(call))
			return json.dumps("success")

		@self.app.route('/syncsetnp/<entity>', methods=['POST'])
		def syncsetnvarp(entity):
			data = json.loads(request.data.decode("utf-8"))
			try:
				for k,v in data.items():
					call = {'cmd': 'setVar', 'entity' : entity, 'var': k, 'val': v}
					self.host.cmdQueue.put(dict(call))
			except:
				return json.dumps("error")
			return json.dumps("success")

		@self.app.route('/syncsetobj/<entity>/<var>/<val>')
		def syncsetvarobj(entity, var, val):
			call = {'cmd': 'setObj', 'entity' : entity, 'var': var, 'val': val}
			self.host.cmdQueue.put(dict(call))
			return json.dumps("success")

		@self.app.route('/syncsetobjp/<entity>/<var>', methods=['POST'])
		def syncsetvarobjp(entity, var):
			val = json.loads(request.data.decode("utf-8"))
			call = {'cmd': 'setObj', 'entity' : entity, 'var': var, 'val': val}
			self.host.cmdQueue.put(dict(call))
			return json.dumps("success")

		# For now we assume that due to the global interperter lock an "async" call on retrieving a variable won't cause problems
		@self.app.route('/syncget/<entity>/<var>')
		def syncgetvar(entity, var):
			answer = self.host.getVar(entity, var)
			if answer == None:
				return json.dumps("error")
			else:
				return json.dumps(answer)
			return json.dumps("error")

		# create an object
		@self.app.route('/synccreateobj/<entity>')
		def synccreateobj(entity):
			call = {'cmd': 'createObj', 'entity' : entity}
			self.host.cmdQueue.put(dict(call))
			return json.dumps("success")

		# create an object
		@self.app.route('/synccreateobjp/<entity>', methods=['POST'])
		def synccreateobjp(entity):
			val = json.loads(request.data.decode("utf-8"))
			call = {'cmd': 'createObj', 'entity' : entity, 'val': val}
			self.host.cmdQueue.put(dict(call))
			return json.dumps("success")

		# Remove an object
		@self.app.route('/syncremoveobj/<entity>')
		def syncremoveobj(entity):
			call = {'cmd': 'removeObj', 'entity' : entity}
			self.host.cmdQueue.put(dict(call))
			return json.dumps("success")

		# Raw send commands with in-order-execution
		@self.app.route('/synccmds', methods=['POST'])
		def synccmds():
			list = json.loads(request.data.decode("utf-8"))
			for e in list:
				call = dict(e)
				self.host.cmdQueue.put(dict(call))
			return json.dumps("success")