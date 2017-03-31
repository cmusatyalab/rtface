class RTFace:

    def __init__(self, dict):
        self.dict = dict

    def __str__(self):
        return "rtface<{}>".format(self)

    def push(self):
        '''
        push an image for real-time recognition
        :return: an old image with recognized faces
        '''
        pass

    def pop(self):
        '''
        retrive the oldest image in the processing queue
        :return:
        '''
