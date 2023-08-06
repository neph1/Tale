import json
import os
import re
import requests
import yaml
from json import JSONDecodeError
import tale.parse_utils as parse_utils

class LlmUtil():
    def __init__(self):
        with open(os.path.realpath(os.path.join(os.path.dirname(__file__), "llm_config.yaml")), "r") as stream:
            try:
                config_file = yaml.safe_load(stream)
            except yaml.YAMLError as exc:
                print(exc)
        self.url = config_file['URL'] + config_file['ENDPOINT']
        self.default_body = json.loads(config_file['DEFAULT_BODY'])
        self.analysis_body = json.loads(config_file['ANALYSIS_BODY'])
        self.memory_size = config_file['MEMORY_SIZE']
        self.pre_prompt = config_file['PRE_PROMPT']
        self.base_prompt = config_file['BASE_PROMPT']
        self.dialogue_prompt = config_file['DIALOGUE_PROMPT']
        self.item_prompt = config_file['ITEM_PROMPT']
        self._story_background = ''

    def evoke(self, message: str, max_length : bool=False, rolling_prompt='', alt_prompt=''):
        if len(message) > 0 and str(message) != "\n":
            if not rolling_prompt:
                rolling_prompt += self._story_background
            trimmed_message = parse_utils.remove_special_chars(str(message))
            base_prompt = alt_prompt if alt_prompt else self.base_prompt
            amount = int(len(trimmed_message) * 2.5)
            prompt = rolling_prompt if not alt_prompt else ''
            prompt += base_prompt.format(input_text=str(trimmed_message))
            
            rolling_prompt = self.update_memory(rolling_prompt, trimmed_message)
            
            request_body = self.default_body 
            request_body['prompt'] = prompt
            if max_length:
                request_body['max_length'] = amount
            response = requests.post(self.url, data=json.dumps(request_body))
            text = parse_utils.trim_response(json.loads(response.text)['results'][0]['text'])
            
            rolling_prompt = self.update_memory(rolling_prompt, text)
            return f'Original:[ {message} ] Generated:\n{text}', rolling_prompt
        return str(message), rolling_prompt
    
    def generate_dialogue(self, conversation: str, character_card: str, character_name: str, target: str, sentiment = ''):
        prompt = self.pre_prompt
        prompt += self.dialogue_prompt.format(
                previous_conversation=conversation, 
                character2_description=character_card,
                character2=character_name,
                character1=target,
                sentiment=sentiment)
        
        request_body = self.default_body
        request_body['prompt'] = prompt
        response = requests.post(self.url, data=json.dumps(request_body))
        text = parse_utils.trim_response(json.loads(response.text)['results'][0]['text'])
        
        item_handling_result, new_sentiment = self.dialogue_analysis(text, character_card, character_name, target)
        
        return f'{text}', item_handling_result, new_sentiment
    
    def dialogue_analysis(self, text: str, character_card: str, character_name: str, target: str):
        items = character_card.split('items:')[1].split(']')[0]
        prompt = self.generate_item_prompt(text, items, character_name, target)
        request_body = self.analysis_body
        request_body['prompt'] = prompt
        response = requests.post(self.url, data=json.dumps(request_body))
        
        text = parse_utils.trim_response(json.loads(response.text)['results'][0]['text'])
        try:
            json_result = json.loads(text.replace('\n', ''))
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
        rolling_prompt += response_text
        if len(rolling_prompt) > self.memory_size:
            rolling_prompt = rolling_prompt[len(rolling_prompt) - self.memory_size + 1:]
        return rolling_prompt
     
    @property
    def story_background(self) -> str:
        return self._story_background

    @story_background.setter
    def story_background(self, value: str) -> None:
        self._story_background = value
