# 桌面端开发与交付

第一批面向 Windows x64。现有 Vue 工作台与 Python 研究服务共用一套实现；`desktop/` 仅包含 Tauri 宿主、启动页和安装配置。浏览器开发入口仍使用现有 Vite/FastAPI 命令，不是独立产品实现。

## 构建

维护者需要 Node、Rust MSVC 工具链、Visual Studio C++ 工具、Windows SDK，以及项目的 Python 3.11+ 虚拟环境。最终用户无需安装这些开发工具。

在仓库根目录执行：

```powershell
npm --prefix web ci
npm --prefix desktop ci
server/.venv/Scripts/python.exe -m pip install -r scripts/desktop/requirements-build.txt
./scripts/desktop/build.ps1
```

Python 应用依赖按 `server/poetry.lock` 安装。基础包不包含训练依赖与模型权重。`-BackendOnly` 只生成后端；构建脚本先验证并构建现有前端，再打包后端，最后构建 NSIS 安装包。生成物在 `desktop/src-tauri/target/release/bundle/nsis/`，不提交 Git。构建环境须能访问 npm、crates.io 及安装器工具下载源。

需要避开正在运行的开发产物时，可在当前 PowerShell 会话设置 `$env:CARGO_TARGET_DIR = Join-Path (Get-Location) 'desktop/.build/final'` 再构建；安装包相应生成在该目录的 `release/bundle/nsis/` 下。

应用图标由 web/public/logo.png 生成；直接运行开发宿主前可执行 `npm --prefix desktop exec -- tauri icon web/public/logo.png --output desktop/src-tauri/icons`。

后端打包完成后，`npm --prefix desktop run dev` 可启动桌面宿主；修改 Python 或前端代码后必须重新执行后端打包，不能自动切换到源码服务。Cargo.lock 与 package-lock.json 纳入版本控制。

## 使用与范围

应用启动后自动启动独立后端并进入同一工作台。可以创建三个不调用模型的基线选手（first / heuristic / random），创建实验并开始对局，再审查决策、比较和导出结论。应用不会自动运行实验或调用模型。

数据默认位于当前用户 LocalAppData 下的 `com.cardlab.workbench/research`，日志在同级 `logs/backend.log`。实际路径以应用设置中显示的路径为准。源码仓库的 `.env` 与 `data/` 不用于桌面应用。可选模型配置文件为 research/config.env；设置页显示其完整路径，修改后需重启。基线实验不需要该文件。安装目录与数据目录分离，升级不复制或删除研究数据。

关闭主窗口时会先检查所有研究窗口：保存编辑中的研究草稿，确认没有未完成的 Prompt A/B 设计，再询问是否退出。保存失败、冲突或窗口未响应时取消关闭并保留输入；请在原编辑器处理后重试。关闭证据窗口只保存并关闭自身。确认退出会停止服务，尚未完成的任务在下次启动时由现有恢复逻辑标记为中断。

首次运行可在「创建实验」选择「离线试跑一局」，保存三席一局的固定发牌计划，再到运行页确认开局。「自选席位」允许在当前表单中添加选手，查看缺少的配置项和本机配置文件路径。需要验证连接时可主动读取所选模型目录；修改配置文件后重启桌面应用。

普通未提交创建表单不会自动成为研究草稿；强制结束或断电也无法替代保存确认。尚不支持托盘继续运行、对局中途续跑、自动更新、凭据管理和可选训练组件安装。云模型凭据配置的完整桌面交互属于后续批次；本机验收采用离线数据。

正常关闭时会保存主窗口的最后研究位置、窗口位置、普通窗口大小和最大化状态，下次打开继续原研究、运行、比较或决策审查；比较的样本和时间线位置沿用当前地址中的定位信息。进入设置等页面不会替换当前会话已记录的研究位置，主动回到研究首页则下次从首页开始。独立证据窗口不会覆盖主窗口位置，也不会自动重开。滚动位置、临时面板和全屏模式暂不恢复。

研究位置和主窗口布局共用应用数据目录的 `workspace.json`，只在正常关闭准备阶段一起写入。读取失败会提示并允许继续使用，写入失败会取消关闭；它不影响已经保存在研究数据库中的草稿。恢复对象已被删除时，可从原页面返回研究首页继续选择。最小化不会成为下次启动状态；保存位置完全落在当前屏幕外时，由 Windows 将窗口调整到可见位置。

JSON 导出使用系统“另存为”选择文件位置，适用于研究结论、比较快照、实验包、选手配置和草稿副本。只有写入完成后才显示已保存；取消不会导出，失败可重新选择可写位置。单次桌面 JSON 上限为 32 MiB；大型训练数据导出仍由原数据工具处理。导出期间请先完成或取消保存，再关闭应用。浏览器入口只提示下载已交给浏览器。

保存成功提示提供「在文件夹中显示」，由系统文件管理器定位刚保存的文件，不打开文件内容。提示保留至定位成功、手动关闭或本窗口下一次保存成功；取消下一次导出不会移除原提示。若文件被移动/删除或定位失败，可在恢复文件位置、结束当前操作后重试。该入口只针对本窗口最近一次保存，不提供跨会话文件历史。

安装器以当前用户权限安装；缺少 WebView2 时使用官方引导程序联网安装。首批不宣称离线安装和跨平台支持。未配置发布签名的开发安装包不能作为已签名正式版本发布。

## 发布验收

- 在没有 Python、Node 和源码的 Windows 环境完成安装与启动。
- 创建基线选手，完成对局、保存比较及结论、导出报告。
- 重复打开只聚焦已有窗口，不启动第二个后端。
- 取消退出保持运行，确认退出后不遗留子进程。
- 服务崩溃、启动超时和缺失资源有明确错误。
- 验证中文和带空格路径、卸载保留研究数据、重新安装后仍可读取。
- 在缺少 WebView2 的干净系统检查安装器行为。

本机编译和打包烟测不能替代干净系统验收。实际完成状态见 [验证记录](validation.md)。

桌面研究工作区的改造另见 [设计与分批计划](../../specs/desktop-research-workspace/tasks.md)。当前生命周期工作重建开发宿主和其打包后端用于本机隔离验收；基础批次的 NSIS 安装包不代表最新源码。完整状态见 [第五批 A 验收](../../specs/desktop-research-workspace/validation-5a.md)。

主窗口位置恢复另见 [第五批 B 验收](../../specs/desktop-research-workspace/validation-5b.md)；开发产物的验证不代表发布安装包已更新。

JSON 原生导出及共用文件写入见 [第五批 C 验收](../../specs/desktop-research-workspace/validation-5c.md)，包含系统另存为取消、中文文件名保存、文件读回和保存后退出验证。

保存后文件定位与失败重试见 [第五批 D 验收](../../specs/desktop-research-workspace/validation-5d.md)，包含最终开发宿主的中文文件名选择、键盘重试和文件管理器选中检查。

主窗口布局恢复及最新开发构建见 [第五批 E 验收](../../specs/desktop-research-workspace/validation-5e.md)，包含移动与缩放、最大化重开和完全离屏位置调整；多实体显示器与混合 DPI 仍待专项验证。

## 打包产物烟测

斗地主研究统计按席位所在阵营判胜。席位胜率的分母、快照口径和验收范围见[研究指标说明](../../specs/desktop-research-workspace/seat-results.md)。

```powershell
server/.venv/Scripts/python.exe scripts/desktop/smoke.py desktop/src-tauri/backend/cardlab-backend.exe
```

脚本在临时中文/空格路径中运行两场 first 策略基线，禁用 EV 评估以聚焦交付验证；检查会话、比较、引用、报告导出与重启持久性。不读取用户实验数据，不调用外部模型。
