from include.pubsub.genericPubSub import Publisher


class SomeExamplePublisher(Publisher):
    '''
        This class just needs to inherit Publisher.

        You can here specify your own Routine which should happen.
        This class publishes the data (which FIROS receives).
    '''

    def __init__(self):
        '''
            Here you can do things that need to be initialized.

            You can use the data provided by the 'config.json' here which can be retreived via:
            """self.configData""". This is not None, as long as in config.json a key exists, which
            has the same name as the subfolder this File is in.

            You can also use some other constants in:
            """from include.constants import Constants as CONSTANTS"""
        '''


    def publish(self, topic, rawMsg, msgDefinitions):
        '''
            Here goes the Routine to publish something.
            It is called automatically!
        '''
        pass

    def unpublish(self):
        '''
            Here goes the Routine to unpublish something.
            It is called automatically!
        '''
        pass