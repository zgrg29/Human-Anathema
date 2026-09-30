"""Terminal presentation for the headless game engine."""
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
    print("背包：" + "、".join(f"{game.catalog['items'][k]['name']}×{v}" for k, v in s['inventory'].items() if k != 'coin' and v))
    print(f"阵营：Law/Chaos {p['alignment']['law_chaos']}，Justice/Evil {p['alignment']['justice_evil']} | 侵蚀 {s.get('corruption', 0)}%")
    if e:
        intent = e['moves']['heavy_attack']['name'] if s['battle']['turn'] % 3 == 0 else e['moves']['basic_attack']['name']
        print(f"敌人：{e['name']} HP {e['hp']}  防御 {e['attributes']['defense']} | 意图：{intent}")
    print("最近记录：" + (s['log'][-1] if s['log'] else "无"))


def menu(game):
    if game.state["battle"]:
        print("战斗行动：攻击、技能、魔法、道具、装备、防御、注射、撤退、状态")
        return
    print("村庄行动：出村、商店、买、卖、制作、提取、网咖/休息、状态、帮助、退出")


def main():
    game = Game()
    if SESSION_FILE.exists():
        try:
            game.state = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
            print("已恢复上次的旅程状态。")
        except (OSError, json.JSONDecodeError):
            print("存档读取失败，将开始新旅程。")
    print("《非人与尘世》新手村原型 | 输入 帮助 查看指令；输入 退出 结束。")
    while True:
        show(game)
        menu(game)
        command = input("村民> ").strip().lower()
        if command in ("退出", "q", "quit"):
            break
        if command in ("帮助", "help"):
            print("战斗：攻击；技能；魔法；防御；注射；道具 绷带|闪光弹；装备 短枪|消防斧|防弹衣|护板；撤退")
            print("村庄：出村；商店；买 物品ID；卖 素材ID；制作 scrap_plate；提取；休息；新游戏")
            print("示例：买 bandage / 卖 wolf_fang / 使用 bandage。素材 ID：wolf_fang、wolf_hide。")
            continue
        if command in ("状态", "村庄"):
            continue
        if command == "商店":
            facility = game.catalog["facilities"]["village_shop"]
            print("桥下杂货铺库存：" + "、".join(f"{item_id}（{game.catalog['items'].get(item_id, game.catalog['equipment'].get(item_id))['name']}）" for item_id in facility["stock"]))
            print("收购：" + "、".join(f"{item_id} 每件 {price} 枚" for item_id, price in facility["buyback"].items()))
            print("制作：craft_scrap_plate；体液提取：extract_hound_blood")
            continue
        if command == "网咖":
            print("存档点网咖：每次休息 8 枚硬币，恢复 HP/MP。输入 休息 支付并恢复。")
            continue
        if command in ("出村", "探索"):
            result = game.act({"type": "start_encounter", "encounter_id": "drain_hound"})
        elif command in ("新游戏", "重开"):
            result = game.act({"type": "reset"})
        elif command in ("攻击", "1"):
            result = game.act({"type": "attack"})
        elif command in ("防御", "2"):
            result = game.act({"type": "defend"})
        elif command in ("技能", "瞄准射击"):
            result = game.act({"type": "skill", "skill_id": "aimed_shot"})
        elif command in ("魔法", "血色脉冲"):
            result = game.act({"type": "cast", "spell_id": "blood_pulse"})
        elif command.startswith("使用 "):
            target = command[3:].strip()
            item_id = {"绷带": "bandage", "急救绷带": "bandage", "闪光弹": "flash_bomb"}.get(target, target)
            result = game.act({"type": "use_item", "item_id": item_id})
        elif command.startswith("装备 "):
            target = command[3:].strip()
            item_id = {"短枪": "service_pistol", "消防斧": "fire_axe", "防弹衣": "patched_vest", "护板": "scrap_plate"}.get(target, target)
            slot = game.catalog["equipment"].get(item_id, {}).get("slot")
            result = game.act({"type": "equip", "slot": slot, "item_id": item_id})
        elif command in ("注射", "注射体液"):
            result = game.act({"type": "inject", "sample_id": "wolf_blood"})
        elif command in ("撤退", "逃跑"):
            result = game.act({"type": "flee"})
        elif command.startswith("买 "):
            result = game.act({"type": "buy", "item_id": command[2:].strip()})
        elif command.startswith("卖 "):
            result = game.act({"type": "sell", "item_id": command[2:].strip()})
        elif command == "提取":
            result = game.act({"type": "extract", "recipe_id": "extract_hound_blood"})
        elif command.startswith("制作 "):
            recipe_id = command[3:].strip()
            result = game.act({"type": "craft", "recipe_id": "craft_scrap_plate" if recipe_id == "scrap_plate" else recipe_id})
        elif command in ("休息", "睡觉"):
            result = game.act({"type": "rest", "facility_id": "net_cafe"})
        else:
            print("没听懂这项行动。输入 帮助 查看指令。")
            continue
        if result.get("events"):
            for event in result["events"]:
                print("· " + event)
        elif not result.get("ok"):
            print("· " + result["error"])
        if result.get("ok"):
            SESSION_FILE.write_text(json.dumps(game.state, ensure_ascii=False, indent=2), encoding="utf-8")
    print("旅程暂时结束。")


if __name__ == "__main__":
    main()
