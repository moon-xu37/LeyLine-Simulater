from typing import TYPE_CHECKING, List, Mapping
from core.rules.damage import AMP_DMG
from core.rules.health import Health
from core.rules.alltypes import \
    (DamageType, ElementalReactionType, ElementType, NumericType, HealthType)
from core.entities.creation import Creation
from core.entities.buff import *
from core.entities.enemy import Enemy
from core.entities.panel import EntityPanel
from core.simulation.event import *
if TYPE_CHECKING:
    from core.simulation.simulation import Simulation


class NumericController(object):
    '''
    控制所有数值事件\n
    操作树结构 保证树的干净和可恢复\n
    定时自动更新 记录时间间隔内的全部数值
    '''
    __instance = None

    def __new__(cls, *args, **kwargs):
        if not cls.__instance:
            cls.__instance = object.__new__(cls, *args, **kwargs)
        return cls.__instance

    __interest_data = [
        'ATK', 'DEF', 'HP', 'EM', 'ER', 'CRIT_RATE', 'CRIT_DMG',
        'SHIELD_STRENGTH', 'ANEMO_DMG', 'GEO_DMG', 'ELECTRO_DMG',
        'HYDRO_DMG', 'PYRO_DMG', 'CRYO_DMG', 'DENDRO_DMG', 'PHYSICAL_DMG'
    ]

    def __init__(self):
        if hasattr(self, 'enemy'):
            return
        self.enemy = Enemy()
        self.dynamic_buffs_attr: List[Buff] = []
        self.dynamic_buffs_dmg: List[Buff] = []
        self.const_buffs_attr: List[Buff] = []
        self.const_buffs_dmg: List[Buff] = []
        self.char_attr_log = {}
        self.onstage_log = {}
        self.energy_log = {}
        self.dmg_log = {}
        self.heal_log = {}
        self.shield_log = {}
        self.clock_time = 0.1

    def execute(self, simulation: 'Simulation', event: 'Event'):
        if event.type == EventType.TRY and event.subtype == 'init':
            self.reset()
            self.log_init(simulation.characters)
            self.triggers_init(simulation)
            self.energy_init(simulation)
            return

        if event.time > simulation.clock:
            while(event.time > simulation.clock):
                flag = self.refresh(simulation)
                self.character_info_enquire(simulation, flag)
                simulation.clock += self.clock_time

        self.triggers_call(simulation, event)

        if event.type == EventType.DAMAGE:
            self.damage_case(simulation, event)
        elif event.type == EventType.HEALTH:
            self.health_case(simulation, event)
        elif event.type == EventType.NUMERIC:
            self.numeric_case(simulation, event)
        elif event.type == EventType.ELEMENT:
            self.element_case(simulation, event)

    def set_enemy(self, **configs):
        self.enemy = Enemy(**configs)

    def set_interval(self, interval: float):
        self.clock_time = interval

    def reset(self):
        for k, v in self.__dict__.items():
            if isinstance(v, list) or isinstance(v, dict):
                v.clear()

    def damage_case(self, simulation: 'Simulation', event: 'Event'):
        damage = AMP_DMG()
        # connect to event
        damage.connect(event)
        damage.connect(self.enemy)

        source = event.source.source
        if isinstance(source, Creation):
            # snapshot
            if getattr(source, 'attr_panel', None):
                damage.connect(source.attr_panel)
            # dynamic
            else:
                panel = EntityPanel(source.source.source)
                damage.connect(panel)
        else:
            panel = EntityPanel(source)
            damage.connect(panel)

        # constant buff
        buffs = [b for b in self.const_buffs_dmg
                 if b.trigger(simulation, event) and
                 (not b.target_path or event.sourcename in b.target_path)]
        # dynamic buff
        buffs.extend([b for b in self.dynamic_buffs_dmg
                      if b.trigger(simulation, event) and
                      (not b.target_path or event.sourcename in b.target_path)])
        for b in buffs:
            damage.connect(b)

        apply_flag, amp_flag, react_type, react_multi = self.enemy.attacked_by(
            event)
        # whether apply element
        if apply_flag and event.elem != ElementType.NONE and event.elem != ElementType.PHYSICAL:
            self.apply_element(simulation, event)
        # whether reaction
        if react_type != ElementalReactionType.NONE:
            react_event = self.react_event(event, react_multi, react_type)
            simulation.event_queue.put(react_event)
            if amp_flag:
                damage.connect(react_event)

        numeric_event = NumericEvent(time=event.time,
                                     subtype=NumericType.DAMAGE,
                                     sourcename=event.sourcename,
                                     obj=damage,
                                     desc=event.desc)
        simulation.event_queue.put(numeric_event)
    
    def health_case(self, simulation: 'Simulation', event: 'Event'):
        health = Health()
        # connect to event
        health.connect(event)
        
        source = event.source.source
        if isinstance(source, Creation):
            # snapshot
            if getattr(source, 'attr_panel', None):
                health.connect(source.attr_panel)
            # dynamic
            else:
                panel = EntityPanel(source.source.source)
                health.connect(panel)
        else:
            panel = EntityPanel(source)
            health.connect(panel)
        
        numeric_event = NumericEvent(time=event.time,
                                     subtype=NumericType.HEALTH,
                                     sourcename=event.sourcename,
                                     obj=health,
                                     desc=event.desc)
        simulation.event_queue.put(numeric_event)
        

    def numeric_case(self, simulation: 'Simulation', event: 'Event'):
        if event.subtype == NumericType.DAMAGE:
            self.enemy.hurt(event.obj.value)
            self.dmg_log[event.sourcename][event.obj.damage_type.name].append(
                (event.time, event.obj.value))
        elif event.subtype == NumericType.HEALTH:
            for t in event.obj.target:
                simulation.characters[t].attribute.hp_now += event.obj.value
            self.heal_log[event.sourcename].append((event.time, event.obj.value))
        elif event.subtype == NumericType.SHIELD:
            pass

    def element_case(self, simulation: 'Simulation', event: 'Event'):
        return

    def insert_to(self, buff: 'Buff', type: str, simulation: 'Simulation'):
        '''
        insert buff into the controller\n
        dynamic_attr | da\n
        dynamic_dmg | dd\n
        const_attr | ca\n
        const_dmg | cd\n
        '''
        if type == 'dynamic_attr' or type == 'da':
            if buff not in self.dynamic_buffs_attr:
                self.dynamic_buffs_attr.append(buff)
                for name in simulation.characters.keys():
                    if not buff.target_path[0] or name in buff.target_path[0]:
                        simulation.characters[name].attribute.connect(buff)

        elif type == 'const_attr' or type == 'ca':
            if buff not in self.const_buffs_attr:
                self.const_buffs_attr.append(buff)
                for name in simulation.characters.keys():
                    if not buff.target_path[0] or name in buff.target_path[0]:
                        simulation.characters[name].attribute.connect(buff)

        elif type == 'dynamic_dmg' or type == 'dd':
            if buff not in self.dynamic_buffs_dmg:
                self.dynamic_buffs_dmg.append(buff)

        elif type == 'const_dmg' or type == 'cd':
            if buff not in self.const_buffs_dmg:
                self.const_buffs_dmg.append(buff)

    def log_init(self, characters: Mapping):
        self.char_attr_log = dict.fromkeys(characters.keys())
        for k in self.char_attr_log:
            self.char_attr_log[k] = dict.fromkeys(self.__interest_data)
            self.energy_log[k] = []
            self.onstage_log[k] = []
            self.heal_log[k] = []
            self.shield_log[k] = []
            self.dmg_log[k] = dict.fromkeys(DamageType.__members__.keys())
            for in_k in self.__interest_data:
                self.char_attr_log[k][in_k] = []
            for type_k in DamageType.__members__.keys():
                self.dmg_log[k][type_k] = []

    def triggers_init(self, simulation: 'Simulation'):
        for character in simulation.characters.values():
            # TODO call all the passive, constellation
            # weapon and artifact passive buff
            ev = TryEvent(subtype='init')
            for passive in character.action.PASSIVE:
                passive(simulation, ev)
            for cx in character.action.CX:
                cx(simulation, ev)
            character.weapon.work(simulation, ev)
            character.artifact.work(simulation, ev)

    def energy_init(self, simulation: 'Simulation'):
        if not simulation.energy_full:
            return
        for character in simulation.characters.values():
            character.energy.receive(200)

    def triggers_call(self, simulation: 'Simulation', event: 'Event'):
        for name, character in simulation.characters.items():
            for passive in character.action.PASSIVE:
                passive(simulation, event)
            for cx in character.action.CX:
                cx(simulation, event)
            character.weapon.work(simulation, event)
            character.artifact.work(simulation, event)

    def refresh(self, simulation: 'Simulation') -> bool:
        time = simulation.clock
        flag = False
        for b in self.dynamic_buffs_attr:
            if b.constraint.end < time:
                self.dynamic_buffs_attr.remove(b)
                for name in simulation.characters.keys():
                    if not b.target_path[0] or name in b.target_path[0]:
                        simulation.characters[name].attribute.disconnect(b)
                flag = True
                break
            if b.trigger:
                tmpflag = b.trigger(simulation)
                flag = True if flag or tmpflag else False
        for b in self.dynamic_buffs_dmg:
            if b.constraint.end < time:
                self.dynamic_buffs_dmg.remove(b)
                flag = True
        return flag

    def character_info_enquire(self, simulation: 'Simulation', flag: bool):
        self.onstage_log[simulation.onstage].append(simulation.clock)
        for name, character in simulation.characters.items():
            self.energy_log[name].append(character.energy.count)
            for data in self.__interest_data:
                if flag or not self.char_attr_log[name][data]:
                    v = getattr(character.attribute, data).value
                else:
                    v = self.char_attr_log[name][data][-1]
                self.char_attr_log[name][data].append(v)

    def apply_element(self, simulation: 'Simulation', event: 'Event'):
        apply_event = ElementEvent(time=event.time,
                                   subtype='apply',
                                   sourcename=event.sourcename,
                                   elem=event.elem,
                                   num=event.icd.GU,
                                   desc=f'{event.sourcename}: apply {event.elem} {event.icd.GU}')
        simulation.event_queue.put(apply_event)

    def react_event(self, event: 'Event', react_multi, react_type):
        return ElementEvent(time=event.time,
                            subtype='reaction',
                            source=event.source,
                            sourcename=event.sourcename,
                            elem=event.elem,
                            num=react_multi,
                            react=react_type,
                            desc=f'{event.sourcename}: trigger {react_type}')

    def onstage_record(self) -> List[List]:
        '''return List[(name, start, end)]'''
        time_map = [(t, k) for k, v in self.onstage_log.items() for t in v]
        time_map.sort(key=lambda x: x[0])
        result = []
        tmp_name = time_map[0][1]
        result.append([tmp_name, 0, 0])
        for t, name in time_map:
            if name != tmp_name:
                result[-1][-1] = t
                tmp_name = name
                result.append([tmp_name, t, 0])
        result[-1][-1] = time_map[-1][0]
        return result
