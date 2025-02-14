import enum
import os
import random

from tale.races import BodyType
import json

class WearLocation(enum.Enum):
    FULL_BODY = 0 # robes etc, covers TORSO, ARMS, LEGS
    HEAD = 1
    FACE = 2
    NECK = 3
    TORSO = 4
    ARMS = 5
    HANDS = 6
    LEGS = 7
    FEET = 8
    WAIST = 9 # belts etc
    BACK = 10 # backpacks etc
    UNDER_GARMENTS = 11 # underwear etc

    @classmethod
    def has_value(cls, value):
        return value in cls._member_names_

wearable_colors = ['black', 'green', 'blue', 'red', 'yellow', 'white', 'brown', 'grey', 'purple', 'orange', 'pink', 'cyan', 'magenta']

def load_wearables_from_json(file_path):
    with open(os.path.realpath(os.path.join(os.path.dirname(__file__), file_path)), 'r') as file:
        data = json.load(file, strict=False)["wearables"]
        for item in data:
            item['location'] = WearLocation[item['location']]
            item['type'] = 'Wearable'
        return data
    
wearables_fantasy = load_wearables_from_json('../items/wearables_fantasy.json')
wearables_modern = load_wearables_from_json('../items/wearables_modern.json')
wearbles_story = []

dressable_body_types = [BodyType.HUMANOID, BodyType.SEMI_BIPEDAL, BodyType.WINGED_MAN]

def body_parts_for_bodytype(bodytype: BodyType) -> list:
    if bodytype in dressable_body_types:
        return list(WearLocation)[1:-3]
    if bodytype == BodyType.QUADRUPED:
        return [WearLocation.HEAD, WearLocation.LEGS, WearLocation.TORSO, WearLocation.FEET, WearLocation.NECK]
    return None

def random_wearable_for_body_part(bodypart: WearLocation, setting: str = 'fantasy', armor_only = False) -> dict:
    wearables = []
    if setting == 'fantasy':
        wearables = wearables_fantasy
    elif setting == 'modern' or setting == 'sci-fi' or setting == 'post-apocalyptic':
        wearables = wearables_modern
    wearables.extend(wearbles_story)
    available_wearables = [item for item in wearables if item['location'] == bodypart and (not armor_only or item.get('ac', 0) > 0)]
    if not available_wearables:
        return None
    wearable = random.choice(available_wearables)
    wearable['short_descr'] = f"{random.choice(wearable_colors)} {wearable['name']}"
    return wearable

def add_story_wearables(wearables: list):
    wearbles_story.extend(wearables)