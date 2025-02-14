import datetime
import json
from typing import List
from tale import load_items, util
from tale.base import Exit, Living, Location, Weapon, Wearable
from tale.coord import Coord
from tale.driver_if import IFDriver
from tale.item_spawner import ItemSpawner
from tale.items.basic import Boxlike, Drink, Food, Health
from tale.mob_spawner import MobSpawner
from tale.npc_defs import Trader
from tale.races import BodyType
from tale.story import GameMode, MoneyType
from tale.skills.weapon_type import WeaponType
from tale.story_context import StoryContext
from tale.wearable import WearLocation
from tale.zone import Zone
import tale.parse_utils as parse_utils


class TestParseUtils():

    
    def test_load_json(self):
        assert(parse_utils.load_json("tests/files/test.json"))
        
    def test_load_locations(self):
        room_json = parse_utils.load_json("tests/files/test_locations.json")
        zones, exits = parse_utils.load_locations(room_json)
        room_one = zones['test house'].get_location('test room')
        assert(room_one.name == 'test room')
        assert(room_one.description == 'test room description')
        room_two = zones['test house'].get_location('test room 2')
        assert(room_two.name == 'test room 2')
        assert(room_two.description == 'test room 2 description')
        assert(len(room_two.exits) == 2)
        assert(room_two.exits['north'].target == room_one)
        assert(room_two.exits['test room'].target == room_one)

        assert(exits[0].__repr__().startswith("(<base.Exit to 'test room 2'"))

    def test_load_story_config(self):
        config_json = parse_utils.load_json("tests/files/test_story_config.json")
        config = parse_utils.load_story_config(config_json)
        assert(config)
        assert(config.name == 'Test Story Config 3')
        assert(config.money_type == MoneyType.NOTHING)
        assert(config.supported_modes == {GameMode.IF})
        assert(config.zones == ["test zone"])

        config.context = StoryContext().from_json({'base_story': 'Base context', 'current_context': 'Current context'})

        stored_config = parse_utils.save_story_config(config)

        new_config = parse_utils.load_story_config(stored_config)
        assert(isinstance(new_config.context, StoryContext))
        
    def test_connect_location_to_exit(self):
        """ This simulates a room having been generated before"""

        cave_entrance = Location('Cave entrance', 'A dark cave entrance')
        new_location = Location('Royal grotto', 'A small grotto, fit for a kobold king')
        exit_to = Exit(directions=['north', 'Royal grotto'], target_location=new_location, short_descr='There\'s an opening that leads deeper into the cave', enter_msg='You enter the small crevice')
        cave_entrance.add_exits([exit_to])
        # the room has now been 'built' and is being added to story
        parse_utils.connect_location_to_exit(new_location, cave_entrance, exit_to)
        assert(len(cave_entrance.exits) == 2)
        assert(cave_entrance.exits['north'].target == new_location)
        assert(cave_entrance.exits['Royal grotto'].target == new_location)
        assert(len(new_location.exits) == 2)
        
        assert(new_location.exits['south'].target == cave_entrance)
        assert(new_location.exits['cave entrance'].target == cave_entrance)
        assert(new_location.exits['cave entrance'].short_description == f'You can see {cave_entrance.name}')

    def test_opposite_direction(self):
        assert(parse_utils.opposite_direction('north') == 'south')
        assert(parse_utils.opposite_direction('south') == 'north')
        assert(parse_utils.opposite_direction('east') == 'west')
        assert(parse_utils.opposite_direction('west') == 'east')
        assert(parse_utils.opposite_direction('up') == 'down')
        assert(parse_utils.opposite_direction('down') == 'up')
        assert(parse_utils.opposite_direction('in') == 'out')
        assert(parse_utils.opposite_direction('out') == 'in')
        assert(parse_utils.opposite_direction('hubwards') == None)

    def test_parse_generated_exits(self):
        exits = json.loads('{"exits": [{"name": "The Glacier", "short_descr": "A treacherous path leads up to the icy expanse, the sound of creaking ice echoing in the distance", "enter_msg":"You enter the glacier"}, {"name": "The Cave", "short_descr": "A dark opening in the side of the mountain, rumored to be home to a mysterious creature"}, {"name": "The Forest", "short_descr": "A dense thicket of trees looms in the distance, their branches swaying in the wind"}]}')
        exit_location_name = 'Entrance'
        location = Location(name='Outside')
        new_locations, parsed_exits = parse_utils.parse_generated_exits(exits=exits.get('exits'), 
                                                                        exit_location_name=exit_location_name, 
                                                                        location=location)
        assert(len(new_locations) == 3)
        assert(new_locations[0].name == 'Glacier')
        assert(new_locations[1].name == 'Cave')
        assert(new_locations[2].name == 'Forest')
        assert(len(parsed_exits) == 3)
        assert(parsed_exits[0].name == 'glacier')
        assert(parsed_exits[1].name == 'cave')
        assert(parsed_exits[2].name == 'forest')
        assert(parsed_exits[0].short_description == 'You see a treacherous path leads up to the icy expanse, the sound of creaking ice echoing in the distance.')
        assert(parsed_exits[1].short_description == 'You see a dark opening in the side of the mountain, rumored to be home to a mysterious creature.')
        assert(parsed_exits[2].short_description == 'You see a dense thicket of trees looms in the distance, their branches swaying in the wind.')
        assert(parsed_exits[0].enter_msg == 'You enter the glacier')

    def test_parse_generated_exits_duplicate_direction(self):
        exits = json.loads('{"exits": [{"name": "The Glacier", "direction": "north", "short_descr": "A treacherous path."}, {"name": "The Cave", "direction": "north", "short_descr": "A dark opening."}]}')
        exit_location_name = 'Entrance'
        location = Location(name='Outside')
        new_locations, parsed_exits = parse_utils.parse_generated_exits(exits=exits.get('exits'), 
                                                                        exit_location_name=exit_location_name, 
                                                                        location=location)
        location.add_exits(parsed_exits)
        assert(len(parsed_exits) == 2)
        assert(parsed_exits[0].names == ['glacier', 'north'])
        assert(parsed_exits[0].short_description == 'To the north you see a treacherous path.')
        assert(parsed_exits[1].names == ['cave', 'south'])
        assert(parsed_exits[1].short_description == 'To the south you see a dark opening.')
        
        exits2 = json.loads('{"exits": [{"name": "The Ice Cliff", "direction": "north", "short_descr": "A steep fall."}, {"name": "The Icicle Forest", "direction": "east", "short_descr": "A forest of ice."}]}')

        new_locations, parsed_exits = parse_utils.parse_generated_exits(exits=exits2.get('exits'),
                                                                        exit_location_name='cave',
                                                                        location=new_locations[1])

        assert(parsed_exits[0].names == ['ice cliff', 'south'])
        assert(parsed_exits[1].names == ['icicle forest', 'east'])

    def test_parse_generated_exits_existing_location(self):
        exits = json.loads('{"exits": [{"name": "The Glacier", "direction": "north", "short_descr": "A treacherous path leads up to the icy expanse, the sound of creaking ice echoing in the distance.", "enter_msg":"You enter the glacier"}, {"name": "The Cave", "direction": "east", "short_descr": "A dark opening in the side of the mountain, rumored to be home to a mysterious creature."}]}')
        exit_location_name = 'Entrance'
        location = Location(name='Outside')
        existing_location = dict()
        existing_location["east"] = Location(name='The Forest')
        new_locations, parsed_exits = parse_utils.parse_generated_exits(exits=exits.get('exits'), 
                                                                        exit_location_name=exit_location_name, 
                                                                        location=location, 
                                                                        neighbor_locations=existing_location)
        assert(len(new_locations) == 1)
        assert(new_locations[0].name == 'Glacier')
        assert(len(parsed_exits) == 2)
        assert(parsed_exits[0].name == 'glacier')
        assert(parsed_exits[1].name == 'the forest')
        assert(parsed_exits[0].short_description == 'To the north you see a treacherous path leads up to the icy expanse, the sound of creaking ice echoing in the distance.')
        assert(parsed_exits[1].short_description == 'To the east you see The Forest.')
        assert(parsed_exits[0].enter_msg == 'You enter the glacier')

    def test_parse_generated_exits_no_short_descr(self):
        # Should pick location name if description missing
        exits = json.loads('{"exits": [{"name": "The Glacier", "enter_msg":"You enter the glacier"}]}')
        exit_location_name = 'Entrance'
        location = Location(name='Outside')
        new_locations, parsed_exits = parse_utils.parse_generated_exits(exits=exits.get('exits'), 
                                                                        exit_location_name=exit_location_name, 
                                                                        location=location)
        assert(len(parsed_exits) == 1)
        assert(parsed_exits[0].name == 'glacier')
        assert(parsed_exits[0].short_description == 'You see glacier.')
        assert(parsed_exits[0].enter_msg == 'You enter the glacier')

    def test_coordinates_from_direction(self):
        coord = Coord(0,0,0)
        assert(parse_utils.coordinates_from_direction(coord, 'north') == Coord(0,1,0))
        assert(parse_utils.coordinates_from_direction(coord, 'south') == Coord(0,-1,0))
        assert(parse_utils.coordinates_from_direction(coord, 'east') == Coord(1,0,0))
        assert(parse_utils.coordinates_from_direction(coord, 'west') == Coord(-1,0,0))
        assert(parse_utils.coordinates_from_direction(coord, 'up') == Coord(0,0,1))
        assert(parse_utils.coordinates_from_direction(coord, 'down') == Coord(0,0,-1))
        assert(parse_utils.coordinates_from_direction(coord, 'hubwards') == Coord(0,0,0))

    def test_parse_generated_exits_duplicate_name(self):
        """ Test that location with same name can't be added (and replace an existing location)"""
        zone = Zone('test zone')
        zone.add_location(Location('Glacier', 'A dark cave entrance'))

        exits = json.loads('{"exits": [{"name": "Glacier", "direction": "north", "short_descr": "A treacherous path."}]}')
        exit_location_name = 'Entrance'
        location = Location(name='Outside')
        zone.add_location(location)
        new_locations, parsed_exits = parse_utils.parse_generated_exits(exits=exits.get('exits'), 
                                                                        exit_location_name=exit_location_name, 
                                                                        location=location)
        for loc in new_locations:
            zone.add_location(loc)
        
        assert(len(zone.locations) == 2)

    def test_replace_items_with_world_items(self):
        items = ["sword", "shield", "helmet"]
        world_items = [{"name": "sword", "type": "weapon", "value": 100}, {"name": "shield", "type": "armor", "value": 60}, {"name": "boots", "type": "armor", "value": 50}]

        replaced_items = parse_utils.replace_items_with_world_items(items, world_items)
        assert(len(replaced_items) == 2)
        assert(replaced_items[0]["name"] == "sword")
        assert(replaced_items[0]["value"] == 100)
        assert(replaced_items[1]["name"] == "shield")
        assert(replaced_items[1]["value"] == 60)
        

    def test_replace_creature_with_world_creature(self):
        creatures = ["kobold", "goblin", {"name":"urgokh", "race":"orc"}]
        # creatures have the following format: {"name":"", "body":"", "mass":int(kg), "hp":int, "level":int, "unarmed_attack":One of [FISTS, CLAWS, BITE, TAIL, HOOVES, HORN, TUSKS, BEAK, TALON], "short_descr":""}
        world_creatures = [{"name": "kobold", "body":"Humanoid", "mass":40, "hp":5, "level":1, "unarmed_attack": "FISTS", "short_descr":"A typical kobold"}]
        replaced_creatures = parse_utils.replace_creature_with_world_creature(creatures, world_creatures)
        assert(len(replaced_creatures) == 2)
        assert(replaced_creatures[0]["name"] == "kobold")
        assert(replaced_creatures[0]["body"] == "Humanoid")
        assert(replaced_creatures[0]["mass"] == 40)
        assert(replaced_creatures[0]["hp"] == 5)
        assert(replaced_creatures[0]["level"] == 1)
        assert(replaced_creatures[0]["unarmed_attack"] == "FISTS")
        assert(replaced_creatures[0]["short_descr"] == "A typical kobold")
        assert(replaced_creatures[1] == {'name': 'urgokh', 'race': 'orc'})
          
    def test_parse_basic_items(self):
        items = json.loads('{"items": [{"name": "sword", "type": "Weapon", "value": 100}, {"name": "boots", "type": "Wearable", "value": 50, "ac": 2, "wear_location": "FEET"}, {"name": "ration", "type": "Food", "value": 10, "affects_fullness":10}, {"name": "health_potion", "type": "Health", "value": 10}, {"name":"Bottle of beer", "type":"Drink", "value":10}, {"name":"box", "type":"Container", "value":10}]}')
        parsed_items = load_items.load_items(items['items'])

        assert(len(parsed_items) == 6)
        assert(isinstance(parsed_items["sword"], Weapon))
        assert(parsed_items["sword"])
        assert(isinstance(parsed_items["boots"], Wearable))
        assert(parsed_items["boots"].wear_location == WearLocation.FEET)
        assert(isinstance(parsed_items["ration"], Food))
        assert(parsed_items["ration"].affect_fullness == 10)
        assert(isinstance(parsed_items["health_potion"], Health))
        assert(parsed_items["health_potion"].healing_effect == 10)
        # assert(isinstance(parsed_items[4], Money))
        # assert(parsed_items[4].value == 10)
        # assert(parsed_items[4].name == "10$ bill")
        assert(isinstance(parsed_items["Bottle of beer"], Drink))
        assert(isinstance(parsed_items["box"], Boxlike))

    def test_trim_response(self):
        response = ' {The Duchess takes a seat next to him.}'

        trimmed = parse_utils.trim_response(response)
        assert(trimmed == 'The Duchess takes a seat next to him.')

        response = ' Duchess gently nuzzles the back of your hand."\n" }]\n'
        trimmed = parse_utils.trim_response(response)
        assert(trimmed == 'Duchess gently nuzzles the back of your hand.')

        response = ''
        trimmed = parse_utils.trim_response(response)
        assert(trimmed == '')

        response = '*'  
        trimmed = parse_utils.trim_response(response)
        assert(trimmed == '')

        response = '\n'  
        trimmed = parse_utils.trim_response(response)
        assert(trimmed == '')

        response = '\n\n'  
        trimmed = parse_utils.trim_response(response)
        assert(trimmed == '')      

    def test_save_and_load_stats(self):
        npc = Living('test', gender='m')
        npc.stats.weapon_skills.set(WeaponType.UNARMED, 10)
        json_stats = parse_utils.save_stats(npc.stats)
        assert(json_stats['unarmed_attack'] == 'FISTS')
        
        loaded_stats = parse_utils.load_stats(json_stats)
        assert(isinstance(loaded_stats.unarmed_attack, Weapon))
        assert(loaded_stats.weapon_skills.get(WeaponType.UNARMED) == 10)
        
    def test_load_mob_spawners(self):
        driver = IFDriver(screen_delay=99, gui=False, web=True, wizard_override=True)
        driver.game_clock = util.GameDateTime(datetime.datetime(year=2023, month=1, day=1), 1)

        json_spawners = [
            {
                'location': 'Royal grotto',
                'mob_type': 'Kobbo',
                'spawn_rate': 5,
                'spawn_limit': 10,
                'drop_items': [
                    'Sword', 'Potion'
                ],
                'drop_item_probabilities': [0.5, 0.3]
            },
            {
                'location': 'Dark forest',
                'mob_type': 'Goblin',
                'spawn_rate': 3,
                'spawn_limit': 5
            }
        ]
        locations = {
            'Royal grotto': Location('Royal grotto', 'A small grotto, fit for a kobold king'),
            'Dark forest': Location('Dark forest', 'A dense forest shrouded in darkness')
        }
        creatures = [
            {'name': 'Kobbo', 'title': 'Kobbo the King'},
            {'name': 'Goblin', 'title': 'Goblin Warrior'}
        ]
        world_items = [
            {'name': 'Sword', 'type': 'Weapon'},
            {'name': 'Potion', 'type': 'Drink'}
        ]

        spawners = parse_utils.load_mob_spawners(json_spawners, locations, creatures, world_items)

        assert len(spawners) == 2

        assert isinstance(spawners[0], MobSpawner)
        assert spawners[0].mob_type['title'] == 'Kobbo the King'
        assert spawners[0].location.name == 'Royal grotto'
        assert spawners[0].spawn_rate == 5
        assert spawners[0].spawn_limit == 10
        assert len(spawners[0].drop_items) == 2
        assert spawners[0].drop_items[0].title == 'Sword'
        assert spawners[0].drop_items[1].title == 'Potion'
        assert spawners[0].drop_item_probabilities == [0.5, 0.3]

        assert isinstance(spawners[1], MobSpawner)
        assert spawners[1].mob_type['title'] == 'Goblin Warrior'
        assert spawners[1].location.name == 'Dark forest'
        assert spawners[1].spawn_rate == 3
        assert spawners[1].spawn_limit == 5
        assert spawners[1].drop_items == None

    def test_load_item_spawners(self):
        driver = IFDriver(screen_delay=99, gui=False, web=True, wizard_override=True)
        driver.game_clock = util.GameDateTime(datetime.datetime(year=2023, month=1, day=1), 1)
        driver.moneyfmt = util.MoneyFormatter.create_for(MoneyType.FANTASY)

        json_spawners = [
            {
                'items': ['Sword', 'Potion'],
                'item_probabilities': [0.5, 0.3],
                'zone': 'Royal grotto',
                'spawn_rate': 5,
                'max_items': 10
            },
            {
                'items': ['Gold', 'Potion'],
                'item_probabilities': [0.5, 0.3],
                'zone': 'Dark forest',
                'spawn_rate': 3,
                'max_items': 5
            }
        ]
        zones = {
            'Royal grotto': Zone('Royal grotto'),
            'Dark forest': Zone('Dark forest')
        }
        world_items = [
            {'name': 'Sword', 'type': 'Weapon'},
            {'name': 'Potion', 'type': 'Drink'},
            {'name': 'Gold', 'type': 'Money', 'value': 100}
        ]

        spawners = parse_utils.load_item_spawners(json_spawners, zones, world_items) # type: List[ItemSpawner]

        assert len(spawners) == 2

        assert spawners[0].items[0]['name'] == 'Sword'
        assert spawners[0].items[1]['name'] == 'Potion'
        assert spawners[0].item_probabilities[0] == 0.5
        assert spawners[0].zone.name == 'Royal grotto'
        assert spawners[0].spawn_rate == 5
        assert spawners[0].max_items == 10

        assert spawners[1].items[0]['name'] == 'Gold'
        assert spawners[1].item_probabilities[0] == 0.5
        assert spawners[1].zone.name == 'Dark forest'
        assert spawners[1].spawn_rate == 3
        assert spawners[1].container == None
        assert spawners[1].max_items == 5

    def test_sanitize_json(self):
        json_string = '{ "name": "Whispering Woods", "description": "A dense, misty forest teeming with life. The trees whisper secrets to those who listen, and the creatures here are said to possess ancient wisdom. Friendly creatures roam the area, and the air is filled with the sweet scent of enchanted flowers.", "races": [], "items": [], "mood": 5, "level": 1} '
        sanitized = json.loads(parse_utils.sanitize_json(json_string))
        assert sanitized['name'] == 'Whispering Woods'

    def test_mood_string_from_int(self):
        assert parse_utils.mood_string_from_int(5) == ' uttermost friendly'
        assert parse_utils.mood_string_from_int(0) == ' neutral'
        assert parse_utils.mood_string_from_int(-4) == ' extremely hostile'

class TestLoadNpcs:

    def setup_method(self):
        self.driver = IFDriver(screen_delay=99, gui=False, web=True, wizard_override=True)
        self.driver.game_clock = util.GameDateTime(datetime.datetime(year=2023, month=1, day=1), 1)
        self.driver.moneyfmt = util.MoneyFormatter.create_for(MoneyType.MODERN)

    def test_load_npcs(self):
        locations = {}
        locations['Royal grotto'] = Location('Royal grotto', 'A small grotto, fit for a kobold king')
        npcs_json = parse_utils.load_json("tests/files/test_npcs.json")
        npcs = parse_utils.load_npcs(npcs_json, locations=locations)
        assert(len(npcs) == 3)

        npc = npcs['Kobbo']
        assert(npc.title == 'Kobbo the King')
        assert(npc.location == locations['Royal grotto'])
        assert(npc.aliases.pop() == 'kobbo')
        assert(isinstance(npc.stats.unarmed_attack, Weapon))
        npc2 = npcs['generated name']
        assert(npc2.name == 'generated name')
        assert(npc2.title == 'generated name')
        assert(npc2.aliases.pop() == 'generated')
        assert(npc2.location == locations['Royal grotto'])
        npc3 = npcs['name']
        assert(npc3.location == locations['Royal grotto'])
        assert(npc3.name == 'name')

        saved_npcs = parse_utils.save_npcs(npcs.values())

        assert(len(saved_npcs.values()) == 3)
        assert(saved_npcs['Kobbo']['name'] == 'Kobbo')
        assert(saved_npcs['Kobbo']['title'] == 'Kobbo the King')
        assert(saved_npcs['Kobbo']['location'] == 'Royal grotto')
 
    def test_load_npcs_generated(self):
        npcs_string = '{"npcs": [{"name": "Rosewood Fairy", "sentiment": "friendly", "race": "Fae", "gender": "female", "level": 5, "description": "A delicate creature with wings as soft as rose petals, offering quests and guidance.", "occupation":"healer"}]}'
        npcs = json.loads(npcs_string)
        assert(len(npcs) == 1)

        world_items = [{'name': 'potion', 'type': 'Health', 'value': 10}]

        loaded_npcs = parse_utils.load_npcs(npcs['npcs'], world_items=world_items, parse_occupation=True)
        assert(len(loaded_npcs) == 1)
        fairy = loaded_npcs['Rosewood Fairy'] # type: Living
        assert(fairy)
        assert(fairy.stats.bodytype == BodyType.WINGED_MAN)
        assert(fairy.occupation == 'healer')
        assert(fairy.inventory)

    def test_load_trader(self):
        npcs_string = '{"npcs": [{"name": "Village Trader", "type":"npc", "occupation":"trader", "sentiment": "friendly", "race": "human", "gender": "female", "level": 5, "description": ""}]}'
        npcs = json.loads(npcs_string)
        assert(len(npcs) == 1)

        world_items = [{"name": "sword", "type": "weapon", "value": 100}, {"name": "shield", "type": "armor", "value": 60}, {"name": "boots", "type": "armor", "value": 50}]
        loaded_npcs = parse_utils.load_npcs(npcs['npcs'], world_items=world_items, parse_occupation=True)
        assert(len(loaded_npcs) == 1)
        trader = loaded_npcs['Village Trader'] # type: Living
        assert(trader)
        assert(isinstance(trader, Trader))
        assert(len(trader.inventory) > 0)

    def test_load_bartender(self):
        npcs_string = '{"npcs": [{"name": "Village Bartender", "type":"npc", "occupation":"barkeep", "sentiment": "friendly", "race": "human", "gender": "female", "level": 5, "description": ""}]}'
        npcs = json.loads(npcs_string)

        loaded_npcs = parse_utils.load_npcs(npcs['npcs'], parse_occupation=True)
        assert(len(loaded_npcs) == 1)
        trader = loaded_npcs['Village Bartender'] # type: Living
        assert(trader)
        assert(isinstance(trader, Trader))
        assert(len(trader.inventory) > 0)


    def test_load_npc_parse_occupation(self):
        npcs_string = '{"npcs": [{"name": "Village Guard", "type":"npc", "occupation":"guard", "sentiment": "friendly", "race": "human", "gender":"f", "level": 5, "description": ""}]}'
        npcs = json.loads(npcs_string)
        assert(len(npcs) == 1)

        world_items = [{"name": "Sword", "type": "Weapon", "value": 100, "weapon_type":"ONE_HANDED"}, {"name": "Spear", "type": "Weapon", "value": 100, "weapon_type":"TWO_HANDED"}]
        loaded_npcs = parse_utils.load_npcs(npcs['npcs'], world_items=world_items, parse_occupation=True)

        assert(len(loaded_npcs) == 1)
        guard = loaded_npcs['Village Guard'] # type: Living

        assert(guard.stats.weapon_skills.get(WeaponType.ONE_HANDED) > 0)
        assert(guard.stats.weapon_skills.get(WeaponType.TWO_HANDED) > 0)
        assert(guard.stats.weapon_skills.get(WeaponType.TWO_HANDED_RANGED) == 0)
        assert(guard.locate_item('Sword')[1] or guard.locate_item('Spear')[1])

