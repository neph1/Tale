import tale
from tale.base import Location, Item, Living
from tale.driver import Driver
from tale.llm_ext import DynamicStory
from tale.player import Player
from tale.story import StoryBase, StoryConfig
import tale.parse_utils as parse_utils
from tale.zone import Zone

class JsonStory(DynamicStory):
    
    def __init__(self, path: str, config: StoryConfig):
        self.config = config
        self.path = path
        locs = {}
        for zone in self.config.zones:
            zones, exits = parse_utils.load_locations(parse_utils.load_json(self.path +'zones/'+zone + '.json'))
        for name in zones.keys():
            zone = zones[name]
            for loc in zone.locations.values():
                locs[loc.name] = loc
        self._locations = locs
        self._zones = zones # type: dict(str, dict)
        self._npcs = parse_utils.load_npcs(parse_utils.load_json(self.path +'npcs/'+self.config.npcs + '.json'), self._zones)
        self._items = parse_utils.load_items(parse_utils.load_json(self.path + self.config.items + '.json'), self._zones)
        
    def init(self, driver) -> None:
        pass
        

    def welcome(self, player: Player) -> str:
        player.tell("<bright>Welcome to `%s'.</>" % self.config.name, end=True)
        player.tell("\n")
        player.tell("\n")
        return ""

    def welcome_savegame(self, player: Player) -> str:
        return ""  # not supported in demo

    def goodbye(self, player: Player) -> None:
        player.tell("Thanks for trying out Tale!")


