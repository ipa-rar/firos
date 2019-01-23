# MIT License
#
# Copyright (c) <2015> <Ikergune, Etxetar>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE
# FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import os
import json
import urllib2
import netifaces

from core import FIROS_CONF_PATH



def setConfiguration(path):
    try:
        data = json.load(open(path + "/config.json"))
        return data[data["environment"]]
    except:
        return {}

configured = False

# All Constants with their default value!
PATH = None

LOGLEVEL = "INFO"
INTERFACE = "public"

MAP_SERVER_ADRESS = None
MAP_SERVER_PORT = 10100
ROSBRIDGE_PORT = 9090
CONTEXTBROKER_ADRESS = None
CONTEXTBROKER_PORT = None

CB_THROTTLING = 0
CB_SUB_LENGTH = 300             # In Seconds!
CB_SUB_REFRESH = 0.9            # After 90% of time is exceeded
CB_CONTEXT_TYPE = "ROBOT"   

ROS_NODE_NAME = "firos"
ROS_SUB_QUEUE_SIZE = 10 



if not configured:
    configured = True
    PATH = FIROS_CONF_PATH[0]
    print PATH

    configData = setConfiguration(PATH)

    if "interface" in configData:
        INTERFACE = configData["interface"]
    
    if "log_level" in configData:
        LOGLEVEL = configData["log_level"]

    if "server" in configData and "port" in configData["server"]:
        MAP_SERVER_PORT = configData["server"]["port"]

    try:
        CONTEXTBROKER_ADRESS = configData["contextbroker"]["address"]
        CONTEXTBROKER_PORT = configData["contextbroker"]["port"]
    except:
        print "TODO DL"

    if "contextbroker" in configData and "subscription" in configData["contextbroker"]:
        # Configuration for Subscription
        subConfig = configData["contextbroker"]["subscription"]
        if "throttling" in subConfig:
            CB_THROTTLING = subConfig["throttling"]
        
        if "subscription_length" in subConfig:
            CB_SUB_LENGTH = subConfig["subscription_length"]
        
        if "subscription_refresh_delay" in subConfig:
            CB_SUB_REFRESH = subConfig["subscription_refresh_delay"]


    if "node_name" in configData:
        ROS_NODE_NAME = configData["node_name"]
    
    if "ros_subscriber_queue" in configData:
        ROS_SUB_QUEUE_SIZE = configData["ros_subscriber_queue"]

    if "cb_type" in configData:
        CB_CONTEXT_TYPE = configData["cb_type"]


    if INTERFACE == "public":
        MAP_SERVER_ADRESS = urllib2.urlopen('http://ip.42.pl/raw').read()
    else:
        netifaces.ifaddresses(INTERFACE)
        MAP_SERVER_ADRESS = netifaces.ifaddresses(INTERFACE)[2][0]['addr']

    if "rosbridge_port" in configData:
        ROSBRIDGE_PORT = configData["rosbridge_port"]



