
from copy import deepcopy
import json
from tale import parse_utils, races
from tale import zone
from tale.base import Location
from tale.coord import Coord
from tale.items import generic
from tale.llm import llm_config
from tale.llm.llm_ext import DynamicStory
from tale.llm.llm_io import IoUtil
from tale.llm.requests.build_location import BuildLocation
from tale.llm.requests.generate_zone import GenerateZone
from tale.llm.requests.start_location import StartLocation
from tale.llm.requests.start_zone import StartZone
from tale.story import StoryConfig
from tale.zone import Zone


class WorldBuilding():

    def __init__(self, io_util: IoUtil, default_body: dict, backend: str = 'kobold_cpp'):
        self.story_background_prompt = llm_config.params['STORY_BACKGROUND_PROMPT'] # Type: str
        self.backend = backend
        self.io_util = io_util
        self.default_body = default_body
        self.json_grammar = llm_config.params['JSON_GRAMMAR'] # Type: str
        self.world_items_prompt = llm_config.params['WORLD_ITEMS'] # Type: str
        self.world_creatures_prompt = llm_config.params['WORLD_CREATURES'] # Type: str
        self.player_enter_prompt = llm_config.params['PLAYER_ENTER_PROMPT'] # Type: str
        self.item_types = ["Weapon", "Wearable", "Health", "Money", "Trash", "Food", "Drink", "Key"]


    def build_location(self, location: Location, 
                       exit_location_name: str, 
                       zone_info: dict, 
                       story_type: str, 
                       story_context: str, 
                       world_info: str, 
                       world_items: dict = {}, 
                       world_creatures: dict = {},
                       neighbors: dict = {}) -> (list, list):
        
        extra_items = generic.generic_items.get(self._check_setting(story_type), {})
        if extra_items:
            zone_info['items'].extend(extra_items.keys())
            world_items = {**world_items, **extra_items}

        prompt = BuildLocation().build_prompt({
            'zone_info': zone_info,
            'location': location,
            'exit_location_name': exit_location_name,
            'story_type': story_type,
            'world_info': world_info,
            'story_context': story_context,
            
        })

        request_body = deepcopy(self.default_body)
        if self.backend == 'kobold_cpp':
            request_body = self._kobold_generation_prompt(request_body)

        result = self.io_util.synchronous_request(request_body, prompt=prompt)
        try:
            json_result = json.loads(parse_utils.sanitize_json(result))
            return self._validate_location(json_result, location, exit_location_name, world_items, world_creatures, neighbors)
        except json.JSONDecodeError as exc:
            print(exc)
            return None, None
        except Exception as exc:
            return None, None
        
    def _validate_location(self, json_result: dict, 
                           location_to_build: Location, 
                           exit_location_name: str, 
                           world_items: dict = {}, 
                           world_creatures: dict = {},
                           neighbors: dict = {}):
        """Validate the location generated by LLM and update the location object."""
        try:
            # start locations have description already, and we don't want to overwrite it
            if not location_to_build.description:
                description = json_result.get('description', '')
                if not description:
                    # this is a hack to get around that it sometimes generate an extra json layer
                    json_result = json_result[location_to_build.name]
                location_to_build.description = json_result['description']
            
            self._add_items(location_to_build, json_result, world_items)

            self._add_npcs(location_to_build, json_result, world_creatures)

            new_locations, exits = parse_utils.parse_generated_exits(json_result.get('exits', []), 
                                                                     exit_location_name, 
                                                                     location_to_build)
            location_to_build.built = True
            return new_locations, exits
        except Exception as exc:
            print(f'Exception while parsing location {json_result} ')
            print(exc)
            return None, None
            
    def _add_items(self, location: Location, json_result: dict, world_items: dict = {}):
        generated_items = json_result.get("items", [])
        if not generated_items:
            return location
        
        if world_items:
            generated_items = parse_utils.replace_items_with_world_items(generated_items, world_items)
        # the loading function works differently and will not insert the items into the location
        # since the item doesn't have the location
        items = self._validate_items(generated_items)
        items = parse_utils.load_items(items)
        for item in items.values():
            location.insert(item, None)
        return location
    
    def _add_npcs(self, location: Location, json_result: dict, world_creatures: dict = {}):
        generated_npcs = json_result.get("npcs", [])
        if not generated_npcs:
            return location
        if world_creatures:
            generated_npcs = parse_utils.replace_creature_with_world_creature(generated_npcs, world_creatures)
        try:
            generated_npcs = parse_utils.load_npcs(generated_npcs)
            for npc in generated_npcs.values():
                location.insert(npc, None)
        except Exception as exc:
            print(exc)
        return location

    
    def get_neighbor_or_generate_zone(self, current_zone: Zone, current_location: Location, target_location: Location, story: DynamicStory) -> Zone:
        """ Check if the target location is on the edge of the current zone. If not, will return the current zone.
        If it is, will check if there is a neighbor zone in the direction of the target location. If not, will
        generate a new zone in that direction."""

        direction = target_location.world_location.subtract(current_location.world_location)
        on_edge = current_zone.on_edge(current_location.world_location, direction)
        if on_edge:
            neighbor = current_zone.get_neighbor(direction)
            if neighbor:
                return neighbor
            else:
                for i in range(5):
                    json_result = self._generate_zone(location_desc=target_location.description, 
                                        story_config=story.config,
                                        exit_location_name=current_location.name, 
                                        current_zone_info=current_zone.get_info(),
                                        direction=parse_utils.direction_from_coordinates(direction))  # type: dict
                    if json_result:
                        zone = self.validate_zone(json_result, 
                                                  target_location.world_location.add(
                                                      direction.multiply(json_result.get('size', 5))))
                        if zone and story.add_zone(zone):
                            return zone
        return current_zone

        
    def _generate_zone(self, location_desc: str, story_config: StoryConfig, exit_location_name: str = '', current_zone_info: dict = {}, direction: str = '', catalogue: dict = {}) -> dict:
        """ Generate a zone based on the current story context"""
        prompt = GenerateZone().build_prompt({
            'direction': direction,
            'current_zone_info': current_zone_info,
            'exit_location_name': exit_location_name,
            'location_desc': location_desc,
            'story_type': story_config.type,
            'world_info': story_config.world_info,
            'world_mood': story_config.world_mood,
            'story_context': story_config.context,
            'catalogue': catalogue,
        })
        
        request_body = deepcopy(self.default_body)
        if self.backend == 'kobold_cpp':
            request_body['max_length'] = 750
        elif self.backend == 'openai':
            request_body['max_tokens'] = 750
        result = self.io_util.synchronous_request(request_body, prompt=prompt)
        try:
            return json.loads(parse_utils.sanitize_json(result))
        except json.JSONDecodeError as exc:
            print(exc)
            return None

    def validate_zone(self, json_result: dict, center: Coord) -> Zone:
        """Create the Zone object."""
        zone = Zone(name=json_result['name'], description=json_result['description'])
        zone.level = json_result.get('level', 1)
        zone.mood = json_result.get('mood', 0)
        zone.center = center
        zone.size = json_result.get('size', 5)
        zone.races = json_result.get('races', [])
        zone.items = json_result.get('items', [])
        return zone
    
    def generate_start_location(self, location: Location, zone_info: dict, story_type: str, story_context: str, world_info: str):
        """ Generate a location based on the current story context
        One gotcha is that the location is not returned, its contents are just updated"""

        prompt = StartLocation().build_prompt({
            'zone_info': zone_info,
            'location': location,
            'story_type': story_type,
            'world_info': world_info,
            'story_context': story_context,
        })
        
        request_body = deepcopy(self.default_body)
        if self.backend == 'kobold_cpp':
            request_body = self._kobold_generation_prompt(request_body)
        result = self.io_util.synchronous_request(request_body, prompt=prompt)
        try:
            json_result = json.loads(parse_utils.sanitize_json(result))
            location.name=json_result['name']
            return self._validate_location(json_result, location, '')
        except Exception as exc:
            print(exc)
            return None, None
        
    def generate_start_zone(self, location_desc: str, story_type: str, story_context: str, world_info: dict) -> Zone:
        """ Generate a zone based on the current story context"""
        prompt = StartZone().build_prompt({
            'location_desc': location_desc,
            'story_type': story_type,
            'world_info': world_info,
            'story_context': story_context,
        })
        
        request_body = deepcopy(self.default_body)
        if self.backend == 'kobold_cpp':
            request_body = self._kobold_generation_prompt(request_body)
            request_body['max_length'] = 750
        elif self.backend == 'openai':
            request_body['max_tokens'] = 750
        result = self.io_util.synchronous_request(request_body, prompt=prompt)
        try:
            json_result = json.loads(parse_utils.sanitize_json(result))
            return zone.from_json(json_result)
        except json.JSONDecodeError as exc:
            print(exc)
            return None
        

    def generate_world_items(self, story_context: str, story_type: str, world_info: str, world_mood: int) -> dict:
        prompt = self.world_items_prompt.format(story_context=story_context,
                                                story_type=story_type,
                                                world_info=world_info,
                                                world_mood=parse_utils.mood_string_from_int(world_mood),
                                                item_types=self.item_types)
        request_body = deepcopy(self.default_body)
        if self.backend == 'kobold_cpp':
            request_body = self._kobold_generation_prompt(request_body)

        result = self.io_util.synchronous_request(request_body, prompt=prompt)
        try:
            return json.loads(parse_utils.sanitize_json(result))["items"]
            #return parse_utils.load_items(self._validate_items(json_result["items"]))
        except json.JSONDecodeError as exc:
            print(exc)
            return None
    
    def generate_world_creatures(self, story_context: str, story_type: str, world_info: str, world_mood: int):
        prompt = self.world_creatures_prompt.format(story_context=story_context,
                                                story_type=story_type,
                                                world_info=world_info,
                                                world_mood=parse_utils.mood_string_from_int(world_mood))
        request_body = deepcopy(self.default_body)
        if self.backend == 'kobold_cpp':
            request_body = self._kobold_generation_prompt(request_body)
            
        result = self.io_util.synchronous_request(request_body, prompt=prompt)
        try:
            return json.loads(parse_utils.sanitize_json(result))["creatures"]
            #return self._validate_creatures(json_result["creatures"])
        except json.JSONDecodeError as exc:
            print(exc)
            return None
    
    def generate_random_spawn(self, location: Location, story_context: str, story_type: str, world_info: str, zone_info: dict, world_creatures: dict, world_items: dict):
        location_info = {'name': location.title, 'description': location.look(short=True), 'exits': location.exits}
        extra_items = generic.generic_items.get(self._check_setting(story_type), {})
        if extra_items:
            zone_info['items'].extend(extra_items.keys())
            world_items = {**world_items, **extra_items}
        prompt = self.player_enter_prompt.format(story_context=story_context,
                                                story_type=story_type,
                                                world_info=world_info,
                                                zone_info=zone_info,
                                                location_info=location_info)
        request_body = deepcopy(self.default_body)
        if self.backend == 'kobold_cpp':
            request_body = self._kobold_generation_prompt(request_body)
            
        result = self.io_util.synchronous_request(request_body, prompt=prompt)
        try:
            json_result = json.loads(parse_utils.sanitize_json(result))
            creatures = json_result["npcs"]
            creatures.extend(json_result["mobs"])
            creatures = parse_utils.replace_creature_with_world_creature(creatures, world_creatures)
            creatures = parse_utils.load_npcs(creatures)
            for c in creatures.values():
                location.insert(c)
            items = json_result["items"]
            items = parse_utils.replace_items_with_world_items(items, world_items)
            items = parse_utils.load_items(items)
            for i in items.values():
                location.insert(i)
        except Exception as exc:
            print(exc)
            return None
        
    def _kobold_generation_prompt(self, request_body: dict) -> dict:
        """ changes some parameters for better generation of locations in kobold_cpp"""
        request_body = request_body.copy()
        request_body['stop_sequence'] = ['\n\n']
        request_body['temperature'] = 0.5
        request_body['top_p'] = 0.6
        request_body['top_k'] = 0
        request_body['rep_pen'] = 1.0
        request_body['grammar'] = self.json_grammar
        #request_body['banned_tokens'] = ['```']
        return request_body
    
    def _validate_items(self, items: dict) -> list:
        new_items = []
        for item in items:
            if isinstance(item, str):
                # TODO: decide what to do with later
                new_items.append({"name":item, "type":"Other"})
                continue
            if not item.get("name", ""):
                continue
            item["name"] = item["name"].lower()
            type = item.get("type", "Other")
            if type not in self.item_types:
                item["type"] = "Other"
            new_items.append(item)
        return new_items

    def _validate_creatures(self, creatures: dict) -> dict:
        new_creatures = {}
        for creature in creatures:
            if not creature.get("name", ""):
                continue
            creature["name"] = creature["name"].lower()
            if creature.get("unarmed_attack", ""):
                try:
                    creature["unarmed_attack"] = races.UnarmedAttack[creature["unarmed_attack"]]
                except:
                    creature["unarmed_attack"] = races.UnarmedAttack.BITE
            else:
                creature["unarmed_attack"] = races.UnarmedAttack.BITE
            level = creature.get("level", 1)
            if level < 1:
                creature["level"] = 1
            creature["type"] = "Mob"
            new_creatures[creature["name"]] = creature
        return new_creatures
    
    def _check_setting(self, story_type: str):
        if 'fantasy' in story_type:
            return 'fantasy'
        if 'modern' in story_type or 'contemporary' in story_type:
            return 'modern'
        if 'scifi' in story_type or 'sci-fi' in story_type:
            return 'scifi'
        if 'postapoc' in story_type or 'post-apoc' in story_type:
            return 'postapoc'
        return ''
        