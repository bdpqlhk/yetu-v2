# 野兔 v2 · 手机调试工具箱（PyQt6 版）

面向测试 / 产品的桌面小工具:快速查看安卓 / 鸿蒙设备信息、已装应用、网络状态,
设置全局代理,安装 APK / HAP 测试包,内置「配置助手」帮手机扫码配抓包代理。
**自带 `adb` / `hdc`**,不依赖用户机器预装环境。

> 📖 文档:[使用说明](docs/使用说明.md) · [技术实现文档](docs/技术实现文档.md)

- 版本: 2.0.0
- 界面: **PyQt6**(v1 为 Tkinter,本版重写),深色开发者工具风格(**样式参考 TCode GUI**)
- 打包: PyInstaller,`sh build.sh` → `dist/野兔v2.app`(macOS)

---

## 一、与 v1 的差异

| | v1 | v2 |
|---|---|---|
| GUI 框架 | Tkinter(ttk) | **PyQt6** |
| 视觉风格 | 系统原生 | 深色开发者工具风格(参考 TCode GUI):顶栏品牌区、蓝色主色 `#2e70ef`、Tab 下划线、底部「命令日志」Dock、状态栏忙碌指示 |
| 线程模型 | `threading` + `after()` | **QThread 信号槽**(Worker / InstallWorker) |
| 命令日志 | 无 | 每条 adb/hdc 操作写入底部 Dock,带时间戳 |
| 核心逻辑 | `yetu/core/*` | **原样复用**(env / adb / device 三模块零改动) |

## 二、项目结构

```
main.py                    入口(--selftest 自检 / --screenshot 截图 / 启动 GUI)
野兔v2.spec                PyInstaller 打包配置(内置 tools/,图标)
build.sh                   一键打包
yetu/
├── core/                  ← 复用 v1,零改动
│   ├── env.py             定位内置 adb/hdc(打包态/开发态/PATH 回退)
│   ├── adb.py             Adb / Hdc 连接器(命令差异收敛在这一层)
│   └── device.py          设备抽象:信息/应用/网络/代理/安装
└── gui/
    ├── theme.py           深色 QSS + 配色常量(参考 tcode)
    ├── workers.py         Worker(QThread 后台执行) / InstallWorker(流式安装)
    ├── widgets.py         通用件:只读表格 / 键值表单 / 状态徽标 / 等宽字体
    ├── main_window.py     主窗口:header + 设备栏 + Tabs + 命令日志 Dock + 状态栏
    └── panels/
        ├── base.py        面板基类(run_async 统一后台执行)
        ├── device_panel.py   手机信息
        ├── apps_panel.py     已装应用(搜索过滤 / 仅第三方)
        ├── network_panel.py  网络信息
        ├── proxy_panel.py    全局代理
        └── install_panel.py  安装应用(APK / HAP 流式日志)
```

### 线程模型

Qt 控件只能在主线程操作,adb/hdc 命令动辄数秒:

- `Worker(QThread)`:执行任意函数,结果(或异常实例)经 `done` 信号回主线程。
- `InstallWorker(QThread)`:安装 APK/HAP,每行输出经 `line` 信号实时回传。
- `PanelBase.run_async(fn, on_done, busy_btn, busy_text, cmd)`:
  统一封装 —— 执行期间禁用按钮防重复点击(结束还原文字)、状态栏显示 ⏳、
  操作记录写入底部命令日志。

## 三、开发与打包

```bash
pip3 install -r requirements.txt   # PyQt6 + PyInstaller
python3 main.py                    # 开发运行
python3 main.py --selftest         # 自检(不弹界面):内置工具/面板/设备
python3 main.py --smoke            # 无头自检:配置助手起服务 -> 请求配置页 -> 停止
python3 main.py --screenshot s.png # 无头渲染截图(offscreen)
sh build.sh                        # 打包 → dist/野兔v2.app(含 frozen 冒烟)
```

打包要点:

- `野兔v2.spec` 里 `datas`:把 `tools/`(adb/hdc 及其库)与配置助手页面
  `yetu/core/assistant_page.html` 一并打进包;工具路径由 `yetu/core/env.py` 定位。
- macOS 产物 adhoc 签名,本机直接可跑;分发到别的机器如遇 Gatekeeper 拦截:
  `xattr -dr com.apple.quarantine dist/野兔v2.app`。

## 四、使用说明

1. 手机开启 **开发者选项 + USB 调试**,数据线连接电脑(安卓首次连接需在手机上授权)。
2. 顶部设备栏选择目标设备(同一台鸿蒙手机可能同时出现「安卓 / 鸿蒙」两条:
   装 `.apk` 选安卓条目,装 `.hap` 选鸿蒙条目);`↻ 刷新设备` 或按 `F5` 重新扫描。
3. 六个 Tab:

| Tab | 功能 |
|---|---|
| 手机信息 | 型号/厂商/系统版本/API 级别/序列号/ABI/分辨率/密度/电池 |
| 已装应用 | 应用列表,支持包名搜索、仅第三方开关;版本号对前 60 个包查询 |
| 网络信息 | 接口地址 / DNS·代理属性 / WiFi / 当前全局代理 |
| 全局代理 | 读取/设置/清除全局代理(Charles、mitmproxy 抓包) |
| 安装应用 | 选 `.apk` / `.hap` → 开始安装,下方流式显示安装输出 |
| 配置助手 | 起一个二维码配置页,手机扫码后复制代理地址、按系统查看设置步骤、确认抓包服务在线 |

### 配置助手(手机免手输抓包代理)

「全局代理」走 adb/hdc 直改设备;抓 **Wi-Fi 通道**或手上没线时,用「配置助手」:

1. 电脑上启动 Charles / mitmproxy(勾选允许局域网连接),在面板里填「代理端口」
   (Charles 默认 8888),点「启动助手」
2. 手机扫右侧二维码(或浏览器输入显示的地址)打开配置页
3. 页面自动识别 Android / iPhone 显示对应设置步骤,代理地址一键复制;
   顶部徽标实时显示电脑抓包端口是否在线(5 秒自动刷新)
4. 页面零外部资源,局域网内秒开;助手跑在独立线程,关窗自动回收

## 五、扩展开发

- 新增面板:`yetu/gui/panels/` 下新建文件继承 `PanelBase`,加入 `panels/__init__.py::PANELS` 即可。
- 新增设备能力:优先加在 `yetu/core/device.py` / `adb.py`,面板只管调用与展示。
- 更新内置工具:替换 `tools/adb/adb`、`tools/hdc/hdc`,重新 `sh build.sh`。
