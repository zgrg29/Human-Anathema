# 文字版游戏原型与 Godot API

## 目标

Python 负责规则、战斗状态与内容读取；终端和未来 Godot 客户端只负责呈现选项、收集输入、显示事件。Godot 不应复制伤害、掉落、商店或注射判定。当前服务使用标准库，无第三方依赖。

## 目录

- `human_anathema/engine.py`：无界面规则引擎。`Game.act(command)` 接收一个命令并返回状态快照与事件。
- `human_anathema/catalog.py`：加载 `data/*.json` 内容定义。
- `human_anathema/cli.py`：终端演示客户端；输入命令后调用引擎。
- `human_anathema/api.py`：HTTP/JSON 适配器，供 Godot 或其他客户端调用。
- `data/`：人物、敌人、技能、魔法、装备、物品、体液样本、Buff、属性、地点、场地、遭遇和设施定义。

内容使用稳定的英文 `id` 互相引用；`name`、`description` 是可替换的显示文本。客户端应保存 ID 和状态，不要依赖名称解析。JSON 定义可加入 `icon`、`portrait`、`scene` 等 Godot 资源引用字段，Python 核心会把它们当普通内容数据保留。

## 运行

- 终端游戏：`py -m human_anathema.cli`
- HTTP API：`py -m human_anathema.api`
- 服务监听 `127.0.0.1:8765`，无第三方依赖。

当前垂直切片从灰桥新手村开始：玩家可挑战不同敌人；首胜获得一次性硬币报酬、对应敌人体液和训练点，已完成遭遇可重玩但不重复发放奖励。桥下杂货铺支持按数量买卖消耗品、体液和装备，装备出售价与购买价相同。每场战斗结束自动恢复 HP、MP、Shield 和 AP。体液注射会恢复状态、改变阵营坐标、提高侵蚀度并解锁血色脉冲魔法。基础流程是单人战斗；场地数据已独立定义，尚未实现格子移动。

每场战斗在开始时保存战前状态快照。主人公 HP 归零时，规则引擎恢复快照并结束该场战斗；终端存档在战斗中也保留快照，因此载入存档后可以继续战斗，或在死亡恢复后继续旅程。旧版死亡存档没有快照，客户端会清除失败战斗并恢复 HP/Shield，让旅程保持可玩。

## API v1

所有响应为 UTF-8 JSON。命令成功返回 `ok: true`、完整的 `state` 快照和本次 `events`；无效命令返回 `ok: false`、`error` 和未变更状态。命令使用稳定 ID，不把终端文本传给游戏规则层。

### 读取

- `GET /api/v1/health`：服务状态。
- `GET /api/v1/catalog`：客户端可用的静态 JSON 定义。
- `GET /api/v1/state`：当前游戏状态。

### 修改

- `POST /api/v1/new-game`：开始新旅程。
- `POST /api/v1/action`：执行一个命令。

例：

```json
{"type":"start_encounter","encounter_id":"drain_hound"}
{"type":"attack"}
{"type":"skill","skill_id":"aimed_shot"}
{"type":"use_item","item_id":"bandage"}
{"type":"equip","slot":"weapon","item_id":"fire_axe"}
{"type":"inject","sample_id":"wolf_blood"}
{"type":"buy","item_id":"bandage"}
{"type":"sell","item_id":"wolf_blood"}
```

`state` 顶层字段含 `version`、`location_id`、`player`、`inventory`、`equipment`、`known_skills`、`known_magic`、`battle`、`flags`、`log`。战斗中的 `battle.enemy` 是遭遇敌人的运行时副本；修改它不会改写静态目录。

### Godot 接入约定

建议 Godot 使用 `HTTPRequest`，启动时读取 catalog 和 state，玩家每次确认行动就 POST 一条命令。响应中的 `events` 用于战斗日志，`state` 用于刷新 HUD、背包和菜单。HTTP 适配层和引擎之间的数据边界保持 JSON 兼容，之后也可将 `Game.act` 封装为本地进程/扩展调用。

## 当前原型约束

- HTTP 服务当前只有一个内存中的游戏会话；重启服务会重置进度。正式接入前需增加存档、会话标识、内容版本迁移和更细的规则错误码。
- 战斗每次有效行动触发敌方一次响应；AP 作为技能额外资源，每轮回复。当前速度、范围、命中、随机伤害、完整 Buff 时长处理、队伍和网格战术尚未接入。
- 数值与掉落是可玩的占位平衡，不是最终设定。新增内容优先扩展 JSON 定义；需要新行为时再扩展规则引擎。
