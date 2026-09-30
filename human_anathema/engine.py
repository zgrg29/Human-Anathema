"""Pure-Python campaign rules. Inputs and outputs are JSON-serializable dicts."""
from copy import deepcopy
from .catalog import load_catalog


class GameError(ValueError):
    """An invalid game action with a player-readable message."""


class Game:
    def __init__(self, catalog=None):
        self.catalog = catalog or load_catalog()
        self.reset()

    def reset(self):
        hero = deepcopy(self.catalog["characters"]["protagonist"])
        self.state = {
            "version": 1, "location_id": "rookie_village", "player": hero,
            "inventory": {"coin": 30, "small_round": 6, "bandage": 2, "flash_bomb": 1,
                          "wolf_fang": 0, "wolf_hide": 0, "wolf_blood": 0},
            "equipment": {"weapon": "service_pistol", "armor": "patched_vest"},
            "known_skills": ["aimed_shot"], "known_magic": [], "battle": None,
            "corruption": 0, "flags": {"first_victory": False}, "log": ["你来到新手村。村外的废弃水渠里有低危怪物出没。"],
        }
        return self.response()

    def response(self, events=None):
        return {"ok": True, "state": deepcopy(self.state), "events": events or []}

    def _event(self, text):
        self.state["log"].append(text)
        self.state["log"] = self.state["log"][-30:]
        return text

    def _require(self, condition, message):
        if not condition:
            raise GameError(message)

    def _player(self):
        return self.state["player"]

    def _gear(self, slot=None):
        gear = self.catalog["equipment"]
        return gear[self.state["equipment"][slot]] if slot else gear

    def _attack(self, actor, target, power, weapon=None, label="攻击"):
        player_actor = actor is self._player()
        defense = target["attributes"].get("defense", 0)
        if player_actor and weapon:
            buff_attack = sum(self.catalog["buffs"].get(buff_id, {}).get("effects", {}).get("physical_attack", 0)
                              for buff_id in actor.get("buffs", {}))
            damage = max(1, actor["attributes"]["physical_attack"] + buff_attack + weapon.get("attack", 0) + power - defense)
        else:
            damage = max(1, actor["attributes"].get("physical_attack", 1) + power - defense)
        if target.get("guarding"):
            damage = max(0, damage // 2)
            target["guarding"] = False
        shield = target.get("shield", 0)
        absorbed = min(shield, damage)
        target["shield"] = shield - absorbed
        hp_loss = damage - absorbed
        target["hp"] = max(0, target["hp"] - hp_loss)
        return f"{label}造成 {damage} 伤害（护盾吸收 {absorbed}，生命损失 {hp_loss}）。"

    def _end_battle(self, events):
        battle = self.state["battle"]
        enemy = battle["enemy"]
        for item, count in enemy.get("drops", {}).items():
            self.state["inventory"][item] = self.state["inventory"].get(item, 0) + count
            events.append(self._event(f"获得素材：{self.catalog['items'][item]['name']} ×{count}。"))
        self.state["player"]["experience_notes"] += 1
        self.state["flags"]["first_victory"] = True
        self.state["battle"] = None
        events.append(self._event(f"{enemy['name']}被击倒了。获得战斗记录 ×1。"))

    def _enemy_turn(self, events):
        battle = self.state["battle"]
        if not battle:
            return
        enemy = battle["enemy"]
        if enemy["hp"] <= 0:
            self._end_battle(events)
            return
        if battle.get("skip_enemy_turn", 0):
            battle["skip_enemy_turn"] -= 1
            events.append(self._event(f"{enemy['name']}被闪光弹扰乱，错过行动。"))
            self._finish_round()
            return
        heavy = battle["turn"] % 3 == 0
        move = enemy["moves"]["heavy_attack" if heavy else "basic_attack"]
        events.append(self._event(f"{enemy['name']}使用{move['name']}！"))
        events.append(self._event(self._attack(enemy, self._player(), move.get("power", 0), label=move["name"])))
        battle["turn"] += 1
        self._player()["ap"] = self._player()["ap_max"]
        self._finish_round()
        if self._player()["hp"] <= 0:
            battle["result"] = "defeat"
            events.append(self._event("你倒下了。这场遭遇失败，可以重新开始旅程。"))

    def _finish_round(self):
        buffs = self._player().get("buffs", {})
        for buff_id in list(buffs):
            buffs[buff_id] -= 1
            if buffs[buff_id] <= 0:
                del buffs[buff_id]

    def act(self, action):
        """Apply one command. Each successful battle command spends one player turn."""
        action = dict(action or {})
        kind = action.get("type")
        events = []
        p = self._player()
        try:
            if kind == "reset":
                return self.reset()
            if kind == "start_encounter":
                self._require(not self.state["battle"], "战斗尚未结束。")
                self._require(self.state["location_id"] == "rookie_village", "这里没有可挑战的遭遇。")
                encounter_id = action.get("encounter_id", "drain_hound")
                encounter = self.catalog["encounters"].get(encounter_id)
                self._require(encounter is not None, "找不到这个遭遇。")
                enemy = deepcopy(self.catalog["enemies"][encounter["enemy_id"]])
                self.state["battle"] = {"encounter_id": encounter_id, "enemy": enemy, "turn": 1,
                                         "skip_enemy_turn": 0, "result": None}
                events.append(self._event(f"遭遇：{enemy['name']}。{encounter['description']}"))
            elif self.state["battle"] and kind in ("attack", "defend", "skill", "cast", "use_item", "equip", "inject", "flee"):
                battle = self.state["battle"]
                self._require(battle["result"] is None, "战斗已经结束，请重新开始旅程。")
                if kind == "attack":
                    weapon = self._gear("weapon")
                    ammo_item = weapon.get("ammo_item")
                    if ammo_item:
                        self._require(self.state["inventory"].get(ammo_item, 0) > 0, "弹药不足。")
                        self.state["inventory"][ammo_item] -= 1
                    events.append(self._event(self._attack(p, battle["enemy"], 0, weapon, "普通攻击")))
                elif kind == "defend":
                    p["guarding"] = True
                    events.append(self._event("你进入防御姿态；下一次受到的伤害减半。"))
                elif kind == "skill":
                    skill_id = action.get("skill_id")
                    self._require(skill_id in self.state["known_skills"], "尚未学会这项技能。")
                    skill = self.catalog["skills"][skill_id]
                    self._require(p["ap"] >= skill["ap_cost"], "AP 不足。")
                    ammo_item = skill.get("ammo_item")
                    if ammo_item:
                        self._require(self.state["inventory"].get(ammo_item, 0) > 0, "弹药不足。")
                        self.state["inventory"][ammo_item] -= 1
                    p["ap"] -= skill["ap_cost"]
                    events.append(self._event(self._attack(p, battle["enemy"], skill["power"], self._gear("weapon"), skill["name"])))
                elif kind == "cast":
                    spell_id = action.get("spell_id")
                    self._require(spell_id in self.state["known_magic"], "尚未解锁这项魔法。注射特定体液可能带来异变能力。")
                    spell = self.catalog["magic"][spell_id]
                    self._require(p["mp"] >= spell["mp_cost"], "MP 不足。")
                    p["mp"] -= spell["mp_cost"]
                    amount = max(0, p["attributes"]["magic_attack"] + spell["power"] - battle["enemy"]["attributes"]["defense"])
                    enemy = battle["enemy"]
                    absorbed = min(enemy.get("shield", 0), amount)
                    enemy["shield"] -= absorbed
                    hp_loss = amount - absorbed
                    enemy["hp"] = max(0, enemy["hp"] - hp_loss)
                    events.append(self._event(f"施放{spell['name']}，造成 {amount} 魔法伤害（护盾吸收 {absorbed}，生命损失 {hp_loss}）。"))
                elif kind == "use_item":
                    item_id = action.get("item_id")
                    item = self.catalog["items"].get(item_id)
                    self._require(item and item.get("kind") == "consumable", "这不是可使用的道具。")
                    self._require(self.state["inventory"].get(item_id, 0) > 0, "道具数量不足。")
                    self.state["inventory"][item_id] -= 1
                    if item.get("effect") == "heal":
                        healed = min(item["power"], p["attributes"]["max_hp"] - p["hp"])
                        p["hp"] += healed
                        events.append(self._event(f"使用{item['name']}，恢复 {healed} HP。"))
                    elif item.get("effect") == "stun":
                        battle["skip_enemy_turn"] += 1
                        events.append(self._event(f"使用{item['name']}，敌人将错過下次行动。"))
                elif kind == "equip":
                    slot, item_id = action.get("slot"), action.get("item_id")
                    self._require(slot in ("weapon", "armor"), "装备槽无效。")
                    item = self.catalog["equipment"].get(item_id)
                    self._require(item and item["slot"] == slot, "装备不适用于这个槽位。")
                    self._require(self.state["inventory"].get(item_id, 0) > 0 or self.state["equipment"].get(slot) == item_id, "你没有这件装备。")
                    self.state["equipment"][slot] = item_id
                    if slot == "armor":
                        p["shield_max"] = item["shield"]
                        p["shield"] = min(p["shield"], p["shield_max"])
                    events.append(self._event(f"切换装备：{item['name']}。"))
                elif kind == "inject":
                    sample_id = action.get("sample_id")
                    sample = self.catalog["samples"].get(sample_id)
                    self._require(sample is not None, "未知体液样本。")
                    self._require(self.state["inventory"].get(sample_id, 0) > 0, "没有这种体液样本。")
                    self.state["inventory"][sample_id] -= 1
                    self.state["corruption"] = min(100, self.state.get("corruption", 0) + sample["corruption_gain"])
                    p["hp"] = min(p["attributes"]["max_hp"], p["hp"] + sample["heal"])
                    p["mp_max"] = max(p["mp_max"], sample.get("mp_max", 0))
                    p["mp"] = min(p["mp_max"], p["mp"] + sample.get("mp_restore", 0))
                    for skill_id in sample.get("grants_skills", []):
                        if skill_id not in self.state["known_skills"]:
                            self.state["known_skills"].append(skill_id)
                    for spell_id in sample.get("grants_magic", []):
                        if spell_id not in self.state["known_magic"]:
                            self.state["known_magic"].append(spell_id)
                    for buff in sample.get("buffs", []):
                        p.setdefault("buffs", {})[buff["buff_id"]] = buff["duration"]
                    events.append(self._event(f"注射{sample['name']}：恢复 {sample['heal']} HP，侵蚀度 +{sample['corruption_gain']}%。"))
                else:  # flee
                    self.state["battle"] = None
                    events.append(self._event("你撤出了战斗。"))
                if self.state["battle"] and battle["enemy"]["hp"] <= 0:
                    self._end_battle(events)
                elif self.state["battle"]:
                    self._enemy_turn(events)
            elif kind in ("equip", "inject"):
                if kind == "equip":
                    slot, item_id = action.get("slot"), action.get("item_id")
                    self._require(slot in ("weapon", "armor"), "装备槽无效。")
                    item = self.catalog["equipment"].get(item_id)
                    self._require(item and item["slot"] == slot, "装备不适用于这个槽位。")
                    self._require(self.state["inventory"].get(item_id, 0) > 0 or self.state["equipment"].get(slot) == item_id, "你没有这件装备。")
                    self.state["equipment"][slot] = item_id
                    if slot == "armor":
                        p["shield_max"] = item["shield"]
                        p["shield"] = min(p["shield"], p["shield_max"])
                    events.append(self._event(f"切换装备：{item['name']}。"))
                else:
                    sample_id = action.get("sample_id")
                    sample = self.catalog["samples"].get(sample_id)
                    self._require(sample is not None and self.state["inventory"].get(sample_id, 0) > 0, "没有这种体液样本。")
                    self.state["inventory"][sample_id] -= 1
                    self.state["corruption"] = min(100, self.state.get("corruption", 0) + sample["corruption_gain"])
                    healed = min(sample["heal"], p["attributes"]["max_hp"] - p["hp"])
                    p["hp"] += healed
                    p["mp_max"] = max(p["mp_max"], sample.get("mp_max", 0))
                    p["mp"] = min(p["mp_max"], p["mp"] + sample.get("mp_restore", 0))
                    for skill_id in sample.get("grants_skills", []):
                        if skill_id not in self.state["known_skills"]: self.state["known_skills"].append(skill_id)
                    for spell_id in sample.get("grants_magic", []):
                        if spell_id not in self.state["known_magic"]: self.state["known_magic"].append(spell_id)
                    for buff in sample.get("buffs", []): p.setdefault("buffs", {})[buff["buff_id"]] = buff["duration"]
                    events.append(self._event(f"注射{sample['name']}：恢复 {healed} HP，侵蚀度 +{sample['corruption_gain']}%。"))
            elif kind in ("buy", "sell", "extract", "craft", "rest"):
                self._require(not self.state["battle"], "战斗中不能使用村庄设施。")
                facility_id = action.get("facility_id", "village_shop" if kind in ("buy", "sell", "extract") else "net_cafe")
                facilities = self.catalog["facilities"]
                facility = facilities.get(facility_id)
                self._require(facility is not None, "找不到这个设施。")
                self._require(self.state["location_id"] in facility["locations"], "你不在这个设施所在地点。")
                if kind == "rest":
                    cost = facility["rest_cost"]
                    self._require(self.state["inventory"]["coin"] >= cost, f"休息需要 {cost} 枚硬币。")
                    self.state["inventory"]["coin"] -= cost
                    p["hp"] = p["attributes"]["max_hp"]
                    p["mp"] = p["mp_max"]
                    events.append(self._event(f"你在网咖休息，HP/MP 恢复。支付 {cost} 枚硬币。"))
                elif kind in ("extract", "craft"):
                    recipe_id = action.get("recipe_id", "extract_hound_blood")
                    recipe = self.catalog["recipes"].get(recipe_id)
                    self._require(recipe is not None and recipe.get("kind", "extract") == kind, "没有这项制作/提取配方。")
                    self._require(all(self.state["inventory"].get(k, 0) >= v for k, v in recipe["inputs"].items()), "素材不足，无法提取。")
                    for key, value in recipe["inputs"].items():
                        self.state["inventory"][key] -= value
                    for key, value in recipe["outputs"].items():
                        self.state["inventory"][key] = self.state["inventory"].get(key, 0) + value
                    events.append(self._event(f"提取完成：{recipe['name']}。"))
                else:
                    item_id = action.get("item_id")
                    if kind == "buy":
                        self._require(item_id in facility["stock"], "商店不出售这个物品。")
                        price = self.catalog["items"].get(item_id, {}).get("buy_price", self.catalog["equipment"].get(item_id, {}).get("buy_price", 0))
                        self._require(price > 0 and self.state["inventory"]["coin"] >= price, "硬币不足或商品无价格。")
                        self.state["inventory"]["coin"] -= price
                        self.state["inventory"][item_id] = self.state["inventory"].get(item_id, 0) + 1
                        events.append(self._event(f"购买{self.catalog['items'].get(item_id, self.catalog['equipment'].get(item_id))['name']}，支付 {price} 枚硬币。"))
                    else:
                        self._require(item_id in facility["buyback"], "商店不收购这个物品。")
                        self._require(self.state["inventory"].get(item_id, 0) > 0, "没有可出售的物品。")
                        price = facility["buyback"][item_id]
                        self.state["inventory"][item_id] -= 1
                        self.state["inventory"]["coin"] += price
                        events.append(self._event(f"出售{self.catalog['items'][item_id]['name']}，获得 {price} 枚硬币。"))
            else:
                raise GameError("当前不能执行这个行动。")
            return self.response(events)
        except GameError as error:
            return {"ok": False, "error": str(error), "state": deepcopy(self.state), "events": []}

    def state_json(self):
        return self.response()
