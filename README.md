## 对原代码修改的地方
- 原代码建议用 `pip install .` 这在我这边会有问题

- 修改setup.py
- 替换`from src.pandora import __version__`
```python
def get_version():
	with open('src/pandora/__init__.py') as f:
		for line in f:
			if line.startswith('__version__'):
				return eval(line.split('=')[-1])

__version__ = get_version()
```
- 使用 `-e` 选项来安装 `pandora` 模块。这将创建一个符号链接，将安装的 `pandora` 模块与源代码目录连接起来，从而使 Python 在运行时加载源代码版本而不是编译后的版本。具体步骤如下：

1. 进入 `pandora` 源代码目录，运行以下命令：

   ```
   pip install -e .
   ```

   这将安装 `pandora` 模块，并使用符号链接连接安装的模块与源代码目录。

2. 在 VS Code 中打开 `pandora` 源代码目录，修改 `__main__.py` 并在代码中设置断点。
```python
import sys
import os

# 将 pandora 模块所在的目录添加到 Python 的模块搜索路径中
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from pandora import launcher

if __name__ == '__main__':
    launcher.run()
```