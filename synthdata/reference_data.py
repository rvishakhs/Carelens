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

# resident_life_history's narrative fields -- kept as generic templates (not tied to
# any one persona attribute) since the point is texture for the AI layer to read, not
# another dimension to correlate with clinical data.
FAMILY_BACKGROUND_SNIPPETS = [
    "Grew up one of four siblings in a close-knit family; two siblings are still living.",
    "Only child; described their childhood home as quiet but happy.",
    "Eldest of six children, took on a lot of caring responsibility for younger siblings early on.",
    "Married for over 40 years before being widowed; speaks fondly of their late spouse.",
    "Raised three children, all of whom remain in regular contact.",
    "Comes from a large extended family that still gathers every Christmas.",
    "Divorced in their 40s; closest relationship now is with a sibling rather than former in-laws.",
    "Never married; describes a close circle of lifelong friends as their real family.",
]
SIGNIFICANT_EVENTS_SNIPPETS = [
    "Emigrated to the UK in their twenties and built a life here from scratch.",
    "Lived through the Blitz as a child; rarely discusses it but it shaped a lifelong dislike of loud noises.",
    "Lost a child in infancy; family have asked staff to be sensitive if this comes up.",
    "Took early retirement to care for a spouse with a long-term illness.",
    "Ran a small business for over 20 years before retiring.",
    "Moved house eleven times for a partner's career before finally settling in this area.",
    "Survived a serious illness in their 50s that family say changed their outlook on life.",
    "Was a keen amateur sportsperson in their youth and still follows the sport closely.",
]
IMPORTANT_RELATIONSHIPS_SNIPPETS = [
    "Very close to a daughter who visits weekly and manages most day-to-day decisions.",
    "A son lives abroad but calls every Sunday without fail.",
    "A niece who was more like a daughter growing up remains the primary family contact.",
    "Closest relationship is with a lifelong friend from school who still visits regularly.",
    "Family relationships are somewhat distant; a paid companion previously provided most social contact.",
    "Grandchildren visit often and their photos are prominently displayed in the room.",
    "A former neighbour of many years still calls in for tea most weeks.",
]
CULTURAL_BACKGROUNDS = [
    "British", "Irish", "Afro-Caribbean", "South Asian (Indian)", "South Asian (Pakistani)",
    "Polish", "Welsh", "Scottish", "Jewish", "Chinese", "Nigerian", "Italian",
]

# resident_preferences-style items generated for care_plans in the new 'personal'
# domain (migration 0020) -- future/aspirational goals, distinct from the 11 clinical
# domains, matching the "what matters to me / what would I like to keep doing" strand
# of person-centred planning.
PERSONAL_ASPIRATIONS = [
    "see grandchildren more often",
    "get back into tending the garden",
    "attend church services again",
    "regain confidence walking to the lounge unaided",
    "continue painting watercolours",
    "have more one-to-one time with a favourite carer",
    "listen to more live music",
    "go on a supported outing into town",
    "keep up correspondence with old friends by letter",
    "spend more time outdoors when the weather allows",
]

# advance_care_directives.directive_type variety (migration 0004) -- previously only
# DNACPR was ever generated.
DIRECTIVE_TYPES = ["DNACPR", "ReSPECT", "advance_decision", "ceiling_of_care"]
