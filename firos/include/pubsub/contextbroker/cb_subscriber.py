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
import json
import threading
import requests
try:
    # Python 3
    import _thread as thread
    from http.server import BaseHTTPRequestHandler
    from http.server import HTTPServer
except ImportError:
    # Pyrhon 2
    import thread
    from BaseHTTPServer import BaseHTTPRequestHandler
    from BaseHTTPServer import HTTPServer

from include.constants import Constants as C
from include.logger import log
from include.pubsub.generic_pub_sub import Subscriber
from include.ros.topic_handler import RosTopicHandler
from include.FiwareObjectConverter.objectFiwareConverter import ObjectFiwareConverter


class CbSubscriber(Subscriber):
    ''' The CbSubscriber handles the subscriptions on the ContextBroker.
        Only the url CONTEXT_BROKER / v2 / subcriptions  is used here!
        As on CbPublisher on shutdown all subscriptions are deleted form
        ContextBroker.

        this Objects also converts the received data from ContextBroker
        back into a Python-Object.

        Here each topic of an robot is subscribed seperately.

        THIS IS THE ONLY FILE WHICH OPERATES ON /v2/subscriptions
    '''

    # Saves the subscriptions IDs returned from ContextBroker.
    # Follwoing Structure: subscriptionIds[ROBOT_ID][TOPIC] returns a sub-Id in String
    subscriptionIds = {}
    CB_BASE_URL = None
    FIROS_NOTIFY_URL = None

    def __init__(self):
        '''
            Lazy Initialization of CB_BASE_URL
            and setting up Configuration-Parameters
        '''
        # Do nothing if no Configuration is provided!
        if self.config_data is None:
            log("WARNING", "No Configuration for Context-Broker found!")
            self.no_conf = True
            return
        else:
            self.no_conf = False

        # Set Configuration
        data = self.config_data

        if data is not None and "address" not in data or "port" not in data:
            raise Exception("No Context-Broker specified!")

        if "subscription" not in data:
            data["subscription"] = dict(throttling=0,
                                        subscription_length=300,
                                        subscription_refresh_delay=0.9)

        if "throttling" not in data["subscription"]:
            data["subscription"]["throttling"] = 0
        else:
            data["subscription"]["throttling"] = int(
                data["subscription"]["throttling"])

        if "subscription_length" not in data["subscription"]:
            data["subscription"]["subscription_length"] = 300
        else:
            data["subscription"]["subscription_length"] = int(
                data["subscription"]
                ["subscription_length"]
            )

        if "subscription_refresh_delay" not in data["subscription"]:
            data["subscription"]["subscription_refresh_delay"] = 0.9
        else:
            data["subscription"]["subscription_refresh_delay"] = float(
                data["subscription"]
                ["subscription_refresh_delay"]
            )

        self.data = data
        self.server_is_running = False
        self.cb_base_url = "http://{}:{}".format(data["address"], data["port"])

    def subscribe(self, topic_list, topic_types, msgDefintions):
        ''' topic_list: A list of topics
            msgDefintions: The Messages-Definitions from ROS

            This method only gets called once (or multiple times, if we get a reset!)! So we
            need to make sure, that in this file 'RosTopicHandler.publish' is called somehow
            independently after some Signal arrived (from elsewhere).

            Keep in mind that Firos can get a Reset-Signal, in this case, this method is called
            again. Make sure that this method can get called multiple times!

            In this Context-Broker-Subscriber we spawn ONE HTTP-Base-Server in another Thread,
            which will be used, so that the Context-Broker can notify us after it received a
            Message.

            In addition to that, the Context-Broker needs to know how to notify us. This is solved
            by adding subscriptions into the Context-Broker, which we need to manually maintain.
            Again we start a Thread for each Topic which handles the Subscriptions.



            So After everything is set up, Firos can be notified, explicitly here the method:
            """CBServer.CBHandler.do_post""" is invoked by Notification. This method handles the
            Conversion back into a conform "ROS-Message".

            After we did the Conversion, we simply need to call  """RosTopicHandler.publish"""


        '''
        # Do nothing if no Configuratuion
        if self.no_conf:
            return

        # Start the HTTPServer and wait until it is ready!
        if not self.server_is_running:
            server_ready = threading.Event()
            self.server = CBServer(server_ready)
            thread.start_new_thread(self.server.start, ())
            self.server_is_running = True
            server_ready.wait()

        # If not already subscribed, start a new thread which handles the subscription
        # for each topic for an robot. And only If the topic list is not empty!
        for topic in topic_list:
            if topic not in self.subscriptionIds:
                log("INFO", "Subscribing on Context-Broker to topics: " +
                    str(list(topic_list)))
                # Start Thread via subscription
                thread.start_new_thread(
                    self.subscribe_thread, (topic, topic_types, msgDefintions))

    def unsubscribe(self):
        '''
            Simply unsubscribed from all tracked subscriptions
            and also stop the HTTP-Server
        '''
        # Do nothing if no Configuratuion
        if self.no_conf:
            return

        # close HTTP-Server
        self.server.close()

        # Unsubscribe to all Topics
        for topic in self.subscriptionIds:
            response = requests.delete(
                self.cb_base_url + self.subscriptionIds[topic])
            self._check_response(response, sub_id=self.subscriptionIds[topic])

    ####################################################
    ########## Helpful Classes and Methods #############
    ####################################################

    def subscribe_thread(self, topic, topic_types, msg_defintions):
        '''
            A Subscription-Thread. Its Life-Cycle is as follows:
            -> Subscribe -> Delete old Subs-ID -> Save new Subs-ID -> Wait ->

            topic: The Topic (string) to subscribe to.
        '''
        while True:
            # Subscribe
            json_data = self.subscribe_json_generator(
                topic, topic_types, msg_defintions)
            response = requests.post(self.cb_base_url + "/v2/subscriptions",
                                     data=json_data,
                                     headers={'Content-Type': 'application/json'})
            self._check_response(response, created=True, rob_top=topic)

            if 'Location' in response.headers:
                # <- get subscription-ID
                new_sub_id = response.headers['Location']
            else:
                log("WARNING",  "Firos was not able to subscribe to topic: {}".format(topic))

            # Unsubscribe
            if topic in self.subscriptionIds:
                response = requests.delete(
                    self.cb_base_url + self.subscriptionIds[topic])
                self._check_response(
                    response, sub_id=self.subscriptionIds[topic])

            # Save new ID
            self.subscriptionIds[topic] = new_sub_id

            # Wait
            # sleep Length * Refresh-Rate (where 0 < Refresh-Rate < 1)
            time.sleep(int(self.data["subscription"]["subscription_length"] *
                           self.data["subscription"]["subscription_refresh_delay"]))
            log("INFO", "Refreshing Subscription for topic: " + str(topic))

    def subscribe_json_generator(self, topic, topic_types, msg_defintions):
        '''
            This method returns the correct JSON-format to subscribe to the ContextBroker.
            The Expiration-Date/Throttle and Type of topics is retreived here via the
            configuration we got.

            topic: The actual topic to subscribe to.
        '''
        # This struct correspondes to following JSON-format:
        # https://fiware-orion.readthedocs.io/en/master/user/walkthrough_apiv2/index.html#subscriptions
        struct = {
            "subject": {
                "entities": [
                    {
                        "id": str(topic).replace("/", "."),  # OCB Specific!!
                        # OCB Specific!!
                        "type": topic_types[topic].replace("/", "%2F")
                    }
                ]
            },
            "notification": {
                "http": {
                    "url": "http://{}:{}".format(C.EP_SERVER_ADRESS, self.server.port)
                },
                "attrs": list(msg_defintions[topic].keys())
            },
            "expires": time.strftime("%Y-%m-%dT%H:%M:%S.00Z",
                                     time.gmtime(time.time() +
                                                 self.data["subscription"]
                                                 ["subscription_length"]
                                                 )
                                     ),  # ISO 8601
            "throttling": self.data["subscription"]["throttling"]
        }
        return json.dumps(struct)

    def _check_response(self, response, rob_top=None, sub_id=None, created=False):
        '''
            If a not good response from ContextBroker is received, the error will be printed.

            response: The response from ContextBroker
            rob_top:   A string (topic), for the curretn robot/topic
            sub_id:    The Subscription ID string, which should get deleted
            created:  Creation or Deletion of a subscription (bool)
        '''
        if not response.ok:
            if created:
                log("ERROR", "Could not create subscription for topic {}".format(rob_top)
                    + " in Context-Broker :")
                log("ERROR", response.content)
            else:
                log("WARNING", "Could not delete subscription {}".format(sub_id)
                    + " from Context-Broker :")
                log("WARNING", response.content)


class CBServer:
    '''
        This is the HTTPServer, which start listening on an adress and a free port
        Here we provide 3 methods: Initialize, start and stop. Start and stop either
        start or stop this Server.
    '''

    def __init__(self, thread_event):
        '''
            Set up HTTPServer
            thread_event: The Event where the main Thread waits on
        '''
        self.stopped = False
        self.thread_event = thread_event

        protocol = "HTTP/1.0"

        if C.EP_SERVER_PORT is not None and isinstance(C.EP_SERVER_PORT, int):
            server_address = ("0.0.0.0", C.EP_SERVER_PORT)
        else:
            server_address = ("0.0.0.0", 0)

        self.CBHandler.protocol_version = protocol
        self.httpd = HTTPServer(server_address, self.CBHandler)

    def start(self):
        '''
            This start the HTTPServer and notifies thread_event
        '''
        # Get Port and HostName and save port
        sock_name = self.httpd.socket.getsockname()
        self.port = sock_name[1]
        log("INFO", "\nListening for Context-Broker-Messages on: ",
            C.EP_SERVER_ADRESS, ":", sock_name[1])

        # Notify and start handling Requests
        self.thread_event.set()
        while not self.stopped:
            self.httpd.handle_request()

    def close(self):
        '''
            Stops the HTTPServer
        '''
        self.stopped = True

    class CBHandler(BaseHTTPRequestHandler):
        ''' This is the FIROS-HTTP-Request-Handler. It is needed,
            because the ContextBroker sends Information about the
            subscriptions via HTTP. This Class just handles incoming
            Requests and converts the received Data into a "ROS-conform Message".
            in """do_post""" we invoke """RosTopicHandler.publish"""
        '''

        def log_message(self, format, *args):
            ''' Suppress prints! '''
            return

        def do_get(self):
            '''
                We do not respond to GETs. We do Nothing!!
            '''
            pass

        def do_post(self):
            ''' The ContextBroker is informing us via one of our subscriptions.
                We convert the received content back and publish
                it in ROS.

                self: The "request" from the Context-Broker

                we invoke """RosTopicHandler.publish""" here!
            '''
            # retreive Data and get the updated information
            rec_data = self.rfile.read(int(self.headers['Content-Length']))
            received_data = json.loads(rec_data)
            data = received_data['data'][0]  # Specific to NGSIv2
            json_data = json.dumps(data)

            obj = self.TypeValue()
            ObjectFiwareConverter.fiware2Obj(json_data, obj, setAttr=True, useMetaData=False, encoded=True)
            obj.id = obj.id.replace(".", "/")
            obj.type = obj.type.replace("%2F", "/")

            obj_type = obj.type
            topic = obj.id

            del data["id"]
            del data["type"]
            temp_dict = dict(type=obj_type, value=data)

            data_struct = self._build_type_struct(temp_dict)

            RosTopicHandler.publish(topic, obj.__dict__, data_struct)
            # # Send OK!
            self.send_response(204)
            self.end_headers()  # Python 3 needs an extra end_headers after send_response

        # Back Conversion From Entity-JSON into Python-Object

        def _build_type_struct(self, obj):
            ''' This generates a struct containing a type (the actual ROS-Message-Type) and
                its value (either empty or more ROS-Message-Types).

                This struct is used later to recursivley load needed Messages and fill them with
                content before they are posted back to ROS.

                obj:    The received update from Context-Broker
            '''
            dict_ = {}

            # Searching for a point to get ROS-Message-Types from the obj
            if 'value' in obj and 'type' in obj and "/" in obj['type']:
                dict_['type'] = obj['type']
                objval = obj['value']
                dict_['value'] = {}

                # For each value in Object repeat!
                for k in objval:
                    # Check if we got an Array-Type value
                    if ('type' in objval[k] and
                        'value' in objval[k] and
                            objval[k]['type'] == 'array'):

                        list_ = []
                        for klist in objval[k]['value']:
                            list_.append(self._build_type_struct(klist))
                        dict_['value'][k] = list_
                    else:
                        dict_['value'][k] = self._build_type_struct(objval[k])

            return dict_

        class TypeValue(object):
            ''' A Stub-Object to parse the received data
            '''
