"""Human & Anathema: tiny, playable terminal battle prototype.

Run with: py prototype_battle.py
The numbers and rules here are prototype values, not final game balance.
"""

from dataclasses import dataclass, field


@dataclass
class Fighter:
    name: str
    hp: int
    max_hp: int
    attack: int
    defense: int
    shield: int = 0
    max_shield: int = 0
    mp: int = 0
    max_mp: int = 0
    speed: int = 5
    guarding: bool = False
    buffs: dict = field(default_factory=dict)


HERO = Fighter("主人公·林", 12, 12, 3, 1, 5, 5, speed=5)
ENEMY = Fighter("裂口猎犬", 25, 25, 6, 2, 3, 3, speed=4)
WEAPONS = {"短枪": {"attack": 4, "ammo": None}, "消防斧": {"attack": 6, "ammo": None}}
ARMORS = {"旧式防弹衣": 5, "厚重护甲": 9}
ITEMS = {"急救包": 1, "闪光弹": 1}
weapon = "短枪"
armor = "旧式防弹衣"
ammo = 6
injection = 1
corruption = 0
turn = 1


def status():
    print("\n" + "─" * 58)
    print(f"第 {turn} 回合  |  主人公 HP {HERO.hp}/{HERO.max_hp}  Shield {HERO.shield}/{HERO.max_shield}  MP {HERO.mp}/{HERO.max_mp}")
    print(f"           武器：{weapon} (攻击 {WEAPONS[weapon]['attack']}, 弹药 {ammo if weapon == '短枪' else '—'})  防具：{armor}")
    print(f"           急救包 {ITEMS['急救包']}  闪光弹 {ITEMS['闪光弹']}  注射器 {injection}  侵蚀 {corruption}%")
    print(f"{ENEMY.name} HP {ENEMY.hp}/{ENEMY.max_hp}  Shield {ENEMY.shield}/{ENEMY.max_shield}")
    print("敌方意图：" + ("撕咬（重击，预计 8 伤害）" if turn % 3 == 0 else "扑击（预计 5 伤害）"))
    print("─" * 58)


def damage(target, amount):
    absorbed = min(target.shield, amount)
    target.shield -= absorbed
    wound = amount - absorbed
    target.hp = max(0, target.hp - wound)
    print(f"造成 {amount} 伤害（Shield 吸收 {absorbed}，HP 损失 {wound}）。")


def enemy_turn():
    global turn
    if ENEMY.hp <= 0 or HERO.hp <= 0:
        return
    heavy = turn % 3 == 0
    raw = 8 if heavy else 5
    name = "撕咬" if heavy else "扑击"
    amount = max(1, raw - HERO.defense)
    if HERO.guarding:
        amount = max(0, amount // 2)
        HERO.guarding = False
        print("你的防守姿态让这次伤害减半。")
    print(f"{ENEMY.name}使用{name}！")
    damage(HERO, amount)
    turn += 1


def player_action():
    global weapon, armor, ammo, injection, corruption
    while True:
        print("行动：1攻击  2防御  3魔法  4道具  5换装备  6注射  7查看状态  q退出")
        choice = input("> ").strip().lower()
        if choice == "1":
            if weapon == "短枪" and ammo <= 0:
                print("短枪没有弹药。换消防斧，或使用其他行动。")
                continue
            if weapon == "短枪":
                ammo -= 1
            amount = max(1, (HERO.attack + WEAPONS[weapon]["attack"]) - ENEMY.defense)
            print(f"你用{weapon}攻击！")
            damage(ENEMY, amount)
            return True
        if choice == "2":
            HERO.guarding = True
            print("你稳住姿势，下一次受到的攻击伤害减半。")
            return True
        if choice == "3":
            if HERO.mp < 2:
                print("你没有足够 MP。注射样本后可能获得施法能力。")
                continue
            HERO.mp -= 2
            amount = max(0, HERO.attack + 7 - ENEMY.defense)
            print("你释放【血色脉冲】（消耗 2 MP）。")
            damage(ENEMY, amount)
            return True
        if choice == "4":
            print("道具：1 急救包（恢复 6 HP）  2 闪光弹（敌人跳过下次行动）  b 返回")
            item = input("> ").strip().lower()
            if item == "b":
                continue
            if item == "1" and ITEMS["急救包"] > 0:
                ITEMS["急救包"] -= 1
                healed = min(6, HERO.max_hp - HERO.hp)
                HERO.hp += healed
                print(f"使用急救包，恢复 {healed} HP。")
                return True
            if item == "2" and ITEMS["闪光弹"] > 0:
                ITEMS["闪光弹"] -= 1
                ENEMY.buffs["眩晕"] = 1
                print("闪光弹击中猎犬！它将错过下次行动。")
                return True
            print("没有这个道具，或库存已用完。")
            continue
        if choice == "5":
            print(f"当前武器：{weapon}。切换：1 短枪  2 消防斧；防具：3 旧式防弹衣  4 厚重护甲  b 返回")
            gear = input("> ").strip().lower()
            if gear == "b":
                continue
            if gear == "1":
                weapon = "短枪"
            elif gear == "2":
                weapon = "消防斧"
            elif gear == "3":
                armor = "旧式防弹衣"
                HERO.max_shield = ARMORS[armor]
                HERO.shield = min(HERO.shield, HERO.max_shield)
            elif gear == "4":
                armor = "厚重护甲"
                HERO.max_shield = ARMORS[armor]
                HERO.shield = min(HERO.shield, HERO.max_shield)
            else:
                print("无效选择。")
                continue
            print(f"装备完成：武器 {weapon}，防具 {armor}。切换消耗了本回合。")
            return True
        if choice == "6":
            if injection <= 0:
                print("没有可用的猎犬样本。")
                continue
            injection -= 1
            corruption = min(100, corruption + 20)
            healed = min(5, HERO.max_hp - HERO.hp)
            HERO.hp += healed
            HERO.max_mp = 4
            HERO.mp = min(HERO.max_mp, HERO.mp + 4)
            HERO.buffs["异变强化"] = 3
            print(f"你注射了猎犬体液：恢复 {healed} HP、补充 MP，并获得 3 回合异变强化；侵蚀度升至 {corruption}%。")
            return True
        if choice == "7":
            status()
            continue
        if choice == "q":
            return False
        print("请输入菜单中的选项。")


def main():
    global turn
    print("《非人与尘世》文字战斗原型")
    print("目标：击败裂口猎犬。你可以用短枪、消防斧、道具、注射或防御取胜。")
    print("短枪有 6 发；魔法需要先注射。每次有效行动后敌人行动一次（被闪光弹眩晕时除外）。")
    while HERO.hp > 0 and ENEMY.hp > 0:
        status()
        acted = player_action()
        if not acted:
            print("你结束了试玩。")
            return
        if ENEMY.hp <= 0:
            break
        if ENEMY.buffs.pop("眩晕", 0):
            print(f"{ENEMY.name}被闪光干扰，错过了行动。")
            turn += 1
        else:
            enemy_turn()
        for key in list(HERO.buffs):
            HERO.buffs[key] -= 1
            if HERO.buffs[key] <= 0:
                del HERO.buffs[key]
    status()
    if HERO.hp <= 0:
        print("你倒下了。猎犬退回黑暗。")
    else:
        print("裂口猎犬倒下了！你赢得了战斗。")


if __name__ == "__main__":
    main()
