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

BANNER = r"""
  ┌─────────────────────────────────────────────────────┐
  │                                                     │
  │    蓬  莱  ·  P  E  N  G  L  A  I                  │
  │                                                     │
  │    个人 AI 管家  ·  基于 GenericAgent               │
  │    飞书 · 微信 · 记忆 · 多渠道                      │
  │                                                     │
  └─────────────────────────────────────────────────────┘
"""

def _load_providers():
    """加载 penglai_providers.yaml，失败回退到内置最小列表。"""
    yaml_path = os.path.join(ROOT, "penglai_providers.yaml")
    if not os.path.exists(yaml_path):
        return None
    try:
        import re
        with open(yaml_path, encoding="utf-8") as f:
            raw = f.read()
        # 极简 YAML 解析（只取 providers 块中需要的字段），标准库无 yaml 模块
        # 借助 venv 里的 yaml（setup 完成后可用），或降级到内置列表
        try:
            import importlib.util
            venv_py = os.path.join(ROOT, ".venv", "lib")
            # 尝试找 PyYAML
            for path in sys.path + ([venv_py] if os.path.isdir(venv_py) else []):
                if os.path.isdir(path):
                    for root_, dirs, _ in os.walk(path):
                        if "yaml" in dirs:
                            sys.path.insert(0, root_)
                            break
            import yaml
            return yaml.safe_load(raw)
        except ImportError:
            return None
    except Exception:
        return None

_PROVIDERS_DATA = _load_providers()

def _get_provider_list():
    """返回 [(序号显示名, provider_id, billing_mode_id, base_url, default_model, signup_url), ...]"""
    if not _PROVIDERS_DATA:
        # 内置兜底（数据来自 penglai_providers.yaml，保持同步）
        return [
            (1,  "DeepSeek",               "deepseek",   "paygo", "https://api.deepseek.com",                    "deepseek-v4-flash",           "https://platform.deepseek.com"),
            (2,  "字节火山 Ark (按量)",     "volcengine", "paygo", "https://ark.cn-beijing.volces.com/api/v3",    "doubao-seed-2.0-lite",        "https://console.volcengine.com/ark"),
            (3,  "字节火山 Ark (Coding)",   "volcengine", "coding_plan", "https://ark.cn-beijing.volces.com/api/coding/v3", "doubao-seed-2.0-code", "https://console.volcengine.com/ark"),
            (4,  "阿里云百炼 Qwen",         "bailian",    "paygo", "https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen3.7-plus",         "https://bailian.console.aliyun.com"),
            (5,  "智谱 GLM",               "zhipu",      "paygo", "https://open.bigmodel.cn/api/paas/v4/",       "glm-5.1",                     "https://open.bigmodel.cn"),
            (6,  "MiniMax",                "minimax",    "paygo", "https://api.minimaxi.com/v1",                 "MiniMax-M3",                  "https://platform.minimaxi.com"),
            (7,  "Moonshot Kimi",          "moonshot",   "paygo", "https://api.moonshot.cn/v1",                  "kimi-k2.6",                   "https://platform.kimi.com"),
            (8,  "OpenRouter",             "openrouter", "paygo", "https://openrouter.ai/api/v1",                "anthropic/claude-sonnet-4-6", "https://openrouter.ai"),
            (9,  "腾讯混元",               "hunyuan",    "paygo", "https://api.hunyuan.cloud.tencent.com/v1",    "hunyuan-turbos-20250416",     "https://cloud.tencent.com/product/hunyuan"),
            (10, "讯飞星火",               "xunfei",     "paygo", "https://spark-api-open.xf-yun.com/v1",        "max-32k",                     "https://www.xfyun.cn"),
            (11, "自定义 OpenAI 兼容端点", "custom",     "paygo", "",                                            "",                            ""),
        ]
    rows = []
    idx = 1
    order = _PROVIDERS_DATA.get("wizard_order", list(_PROVIDERS_DATA.get("providers", {}).keys()))
    providers = _PROVIDERS_DATA.get("providers", {})
    for pid in order:
        p = providers.get(pid)
        if not p:
            continue
        billing = p.get("billing", {})
        for bid, bdata in billing.items():
            label = f"{p['display']} ({bdata.get('label', bid)})" if len(billing) > 1 else p["display"]
            models = bdata.get("models", [])
            default_model = next((m["id"] for m in models if m.get("default")), models[0]["id"] if models else "")
            rows.append((idx, label, pid, bid, bdata.get("base_url", ""), default_model, p.get("signup_url", "")))
            idx += 1
    return rows

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
                subprocess.run([uv, "pip", "install", "--python", py, "-q", "-e", ".", "lark-oapi", "qrcode"], cwd=ROOT, check=True,
                               env={**os.environ, "UV_DEFAULT_INDEX": idx})
            else:
                subprocess.run([sys.executable, "-m", "venv", ".venv"], cwd=ROOT, check=True)
                subprocess.run([py, "-m", "pip", "install", "-q", "-i", idx, "-e", ".", "lark-oapi", "qrcode"], cwd=ROOT, check=True)
            print(f"{OK} 依赖安装完成")
        except subprocess.CalledProcessError:
            print(f"{BAD} 依赖安装失败，请手动执行后重试: python3 -m venv .venv && .venv/bin/pip install -e . lark-oapi")
            sys.exit(1)
    else:
        print(f"{OK} 虚拟环境已存在")

# ---------- 步骤 1：LLM ----------
def step_llm():
    print(f"\n{T} 步骤 1/5 选择大模型（蓬莱的大脑）")
    rows = _get_provider_list()
    for row in rows:
        if len(row) == 7:
            idx, label, pid, bid, base, model, signup = row
        else:
            idx, label, pid, bid, base, model, signup = row[0], row[1], row[2], row[3], row[4], row[5], row[6]
        model_hint = f"  默认: {model}" if model else "  （手动填模型名）"
        signup_hint = f"  {signup}" if signup else ""
        print(f"  {idx:>2}. {label:<36}{model_hint:<32}{signup_hint}")
    print()

    # 弃用模型警告表（来自 providers yaml）
    deprecated_map = {}
    if _PROVIDERS_DATA:
        for p in _PROVIDERS_DATA.get("providers", {}).values():
            for d in p.get("deprecated", []):
                deprecated_map[d["id"]] = d.get("replace", "")

    while True:
        try:
            chosen = int(ask("选择序号", "1")) - 1
            row = rows[chosen]
            if len(row) == 7:
                _, name, pid, bid, base, default_model, signup = row
            break
        except (ValueError, IndexError):
            print("  无效序号，请重选")

    # plan 警告
    if _PROVIDERS_DATA and pid in _PROVIDERS_DATA.get("providers", {}):
        bdata = _PROVIDERS_DATA["providers"][pid].get("billing", {}).get(bid, {})
        if bdata.get("warning"):
            print(f"  ⚠️  {bdata['warning']}")

    if not base:
        base = ask("API Base URL（如 https://api.example.com/v1）")
    model = ask("模型名", default_model)

    # 弃用提示
    if model in deprecated_map:
        replace = deprecated_map[model]
        print(f"  ⚠️  {model} 即将废弃，建议改用 {replace}")
        if ask(f"改用 {replace}？(y/n)", "y").lower().startswith("y"):
            model = replace

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
_FS_REG = "https://accounts.feishu.cn/oauth/v1/app/registration"

def _post_form(url, body, timeout=10):
    """表单 POST。注册端点 4xx 也带 JSON（poll 的 authorization_pending 走 400），照常解析。"""
    import urllib.error, urllib.parse
    req = urllib.request.Request(url, data=urllib.parse.urlencode(body).encode(),
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raw = e.read()
        if raw:
            try: return json.loads(raw.decode())
            except ValueError: raise
        raise

def _render_qr(url):
    """终端渲染二维码。当前解释器没有 qrcode 就借 venv 的（step_env 已装入）。"""
    code = ("import qrcode\nq=qrcode.QRCode(); q.add_data(%r); q.make(fit=True); "
            "q.print_ascii(invert=True)" % url)
    for py in (sys.executable, os.path.join(ROOT, ".venv", "bin", "python")):
        if os.path.exists(py) and subprocess.run([py, "-c", code]).returncode == 0:
            return True
    return False

def _feishu_qr_create():
    """扫码自动建应用：飞书官方设备码注册流（accounts.feishu.cn）。
    begin 拿二维码 → 手机飞书扫码确认 → 平台自动创建配好权限的机器人应用 → poll 返回凭证。
    成功返回 (app_id, app_secret)，失败返回 None（外层回落手动）。"""
    init = _post_form(_FS_REG, {"action": "init"})
    if "client_secret" not in (init.get("supported_auth_methods") or []):
        return None
    begin = _post_form(_FS_REG, {"action": "begin", "archetype": "PersonalAgent",
                                 "auth_method": "client_secret", "request_user_info": "open_id"})
    device = begin.get("device_code")
    if not device:
        return None
    qr_url = begin.get("verification_uri_complete", "")
    shown = _render_qr(qr_url)
    print(f"  📱 打开手机飞书「扫一扫」，{'扫上方二维码' if shown else '扫码入口见下方链接（电脑浏览器打开后出码）'}，确认创建机器人应用")
    print(f"  {qr_url}\n  等待确认", end="", flush=True)
    deadline = time.monotonic() + min(int(begin.get("expires_in") or 600), 600)
    interval = max(int(begin.get("interval") or 5), 2)
    while time.monotonic() < deadline:
        try:
            res = _post_form(_FS_REG, {"action": "poll", "device_code": device, "tp": "ob_app"})
        except Exception:
            time.sleep(interval); continue
        if res.get("client_id") and res.get("client_secret"):
            print()
            return res["client_id"], res["client_secret"]
        if res.get("error") in ("access_denied", "expired_token"):
            print(f"\n  {BAD} " + ("已在手机上取消" if res["error"] == "access_denied" else "二维码已过期"))
            return None
        print(".", end="", flush=True)
        time.sleep(interval)
    print(f"\n  {BAD} 等待扫码超时")
    return None

def _feishu_verify(app_id, app_secret):
    r = post_json("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                  {"app_id": app_id, "app_secret": app_secret})
    return r.get("code") == 0, r.get("msg")

def step_feishu():
    print(f"\n{T} 步骤 2/5 接入飞书")
    print("  1. 手机飞书扫码，自动创建机器人应用（推荐，免开网页）")
    print("  2. 手动填入已有的 App ID / App Secret")
    if ask("选择方式", "1") == "1":
        try:
            cred = _feishu_qr_create()
        except Exception as e:
            print(f"  {BAD} 扫码流程异常：{e}"); cred = None
        if cred:
            app_id, app_secret = cred
            print("  凭证验证中...", end="", flush=True)
            ok, msg = _feishu_verify(app_id, app_secret)
            if ok:
                print(f"\r{OK} 应用已创建，凭证有效（App ID: {app_id}）"); return app_id, app_secret
            print(f"\r{BAD} 自动创建的凭证验证失败：{msg}")
        print("  ↓ 回落手动方式")
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
            ok, msg = _feishu_verify(app_id, app_secret)
            if ok:
                print(f"\r{OK} 飞书凭证有效"); return app_id, app_secret
            print(f"\r{BAD} 飞书返回错误：{msg}（检查是否复制完整）")
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

def step_wechat():
    """可选渠道：微信（GA 原生 iLink 协议，扫码绑定）。须在 mykey 写入后调用。"""
    print(f"\n{T} 可选渠道 · 微信（扫码绑定个人微信，作为第二渠道）")
    if not ask("接入微信？(y/n)", "n").lower().startswith("y"):
        return False
    py = os.path.join(ROOT, ".venv", "bin", "python")
    print("  安装微信依赖...", end="", flush=True)
    r = subprocess.run(["uv", "pip", "install", "-q", "--python", py,
                        "qrcode", "pillow", "pycryptodome", "pilk"], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"\r{BAD} 依赖安装失败：{(r.stderr or '')[-120:]}"); return False
    print(f"\r{OK} 微信依赖就绪（qrcode/pillow/pycryptodome/pilk）")
    tok = os.path.expanduser("~/.wxbot/token.json")
    if os.path.exists(tok) and not ask("检测到已有微信绑定，重新扫码？(y/n)", "n").lower().startswith("y"):
        print(f"{OK} 沿用现有绑定"); return True
    print("  📱 打开手机微信「扫一扫」，扫终端二维码并确认（图片也存在 ~/.wxbot/wx_qr.png）")
    # 绕过 GA 主入口的 isatty 检查 bug（检查发生在 stdout 重定向之后，扫码路径不可达），直接调 WxBotClient
    code = (f"import sys; sys.path[:0] = [{ROOT!r}, {os.path.join(ROOT, 'frontends')!r}]\n"
            "from wechatapp import WxBotClient\n"
            "WxBotClient().login_qr()\n")
    if subprocess.run([py, "-c", code]).returncode != 0:
        print(f"{BAD} 扫码未完成（可稍后重跑 penglai setup，只重做本步）"); return False
    print(f"{OK} 微信绑定成功（token 已存 ~/.wxbot/，重启不用重扫）")
    return True

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
def step_launch(with_companion=False, with_wechat=False):
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
        if with_wechat:
            units["penglai-wechat"] = f"python {ROOT}/frontends/wechatapp.py"
        try:
            for name, cmd in units.items():
                # 微信退出码 1=单例/无token、2=token过期需人扫码 → 不自动重启刷屏
                extra = "RestartPreventExitStatus=1 2\n" if name == "penglai-wechat" else ""
                unit = (f"[Unit]\nDescription=Penglai {name}\nAfter=network-online.target\n\n[Service]\nType=simple\n"
                        f"User={os.environ.get('USER', 'root')}\nWorkingDirectory={ROOT}\nEnvironment=HOME={os.path.expanduser('~')}\n"
                        f"Environment=GA_WORKSPACE_ROOT={work}\nExecStart=/bin/bash -lc 'source {env_sh} && exec {cmd}'\n"
                        f"Restart=always\nRestartSec=20\n{extra}\n[Install]\nWantedBy=multi-user.target\n")
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
    print(BANNER)
    step_env()
    llm = step_llm()
    app_id, app_secret = step_feishu()
    agent = step_identity()
    intel = step_intel()
    comp = step_companion()
    intel.update(comp)
    step_write(llm, app_id, app_secret, intel)
    wx = step_wechat()
    step_launch(with_companion=bool(comp), with_wechat=wx)
    print(f"\n🎉 安装完成！现在去飞书找到你的应用，给「{agent}」发一句：你好")
    print("   体检: ./penglai doctor   日志: ./penglai logs   同步上游: ./penglai update")

if __name__ == "__main__":
    try: sys.exit(main())
    except KeyboardInterrupt: print("\n已取消。随时重新运行 ./penglai setup"); sys.exit(1)
