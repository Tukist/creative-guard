# Creative Guard

Windows 下持续监控并自动杀掉 Adobe Creative Cloud 后台进程的小工具。

开机自启，全程无窗口后台运行；按 `Ctrl + Alt + \`` 随时开启或暂停监控。

## 背景

Adobe Creative Cloud 装完后会常驻一堆后台进程，任务管理器里显示为：

| exe 名 | 描述（Description） |
|---|---|
| Adobe Desktop Service | Creative Cloud Core Service |
| CCXProcess | Creative Cloud Content Manager |
| AdobeIPCBroker | Creative Cloud Interprocess Service |
| CCLibrary | Creative Cloud Libraries Synchronizer |
| CoreSync | Adobe Content Synchronizer |

这些进程**吃内存、常驻开机自启**，而且 exe 名里根本没有 "creative" 字样——所以本工具按**进程描述**匹配，而不是按 exe 名。

## 功能

- 每 3 秒扫描一次，杀掉描述含 `Creative` 的进程
- 全局热键 `Ctrl + Alt + \`` 开启 / 关闭监控（程序不退出）
  - 高音两声 = 已开启，低音一声 = 已关闭
- 开机自动启动，无窗口（`pythonw.exe`）
- 日志写到 `creative_guard.log`

## 文件和用法

### `creative_guard.py` —— 常驻热键版（推荐）

```bash
# 前台运行（能看到日志输出）
python creative_guard.py

# 无窗口后台运行
pythonw creative_guard.py
```

启动后默认处于「监控开启」状态。要彻底退出，在任务管理器里结束 `pythonw.exe`。

### `kill_creative.py` —— 命令行版

只做监控和杀进程，没有热键，适合临时跑：

```bash
python kill_creative.py        # 默认每 5 秒检查一次
python kill_creative.py 2      # 每 2 秒检查一次
```

`Ctrl+C` 退出。

## 开机自启

启动文件夹里放一个指向 `pythonw.exe` 的快捷方式即可：

- 按 `Win + R`，输入 `shell:startup`，回车
- 右键 → 新建 → 快捷方式
- 目标填：`D:\anaconda3\pythonw.exe "D:\pythoncode\creative-guard\creative_guard.py"`（路径换成你自己的）
- 起始位置填脚本所在目录
- 运行方式选「最小化」

也可以直接用 PowerShell 生成：

```powershell
$startup = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\CreativeGuard.lnk"
$W = New-Object -ComObject WScript.Shell
$S = $W.CreateShortcut($startup)
$S.TargetPath = "D:\anaconda3\pythonw.exe"
$S.Arguments = [char]34 + "D:\pythoncode\creative-guard\creative_guard.py" + [char]34
$S.WorkingDirectory = "D:\pythoncode\creative-guard"
$S.WindowStyle = 7
$S.Save()
```

## 依赖

- Python 3.7+（只用标准库：`ctypes` / `subprocess` / `logging` / `winsound`）
- Windows（依赖 Win32 API 的全局热键和 PowerShell）

## 注意

- 会**影响 Adobe 软件正常使用**：正在修图 / 剪视频时后台组件会被反复杀掉。需要临时用 Adobe 时按一次热键关闭监控即可。
- 部分 Adobe 进程有守护机制，被杀后会自动重启，本工具会持续压制。
- 如果 `Ctrl + Alt + \`` 注册失败（被其他软件占用），日志里会有记录，监控本身仍照常运行。
- 仅适用于你自己的电脑；请勿用于绕过软件授权。
