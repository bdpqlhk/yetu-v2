# -*- coding: utf-8 -*-
"""功能面板包:import 即完成注册(main_window 按固定顺序建 Tab)。"""
from .device_panel import DevicePanel
from .apps_panel import AppsPanel
from .network_panel import NetworkPanel
from .proxy_panel import ProxyPanel
from .install_panel import InstallPanel
from .assistant_panel import AssistantPanel

PANELS = [DevicePanel, AppsPanel, NetworkPanel, ProxyPanel, InstallPanel,
          AssistantPanel]
