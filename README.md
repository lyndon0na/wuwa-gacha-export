# 鸣潮唤取记录链接提取 & 导出

从《鸣潮》（Wuthering Waves）客户端日志中提取**唤取记录链接**，并顺手导出抽卡记录与统计。

提取出的链接可以直接粘贴到 [Wuwa Tracker](https://wuwatracker.com/) 等第三方统计工具中导入历史记录。

纯 Python 标准库实现，**无第三方依赖**。

## 功能

- 🔓 解密并解析 `Client.log`（3.4 版本起库洛对日志做了逐字节异或加密）
- 🔗 输出唤取记录链接，并保存到 `wuwa_gacha_url.txt` 方便复制
- 📊 调用官方接口拉取各卡池记录，生成 `wuwa_gacha_records.json` 与 `wuwa_gacha_report.md`
- 📈 统计各卡池抽数、5★ / 4★ 数量、出货率与当前保底
- 🌏 国服 / 国际服均可

## 环境要求

Python 3.8+，无需安装任何依赖。

## 使用方法

1. 启动游戏，进入主界面
2. 在游戏内打开 **唤取 → 唤取记录** 页面（这一步会让游戏把带链接的日志写进 `Client.log`）
3. 运行脚本，按提示输入游戏目录：

   ```bash
   python3 wuwa_gacha.py
   ```

   也可以直接传参跳过输入：

   ```bash
   python3 wuwa_gacha.py "D:\Wuthering Waves\Wuthering Waves Game"
   ```

4. 从终端输出中复制链接，或打开脚本目录下的 `wuwa_gacha_url.txt`

游戏目录填到哪一层都可以，脚本会自动向下查找日志：

```
游戏根目录/                          ← 填这里
└── Client/Saved/Logs/Client.log     ← 也可以直接填 Logs 目录或这个文件
```

## 输出文件

脚本会在自身所在目录生成：

| 文件 | 内容 |
| --- | --- |
| `wuwa_gacha_url.txt` | 唤取记录链接（导入第三方工具用） |
| `wuwa_gacha_records.json` | 各卡池原始记录 |
| `wuwa_gacha_report.md` | 出货统计与 5★ 明细（含保底抽数） |

## 工作原理

1. **解密日志**：3.4 版本起 `Client.log` 按字节奇偶做异或——偶数异或 `0xEF`、奇数异或 `0xA5`
2. **提取链接**：在解密后的日志中匹配 `aki-gm-resources*.aki-game.*/aki/gacha` 开头的链接
3. **拉取记录**：用链接中的参数（`player_id` / `svr_id` / `record_id` / `resources_id`）调用官方接口
   `POST https://gmserver-api.aki-game2.com/gacha/record/query`（国际服为 `.net` 域名）

## 常见问题

**找不到日志文件？**
确认目录里有 `Client/Saved/Logs/Client.log`。游戏运行过、且打开过唤取记录页面后该文件才会包含链接。

**提示链接已失效？**
唤取记录链接有时效（数小时）。重新在游戏内打开一次「唤取 → 唤取记录」页面，再运行脚本即可。

**能拿到多久以前的记录？**
以官方接口返回为准，通常只保留最近一段时间的记录。

## 免责声明

本工具仅读取本机游戏日志，不涉及账号密码，也不修改游戏数据。请仅用于导出自己的记录，并遵守游戏服务条款。因使用本工具产生的一切后果由使用者自行承担。

## 致谢

日志异或加密方式来自社区分享，感谢 [wuwa-gacha-url-extractor](https://github.com/SugarRainbow/wuwa-gacha-url-extractor) 等项目提供的思路。

## License

[MIT](LICENSE)
