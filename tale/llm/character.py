

from copy import deepcopy
from json import JSONDecodeError
import json
import random

from tale import _MudContext, parse_utils
from tale.base import Location
from tale.errors import LlmResponseException
from tale.llm import llm_config
from tale.llm.contexts.ActionContext import ActionContext
from tale.llm.llm_io import IoUtil
from tale.llm.contexts.DialogueContext import DialogueContext
from tale.load_character import CharacterV2


class CharacterBuilding():

    def __init__(self, backend: str, io_util: IoUtil, default_body: dict):
        self.pre_prompt = llm_config.params['PRE_PROMPT']
        self.dialogue_prompt = llm_config.params['DIALOGUE_PROMPT']
        self.character_prompt = llm_config.params['CREATE_CHARACTER_PROMPT']
        self.backend = backend
        self.io_util = io_util
        self.default_body = default_body
        self.travel_prompt = llm_config.params['TRAVEL_PROMPT']
        self.reaction_prompt = llm_config.params['REACTION_PROMPT']
        self.idle_action_prompt = llm_config.params['IDLE_ACTION_PROMPT']
        self.free_form_action_prompt = llm_config.params['ACTION_PROMPT']
        self.json_grammar = llm_config.params['JSON_GRAMMAR']
        self.dialogue_template = llm_config.params['DIALOGUE_TEMPLATE']
        self.action_template = llm_config.params['ACTION_TEMPLATE']

    def generate_dialogue(self,
                          context: DialogueContext,
                          conversation: str,
                          sentiment = '', 
                          event_history = '',
                          short_len : bool=False):
        prompt = self.pre_prompt

        #formatted_conversation = llm_config.params['USER_START']
        formatted_conversation = conversation.replace('<break>', '\n')#llm_config.params['USER_END'] + '\n' + llm_config.params['USER_START'])
        prompt += self.dialogue_prompt.format(
                context='',
                previous_conversation=formatted_conversation,
                character2=context.speaker_name,
                character1=context.target_name,
                dialogue_template=self.dialogue_template,
                history=event_history,
                sentiment=sentiment)
        request_body = deepcopy(self.default_body)
        request_body['grammar'] = self.json_grammar
        response = self.io_util.synchronous_request(request_body, prompt=prompt, context=context.to_prompt_string())
        try:
            json_result = json.loads(parse_utils.sanitize_json(response))
            text = json_result["response"]
            if isinstance(text, list):
                text = text[0]
            new_sentiment = json_result.get("sentiment", None)
            item = json_result.get("give", None)
            if not isinstance(item, str):
                item = None
        except Exception as exc:
            return None, None, None
        
        return text, item, new_sentiment
    
    def generate_character(self, story_context: str = '', keywords: list = [], story_type: str = '') -> CharacterV2:
        """ Generate a character card based on the current story context"""
        prompt = self.character_prompt.format(story_type=story_type if story_type else _MudContext.config.type,
                                              story_context=story_context, 
                                              world_info='',
                                              keywords=', '.join(keywords))
        request_body = deepcopy(self.default_body)
        request_body['grammar'] = self.json_grammar
        result = self.io_util.synchronous_request(request_body, prompt=prompt)
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
    
    def perform_idle_action(self, character_name: str, location: Location, story_context: str, character_card: str = '', sentiments: dict = {}, last_action: str = '', event_history: str = '') -> list:
        characters = {}
        for living in location.livings:
            if living.visible and living.name != character_name.lower():
                if living.alive:
                    characters[living.name] = living.short_description
                else:
                    characters[living.name] = f"{living.short_description} (dead)"
        items = [item.name for item in location.items if item.visible]
        prompt = self.idle_action_prompt.format(
            last_action=last_action if last_action else f"{character_name} arrives in {location.name}",
            location=": ".join([location.title, location.short_description]),
            story_context=story_context,
            character_name=character_name,
            character=character_card,
            items=items,
            characters=json.dumps(characters),
            history=event_history,
            sentiments=json.dumps(sentiments))
        request_body = deepcopy(self.default_body)
        if self.backend == 'kobold_cpp':
            request_body['banned_tokens'] = ['You']

        text = self.io_util.synchronous_request(request_body, prompt=prompt)
        return parse_utils.trim_response(text) + "\n"
    
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
        request_body = deepcopy(self.default_body)
        text = self.io_util.synchronous_request(request_body, prompt=prompt)
        return text
    
    def perform_reaction(self, action: str, character_name: str, acting_character_name: str, location: Location, story_context: str, character_card: str = '', sentiment: str = '', event_history: str = ''):
        prompt = self.pre_prompt
        prompt += self.reaction_prompt.format(
            action=action,
            location_name=location.name,
            character_name=character_name,
            character=character_card,
            acting_character_name=acting_character_name,
            story_context=story_context,
            history=event_history,
            sentiment=sentiment)
        request_body = deepcopy(self.default_body)
        text = self.io_util.synchronous_request(request_body, prompt=prompt)
        return parse_utils.trim_response(text) + "\n"
    
    def free_form_action(self, action_context: ActionContext):
        prompt = self.pre_prompt
        prompt += self.free_form_action_prompt.format(
            context = '',
            character_name=action_context.character_name,
            action_template=self.action_template)
        request_body = deepcopy(self.default_body)
        request_body['grammar'] = self.json_grammar
        try :
            text = self.io_util.synchronous_request(request_body, prompt=prompt, context=action_context.to_prompt_string())
            if not text:
                return None
            response = json.loads(parse_utils.sanitize_json(text))
            return self._sanitize_free_form_response(response)
        except Exception as exc:
            print('Failed to parse action')  
            return None
            
        
    def _sanitize_free_form_response(self, action: dict):
        if action.get('text'):
            if isinstance(action['text'], list):
                action['text'] = action['text'][0]
        if action.get('target'):
            target_name = action['target']
            if isinstance(target_name, list):
                action['target'] = target_name[0]
            elif isinstance(target_name, dict):
                action['target'] = target_name.get('name', '')
        if action.get('item'):
            item_name = action['item']
            if isinstance(item_name, list):
                action['item'] = item_name[0]
            elif isinstance(item_name, dict):
                action['item'] = item_name.get('name', '')
        if action.get('action'):
            action_name = action['action']
            if isinstance(action_name, list):
                action['action'] = action_name[0]
            elif isinstance(action_name, dict):
                action['action'] = action_name.get('action', '')
        return action