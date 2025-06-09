from leancloud import Object

class Memory(Object):
    pass

# Bind to the correct class name in LeanCloud
Memory = Object.extend('memories')
