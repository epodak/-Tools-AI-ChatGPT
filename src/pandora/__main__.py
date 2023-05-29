import sys
import os

# 将 pandora 模块所在的目录添加到 Python 的模块搜索路径中
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from pandora import launcher

if __name__ == '__main__':
    print("在这个地方开始")
    launcher.run()