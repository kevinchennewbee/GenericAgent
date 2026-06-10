#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""蓬莱安装向导（penglai setup）— 目标：10 分钟从裸机到飞书说上话。

纯标准库实现（venv 建立之前也能运行）。流程：
  环境自检 → LLM（预设+真实连通测试）→ 飞书（图文指引+凭证验证）→ 起名 → 写 mykey.py → 部署提示
原则：身份与记忆分离 — 只在出厂态种入身份，绝不覆盖已有用户记忆。
"""
import os, sys, json, time, shutil, subprocess, urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
OK, BAD, T = "✅", "❌", "🏮"

PRESETS = [  # (名称, apibase, 默认model, 申请地址)
    ("DeepSeek",        "https://api.deepseek.com",                  "deepseek-chat",          "https://platform.deepseek.com"),
    ("智谱 GLM",        "https://open.bigmodel.cn/api/paas/v4",      "glm-5.1",                "https://open.bigmodel.cn"),
    ("MiniMax",         "https://api.minimaxi.com/v1",               "MiniMax-M2.7",           "https://platform.minimaxi.com"),
    ("Moonshot Kimi",   "https://api.moonshot.cn/v1",                "kimi-k2-turbo-preview",  "https://platform.moonshot.cn"),
    ("字节火山 Ark",    "https://ark.cn-beijing.volces.com/api/v3",  "",                       "https://console.volcengine.com/ark（model 填推理接入点 ID）"),
    ("OpenRouter",      "https://openrouter.ai/api/v1",              "anthropic/claude-sonnet-4-6", "https://openrouter.ai"),
    ("自定义 OpenAI 兼容端点", "", "", ""),
]

def ask(prompt, default=""):
    tip = f"（回车={default}）" if default else ""
    v = input(f"  {prompt}{tip}: ").strip()
    return v or default

def post_json(url, payload, headers=None, timeout=40):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())

# ---------- 步骤 0：环境 ----------
def step_env():
    print(f"\n{T} 步骤 0/5 环境自检")
    if sys.version_info < (3, 10):
        print(f"{BAD} 需要 Python 3.10+，当前 {sys.version.split()[0]}"); sys.exit(1)
    print(f"{OK} Python {sys.version.split()[0]}")
    py = os.path.join(ROOT, ".venv", "bin", "python")
    if not os.path.exists(py):
        print("  正在创建虚拟环境并安装依赖（清华镜像）...")
        uv = shutil.which("uv")
        idx = "https://pypi.tuna.tsinghua.edu.cn/simple"
        try:
            if uv:
                subprocess.run([uv, "venv", ".venv"], cwd=ROOT, check=True, env={**os.environ, "UV_DEFAULT_INDEX": idx})
                subprocess.run([uv, "pip", "install", "--python", py, "-q", "-e", ".", "lark-oapi"], cwd=ROOT, check=True,
                               env={**os.environ, "UV_DEFAULT_INDEX": idx})
            else:
                subprocess.run([sys.executable, "-m", "venv", ".venv"], cwd=ROOT, check=True)
                subprocess.run([py, "-m", "pip", "install", "-q", "-i", idx, "-e", ".", "lark-oapi"], cwd=ROOT, check=True)
            print(f"{OK} 依赖安装完成")
        except subprocess.CalledProcessError:
            print(f"{BAD} 依赖安装失败，请手动执行后重试: python3 -m venv .venv && .venv/bin/pip install -e . lark-oapi")
            sys.exit(1)
    else:
        print(f"{OK} 虚拟环境已存在")

# ---------- 步骤 1：LLM ----------
def step_llm():
    print(f"\n{T} 步骤 1/5 选择大模型（蓬莱的大脑）")
    for i, (name, _, model, url) in enumerate(PRESETS, 1):
        print(f"  {i}. {name:<22}{model:<28}{url}")
    while True:
        try: idx = int(ask("选择序号", "1")) - 1; name, base, model, _ = PRESETS[idx]; break
        except (ValueError, IndexError): print("  无效序号，请重选")
    if not base: base = ask("API Base URL（如 https://api.example.com/v1）")
    model = ask("模型名", model) if model else ask("模型名（Ark 填推理接入点 ID）")
    key = ask("API Key（粘贴后回车）")
    print("  连通性测试中...", end="", flush=True)
    try:
        r = post_json(base.rstrip("/") + "/chat/completions",
                      {"model": model, "messages": [{"role": "user", "content": "回复两个字：蓬莱"}], "max_tokens": 64},
                      {"Authorization": f"Bearer {key}"})
        reply = r["choices"][0]["message"]["content"].strip()[:20]
        print(f"\r{OK} 模型连通" + (f"，回复：{reply}" if reply else "（思考型模型，空文本正常）"))
        return {"name": name, "apikey": key, "apibase": base, "model": model}
    except Exception as e:
        print(f"\r{BAD} 测试失败：{e}")
        if ask("重试？(y/n)", "y").lower().startswith("y"): return step_llm()
        sys.exit(1)

# ---------- 步骤 2：飞书 ----------
def step_feishu():
    print(f"\n{T} 步骤 2/5 接入飞书（约 3 分钟，跟着做）")
    print("""  ① 浏览器打开 https://open.feishu.cn/app → 创建企业自建应用（名字随意，如「蓬莱」）
  ② 左栏「添加应用能力」→ 添加「机器人」
  ③ 左栏「权限管理」→ 搜索并开通: im:message（获取与发送单聊/群聊消息相关权限，批量勾选）
  ④ 左栏「事件订阅」→ 订阅方式选「使用长连接接收事件」→ 添加事件: 接收消息 im.message.receive_v1
  ⑤ 左栏「版本管理与发布」→ 创建版本并发布（自建应用秒过审）
  ⑥ 「凭证与基础信息」页拿 App ID 和 App Secret，填到下面""")
    while True:
        app_id = ask("App ID（cli_ 开头）")
        app_secret = ask("App Secret")
        print("  凭证验证中...", end="", flush=True)
        try:
            r = post_json("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                          {"app_id": app_id, "app_secret": app_secret})
            if r.get("code") == 0:
                print(f"\r{OK} 飞书凭证有效"); return app_id, app_secret
            print(f"\r{BAD} 飞书返回错误：{r.get('msg')}（检查是否复制完整）")
        except Exception as e:
            print(f"\r{BAD} 验证失败：{e}")

# ---------- 步骤 3：起名 ----------
def step_identity():
    print(f"\n{T} 步骤 3/5 给你的管家起名")
    agent = ask("管家名字", "蓬莱助手 Penglai")
    user = ask("它怎么称呼你", "主人")
    # 身份写入 L1 索引（GA 每轮注入系统提示的是 L1，不是 L2）
    ins = os.path.join(ROOT, "memory", "global_mem_insight.txt")
    if not os.path.exists(ins):
        tpl = os.path.join(ROOT, "assets", "global_mem_insight_template.txt")
        os.makedirs(os.path.dirname(ins), exist_ok=True)
        with open(ins, "w", encoding="utf-8") as f:
            f.write(open(tpl, encoding="utf-8").read() if os.path.exists(tpl) else "# [Global Memory Insight]\n")
    lines = [l for l in open(ins, encoding="utf-8", errors="replace").read().splitlines()
             if not l.startswith(("[身份]", "[蓬莱SOP]", "[蓬莱规则]"))]
    ident = (f"[身份] 我是「{agent}」，基于 GenericAgent 的开源个人管家发行版蓬莱。用户称呼：{user}。"
             f"被问及身份/名字时以此为准，勿自称底层模型名。")
    # 蓬莱 SOP 包索引（L3 文件随发行版出厂，带 penglai_ 前缀与上游永不撞名）
    sops = ("[蓬莱SOP] 长任务断点→penglai_checkpoint_sop | 压缩记忆留出处→penglai_compress_sop"
            " | 生成海报/SVG/视频→penglai_genmedia_sop")
    # 聊天渠道行为规则（vision_sop 的 OCR 优先是桌面 UI 自动化基因，不适合用户聊天发图）
    rules = ("[蓬莱规则] 聊天渠道用户发图→直接 vision 原生看图(勿先OCR,仅需逐字提取时才OCR)；"
             "语音→直接 transcribe(支持微信silk,自带情绪)")
    out = ([lines[0], ident, sops, rules] + lines[1:] if lines and lines[0].startswith("#")
           else [ident, sops, rules] + lines)
    with open(ins, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print(f"{OK} 身份 + 蓬莱SOP索引已写入 L1（每轮注入）")
    return agent

# ---------- 步骤 4：写配置 ----------
def step_intel():
    """可选增强：情报矩阵（默认跳过=用 GA 原生浏览器）。"""
    print(f"\n{T} 可选增强 · 情报矩阵（多源交叉验证，降低幻觉）")
    print("  默认不开 → 蓬莱用 GA 自带的真浏览器搜索（免费、开箱即用，已够用）。")
    print("  开启后 → 多个独立搜索 API 并查 + 交叉验证，更适合事实核查/写记忆/做决策。")
    if not ask("现在开启情报矩阵增强？(y/n)", "n").lower().startswith("y"):
        return {}
    print("  推荐 TinyFish（免费、自有索引）：到 https://agent.tinyfish.ai/api-keys 申请，回车跳过")
    keys = {}
    if k := ask("TinyFish API Key（X-API-Key，可空）"): keys["tinyfish_key"] = k
    if k := ask("Tavily API Key（免费额度，可空）"):    keys["tavily_key"] = k
    if k := ask("Firecrawl API Key（可空）"):           keys["firecrawl_key"] = k
    print(f"{OK} 情报矩阵：{len(keys)} 个源已配置" if keys else "  未填 key，保持默认（GA 浏览器）")
    return keys

def step_companion():
    """可选增强：主动陪伴（默认关闭=零成本零打扰）。"""
    print(f"\n{T} 可选增强 · 主动陪伴（会主动关心你，不只是被动回复）")
    print("  默认不开 → 蓬莱只在你发消息时回应（零成本）。")
    print("  开启后 → 独立心跳进程，门禁守护（勿扰时段/不打断聊天/频率上限），")
    print("           偶尔主动联系你。是蓬莱第一个有持续 token 成本的功能（一天约几分钱）。")
    if not ask("现在开启主动陪伴？(y/n)", "n").lower().startswith("y"):
        return {}
    print(f"{OK} 主动陪伴已开启（默认勿扰 22-8 点、最短间隔 4 小时；可后续在 mykey.py 调）")
    return {"companion_enabled": True}

def step_write(llm, app_id, app_secret, intel=None):
    print(f"\n{T} 步骤 4/5 写入配置 mykey.py")
    path = os.path.join(ROOT, "mykey.py")
    if os.path.exists(path):
        bak = f"{path}.bak.{time.strftime('%Y%m%d-%H%M%S')}"
        shutil.copy2(path, bak); print(f"  已备份旧配置 → {os.path.basename(bak)}")
    body = f"""# mykey.py — 由 penglai setup 生成 {time.strftime('%Y-%m-%d %H:%M')}
native_oai_config = {{
    'name': {llm['name']!r},
    'apikey': {llm['apikey']!r},
    'apibase': {llm['apibase']!r},
    'model': {llm['model']!r},
    'max_retries': 3,
}}
mixin_config = {{
    'llm_nos': [{llm['name']!r}],
    'max_retries': 2,
    'base_delay': 2,
}}
fs_app_id = {app_id!r}
fs_app_secret = {app_secret!r}
fs_allowed_users = []   # 留空=所有人可用；建议测试后填入自己的 open_id 收紧权限
"""
    for k, v in (intel or {}).items():
        body += f"{k} = {v!r}\n"
    with open(path, "w", encoding="utf-8") as f: f.write(body)
    os.chmod(path, 0o600)
    print(f"{OK} 配置完成（权限 600，已加入 .gitignore 范围）")

# ---------- 步骤 5：启动 ----------
def step_launch(with_companion=False):
    print(f"\n{T} 步骤 5/5 启动")
    if shutil.which("systemctl") and ask("安装为系统服务（开机自启）？(y/n)", "y").lower().startswith("y"):
        env_sh = os.path.join(ROOT, "env.sh")
        if not os.path.exists(env_sh):
            open(env_sh, "w").write(f'export PATH="{ROOT}/.venv/bin:$PATH"\n')
        work = os.path.expanduser("~/penglai-work"); os.makedirs(work, exist_ok=True)
        units = {"penglai-feishu": f"python {ROOT}/frontends/fsapp.py",
                 "penglai-scheduler": f"python {ROOT}/agentmain.py --reflect {ROOT}/reflect/scheduler.py"}
        if with_companion:
            units["penglai-companion"] = f"python {ROOT}/agentmain.py --reflect {ROOT}/reflect/penglai_companion.py"
        try:
            for name, cmd in units.items():
                unit = (f"[Unit]\nDescription=Penglai {name}\nAfter=network-online.target\n\n[Service]\nType=simple\n"
                        f"User={os.environ.get('USER', 'root')}\nWorkingDirectory={ROOT}\nEnvironment=HOME={os.path.expanduser('~')}\n"
                        f"Environment=GA_WORKSPACE_ROOT={work}\nExecStart=/bin/bash -lc 'source {env_sh} && exec {cmd}'\n"
                        f"Restart=always\nRestartSec=20\n\n[Install]\nWantedBy=multi-user.target\n")
                subprocess.run(["sudo", "tee", f"/etc/systemd/system/{name}.service"], input=unit, text=True,
                               check=True, stdout=subprocess.DEVNULL)
            subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)
            subprocess.run(["sudo", "systemctl", "enable", "--now"] + list(units), check=True)
            print(f"{OK} 服务已启动并设为开机自启")
        except subprocess.CalledProcessError:
            print(f"{BAD} 服务安装失败（sudo 权限？），可手动前台运行: .venv/bin/python frontends/fsapp.py")
    else:
        print(f"  前台运行命令: .venv/bin/python {os.path.join(ROOT, 'frontends/fsapp.py')}")

def main():
    print(f"{T} 欢迎使用蓬莱 Penglai — 基于 GenericAgent 的个人管家发行版")
    step_env()
    llm = step_llm()
    app_id, app_secret = step_feishu()
    agent = step_identity()
    intel = step_intel()
    comp = step_companion()
    intel.update(comp)
    step_write(llm, app_id, app_secret, intel)
    step_launch(with_companion=bool(comp))
    print(f"\n🎉 安装完成！现在去飞书找到你的应用，给「{agent}」发一句：你好")
    print("   体检: ./penglai doctor   日志: ./penglai logs   同步上游: ./penglai update")

if __name__ == "__main__":
    try: sys.exit(main())
    except KeyboardInterrupt: print("\n已取消。随时重新运行 ./penglai setup"); sys.exit(1)
