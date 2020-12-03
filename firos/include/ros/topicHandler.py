# MIT License
#
# Copyright (c) <2015> <Ikergune, Etxetar>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

__author__ = "Dominik Lux"
__credits__ = ["Peter Detzner"]
__maintainer__ = "Dominik Lux"
__version__ = "0.0.1a"
__status__ = "Developement"

import os
import rospy
import importlib
import time

from include.logger import Log
from include.constants import Constants as C
from include.libLoader import LibLoader
from include import confManager

# PubSub Handlers
from include.pubsub.genericPubSub import PubSub

# this Message is needed, for the Listeners on connect on disconnect
import std_msgs.msg

# Structs with topic:
# ROS_PUBSUB[topic] --> returns  rospy Publisher/Subsriber
ROS_PUBLISHER = {}
ROS_SUBSCRIBER_LAST_MESSAGE = {}
ROS_SUBSCRIBER = {}

# A Struct which is used to minimize the Number of publishes. Here we only
# save time stamps of ids. LAST_PUBLISH_TIME[topic] would return a time
LAST_PUBLISH_TIME = dict()

# Topics in ROS do only have one data-type!
# (There might be an Exception to this if the topic gets deregistered, this is currently ignored)
# We use this here to load the type of an topic and the dictionary rep. only once!
ROS_TOPIC_TYPE = {}
ROS_TOPIC_AS_DICT ={}

# ROS-Node Subscribers  (connect/disconnect)
subscribers = []

# Actual ROS-Classes are used in instantiateROSMessage and loadMsgHandlers.
# An entry is the ._type-Attribute of the ROS-Messages ('/' is replaced by '.')
ROS_MESSAGE_CLASSES = {}

# If shutdown is signaled, do stop posting ROS-Messages to the ContextBroker
SHUTDOWN_SIGNAL = False

CloudPubSub = None

def initPubAndSub():
    global CloudPubSub
    CloudPubSub = PubSub()

def loadMsgHandlers(topics_data):
    ''' This method initializes The Publisher and Subscriber for ROS and
        the Subscribers for the Context-broker (based on ROS-Publishers).
        It also initializes the structs for ROS messages (types, dicts and classes)

        For each topic, the ROS message-structs are initialized.
        Then (depending on Publisher or Subscriber) the corrsponding rospy Publisher/Subscriber
        is generated and added in its struct.

        topics_data: The data, as in topics.json  (and whitelist) specified.
    '''


    Log("INFO", "Getting configuration data")
    Log("INFO", "Generating topic handlers:")

    # Generate
    for topic in topics_data.keys():
        # for each topic and topic in topics_data:

        # Load specific message from robot_data
        msg = str(topics_data[topic][0])
        theclass = LibLoader.loadFromSystem(msg, topic)

        # Add specific message in struct to not load it again later.
        if theclass._type not in ROS_MESSAGE_CLASSES:
            ROS_MESSAGE_CLASSES[theclass._type] = theclass  # setting Class

        # Create, if not already, a dictionary from the corresponding message-type
        if topic not in ROS_TOPIC_AS_DICT:
            ROS_TOPIC_AS_DICT[topic] = rosMsg2Dict(theclass())

        # Set the topic class-type, which is for each topic always the same
        ROS_TOPIC_TYPE[topic] = theclass._type

        # Create Publisher or Subscriber
        if topics_data[topic][1].lower() == "subscriber":
            # Case it is a subscriber, add it in subscribers
            additionalArgsCallback = {"topic": topic} # Add addtional Infos about topic
            ROS_SUBSCRIBER[topic] = rospy.Subscriber(topic, theclass, _publishToCBRoutine,
                                                    additionalArgsCallback)
            ROS_SUBSCRIBER_LAST_MESSAGE[topic] = None # No message currently published
        else:
            # Case it is a publisher, add it in publishers
            ROS_PUBLISHER[topic] = rospy.Publisher(topic, theclass,
                                                    queue_size=C.ROS_SUB_QUEUE_SIZE, latch=True)

    # After initializing ROS-PUB/SUBs, intitialize ContextBroker-Subscriber
    # based on ROS-Publishers for each robot
    CloudPubSub.subscribe(ROS_PUBLISHER.keys(), ROS_TOPIC_TYPE, ROS_TOPIC_AS_DICT)
    Log("INFO", "\n")
    Log("INFO", "Subscribed to " + str(list(ROS_PUBLISHER.keys())) + "\n")


def _publishToCBRoutine(data, args):
    ''' This routine is executed on every received (subscribed) message on ROS.
        It just wraps it content and publishes the data via the cbPublisher.publishToCB
        Here we explicitly check at the SHUTDOWN_SIGNAL. if it is set, we stop publishing

        Here we also use the PUB_FREQUENCY-variable, to limit the number of publishes, if needed

        data: data received from ROS
        args: additional arguments we set prior
    '''
    if not SHUTDOWN_SIGNAL:
        topic = args['topic'] # Retreiving additional Infos, which were set on initialization

        t = time.time() * 1000 # Get Millis
        if topic in LAST_PUBLISH_TIME and LAST_PUBLISH_TIME[topic] >= t:
            # Case: We want it to publish again, but we did not wait PUB_FREQUENCY milliseconds
            return

        CloudPubSub.publish(topic, data, ROS_TOPIC_AS_DICT)
        ROS_SUBSCRIBER_LAST_MESSAGE[topic] = data
        LAST_PUBLISH_TIME[topic] = t + C.PUB_FREQUENCY



class RosTopicHandler:
    ''' The Class RosTopicHandler is a Wrapper-Class which
        just maps the publish Routine to the cbPublisher (for the requestHandler) and
        by shutdown removes and deletes all Subscriptions/created Entities (for core)
    '''



    @staticmethod
    def publish(topic, convertedData, dataStruct):
        ''' This method publishes the receive data from the
            ContextBroker to ROS

            topic: The topic to be published
            convertedData: the converted data from the Subscriber
            dataStruct: The struct of convertedData, specified by their types
        '''
        if topic in ROS_PUBLISHER:
            if topic in ROS_TOPIC_TYPE and ROS_TOPIC_TYPE[topic] == dataStruct['type']:
                # check if a publisher to this topic is set
                # then check the received and expected type to be equal
                # Iff, then publish received message to ROS
                newMsg = instantiateROSMessage(convertedData, dataStruct)
                ROS_PUBLISHER[topic].publish(newMsg)


    @staticmethod
    def unregisterAll():
        global SHUTDOWN_SIGNAL
        ''' First set the SHUTDOWN_SIGNAL, then
            unregister all subscriptions on ContextBroker,
            delete all created Entities on Context Broker and
            unregister subscriptions from ROS
        '''
        SHUTDOWN_SIGNAL = True

        CloudPubSub.unsubscribe()
        CloudPubSub.unpublish()

        Log("INFO", "Unsubscribing topics...")
        for subscriber in subscribers:
            subscriber.unregister()
        for topic in ROS_SUBSCRIBER:
            ROS_SUBSCRIBER[topic].unregister()
        Log("INFO", "Unsubscribed topics\n")



def instantiateROSMessage(obj, dataStruct):
    ''' This method instantiates via obj and dataStruct the actual ROS-Message like
        "geometry_msgs.Twist". Explicitly it loads the ROS-Message-class (if not already done)
        with the dataStruct["type"] if given and recursively sets all attributes of the Message.

        obj: The Object to instantiate
        dataStruct: The corresponding dataStruct, which helps by setting the explicit ROS-Message
    '''
    # Check if type and value in datastruct, if not we default to a primitive value
    if 'type' in dataStruct and 'value' in dataStruct:

        # Load Message-Class only if not already loaded!
        if dataStruct['type'] not in ROS_MESSAGE_CLASSES:
            msgClass = LibLoader.loadFromSystem(dataStruct['type'], None)
            ROS_MESSAGE_CLASSES[dataStruct['type']] = msgClass
        #instantiate Message
        instance = ROS_MESSAGE_CLASSES[dataStruct['type']]()

        for attr in ROS_MESSAGE_CLASSES[dataStruct['type']].__slots__:
            # For each attribute in Message
            if attr in obj and attr in dataStruct['value']:
                # Check iff obj AND dataStruct contains attr
                if type(dataStruct['value'][attr]) is list:
                    l =[]
                    for it in range(len(dataStruct['value'][attr])):
                        l.append(instantiateROSMessage(obj[attr][it],
                                                        dataStruct['value'][attr][it]))
                    setattr(instance, attr, l)
                else:
                    setattr(instance, attr, instantiateROSMessage(obj[attr],
                                                                    dataStruct['value'][attr]))
        return instance
    else:
        # Struct is {}:
        if type(obj) is dict:
            # if it is still a dict, convert into an Object with attributes
            t = Temp()
            for k in obj:
                setattr(t, k, obj[k])
            return t
        else:
            # something more simple (int, long, float), return it
            return obj


class Temp(object):
    ''' A Temp-object, to convert from a Dictionary into an object with attributes.
    '''
    pass


def rosMsg2Dict(rosClassInstance):
    ''' Generating a dictionary out of the instance of a
        ROS-Message

        rosClassInstance: an actual instance of the ROS-Message (values will be omitted)
    '''
    obj = {}
    for key, t in zip(rosClassInstance.__slots__, rosClassInstance._slot_types):
        attr = getattr(rosClassInstance, key)
        if hasattr(attr, '__slots__'):
            obj[key] = rosMsg2Dict(attr)
        else:
            obj[key] = t
    return obj



###############################################################################
#######################   Connect/Disconnect Mapping   ########################
###############################################################################

def createConnectionListeners():
    ''' This creates the following listeners for firos in ROS for robot-creation
        and -removal and maps them to the methods below:

        /ROS_NODE_NAME/connect    --> std_msgs/String
        /ROS_NODE_NAME/disconnect --> std_msgs/String
    '''
    subscribers.append(rospy.Subscriber(C.ROS_NODE_NAME + "/disconnect",
                                        std_msgs.msg.String, _robotDisconnection))
    subscribers.append(rospy.Subscriber(C.ROS_NODE_NAME +"/connect",
                                        std_msgs.msg.String, _robotConnection))


def _robotDisconnection(data):
    ''' Unregisters from a given topic

        data: The String which was sent to firos
    '''
    topic = str(data.data)


    if topic in ROS_PUBLISHER:
        for topic in ROS_PUBLISHER[topic]:
            ROS_PUBLISHER[topic][topic].unregister()
        Log("INFO", "Disconnected publisher for: " + topic)
        del ROS_PUBLISHER[topic]

    if topic in ROS_SUBSCRIBER:
        for topic in ROS_SUBSCRIBER[topic]:
            ROS_SUBSCRIBER[topic][topic].unregister()
        Log("INFO", "Disconnected subscriber for: " + topic)
        del ROS_SUBSCRIBER[topic]


def _robotConnection(data):
    ''' This resets firos into its original state

        TODO DL reset, instead of connect?
        TODO DL Add real connect for only one Robot?
    '''
    robot_name = data.data
    Log("INFO", "Connected robot: " + robot_name)
    loadMsgHandlers(confManager.getRobots(True))
