# 桌面基础批次验证记录

验证日期：2026-11-03。范围：Windows x64、共用研究工作台、无需模型的基线实验。

状态：开发构建和打包后端流程通过；安装包已生成，正式发布验收尚未完成。

本记录仅覆盖桌面基础批次产物。后续工作区和生命周期开发验证分别见 [实施计划](../../specs/desktop-research-workspace/tasks.md) 与 [第五批 A 验收](../../specs/desktop-research-workspace/validation-5a.md)。下列测试数量及安装包状态不代表最新源码。

主窗口研究位置恢复的开发构建及验证见 [第五批 B 验收](../../specs/desktop-research-workspace/validation-5b.md)。

JSON 原生导出与共用文件写入见 [第五批 C 验收](../../specs/desktop-research-workspace/validation-5c.md)；保存后文件定位见 [第五批 D 验收](../../specs/desktop-research-workspace/validation-5d.md)。

主窗口布局恢复及最新开发构建验证见 [第五批 E 验收](../../specs/desktop-research-workspace/validation-5e.md)。

## 已完成

| 检查 | 结果 |
| --- | --- |
| Python 回归测试 | 643 通过、2 跳过 |
| 前端单元测试 | 34 个文件、123 项通过 |
| 静态检查 | Python Ruff、mypy（111 个文件），前端 lint、类型检查通过 |
| Rust | Cargo check、Clippy 通过 |
| 发布构建 | 前端、PyInstaller 后端、Tauri Windows x64 和 NSIS 安装包构建成功 |
| 打包后端烟测 | 中文及空格临时路径、独立 config.env 加载、未认证请求拒绝、两场基线对局、比较、引用结论、报告导出通过 |
| 后端退出与重启 | 关闭父进程管道后正常退出，重新启动后结论记录保持一致 |
| 本机原生窗口 | 打开工作台、重复启动保持单实例、取消退出后继续使用通过 |

烟测使用实际打包的后端可执行文件和隔离临时目录，不依赖源码工作目录，不读取用户研究数据，不调用模型。静态资源和 WebSocket 会话边界另有单元测试。

本次最终安装包位于 `desktop/.build/final/release/bundle/nsis/CardLab_0.1.0_x64-setup.exe`。构建时设置了独立 `CARGO_TARGET_DIR`，避免覆盖正在使用的开发应用；默认构建路径见 [开发文档](README.md)。构建产物不纳入 Git。

## 发布前仍需验收

- 无 Python、Node、源码的干净 Windows 系统：安装、启动、卸载保留数据、重新安装。
- 缺少 WebView2 时的联网安装流程。
- 最终宿主的同源证据窗口、确认退出后进程树清理、宿主异常退出及服务启动失败提示。
- 发布签名。本次产物是未签名的开发安装包。

本机窗口检查使用同批较早的宿主构建；最后新增的证据窗口处理已经编译，但尚未完成原生交互验收。为避免打断用户正在使用的应用，本批未执行安装覆盖和强制退出测试。以上待验收项不能由编译或后端烟测替代。
