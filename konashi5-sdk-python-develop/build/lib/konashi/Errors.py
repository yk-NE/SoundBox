#!/usr/bin/env python3


class KonashiError(Exception):
    pass

class KonashiConnectionError(Exception):
    pass

class KonashiInvalidError(Exception):
    pass

class KonashiDisabledError(Exception):
    pass

class NotFoundError(Exception):
    pass

class InvalidDeviceError(Exception):
    pass

class PinInvalidError(Exception):
    pass

class PinUnavailableError(Exception):
    pass

