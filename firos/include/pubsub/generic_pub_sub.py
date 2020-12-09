# MIT License
#
# Copyright (c) 2019 Fraunhofer IML
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
__credits__ = ["Dominik Lux"]
__maintainer__ = "Dominik Lux"


import sys
import os
import abc
import inspect

from include.constants import Constants as C

# ABC compatibility with Python 2 and 3
ABC = abc.ABCMeta('ABC', (object,), {'__slots__': ()})

class Publisher(ABC):
    '''
        Abstract Publisher. Import this and set it as base
        to write your own Publisher
    '''

    # Data which is added via config.json
    # This will be initialized before__init__() is even called!
    config_data = dict()

    @abc.abstractmethod
    def publish(self, topic, raw_msg, msg_definitions):
        pass

    @abc.abstractmethod
    def unpublish(self):
        pass


class Subscriber(ABC):
    '''
        Abstract Subscriber. Import this and set it as base
        to write your own Subscriber
    '''

    # Data which is added via config.json
    # This will be initialized before__init__() is even called!
    config_data = dict()

    @abc.abstractmethod
    def subscribe(self, topic_list, topic_types, msg_definitions):
        pass

    @abc.abstractmethod
    def unsubscribe(self):
        pass


class PubSub(object):
    '''
        This is a generic Publisher and Subscriber class which contains all
        defined Publishers and Subscribers. It automatically loads the classes,
        which inherit from the above defined Publisher/Subscriber-class and are in
        a subfolder (depending on this files location).

        This class maps the calls 'publish', 'unpublish', 'subscribe' and 'unsubscribe'
        to each Publisher and Subscriber.
    '''

    publishers = []
    subscribers = []

    def __init__(self):
        '''
            This Routine imports all publisher and subscriber and saves them into the list.

            We retreive here all classes which are in the subfolder (depending on
            the files location).

            Each subfolder should contain an '__init__.py' and the corresponding
            Publishers and Subscribers you want to add.
        '''
        folder = os.path.dirname(os.path.realpath(__file__))
        folder_info = os.listdir(folder)


        ### Get all subfolders (only 1 deeper)
        subfolders = {}
        for folder_i in folder_info:
            if not folder_i.startswith("_") and os.path.isdir(folder + os.path.sep + folder_i):
                subfolders[folder_i] = {}

        ### Get all Files inside those subfolders
        for i in subfolders.keys():
            for _, _, files in os.walk(folder + os.path.sep + i):
                for file in files:
                    if not file.startswith("_"):
                        subfolders[i][file.split(".")[0]] = None

        ### Import the modules, defined in the files
        for fold in subfolders.keys():
            for fil in subfolders[fold].keys():
                module_def = "include.pubsub." + fold + "." + fil
                __import__(module_def) # module needs to be imported manually!
                clsmembers = inspect.getmembers(sys.modules[module_def], \
                    lambda member: inspect.isclass(member) and member.__module__ == module_def)
                for clazz in clsmembers:
                    subfolders[fold][fil] = clazz[1]

        ### Distinguish between Subscribers and Publishers and add them appropiatly
        for fold in subfolders.keys():
            for fil in subfolders[fold].keys():
                # initialize config data
                subfolders[fold][fil].config_data = self._get_pub_sub_constants(fold)
                if subfolders[fold][fil].__base__ is Subscriber:
                    # We found a Subscriber
                    self.subscribers.append(subfolders[fold][fil]())
                elif subfolders[fold][fil].__base__ is Publisher:
                    # We found a Publisher
                    self.publishers.append(subfolders[fold][fil]())
                else:
                    # We do nothing to other classes
                    pass

        pass

    def _get_pub_sub_constants(self, fold):
        '''
            Depending on the Folder-Name the corresponding entry of Constants is loaded
        '''
        try:
            return C.DATA[fold]
        except:
            return None


    def publish(self, topic, raw_msg, msg_definitions):
        '''
            Call publish on each Publisher
        '''
        for pub in self.publishers:
            pub.publish(topic, raw_msg, msg_definitions)


    def unpublish(self):
        '''
            Call unpublish on each Publisher
        '''
        for pub in self.publishers:
            pub.unpublish()

    def subscribe(self, topic_list, topic_types, msg_definitions):
        '''
            Call subscribe on each Subscriber
        '''
        for sub in self.subscribers:
            sub.subscribe(topic_list, topic_types, msg_definitions)

    def unsubscribe(self):
        '''
            Call unsubscribe on each Subscriber
        '''
        for sub in self.subscribers:
            sub.unsubscribe()
