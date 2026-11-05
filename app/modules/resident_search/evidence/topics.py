from enum import Enum

class ResidentTopic(str, Enum):
    MOBILITY = "mobility"
    TRANSFER = "transfer"
    FALL = "fall"

    NUTRITION = "nutrition"
    HYDRATION = "hydration"

    COMMUNICATION = "communication"
    SLEEP = "sleep"

    SKIN = "skin"
    WOUND = "wound"

    CONTINENCE = "continence"
    PERSONAL_CARE = "personal_care"

    WELLBEING = "wellbeing"
    BEHAVIOUR = "behaviour"

    PAIN = "pain"
    VITALS = "vitals"
    WEIGHT = "weight"

    MEDICATION = "medication"
    APPOINTMENT = "appointment"