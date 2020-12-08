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

import time
import rospy

from include.logger import log
from include.constants import Constants as C
from include.lib_loader import LibLoader
from include import conf_manager

# PubSub Handlers
from include.pubsub.generic_pub_sub import PubSub

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

# Actual ROS-Classes are used in instantiate_ros_message and load_msg_handlers.
# An entry is the ._type-Attribute of the ROS-Messages ('/' is replaced by '.')
ROS_MESSAGE_CLASSES = {}

# If shutdown is signaled, do stop posting ROS-Messages to the ContextBroker
SHUTDOWN_SIGNAL = False

CLOUD_PUB_SUB = None

def init_pub_and_sub():
    global CLOUD_PUB_SUB
    CLOUD_PUB_SUB = PubSub()

def load_msg_handlers(topics_data):
    ''' This method initializes The Publisher and Subscriber for ROS and
        the Subscribers for the Context-broker (based on ROS-Publishers).
        It also initializes the structs for ROS messages (types, dicts and classes)

        For each topic, the ROS message-structs are initialized.
        Then (depending on Publisher or Subscriber) the corrsponding rospy Publisher/Subscriber
        is generated and added in its struct.

        topics_data: The data, as in topics.json  (and whitelist) specified.
    '''


    log("INFO", "Getting configuration data")
    log("INFO", "Generating topic handlers:")

    # Generate
    for topic in topics_data.keys():
        # for each topic and topic in topics_data:

        # Load specific message from robot_data
        msg = str(topics_data[topic][0])
        theclass = LibLoader.load_from_system(msg, topic)

        # Add specific message in struct to not load it again later.
        if theclass._type not in ROS_MESSAGE_CLASSES:
            ROS_MESSAGE_CLASSES[theclass._type] = theclass  # setting Class

        # Create, if not already, a dictionary from the corresponding message-type
        if topic not in ROS_TOPIC_AS_DICT:
            ROS_TOPIC_AS_DICT[topic] = ros_msg_to_dict(theclass())

        # Set the topic class-type, which is for each topic always the same
        ROS_TOPIC_TYPE[topic] = theclass._type

        # Create Publisher or Subscriber
        if topics_data[topic][1].lower() == "subscriber":
            # Case it is a subscriber, add it in subscribers
            additional_args_callback = {"topic": topic} # Add addtional Infos about topic
            ROS_SUBSCRIBER[topic] = rospy.Subscriber(topic, theclass, _publish_to_cb_routine,
                                                    additional_args_callback)
            ROS_SUBSCRIBER_LAST_MESSAGE[topic] = None # No message currently published
        else:
            # Case it is a publisher, add it in publishers
            ROS_PUBLISHER[topic] = rospy.Publisher(topic, theclass,
                                                    queue_size=C.ROS_SUB_QUEUE_SIZE, latch=True)

    # After initializing ROS-PUB/SUBs, intitialize ContextBroker-Subscriber
    # based on ROS-Publishers for each robot
    CLOUD_PUB_SUB.subscribe(ROS_PUBLISHER.keys(), ROS_TOPIC_TYPE, ROS_TOPIC_AS_DICT)
    log("INFO", "\n")
    log("INFO", "Subscribed to " + str(list(ROS_PUBLISHER.keys())) + "\n")


def _publish_to_cb_routine(data, args):
    ''' This routine is executed on every received (subscribed) message on ROS.
        It just wraps it content and publishes the data via the cbPublisher.publishToCB
        Here we explicitly check at the SHUTDOWN_SIGNAL. if it is set, we stop publishing

        Here we also use the PUB_FREQUENCY-variable, to limit the number of publishes, if needed

        data: data received from ROS
        args: additional arguments we set prior
    '''
    if not SHUTDOWN_SIGNAL:
        topic = args['topic'] # Retreiving additional Infos, which were set on initialization

        time_ = time.time() * 1000 # Get Millis
        if topic in LAST_PUBLISH_TIME and LAST_PUBLISH_TIME[topic] >= time_:
            # Case: We want it to publish again, but we did not wait PUB_FREQUENCY milliseconds
            return

        CLOUD_PUB_SUB.publish(topic, data, ROS_TOPIC_AS_DICT)
        ROS_SUBSCRIBER_LAST_MESSAGE[topic] = data
        LAST_PUBLISH_TIME[topic] = time_ + C.PUB_FREQUENCY



class RosTopicHandler:
    ''' The Class RosTopicHandler is a Wrapper-Class which
        just maps the publish Routine to the cbPublisher (for the requestHandler) and
        by shutdown removes and deletes all Subscriptions/created Entities (for core)
    '''



    @staticmethod
    def publish(topic, converted_data, data_struct):
        ''' This method publishes the receive data from the
            ContextBroker to ROS

            topic: The topic to be published
            converted_data: the converted data from the Subscriber
            data_struct: The struct of converted_data, specified by their types
        '''
        if topic in ROS_PUBLISHER:
            if topic in ROS_TOPIC_TYPE and ROS_TOPIC_TYPE[topic] == data_struct['type']:
                # check if a publisher to this topic is set
                # then check the received and expected type to be equal
                # Iff, then publish received message to ROS
                new_msg = instantiate_ros_message(converted_data, data_struct)
                ROS_PUBLISHER[topic].publish(new_msg)


    @staticmethod
    def unregister_all():
        global SHUTDOWN_SIGNAL
        ''' First set the SHUTDOWN_SIGNAL, then
            unregister all subscriptions on ContextBroker,
            delete all created Entities on Context Broker and
            unregister subscriptions from ROS
        '''
        SHUTDOWN_SIGNAL = True

        CLOUD_PUB_SUB.unsubscribe()
        CLOUD_PUB_SUB.unpublish()

        log("INFO", "Unsubscribing topics...")
        for subscriber in subscribers:
            subscriber.unregister()
        for topic in ROS_SUBSCRIBER:
            ROS_SUBSCRIBER[topic].unregister()
        log("INFO", "Unsubscribed topics\n")



def instantiate_ros_message(obj, data_struct):
    ''' This method instantiates via obj and data_struct the actual ROS-Message like
        "geometry_msgs.Twist". Explicitly it loads the ROS-Message-class (if not already done)
        with the data_struct["type"] if given and recursively sets all attributes of the Message.

        obj: The Object to instantiate
        data_struct: The corresponding data_struct, which helps by setting the explicit ROS-Message
    '''
    # Check if type and value in data_struct, if not we default to a primitive value
    if 'type' in data_struct and 'value' in data_struct:

        # Load Message-Class only if not already loaded!
        if data_struct['type'] not in ROS_MESSAGE_CLASSES:
            msg_class = LibLoader.load_from_system(data_struct['type'], None)
            ROS_MESSAGE_CLASSES[data_struct['type']] = msg_class
        #instantiate Message
        instance = ROS_MESSAGE_CLASSES[data_struct['type']]()

        for attr in ROS_MESSAGE_CLASSES[data_struct['type']].__slots__:
            # For each attribute in Message
            if attr in obj and attr in data_struct['value']:
                # Check iff obj AND data_struct contains attr
                if type(data_struct['value'][attr]) is list:
                    list_ =[]
                    for number in range(len(data_struct['value'][attr])):
                        list_.append(instantiate_ros_message(obj[attr][number],
                                                        data_struct['value'][attr][number]))
                    setattr(instance, attr, list_)
                else:
                    setattr(instance, attr, instantiate_ros_message(obj[attr],
                                                                    data_struct['value'][attr]))
        return instance
    else:
        # Struct is {}:
        if type(obj) is dict:
            # if it is still a dict, convert into an Object with attributes
            temp_ = Temp()
            for k in obj:
                setattr(temp_, k, obj[k])
            return temp_
        else:
            # something more simple (int, long, float), return it
            return obj


class Temp(object):
    ''' A Temp-object, to convert from a Dictionary into an object with attributes.
    '''
    pass


def ros_msg_to_dict(ros_class_instance):
    ''' Generating a dictionary out of the instance of a
        ROS-Message

        ros_class_instance: an actual instance of the ROS-Message (values will be omitted)
    '''
    obj = {}
    for key, type_ in zip(ros_class_instance.__slots__, ros_class_instance._slot_types):
        attr = getattr(ros_class_instance, key)
        if hasattr(attr, '__slots__'):
            obj[key] = ros_msg_to_dict(attr)
        else:
            obj[key] = type_
    return obj



###############################################################################
#######################   Connect/Disconnect Mapping   ########################
###############################################################################

def create_connection_listeners():
    ''' This creates the following listeners for firos in ROS for robot-creation
        and -removal and maps them to the methods below:

        /ROS_NODE_NAME/connect    --> std_msgs/String
        /ROS_NODE_NAME/disconnect --> std_msgs/String
    '''
    subscribers.append(rospy.Subscriber(C.ROS_NODE_NAME + "/disconnect",
                                        std_msgs.msg.String, _robot_disconnection))
    subscribers.append(rospy.Subscriber(C.ROS_NODE_NAME +"/connect",
                                        std_msgs.msg.String, _robot_connection))


def _robot_disconnection(data):
    ''' Unregisters from a given topic

        data: The String which was sent to firos
    '''
    topic = str(data.data)


    if topic in ROS_PUBLISHER:
        for topic in ROS_PUBLISHER[topic]:
            ROS_PUBLISHER[topic][topic].unregister()
        log("INFO", "Disconnected publisher for: " + topic)
        del ROS_PUBLISHER[topic]

    if topic in ROS_SUBSCRIBER:
        for topic in ROS_SUBSCRIBER[topic]:
            ROS_SUBSCRIBER[topic][topic].unregister()
        log("INFO", "Disconnected subscriber for: " + topic)
        del ROS_SUBSCRIBER[topic]


def _robot_connection(data):
    ''' This resets firos into its original state

        TODO DL reset, instead of connect?
        TODO DL Add real connect for only one Robot?
    '''
    robot_name = data.data
    log("INFO", "Connected robot: " + robot_name)
    load_msg_handlers(conf_manager.get_robots(True))
