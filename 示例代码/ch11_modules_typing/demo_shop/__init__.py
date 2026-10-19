# demo_shop/__init__.py | EX-11-02 支撑文件：包的"门面"
"""demo_shop：演示包结构与导入机制的最小包。

__init__.py 的作用：
1. 告诉 Python "这是一个包"（3.3+ 支持 no-namespace 包以外的常规包必须有它）；
2. 控制 from demo_shop import * 能拿到什么（__all__）；
3. 把常用的名字提前导入，调用方就可以 from demo_shop import Order，
   而不必知道 Order 具体住在 core.py 还是 pricing.py——类似 Java 门面类。
"""
from .core import CURRENCY, Order          # 相对导入：. 指 demo_shop 包自己
from .pricing import calc_total

__all__ = ["CURRENCY", "Order", "calc_total"]
