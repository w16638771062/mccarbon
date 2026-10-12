# 麦麦碳账本 · mccarbon

> 你大概从没算过，自己在麦当劳吃掉了一年多少公斤二氧化碳。
> **麦麦碳账本**把它算出来，还告诉你换成什么能少一点。

![carbon-book-preview](examples/carbon-book.html.png)

---

## 一句话介绍

省钱不是主题，热量不是主题，点餐更不是主题——**麦麦碳账本**要讲的是「你的麦当劳一年，排了多少碳，以及怎么少排一点」。

它用麦当劳官方 MCP 拉取你的历史订单，按**三层碳核算模型**（餐品 / 包装 / 配送）估算出个人餐饮碳足迹，产出一份单文件 HTML「碳账本」：总碳足迹、碳等级 A–E、三层结构、月度曲线、碳重集中类别、最碳重一单、直观换算（几棵树 / 开车多少公里），以及一个**减排模拟器**。

**为什么选这个方向？** 全站参赛作品里，没有任何一份做环保 / 碳足迹维度（详见 [选题分析]）。它天然契合麦当劳自身的「Plan for Change / 2050 净零」叙事，同时是一个真正的**个人工具**——不是玩梗，是能用的东西。

## 核心能力

- **三层碳核算**：把碳足迹拆成 餐品层（约 90%）/ 包装层 / 配送层，每一层都有独立的排放因子与来源。
- **可辩护的方法学**：能查到公开实测数据的餐品直接采用实测值（带 `measured` 标注），其余按碳类别中值外推；所有因子都在 [`factors.py`](src/mccarbon/factors.py) 里，可逐条核对（见下文「方法学」）。
- **数据真实**：通过麦当劳 MCP 的 `order-list`、`query-order`、`list-nutrition-foods`、`query-my-account` 拉取历史订单与账户信息。
- **套餐自动展开**：真实订单里的「随心配」「买薯送薯」等套餐会被展开成单品，碳核算才准确。
- **减排模拟器**：红肉换白肉、外送改自提、小食减量、甜品减半、拆掉套餐组合——每一条都算出「能减多少 kg」和「占总量的百分比」。
- **离线可跑**：内置 2026 年全年示例数据（`--mock`），零 Token 也能一键看效果。
- **单文件碳账本**：生成的 `carbon-book.html` **不依赖任何外部 CDN / 图表库**，双击打开就是一张可截图的「碳账本长图」。
- **隐私保护**：会员卡号**默认打码**展示，避免截图分享时泄露账号。
- **零第三方依赖**：只用 Python 标准库（`urllib`、`datetime`、`html`、`json`）。

## 快速开始

> 📖 **第一次使用？** 直接看 [**USAGE.md**](USAGE.md)。

```bash
# 1. 克隆仓库
git clone https://github.com/w16638771062/mccarbon.git
cd mccarbon

# 2. 零安装直接跑（无需第三方依赖、无需 Token、无需联网）
PYTHONPATH=src python3 -m mccarbon demo

# 3. 生成可分享的 HTML 碳账本
PYTHONPATH=src python3 -m mccarbon --mock --html carbon-book.html
```

嫌 `PYTHONPATH=src` 麻烦的话，装一次就能用短命令：

```bash
pip install .
mccarbon demo
```

环境要求：**Python 3.9+**（已在 3.9.6 与 3.13.12 实测通过），**零第三方依赖**。

## 方法学（M）

碳足迹题材最怕被质疑「数字是编的」，所以这里把口径写在明处。三层模型：

### 第一层 · 餐品层（约占总量 90%）

| 来源 | 关键数据 |
|---|---|
| Vegan Society「Plate Up For The Planet」 | 英国麦当劳餐品实测：Double Big Mac 4.46 / Quarter Pounder 2.99 / Big Mac 2.35 / 20 块麦乐鸡 2.13 / Filet-O-Fish 0.82 / McPlant 0.29 / McFlurry 0.17 / 大薯条 0.15（kg CO2e / 份）|
| ADEME Agribalyse 数据库 | 快餐汉堡品类 LCA 值 18.6 kg CO2e/kg 成品，其中**农业环节占 92.5%** |
| 欧盟牛肉 LCA | 23.5 kg CO2e/kg——是豆类 / 土豆的 20 倍以上，这就是「换蛋白质」最有效的原因 |

中文菜单的绝大多数餐品没有公开实测值，因此按**碳类别中值**外推（牛肉 2.40 / 鸡肉 1.00 / 鱼 0.80 / 植物基 0.30 / 小食 0.35 … kg CO2e 每份）。这比把英国单品数据硬套到中文菜单上更稳，也更好解释。

### 第二层 · 包装层

依据《中国产品全生命周期温室气体排放系数库》：

- PP 餐盒（650mL / 23g）≈ **186.18 g CO2e / 个**
- 一次性餐具（一套）≈ **54 g CO2e**
- 塑料袋（6g）≈ **19 g CO2e**

按渠道分摊：外送（餐盒 + 餐具 + 袋）远重于到店 / 自提。

### 第三层 · 配送层

参考国内外卖研究：每单平均 111.80 g CO2e，其中**包装占 86%**，配送段本身仅约 **15.6 g**（电动两轮为主）。
→ 所以「到店自提」几乎能抹掉配送层，是减排里性价比最高的动作之一。

### 换算常数

一棵成熟树每年约吸收 21 kg CO2；汽油乘用车约 170 g CO2 / 公里。

> ⚠️ **免责声明**：本账本为**估算值**，非麦当劳官方披露数据，仅用于横向对比与减排方向判断。不同地区、供应链、包装规格都会导致实际值偏差。

## 真实数据接入

真实历史订单来自 `order-list`，营养数据来自 `list-nutrition-foods`，积分账户来自 `query-my-account`。**必须先有 Token**。

1. 申请麦当劳 MCP Token（参考 [M-China/mcd-mcp-server](https://github.com/M-China/mcd-mcp-server)）。
2. 配置 Token（二选一）：

```bash
# 方式 A：环境变量
export MCD_MCP_TOKEN="your_token"

# 方式 B：命令行直接传
PYTHONPATH=src python3 -m mccarbon account --token "your_token"
```

3. **先验证 Token**（推荐第一步）：

```bash
PYTHONPATH=src python3 -m mccarbon account --token "your_token"
```

能打印出**会员卡号 / 积分**，说明 Token 有效；若报 `401` 则 Token 无效或已过期。

4. 拉取真实订单并生成碳账本：

```bash
PYTHONPATH=src python3 -m mccarbon --live --html carbon-book.html --token "your_token"
```

## 命令说明

```bash
python3 -m mccarbon [report|demo|export|account] [选项]
```

| 子命令 | 作用 | 常用选项 |
|---|---|---|
| `report`（默认）| 生成碳账本 | `--html <PATH>` `--json <PATH>` `--start/--end` `--name` `--city` `--token` `--detail` |
| `demo` | 用离线示例数据一键演示 | 同 `report` |
| `export` | 只导出归一化订单 JSON | `--json <PATH>` |
| `account` | 只读取并打印真实会员账号信息（验证 Token 用） | `--token` |

数据源优先级：`--mock` 强制离线；`--live` / `--token` / `MCD_MCP_TOKEN` 强制走真实；都不写则检测到 Token 就走真实，否则回退 mock。

## 项目结构

```
mccarbon/
├── src/mccarbon/
│   ├── factors.py         # 排放因子库（餐品/包装/配送）+ 食材归类
│   ├── carbon.py          # 三层碳核算引擎
│   ├── reduce.py          # 减排模拟器
│   ├── models.py          # Order / OrderItem 数据模型
│   ├── nutrition.py       # 官方营养表解析与餐品归类
│   ├── mcp_client.py      # 零依赖 MCP Streamable HTTP 客户端
│   ├── source.py          # MCP 数据源抽象与容错解析
│   ├── mock_data.py       # 2026 年全年示例订单
│   ├── report.py          # 单文件 HTML 碳账本生成
│   ├── render.py          # 终端文本碳账单
│   └── cli.py             # 命令行入口
├── tests/                 # 单元测试
├── examples/              # 演示产物
├── README.md              # 项目介绍（本文件）
├── USAGE.md               # 📖 面向使用者的完整使用指南
├── CONTEST_DECLARATION.md # 官方原版参赛声明，请勿改动
├── MCP_INTEGRATION.md     # MCP 接入说明
├── mcp-config.example.json
├── workbuddy.md           # WorkBuddy 专项奖励说明
├── skill/SKILL.md         # 在 WorkBuddy 里当对话式 Skill 用
├── requirements.txt       # 空文件：零第三方依赖
└── pyproject.toml
```

## 技术亮点

- **三层核算可解释**：每一层的贡献都能拆开、能核对，不是一个大黑箱。
- **因子表是数据，不是代码**：新增餐品只要往 `DISH_FACTORS` 加一行；新增类别只要往 `CATEGORY_SERVING_KG` 加一行。
- **最长关键词优先匹配**：保证「双层巨无霸」不会被「巨无霸」抢走。
- **纯 SVG 可视化**：环形图、月度柱状图全部由内联 SVG 生成，没有脚本、没有网络依赖。
- **只算不劝**：减排模块输出的是「换一下能少多少 kg」，不替用户做价值判断——这是碳题材必须守住的边界（不做洗绿）。

## 示例输出

见 [`examples/carbon-book.html`](examples/carbon-book.html)，或直接跑 `python3 -m mccarbon demo`。

## 许可证

MIT License — 详见 [LICENSE](LICENSE)。

> 本项目为麦当劳程序员节创意开发大赛参赛作品，**非麦当劳官方产品**。碳足迹为估算值，不构成任何环保声明或专业建议；餐品、包装与供应状态以麦当劳官方渠道实时结果为准。
