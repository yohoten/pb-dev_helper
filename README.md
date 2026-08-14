# PB Dev Helper

> PowerBuilder 开发辅助工具 – 浏览 PBL 文件，导出/导入 SR，支持现代编辑工作流

![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)

## ✨ 特性

- 📁 **浏览与导入/出** ：加载 PBL 库，快速筛选，批量导出为 SR 文件（.srd、.srw），将 SR 文件批量导回 PBL 库

### 环境要求
- 主程序：Python 3.8+（64位）
- Worker：Python 3.8+（32位）– 用于调用 ORCA API
- Windows 操作系统 + PowerBuilder 10 或 2025 安装

### 安装与运行
```bash
git clone https://github.com/your-repo/pb-dev-helper.git
cd pb-dev-helper
python main.py
```

### 首次配置

1. 打开 **Settings** 标签页
2. 在 **PB Paths** 中点击 **Auto Detect** 自动识别 IDE 和 Runtime 路径
3. 在 **Worker** 标签页选择 32 位 Python 可执行文件路径（如 `C:\Python38-32\python.exe`）
4. 点击 **Save All Settings**，然后 **Test Connection** 验证
5. 切换到 **Browse** 标签页，加载 PBL 文件并开始导出

## 📁 项目结构

text

```
pb-dev-helper/
├── gui/                 # Tkinter 界面组件
├── models/              # 配置与枚举
├── orca/                # JSON-RPC 客户端与会话管理
├── scripts/             # 32-bit Worker 脚本
├── tools/pbpicker/      # 集成 PBPicker 工具
├── main.py              # 入口
└── pbdev_config.json    # 自动生成的配置文件
```

## ⚙️ 配置

`pbdev_config.json` 自动保存以下设置（示例）：

json

```
{
  "pb_ide_path": "C:\\Program Files (x86)\\Appeon\\PowerBuilder 25.0\\IDE",
  "pb_runtime_path": "C:\\Program Files (x86)\\Appeon\\Common\\PowerBuilder\\Runtime 25.0.0.3683",
  "export_encoding": 1,
  "export_headers": true
}
```

## 🛠️ 常见问题

| 问题              | 解决方法                                                     |
| :---------------- | :----------------------------------------------------------- |
| Worker 连接失败   | 检查 32 位 Python 路径是否正确，IDE 目录是否包含 ORCA DLL    |
| 导出中文乱码      | 在导出设置中切换编码（ANSI/UTF-8）与 PB 版本一致             |
| PBPicker 无法启动 | 检查 `tools/pbpicker/pb_picker.exe` 是否存在，临时关闭杀毒软件 |

## 🙌 致谢

- PowerBuilder ORCA API 
- PBPicker 工具
