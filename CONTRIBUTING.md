# 贡献指南

欢迎通过 Issue 报告问题、提出建议，或提交 Pull Request。

## 开发流程

1. Fork 项目并创建功能分支。
2. 按 README 建立虚拟环境，安装 `requirements-dev.txt`。
3. 使用独立的数据目录测试，避免改动自己的日常课表：

```powershell
$env:COURSEDESK_DATA_DIR = "$PWD\build\dev-profile"
$env:COURSEDESK_NO_OS_ACTIONS = '1'
.\.venv\Scripts\python.exe course_assistant.py
```

`COURSEDESK_NO_OS_ACTIONS=1` 关闭测试时的系统通知和任务注册，退出终端后环境变量即失效。运行 `python -m unittest discover -s tests -v`，并对涉及窗口、OCR、提醒的修改做 Windows 实机检查。

## 提交要求

说明修改目的、复现步骤和测试结果；新增行为应带相应测试。保持中文界面和本地优先的数据处理。不要提交自己的课表、截图、备份、日志、密钥或打包运行环境；测试和演示必须使用虚构数据。依赖变更需同步版本与许可证声明。

提交贡献即表示你拥有提交内容的权利，并同意以本项目 MIT 许可证发布贡献。第三方内容必须保留原有声明。
