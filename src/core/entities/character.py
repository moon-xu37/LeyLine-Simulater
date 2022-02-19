import json
from typing import Callable, Mapping, Sequence, Dict, List, Any, Tuple
from core.entities.artifact import Artifact
from core.entities.weapon import Weapon
from core.rules import DNode
from data.characters import *


class Character(object):
    def __init__(self):
        self.base: CharacterBase = CharacterBase()
        self.attribute: CharacterAttribute = CharacterAttribute()
        self.action: CharacterAction = CharacterAction()
        self.artifact: Artifact = Artifact()
        self.weapon: Weapon = Weapon()

    def set_base(self, **configs):
        if 'name' in configs.keys():
            self.base.choose(configs['name'])
            self.update()
        if 'lv' in configs.keys() and 'asc' in configs.keys() and self.base.name:
            self.base.set_lv(configs['lv'], configs['asc'])
            self.update()
        if self.base.name and self.base.lv:
            self.action.attach_skill(configs['name'], self)
    
    def set_talents(self, norm=1, skill=1, burst=1, cx=0):
        self.attribute.update_talents(norm, skill, burst, cx, self.base.asc)
        self.action.attach_skill(self.base.name, self)

    def equip(self, *items):
        for item in items:
            if not item:
                continue
            elif isinstance(item, Weapon):
                self.weapon = item
            elif isinstance(item, Artifact):
                self.artifact = item
            else:
                self.artifact.equip(item)
        self.update()

    def update(self):
        self.attribute.update_base(self.base)
        self.attribute.update_weapon(self.weapon)
        self.attribute.update_artifact(self.artifact)

    @property
    def name(self):
        return self.base.name


class CharacterBase(object):
    with open('./docs/constant/CharacterLevelMultiplier.json', 'r') as f:
        __lv_curve: Dict[str, List[float]] = json.load(f)

    with open('./docs/constant/CharacterConfig.json', 'r') as f:
        __char_info: Dict[str, Dict] = json.load(f)

    def __init__(self, **configs):
        self.name: str = ''
        self.rarity: str = ''
        self.weapon: int = 0
        self.element: int = 0
        self.region: int = 0
        self.lv: int = 0
        self.asc: int = 0
        self.asc_info: Mapping[str, List[float]] = {}
        self.HP_BASE: float = 0
        self.ATK_BASE: float = 0
        self.DEF_BASE: float = 0
        self.HP: float = 0
        self.ATK: float = 0
        self.DEF: float = 0
        self.EXTRA: Sequence[str, float] = ['', 0]
        self.initialize(**configs)

    def initialize(self, **configs) -> None:
        if 'name' in configs.keys():
            self.choose(configs['name'])
        if 'lv' in configs.keys() and 'asc' in configs.keys() and self.name:
            self.set_lv(configs['lv'], configs['asc'])

    def choose(self, name: str) -> None:
        self.name = name
        c = self.__char_info.get(name)
        self.rarity = str(c['rarity'])
        self.weapon = c['weapon']
        self.element = c['element']
        self.region = c['region']
        self.HP_BASE = c['HP_BASE']
        self.ATK_BASE = c['ATK_BASE']
        self.DEF_BASE = c['DEF_BASE']
        self.asc_info = c['asc']

    def set_lv(self, lv: int, asc: bool) -> None:
        if not self.name:
            return
        self.lv = lv
        self.asc = self.set_asc(lv, asc)
        lv_list = self.__lv_curve[self.rarity]
        self.HP = self.HP_BASE * lv_list[self.lv]
        self.ATK = self.ATK_BASE * lv_list[self.lv]
        self.DEF = self.DEF_BASE * lv_list[self.lv]
        if self.asc:
            self.HP += self.asc_info['HP_BASE'][self.asc-1]
            self.ATK += self.asc_info['ATK_BASE'][self.asc-1]
            self.DEF += self.asc_info['DEF_BASE'][self.asc-1]
            for k in self.asc_info.keys():
                if 'BASE' not in k:
                    self.EXTRA[0] = k
                    self.EXTRA[1] = self.asc_info[k][self.asc-1]
                    break
        else:
            self.EXTRA[0] = [
                k for k in self.asc_info.keys() if 'BASE' not in k][0]
            self.EXTRA[1] = 0

    @staticmethod
    def set_asc(lv: int, asc: bool) -> int:
        if lv <= 20:
            return (lv + int(asc))//21
        elif (20 < lv < 40):
            return lv // 20
        elif (lv % 10 != 0):
            return lv // 10 - 2
        else:
            return min(lv // 10 - 3 + int(asc), 6)

    def show(self) -> None:
        print('Name:{}\nLv:{}\nHP:{:.3f} / ATK:{:.3f} / DEF:{:.3f} / {}:{:.3f}'.format(
            self.name, self.lv,
            self.HP, self.ATK, self.DEF, self.EXTRA[0], self.EXTRA[1]))


class CharacterAction(object):
    with open('./docs/constant/SkillConfig.json', 'r') as f:
        __skill_info: Dict[str, Dict] = json.load(f)
        
    def __init__(self) -> None:
        '''
        ### 属性:
        battle action\n
        \tNORMAL_ATK: Callable\n
        \tELEM_SKILL: Callable\n
        \tELEM_BURST: Callable\n
        \tPASSIVE: Callable\n
        \tCX: Callable\n
        numeric action\n
        \tuse_artifact: Callable\n
        \tuse_weapon: Callable\n
        '''
        # battle action
        self.NORMAL_ATK: Callable = None
        self.ELEM_SKILL: Callable = None
        self.ELEM_BURST: Callable = None
        self.PASSIVE: Callable = None
        self.CX: Callable = None
        # numeric action
        self.use_artifact: Callable = None
        self.use_weapon: Callable = None
        # scalers
        self.normatk_scaler: Dict[str, List[float]] = {}
        self.elemskill_scaler: Dict[str, List[float]] = {}
        self.elemburst_scaler: Dict[str, List[float]] = {}

    def attach_skill(self, name, character: Character):
        self.normatk_scaler = self.__skill_info[name]['A']
        self.elemskill_scaler = self.__skill_info[name]['E']
        self.elemburst_scaler = self.__skill_info[name]['Q']
        exec(f'self.NORMAL_ATK = {name}NormATK(character)')
        exec(f'self.ELEM_SKILL = {name}Elemskill(character)')
        exec(f'self.ELEM_BURST = {name}Elemburst(character)')


class CharacterAttribute(object):
    def __init__(self) -> None:
        '''
        ### 包含面板属性\n
        include panel attributes:\n
        \tATK | DEF | HP | EM | ER | CRIT_RATE | CRIT_DMG\n
        \tHEAL_BONUS | HEAL_INCOME | SHIELD_STRENGTH | CD_REDUCTION\n
        \tELEM_DMG... | ELEM_RES...\n
        ### 和其他隐藏属性\n
        and other character attributes:\n
        \tENERGY | STAMINA | STAMINA_CONSUMPTION\n
        \tATK_SPD | MOVE_SPD | INTERRUPT_RES | DMG_REDUCTION\n
        '''
        # panel attributes
        self.ATK: DNode = self.tree_expr('ATK')
        self.DEF: DNode = self.tree_expr('DEF')
        self.HP: DNode = self.tree_expr('HP')
        self.EM = DNode('Total EM', '+')
        self.ER = DNode('Total ER', '+')
        self.CRIT_RATE = DNode('Total CRIT_RATE', '+')
        self.CRIT_DMG = DNode('Total CRIT_DMG', '+')
        self.HEAL_BONUS = DNode('Total HEAL_BONUS', '+')
        self.HEAL_INCOME = DNode('Total HEAL_INCOME', '+')
        self.SHIELD_STRENGTH = DNode('Total SHIELD_STRENGTH', '+')
        self.CD_REDUCTION = DNode('Total CD_REDUCTION', '+')
        self.ANEMO_DMG = DNode('Total ANEMO_DMG', '+')
        self.GEO_DMG = DNode('Total GEO_DMG', '+')
        self.ELECTRO_DMG = DNode('Total ELECTRO_DMG', '+')
        self.HYDRO_DMG = DNode('Total HYDRO_DMG', '+')
        self.PYRO_DMG = DNode('Total PYRO_DMG', '+')
        self.CRYO_DMG = DNode('Total CRYO_DMG', '+')
        self.DENDRO_DMG = DNode('Total DENDRO_DMG', '+')
        self.PHYSICAL_DMG = DNode('Total PHYSICAL_DMG', '+')
        # other attributes
        self.ENERGY: float = 0
        self.STAMINA: float = 0
        self.STAMINA_CONSUMPTION: float = 0
        self.ATK_SPD: float = 0
        self.MOVE_SPD: float = 0
        self.INTERRUPT_RES: float = 0
        self.DMG_REDUCTION: float = 0
        # talent attributes
        self.normatk_lv: int = 1
        self.elemskill_lv: int = 1
        self.elemburst_lv: int = 1
        self.passive_lv = 0
        self.cx_lv: int = 0

    def tree_expr(self, stat: str) -> DNode:
        root = DNode(f'Total {stat}', '+')
        root.extend([
            DNode(f'Scaled {stat}', '*').extend([
                DNode(f'{stat} Base', '+').extend([
                    DNode(f'Charater {stat} Base'),
                    DNode(f'Weapon {stat} Base')
                ]),
                DNode(f'{stat} Scalers', '+').extend([
                    DNode('Artifact Scalers', '+').extend([
                        DNode('Main Stat Scaler', '+'),
                        DNode('Sub Stat Scaler', '+')
                    ]),
                    DNode('Bonus Scalers', '+'),
                    DNode('Weapon Scaler', '%'),
                    DNode('Ascension Scaler')
                ])
            ]),
            DNode(f'Flat {stat}', '+').extend([
                DNode('Artifact Flat', '+'),
                DNode('Bonus Flat', '+')
            ]),
            DNode(f'Bonus {stat}', '+').extend([
                DNode(f'Skill Transform {stat}', '*').extend([
                    DNode('Skill Transform Stat'),
                    DNode('Skill Transform Scaler', '%')
                ]),
                DNode(f'Weapon Transform {stat}', '*').extend([
                    DNode('Weapon Transform Stat'),
                    DNode('Weapon Transform Scaler', '%')
                ])
            ])
        ])
        return root

    def update_base(self, base: CharacterBase):
        for k in ['ATK', 'DEF', 'HP']:
            self.__dict__[k].modify(
                f'Charater {k} Base',
                num=base.__dict__[k]
            )
        for k, n in zip(['ER', 'CRIT_RATE', 'CRIT_DMG'], [100, 5, 50]):
            try:
                self.__dict__[k].find(f'Character {k} Base')
            except:
                self.__dict__[k].insert(DNode(f'Character {k} Base', '%', n))

        if base.EXTRA[0] in ['ATK_PER', 'DEF_PER', 'HP_PER']:
            k = base.EXTRA[0].split('_')[0]
            self.__dict__[k].modify('Ascension Scaler', num=base.EXTRA[1])
        else:
            try:
                self.__dict__[k].modify(f'Character {k} Ascension', num=n)
            except:
                self.__dict__[k].insert(DNode(f'Character {k} Ascension', num=n))

    def update_weapon(self, weapon: Weapon):
        self.ATK.modify('Weapon ATK Base', num=weapon.base.ATK)

    def update_artifact(self, artifact: Artifact) -> None:
        for s in ['ATK', 'DEF', 'HP', 'EM', 'ER', 'CRIT_RATE', 'CRIT_DMG', 'HEAL_BONUS',
                  'ANEMO_DMG', 'GEO_DMG', 'ELECTRO_DMG', 'HYDRO_DMG', 'PYRO_DMG', 'CRYO_DMG',
                  'PHYSICAL_DMG']:
            que: List[DNode] = []
            que.append(self.__dict__[s])
            while(que):
                p = que.pop(0)
                if not p.leaf:
                    for i, c in enumerate(p.child):
                        for k in ['FLOWER', 'PLUME', 'SANDS', 'GOBLET', 'CIRCLET']:
                            if k in c.key:
                                del p.child[i]
                    que.extend(p.child)

        for pos_index, art_piece in enumerate(artifact.artifacts):
            if not art_piece:
                continue
            val = art_piece.value_data()

            main_name = art_piece.main_stat.name
            main_key = 'Main {} {}'.format(
                art_piece.pos_type.name, main_name)
            main_value = val[art_piece.main_stat.name]
            if 'CONST' in main_name or 'PER' in main_name:
                main_name = main_name.split('_')[0]
            if 'PER' in art_piece.main_stat.name:
                self.__dict__[main_name].find('Main Stat Scaler').insert(
                    DNode(main_key, '%', main_value))
            elif 'CONST' in art_piece.main_stat.name:
                self.__dict__[main_name].find('Artifact Flat').insert(
                    DNode(main_key, '', main_value))
            elif main_name == 'EM':
                self.__dict__[main_name].insert(
                    DNode(main_key, '', main_value))
            else:
                self.__dict__[main_name].insert(
                    DNode(main_key, '%', main_value))

            for sub, sub_num in val.items():
                if sub == art_piece.main_stat.name:
                    continue
                sub_key = 'Sub {} {}'.format(art_piece.pos_type.name, sub)
                if 'PER' in sub:
                    self.__dict__[sub.split('_')[0]].find('Sub Stat Scaler').insert(
                        DNode(sub_key, '%', sub_num))
                elif 'CONST' in sub:
                    self.__dict__[sub.split('_')[0]].find('Artifact Flat').insert(
                        DNode(sub_key, '', sub_num))
                elif sub == 'EM':
                    self.__dict__[sub].insert(
                        DNode(sub_key, '', sub_num))
                else:
                    self.__dict__[sub].insert(
                        DNode(sub_key, '%', sub_num))
    
    def update_talents(self, norm, skill, burst, cx, asc):
        self.normatk_lv = norm
        self.elemskill_lv = skill
        self.elemburst_lv = burst
        self.cx_lv = cx
        if asc < 3:
            self.passive_lv = 0
        elif asc < 5:
            self.passive_lv = 1
        else:
            self.passive_lv = 2


# def visualize(a) -> None:
#     que: List = []
#     que.append((a, 0))
#     while (que):
#         c, n = que.pop(0)
#         print('\t'*n+'->', f'[{c.key}][{c.func}][ {c.num} ]')
#         if not c.leaf:
#             for i in range(len(c.child)):
#                 que.insert(i, (c.child[i], n+1))

# d = CharacterAttribute()
# visualize(d.DEF)
