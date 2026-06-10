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
    mem = os.path.join(ROOT, "memory", "global_mem.txt")
    if os.path.exists(mem) and sum(1 for _ in open(mem, encoding="utf-8", errors="replace")) > 6:
        print(f"  ⚠️ 检测到已有使用中的记忆，跳过身份写入（身份与记忆分离原则，绝不覆盖）")
        return agent
    os.makedirs(os.path.dirname(mem), exist_ok=True)
    with open(mem, "w", encoding="utf-8") as f:
        f.write(f"## 身份\n- 我是「{agent}」，基于 GenericAgent 的开源个人管家发行版蓬莱。\n- 用户称呼：{user}。\n")
    print(f"{OK} 身份已写入（出厂态记忆）")
    return agent

# ---------- 步骤 4：写配置 ----------
def step_write(llm, app_id, app_secret):
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
    with open(path, "w", encoding="utf-8") as f: f.write(body)
    os.chmod(path, 0o600)
    print(f"{OK} 配置完成（权限 600，已加入 .gitignore 范围）")

# ---------- 步骤 5：启动 ----------
def step_launch():
    print(f"\n{T} 步骤 5/5 启动")
    if shutil.which("systemctl") and ask("安装为系统服务（开机自启）？(y/n)", "y").lower().startswith("y"):
        env_sh = os.path.join(ROOT, "env.sh")
        if not os.path.exists(env_sh):
            open(env_sh, "w").write(f'export PATH="{ROOT}/.venv/bin:$PATH"\n')
        work = os.path.expanduser("~/penglai-work"); os.makedirs(work, exist_ok=True)
        units = {"penglai-feishu": f"python {ROOT}/frontends/fsapp.py",
                 "penglai-scheduler": f"python {ROOT}/agentmain.py --reflect {ROOT}/reflect/scheduler.py"}
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
    step_write(llm, app_id, app_secret)
    step_launch()
    print(f"\n🎉 安装完成！现在去飞书找到你的应用，给「{agent}」发一句：你好")
    print("   体检: ./penglai doctor   日志: ./penglai logs   同步上游: ./penglai update")

if __name__ == "__main__":
    try: sys.exit(main())
    except KeyboardInterrupt: print("\n已取消。随时重新运行 ./penglai setup"); sys.exit(1)
