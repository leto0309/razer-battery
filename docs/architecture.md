# 架构

代码、测试和脚本分离；统一 verify/build/package 接口，技术栈由 .ai-factory.json 选择。

| 模块 | 职责 | 依赖 Windows |
|---|---|---|
| `protocol.py` | 构造请求、校验和、解析回复、电量换算；无 I/O | 否 |
| `device.py` | 发送命令并在“忙”时重试；读取电量和充电状态；选择已连接的鼠标 | 只有 `read_connected_mouse` |
| `hid_win.py` | 枚举 HID 集合，以 0 访问权限打开，收发 Feature Report | 是 |
| `display.py` | 文本、颜色、字形居中与上色；CLI 和托盘共用 | 否 |
| `cli.py` | 参数解析、退出码、JSON 输出 | 否（延迟导入） |
| `detach.py` | 决定托盘是否以及如何以无控制台方式重新启动自己 | 否 |
| `tray.py` | 隐藏窗口、托盘图标、定时器、右键菜单、单实例互斥量；有控制台时重新启动为后台进程 | 是 |

Windows 模块只在运行时导入，所以测试和 `app.py --self-test` 能在 Linux CI 上运行。
`device.query` 接收任何实现了 `send`/`receive` 的对象，测试用模拟鼠标代替真实设备。
托盘先在 2 倍大小的画布上绘制文字，测量字形边界后再居中，不依赖字体的行距。
