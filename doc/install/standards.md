# Creating new Standards

FIROS now allows to implement custom standards to do multiple publications of data on multiple platforms with only one
instance. In order to write a new standard, where the ROS-Messages are transformed in your standard and vice-versa, you
need to think about the following:

-   Think of a name for your standard. In this example we choose `testbroker`
-   Does your standard need any Configuration to work porperly? A server might need an `address` or `port`. Or if you
    simply want to save all received messages along on the hard drive, you might want to consider adding a `filename`.
-   Is your standard programmatically callable? And is it possible that in return it notifies you about changes, which
    you might want to translate back into the ROS-World?

The following subchapters will give you a brief guide on how to create a custom `Publisher` and `Subscriber` for FIROS.
An example Implementation can already be found in FIROS: the `contextbroker`-standard!

## Standard-Name

After creating the standards name you can directly go ahead and create the folder in `firos/include/pubsub/` with your
standards name. This is crucial, since FIROS only looks inside the `pubsub`-folder for new standards and recognizes them
by the name you named your folder. In this example we created the folder `examplePubSub`.

**Note**: Do not forget to also add a `__init__.py` inside this folder, since Python needs this file in order to Import
other files inside this folder.

## Adding Configuration-Parameters

With the new Folder you created, you are now able to add Configuration-Parameters specifically for each `Publisher` and
`Subscriber` inside this folder. Here is an example for specific Parameters for the `examplePubSub`-Standard:

```json
{
    "environment": "local",
    "local": {
        "server": {
            "port": 10100
        },
        "contextbroker": {
            "address": "localhost",
            "port": 1026
        },
        "examplePubSub": {
            "myParam": "SomeString",
            "PortOrSomeInt": 12345
        },
        "log_level": "INFO"
    }
}
```

You decide which Parameters should be added and how they are represented in `json`. Those Parameters can be later
retrieved easily and is described further below.

## Writing the first Publisher

In this case a Publisher is a class, which publishes received data from the ROS-WORLD and converts and delegates it into
the Non-ROS-World (your custom Standard). The file `genericPubSub.py` contains an abstract class `Publisher` which you
just need to inherit from. Create a Python-file in your newly created folder (you can name it as you like) and add the
following content:

```python
from include.pubsub.genericPubSub import Publisher

class SomeExamplePublisher(Publisher):

    def __init__(self):
      pass

    def publish(self, topic, raw_msg, msg_definitions):
        pass

    def unpublish(self):
        pass
```

The Publisher is the easiest part to write, since the methods `publish` and `unpublish` (which need to be implemented)
are called automatically by FIROS. The `publish`-method is called once, every time FIROS receives a new Message. For
more details and what each Parameter contains, please follow the comments in the `contextbroker`-standard.

The `unpublish`-method is called once. Exactly then, when FIROS wants to shut down. Does your standard need to know that
FIROS is shutting down? Then implement this appropriately!

The `self`-instance also contains your custom described configuration and can be accessed via : `self.config_data`.
**NOTE** It returns `None` if nothing was specified.

## Writing the first Subscriber

The Subscriber does the opposite of a Publisher. It receives Messages from the Non-ROS-World and translate them back
into the ROS-World. Similar to the Publisher you also need to implement the abstract class `Subscriber` as follows:

```python
from include.pubsub.genericPubSub import Subscriber
from include.ros.topicHandler import RosTopicHandler

class SomeExampleSubscriber(Subscriber):

    def __init__(self):
      pass

    def subscribe(self, topic_list, msg_definitions):
        pass

    def unsubscribe(self):
        pass
```

The Subscriber is more trickier. Here the `subscribe` method gets only called once during start up (or multiple times
during a restart, which may happen!). You need to write a mechanism inside the method `subscribe`, so that your standard
is able to contact FIROS.

The `contextbroker`-standard achieves this via creating a very own `HTTPServer` in a new Thread, which listens on a
specific port, where the actual Context-Broker can message it with updates. But receiving Messages from the standard is
not enough to actually publish them onto the ROS-World.

The received Messages need to be converted into a special class which can be directly retrieved from the
`ObjectFiwareConverter` . Also the Message-Definitions (`msgDefintions`) might help.

After the received Message is converted correctly, you can publish it via:

```python
RosTopicHandler.publish(topic, converted_data, data_struct):
```

and it should be published in the ROS-World automatically!

You might also consider the `context-broker`-standard Implementation, which is well documented.

As in Publisher, the `unsubscribe`-method is called during shut down. If your standard needs some special shut down
routine implement it here.

**NOTE** The `self`-instance here also contains your custom described configuration and can be accessed via :
`self.config_data`. It returns `None` if nothing was specified!

# Remarks

The standards you want to implement need to be at the at the root of you standard-folder. E. g.
`firos/include/pubsub/YOUR_STANDARD/YOUR_FILE.py`. If they are located in subfolders, they won't be imported and
executed.

It is possible to write mulitple Publishers and multiple Subscribers in one custom standard. A standard does not
necessarily needs a Publisher AND a Subscriber. It is up to you, what you want to publish/subscribe

You can also customly name your Publish/Subscribe-class.
