# 安装与使用

## Windows：用户级安装

1. 解压 ZIP，确认解压后的目录中直接存在 `project-cognition/SKILL.md`。
2. 将整个 `project-cognition` 文件夹复制到：

```text
%USERPROFILE%\.agents\skills\project-cognition
```

PowerShell 示例：

```powershell
$target = Join-Path $HOME ".agents\skills\project-cognition"
New-Item -ItemType Directory -Force (Split-Path $target) | Out-Null
Copy-Item -Recurse -Force ".\project-cognition" $target
```

3. 在 Codex 中输入 `/skills`，确认可以看到 `project-cognition`。未出现时重启 Codex。
4. 显式调用：

```text
$project-cognition 先建立当前项目认知，然后分析这个项目的架构。
```

## 仓库级安装

将文件夹复制到项目内：

```text
<项目根目录>/.agents/skills/project-cognition/SKILL.md
```

该安装方式只对当前项目及其子目录生效。

## 运行要求

- Python 3.9或更高版本。
- Git可选；Git项目会自动使用Git文件清单和忽略规则。
- 无第三方Python依赖。

## 生成目录

首次运行后，Skill会在项目根目录创建：

```text
.project-cognition/
```

该目录保存结构索引、项目地图和任务上下文包。需要保持本地时，可将它加入项目的 `.gitignore`。

## 自动进入项目认知流程

Skill支持基于描述的隐式调用，宿主是否自动选择Skill仍由Codex判断。需要提高项目内每次新对话的触发稳定性时，明确要求Skill执行：

```bash
python "<Skill目录>/scripts/project_cognition.py" install-entry --project "<项目根目录>"
```

该命令向 `AGENTS.md` 添加可识别、可重复执行、可移除的托管区块。只有在用户明确要求时才应执行。
