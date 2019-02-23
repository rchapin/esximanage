
class DottedDict(dict):

    def __getattr__(self, k):
        return self[k]

    def __setattr__(self, k, v):
        if k in self.__dict__:
            self.__dict__[k] = v
        else:
            self[k] = v
