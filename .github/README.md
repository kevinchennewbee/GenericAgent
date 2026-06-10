# 蓬莱 Penglai

**基于 [GenericAgent](https://github.com/lsdefine/GenericAgent) 的中文个人管家发行版**
*A Chinese personal-butler distribution of GenericAgent — kernel untouched, batteries included.*

> 八仙过海，各显神通。

---

## 这是什么

蓬莱**不是一个新框架**。它之于 GenericAgent（GA），如同 Ubuntu 之于 Linux 内核：

- **完整保留 GA 的全部代码与功能**——内核文件零改动，随时合并上游更新；
- 在 GA 的原生扩展面上，叠加一层面向中文个人用户的精选外设；
- 你的管家自称「蓬莱助手 Penglai」，跑在你自己的服务器上，记忆只属于你。

GA 的本质是一个 ~130 行的 Agent 循环：`上下文 → LLM → 工具 → 结果回流`。
蓬莱层的每一个功能，都挂在这个循环的五个坐标位上（唤醒 / 知道 / 能做 / 看着 / 出口），
绝不修改循环本身。

## 蓬莱层提供什么

| 状态 | 能力 | 说明 |
|---|---|---|
| ✅ | `penglai` 入口命令 | 用户唯一入口：`doctor` 体检 · `start/stop/status/logs` 服务管理 · `update` 一键同步上游 GA |
| ✅ | `penglai doctor` | 七项体检：环境/依赖/配置/LLM/记忆/服务/上游（GA 没有的，理念来自 Hermes doctor） |
| 🚧 | `penglai setup` 向导 | 目标：新用户 10 分钟从裸机到飞书说上话 |
| 🚧 | 语音 + 情绪感知 | SenseVoice-Small（int8 约 230MB，CPU 可跑）：语音转文字 + 情绪标签 |
| 🚧 | 确定性安全 | 红线检查 + 全量审计日志（hook 插件，不靠 LLM 自觉） |
| 🚧 | 防幻觉双脑 | 绊线检测 + 跨厂商二次复核（写记忆前 / 重要结论前 / 不可逆操作前） |
| 🚧 | 主动陪伴 | 心跳 + 门禁（勿扰时段、对话中不插话、频率上限），真主动而非闹钟 |

## 快速开始

```bash
git clone https://github.com/kevinchennewbee/Penglai.git && cd Penglai
./penglai setup     # 向导开发中，当前请参考上游 GA 文档配置 mykey.py
./penglai doctor    # 体检
```

服务器部署（systemd）后，日常只需要：

```bash
penglai status / logs / restart
penglai update      # 同步上游 GA：蓬莱层全部是新增文件，合并零冲突
```

## 设计三原则

1. **改门面，不改骨架**：品牌活在入口（`penglai` 命令、README、服务名），不在 GA 的骨头里。
2. **形态梯度**：新能力优先用 SOP（0 行代码）实现，其次 hook 插件，再次 reflect 模块，最后才是工具——永不修改内核。
3. **身份与记忆分离**：发行版出厂态零用户记忆，只带一行身份。你的记忆是你的隐私资产。

## 致谢

- [GenericAgent](https://github.com/lsdefine/GenericAgent)（MIT）——内核本身，极简与自进化哲学的源头
- [Hermes Agent](https://github.com/NousResearch/hermes-agent)（MIT）——doctor 与安装体验、渠道质量标准、记忆卫生
- [PilotDeck](https://github.com/OpenBMB/PilotDeck)（AGPL，仅借鉴设计理念）——门禁系统与可回滚纪律
- [SenseVoice / FunASR](https://github.com/FunAudioLLM/SenseVoice)——CPU 友好的语音与情绪识别
- TencentDB Agent Memory / Hindsight / Letta / Mem0 / Graphiti——记忆系统理念调研来源
- OpenClaw——“Agent 的本质是一个循环”

## 许可证

MIT（与上游 GenericAgent 一致）。根目录 `README.md` 为上游 GA 原版文档，保持零改动。
