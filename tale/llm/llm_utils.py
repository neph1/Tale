import json
import os
import yaml
import random
from json import JSONDecodeError
from tale import mud_context, math_utils
from tale import zone
from tale.base import Location
from tale.coord import Coord
from tale.llm.llm_ext import DynamicStory
from tale.llm.llm_io import IoUtil
from tale.load_character import CharacterV2
from tale.player_utils import TextBuffer
import tale.parse_utils as parse_utils
from tale.zone import Zone

class LlmUtil():
    """ Prepares prompts for various LLM requests"""

    def __init__(self):
        with open(os.path.realpath(os.path.join(os.path.dirname(__file__), "../../llm_config.yaml")), "r") as stream:
            try:
                config_file = yaml.safe_load(stream)
            except yaml.YAMLError as exc:
                print(exc)
        self.backend = config_file['BACKEND']
        self.default_body = json.loads(config_file['DEFAULT_BODY']) if self.backend == 'kobold_cpp' else json.loads(config_file['OPENAI_BODY'])
        self.analysis_body = json.loads(config_file['ANALYSIS_BODY'])
        self.memory_size = config_file['MEMORY_SIZE']
        self.pre_prompt = config_file['PRE_PROMPT'] # type: str
        self.pre_json_prompt = config_file['PRE_JSON_PROMPT'] # type: str
        self.base_prompt = config_file['BASE_PROMPT'] # type: str
        self.dialogue_prompt = config_file['DIALOGUE_PROMPT'] # type: str
        self.action_prompt = config_file['ACTION_PROMPT'] # type: str
        self.combat_prompt = config_file['COMBAT_PROMPT'] # type: str
        self.character_prompt = config_file['CREATE_CHARACTER_PROMPT'] # type: str
        self.location_prompt = config_file['CREATE_LOCATION_PROMPT'] # type: str
        self.item_prompt = config_file['ITEM_PROMPT'] # type: str
        self.word_limit = config_file['WORD_LIMIT']
        self.spawn_prompt = config_file['SPAWN_PROMPT'] # type: str
        self.items_prompt = config_file['ITEMS_PROMPT'] # type: str
        self.zone_prompt = config_file['CREATE_ZONE_PROMPT'] # type: str
        self.idle_action_prompt = config_file['IDLE_ACTION_PROMPT'] # type: str
        self.travel_prompt = config_file['TRAVEL_PROMPT'] # type: str
        self.reaction_prompt = config_file['REACTION_PROMPT'] # type: str
        self.story_background_prompt = config_file['STORY_BACKGROUND_PROMPT'] # type: str
        self.start_location_prompt = config_file['START_LOCATION_PROMPT'] # type: str
        self.json_grammar = config_file['JSON_GRAMMAR'] # type: str
        self.__story = None # type: DynamicStory
        self.io_util = IoUtil(config=config_file)
        self.stream = config_file['STREAM']
        self.connection = None
        self._look_hashes = dict() # type: dict[int, str] # location hashes for look command. currently never cleared.

    def evoke(self, player_io: TextBuffer, message: str, max_length : bool=False, rolling_prompt='', alt_prompt='', skip_history=True):
        """Evoke a response from LLM. Async if stream is True, otherwise synchronous.
        Update the rolling prompt with the latest message.
        Will put generated text in _look_hashes, and reuse it if same hash is passed in."""

        if not message or str(message) == "\n":
            str(message), rolling_prompt

        rolling_prompt = self.update_memory(rolling_prompt, message)

        text_hash_value = hash(message)
        if text_hash_value in self._look_hashes:
            text = self._look_hashes[text_hash_value]
            
            return f'Original:[ {message} ]\nGenerated:\n{text}', rolling_prompt

        trimmed_message = parse_utils.remove_special_chars(str(message))

        base_prompt = alt_prompt if alt_prompt else self.base_prompt
        amount = 25 #int(len(trimmed_message) / 2)
        prompt = self.pre_prompt
        prompt += base_prompt.format(
            story_context=self.__story.config.context,
            history=rolling_prompt if not skip_history or alt_prompt else '',
            max_words=self.word_limit if not max_length else amount,
            input_text=str(trimmed_message))
        
        request_body = self.default_body
        if self.backend == 'kobold_cpp':
            request_body['prompt'] = prompt
        elif self.backend == 'openai':
            request_body['messages'][1]['content'] = prompt

        if not self.stream:
            text = self.io_util.synchronous_request(request_body)
            self._store_hash(text_hash_value, text)
            return f'Original:[ {message} ]\n\nGenerated:\n{text}', rolling_prompt

        player_io.print(f'Original:[ {message} ]\nGenerated:\n', end=False, format=True, line_breaks=False)
        text = self.io_util.stream_request(request_body, player_io, self.connection)
        self._store_hash(text_hash_value, text)
        
        return '\n', rolling_prompt
    
    def generate_dialogue(self, conversation: str, 
                          character_card: str, 
                          character_name: str, 
                          target: str, 
                          target_description: str='', 
                          sentiment = '', 
                          location_description = '',
                          max_length : bool=False):
        prompt = self.pre_prompt
        prompt += self.dialogue_prompt.format(
                story_context=self.__story.config.context,
                location=location_description,
                previous_conversation=conversation, 
                character2_description=character_card,
                character2=character_name,
                character1=target,
                character1_description=target_description,
                sentiment=sentiment)
        request_body = self.default_body
        if self.backend == 'kobold_cpp':
            request_body['prompt'] = prompt
        elif self.backend == 'openai':
            request_body['messages'][1]['content'] = prompt
        #if not self.stream:
        text = parse_utils.trim_response(self.io_util.synchronous_request(request_body))
        #else:
        #    player_io = mud_context.pla
        #    text = self.io_util.stream_request(self.url + self.stream_endpoint, self.url + self.data_endpoint, request_body, player_io, self.connection)

        item_handling_result, new_sentiment = self.dialogue_analysis(text, character_card, character_name, target)
        
        return f'{text}', item_handling_result, new_sentiment
    
    def dialogue_analysis(self, text: str, character_card: str, character_name: str, target: str):
        """Parse the response from LLM and determine if there are any items to be handled."""
        items = character_card.split('items:')[1].split(']')[0]
        prompt = self.generate_item_prompt(text, items, character_name, target)
        
        if self.backend == 'kobold_cpp':
            request_body = self.analysis_body
            request_body['prompt'] = prompt
        elif self.backend == 'openai':
            request_body = self.default_body
            request_body['messages'][1]['content'] = prompt
        text = parse_utils.trim_response(self.io_util.synchronous_request(request_body))
        try:
            json_result = json.loads(parse_utils.sanitize_json(text))
        except JSONDecodeError as exc:
            print(exc)
            return None, None
        
        valid, item_result = self.validate_item_response(json_result, character_name, target, items)
        
        sentiment = self.validate_sentiment(json_result)
        
        return item_result, sentiment
    
    def validate_sentiment(self, json: dict):
        try:
            return json.get('sentiment')
        except:
            print(f'Exception while parsing sentiment {json}')
            return ''
    
    def generate_item_prompt(self, text: str, items: str, character1: str, character2: str) -> str:
        prompt = self.pre_prompt
        prompt += self.item_prompt.format(
                text=text, 
                items=items,
                character1=character1,
                character2=character2)
        return prompt
     
    def validate_item_response(self, json_result: dict, character1: str, character2: str, items: str) -> bool:
        if 'result' not in json_result or not json_result.get('result'):
            return False, None
        result = json_result['result']
        if 'item' not in result or not result['item']:
            return False, None
        if not result['from']:
            return False, None
        if result['item'] in items:
            return True, result
        return False, None
      
    def update_memory(self, rolling_prompt: str, response_text: str):
        """ Keeps a history of the last couple of events"""
        rolling_prompt += response_text
        if len(rolling_prompt) > self.memory_size:
            rolling_prompt = rolling_prompt[len(rolling_prompt) - self.memory_size + 1:]
        return rolling_prompt
    
    def generate_character(self, story_context: str = '', keywords: list = [], story_type: str = ''):
        """ Generate a character card based on the current story context"""
        prompt = self.character_prompt.format(story_type=story_type if story_type else mud_context.config.type,
                                              story_context=story_context, 
                                              keywords=', '.join(keywords))
        request_body = self.default_body
        if self.backend == 'kobold_cpp':
            # do some parameter tweaking for kobold_cpp
            request_body['stop_sequence'] = ['\n\n'] # to avoid text after the character card
            request_body['temperature'] = 0.7
            request_body['top_p'] = 0.92
            request_body['rep_pen'] = 1.0
            request_body['banned_tokens'] = ['```']
            request_body['grammar'] = self.json_grammar
            request_body['prompt'] = prompt
        elif self.backend == 'openai':
            request_body['messages'][1]['content'] = prompt
        result = self.io_util.synchronous_request(request_body)
        try:
            json_result = json.loads(parse_utils.sanitize_json(result))
        except JSONDecodeError as exc:
            print(exc)
            return None
        try:
            return CharacterV2().from_json(json_result)
        except:
            print(f'Exception while parsing character {json_result}')
            return None
    
    def get_neighbor_or_generate_zone(self, current_zone: Zone, current_location: Location, target_location: Location) -> Zone:
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
                    json_result = self.generate_zone(location_desc=target_location.description, 
                                        exit_location_name=current_location.name, 
                                        current_zone_info=current_zone.get_info(),
                                        direction=parse_utils.direction_from_coordinates(direction))
                    if json_result:
                        zone = self.validate_zone(json_result, 
                                                  target_location.world_location.add(
                                                      direction.multiply(json_result.get('size', 5))))
                        if zone:
                            if self.__story.add_zone(zone):
                                return zone
        return current_zone

    def build_location(self, location: Location, exit_location_name: str, zone_info: dict):
        """ Generate a location based on the current story context"""

        # TODO: this is a just a placeholder algo to create some things randomly.
        spawn_prompt = ''
        spawn_chance = 0.25
        spawn = random.random() < spawn_chance
        if spawn:
            
            mood = zone_info.get('mood', 0)
            if mood == 'friendly':
                num_mood = 2
            elif mood == 'neutral':
                num_mood = 0
            else:
                num_mood = -1
            num_mood = random.gauss(num_mood, 2)
            level = (int) (math_utils.normpdf(mean=zone_info.get('level', 1), sd=3, x=0) + 1)
            spawn_prompt = self.spawn_prompt.format(alignment=num_mood > 0 and 'friendly' or 'hostile', level= level)

        items_prompt = ''
        item_amount = random.randint(0, 2)
        if item_amount > 0:
            items_prompt = self.items_prompt.format(items=item_amount)

        prompt = self.pre_json_prompt
        prompt += self.location_prompt.format(
            story_type=self.__story.config.type,
            world_info=self.__story.config.world_info,
            zone_info=zone_info,
            story_context=self.__story.config.context,
            exit_location=exit_location_name,
            location_name=location.name,
            spawn_prompt=spawn_prompt,
            items_prompt=items_prompt,)
        
        request_body = self.default_body
        if self.backend == 'kobold_cpp':
            request_body = self._kobold_generation_prompt(request_body)
            request_body['prompt'] = prompt
        elif self.backend == 'openai':
            request_body['messages'][1]['content'] = prompt
        result = self.io_util.synchronous_request(request_body)
        try:
            json_result = json.loads(parse_utils.sanitize_json(result))
            return self.validate_location(json_result, location, exit_location_name)
        except JSONDecodeError as exc:
            print(exc)
            return None, None
        except Exception as exc:
            return None, None
        
    def validate_location(self, json_result: dict, location_to_build: Location, exit_location_name: str):
        """Validate the location generated by LLM and update the location object."""
        try:
            # start locations have description already, and we don't want to overwrite it
            if not location_to_build.description:
                description = json_result.get('description', '')
                if not description:
                    # this is a hack to get around that it sometimes generate an extra json layer
                    json_result = json_result[location_to_build.name]
                location_to_build.description = json_result['description']

            items = parse_utils.load_items(json_result.get("items", []))
            # the loading function works differently and will not insert the items into the location
            # since the item doesn't have the location
            
            for item in items.values():
                location_to_build.insert(item, None)

            npcs = parse_utils.load_npcs(json_result.get("npcs", []))
            for npc in npcs.values():
                location_to_build.insert(npc, None)

            new_locations, exits = parse_utils.parse_generated_exits(json_result, 
                                                                     exit_location_name, 
                                                                     location_to_build)
            location_to_build.built = True
            return new_locations, exits
        except Exception as exc:
            print(f'Exception while parsing location {json_result} ')
            print(exc)
            return None, None
            
        
    def generate_zone(self, location_desc: str, exit_location_name: str = '', current_zone_info: dict = {}, direction: str = '') -> dict:
        """ Generate a zone based on the current story context"""
        prompt = self.pre_json_prompt
        prompt += self.zone_prompt.format(
            world_info=self.__story.config.world_info,
            mood = parse_utils.mood_string_from_int(random.gauss(self.__story.config.world_mood, 2)),
            story_type=self.__story.config.type,
            direction=direction,
            zone_info=json.dumps(current_zone_info),
            story_context=self.__story.config.context,
            exit_location=exit_location_name,
            location_desc=location_desc)
        
        request_body = self.default_body
        if self.backend == 'kobold_cpp':
            request_body = self._kobold_generation_prompt(request_body)
            request_body['prompt'] = prompt
        elif self.backend == 'openai':
            request_body['messages'][1]['content'] = prompt
        request_body['max_length'] = 750
        result = self.io_util.synchronous_request(request_body)
        try:
            json_result = json.loads(parse_utils.sanitize_json(result))
            return json_result
        except JSONDecodeError as exc:
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

    def perform_idle_action(self, character_name: str, location: Location, character_card: str = '', sentiments: dict = {}, last_action: str = '') -> list:
        characters = {}
        for living in location.livings:
            if living.name != character_name.lower():
                characters[living.name] = living.short_description
        items=location.items,
        prompt = self.idle_action_prompt.format(
            last_action=last_action if last_action else f"{character_name} arrives in {location.name}",
            location=": ".join([location.title, location.short_description]),
            story_context=self.__story.config.context,
            character_name=character_name,
            character=character_card,
            items=items,
            characters=json.dumps(characters),
            sentiments=json.dumps(sentiments))
        request_body = self.default_body
        if self.backend == 'kobold_cpp':
            request_body['prompt'] = prompt
            request_body['seed'] = random.randint(0, 2147483647)
            request_body['banned_tokens'] = ['You']
        elif self.backend == 'openai':
            request_body['messages'][1]['content'] = prompt

        text = self.io_util.asynchronous_request(request_body)
        return text.split(';')
    
    def perform_travel_action(self, character_name: str, location: Location, locations: list, directions: list, character_card: str = ''):
        if location.name in locations:
            locations.remove(location.name)

        prompt = self.pre_prompt
        prompt += self.travel_prompt.format(
            location_name=location.name,
            locations=locations,
            directions=directions,
            character=character_card,
            character_name=character_name)
        request_body = self.default_body
        if self.backend == 'kobold_cpp':
            request_body['prompt'] = prompt
        elif self.backend == 'openai':
            request_body['messages'][1]['content'] = prompt
        text = self.io_util.asynchronous_request(request_body)
        return text
    
    def perform_reaction(self, action: str, character_name: str, acting_character_name: str, location: Location, character_card: str = '', sentiment: str = ''):
        prompt = self.pre_prompt
        prompt += self.reaction_prompt.format(
            action=action,
            location_name=location.name,
            character_name=character_name,
            character=character_card,
            acting_character_name=acting_character_name,
            sentiment=sentiment)
        request_body = self.default_body
        if self.backend == 'kobold_cpp':
            request_body['prompt'] = prompt
        elif self.backend == 'openai':
            request_body['messages'][1]['content'] = prompt
        text = self.io_util.asynchronous_request(request_body)
        return text
    
    def generate_story_background(self, world_mood: int, world_info: str):
        prompt = self.story_background_prompt.format(
            story_type=self.__story.config.type,
            world_mood=parse_utils.mood_string_from_int(world_mood),
            world_info=world_info)
        request_body = self.default_body
        if self.backend == 'kobold_cpp':
            request_body['prompt'] = prompt
        elif self.backend == 'openai':
            request_body['messages'][1]['content'] = prompt
        return self.io_util.synchronous_request(request_body)
        
    def _store_hash(self, text_hash_value: int, text: str):
        """ Store the generated text in a hash table."""
        if text_hash_value != -1:
            self._look_hashes[text_hash_value] = text

    def set_story(self, story: DynamicStory):
        """ Set the story object."""
        self.__story = story

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
    
    def generate_start_location(self, location: Location, zone_info: dict, story_type: str, story_context: str, world_info: str):
        """ Generate a location based on the current story context
        One gotcha is that the location is not returned, its contents are just updated"""

        items_prompt = ''
        item_amount = random.randint(0, 2)
        if item_amount > 0:
            items_prompt = self.items_prompt.format(items=item_amount)

        prompt = self.pre_json_prompt
        prompt += self.start_location_prompt.format(
            story_type=story_type,
            world_info=world_info,
            location_description=location.description,
            spawn_prompt='',
            item_prompt='',
            zone_info=zone_info,
            story_context=story_context,
            items_prompt=items_prompt)
        
        request_body = self.default_body
        if self.backend == 'kobold_cpp':
            request_body = self._kobold_generation_prompt(request_body)
            request_body['prompt'] = prompt
        elif self.backend == 'openai':
            request_body['messages'][1]['content'] = prompt
        result = self.io_util.synchronous_request(request_body)
        try:
            json_result = json.loads(parse_utils.sanitize_json(result))
            location.name=json_result['name']
            return self.validate_location(json_result, location, '')
        except json.JSONDecodeError as exc:
            print(exc)
            return None, None
        except Exception as exc:
            return None, None
        
    def generate_start_zone(self, location_desc: str, story_type: str, story_context: str, world_mood: int, world_info: str) -> Zone:
        """ Generate a zone based on the current story context"""
        prompt = self.pre_json_prompt
        prompt += self.zone_prompt.format(
            world_info=world_info,
            mood = parse_utils.mood_string_from_int(random.gauss(world_mood, 2)),
            story_type=story_type,
            direction='',
            zone_info='',
            story_context=story_context,
            exit_location='',
            location_desc=location_desc)
        
        request_body = self.default_body
        if self.backend == 'kobold_cpp':
            request_body = self._kobold_generation_prompt(request_body)
            request_body['prompt'] = prompt
            request_body['max_length'] = 750
        elif self.backend == 'openai':
            request_body['messages'][1]['content'] = prompt
            request_body['max_tokens'] = 750
        
        result = self.io_util.synchronous_request(request_body)
        try:
            json_result = json.loads(parse_utils.sanitize_json(result))
            return zone.from_json(json_result)
        except json.JSONDecodeError as exc:
            print(exc)
            return None
    


