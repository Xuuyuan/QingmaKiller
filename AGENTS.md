# AGENTS.md — QingmaKiller

面向 AI 编码代理的项目约束与经验。用户可见文档在 `README.md`, 此处只记录代理必须遵守的规则和已踩过的坑。

## 项目速览

- 青马易战自动答题工具, Windows 优先的 CLI 程序, 通过 GitHub Releases 以 zip 分发
- 源码为扁平布局, 顶层模块即全部代码: api / auth / bank / cli / config / logger / main / paths / solver / tiku / utils / winproc
- 外部依赖程序: `tikuAdapter.exe`(第三方 Go 搜题服务, 42MB, 仓库自带、独立版本迭代, 监听 localhost:8060), 由主程序自动拉起/关闭
- 运行时产物均在程序同目录: `session.json`(会话缓存), `tiku.json`(题库, 可写、运行中自动补充), `qingmakiller.log`(日志), `tiku.db`(tikuAdapter 自己的 SQLite 缓存, **不是本项目的文件**, 勿提交勿引用)
- 测试: unittest, `python -m unittest discover -s tests`

## 硬性约束

1. **路径逻辑必须兼容打包场景**: 程序以 PyInstaller onefile 发布, `paths.py#get_app_dir` 已处理 `sys.frozen`(返回 exe 所在目录)。任何新增的文件读写路径必须经 `get_app_dir()` 定位, 禁止依赖源码目录相对路径。
2. **外部服务异常只降级、不炸轮次**: tikuAdapter 等外部依赖的任何异常(连接失败/超时/响应为空或畸形)必须捕获并降级为"跳过本题", 参照 `tiku.py#search` 的兜底写法。主循环(main.py)对未处理异常有"连续 3 次即退出"机制, 不允许让可恢复故障触发它。
3. **子进程必须绑定 Job 守护**: 本程序拉起的子进程必须调用 `winproc.py#bind_to_parent`, 否则用户直接关闭终端窗口(点叉)时会残留孤儿进程(Job Object 内核级守护, 比 CTRL_CLOSE_EVENT 信号拦截可靠)。新增子进程一律复用该函数。
4. **新增顶层 .py 模块必须同步 `pyproject.toml` 的 `py-modules` 清单**: setuptools 会拒绝 flat 布局多顶层模块的自动发现, 漏加会导致 `pip install .` 静默漏装该模块或构建失败(已踩坑)。
5. **提交遵循 Conventional Commits + 中文描述**(feat/fix/perf/docs/build/chore/refactor), 小步提交。

## 发行包与构建

- 构建: `pip install . pyinstaller && python scripts/package_release.py`(脚本需 Python 3.11+; CI 构建环境用 3.13)
- 包内固定 4 个文件: `QingmaKiller.exe` + `tikuAdapter.exe` + `tiku.json` + `LICENSE`(MIT 要求分发副本附带许可证)
- 打包参数约定: onefile、不用 UPX(杀软误报放大器)、console 程序、无图标; 版本号从 pyproject.toml 读取, 单一来源
- 打包脚本会把发行文件铺开到 `dist/` 以便直接运行验收; 若 dist 内程序被占用(如 zip 已打开), 脚本会明确报错
- 禁止入库或入包的运行时残留: `session.json`、`*.log`、`tiku.db`、`tiku.json.tmp`、`tiku.json.broken`、`build/`、`dist/`、`*.spec`(.gitignore 已覆盖)
- `tiku.json` 缺失时程序可空题库启动(全靠在线题库兜底), 但对外承诺"已内置科目 7/8/9/10/12/173 题目", 发行包必须携带

## 发版流程

1. 更新 `pyproject.toml` 版本号, 并重写根目录 `RELEASE_NOTES.md`(用用户视角措辞而非 commit 语言; 必须包含 "v{版本}" 字样, 否则构建时告警)
2. `git push` 后可先 `gh workflow run release.yml` 做构建验证(仅出 artifact, 不发布)
3. 绿灯后打 tag 发布: `git tag -a vX.Y.Z -m "..." && git push origin vX.Y.Z`, CI 自动构建并按 `RELEASE_NOTES.md` 原文发布 Release
4. 若根目录无 `RELEASE_NOTES.md`, CI 回退为自动生成文案(按提交标题、剔除 build/docs/test/ci 类提交), 因此该文件是文案的唯一出口, 发版前必须检查是否已随版本更新

## 已踩过的坑

- GitHub Actions 的 Windows runner 控制台是 cp1252, Python 打印中文会 UnicodeEncodeError → workflow 作业级已设 `PYTHONUTF8: '1'`, 新增 workflow 记得保持
- setuptools 自动发现拒绝 flat 布局多顶层模块, `pip install .` 报 "Multiple top-level modules discovered"(见硬性约束 4)
- dist 内缺少 tikuAdapter.exe 时程序仍可运行(提示后全部跳题、本地题库为空), 易被误判为程序缺陷; 本地验收请用打包脚本铺开的完整 dist
- 站点域名变更意味着旧版 exe 全部不可用(v1.0.0 硬编码旧 IP 的教训): 务必 bump 版本并在 RELEASE_NOTES 置顶强制升级提示; 域名常量在 `config.py`
- 解密密钥与授权页域名等常量集中在 `config.py`, 改动前先读 README 注意事项中对应说明
