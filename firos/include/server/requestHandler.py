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

import re
import cgi
import json
try:
    # Python 3
    from urllib.parse import urlparse
    from http.server import BaseHTTPRequestHandler
    IS_PYTHON_3 = True
except ImportError:
    # Python 2
    from BaseHTTPServer import BaseHTTPRequestHandler
    from urlparse import urlparse
    IS_PYTHON_3 = False

from include.logger import log
from include.confManager import get_robots
from include.ros.rosConfigurator import RosConfigurator
from include.ros.topicHandler import (load_msg_handlers, ROS_PUBLISHER,
                                        ROS_SUBSCRIBER, ROS_TOPIC_AS_DICT,
                                        ROS_SUBSCRIBER_LAST_MESSAGE)
from include.FiwareObjectConverter.objectFiwareConverter import ObjectFiwareConverter


class RequestHandler(BaseHTTPRequestHandler):
    ''' This is the FIROS-HTTP-Request-Handler. It is needed,
        because we offer some functionality via Firos. This Class just handles incoming
        Requests and deligates them further to the specific ones. Firos
        allows some extra operations here like Connect and Disconnect.
    '''
    def do_get(self):
        ''' Case: only a GET Request
        '''
        path = urlparse("http://localhost" + self.path).path
        action = get_action(path, "GET")
        if action is not None:
            action["action"](self, action)
        else:
            end_request(self, ('Content-type', 'text/html'), 200, "Firos is running!")
        return

    def do_post(self):
        ''' Case: only a POST Requst
        '''
        path = urlparse("http://localhost" + self.path).path
        action = get_action(path, "POST")
        if action is not None:
            action["action"](self, action)
        else:
            end_request(self, ('Content-type', 'text/html'), 200, "Firos is running!")
        return


def get_post_params(request):
    ''' Returns from the given request its parameters which were
        posted prior.
    '''
    ctype, pdict = cgi.parse_header(request.headers.get('content-type'))
    if ctype == 'multipart/form-data':
        return cgi.parse_multipart(request.rfile, pdict)
    elif ctype == 'application/x-www-form-urlencoded':
        length = int(request.headers.getheader('content-length'))
        return cgi.parse_qs(request.rfile.read(length), keep_blank_values=1)
    elif ctype == 'application/json':
        json_data = request.rfile.read(int(request.headers['Content-Length']))

        return json.loads(json_data)
    else:
        return {}


def get_action(path, method):
    ## \brief URL checker to find what action to execute
    # \param url string
    # \param HTTP method
    for route in MAPPER[method]:
        if re.search(route['regexp'], path):
            return route
    return None


###############################################################################
#############################   Request Mapping   #############################
###############################################################################

def list_topics(request, action):
    ''' Generates a list of all topics (depending on RosConfigurator, confManager)
        and returns them back as json
    '''
    robots = get_robots(False)
    data = []
    for topic in robots.keys():
        robot_data = {"topic": topic,
                    "pubSub": robots[topic][1],
                    "messageType": robots[topic][0] }
        robot_data["structure"] = ROS_TOPIC_AS_DICT[topic]
        data.append(robot_data)

    # Return data and success
    end_request(request, ('Content-Type', 'application/json'), 200, json.dumps(data))


def on_robot_data(request, action):
    ''' Returns the actual Content of the last sent Data  of this robot onto
        the page. No Manipulation is done here. NOTE: only the data the robot published
        is shown here!

        Depending what is written after 'robot', specific content is published
    '''

    name = request.path[6:]
    if name in ROS_SUBSCRIBER_LAST_MESSAGE:
        last_pub_data = ROS_SUBSCRIBER_LAST_MESSAGE[name]
        if last_pub_data is not None:
            obj = {s: getattr(last_pub_data, s, None) for s in last_pub_data.__slots__}
            obj["id"] = name
            obj["type"] = last_pub_data._type
            json = ObjectFiwareConverter.obj2Fiware(obj, dataTypeDict=ROS_TOPIC_AS_DICT[name], ignorePythonMetaData=True, ind=None)
        else:
            json = ""
    else:
        json = ""



    # Return the Information provided by the Context-Broker
    end_request(request, ('Content-Type', 'application/json'), 200, json)


def on_connect(request, action):
    ''' This resets firos into its original state

        TODO DL reset, instead of connect?
        TODO DL Add real connect for only one Robot?
    '''
    log("INFO", "Connecting topics")
    load_msg_handlers(RosConfigurator.system_topics(True))

    # Return Success
    end_request(request, None, 200, "")


def on_disconnect(request, action):
    ''' Removes the robot specified via url like
        '/disconnect/ROBOT_ID' from ROS-Publisher and
        Ros-Subscriber

        We only are here when the URl is like:
        '/disconnect/ROBOT_ID'
    '''
    part_url = request.path
    # If at the end is a slash we remove it simply
    if "/" is part_url[-1]:
        part_url = part_url[:-1]

    # Get ROBOT_ID, which is the last element
    topic = part_url[11:] # Get everything after "/disconnect"



    # Iterate through every topic and unregister, then delete it
    if topic in ROS_PUBLISHER:
        ROS_PUBLISHER[topic].unregister()
        del ROS_PUBLISHER[topic]
        log("INFO", "Disconnecting publisher on '{}'".format(topic))
        RosConfigurator.remove_topic(topic)

    if topic in ROS_SUBSCRIBER:
        ROS_SUBSCRIBER[topic].unregister()
        del ROS_SUBSCRIBER[topic]
        log("INFO", "Disconnecting subscriber on '{}'".format(topic))
        RosConfigurator.remove_topic(topic)

    # Return success
    end_request(request, None, 200, "")



# Mapper to the methods
MAPPER = {
    "GET": [
        {"regexp": "^/topics/*$", "action": list_topics},
        {"regexp": "^/topic/.*$", "action": on_robot_data}],
    "POST": [
        {"regexp": "^/connect/*$", "action": on_connect},
        {"regexp": "^/disconnect/.*$", "action": on_disconnect}
    ]
}


def end_request(request, header, status, content):
    '''
        Ends the request via the statuscode, one header, end_headers and its content
    '''
    request.send_response(status)
    if header is not None:
        request.send_header(header[0], header[1])
    request.end_headers()
    if IS_PYTHON_3:
        request.wfile.write(bytes(content, "utf-8"))
    else:
        request.wfile.write(bytes(content))