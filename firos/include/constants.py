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




import json
import socket

class Constants:
    configured = False
    PATH = None
    DATA = None
    # All Constants with their default value!
    LOGLEVEL = "INFO"

    EP_SERVER_ADRESS = None
    EP_SERVER_PORT = None
    MAP_SERVER_PORT = 10100
    ROSBRIDGE_PORT = 9090
    PUB_FREQUENCY = 0               # In Milliseconds

    ROS_NODE_NAME = "firos"
    ROS_SUB_QUEUE_SIZE = 10

    @classmethod
    def set_configuration(cls, path):
        try:
            data = json.load(open(path + "/config.json"))
            return data[data["environment"]]
        except:
            return {}

    @classmethod
    def init(cls, path):
        if not cls.configured:
            cls.configured = True
            cls.PATH = path

            config_data = cls.set_configuration(path)
            cls.DATA = config_data

            if "log_level" in config_data:
                cls.LOGLEVEL = config_data["log_level"]

            if "server" in config_data and "port" in config_data["server"]:
               cls. MAP_SERVER_PORT = config_data["server"]["port"]

            if "node_name" in config_data:
                cls.ROS_NODE_NAME = config_data["node_name"]

            if "ros_subscriber_queue" in config_data:
                cls.ROS_SUB_QUEUE_SIZE = int(config_data["ros_subscriber_queue"])

            if "endpoint" in config_data and "address" in config_data["endpoint"]:
                    cls.EP_SERVER_ADRESS = config_data["endpoint"]["address"]
            else:
                # If not set, we get ourselves the ip-address
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.connect(("8.8.8.8", 80))
                cls.EP_SERVER_ADRESS = sock.getsockname()[0]

            if "endpoint" in config_data and "port" in config_data["endpoint"]:
                    cls.EP_SERVER_PORT = int(config_data["endpoint"]["port"])

            if "rosbridge_port" in config_data:
                cls.ROSBRIDGE_PORT = int(config_data["rosbridge_port"])

            if "pub_frequency" in config_data:
                cls.PUB_FREQUENCY = int(config_data["pub_frequency"])