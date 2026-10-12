# WorkBuddy 专项奖励说明

本项目全程在 **腾讯 WorkBuddy** 中开发完成——从选题竞品分析、方法学论证、架构设计、编码实现、测试编写到真实数据联调，均由 WorkBuddy 作为智能体协作平台驱动。本文件记录开发过程中的 WorkBuddy 对话上下文，供核验联动活动（WorkBuddy 专项奖励）条件使用。

## 开发环境

- **协作平台**：腾讯 WorkBuddy
- **交互方式**：通过 WorkBuddy 对话完成需求澄清、竞品分析、创意筛选、方法学调研、架构设计、代码生成、测试编写、真实数据联调与文档交付
- **作品仓库**：https://github.com/w16638771062/mccarbon
- **开发日期**：2026-10-12
- **Python 版本**：3.9+（已在 3.9.6 与 3.13.12 实测通过全部测试）

## 选题来源（可核验的关键决策）

本项目不是拍脑袋选的，而是**数据驱动**选出来的：

1. 用 GitHub API 分页拉取大赛官方仓库 `M-China/mcd-developer-innovation-challenge` 的**全部 533 条 Issue（含 529 份参赛申请）**，提取标题与正文做词频归类与 MCP 工具提及统计。
2. 结论一（红海）：`calculate-price` 117 份、`list-nutrition-foods` 57 份、`query-meals`/`query-nearby-stores` 各 51 份……省钱/热量/点餐决策三个方向极度拥挤。
3. 结论二（蓝海）：**环保 / 碳足迹方向全站零对标**——529 份作品中没有一份做此事。
4. 因此选定「碳足迹」这一全新维度，策略是「不换题材换工具」，锚定冷门能力并做深度而非广度。

## WorkBuddy 在项目中的实际作用

1. **竞品分析**：驱动 GitHub API 拉取并统计全站 529 份作品，量化红海/蓝海，输出《选题避坑与 30 个新主题》。
2. **方法学调研**：联网核实碳核算的公开依据（Vegan Society 餐品实测、ADEME Agribalyse、中国产品全生命周期温室气体排放系数库、国内外卖配送研究），确保数字可辩护而非拍脑袋。
3. **架构设计**：确定「三层碳核算模型 + 零第三方依赖（仅 Python 标准库）+ 单文件内联 SVG HTML」的技术方案；复用通用模块（MCP 客户端、数据源、订单模型），新增 `factors` / `carbon` / `reduce` 三个核心模块。
4. **代码实现**：分模块实现 `factors`（排放因子与食材归类）/ `carbon`（三层核算引擎）/ `reduce`（减排模拟器）/ `report`（单文件 HTML 碳账本）/ `render`（终端碳账单）/ `cli` 等模块。
5. **真实数据联调**：接入麦当劳官方 MCP，复用并验证 `structuredContent` 结构化响应解析、套餐自动展开、会员卡号打码等关键处理。
6. **测试验证**：编写并运行 **57 个单元测试**（覆盖排放因子、三层核算、减排模拟、MCP 客户端、数据源、营养解析），全部通过。
7. **文档交付**：生成 `README.md`（含完整方法学与免责声明）、`USAGE.md`、`MCP_INTEGRATION.md`、`mcp-config.example.json`、`workbuddy.md` 等文件，并逐字节校验官方 `CONTEST_DECLARATION.md` 未被改动。
8. **提交上线**：完成 git 初始化与提交、推送公开仓库。

## 关键实现文件

| 文件 | 说明 |
|---|---|
| `src/mccarbon/factors.py` | 排放因子库：餐品（含实测锚点与类别外推）/ 包装 / 配送三层因子，食材碳类别归类（最长关键词优先匹配）|
| `src/mccarbon/carbon.py` | 三层碳核算引擎：总量、三层结构、月度曲线、类别归因、碳等级 A–E、直观换算 |
| `src/mccarbon/reduce.py` | 减排模拟器：红肉换白肉 / 外送改自提 / 小食减量 / 甜品减半 / 拆套餐，量化可减排量与占比 |
| `src/mccarbon/mcp_client.py` | 基于 `urllib` 的 MCP Streamable HTTP 客户端，兼容 JSON/SSE、`structuredContent` 与 429 退避 |
| `src/mccarbon/source.py` | 数据源层：订单/账号归一化，套餐自动展开，会员卡号打码 |
| `src/mccarbon/report.py` | 单文件 HTML 碳账本生成器，纯内联 SVG，零外部依赖 |

## 运行方式

```bash
# 零安装体验（离线示例数据）
cd mccarbon
PYTHONPATH=src python3 -m mccarbon demo

# 使用真实麦当劳 MCP Token 生成个人碳账本
PYTHONPATH=src python3 -m mccarbon --live --html 我的碳账本.html --token <你的 MCP Token>
```

## 备注

- 项目零第三方依赖，仅使用 Python 标准库，**Python 3.9+** 即可运行。
- 碳足迹为**估算值**，`README.md` 中逐项列出因子来源，立场中立、不做洗绿声明。
- 隐私优先：会员卡号默认打码，真实数据建议输出到仓库外目录，不会误提交。
- 官方 `CONTEST_DECLARATION.md` 已逐字节校验，与大赛官方仓库版本完全一致，未被改动。
