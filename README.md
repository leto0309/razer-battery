# razer-battery

在 Windows 上读取 **Razer DeathAdder V3 Pro** 无线鼠标的电量，支持命令行输出和系统托盘数字图标。
只用 Python 标准库（ctypes 调用 `hid.dll` 等系统 DLL），不需要安装 Razer Synapse，和 Synapse 同时运行也没问题。

> 本项目与 Razer Inc. 无关，也未经其认可。“Razer”和“DeathAdder”是 Razer 的商标。

## 支持的设备

| 设备 | VID:PID | 状态 |
|---|---|---|
| DeathAdder V3 Pro + 2.4G 接收器 | `1532:00B7` | 已在实机验证 |
| DeathAdder V3 Pro 有线连接 | `1532:00B6` | 协议相同，未实机验证 |

其他雷蛇鼠标可能使用不同的事务 ID 或 PID，需要在 `src/razer_battery/device.py` 里补充并实测。

## 使用

需要 Windows 10/11 和 Python 3.11+。

```powershell
python app.py              # Razer DeathAdder V3 Pro (wireless): 67%（未充电）
python app.py --json       # {"model": "...", "percent": 67, "charging": false}
pythonw app.py --tray      # 托盘图标，默认每 60 秒刷新
python app.py --tray --interval 30
```

退出码：`0` 成功，`1` 非 Windows，`2` 未找到设备，`3` 读取失败（鼠标休眠、超时等）。

托盘图标直接显示电量数字：
- 电量 ≤ 20% 显示红色，充电时显示绿色，读取失败显示“?”。
- 鼠标悬停可以看到详细信息；左键单击立即刷新；右键菜单有“立即刷新”和“退出”。
- 同一时间只运行一个托盘实例。

**开机自启**：按 `Win+R` 输入 `shell:startup`，在打开的文件夹里新建快捷方式，
目标填 `pythonw.exe "<项目路径>\app.py" --tray`；如果用打包好的 exe，目标填 `"<路径>\razer-battery.exe" --tray`。

## 打包为 exe

用 PowerShell 7 运行 `./scripts/package.ps1`，会先跑测试，再用 PyInstaller 生成 `dist/razer-battery.exe`。
exe 不需要安装 Python。`--tray` 会在后台以无控制台的方式重新启动自己：在终端里运行会立即返回，
双击快捷方式也不会留下控制台窗口。

## 工作原理

雷蛇鼠标不使用标准的 HID 电量字段，而是通过 90 字节的 Feature Report 私有协议通信。
鼠标的 `MI_00` 集合由系统独占，只能以 0 访问权限打开，但仍然可以收发 Feature Report。

| 字节 | 含义 |
|---|---|
| 0 | 状态（请求为 0；回复 2 成功、1 忙、3 失败、4 超时、5 不支持） |
| 1 | 事务 ID，DeathAdder V3 Pro 为 `0x1F` |
| 2–3 | 剩余包数 |
| 4 | 协议类型 |
| 5 | 数据长度 |
| 6–7 | 命令类 / 命令 ID：电量 `07 80`，充电状态 `07 84` |
| 8–87 | 参数；回复的第 9 字节是 0–255 的电量值或充电标志 |
| 88 | 第 2–87 字节的异或校验 |

协议格式参考了 [OpenRazer](https://github.com/openrazer/openrazer) 公开的逆向研究，
本项目代码是独立编写的。

## 开发

PowerShell 7：`./scripts/verify.ps1` 运行测试、ruff 和自检，`./scripts/build.ps1` 构建，
`./scripts/package.ps1` 先验证再生成 `dist/` 产物。外部环境先执行 `python -m pip install -r requirements-dev.txt`。
测试不依赖硬件，Linux CI 也能运行；需求与验收条件见 [docs/requirements.md](docs/requirements.md)。

## 许可证

[MIT](LICENSE)
