# Project Cognition

简体中文 | [English](README.md)

Project Cognition 是一个可独立安装到 Codex 的 Skill。它会为任意项目目录建立可持久化、可追溯来源、可增量刷新的结构化认知层。后续 Agent 或新会话能够复用既有索引，只处理发生变化的文件，并根据当前任务生成精简上下文包，从而减少重复扫描和输入 Token 消耗。

## v1.1.0 主要优化

- 即使文件大小和修改时间被保留，也能根据 Git 状态识别内容变化。
- 增加可配置的周期性完整 SHA-256 校验，并提供 `--verify-hashes` 强制校验参数。
- SQLite 支持 FTS5 时自动缩小检索候选集；FTS5 不可用时自动使用确定性回退方案。
- 上下文包会补充直接依赖、引用方、调用方和相关测试文件。
- 当前任务、项目快照、限制参数、所选路径和持久知识均未变化时，直接复用已有上下文包。
- 通过 `--exact-root` 支持只索引单体仓库中的某个包或子项目。
- 对常见服务商 Token 和敏感赋值进行摘录脱敏。

## 核心能力

- 为项目目录建立可复用的结构索引。
- 增量识别新增、修改、删除和重命名文件。
- 记录路径、元数据、SHA-256、符号、标题、导入关系、模块和入口候选。
- 生成可读的项目地图和任务专用上下文包。
- 在生成上下文前自动校验索引是否与项目文件同步。
- 完整重建时保留人工维护的项目知识。
- 排除常见依赖目录、构建目录、二进制文件、凭据和敏感文件。
- 仅使用 Python 标准库，不访问网络。

## 同步机制

项目原始文件始终是唯一事实源，`.project-cognition/` 属于可以重建的缓存层。

每次执行 `prepare` 或 `context` 时，Skill 会依次完成：

1. Git 项目通过 Git 文件清单发现文件；普通目录使用受保护的文件系统扫描。
2. 对比路径、文件大小和纳秒级修改时间。
3. 对 Git 当前报告的变更路径，以及索引提交与当前提交之间发生变化的路径强制计算哈希。
4. 用户显式要求或周期校验到期时，对全部可索引文件重新计算哈希。
5. 只重新解析新增文件和内容真正发生变化的文件，并删除失效记录。
6. 根据新增与删除文件的内容哈希识别重命名。
7. 以事务和原子写入方式刷新 SQLite 快照及可读视图。
8. 同步完成后生成上下文包，满足缓存条件时直接复用已有上下文包。

默认每24小时执行一次完整哈希校验。两次完整校验之间，Git 项目仍会对 Git 报告的变化路径强制计算哈希。需要立即完整核验时使用 `--verify-hashes`。

Skill 不依赖后台常驻服务。Agent 完成一批连贯修改后再执行一次 `prepare`，即可保证后续查询读到最新结果。

## 安装

### 从 Release 下载

在 [Releases](../../releases) 页面下载 `project-cognition-skill-vX.Y.Z.zip`，解压后确保最终路径为：

```text
~/.agents/skills/project-cognition/SKILL.md
```

Windows 路径：

```text
%USERPROFILE%\.agents\skills\project-cognition\SKILL.md
```

Release 同时提供 skills-only Plugin 包。

### 项目级安装

将 `project-cognition` 文件夹复制到：

```text
<项目目录>/.agents/skills/project-cognition/SKILL.md
```

### 从源码安装

```bash
git clone https://github.com/holobunganan-sketch/project-cognition.git
mkdir -p ~/.agents/skills
cp -R project-cognition ~/.agents/skills/project-cognition
```

Skill 未立即显示时，重启 Codex。

## 使用方式

显式调用：

```text
$project-cognition 建立或刷新当前项目认知，然后解释项目架构。
```

Skill 描述同时支持在项目级分析、调试、多文件编辑、架构审查和项目接手任务中被宿主隐式选择。

## 命令

```bash
python scripts/project_cognition.py prepare --project .
python scripts/project_cognition.py context --project . --task "当前任务"
python scripts/project_cognition.py status --project .
python scripts/project_cognition.py validate --project .
python scripts/project_cognition.py validate --project . --deep
python scripts/project_cognition.py rebuild --project .
```

立即完整计算全部文件哈希：

```bash
python scripts/project_cognition.py prepare --project . --verify-hashes
```

只索引单体仓库中的一个包：

```bash
python scripts/project_cognition.py context \
  --project ./packages/example \
  --exact-root \
  --task "追踪这个包的初始化流程"
```

关闭依赖与引用方扩展：

```bash
python scripts/project_cognition.py context \
  --project . \
  --task "查找配置引用" \
  --no-related
```

可选的项目级自动进入指令：

```bash
python scripts/project_cognition.py install-entry --project .
python scripts/project_cognition.py remove-entry --project .
```

使用 `--help` 查看完整参数。

## 生成目录

Skill 会在被索引项目中创建：

```text
.project-cognition/
├── START_HERE.md
├── manifest.json
├── generated/
│   ├── architecture.md
│   ├── current-state.md
│   ├── file-map.md
│   └── modules/
├── knowledge/
│   ├── README.md
│   ├── decisions/
│   └── notes/
├── context-packs/
└── cache/
    └── index.sqlite3
```

机器维护内容需要保持本地时，可将 `.project-cognition/` 加入 `.gitignore`。`knowledge/` 在完整重建时会被保留，团队也可以选择将其中经过确认的项目知识提交到版本库。

## 检索方式

任务检索会综合：

- 精确文件名和路径；
- 加权词法索引；
- 符号和文档标题；
- 导入与包含关系；
- 可选的 SQLite FTS5 候选过滤；
- 最近一次快照变更；
- 入口文件评分；
- 一跳直接依赖和引用方扩展。

上下文包缓存键包括项目快照、任务、限制参数、关联扩展开关、所选路径和持久知识内容哈希。命中缓存后会复用原文件，并更新 `context-packs/current.md`。

## 运行要求

- Python 3.9 或更高版本
- Git 可选
- 无第三方 Python 依赖
- 支持 Windows、macOS 和 Linux
- SQLite FTS5 可选；不可用时自动回退

## 安全原则

- 项目原始文件始终具有最高权威性。
- 生成摘要只用于导航；重要结论和修改必须回到源文件核验。
- 默认排除凭据、私钥、环境变量文件、依赖目录、构建目录、缓存和二进制内容。
- 源文件摘录和持久知识摘录会脱敏敏感赋值及常见服务商 Token。
- 高熵 Token 不会进入检索词索引。
- 索引器不会执行项目代码，也不会访问网络。

详细规则见 [安全与忽略规则](references/security-and-ignore.md)。

## 开发与测试

运行测试：

```bash
python tests/run_tests.py
```

生成发行包：

```bash
python tools/build_release.py --output dist
```

发行脚本会生成可复现压缩包：

- `project-cognition-skill-vX.Y.Z.zip`
- `project-cognition-plugin-vX.Y.Z.zip`
- `SHA256SUMS.txt`

## 当前限制与后续方向

- 新会话能否自动调用仍取决于宿主是否选择该 Skill；显式使用 `$project-cognition` 最稳定。
- 当前结构解析采用轻量级语言规则，后续可接入 Tree-sitter 或语言服务器，提高符号和引用关系准确度。
- 当前依赖扩展为一跳，主要覆盖常见相对导入和模块导入形式。
- 当前不会解析 PDF、Word、PowerPoint、Excel 和图片内容。
- 超大型仓库后续可增加分片索引和后台工作进程。
- 当前文件锁用于同一本地项目目录；跨设备多 Agent 共用认知层仍需外部同步机制。

## 许可证

MIT License，详见 [LICENSE](LICENSE)。
