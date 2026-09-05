# QingmaKiller 青马易战自动答题工具

这是一个起步并不成熟的项目，缺少完善的异常处理和工程设计——在 AI Agent 的辅助下，我深度重构和完善了它。希望这个项目和以下相关项目多少能够帮助到你，不要将时间和精力浪费在毫无意义的形式上。

- 同类项目：[青马易战自动刷题(@shibig666)](https://github.com/shibig666/QMYZ)、[AutoQMYZ(@Haicaji)](https://github.com/Haicaji/AutoQMYZ)
- 相关项目：[安全微伴-大学新生安全教育课程自动刷题(@hangone)](https://github.com/hangone/WeBan)、[超星学习通自动化完成任务点(@Samueli924)](https://github.com/Samueli924/chaoxing)、[随地大小签(@aquamarine5)](https://github.com/aquamarine5/ChaoxingSignFaker)

## 这是什么？

这是面向某大学公共思政课（线上作业部分）的自动答题工具，主要功能如下：

- URL 自动提取 Cookie
- 本地会话缓存与失效诊断
- 答题次数与目标正确率配置
- 防刷题题目自动跳过
- 随机答题延迟
- 本地题库 + 在线题库兜底（感谢[题库适配器(@DokiDoki1103)](https://github.com/DokiDoki1103/tikuAdapter)）

> [!WARNING]
> 本工具遵循MIT License，即任何人都有免费获得本软件和相关文档文件副本的许可，能够不受限制地处理本软件，包括但不限于使用、复制、修改、合并、发布、分发、再许可的权利，被许可人有权利使用、复制、修改、合并、出版发行、散布、再许可和/或贩售软件及软件的副本，及授予被供应人同等权利，但在软件和软件的所有副本中都必须包含版权声明和许可声明，**作者不对使用本项目产生的任何后果承担责任**。

## 使用方法

**若需要下载发行版本请进入 [Releases](https://github.com/Xuuyuan/QingmaKiller/releases)**，压缩包内含主程序 `QingmaKiller.exe`、搜题服务 `tikuAdapter.exe` 与本地题库 `tiku.json`，解压后双击 `QingmaKiller.exe` 即可使用，无需配置 Python 环境。源码运行则请按照以下步骤依次执行。

### 1. 拉取本仓库至本地

在仓库主页面中单击 Code 按钮，根据实际需求选择 Clone 或 Download ZIP（若无二次开发/在 VSCode 等 IDE 中运行的需求时，可以选择 Download ZIP）。

### 2. 运行 tikuAdapter

仓库中已经内置了 tikuAdapter_0.1.0-beta.39 的可执行文件，适用于 Windows_amd64。在 Windows 系统中启动主程序时，会自动启动/关闭 tikuAdapter 服务。  
若需要应用于其它系统，请前往 [tikuAdapter Releases](https://github.com/DokiDoki1103/tikuAdapter/releases) 下载。

### 3. 配置环境（二选一）

#### 3.1 使用 uv 管理环境

1. **安装 uv** (如果尚未安装) 在终端中执行如下指令:
   - **Windows 系统**： `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
   - **macOS/Linux 系统**： `curl -LsSf https://astral.sh/uv/install.sh | sh`
   - 使用 pip 安装（若已安装 Python 环境）： `pip install uv`

2. **直接运行**：
    在项目根目录下打开终端，执行以下指令：

    ```bash
    uv run main.py
    ```

#### 3.2 使用 pip 管理环境

请使用 Python 3.8+ 环境运行，相关环境请自行配置。  
工具所需的软件包已在 `pyproject.toml` 中注明，或可在项目根目录下打开终端、执行以下指令：

```bash
pip install .
```

依赖安装完成后，在项目根目录下打开终端，执行 `python main.py` 运行主程序，按照提示输入参数即可。

### 4. 完成用户认证

用户认证获取方法（程序按以下优先级自动依次尝试）：

1. **本地会话复用**：程序会将会话缓存在同目录的 `session.json` 中，下次运行时自动验证；验证通过后会询问沿用该会话还是切换其它账号（直接回车沿用，输入 `y` 并回车切换），有效期内无需再次认证；
2. **URL 认证**：进入青马易战主界面（有大视频播放的页面），点击右上角交互按钮，选择【复制链接】，将获取到的 URL 粘贴到输入框中。若 URL 已失效，程序会在数秒内给出明确提示，此时请重新复制最新链接。

## 注意事项

- 目前青马易战站点所使用的域名为 `sdyb.fjhdrs.com` ，若今后发生变更，请自行修改程序中对应部分（授权页域名常量位于 `config.py`）。
- decrypt 函数中固定了解密所使用的密钥，此固定密钥由青马易战网页的JS文件中获取，在未来有变动的可能性。若密钥发生变更，可自行通过调试网页JS重新获取。
- 本地题库为程序同目录下的 `tiku.json`，已内置科目7（毛概）、8（思政）、9（马原）、10（近现代史）、12（习概）、173（竞赛）的部分题目。题目按科目分组（`subjects` → 科目ID → 题目数组），每题包含 `question`（题目）、`options`（选项文本）、`answer`（正确选项字母）、`answer_text`（正确答案文本，未知时为 `null`）四个字段，可以自行补充，亦可在答题工具运行过程中由工具自动完成填充。
- 程序运行时会在同目录生成 `qingmakiller.log` 日志文件（超过 10MB 自动轮转），遇到异常时可通过该文件定位问题。  
