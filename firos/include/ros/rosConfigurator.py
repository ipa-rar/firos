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

import os
import re
import json
import rostopic
import rospy

from include.constants import Constants as C


entries = [] # Entries we found in the ROS-World
whitelist = {} # The Current Whitelist FIROS is currently using
robots = {} # The dictionary containing: robots["topics"] = [MessageType, pubSub]

class RosConfigurator:
    '''
        RosConfigurator -> This is an OLD Name
        This loads the Whitelist.json and generates the first
    '''

    @staticmethod
    def getAllTopics(refresh=True):
        '''
            this retrieves all Entries/Topics found in the current
            ROS-World. The Parameter, refresh, indicates, whether we want to
            update our current information abour the entries or not
        '''
        global entries
        if refresh or len(entries) == 0:
            listOfData = rospy.get_published_topics()
            entries = [item for sublist in listOfData for item in sublist if item.startswith("/")]

        return entries


    @staticmethod
    def getWhiteList(restore=False):
        '''
            This retrieves the Whitelist.json Configuration
            and overwrites the data, depending on the restore-Flag
        '''
        global whitelist
        if whitelist == {} or restore:
            if not os.path.isfile(C.PATH + "/whitelist.json"):
                return {}
            json_path = C.PATH + "/whitelist.json"
            whitelist = json.load(open(json_path))

        return whitelist


    @staticmethod
    def systemTopics(refresh=False, restore=False):
        '''
            This generates the actual robots-Structure
            At First the Regex-Expressions are generated, then the Robot with the
            topic is added iff it exists in the ROS-World.

            refresh: Refreshes the ROS-World Information if set to True AND the robots dictionary
            restore: Restores the Whitelist to the original Whitelist.json-File
                     if set to True
        '''
        global entries
        global whitelist
        global robots
        if refresh:
            # Only Update robots if we want to
            entries = RosConfigurator.getAllTopics(refresh=refresh)
            whitelist = RosConfigurator.getWhiteList(restore=restore)

            # Create the robots Structure
            _robots = {}

            if "publisher" in whitelist:
                for regex in whitelist["publisher"]:
                    RosConfigurator.addRobots(_robots, regex, entries, "publisher")

            if "subscriber" in whitelist:
                for regex in whitelist["subscriber"]:
                    RosConfigurator.addRobots(_robots, regex, entries, "subscriber")

            robots = _robots
        return robots


    @staticmethod
    def addRobots(robots, regex, entries, pubsub):
        '''
            This adds the Entry in the complex robots dictionary
            We iterate over each entry and initialize the robots-dict
            appropiately. Then It is simply added.

            robots: The dictionary robots["topics"] = [MessageType , pubSub]
            regex:  The Regex we try to match in each entry
            entries:The String Entries. Each element is in the following
                    structure "/ROBOT_ID/TOPIC_NAME"
            pubsub: A String. Either "publisher" or "subscriber"
        '''
        for entry in entries:
            matches = re.search(regex, entry)
            if matches is not None:
                # We found a Match. Now add it to robots

                if entry not in robots:
                    # if not already added, add it
                    topic_type, _, _ = rostopic.get_topic_type(entry)
                    robots[entry] = [topic_type ,pubsub]


    @staticmethod
    def removeTopic(topic):
        '''
            This removes the topic
        '''
        global robots
        if topic in robots:
            del robots[topic]


    @staticmethod
    def setWhiteList(additions, deletions, restore=False):
        '''
            This Adds or deletes entries inside the whitelist
        '''
        global whitelist


        if additions:
            for robot_name in additions:
                whitelist[robot_name] = additions[robot_name]

        if deletions:
            for robot_name in deletions:
                if robot_name in whitelist:
                    for topic in deletions[robot_name]["publisher"]:
                        if topic in whitelist[robot_name]["publisher"]:
                            whitelist[robot_name]["publisher"].remove(topic)
                    for topic in deletions[robot_name]["subscriber"]:
                        if topic in whitelist[robot_name]["subscriber"]:
                            whitelist[robot_name]["subscriber"].remove(topic)

        if restore:
            whitelist = RosConfigurator.getWhiteList(restore=True)
