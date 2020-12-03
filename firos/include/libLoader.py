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
import imp
import importlib
import sys

try:
    import roslib.message
    import rostopic
except ImportError:
    pass

# Add genpy to sys.path (This is not written as a module)
from genpy.generator import MsgGenerator
from include.logger import Log
sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "/genpy/src/")

regex = re.compile(u'^(.*)(\\b.msg\\b)(.*)$')


class LibLoader:
    ''' LibLoader is a class which tries to retrieve the python class of
        specific ROS-Messages. First it tries to retrieve it via the standard
        python import module. If this fails, it checks the folder FIORS/msgs for the
        specific message. If the '.msg'-File is missing in the corresponding folder (or
        the class could not be generated), this LibLoader tries to load the message via
        roslib. If every method fails FIROS will shutdown, since FIROS need the messages
        due to rospy beforehand. At least for The Subscriptions and Publishes defined in
        'topics.json'
    '''

    # Our custom search path for genpy
    searchpath = dict()
    systemPath = dict()
    isGenerated = False # Check if Generated


    @staticmethod
    def _init_search_path(path):
        ''' Initializes the search path for genpy.
            In this case we add all directory-names into the search path which
            are available in path and try to retrieve available Message from the System

            'namespace' still needs to be set to the actual package of the Message
        '''
        LibLoader._init_searchpath_for_available_msgs_on_system()
        if len(LibLoader.searchpath) == 0:
            # Initialize seachpath
            subdirs = [x[0] for x in os.walk(path)] # get all directories inside path
                                                    # (including itself)
            subdirs = subdirs[1:] # Remove reference to itself
            LibLoader.searchpath = LibLoader.systemPath # 'Copy' to Searchpath
            for subdir in subdirs:
                # Append from specified path
                subdir_name = subdir.split("/")[-1]
                if subdir_name in LibLoader.searchpath:
                    LibLoader.searchpath[subdir_name].append(subdir)
                else:
                    LibLoader.searchpath[subdir_name] = [subdir]

        return LibLoader.searchpath

    @staticmethod
    def _init_searchpath_for_available_msgs_on_system():
        ''' Initializes the systempath for genpy for available Messages.
            To achieve this, we use the Environment-Variable 'ROS_PACKAGE_PATH'
            which usually should be available.
        '''

        if len(LibLoader.systemPath) != 0:
            # SystemPath is already initialized
            return

        if "ROS_PACKAGE_PATH" not in os.environ:
            Log("WARNING", "The ENV 'ROS_PACKAGE_PATH' is not set. Unable to search for Messages"
                + " on this system")


        pkgs_paths = os.environ.get('ROS_PACKAGE_PATH').split(":")
        searchpath = dict()

        for pkg_path in pkgs_paths:
            # Retrieve all folder and Files from pkg_path which ends with ".msg"
            result = [os.path.join(dp, f) for dp, dn, filenames in os.walk(pkg_path)
                        for f in filenames if os.path.splitext(f)[1] == '.msg']
            for found_msg in result:
                # found_msg is like '/opt/.../share/PACKAGE_NAME/msg/THE_MESSAGE.msg'

                # with very few exceptions (in case CMakeLists.txt tells Catkin to look for the
                # Messages in another Folder)
                
                # TODO DL Maybe we can look inside the parent folders for the nearest
                # CMakeLists.txt-File. The pkg_name is then the folder name, where the
                # CMakeLists.txt-File is (always the case?)
                if "/firos/" in  found_msg:
                    # Skip the Project itself
                    continue

                path_parts = found_msg.split("/")
                pkg_name = path_parts[path_parts.index("msg")-1]

                if pkg_name in searchpath:
                    # Skip already added package
                    continue

                # Retrieve Package Folder and add it to the searchpath
                path = '/'.join(path_parts[0:path_parts.index("msg")]) + "/msg"
                searchpath[pkg_name] = [path]

        LibLoader.systemPath = searchpath


    @staticmethod
    def loadFromSystem(msgType, topic):
        ''' This actually tries all three methods mentioned above.
        '''
        splits = msgType.split("/")

        if len(splits) == 2:
            module_name = splits[0] # PACKAGE
            module_msg = splits[1] # MESSAGE


            #####  1: Try to load it via Python-Import
            try:
                module = importlib.import_module(module_name + ".msg")
                clazz = getattr(module, module_msg)
                return clazz
            except ImportError:
                Log("WARNING", "Message {} was not found.".format(module_msg)
                    + "Trying to load the Message-File in FIROS/msgs")
            except AttributeError:
                Log("WARNING", "Message {} was not found.".format(module_msg)
                    + "Trying to load the Message-File in FIROS/msgs")



            ##### 2: Try to load the Message given the Message-files inside FIROS/msgs
            current_path = os.path.dirname(os.path.abspath(__file__))
            msgsFold = current_path + "/../../msgs/" # FIROS/msgs - Folder
            search_path = LibLoader._init_search_path(msgsFold)
            search_path["namespace"] = module_name
            try:
                # Disable Output, since genpy prints exceptions
                sys.stdout = open(os.devnull, "w")
                sys.stderr = open(os.devnull, "w")
                retcode = MsgGenerator().generate_messages( module_name,
                                                            [msgsFold + module_name + "/"
                                                                + module_msg + ".msg"],
                                                            msgsFold + module_name, search_path)
            except Exception:
                # Case we got an Exception -> retcode = 1 -> Error
                retcode = 1
                pass
            finally:
                # Enable Output again
                sys.stdout = sys.__stdout__
                sys.stderr = sys.__stderr__

            if retcode == 1:
                Log("WARNING", "Could not load Message {}/{}.".format(module_name, module_msg)
                    + "Maybe it references other missing Messages?")
            elif retcode == 0:
                LibLoader.isGenerated = True
                module = imp.load_source(module_msg,
                                        msgsFold + module_name + "/_" + module_msg + ".py")
                clazz = getattr(module, module_msg)
                Log("INFO", "Message {}/{} succesfully loaded.".format(module_name, module_msg))
                return clazz



            ##### 3: Our last resort, the roslib.message which might know this message!
            try:
                type_name = rostopic.get_topic_type(topic, blocking=False)[0]
                if type_name:
                    clazz = roslib.message.get_message_class(type_name)
                    Log("INFO", "Message {}/{}".format(module_name, module_msg)
                        + "loaded via roslib.message!")
                    return clazz
            except Exception:
                pass


        ### Message could not be loaded or the regex does not match
        Log("ERROR", "Unable to load the Message: {} on this System.".format(msgType))
        exit()
