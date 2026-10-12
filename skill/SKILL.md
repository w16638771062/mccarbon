# WorkBuddy Skill 集成说明

如果你是在 WorkBuddy 中使用本项目，可以把它配置成一个对话式 Skill：

1. 在 WorkBuddy 的「连接器 / 自定义连接器」中新增一个「本地命令」连接器；
2. 工作目录指向本仓库根目录；
3. 执行命令设为：

```bash
PYTHONPATH=src python3 -m mccarbon --mock --html /tmp/carbon-book.html --name {{user_name}} --city {{city}}
```

（若已配置 `MCD_MCP_TOKEN`，把 `--mock` 换成 `--live` 即用真实订单。）

4. 输出格式：把生成的 `/tmp/carbon-book.html` 作为文件附件返回给对话。

## 对话示例

> 用户：帮我算算我今年在麦当劳吃了多少碳

> WorkBuddy：好，我用你的历史订单核算一下……这是你的麦麦碳账本，
> 年度碳足迹约 359 kg CO2e，碳等级 E；碳重集中在牛肉类（54%）。
> 最有效的减排动作是「红肉换白肉」，一年能少约 117 kg（32.6%）。
> [carbon-book.html]

## 注意事项

- 真实数据接入需要配置环境变量 `MCD_MCP_TOKEN`；
- `--mock` 模式使用固定示例数据，仅用于体验形态；
- 碳足迹为估算值，不构成环保声明或专业建议；减排模块只输出「换一下能少多少」，不替用户做价值判断。
