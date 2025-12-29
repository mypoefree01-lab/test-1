import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from flask import Flask, after_this_request, render_template_string, request, send_file

from compress_pdf import compress_pdf, _human_size


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024 * 1024  # 2 GB


HTML_TEMPLATE = """
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>PDF 压缩工具</title>
    <style>
      body { font-family: Arial, sans-serif; max-width: 760px; margin: 40px auto; padding: 0 16px; color: #222; }
      h1 { margin-bottom: 0.5em; }
      form { border: 1px solid #ddd; padding: 16px; border-radius: 6px; background: #fafafa; }
      label { display: block; margin: 12px 0 6px; font-weight: 600; }
      input[type="number"], input[type="file"] { width: 100%; }
      .error { color: #c0392b; margin-top: 12px; font-weight: 600; }
      .hint { color: #555; font-size: 0.95em; }
      button { margin-top: 16px; padding: 10px 16px; font-size: 1em; cursor: pointer; }
    </style>
  </head>
  <body>
    <h1>PDF 压缩工具</h1>
    <p class="hint">上传 PDF（最大 2GB），压缩到目标大小（默认 100MB）。</p>
    <form action="/compress" method="post" enctype="multipart/form-data">
      <label for="pdf">选择 PDF 文件：</label>
      <input id="pdf" name="pdf" type="file" accept="application/pdf" required />
      <div class="hint">文件不会持久保存，仅用于本次压缩。</div>

      <label for="target_mb">目标大小 (MB)：</label>
      <input id="target_mb" name="target_mb" type="number" value="{{ target_mb }}" min="1" step="1" required />
      <div class="hint">默认 100MB，可根据需要调整。数值越低压缩越激进。</div>

      <button type="submit">开始压缩</button>

      {% if error %}
      <div class="error">错误：{{ error }}</div>
      {% endif %}
    </form>
  </body>
</html>
"""


def _render_form(error: Optional[str] = None, target_mb: int = 100):
    return render_template_string(HTML_TEMPLATE, error=error, target_mb=target_mb)


@app.route("/", methods=["GET"])
def index():
    return _render_form()


@app.route("/compress", methods=["POST"])
def compress_route():
    file = request.files.get("pdf")
    target_mb_raw = request.form.get("target_mb", "100")

    try:
        target_mb = int(target_mb_raw)
        if target_mb <= 0:
            raise ValueError
    except ValueError:
        return _render_form("目标大小必须是正整数。", target_mb=100)

    if not file or file.filename == "":
        return _render_form("请选择一个 PDF 文件。", target_mb=target_mb)

    original_name = Path(file.filename).name
    download_name = f"{Path(original_name).stem}-compressed.pdf"

    temp_dir = tempfile.mkdtemp()

    @after_this_request
    def cleanup(response):
        shutil.rmtree(temp_dir, ignore_errors=True)
        return response

    input_path = os.path.join(temp_dir, "input.pdf")
    output_path = os.path.join(temp_dir, "output.pdf")

    try:
        file.save(input_path)
    except Exception:
        return _render_form("无法保存上传的文件。", target_mb=target_mb)

    try:
        success, _ = compress_pdf(
            input_path=input_path,
            output_path=output_path,
            target_mb=target_mb,
            max_input_mb=2000,
        )
    except Exception as exc:
        return _render_form(f"压缩失败：{exc}", target_mb=target_mb)

    if not os.path.exists(output_path):
        return _render_form("未能生成压缩后的文件。", target_mb=target_mb)

    output_size = os.path.getsize(output_path)
    headers = {"X-Output-Size": _human_size(output_size)}
    status_code = 200 if success else 206

    return send_file(
        output_path,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=download_name,
        max_age=0,
        conditional=False,
        etag=False,
        last_modified=None,
    ), status_code, headers


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)
