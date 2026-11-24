# mdpath

[![Tests and Markdown links](https://github.com/kunzi4261-lang/mdpath/actions/workflows/check.yml/badge.svg?branch=main)](https://github.com/kunzi4261-lang/mdpath/actions/workflows/check.yml)

**在提交之前，找出 Markdown 里已经失效的本地链接。** 移动文档、重命名数据文件或整理截图后，mdpath 会指出需要修改的文件、行号和目标路径。扫描只访问本地文件系统，运行时只用 Python 标准库。

```text
README.md:3: missing: data/run 01.csv
```

## 快速开始

使用 Python 3.10 或更新版本。克隆仓库后可以直接运行脚本，最后一个参数是要检查的目录。

```sh
git clone https://github.com/kunzi4261-lang/mdpath.git
cd mdpath
python mdpath.py .
```

要亲眼看看失效链接是什么样子，可以运行这个[改名示例](examples/renamed_file.py)。它会在临时目录里重命名一份 CSV，打印上面的诊断，再更新 Markdown 链接并检查一次。

```sh
python examples/renamed_file.py
```

## 安装为命令行工具

在已激活的 Python 虚拟环境中，可以直接安装 [GitHub Release](https://github.com/kunzi4261-lang/mdpath/releases/tag/v0.2.0) 里的 wheel。之后就可以在其他仓库里运行 `mdpath`。

```sh
python -m pip install https://github.com/kunzi4261-lang/mdpath/releases/download/v0.2.0/mdpath-0.2.0-py3-none-any.whl
mdpath ../my-notes
```

从项目源码安装可用 `python -m pip install .`，边修改边运行可用 `python -m pip install -e .`。省略目录参数会检查当前目录。

## 接入脚本与 CI

| 命令 | 适用场景 |
| --- | --- |
| `mdpath .` | 在终端查看失效链接和汇总 |
| `mdpath . --json` | 读取文档数 `files`、本地链接数 `links`、问题列表 `broken` 和扫描错误 `errors` |
| `mdpath . --github` | 在 GitHub Actions 中把失效链接标到对应的文件与行 |

三种输出使用相同的退出码。全部通过返回 `0`，发现失效或越界的链接返回 `1`。参数错误或未能完成扫描时返回 `2`。本仓库在推送和拉取请求中都会运行测试，并用 mdpath 检查自己的文档。[查看工作流](.github/workflows/check.yml)

## 路径如何解析

- **相对路径**从引用所在文档的目录开始查找，如 `../data/results.csv`。以 `/` 开头的路径从扫描根目录开始查找，如 `/README.md`。解析后指向根目录外的目标记为 `outside-root`。
- **含空格、中文的文件名**可写成 `![结果](<images/实验 1.png>)`，也可以用 `%20` 编码空格。`guide.md#install` 只检查 `guide.md` 是否存在。
- **扫描范围**包括 UTF-8 编码的 `.md` 和 `.markdown`。遍历时跳过符号链接，以及 `.git`、`node_modules`、`.venv`、`dist` 等目录。外部 URL 和纯页内锚点会跳过。
- **语法范围**包括常用的单行内联链接、图片和引用定义。每条引用定义在定义行检查一次。解析器跳过顶层围栏代码块和单行代码片段。HTML、跨行链接和容器内嵌套围栏超出支持范围。[查看解析器](mdlinks.py)

## 开发与验证

路径检查、输出格式和退出码集中在[命令行实现](mdpath.py)中。[测试](tests/)覆盖链接语法、目录边界、文件读取错误和自动化输出。可以在本地运行整个测试集。

```sh
python -m unittest discover -s tests -v
```
