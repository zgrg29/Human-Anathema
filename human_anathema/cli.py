"""Numbered terminal menus for the headless game engine."""
import json
from pathlib import Path

from .engine import Game

SESSION_FILE = Path(__file__).resolve().parent.parent / ".game_session.json"


def show(game):
    s = game.state
    p = s["player"]
    e = s["battle"]["enemy"] if s["battle"] else None
    loc = game.catalog["locations"][s["location_id"]]
    gear = game.catalog["equipment"]
    print("\n" + "=" * 64)
    print(f"{loc['name']} | {loc['description']}")
    print(f"{p['name']} HP {p['hp']}/{p['attributes']['max_hp']}  Shield {p['shield']}/{p['shield_max']}  MP {p['mp']}/{p['mp_max']}  AP {p['ap']}/{p['ap_max']}")
    print(f"装备：{gear[s['equipment']['weapon']]['name']} / {gear[s['equipment']['armor']]['name']}  硬币：{s['inventory']['coin']}")
    bag = [f"{game.catalog['items'][k]['name']}×{v}" for k, v in s['inventory'].items()
           if k != 'coin' and v and k in game.catalog['items']]
    bag += [f"{gear[k]['name']}×{v}" for k, v in s['inventory'].items()
            if v and k in gear]
    print("背包：" + ("、".join(bag) if bag else "空"))
    print(f"阵营：Law/Chaos {p['alignment']['law_chaos']}，Justice/Evil {p['alignment']['justice_evil']} | 侵蚀 {s.get('corruption', 0)}% | 训练点 {s.get('training_points', 0)}")
    if e:
        intent = e['moves']['heavy_attack']['name'] if s['battle']['turn'] % 3 == 0 else e['moves']['basic_attack']['name']
        print(f"敌人：{e['name']} HP {e['hp']}  防御 {e['attributes']['defense']} | 意图：{intent}")
    print("最近记录：" + (s['log'][-1] if s['log'] else "无"))


def choose(title, options):
    """Show numbered (at most nine) options and return the selected index."""
    offset = 0
    while True:
        if len(options) <= 9:
            page = options
            controls = []
        else:
            page = options[offset:offset + 7]
            controls = []
            if offset:
                controls.append("上一页")
            if offset + len(page) < len(options):
                controls.append("下一页")
        print(title)
        visible = page + controls
        for number, label in enumerate(visible, 1):
            print(f"  {number}. {label}")
        value = input("请输入编号（1-9）> ").strip()
        if value.isdigit() and 1 <= int(value) <= len(visible):
            selected = int(value) - 1
            if selected < len(page):
                return offset + selected
            control = visible[selected]
            offset += 7 if control == "下一页" else -7
        else:
            print("请输入列表中的数字编号。")


def quantity_input(max_hint=None):
    hint = f"（当前持有 {max_hint}，输入更大的数量会按全部出售）" if max_hint is not None else ""
    while True:
        value = input(f"请输入数量{hint}> ").strip()
        if value.isdigit() and int(value) > 0:
            return int(value)
        print("请输入大于 0 的整数。")


def act(game, payload):
    result = game.act(payload)
    for event in result.get("events", []):
        print("· " + event)
    if not result.get("ok"):
        print("· " + result["error"])
    elif result.get("events"):
        SESSION_FILE.write_text(json.dumps(game.state, ensure_ascii=False, indent=2), encoding="utf-8")
    return result.get("ok", False)


def migrate_save(state):
    """Apply the new opening package once to existing v1 local saves."""
    if state.get("version", 1) < 2:
        inventory = state.setdefault("inventory", {})
        inventory["coin"] = inventory.get("coin", 0) + 60
        inventory["small_round"] = inventory.get("small_round", 0) + 2
        inventory["wolf_blood"] = inventory.get("wolf_blood", 0) + 1
        state["training_points"] = state.get("training_points", 0) + 1
        state.setdefault("trained_skills", [])
        state["version"] = 2
    state.setdefault("flags", {}).setdefault("cleared_encounters", [])
    return state


def inventory_items(game, predicate):
    return [(key, item) for key, item in game.catalog["items"].items()
            if predicate(key, item) and game.state["inventory"].get(key, 0) > 0]


def equip_menu(game):
    equipment = game.catalog["equipment"]
    choices = [(item_id, item) for item_id, item in equipment.items()
               if item["slot"] in ("weapon", "armor") and
               (game.state["inventory"].get(item_id, 0) > 0 or
                game.state["equipment"].get(item["slot"]) == item_id)]
    if not choices:
        print("没有可切换的装备。")
        return
    labels = [f"{item['name']}（{'武器' if item['slot'] == 'weapon' else '防具'}）" for _, item in choices]
    labels.append("返回")
    selected = choose("选择要装备的物品：", labels)
    if selected < len(choices):
        item_id, item = choices[selected]
        act(game, {"type": "equip", "slot": item["slot"], "item_id": item_id})


def use_item_menu(game):
    choices = inventory_items(game, lambda _key, item: item.get("kind") == "consumable")
    if not choices:
        print("没有可使用的道具。")
        return
    labels = [f"{item['name']}（持有 {game.state['inventory'][item_id]}）" for item_id, item in choices]
    labels.append("返回")
    selected = choose("选择要使用的道具：", labels)
    if selected < len(choices):
        act(game, {"type": "use_item", "item_id": choices[selected][0]})


def ability_menu(game, kind):
    ids = game.state["known_skills"] if kind == "skill" else game.state["known_magic"]
    catalog = game.catalog["skills"] if kind == "skill" else game.catalog["magic"]
    if not ids:
        print("尚未学会相关能力。")
        return
    labels = [catalog[key]["name"] for key in ids] + ["返回"]
    selected = choose("选择要使用的能力：", labels)
    if selected < len(ids):
        field = "skill_id" if kind == "skill" else "spell_id"
        action_type = kind if kind == "skill" else "cast"
        act(game, {"type": action_type, field: ids[selected]})


def shop_menu(game):
    choice = choose("桥下杂货铺：", ["购买", "出售物品/素材/装备", "返回"])
    if choice == 2:
        return
    facility = game.catalog["facilities"]["village_shop"]
    if choice == 0:
        rows = []
        for item_id in facility["stock"]:
            item = game.catalog["items"].get(item_id, game.catalog["equipment"].get(item_id, {}))
            price = item.get("buy_price", 0)
            rows.append((item_id, item, price))
        if not rows:
            print("商店当前没有商品。")
            return
        labels = [f"{item['name']}（{price} 枚/件）" for _, item, price in rows] + ["返回"]
        selected = choose("选择要购买的商品：", labels)
        if selected < len(rows):
            quantity = quantity_input()
            act(game, {"type": "buy", "item_id": rows[selected][0], "quantity": quantity})
    else:
        rows = [(item_id, price) for item_id, price in facility["buyback"].items()
                if game.state["inventory"].get(item_id, 0) > 0]
        if not rows:
            print("没有可出售的素材。")
            return
        labels = [f"{game.catalog['items'].get(item_id, game.catalog['equipment'].get(item_id, {}))['name']}（持有 {game.state['inventory'][item_id]}，售价 {price}/件）"
                  for item_id, price in rows] + ["返回"]
        selected = choose("选择要出售的物品、素材或装备：", labels)
        if selected < len(rows):
            item_id = rows[selected][0]
            quantity = quantity_input(game.state["inventory"][item_id])
            act(game, {"type": "sell", "item_id": item_id, "quantity": quantity})


def recipe_menu(game, kind):
    rows = [(recipe_id, recipe) for recipe_id, recipe in game.catalog["recipes"].items()
            if recipe.get("kind", "extract") == kind]
    if not rows:
        print("目前没有可用配方。")
        return
    labels = [recipe["name"] for _, recipe in rows] + ["返回"]
    selected = choose("选择配方：", labels)
    if selected < len(rows):
        act(game, {"type": kind, "recipe_id": rows[selected][0]})


def training_menu(game):
    skills = game.catalog["skills"]
    available = [(key, skill) for key, skill in skills.items()
                 if key not in game.state["known_skills"] and game.state.get("training_points", 0) > 0]
    options = [f"学习：{skill['name']}（1 点）" for _, skill in available]
    reset_index = None
    if game.state.get("trained_skills"):
        reset_index = len(options)
        options.append("重置已训练技能并返还点数")
    options.append("返回")
    selected = choose(f"技能训练（可用训练点：{game.state.get('training_points', 0)}）：", options)
    if selected < len(available):
        act(game, {"type": "learn_skill", "skill_id": available[selected][0]})
    elif reset_index is not None and selected == reset_index:
        act(game, {"type": "reset_skill_training"})


def workshop_menu(game):
    selected = choose("工坊服务：", ["提取体液", "制作装备", "返回"])
    if selected == 0:
        recipe_menu(game, "extract")
    elif selected == 1:
        recipe_menu(game, "craft")


def village_turn(game):
    selected = choose("村庄行动：", ["出村挑战", "商店", "网咖充能休息（全恢复，8 硬币）", "装备", "注射体液", "工坊", "技能训练/重置", "状态", "结束游戏"])
    if selected == 0:
        encounters = list(game.catalog["encounters"].items())
        if not encounters:
            print("当前委托都已完成。")
            return True
        cleared = game.state["flags"].get("cleared_encounters", [])
        labels = []
        for key, encounter in encounters:
            reward_label = "重复挑战，无奖励" if key in cleared else f"报酬 {encounter.get('coin_reward', 0)} 枚"
            labels.append(f"{encounter['name']}（{reward_label}）")
        labels.append("返回")
        pick = choose("选择一项尚未完成的遭遇：", labels)
        if pick < len(encounters):
            act(game, {"type": "start_encounter", "encounter_id": encounters[pick][0]})
    elif selected == 1:
        shop_menu(game)
    elif selected == 2:
        act(game, {"type": "rest", "facility_id": "net_cafe"})
    elif selected == 3:
        equip_menu(game)
    elif selected == 4:
        samples = [(key, sample) for key, sample in game.catalog["samples"].items()
                   if game.state["inventory"].get(key, 0) > 0]
        if not samples:
            print("没有可注射的体液样本。")
        else:
            labels = [f"{sample['name']}（持有 {game.state['inventory'][key]}）" for key, sample in samples] + ["返回"]
            pick = choose("选择体液样本：", labels)
            if pick < len(samples):
                act(game, {"type": "inject", "sample_id": samples[pick][0]})
    elif selected == 5:
        workshop_menu(game)
    elif selected == 6:
        training_menu(game)
    elif selected == 7:
        return True
    else:
        return False
    return True


def battle_turn(game):
    selected = choose("战斗行动：", ["普通攻击", "使用技能", "使用魔法", "使用道具", "切换装备", "防御", "注射体液", "撤退", "状态"])
    if selected == 0:
        act(game, {"type": "attack"})
    elif selected == 1:
        ability_menu(game, "skill")
    elif selected == 2:
        ability_menu(game, "magic")
    elif selected == 3:
        use_item_menu(game)
    elif selected == 4:
        equip_menu(game)
    elif selected == 5:
        act(game, {"type": "defend"})
    elif selected == 6:
        samples = [(key, sample) for key, sample in game.catalog["samples"].items()
                   if game.state["inventory"].get(key, 0) > 0]
        if not samples:
            print("没有可注射的体液样本。")
        else:
            labels = [sample["name"] for key, sample in samples] + ["返回"]
            pick = choose("选择体液样本：", labels)
            if pick < len(samples):
                act(game, {"type": "inject", "sample_id": samples[pick][0]})
    elif selected == 7:
        act(game, {"type": "flee"})
    else:
        return True
    return True


def main():
    game = Game()
    if SESSION_FILE.exists():
        try:
            game.state = migrate_save(json.loads(SESSION_FILE.read_text(encoding="utf-8")))
            recovery_event = game.restore_before_battle()
            SESSION_FILE.write_text(json.dumps(game.state, ensure_ascii=False, indent=2), encoding="utf-8")
            print("已恢复上次的旅程状态。")
            if recovery_event:
                print("· " + recovery_event)
        except (OSError, json.JSONDecodeError):
            print("存档读取失败，将开始新旅程。")
    print("《非人与尘世》新手村原型 | 所有行动均可通过 1-9 数字菜单选择。")
    while True:
        show(game)
        if game.state["battle"]:
            if game.state["battle"].get("result"):
                print("这场遭遇已结束。请重新开始旅程。")
                break
            if not battle_turn(game):
                break
        elif not village_turn(game):
            break
    print("旅程暂时结束。")


if __name__ == "__main__":
    main()
