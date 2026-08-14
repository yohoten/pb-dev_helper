- # PBPicker 集成说明

  本目录包含集成的 PBPicker 工具，用于浏览 PowerBuilder 库文件。

  ## 文件列表

  - `pb_picker.exe` - 主程序
  - `pb_picker.dll` - 核心库
  - `pbvm115.dll` - PowerBuilder 虚拟机运行时
  - `pbshr115.dll` - PowerBuilder 共享库
  - `PBCLTRT115.msi` - PowerBuilder 客户端运行时安装程序
  - 支持库：`atl71.dll`、`ClassXP.dll`、`libjcc.dll`、`libjutils.dll`、`msvcp71.dll`、`msvcr71.dll`

  ## 使用方法

  在“浏览与导出”选项卡中，点击 **🔍 PBPicker** 按钮即可自动启动该工具。

  ## 来源

  原始位置：`F:\（8）Desktop\share\pbpicker_4_pb11\`

  ## 注意事项

  - PBPicker 作为外部可执行文件保留，以保持架构清晰
  - 所有依赖项均已包含在此目录中
  - 应用程序会从项目的 tools 目录中加载 PBPicker
