这是我用 Codex 测试的第一个项目。

## PDF 压缩工具

这个仓库提供了一个命令行工具 `compress_pdf.py`，用于在尽量保持内容完整的前提下压缩 PDF 文件。支持最大 2GB 输入，目标可设置为 100MB（默认）。

### 命令行使用

1. 安装依赖：

   ```bash
   pip install -r requirements.txt
   ```

2. 运行压缩：

   ```bash
   python compress_pdf.py 输入文件.pdf 输出文件.pdf --target-mb 100
   ```

   - `--target-mb`：期望的输出大小（MB），默认 100MB。
   - `--max-input-mb`：允许的最大输入大小（MB），默认 2000MB。

工具会多次尝试不同的图像质量和分辨率组合，并在每次尝试后保存结果，直到满足目标大小或用尽尝试次数。最终输出的文件路径就是你提供的目标路径。

### 网页工具

现在也提供了一个简单的网页版本（基于 Flask）：

```bash
python web_app.py
```

然后在浏览器打开 <http://localhost:8000>，上传 PDF 并设置目标大小（默认 100MB）。上传文件大小上限为 2GB，压缩后的文件会以附件形式下载。
