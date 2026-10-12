# 使用指南 · mccarbon

按「你想做什么」分了四类，各自有可直接复制的命令。**零第三方依赖**，Python 3.9+ 即可。

---

## 一、只想先看效果（无需 Token、无需联网）

```bash
git clone https://github.com/w16638771062/mccarbon.git
cd mccarbon
PYTHONPATH=src python3 -m mccarbon demo
```

会在终端打印一份完整的碳账单。想拿到可截图的 HTML：

```bash
PYTHONPATH=src python3 -m mccarbon demo --html carbon-book.html
open carbon-book.html        # macOS；Windows 直接双击
```

用的是内置的 2026 年全年示例数据，固定随机种子，任何机器结果一致。

---

## 二、想跑自己的真实数据（需要麦当劳 MCP Token）

### 第 0 步：申请 Token

参考官方仓库 [M-China/mcd-mcp-server](https://github.com/M-China/mcd-mcp-server)。

### 第 1 步：验证 Token 能不能用（强烈建议）

```bash
PYTHONPATH=src python3 -m mccarbon account --token "你的Token"
```

- 能打印出**会员卡号（已打码）/ 积分** → Token 有效；
- 报 `401` → Token 无效或过期；
- 报网络错误 → 检查网络或代理。

### 第 2 步：生成你的碳账本

```bash
# 基础模式
PYTHONPATH=src python3 -m mccarbon --live --html 我的碳账本.html --token "你的Token"

# 更准（逐单补渠道/优惠明细，更慢）
PYTHONPATH=src python3 -m mccarbon --live --detail --html 我的碳账本.html --token "你的Token"

# 限定时间区间
PYTHONPATH=src python3 -m mccarbon --live --start 2026-01-01 --end 2026-12-31 --html 我的碳账本.html --token "你的Token"
```

> 也可以把 Token 放进环境变量，省去每次都传：
> ```bash
> export MCD_MCP_TOKEN="你的Token"
> PYTHONPATH=src python3 -m mccarbon --live --html 我的碳账本.html
> ```

---

## 三、想在 WorkBuddy 里当对话式 Skill 用

见 [`skill/SKILL.md`](skill/SKILL.md)。核心是把下面这条命令挂成一个本地命令连接器：

```bash
PYTHONPATH=src python3 -m mccarbon --mock --html /tmp/carbon-book.html --name {{user_name}} --city {{city}}
```

然后对 WorkBuddy 说「帮我生成麦麦碳账本」，它会返回 `/tmp/carbon-book.html`。

---

## 四、想在其它 MCP 客户端里用（Claude Desktop / Cursor 等）

本项目本身就是「消费者」——它通过麦当劳 MCP 拉数据。若你想把**麦当劳 MCP** 接到你自己的客户端，配置见
[`mcp-config.example.json`](mcp-config.example.json) 与 [`MCP_INTEGRATION.md`](MCP_INTEGRATION.md)。

```json
{
  "mcpServers": {
    "mcd-mcp": {
      "type": "streamablehttp",
      "url": "https://mcp.mcd.cn",
      "headers": { "Authorization": "Bearer ${MCD_MCP_TOKEN}" }
    }
  }
}
```

---

## 命令速查

| 子命令 | 作用 |
|---|---|
| `report`（默认）| 生成碳账本（终端 + 可选 HTML）|
| `demo` | 用离线示例数据一键演示 |
| `export` | 只导出归一化订单 JSON（便于二次分析）|
| `account` | 只读取真实会员账号（验证 Token）|

| 选项 | 说明 |
|---|---|
| `--mock` / `--live` | 强制离线 / 强制真实 |
| `--token` | MCP Token |
| `--start` / `--end` | 统计区间 `YYYY-MM-DD` |
| `--name` / `--city` | 覆盖显示名称 / 城市 |
| `--detail` | 真实模式下逐单补明细（更准更慢）|
| `--html <PATH>` | 生成可分享的 HTML 碳账本 |
| `--json <PATH>` | 导出归一化订单 JSON |
| `--quiet` | 不打印终端账单 |

---

## 常见问题

**Q：能安装成命令吗？**
```bash
pip install .
mccarbon demo
```

**Q：碳足迹数字准吗？**
是**估算值**，不是官方披露数据。方法学与因子来源见 [README 的「方法学」一节](README.md#方法学m)，所有因子都在 `factors.py` 里可逐条核对。**它适合用来做横向对比和减排方向判断，不适合当作精确计量。**

**Q：为什么到店自提的碳比外送低？**
外送的包装（餐盒 + 餐具 + 袋）和配送段都会计入；到店自提几乎可以忽略这两层。这也是减排里性价比最高的动作之一。

**Q：会员卡号会不会泄露？**
默认打码（前 8 位 + … + 后 4 位）。真实数据建议输出到仓库外目录，避免误提交。

**Q：统计区间内没订单怎么办？**
真实数据模式下若没有任何可解析订单，程序会明确提示，而不是静默输出空账本。可先用 `--mock` 看形态。
