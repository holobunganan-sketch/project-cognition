# Project Cognition

简体中文 | [English](README.md)

Project Cognition 是一个可独立安装到 Codex 的 Skill。它会为任意项目目录建立可持久化、可追溯来源、可增量刷新的结构化认知层。后续 Agent 或新会话能够复用既有索引，只处理发生变化的文件，并根据当前任务生成精简上下文包，从而减少重复扫描和输入 Token 消耗。

## 主要能力

- 为项目目录建立可复用的结构索引。
- 增量识别新增、修改、删除和重命名文件。
- 记录路径、元数据、SHA-256、符号、标题和导入关系。
- 生成可读的项目地图和任务专用上下文包。
- 在生成上下文前自动校验索引是否与项目文件同步。
- 完整重建时保留人工维护的项目知识。
- 排除常见依赖目录、构建目录、二进制文件、凭据和敏感文件。
- 仅使用 Python 标准库，不访问网络。

## 同步机制

项目文件始终是唯一事实源，`.project-cognition/` 属于可以重建的缓存层。

每次调用都会先执行 `prepare`：

1. 定位项目根目录并读取上一次清单。
2. 比较当前文件集合、Git 状态和上一次快照。
3. 使用文件元数据快速筛选，使用 SHA-256 最终确认内容变化。
4. 只重新处理新增、修改、重命名和删除的文件。
5. 以原子方式刷新受影响的生成视图。
6. 相关索引更新完成后再生成任务上下文包。

它不依赖后台常驻服务。Agent 完成一批连贯修改后再执行一次 `prepare`，即可保证后续查询读到最新结果。

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

Release 同时提供适合插件式安装的 skills-only Plugin 包。

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
python scripts/project_cognition.py rebuild --project .
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

## 运行要求

- Python 3.9 或更高版本
- Git 可选
- 无第三方 Python 依赖
- 支持 Windows、macOS 和 Linux

## 安全原则

- 项目原始文件始终具有最高权威性。
- 生成摘要只用于导航；重要结论和修改必须回到源文件核验。
- 默认排除凭据、私钥、环境变量文件、依赖目录、构建目录、缓存和二进制内容。
- 上下文摘录中的敏感赋值会被脱敏。
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

发行脚本会生成：

- `project-cognition-skill-vX.Y.Z.zip`
- `project-cognition-plugin-vX.Y.Z.zip`
- `SHA256SUMS.txt`

## 当前限制

- 新会话能否自动调用仍取决于宿主是否选择该 Skill；显式使用 `$project-cognition` 最稳定。
- Agent 生成的语义总结仍需根据源文件核验。
- 当前版本采用确定性结构索引和词法检索，不依赖向量数据库。
- 超大文件和不支持的二进制文件会被跳过。

## 许可证

MIT License，详见 [LICENSE](LICENSE)。
