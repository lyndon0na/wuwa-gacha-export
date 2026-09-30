#!/usr/bin/env python3
"""鸣潮（Wuthering Waves）唤取记录链接提取 & 记录导出工具

流程：
  1. 读取并解密 Client.log（3.4+ 版本库洛对日志做了逐字节异或加密）
  2. 提取唤取记录链接（可直接导入 Wuwa Tracker 等第三方工具）
  3. 调用官方接口拉取各卡池记录，输出 JSON 原始记录 + Markdown 统计报告

用法：
  python3 wuwa_gacha.py              # 交互式输入游戏目录
  python3 wuwa_gacha.py <游戏目录>    # 直接指定，跳过输入

游戏目录填到哪一层都可以，例如：
  D:\\Wuthering Waves\\Wuthering Waves Game
  ~/Games/KuroGames/Wuthering Waves Game/Client/Saved/Logs

注意：链接有时效，过期后需重新在游戏内打开「唤取 → 唤取记录」页面再运行本脚本。
"""
import glob
import json
import os
import re
import sys
import urllib.request

URL_RE = re.compile(
    rb"https://aki-gm-resources(-oversea)?\.aki-game\.(com|net)/aki/gacha[^\x00-\x20\"'<>\\]*"
)
API_CN = "https://gmserver-api.aki-game2.com/gacha/record/query"
API_GLOBAL = "https://gmserver-api.aki-game2.net/gacha/record/query"
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
URL_FILE = os.path.join(OUT_DIR, "wuwa_gacha_url.txt")

POOLS = {
    1: "角色活动唤取",
    2: "武器活动唤取",
    3: "角色常驻唤取",
    4: "武器常驻唤取（全频调谐）",
    5: "新手唤取",
    6: "新手自选唤取",
    7: "新手自选唤取（感恩定向唤取）",
    8: "角色新旅唤取",
    9: "武器新旅唤取",
    12: "角色忆旅唤取",
    13: "武器忆旅唤取",
}


def decrypt(data: bytes) -> bytes:
    """偶数 -> 异或 0xEF，奇数 -> 异或 0xA5。"""
    return bytes(c ^ (0xEF if (c & 1) == 0 else 0xA5) for c in data)


def clean_path(raw: str) -> str:
    return os.path.expanduser(raw.strip().strip('"').strip("'"))


def ask_game_dir() -> str:
    print("提示：请先在游戏内打开「唤取 → 唤取记录」页面，游戏会把带链接的日志写进 Client.log。")
    raw = input("请输入游戏目录（如 D:\\Wuthering Waves\\Wuthering Waves Game）: ")
    root = clean_path(raw)
    if not root:
        sys.exit("未输入游戏目录，已退出。")
    return root


def find_logs(root: str) -> list:
    """从用户给出的目录/文件定位 Client.log（含历史备份日志）。"""
    if os.path.isfile(root):
        return [root]
    patterns = [
        "Client/Saved/Logs/*.log",
        "Saved/Logs/*.log",
        "Wuthering Waves Game/Client/Saved/Logs/*.log",
        "*/Client/Saved/Logs/*.log",
        "*/*/Client/Saved/Logs/*.log",
        "*.log",
    ]
    logs = []
    for pattern in patterns:
        logs += glob.glob(os.path.join(root, pattern))
    if not logs:
        sys.exit(f"在 {root} 下没找到日志文件。\n"
                 f"请确认目录里有 Client/Saved/Logs/Client.log，"
                 f"并先在游戏内打开「唤取 → 唤取记录」页面。")
    return sorted(set(logs), key=os.path.getmtime, reverse=True)


def extract_url(logs: list) -> str:
    for path in logs:
        try:
            with open(path, "rb") as f:
                text = decrypt(f.read())
        except OSError:
            continue
        found = [m.group(0).decode("ascii") for m in URL_RE.finditer(text)]
        if found:
            print(f"日志: {path}")
            return found[0]
    sys.exit("日志里没有唤取记录链接。请先在游戏内打开「唤取 → 唤取记录」页面，再运行本脚本。")


def query(pool_type: int, params: dict, api: str) -> list:
    body = json.dumps({
        "playerId": params["player_id"],
        "cardPoolId": params["resources_id"],
        "cardPoolType": pool_type,
        "serverId": params["svr_id"],
        "languageCode": params.get("lang", "zh-Hans"),
        "recordId": params["record_id"],
    }).encode()
    req = urllib.request.Request(api, data=body, headers={
        "Content-Type": "application/json",
        "Origin": "https://aki-gm-resources.aki-game.com",
        "Referer": "https://aki-gm-resources.aki-game.com/",
        "User-Agent": "Mozilla/5.0",
    })
    with urllib.request.urlopen(req, timeout=25) as resp:
        payload = json.loads(resp.read().decode())
    if str(payload.get("code")) not in ("0", "200") and payload.get("message") != "成功":
        raise RuntimeError(payload.get("message", payload))
    return payload.get("data") or []


def pool_label(pool_id: int, records: list) -> str:
    """接口返回的 cardPoolType 是卡池实际名称，为纯数字时回退到本地映射。"""
    label = str(records[0].get("cardPoolType", ""))
    if label.isdigit():
        return f"{POOLS.get(pool_id, pool_id)}（type {pool_id}）"
    return label


def fetch_all(params: dict, global_server: bool) -> dict:
    api = API_GLOBAL if global_server else API_CN
    pools, failed = {}, 0
    for pool_id in POOLS:
        try:
            records = query(pool_id, params, api)
        except Exception as exc:
            failed += 1
            print(f"  [{pool_id:>2}] {POOLS[pool_id]}: 查询失败 - {exc}")
            if failed >= 2:
                print("  剩余卡池跳过（连续失败，链接多半已过期）")
                break
            continue
        if records:
            pools[pool_id] = records
            print(f"  [{pool_id:>2}] {pool_label(pool_id, records)}: {len(records)} 条")
    return pools


def expand(records: list) -> list:
    """接口按新->旧返回，反转成单抽的时间正序序列（count>1 时展开）。"""
    out = []
    for r in reversed(records):
        out += [r] * int(r.get("count", 1) or 1)
    return out


def analyze(name: str, records: list) -> dict:
    pulls = expand(records)
    five, four, pity = [], 0, 0
    for p in pulls:
        pity += 1
        quality = int(p.get("qualityLevel", 0))
        if quality == 5:
            five.append({"name": p["name"], "time": p["time"], "pity": pity,
                         "type": p.get("resourceType"), "banner": p.get("cardPoolType")})
            pity = 0
        elif quality == 4:
            four += 1
    return {"pool": name, "total": len(pulls), "five": five, "four_count": four,
            "pity_now": pity, "first": pulls[0]["time"], "last": pulls[-1]["time"]}


def write_report(params: dict, results: list) -> None:
    lines = ["# 鸣潮唤取记录报告", "",
             f"- UID / player_id: `{params['player_id']}`",
             f"- 服务器: {params.get('svr_area')} (`{params['svr_id']}`)",
             f"- 数据范围: {min(r['first'] for r in results)} ~ {max(r['last'] for r in results)}",
             "", "## 总览", "",
             "| 卡池 | 总抽数 | 5★ | 4★ | 5★ 出货率 | 当前保底 |",
             "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for r in results:
        rate = f"{len(r['five']) / r['total'] * 100:.2f}%"
        lines.append(f"| {r['pool']} | {r['total']} | {len(r['five'])} | "
                     f"{r['four_count']} | {rate} | {r['pity_now']} |")
    for r in results:
        if not r["five"]:
            continue
        lines += ["", f"## {r['pool']} — 5★ 明细", "",
                  "| 时间 | 名称 | 类型 | 消耗抽数 | 卡池 |", "| --- | --- | --- | ---: | --- |"]
        for f in r["five"]:
            lines.append(f"| {f['time']} | **{f['name']}** | {f['type']} | {f['pity']} | {f['banner']} |")
    path = os.path.join(OUT_DIR, "wuwa_gacha_report.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"报告: {path}")


def show_url(url: str, stale: bool) -> None:
    with open(URL_FILE, "w", encoding="utf-8") as f:
        f.write(url + "\n")
    print()
    print("=" * 72)
    if stale:
        print("唤取记录链接（已过期，仅供查看——下方链接无法再导入）")
    else:
        print("唤取记录链接（复制到 Wuwa Tracker 等工具即可导入）")
    print("-" * 72)
    print(url)
    print("-" * 72)
    print(f"已保存到: {URL_FILE}")
    if stale:
        print("该链接已失效：请在游戏内重新打开「唤取 → 唤取记录」页面，再运行本脚本。")
    else:
        print("链接有时效，过期后请重新在游戏内打开「唤取 → 唤取记录」页面再运行本脚本。")
    print("=" * 72)


def main() -> None:
    root = clean_path(sys.argv[1]) if len(sys.argv) > 1 else ask_game_dir()
    url = extract_url(find_logs(root))
    params = dict(p.split("=", 1) for p in url.split("?", 1)[1].split("&"))
    global_server = params.get("svr_area") == "global" or "-oversea" in url

    print(f"游戏目录: {root}")
    print(f"UID: {params['player_id']}  区服: {params.get('svr_area') or 'unknown'}\n"
          f"拉取各卡池记录...")
    pools = fetch_all(params, global_server)

    if pools:
        raw_path = os.path.join(OUT_DIR, "wuwa_gacha_records.json")
        with open(raw_path, "w", encoding="utf-8") as f:
            json.dump({"url": url, "params": params, "pools": pools}, f, ensure_ascii=False, indent=2)
        print(f"原始记录: {raw_path}")

        results = [analyze(pool_label(int(pid), recs), recs) for pid, recs in sorted(pools.items())]
        total = sum(r["total"] for r in results)
        five = sum(len(r["five"]) for r in results)
        print(f"\n总抽数 {total} | 5★ {five} | 出货率 {five / total * 100:.2f}%")
        for r in results:
            print(f"  {r['pool']:<18} {r['total']:>4} 抽, 5★ {len(r['five'])}, 当前保底 {r['pity_now']}")
        for r in results:
            for f in r["five"]:
                print(f"    {f['time']}  {f['name']} ({f['type']}) — 第 {f['pity']} 抽")
        write_report(params, results)
    else:
        print("\n没拉到任何记录：日志里的链接多半已过期。")
        print("请在游戏内重新打开「唤取 → 唤取记录」页面，再运行本脚本。")

    show_url(url, stale=not pools)


if __name__ == "__main__":
    main()
