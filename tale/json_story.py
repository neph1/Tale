from tale import load_items, wearable
from tale.items import generic
from tale.llm.dynamic_story import DynamicStory
from tale.player import Player
from tale.story import StoryConfig
import tale.parse_utils as parse_utils
import tale.llm.llm_cache as llm_cache

class JsonStory(DynamicStory):
    
    def __init__(self, path: str, config: StoryConfig):
        super(JsonStory, self).__init__()
        self.config = config
        self.path = path
        
    
    def init(self, driver) -> None:
        super(JsonStory, self).init(driver)
        locs = {}
        zones = []
        world = parse_utils.load_json(self.path +'world.json')
        for zone in world['zones'].values():
            zones, exits = parse_utils.load_locations(zone)
        if len(zones) < 1:
            print("No zones found in story config")
            return
        for name in zones.keys():
            zone = zones[name]
            self.add_zone(zone)
            for loc in zone.locations.values():
                self.add_location(loc, name)
        if world.get('catalogue', None):
            if world['catalogue']['creatures']:
                self._catalogue._creatures = world['catalogue']['creatures']
            if  world['catalogue']['items']:
                self._catalogue._items = world['catalogue']['items']
            if world['catalogue'].get('wearables', None):
                wearable.add_story_wearables(world['catalogue']['wearables'])
        if world.get('world', None):
            if  world['world']['items']:
                # Keep this so that saved items in worlds will transfer to locations. But don't save them.
                self._world.items = load_items.load_items(world['world']['items'].values(), self.locations)
            if world['world']['npcs']:
                self._world.npcs = parse_utils.load_npcs(world['world']['npcs'].values(), locations=self.locations, world_items=self._catalogue._items)
            if world['world'].get('spawners', None):
                self._world.mob_spawners = parse_utils.load_mob_spawners(world['world']['spawners'], self.locations, self._catalogue._creatures, self._catalogue._items)
            if world['world'].get('item_spawners', None):
                self._world.item_spawners = parse_utils.load_item_spawners(world['world']['item_spawners'], self._zones, self._catalogue._items)

        llm_cache.load(parse_utils.load_json(self.path +'llm_cache.json'))

        # check if there are predefined items for the setting
        extra_items = generic.generic_items.get(self.check_setting(self.config.type), [])
        if extra_items:
            for item in extra_items:
                self._catalogue.add_item(item)


    def welcome(self, player: Player) -> str:
        player.tell("<bright>Welcome to `%s'.</>" % self.config.name, end=True)
        player.tell("\n")
        player.tell("\n")
        return ""

    def welcome_savegame(self, player: Player) -> str:
        return ""  # not supported in demo

    def goodbye(self, player: Player) -> None:
        player.tell("Thanks for trying out LlamaTale!")


