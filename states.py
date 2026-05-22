from enum import Enum

class OrderState(Enum):
    IDLE      = "idle"
    ORDERING  = "ordering"
    ADDRESS   = "address"
    PHONE     = "phone"
    CONFIRM   = "confirm"