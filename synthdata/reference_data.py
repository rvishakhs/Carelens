"""Realistic reference data for a UK residential care home. Kept as plain lists/tuples
(not enums) since these aren't schema constraints -- the schema's actual enum labels
live in migrations/versions/0001_extensions_enums_helpers.py and are read at runtime
via Schema.enum_values() in db.py, not duplicated here."""

RESIDENT_FIRST_NAMES = [
    "Margaret", "Arthur", "Doris", "Frank", "Joan", "Stanley", "Elsie", "Norman",
    "Vera", "Reginald", "Winifred", "Cyril", "Gladys", "Leonard", "Ivy", "Bernard",
    "Hilda", "Wilfred", "Nora", "Sidney", "Muriel", "Alfred", "Edna", "Herbert",
]
RESIDENT_LAST_NAMES = [
    "Baker", "Whitfield", "Nolan", "Carver", "Meredith", "Ogden", "Fenwick", "Pryor",
    "Sutcliffe", "Marchant", "Hollis", "Tremaine", "Ashworth", "Goodwin", "Kirby",
]

STAFF_FIRST_NAMES = [
    "Sarah", "James", "Priya", "Michael", "Amara", "David", "Grace", "Kwame",
    "Emily", "Tom", "Fatima", "Chris", "Aisha", "Ben", "Olusegun", "Chloe",
]
STAFF_LAST_NAMES = [
    "Adeyemi", "Walsh", "Chowdhury", "Novak", "Byrne", "Okafor", "Sinclair",
    "Malhotra", "Fitzgerald", "Nwosu", "Osei", "Doyle",
]

# (relationship, is_next_of_kin more likely for these)
FAMILY_RELATIONSHIPS = ["daughter", "son", "granddaughter", "grandson", "niece", "nephew", "sister", "brother"]

# (condition_name, icd10_code) -- common in UK residential/nursing care populations
DIAGNOSES = [
    ("Alzheimer's disease", "G30.9"),
    ("Vascular dementia", "F01.9"),
    ("Type 2 diabetes mellitus", "E11.9"),
    ("Essential hypertension", "I10"),
    ("Atrial fibrillation", "I48.9"),
    ("Chronic obstructive pulmonary disease", "J44.9"),
    ("Osteoarthritis", "M19.9"),
    ("Chronic kidney disease stage 3", "N18.3"),
    ("Parkinson's disease", "G20"),
    ("Depression", "F32.9"),
    ("Osteoporosis", "M81.0"),
    ("Ischaemic heart disease", "I25.9"),
    ("Hypothyroidism", "E03.9"),
    ("Previous cerebrovascular accident (stroke)", "I69.4"),
    ("Urinary incontinence", "N39.3"),
]

ALLERGENS = [
    ("Penicillin", "rash", "moderate"),
    ("Peanuts", "anaphylaxis", "anaphylaxis"),
    ("Latex", "contact dermatitis", "mild"),
    ("Aspirin", "gastrointestinal bleeding", "moderate"),
    ("Shellfish", "swelling", "moderate"),
    ("Sulfa drugs", "rash", "mild"),
    ("Codeine", "nausea", "mild"),
]

# (drug_name, dose, route, is_prn, prn_indication) -- realistic UK care-home formulary
REGULAR_MEDICATIONS = [
    ("Atorvastatin", "20mg", "oral"),
    ("Amlodipine", "5mg", "oral"),
    ("Ramipril", "2.5mg", "oral"),
    ("Omeprazole", "20mg", "oral"),
    ("Metformin", "500mg", "oral"),
    ("Levothyroxine", "50mcg", "oral"),
    ("Furosemide", "40mg", "oral"),
    ("Sertraline", "50mg", "oral"),
    ("Donepezil", "10mg", "oral"),
    ("Apixaban", "5mg", "oral"),
    ("Bisoprolol", "2.5mg", "oral"),
    ("Senna", "7.5mg", "oral"),
    ("Co-codamol 30/500", "1 tablet", "oral"),
    ("Alendronic acid", "70mg", "oral"),
]
PRN_MEDICATIONS = [
    ("Paracetamol", "1g", "oral", "for pain or pyrexia"),
    ("Lorazepam", "0.5mg", "oral", "for agitation or distress"),
    ("Buccal midazolam", "10mg", "other", "for prolonged seizure"),
    ("GTN spray", "400mcg", "other", "for chest pain"),
    ("Cyclizine", "50mg", "oral", "for nausea"),
]

PREFERENCE_ITEMS = {
    "food": [
        ("likes a cooked breakfast", True),
        ("prefers tea over coffee", True),
        ("dislikes fish", False),
        ("enjoys a dessert after dinner", True),
        ("does not like spicy food", False),
        ("prefers smaller portions", True),
    ],
    "routine": [
        ("likes curtains open at night", True),
        ("prefers a lie-in on Sundays", True),
        ("likes the radio on in the morning", True),
        ("dislikes being woken before 8am", False),
    ],
    "personal_care": [
        ("prefers a female carer for personal care", True),
        ("likes to choose their own clothes", True),
        ("prefers a shower over a bath", True),
        ("dislikes having hair washed", False),
    ],
    "social": [
        ("enjoys one-to-one conversation over group activities", True),
        ("likes to sit near the window", True),
        ("enjoys visits from the therapy dog", True),
        ("finds large groups overwhelming", False),
    ],
    "environment": [
        ("prefers the room a little cooler", True),
        ("likes a nightlight left on", True),
        ("dislikes loud television", False),
    ],
}

OCCUPATIONS = [

    "schoolteacher", "coal miner", "seamstress", "bus driver", "shopkeeper",
    "nurse", "factory worker", "postal worker", "farmer", "typist", "carpenter",
]
HOBBIES = [
    "gardening", "knitting", "watching cricket", "baking", "crossword puzzles",
    "ballroom dancing", "birdwatching", "painting watercolours", "listening to jazz",
]
FAITHS = ["Church of England", "Roman Catholic", "Methodist", "none", "Sikh", "Muslim", "Jewish"]

ACTIVITY_CALENDAR = [
    ("Armchair exercise", "physical"),
    ("Bingo", "social"),
    ("Music and memories", "cognitive"),
    ("Arts and crafts", "creative"),
    ("Garden club", "physical"),
    ("Sunday service", "spiritual"),
    ("Movie afternoon", "social"),
    ("Reminiscence group", "cognitive"),
]
