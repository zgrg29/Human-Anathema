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
            "version": 2, "location_id": "rookie_village", "player": hero,
            "inventory": {"coin": 90, "small_round": 8, "bandage": 2, "flash_bomb": 1,
                          "wolf_fang": 0, "wolf_hide": 0, "wolf_blood": 1},
            "equipment": {"weapon": "service_pistol", "armor": "patched_vest"},
            "known_skills": ["aimed_shot"], "trained_skills": [], "training_points": 1,
            "known_magic": [], "battle": None,
            "corruption": 0, "flags": {"first_victory": False, "cleared_encounters": []}, "log": ["你来到新手村。村外的废弃水渠里有低危怪物出没。"],
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
            defense = max(0, defense - weapon.get("armor_piercing", 0))
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
        encounter_id = battle["encounter_id"]
        cleared = self.state["flags"].setdefault("cleared_encounters", [])
        first_clear = encounter_id not in cleared
        if first_clear:
            for item, count in enemy.get("drops", {}).items():
                self.state["inventory"][item] = self.state["inventory"].get(item, 0) + count
                events.append(self._event(f"获得素材：{self.catalog['items'][item]['name']} ×{count}。"))
            reward = self.catalog["encounters"].get(encounter_id, {}).get("coin_reward", 0)
            if reward:
                self.state["inventory"]["coin"] += reward
                events.append(self._event(f"获得委托报酬：{reward} 枚硬币。"))
            self.state["training_points"] = self.state.get("training_points", 0) + 1
            events.append(self._event("获得训练点 ×1，可在村中学习战斗技能。"))
            cleared.append(encounter_id)
            self.state["player"]["experience_notes"] += 1
            events.append(self._event(f"{enemy['name']}被击倒了。获得战斗记录 ×1。"))
        else:
            events.append(self._event("这是已完成过的遭遇，没有重复报酬、素材或训练点。"))
        self.state["flags"]["first_victory"] = True
        self.state["battle"] = None

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
            events.append(self._event(f"{enemy['name']}被打断，错过行动。"))
            battle["turn"] += 1
            self._player()["ap"] = self._player()["ap_max"]
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
            recovery_event = self.restore_before_battle()
            if recovery_event:
                events.append(recovery_event)

    def _finish_round(self):
        buffs = self._player().get("buffs", {})
        for buff_id in list(buffs):
            buffs[buff_id] -= 1
            if buffs[buff_id] <= 0:
                del buffs[buff_id]

    def restore_before_battle(self):
        """Recover a defeated character to the saved state from before combat."""
        battle = self.state.get("battle")
        if not battle or (battle.get("result") != "defeat" and self.state["player"].get("hp", 1) > 0):
            return None
        snapshot = battle.get("pre_battle_state")
        if snapshot:
            self.state = deepcopy(snapshot)
        else:
            # Older saves did not keep a battle checkpoint. Recover them to a
            # playable village state while retaining their non-battle progress.
            self.state["battle"] = None
            player = self.state["player"]
            player["hp"] = player["attributes"]["max_hp"]
            player["shield"] = player.get("shield_max", 0)
            player["guarding"] = False
        message = "你在战斗中倒下了。旅程已恢复到战斗前，可以重新整备或再次挑战。"
        return self._event(message)

    def act(self, action):
        """Apply one command. Each successful battle command spends one player turn."""
        action = dict(action or {})
        kind = action.get("type")
        events = []
        p = self._player()
        try:
            if kind == "reset":
                return self.reset()
            if kind in ("learn_skill", "reset_skill_training"):
                self._require(not self.state["battle"], "战斗中不能调整技能配置。")
                if kind == "learn_skill":
                    skill_id = action.get("skill_id")
                    self._require(skill_id in self.catalog["skills"], "找不到这项技能。")
                    self._require(skill_id not in self.state["known_skills"], "已经学会这项技能。")
                    self._require(self.state.get("training_points", 0) > 0, "训练点不足。")
                    self.state["training_points"] -= 1
                    self.state["known_skills"].append(skill_id)
                    self.state.setdefault("trained_skills", []).append(skill_id)
                    events.append(self._event(f"学会技能：{self.catalog['skills'][skill_id]['name']}。"))
                else:
                    trained = self.state.setdefault("trained_skills", [])
                    self.state["training_points"] = self.state.get("training_points", 0) + len(trained)
                    self.state["known_skills"] = [skill_id for skill_id in self.state["known_skills"] if skill_id not in trained]
                    trained.clear()
                    events.append(self._event("已重置技能训练，训练点返还。"))
                return self.response(events)
            if kind == "start_encounter":
                self._require(not self.state["battle"], "战斗尚未结束。")
                self._require(self.state["location_id"] == "rookie_village", "这里没有可挑战的遭遇。")
                encounter_id = action.get("encounter_id", "drain_hound")
                encounter = self.catalog["encounters"].get(encounter_id)
                self._require(encounter is not None, "找不到这个遭遇。")
                enemy = deepcopy(self.catalog["enemies"][encounter["enemy_id"]])
                pre_battle_state = deepcopy(self.state)
                self.state["battle"] = {"encounter_id": encounter_id, "enemy": enemy, "turn": 1,
                                         "pre_battle_state": pre_battle_state,
                                         "skip_enemy_turn": 0, "result": None}
                events.append(self._event(f"遭遇：{enemy['name']}。{encounter['description']}"))
            elif self.state["battle"] and kind in ("attack", "defend", "skill", "cast", "use_item", "equip", "inject", "flee"):
                battle = self.state["battle"]
                self._require(battle["result"] is None, "战斗已经结束，请重新开始旅程。")
                if kind == "attack":
                    weapon = self._gear("weapon")
                    ammo_item = weapon.get("ammo_item")
                    if ammo_item:
                        ammo_cost = weapon.get("ammo_cost", 1)
                        self._require(self.state["inventory"].get(ammo_item, 0) >= ammo_cost, "弹药不足。")
                        self.state["inventory"][ammo_item] -= ammo_cost
                    events.append(self._event(self._attack(p, battle["enemy"], 0, weapon, "普通攻击")))
                elif kind == "defend":
                    p["guarding"] = True
                    events.append(self._event("你进入防御姿态；下一次受到的伤害减半。"))
                elif kind == "skill":
                    skill_id = action.get("skill_id")
                    self._require(skill_id in self.state["known_skills"], "尚未学会这项技能。")
                    skill = self.catalog["skills"][skill_id]
                    self._require(p["ap"] >= skill["ap_cost"], "AP 不足。")
                    required_tags = skill.get("weapon_tags", [])
                    weapon = self._gear("weapon")
                    self._require(not required_tags or any(tag in weapon.get("tags", []) for tag in required_tags),
                                  "当前武器无法使用这项技能。")
                    ammo_item = skill.get("ammo_item")
                    if ammo_item:
                        ammo_cost = max(skill.get("ammo_cost", 1), weapon.get("ammo_cost", 1))
                        self._require(self.state["inventory"].get(ammo_item, 0) >= ammo_cost, "弹药不足。")
                        self.state["inventory"][ammo_item] -= ammo_cost
                    p["ap"] -= skill["ap_cost"]
                    events.append(self._event(self._attack(p, battle["enemy"], skill["power"], weapon, skill["name"])))
                    if skill.get("effect") == "stun" and battle["enemy"]["hp"] > 0:
                        battle["skip_enemy_turn"] += 1
                        events.append(self._event(f"{battle['enemy']['name']}被打断，错过本次行动。"))
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
                    p["shield"] = p["shield_max"]
                    events.append(self._event(f"你在网咖休息，HP/MP 恢复，护甲 Shield 已充满。支付 {cost} 枚硬币。"))
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
                    quantity = action.get("quantity", 1)
                    self._require(isinstance(quantity, int) and quantity > 0, "数量必须是正整数。")
                    if kind == "buy":
                        self._require(item_id in facility["stock"], "商店不出售这个物品。")
                        price = self.catalog["items"].get(item_id, {}).get("buy_price", self.catalog["equipment"].get(item_id, {}).get("buy_price", 0))
                        affordable = self.state["inventory"]["coin"] // price if price > 0 else 0
                        self._require(price > 0 and affordable > 0, "硬币不足或商品无价格。")
                        quantity = min(quantity, affordable)
                        total = price * quantity
                        self.state["inventory"]["coin"] -= total
                        self.state["inventory"][item_id] = self.state["inventory"].get(item_id, 0) + quantity
                        events.append(self._event(f"购买{self.catalog['items'].get(item_id, self.catalog['equipment'].get(item_id))['name']} ×{quantity}，支付 {total} 枚硬币。"))
                    else:
                        self._require(item_id in facility["buyback"], "商店不收购这个物品。")
                        self._require(self.state["inventory"].get(item_id, 0) > 0, "没有可出售的物品。")
                        price = facility["buyback"][item_id]
                        quantity = min(quantity, self.state["inventory"][item_id])
                        total = price * quantity
                        self.state["inventory"][item_id] -= quantity
                        self.state["inventory"]["coin"] += total
                        item = self.catalog["items"].get(item_id, self.catalog["equipment"].get(item_id, {}))
                        events.append(self._event(f"出售{item['name']} ×{quantity}，获得 {total} 枚硬币。"))
            else:
                raise GameError("当前不能执行这个行动。")
            return self.response(events)
        except GameError as error:
            return {"ok": False, "error": str(error), "state": deepcopy(self.state), "events": []}

    def state_json(self):
        return self.response()
