# 《非人与尘世》（Human & Anathema）项目总览

## 核心概念与愿景

* **游戏类型**：无跑图、菜单驱动型、回合制战术 RPG，强调策略、资源管理与博弈。
* **核心基调**：克苏鲁式身体异变与痛苦抉择，凡人以弱胜强的悲壮史诗。
* **开发架构**：先实现纯文本 Headless API 核心，与未来表现层解耦，并支持自动化平衡验证及 RL 兼容。
* **通关路线**：支持零注射纯人类通关，以及多种非人化异变结局。

## 核心循环

游戏由两个主要阶段构成：

1. **战斗阶段**：回合制战术对抗，围绕护甲缓冲、武器熟练度、战术道具、交涉和注射抉择展开。
2. **整备阶段**：通过菜单购买装备、交易、训练和与 NPC 交互，不进行跑图。

整备设施包括医疗所/休息区、黑市/炼金工坊、情报屋/议事厅，以及武器库/训练场。

## 系统概览

* **战斗与角色数值**：角色与敌人共用基础属性框架；角色没有通用等级。详见[角色属性与战斗规则](docs/character-combat.md)。
* **成长、注射与阵营**：纯人类依靠武器熟练与战术配置成长；注射样本带来恢复、Buff 或技能，也会改变阵营坐标并累积侵蚀。详见[成长、注射与阵营系统](docs/progression-injection-alignment.md)。
* **交涉、队友与结局**：战斗招募、队友的阵营与注射限制，以及基于侵蚀度和阵营的结局判定。详见[交涉、队友与结局](docs/social-and-endings.md)。

## 设计文档

* [角色属性与战斗规则](docs/character-combat.md)
* [成长、注射与阵营系统](docs/progression-injection-alignment.md)
* [交涉、队友与结局](docs/social-and-endings.md)
* [设定与系统设计基准](docs/design-baseline.md)：设计原则、未决问题与后续决策顺序。
* [文字版游戏架构与 Godot API](docs/game-architecture.md)：Python Headless 核心、JSON 内容目录、终端客户端及 HTTP/JSON 接口。

## 可运行原型

当前新手村文字版可用 `py -m human_anathema.cli` 启动；行动菜单使用 1–9 数字选择，只有购买/出售数量提示接受任意正整数，出售数量超过持有量时自动按全部出售。首胜奖励仅首次结算，重复挑战无奖励；每场战斗结束后恢复 HP、MP、Shield 和 AP。敌人首胜掉落各自专属体液，注射会改变 Law/Chaos 与 Justice/Evil 阵营坐标；装备可按原价出售回收。Godot 对接用的本地 HTTP/JSON API 可用 `py -m human_anathema.api` 启动。两者使用同一套 `human_anathema.engine` 规则核心和 `data/*.json` 内容定义。
