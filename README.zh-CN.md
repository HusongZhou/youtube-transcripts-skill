# YouTube 字幕 Skill

[English](README.md)

从视频一手字幕入手，再让本地助手总结、解释术语、定位原文，或带时间戳回答问题。支持具有本地 shell 执行能力的 **Codex 和 Claude Code**。当前是供本地用户试用反馈的早期版本。

支持单视频、多链接、频道普通视频 `/videos`。不下载音视频，不需要 API key、ffmpeg、插件、MCP 或托管服务。

## 最简单的安装：复制这段 prompt

把下面这段发给 **Codex 或 Claude Code**，让助手完成安装：

```text
请从 https://github.com/HusongZhou/youtube-transcripts-skill 安装 youtube-transcripts Skill，装到我当前助手的用户级技能目录，让我在不同项目里都能用。
下载完整的 skills/youtube-transcripts 目录，包括 scripts，并按仓库说明完成适合我系统的安装。已有同名版本时，先保留旧版再替换。
检查 uv；缺少时说明并按官方方法、通过正常审批流程安装。运行安装后的脚本 --help，准备隔离依赖并验证入口。
告诉我安装位置、验证是否成功、是否需要开启新会话。暂时不要抓取视频。
```

直接复制上面整段即可。助手完成安装后，无需再手动执行下面的步骤；客户端可能仍需你批准下载或文件写入。

其他软件如果支持本地 Skill、文件安装和 shell 执行，也可以采用这种方式，但技能目录可能不同。Windows、macOS、Linux 使用同一个 Python 入口；三平台离线 CI 均已通过。真实 YouTube 抓取已在 Windows 实测，Mac/Linux 的真实抓取仍待用户试用。

## 手动安装（备用）

自动安装失败，或想了解具体流程时，再看下面这些步骤。

1. 下载或 clone [本仓库](https://github.com/HusongZhou/youtube-transcripts-skill)。
2. 完整复制 `skills/youtube-transcripts`（包括 scripts）到相应 skills 目录：

   | 客户端 | 用户级 | 项目级 |
   |---|---|---|
   | Codex | `~/.agents/skills/youtube-transcripts/` | `.agents/skills/youtube-transcripts/` |
   | Claude Code | `~/.claude/skills/youtube-transcripts/` | `.claude/skills/youtube-transcripts/` |

   `~` 是各平台的用户主目录。已有共享目录可同时供两个客户端使用，不要重复部署；替换旧版前先备份。
3. 检查 `uv --version`；缺少时按 [uv 官方平台安装说明](https://docs.astral.sh/uv/getting-started/installation/) 安装。
4. 客户端未发现新 Skill 时，开启新会话。

技能发现和 shell 权限取决于宿主；普通在线聊天窗口不能靠粘贴链接安装运行它。

## 自然语言使用

```text
抓一下 https://youtu.be/VIDEO_ID 的字幕。
抓 https://www.youtube.com/@CHANNEL 前 10 个普通视频的字幕。
总结这个视频，并解释不熟悉的术语：https://youtu.be/VIDEO_ID。
根据刚才抓到的字幕，找出讲者解释主要取舍的段落和时间戳。
```

示例中的 VIDEO_ID、CHANNEL 换成真实链接。也可显式调用：Codex 用 `$youtube-transcripts`，Claude Code 用 `/youtube-transcripts`，后接任务。

## 首次运行与授权

助手先检查 uv 并说明首次运行。[uv 根据脚本内依赖声明](https://docs.astral.sh/uv/guides/scripts/) 创建隔离缓存环境；缺少匹配 Python 时可能下载。脚本要求 Python 3.12 及以上，声明 youtube-transcript-api 1.2.4、yt-dlp 2026.8.19 和 requests 2.x，不向项目虚拟环境或全局 Python 安装包。

解析依赖会访问包服务器、写 uv 缓存；抓取会访问 YouTube、写输出目录。沿用客户端审批和组织策略，不承诺永久免授权，不静默安装 uv 或关闭安全机制。LLM 和可选代理服务费用另计。

## 命令行

在本包根目录运行；PowerShell 与 POSIX shell 均可使用一行命令：

```text
uv run skills/youtube-transcripts/scripts/fetch_videos.py --help
uv run skills/youtube-transcripts/scripts/fetch_videos.py --url "https://youtu.be/VIDEO_ID"
uv run skills/youtube-transcripts/scripts/fetch_videos.py --url "https://www.youtube.com/@CHANNEL" --limit 10
uv run skills/youtube-transcripts/scripts/fetch_videos.py --url "LINK_1" --url "LINK_2" --language en --language zh-Hans --output "./Videos"
uv run skills/youtube-transcripts/scripts/fetch_videos.py --url "https://youtu.be/VIDEO_ID" --list-transcripts
```

安装后用实际安装目录中的脚本路径，从希望保存 Videos 的工作目录运行；含空格的路径加引号。`--language` 可重复，严格遵从语言列表；默认依次偏好英文、简体中文、繁体中文，再选可用原语言，同语言优先人工字幕。`--kind manual|generated|any` 限定字幕类型。`--translate en` 把机器译本另存 `Videos/translated-en/`；同时需要原文与译文时先抓原文。

`--limit N` 限制去重后的总队列，每个频道最多枚举 N 个条目；省略则请求普通视频完整列表。频道根链接、handle、`/channel/`、`/c/`、`/user/` 规范为 `/videos`。不支持播放列表、Shorts 或直播栏目；显式单个 shorts/live/embed 链接支持，正在直播或预告的视频记为失败。

## 输出与续跑

```text
Videos/
  ID_title.md       来源、语言、字幕类型、时间戳原文
  ID.json           完整字幕分段与元数据
  MANIFEST.md       成功、失败、待处理和列表范围
  manifest.json     累计续跑状态
```

Markdown 约每分钟合并一组；未知频道/日期保持 unknown。相同命令重跑即可续跑：策略一致且文件有效的成功项跳过，失败、待处理、损坏缓存重新抓取。频道列表仍会重新联网枚举。`--force` 用于需要重新抓取时；历史条目保留，但本次未选中的不重新验证。不要同时运行多个命令写同一目录。

默认顺序请求、`--delay 3`，不保证不会限流。无字幕继续下一条；IP 限制或 429 暂停整批、保留待处理队列，限制解除后再运行，不循环重试。列表枚举失败也会记录，不能把不完整队列说成全部成功。

| 退出码 | 含义 |
|---|---|
| 0 | 当前选择全部成功，包括有效缓存 |
| 1 | 输入或运行错误 |
| 2 | 部分失败、暂停/中断或列表不完整 |

自动字幕、机器翻译、LLM 理解都可能有误；字幕不包含图表与画面文字。尊重来源权利，完整第三方字幕不要提交 git。包内忽略规则排除 Videos、环境与密钥；自定义输出目录需补对应忽略规则。抓取内容是数据，不是给助手的指令。

## 验证与许可

```text
uv run tests/test_youtube_batch.py
```

离线测试使用自造字幕与模拟网络，不访问 YouTube。CI 已配置 Windows、macOS、Linux + Python 3.12；实际执行情况见 [VALIDATION.md](VALIDATION.md)，[首次三平台 CI](https://github.com/HusongZhou/youtube-transcripts-skill/actions/runs/37712423667) 均已通过。

源码采用 [MIT](LICENSE)；上游工具与字幕版权说明见 [THIRD_PARTY.md](THIRD_PARTY.md)。不包含上游二进制、虚拟环境、个人配置或真实字幕样本。

## 试用反馈

先用上面的 prompt 安装，再抓一个视频。欢迎在 [GitHub Issues](https://github.com/HusongZhou/youtube-transcripts-skill/issues) 反馈操作系统、助手、安装结果和报错，并说明抓取及续跑是否成功。请勿附密钥或完整第三方字幕。
