# 第二部分（上）Python 语言基础（一）：对象模型、数据结构、函数、类与异常（ch04~ch08）

> 资料核实日期：2026-10-19。本部分全部示例均在本教材约定的沙箱环境（Python 3.14.7，见 `requirements.txt`）实际运行，输出为真实记录；教材基准 Python 3.12+，代码兼容 3.10+。
> 前置知识：ch01~ch03（环境搭建、venv、第一个程序、异常堆栈阅读法）。
> 学完你能做什么：
> 1. 说清"Python 变量是名字不是盒子"这句话的确切含义，并据此预判共享、拷贝、函数传参产生的全部副作用；
> 2. 熟练使用 list/tuple/dict/set 与推导式完成日常数据加工，能从可哈希性角度判断"什么能做 dict 的 key"；
> 3. 写出带完整类型注解的函数、类（含魔术方法、property、dataclass）与业务异常体系，直接对接 FastAPI、Pydantic、LangChain 等框架的惯用法。

这一部分是全书语言地基。Java 经验大约能覆盖六成常识，本部分重点讲剩下的四成：Python 的对象模型（ch04）、容器与可哈希性（ch05）、函数与作用域（ch06）、类与结构化子类型（ch07）、异常体系（ch08）。ch09~ch12（生成器、装饰器、模块、标准库）见第二部分（下）。

---

# 第 4 章 变量与对象模型：名字贴在对象上

> **本章目标**：建立"一切皆对象 + 名字绑定"的心智模型，能用它解释别名共享、函数传参、浅/深拷贝的行为。
> **前置知识**：ch03 的程序运行与堆栈阅读。
> **学完你能做什么**：预判任何一段 Python 代码里"谁和谁共享同一个对象"；正确选择 `==` 与 `is`、赋值与 `copy`；说清 Python 与 Java 在变量模型上的三条本质差异。

## 4.1 真实问题引入：跨会话"漏消息"的对话历史

某电商平台（合成案例）的 Java 团队转写一个客服 AI 服务：`ConversationService` 维护对话历史。转写者写出了这样的 Python 代码：

```python
def new_session(messages: list[str] = []):
    messages.append("会话开始")
    return messages

def clear(messages: list[str]):
    messages = []          # 本意：清空历史
```

上线后出现两个诡异现象：**每个"新会话"都带着上一个会话的消息**（`new_session` 的默认列表被所有调用共享）；而 `clear` 调用后历史"根本没清掉"（函数内 `messages = []` 只是把局部名字贴到新列表上，调用者的列表原封不动）。这两个 bug 都不是"语法不会"，而是**对象模型的心智模型错了**：Java 工程师默认"变量是装值的盒子"，而 Python 的变量是"贴在对象上的名字"。本章就把这个模型建立起来。

## 4.2 一句话解释 + 生活类比 + 类比边界

**一句话解释**：Python 中变量是"名字到对象的引用"，赋值不复制数据、只是把名字绑到某个对象上；数据都活在堆上的对象里，每个对象自带类型信息与引用计数。

**生活类比**：对象是仓库里的货物，变量（名字）是贴在货物上的便利贴。`b = a` 不是复印货物，而是再贴一张写着 `b` 的便利贴到同一件货物上；`del b` 只是撕掉便利贴，货物不受影响。

> 💡 类比边界：
> 1. 便利贴可以随意撕下重贴（重新绑定名字），但**容器内部的槽位不是便利贴**——`lst[0] = x` 改的是 list 这个对象自己的内容，所有贴在这个 list 上的名字都会看到；
> 2. Python 里"一切皆对象"，连 `int` 也是堆上的对象；Java 有 `int` 这种值语义的"真盒子"（基本类型），Python 没有对应物——这是类比失效最深的一层；
> 3. "垃圾回收像保洁员收走没人指的货物"只对一半：CPython 主要靠**引用计数**（贴纸数量归零立即回收），分代 GC 只兜底循环引用，与 JVM"定时批量清扫"的节奏完全不同。

## 4.3 正式原理与准确术语

**对象（object）**：Python 中一切数据的最小实体，每个对象都有三要素——**身份**（identity，实现上即内存地址，用 `id()` 观察）、**类型**（type，决定它能做什么操作）、**值**（value）。函数、类、模块、`None` 都是对象，都继承自 `object`。

**名字绑定（name binding）**：`a = [1, 2]` 的语义是"在当前命名空间里建立名字 `a` 到该 list 对象的引用"。命名空间可以粗略理解成一张 `名字 -> 对象` 的字典。**动态类型（dynamic typing）**：类型信息挂在对象上而不是名字上，同一个名字可以先绑定 `int` 再绑定 `str`；类型注解（如 `a: list[int]`）只是给人与静态检查器看的提示，**运行时不做类型检查**（这与 Java 的编译期类型检查是本质差异，详见 FACTS 与 ch11）。

**可变对象（mutable object）与不可变对象（immutable object）**：list/dict/set/自定义类实例默认可变；int/float/str/bool/tuple/frozenset/bytes 不可变。对不可变对象"修改"实际上是创建新对象再重新绑定。

**两条常被 Java 经验误导的对照**：

| 维度 | Java | Python |
|---|---|---|
| 变量本质 | 基本类型是值槽位；引用类型是"有类型的引用槽位" | 名字 → 对象引用，名字本身无类型 |
| 字面量缓存 | `Integer` 缓存 -128~127；字符串常量池 | CPython 小整数缓存 -5~256；标识符样式的字符串字面量会被驻留（interning） |
| `final`/`const` | `final` 引用：引用不可换，对象内容可变 | 同样分两层：绑定不可变（无语言级 const，约定全大写）与对象不可变（tuple/frozen dataclass） |

> ⚠️ 常见坑：`final` ≠ immutable 在 Python 里同样成立——`tuple` 里装一个 `list`，tuple 的槽位不能换，但 list 可以被改。用 `is` 比较两个"值相等"的普通对象来"优化性能"，可能因为缓存与否得出不同结果，这是逻辑 bug 而不是报错，更难排查。

## 4.4 最小完整示例：一切皆对象 + 名字绑定

**EX-04-01 | examples/ch04_objects/ex_04_01_everything_is_object.py（完整可运行）**

```python
# EX-04-01 | 一切皆对象 | 运行: python3 examples/ch04_objects/ex_04_01_everything_is_object.py
"""在 Python 里，整数、字符串、函数、类……全部都是对象（object）。"""
from typing import Any


def describe(value: Any, label: str) -> None:
    """打印一个值的类型与两个内省结果。"""
    print(f"{label}: 值={value!r:<14} 类型={type(value).__name__}  "
          f"是object的实例={isinstance(value, object)}")


def main() -> None:
    describe(42, "整数    ")
    describe("hello", "字符串  ")
    describe([1, 2], "列表    ")
    describe(3.14, "浮点数  ")
    describe(None, "None    ")
    describe(len, "内置函数")
    # 函数的 repr 里含内存地址（每次运行都不同），这里只看类型与归属
    print(f"自定义函数: 类型={type(describe).__name__}  "
          f"是object的实例={isinstance(describe, object)}")

    # 函数是对象：可以赋值、放进容器、当参数传
    registry: dict[str, Any] = {"求和": sum, "计数": len}
    print(f"把函数放进字典并调用: registry['求和']([1, 2, 3]) = {registry['求和']([1, 2, 3])}")

    # 类本身也是对象：类对象的类型是 type
    print(f"int 的类型是 {type(int).__name__}，type 的类型是 {type(type).__name__}")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（Python 3.14.7）
整数    : 值=42             类型=int  是object的实例=True
字符串  : 值='hello'        类型=str  是object的实例=True
列表    : 值=[1, 2]         类型=list  是object的实例=True
浮点数  : 值=3.14           类型=float  是object的实例=True
None    : 值=None           类型=NoneType  是object的实例=True
内置函数: 值=<built-in function len> 类型=builtin_function_or_method  是object的实例=True
自定义函数: 类型=function  是object的实例=True
把函数放进字典并调用: registry['求和']([1, 2, 3]) = 6
int 的类型是 type，type 的类型是 type
```

**EX-04-02 | examples/ch04_objects/ex_04_02_name_binding.py（完整可运行）**

```python
# EX-04-02 | 名字绑定与引用语义 | 运行: python3 examples/ch04_objects/ex_04_02_name_binding.py
"""Python 变量是"名字贴在对象上"，不是"装值的盒子"。"""


def main() -> None:
    a: list[int] = [1, 2, 3]
    b = a                      # 不复制列表，只是给同一个对象贴了第二个名字
    b.append(4)
    print(f"b 追加元素后 a = {a}")   # a 也"变"了：a、b 指向同一个对象
    print(f"a is b: {a is b}")       # 身份相同

    x: int = 1000
    y = x                    # 名字 y 绑定到 x 所指的对象
    y = y + 1                # int 不可变：新建对象 1001，让 y 改贴到它上面
    print(f"x = {x}, y = {y}  （x 不受影响，因为 1000 这个对象从未被修改）")

    # 函数传参同样只传"对象引用"
    def append_one(lst: list[int]) -> None:
        lst.append(99)       # 原地修改：调用者可见

    def rebind(lst: list[int]) -> None:
        lst = [0]            # 只是让局部名字改贴到新对象：调用者不可见

    data = [1]
    append_one(data)
    print(f"append_one 后 data = {data}（原地修改可见）")
    rebind(data)
    print(f"rebind    后 data = {data}（重新绑定不可见）")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（Python 3.14.7）
b 追加元素后 a = [1, 2, 3, 4]
a is b: True
x = 1000, y = 1001  （x 不受影响，因为 1000 这个对象从未被修改）
append_one 后 data = [1, 99]（原地修改可见）
rebind    后 data = [1, 99]（重新绑定不可见）
```

## 4.5 逐段解释：身份、可变性、拷贝与回收

**（1）`==` 与 `is`：值相等 vs 身份相同**。`==` 调用对象的 `__eq__`，比较"内容"；`is` 比较两个名字是否指向同一个对象（等价于 `id(a) == id(b)`，但更快更明确）。EX-04-03 里特意用"运行时计算出来的 257"来演示：`base + 7` 计算两次会得到两个不同对象，`==` 为 True、`is` 为 False。小整数缓存（-5~256）与字符串驻留是 **CPython 的实现细节**，不是语言规范，因此**业务代码里用 `is` 判等值是 bug**；`is` 只用于 `x is None` 这类哨兵判断。

**EX-04-03 | examples/ch04_objects/ex_04_03_is_vs_eq.py（完整可运行）**

```python
# EX-04-03 | is 与 == 的区别 | 运行: python3 examples/ch04_objects/ex_04_03_is_vs_eq.py
def main() -> None:
    # 1) == 比较"值相等"，is 比较"是否同一个对象"（身份）
    list_a: list[int] = [1, 2, 3]
    list_b: list[int] = [1, 2, 3]
    print(f"list_a == list_b: {list_a == list_b}")   # True：内容相等
    print(f"list_a is list_b: {list_a is list_b}")   # False：两个不同对象

    # 2) 小整数缓存（CPython 缓存 -5..256）：两次拿到同一个对象
    small1: int = 256
    small2: int = 256
    print(f"small1 is small2 (256): {small1 is small2}")

    # 3) 运行时计算出来的 257：各自新建，值相等但不是同一个对象
    base = 250
    big1: int = base + 7     # 257，运行时创建
    big2: int = base + 7
    print(f"big1 == big2: {big1 == big2}")
    print(f"big1 is big2: {big1 is big2}")

    # 4) 字符串同理：运行时拼接得到的是新对象
    s1: str = "".join(["hel", "lo"])
    s2: str = "".join(["hel", "lo"])
    print(f"s1 == s2: {s1 == s2}, s1 is s2: {s1 is s2}")

    # 5) is 的正确用法：与 None 等哨兵对象比较
    value: str | None = None
    print(f"value is None: {value is None}")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（Python 3.14.7）
list_a == list_b: True
list_a is list_b: False
small1 is small2 (256): True
big1 == big2: True
big1 is big2: False
s1 == s2: True, s1 is s2: False
value is None: True
```

**（2）可变 vs 不可变决定了"共享"的后果**。共享一个不可变对象永远安全（反正改不了）；共享一个可变对象，任何持有一方修改都会"同时"影响另一方——这就是 4.1 场景里漏消息的根因。EX-04-04 还演示了一个高频面试点：**tuple 的槽位不可赋值，但槽位里装的可变对象可以被原地修改**（"不可变"只约束 tuple 自己的槽位）。

**EX-04-04 | examples/ch04_objects/ex_04_04_mutable_immutable.py（完整可运行）**

```python
# EX-04-04 | 可变与不可变 | 运行: python3 examples/ch04_objects/ex_04_04_mutable_immutable.py
from typing import Any


def try_modify_str(s: str) -> str:
    s = s + "!"        # 不可变对象：只能新建，原对象不受影响
    return s


def try_modify_list(lst: list[Any]) -> None:
    lst.append("!")    # 可变对象：原地修改，调用者可见


def main() -> None:
    # 常见不可变类型：int/float/str/bool/tuple/frozenset/bytes
    # 常见可变类型：list/dict/set/自定义类实例（默认可变）
    greeting: str = "hello"
    modified: str = try_modify_str(greeting)
    print(f"原字符串: {greeting!r}，函数返回: {modified!r}")

    items: list[str] = ["a"]
    try_modify_list(items)
    print(f"原列表: {items}（被函数改掉了）")

    # 不可变对象内部引用可变对象：整体仍可能"变化"
    record: tuple[str, list[int]] = ("scores", [90])
    record[1].append(95)               # 合法：改的是 tuple 里的 list，不是 tuple 的槽位
    print(f"tuple 内部的 list 修改后: {record}")

    # 试图改 tuple 自己的槽位则报错
    try:
        record[0] = "new"
    except TypeError as exc:
        print(f"修改 tuple 槽位 -> TypeError: {exc}")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（Python 3.14.7）
原字符串: 'hello'，函数返回: 'hello!'
原列表: ['a', '!']（被函数改掉了）
tuple 内部的 list 修改后: ('scores', [90, 95])
修改 tuple 槽位 -> TypeError: 'tuple' object does not support item assignment
```

**（3）拷贝三档：别名、浅拷贝、深拷贝**。赋值是别名（零拷贝）；`copy.copy()` 只复制最外层容器，内层对象仍然共享；`copy.deepcopy()` 递归复制整棵对象树。Java 里 `ArrayList` 的拷贝构造、`clone()`、序列化深拷贝也是同样的三档，但 Java 的泛型容器很少装"可变嵌套结构"，Python 的 dict 套 list 却是日常，所以浅拷贝的坑在 Python 里出现频率高得多。

**EX-04-05 | examples/ch04_objects/ex_04_05_copy.py（完整可运行）**

```python
# EX-04-05 | 浅拷贝与深拷贝 | 运行: python3 examples/ch04_objects/ex_04_05_copy.py
import copy


def main() -> None:
    original: dict[str, list[int]] = {"scores": [90, 85], "owner": "alice"}

    alias = original                        # 不是拷贝，只是别名
    shallow = copy.copy(original)           # 浅拷贝：外层新建，内层仍共享
    deep = copy.deepcopy(original)          # 深拷贝：逐层递归复制

    # 外层：alias 是同一个对象；shallow/deep 是新对象
    print(f"alias is original:   {alias is original}")
    print(f"shallow is original: {shallow is original}")
    print(f"deep is original:    {deep is original}")

    # 内层：浅拷贝的 list 与原对象是同一个；深拷贝不是
    print(f"shallow['scores'] is original['scores']: {shallow['scores'] is original['scores']}")
    print(f"deep['scores']    is original['scores']: {deep['scores'] is original['scores']}")

    # 通过浅拷贝改内层，original 跟着变；深拷贝不受影响
    shallow["scores"].append(70)
    print(f"浅拷贝追加后 original = {original}")
    deep["scores"].append(60)
    print(f"深拷贝追加后 original = {original}（不受影响）")
    print(f"deep = {deep}")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（Python 3.14.7）
alias is original:   True
shallow is original: False
deep is original:    False
shallow['scores'] is original['scores']: True
deep['scores']    is original['scores']: False
浅拷贝追加后 original = {'scores': [90, 85, 70], 'owner': 'alice'}
深拷贝追加后 original = {'scores': [90, 85, 70], 'owner': 'alice'}（不受影响）
deep = {'scores': [90, 85, 60], 'owner': 'alice'}
```

**（4）垃圾回收：引用计数为主，分代 GC 兜底（点到为止）**。CPython 给每个对象维护引用计数，计数归零立即回收——这与 JVM 的"后台批量回收"节奏完全不同。引用计数解决不了**循环引用**（两个对象互相引用，计数永不归零），于是 CPython 内置分代垃圾回收器（`gc` 模块，0/1/2 三代，新对象在 0 代，扛过回收的晋升）定期扫描容器对象找循环。**工程结论只有两条**：不要依赖析构时机做关键业务（跨实现不可靠，PyPy 等实现无引用计数）；`del x` 删的是名字不是对象。

**EX-04-06 | examples/ch04_objects/ex_04_06_gc.py（完整可运行）**

```python
# EX-04-06 | 引用计数与分代 GC（点到为止） | 运行: python3 examples/ch04_objects/ex_04_06_gc.py
import gc
import sys


class Node:
    """一个最小节点类，用于观察回收。"""

    def __init__(self, name: str) -> None:
        self.name = name
        self.partner: "Node | None" = None

    def __repr__(self) -> str:
        return f"Node({self.name!r})"


def main() -> None:
    # getrefcount 的绝对数值受解释器实现细节影响（含临时引用的处理），
    # 但"别名 +1、del -1"的趋势在 CPython 上是稳定的
    n: Node = Node("n")
    print(f"创建后引用计数: {sys.getrefcount(n)}")
    alias: Node = n
    print(f"别名绑定后引用计数: {sys.getrefcount(n)}")   # +1
    del alias
    print(f"del 别名后引用计数: {sys.getrefcount(n)}")   # -1（del 删的是名字，不是对象）

    # 引用计数处理不了"循环引用"，需要分代 GC 兜底
    a: Node = Node("a")
    b: Node = Node("b")
    a.partner = b
    b.partner = a
    del a, b                       # 外部引用消失，但两对象互相引用，计数都不为 0
    collected: int = gc.collect()  # 手动触发一次回收，返回收集到的不可达对象数
    print(f"gc.collect() 回收的不可达对象数: {collected}")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（Python 3.14.7）
创建后引用计数: 1
别名绑定后引用计数: 2
del 别名后引用计数: 1
gc.collect() 回收的不可达对象数: 2
```

注意：`getrefcount` 的绝对值是 1 还是 2（是否把传入的临时引用计入）随 CPython 版本实现变化——本环境 3.14.7 实测如上。**记住趋势即可，不要在业务代码里依赖这个数值。**

## 4.6 安装/文件位置/运行命令

- **依赖**：本章仅用标准库（`copy`、`gc`、`sys`、`typing`），无新增安装。
- **文件位置**：`examples/ch04_objects/`（6 个示例）；测试 `tests/test_ch04.py`。
- **运行命令**：

```bash
cd /workspace/ai_application_course
python3 examples/ch04_objects/ex_04_01_everything_is_object.py
python3 -m pytest tests/test_ch04.py -q
```

## 4.7 常见错误与排查

1. **`TypeError: can only concatenate str (not "int") to str`**——对不可变对象 `str` 做 `"1" + 1`。原因：Python 不做隐式类型转换（Java 的 `"1" + 1` 会得到 `"11"`）。修复：显式 `f"{s}{n}"` 或 `str(n)`。
2. **`AttributeError: 'NoneType' object has no attribute 'append'`**——函数在出错分支 `return None`（Python 函数不写 return 默认返回 `None`），调用方继续链式调用。修复：出错分支显式 `raise`（ch08）或返回明确的哨兵并检查。
3. **用 `is` 判等值导致逻辑错误**（无报错）——`a is b` 在小整数/驻留字符串上"碰巧"为 True，换成 257 或运行时字符串就为 False。修复：判值一律 `==`；`is` 只用于 `None`/哨兵/单例。
4. **共享可变默认值/共享列表导致"幽灵数据"**（无报错）——4.1 的漏消息场景。修复见 ch06 EX-06-01；跨请求的数据要么深拷贝，要么用不可变结构重建（`new = old + [msg]`）。

## 4.8 企业场景中的使用方式（Spring Boot 视角）

- **AI 服务的对话历史**：`messages: list[dict]` 是最常被共享/篡改的对象。向 OpenAI 兼容接口发请求时传历史列表，务必明确"谁拥有这个列表"——框架代码原地 `append`，调用方持有旧引用会看到"多出来的消息"（LangGraph 的 `add_messages` reducer 返回**新列表**正是为了规避共享可变状态，ch44 展开）。
- **配置对象**：Java 里 `@ConfigurationProperties` Bean 是单例可变的，Python 侧惯用 frozen dataclass / pydantic-settings 的不可变配置（ch16），从模型上杜绝"某处热改配置、别处读到半成品"。
- **缓存与对象池**：理解小整数缓存/驻留后，不要模仿着对业务对象做"手工 intern"——那是解释器层优化，业务层请用明确的缓存键 + 缓存结构（ch19）。
- **Spring 事务类比**：`rebind` 不可见（EX-04-02）类似"方法里 new 了一个新集合却没有 set 回字段"——Python 里没有"引用的引用"，要把修改传出函数，只能原地修改对象、返回新对象或改容器内容。

## 4.9 练习

1. **（基础）**不用运行代码，写出 `a = [1, 2]; b = a; b += [3]; print(a)` 的输出，并说明 `b += [3]` 与 `b = b + [3]` 的区别（提示：前者是原地 `__iadd__`，后者是新建后重新绑定）。
2. **（基础）**`x = 300; y = 300; x is y` 在"脚本里同一函数内"与"交互式解释器逐行输入"下结果可能不同，为什么？业务代码应该用 `==` 还是 `is`？
3. **（代码）**写函数 `def pop_all(items: list[int]) -> list[int]`：返回一个**新列表**，内容为 `items` 的倒序，且不得修改 `items` 本身；再写一个错误版本（原地 `reverse`）并说明区别。
4. **（代码）**给定 `config = {"model": "m1", "params": {"temperature": 0.2}}`，写代码得到一个可以安全修改 `params` 而不影响 `config` 的副本，并说明为什么 `copy.copy` 不够。
5. **（调试题）**下面的函数想"清空并复用缓冲区"但调用者发现缓冲区没被清空，请指出 bug 并修复：

```python
def reset(buf: list[str]) -> None:
    buf = []
```

### 参考答案

<details>
<summary>点开查看参考答案</summary>

1. 输出 `[1, 2, 3]`。`b += [3]` 等价于 `b.extend([3])`，原地修改 `a`、`b` 共享的那个列表；`b = b + [3]` 会新建列表并把 `b` 改贴过去，`a` 不变。
2. 小整数缓存与常量合并是 CPython 实现细节：同一代码对象里的字面量常量会被共享（脚本内常见 True），交互式逐行编译则可能各自建对象。判值用 `==`。
3. 正确：`return list(reversed(items))` 或 `return items[::-1]`（切片产生新列表，浅拷贝；元素是 int 不可变所以够用）。错误版本 `items.reverse()` 原地修改并返回 `None`，调用者的列表被改动。
4. `import copy; safe = copy.deepcopy(config)`。`copy.copy` 只新建外层 dict，内层 `"params"` 仍是同一个 dict，修改副本的 `params` 会同步到 `config`。
5. `buf = []` 只是把局部名字重新绑定到新列表，调用者的列表没变。修复：`buf.clear()`（原地清空）或 `del buf[:]`。

</details>

## 4.10 自测检查表

- 我能说出对象三要素（身份/类型/值）并解释 `id()` 的含义与局限。
- 我能用"名字贴在对象上"模型解释别名共享、函数传参、`rebind` 不可见。
- 我能区分 `==` 与 `is`，并说出 `is` 的正确使用场景（哨兵判断）。
- 我能列出常见可变与不可变类型，并解释"tuple 里的 list 可变"。
- 我能说清别名/浅拷贝/深拷贝三档的区别与各自适用场景。
- 我能解释 CPython 回收对象的两个机制（引用计数 + 分代 GC 兜底循环引用），并说明为什么业务代码不应依赖析构时机。

## 4.11 面试追问

1. **[模拟题] Python 的赋值语句做了什么？与 Java 有何不同？**——参考回答：在当前命名空间建立"名字→对象引用"的绑定，不复制数据；Java 基本类型是值拷贝、引用类型是引用值拷贝（语义上与 Python 传对象引用接近），但 Java 的变量有静态类型，Python 的类型在对象上。追问方向：`del` 删什么、小整数缓存。
2. **[模拟题] 什么时候浅拷贝就够了？什么时候必须深拷贝？**——参考回答：外层容器新建、内层元素全为不可变对象（或内层只读）时浅拷贝够用；存在嵌套可变结构且要独立修改时必须深拷贝；深拷贝有性能与循环引用处理成本（`copy.deepcopy` 自带备忘录机制）。
3. **[模拟题] CPython 的垃圾回收和 JVM 有什么区别？**——参考回答：CPython 主力是引用计数（归零即回收、无 STW 批量清扫），分代 GC 只为解决循环引用；JVM 全靠分代/并发收集器批量回收。工程含义：Python 里资源释放要靠 `with`（ch08），不能像 Java 靠 finalize/try-finally 兜内存外的资源。

### 待核实

- `sys.getrefcount` 是否把临时引用计入，随 CPython 版本实现变化（本章 3.14.7 实测返回"变量本身计 1"）；写跨版本代码时请以所用解释器的实测为准。
- 小整数缓存范围（-5~256）、字符串驻留规则属 CPython 实现细节，其他实现（PyPy 等）不保证相同，以各实现官方文档为准。

---

# 第 5 章 内置数据结构：list / tuple / dict / set 与推导式

> **本章目标**：完整掌握四大内置容器的操作、切片与解包、四种推导式，并从可哈希性理解 dict/set 的底层约束。
> **前置知识**：ch04 的可变性与引用语义。
> **学完你能做什么**：为任何"数据加工"任务（去重、分组、计数、展平、截断）选出正确的容器与推导式写法；避免 `KeyError`、`unhashable type` 等高频运行时错误。

## 5.1 真实问题引入：一个"词频统计"服务的三种写法

Java 团队做 AI 评估平台（合成案例），要统计评估集里每类失败原因出现的次数、给不同模型的回答打标签集合、并把长对话历史按条截断。用 Java 的第一反应是 `Map<String, Integer>` + `merge`、`HashSet`、`subList`。Python 里这对应 `Counter`、`set`、切片——但Java 工程师常写出三种"能跑但别扭"的代码：手写 `if key in map` 计数（该用 `Counter`）、用 `list` 去重（`O(n²)`，该用 `set`）、用下标循环截取（该用切片）。本章按"容器选型 → 操作 → 推导式 → 底层约束（可哈希性）"的顺序一次讲透。

## 5.2 一句话解释 + 生活类比 + 类比边界

**一句话解释**：`list` 是有序可变序列，`tuple` 是有序不可变序列，`dict` 是可哈希 key 到 value 的映射（3.7+ 保证按插入顺序遍历），`set` 是可哈希元素的无序去重集合；推导式是"循环+条件+构造"的声明式写法。

**生活类比**：list 是火车车厢（有编号、可增删）；tuple 是出厂封死的整列车（只能看不能改）；dict 是带唯一车牌号的寄存柜（凭 key 取件）；set 是"只看人脸不记顺序"的签到表。

> 💡 类比边界：
> 1. dict ↔ `HashMap` 的最大差异：Python 3.7 起**插入顺序是语言规范**，Java 的 `HashMap` 无序、要保序得用 `LinkedHashMap`——所以"dict 输出顺序"不是巧合，可以依赖；
> 2. set 的"无序"是语义无序：遍历顺序取决于哈希且跨进程不稳定（本教材示例统一用 `sorted()` 展示集合内容，就是为了让输出可复现）；
> 3. tuple 不是 Java 的 `record`：record 是"具名字段的结构"，tuple 是"位置的序列"，具名结构请看 ch07 的 dataclass/NamedTuple。

## 5.3 正式原理与准确术语

**可哈希（hashable）**：对象实现了 `__hash__` 且生命周期内哈希值不变。它是做 dict key / 进 set 的门票：dict 内部按 `hash(key)` 定位桶、按 `==` 判同，所以 key 必须**全程稳定**——这直接推出"list/dict/set 不可哈希，tuple（内容全可哈希时）可哈希"。**插入有序（insertion-ordered）**：dict 自 3.7 起语言规范保证；覆盖已有 key 不改变其位置。**推导式（comprehension）**：列表 `[表达式 for x in 可迭代 if 条件]`、字典/集合同理、生成器表达式用圆括号（惰性，ch09 展开）。

容器与 Java 对照速查：

| Python | 最接近的 Java | 关键差异 |
|---|---|---|
| list | ArrayList | 可装异构对象；切片语法独有 |
| tuple | List.of(...) | 无名字段；常用于多返回值、dict key |
| dict | HashMap / LinkedHashMap | 语言级插入有序；字面量语法一等公民 |
| set | HashSet | 字面量 `{1, 2}`；`-`/`&`/`|` 运算符 |
| collections.deque | ArrayDeque | 头尾 O(1)，ch09 用 |

## 5.4 最小完整示例：list 与 tuple/unpacking

**EX-05-01 | examples/ch05_datastructures/ex_05_01_list_ops.py（完整可运行）**

```python
# EX-05-01 | list 常用操作 | 运行: python3 examples/ch05_datastructures/ex_05_01_list_ops.py
def main() -> None:
    nums: list[int] = [3, 1, 2]
    nums.append(4)               # 尾部追加
    nums.extend([0, 5])          # 合并另一个可迭代对象
    nums.insert(0, 9)            # 指定位置插入
    print(f"构造后: {nums}")

    last: int = nums.pop()       # 弹出末尾
    first: int = nums.pop(0)     # 弹出指定下标
    nums.remove(2)               # 按值删除第一个匹配
    print(f"pop 得到 {last} 和 {first}，remove(2) 后: {nums}")

    nums.sort()                  # 原地排序，返回 None（注意！）
    print(f"sort 后: {nums}")
    print(f"sorted 副本（倒序）: {sorted(nums, reverse=True)}，原列表仍是 {nums}")

    print(f"index(1) = {nums.index(1)}，count(1) = {nums.count(1)}")
    print(f"len = {len(nums)}，min = {min(nums)}，max = {max(nums)}，sum = {sum(nums)}")

    words: list[str] = ["banana", "apple", "cherry"]
    words.sort(key=len)          # key 函数：按长度排序（稳定排序，同长度保持原顺序）
    print(f"按长度排序: {words}")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（Python 3.14.7）
构造后: [9, 3, 1, 2, 4, 0, 5]
pop 得到 5 和 9，remove(2) 后: [3, 1, 4, 0]
sort 后: [0, 1, 3, 4]
sorted 副本（倒序）: [4, 3, 1, 0]，原列表仍是 [0, 1, 3, 4]
index(1) = 1，count(1) = 1
len = 4，min = 0，max = 4，sum = 8
按长度排序: ['apple', 'banana', 'cherry']
```

**EX-05-02 | examples/ch05_datastructures/ex_05_02_tuple_unpacking.py（完整可运行）**

```python
# EX-05-02 | tuple 与解包 | 运行: python3 examples/ch05_datastructures/ex_05_02_tuple_unpacking.py
def min_max(values: list[int]) -> tuple[int, int]:
    """返回多个值的惯用法：本质上就是返回一个 tuple。"""
    return min(values), max(values)


def main() -> None:
    point: tuple[float, float] = (3.0, 4.0)
    x, y = point                          # 按位置解包
    print(f"x = {x}, y = {y}")

    a, b = 1, 2
    a, b = b, a                           # 交换变量：右侧先打包成 tuple 再解包
    print(f"交换后 a = {a}, b = {b}")

    first, *rest = [10, 20, 30, 40]       # 星号解包：吃掉中间任意多个
    print(f"first = {first}, rest = {rest}")
    *init, last = [10, 20, 30, 40]
    print(f"init = {init}, last = {last}")

    low, high = min_max([5, 3, 9, 1])
    print(f"min = {low}, max = {high}")

    # 单元素 tuple 必须带逗号；括号本身不制造 tuple
    single: tuple[int] = (42,)
    not_tuple: int = (42)                 # 这只是带括号的 42
    print(f"single = {single}（类型 {type(single).__name__}）；(42) 的类型是 {type(not_tuple).__name__}")

    # 解包也用于调用与字面量
    args = [1, 2, 3]
    print(f"max(*args) = {max(*args)}")
    merged_list = [*[1, 2], *[3]]
    merged_dict = {**{"a": 1}, **{"b": 2}}
    print(f"列表解包合并 = {merged_list}，字典解包合并 = {merged_dict}")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（Python 3.14.7）
x = 3.0, y = 4.0
交换后 a = 2, b = 1
first = 10, rest = [20, 30, 40]
init = [10, 20, 30], last = 40
min = 1, max = 9
single = (42,)（类型 tuple）；(42) 的类型是 int
max(*args) = 3
列表解包合并 = [1, 2, 3]，字典解包合并 = {'a': 1, 'b': 2}
```

## 5.5 逐段解释：dict/set、推导式、切片、可哈希性、defaultdict/Counter

**（1）dict 与 set**。`user["key"]` 缺失即抛 `KeyError`，`get` 给默认值不抛；`|` 合并（3.9+）右侧优先；`update` 原地合并。set 支持 `|`/`&`/`-`/`^` 四则运算，去重是它的本职。

**EX-05-03 | examples/ch05_datastructures/ex_05_03_dict_set.py（完整可运行）**

```python
# EX-05-03 | dict 与 set | 运行: python3 examples/ch05_datastructures/ex_05_03_dict_set.py
def main() -> None:
    # dict：键值对。3.7+ 语言规范保证按插入顺序遍历
    user: dict[str, str] = {"name": "alice", "role": "admin"}
    user["email"] = "a@example.com"           # 新增；对已有 key 则覆盖
    print(f"user['name'] = {user['name']}")
    print(f"get 不抛异常: user.get('phone') = {user.get('phone')!r}")
    print(f"get 带默认值: {user.get('phone', '未绑定')}")
    print(f"插入顺序遍历 keys: {list(user.keys())}")

    removed: str = user.pop("role")
    print(f"pop('role') = {removed}，剩余 keys = {list(user)}")

    defaults: dict[str, str] = {"role": "guest", "theme": "light"}
    merged: dict[str, str] = defaults | user  # 3.9+ 合并运算符：右侧优先
    print(f"| 合并 = {merged}")
    defaults.update(user)
    print(f"update 后 defaults = {defaults}")

    # set：元素唯一且必须可哈希；遍历顺序不保证（下面用 sorted 展示）
    tags1: set[str] = {"java", "python", "sql"}
    tags2: set[str] = {"python", "docker"}
    print(f"并集 |: {sorted(tags1 | tags2)}")
    print(f"交集 &: {sorted(tags1 & tags2)}")
    print(f"差集 -: {sorted(tags1 - tags2)}")
    print(f"对称差 ^: {sorted(tags1 ^ tags2)}")
    print(f"list 去重: {sorted({1, 2, 2, 3, 3, 3})}")
    probe: set[str] = {"python", "docker"}
    print(f"子集判断: probe <= tags2 = {probe <= tags2}")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（Python 3.14.7）
user['name'] = alice
get 不抛异常: user.get('phone') = None
get 带默认值: 未绑定
插入顺序遍历 keys: ['name', 'role', 'email']
pop('role') = admin，剩余 keys = ['name', 'email']
| 合并 = {'role': 'guest', 'theme': 'light', 'name': 'alice', 'email': 'a@example.com'}
update 后 defaults = {'role': 'guest', 'theme': 'light', 'name': 'alice', 'email': 'a@example.com'}
并集 |: ['docker', 'java', 'python', 'sql']
交集 &: ['python']
差集 -: ['java', 'sql']
对称差 ^: ['docker', 'java', 'sql']
list 去重: [1, 2, 3]
子集判断: probe <= tags2 = True
```

**（2）四种推导式**。口诀：**方括号出列表、花括号带冒号出字典、花括号不带冒号出集合、圆括号出生成器**。条件有两种位置：写在 `for` 之后是"过滤"（可以只有 if），写在表达式处是"分支"（必须是 if-else 三元）。EX-05-04 中 `marks` 一行演示了后者。

**EX-05-04 | examples/ch05_datastructures/ex_05_04_comprehensions.py（完整可运行）**

```python
# EX-05-04 | 推导式全家 | 运行: python3 examples/ch05_datastructures/ex_05_04_comprehensions.py
def main() -> None:
    scores: dict[str, int] = {"alice": 92, "bob": 58, "carol": 77}

    # 列表推导式：[表达式 for 变量 in 可迭代 if 条件]
    names = [name for name in scores if scores[name] >= 60]
    print(f"及格名单: {names}")

    # if-else 写在表达式位置（三元）：注意与"过滤用的 if"位置不同
    marks = [f"{s}分" if s >= 60 else f"{s}分(补考)" for s in scores.values()]
    print(f"成绩标注: {marks}")

    # 字典推导式
    passed = {name: s for name, s in scores.items() if s >= 60}
    print(f"及格成绩表: {passed}")

    # 集合推导式
    initials = {name[0].upper() for name in scores}
    print(f"首字母集合: {sorted(initials)}")

    # 生成器表达式：不立即构建列表，惰性求值（ch09 展开）
    total = sum(s for s in scores.values())
    print(f"总分: {total}")

    # 嵌套推导式：按"先外后内"的阅读顺序展平矩阵
    matrix = [[1, 2, 3], [4, 5, 6]]
    flat = [cell for row in matrix for cell in row]
    print(f"展平: {flat}")

    # 与传统写法对照（两者等价）
    flat_loop: list[int] = []
    for row in matrix:
        for cell in row:
            flat_loop.append(cell)
    print(f"传统循环: {flat_loop}")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（Python 3.14.7）
及格名单: ['alice', 'carol']
成绩标注: ['92分', '58分(补考)', '77分']
及格成绩表: {'alice': 92, 'carol': 77}
首字母集合: ['A', 'B', 'C']
总分: 227
展平: [1, 2, 3, 4, 5, 6]
传统循环: [1, 2, 3, 4, 5, 6]
```

**（3）切片**。`seq[start:stop:step]`，含头不含尾；负下标从尾数；`[::-1]` 反转；**切片越界不报错**（与下标访问不同）；切片结果是浅拷贝（EX-05-05 中 `data[:] is data` 为 False）；切片还能出现在赋值号左边，一次替换一段。

**EX-05-05 | examples/ch05_datastructures/ex_05_05_slicing.py（完整可运行）**

```python
# EX-05-05 | 切片 | 运行: python3 examples/ch05_datastructures/ex_05_05_slicing.py
def main() -> None:
    data: list[int] = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]

    print(f"data[2:5]    = {data[2:5]}     # 下标 2 到 4（不含 5）")
    print(f"data[:3]     = {data[:3]}      # 省略起点 = 从头开始")
    print(f"data[7:]     = {data[7:]}      # 省略终点 = 一直到尾")
    print(f"data[-3:]    = {data[-3:]}     # 负下标：最后三个")
    print(f"data[::2]    = {data[::2]}     # 步长 2")
    print(f"data[::-1]   = {data[::-1]}    # 步长 -1：反转")
    print(f"data[5:2:-1] = {data[5:2:-1]}  # 逆序切片")

    # 越界不报错（这与下标访问不同）
    print(f"data[5:100]  = {data[5:100]}")

    # 切片是浅拷贝：得到新列表（对照 ch04）
    copy_via_slice: list[int] = data[:]
    print(f"data[:] is data: {copy_via_slice is data}")

    # 切片赋值：一次替换一段，甚至改变列表长度
    nums = [1, 2, 3, 4, 5]
    nums[1:3] = [20, 30, 99]
    print(f"切片赋值后 nums = {nums}")

    text: str = "Hello,Python"
    print(f"字符串同样支持切片: {text[7:]} / {text[::-1]}")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（Python 3.14.7）
data[2:5]    = [2, 3, 4]     # 下标 2 到 4（不含 5）
data[:3]     = [0, 1, 2]      # 省略起点 = 从头开始
data[7:]     = [7, 8, 9]      # 省略终点 = 一直到尾
data[-3:]    = [7, 8, 9]     # 负下标：最后三个
data[::2]    = [0, 2, 4, 6, 8]     # 步长 2
data[::-1]   = [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]    # 步长 -1：反转
data[5:2:-1] = [5, 4, 3]  # 逆序切片
data[5:100]  = [5, 6, 7, 8, 9]
data[:] is data: False
切片赋值后 nums = [1, 20, 30, 99, 4, 5]
字符串同样支持切片: ython / nohtyP,olleH
```

**（4）可哈希性：为什么 tuple 能当 key、list 不能**。dict 的实现要按 `hash(key)` 定位桶，key 的哈希与相等关系必须**终身稳定**。list/dict/set 内容可变、未提供内容哈希，直接判为不可哈希；tuple 自身槽位不可变，当内容全部可哈希时它就可哈希；一旦 tuple 里装了 list，整体立刻不可哈希。这不是语法限制，而是哈希表正确性的数学要求。

**EX-05-06 | examples/ch05_datastructures/ex_05_06_hashable.py（完整可运行）**

```python
# EX-05-06 | 可哈希性 | 运行: python3 examples/ch05_datastructures/ex_05_06_hashable.py
def main() -> None:
    # tuple 可哈希 -> 可以做 dict 的 key、放进 set
    locations: dict[tuple[str, int], str] = {
        ("beijing", 100000): "总部",
        ("shanghai", 200000): "分部",
    }
    print(f"tuple 作 key: {locations[('shanghai', 200000)]}")

    index: set[tuple[str, int]] = {("a", 1), ("b", 2)}
    print(f"tuple 集合: {sorted(index)}")

    # list 不可哈希 -> 不能作 key
    try:
        bad = {[1, 2]: "x"}
    except TypeError as exc:
        print(f"list 作 key -> TypeError: {exc}")

    # tuple 一旦内含 list，同样不可哈希：hash 基于内容，内容可变就无法保证稳定
    mixed: tuple[str, list[int]] = ("a", [1])
    try:
        hash(mixed)
    except TypeError as exc:
        print(f"含 list 的 tuple -> TypeError: {exc}")

    # hash 的含义：dict 内部按 hash 定位桶，因此 key 必须全程稳定
    print(f"hash('alice') 两次计算是否相等: {hash('alice') == hash('alice')}")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（Python 3.14.7）
tuple 作 key: 分部
tuple 集合: [('a', 1), ('b', 2)]
list 作 key -> TypeError: cannot use 'list' as a dict key (unhashable type: 'list')
含 list 的 tuple -> TypeError: unhashable type: 'list'
hash('alice') 两次计算是否相等: True
```

**（5）defaultdict 与 Counter**。手写计数要 `counts.get(w, 0) + 1`（对应 Java 的 `map.merge(k, 1, Integer::sum)`）；`defaultdict(list)` 让"分组"代码零判断；`Counter` 直接给计数与 `most_common`。注意行为差异：**defaultdict 访问缺失 key 会把默认值写进字典，Counter 不会**。

**EX-05-07 | examples/ch05_datastructures/ex_05_07_defaultdict_counter.py（完整可运行）**

```python
# EX-05-07 | defaultdict 与 Counter | 运行: python3 examples/ch05_datastructures/ex_05_07_defaultdict_counter.py
from collections import Counter, defaultdict


def main() -> None:
    words: list[str] = ["java", "python", "java", "go", "python", "java"]

    # 手写计数（对照 Java: map.merge(k, 1, Integer::sum)）
    counts: dict[str, int] = {}
    for w in words:
        counts[w] = counts.get(w, 0) + 1
    print(f"手写计数: {counts}")

    # defaultdict：访问缺失 key 时按工厂函数自动创建默认值
    grouped: defaultdict[int, list[str]] = defaultdict(list)
    for w in words:
        grouped[len(w)].append(w)
    print(f"按长度分组: {dict(grouped)}")
    print(f"访问缺失 key: grouped[99] = {grouped[99]}（自动创建空列表并写入）")
    print(f"访问之后 keys: {sorted(grouped)}")

    # Counter：计数器专用工具，缺失 key 返回 0 且不写入
    counter: Counter[str] = Counter(words)
    print(f"Counter: {dict(counter)}")
    print(f"最常见的 2 个: {counter.most_common(2)}")
    print(f"缺失 key 计数: counter['rust'] = {counter['rust']}（不写入 key）")
    print(f"访问之后 keys: {sorted(counter)}")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（Python 3.14.7）
手写计数: {'java': 3, 'python': 2, 'go': 1}
按长度分组: {4: ['java', 'java', 'java'], 6: ['python', 'python'], 2: ['go']}
访问缺失 key: grouped[99] = []（自动创建空列表并写入）
访问之后 keys: [2, 4, 6, 99]
Counter: {'java': 3, 'python': 2, 'go': 1}
最常见的 2 个: [('java', 3), ('python', 2)]
缺失 key 计数: counter['rust'] = 0（不写入 key）
访问之后 keys: ['go', 'java', 'python']
```

## 5.6 安装/文件位置/运行命令

- **依赖**：仅标准库（`collections`），无新增安装。
- **文件位置**：`examples/ch05_datastructures/`（7 个示例）；测试 `tests/test_ch05.py`。
- **运行命令**：

```bash
cd /workspace/ai_application_course
python3 examples/ch05_datastructures/ex_05_03_dict_set.py
python3 -m pytest tests/test_ch05.py -q
```

## 5.7 常见错误与排查

1. **`KeyError: 'phone'`**——`user["phone"]` 直接下标访问缺失 key。修复：读侧用 `user.get("phone", 默认值)`；写侧先 `in` 判断或用 `setdefault`。注意别把 `get` 的默认值当"写入"。
2. **`TypeError: cannot use 'list' as a dict key (unhashable type: 'list')`**——拿 list（或含 list 的 tuple、含 dict 的 tuple）当 key。修复：改用 tuple、frozen dataclass 或把可变字段转成字符串/数字组合。
3. **`IndexError: list index out of range`**——下标越界（切片越界不报错，别混淆）。修复：先 `len()` 判断或用切片语义；循环中删除元素导致的索引错位是重灾区，应改为遍历副本或重建列表。
4. **`ValueError: list.remove(x): x not in list`**——`remove` 按值删除但值不存在。修复：先 `if x in lst` 或捕获 `ValueError`（EAFP 风格，见 ch08）。
5. **`lst.sort().reverse()` 返回 None**——`sort`/`append` 等原地方法返回 `None` 是刻意设计。修复：要么链式使用 `sorted()`，要么分两行调用原地方法。

## 5.8 企业场景中的使用方式（Spring Boot 视角）

- **Prompt 模板与消息组装**：`dict` 组装模板变量（对应 Java 的 `Map<String, Object>` + `StringTemplate`），`list[dict]` 组装 chat messages；消息历史的窗口截断就是 `messages[-N:]` 一行切片（ch27 展开）。
- **评估与统计**：`Counter` 统计失败类型 Top-K（`most_common`），`defaultdict(list)` 把样本按模型/类别分组——对应 Java Stream 的 `Collectors.groupingBy` + `counting()`，但无需 stream 管道。
- **权限与标签**：多租户标签过滤用 `set` 交集 `user_tags & doc_tags`，语义与 Java 的 `retainAll` 相同但表达式化。
- **配置合并**：`defaults | overrides` 一行完成"默认配置被用户配置覆盖"，右侧优先语义要在代码评审里讲清楚（对应 Spring 的 profile 覆盖顺序）。

## 5.9 练习

1. **（基础）**`{"a": 1, "b": 2} | {"b": 9, "c": 3}` 的结果是什么？若把两个操作数交换呢？总结"右侧优先"规则。
2. **（基础）**想把 `(规则名, 参数列表)` 作为 dict 的 key，但参数列表是 `list`，怎么改设计才能合法？
3. **（代码）**用一行推导式把 `["java:8", "python:3.12", "go:1.22"]` 变成 `{"java": "8", "python": "3.12", "go": "1.22"}`（提示：`str.split(":", 1)` 与字典推导式）。
4. **（代码）**实现 `def chunk(lst: list, size: int) -> list[list]`：把列表按 size 切块（最后一块可短），用切片实现并写一个单元素边界用例。
5. **（调试题）**下面的"去重保序"代码丢了元素顺序，请修复：

```python
def dedup(items: list[str]) -> list[str]:
    return list(set(items))
```

### 参考答案

<details>
<summary>点开查看参考答案</summary>

1. `{'a': 1, 'b': 9, 'c': 3}`；交换后 `{'a': 1, 'b': 2, 'c': 3}`（"b": 9 被左侧盖掉）。规则：`|` 右侧的同名 key 胜出，key 的位置沿用首次出现的顺序。
2. 把 key 中所有字段换成不可变表示：`(规则名, tuple(参数列表))` 整体成为可哈希 tuple 即可（前提是列表元素本身可哈希）；若元素也可能可变，则退而求其次把整个 key 序列化为字符串（如 `json.dumps`）作为规范形。
3. `{kv.split(":", 1)[0]: kv.split(":", 1)[1] for kv in items}`；更优雅的写法：`dict(kv.split(":", 1) for kv in items)`。
4. `return [lst[i:i + size] for i in range(0, len(lst), size)]`；边界：`chunk([1], 3) == [[1]]`，`chunk([], 2) == []`。
5. `set` 无序。修复：`seen: set = set(); return [x for x in items if not (x in seen or seen.add(x))]`（可读性差），推荐两行版：先 `seen` 循环追加，或 `list(dict.fromkeys(items))`（dict 保序去重，3.7+）。

</details>

## 5.10 自测检查表

- 我能不查资料写出列表/字典/集合推导式，并说清"过滤 if"与"三元 if-else"的位置差异。
- 我能解释为什么 list 不能做 dict key，而 tuple 可以（哈希稳定性）。
- 我能说出 dict 插入有序的语言规范版本（3.7+）以及覆盖 key 不换位的细节。
- 我能熟练使用切片完成反转、步长取样、窗口截断，并知道切片是浅拷贝。
- 我能区分 defaultdict 与 Counter 对缺失 key 的不同行为。
- 我能说出 `sort` 与 `sorted`、`pop` 与 `remove` 的差异与返回值。

## 5.11 面试追问

1. **[模拟题] dict 的 key 为什么必须可哈希？如果自定义类想做 key 要实现什么？**——参考回答：哈希表按 `__hash__` 定位、按 `__eq__` 判同，key 哈希必须终身稳定；自定义类默认按身份哈希（object 的实现），要做"值语义 key"需同时实现 `__hash__` 与 `__eq__`（ch07 EX-07-02）。追问：`__eq__` 定义后不定义 `__hash__` 会发生什么（类被置为不可哈希）。
2. **[模拟题] 列表推导式和等价 for 循环，该用哪个？性能呢？**——参考回答：简单映射/过滤用推导式更声明式；超过两层嵌套或含副作用（如写日志）用循环。性能上推导式少了循环体的方法查找开销，但**可读性优先，微秒级差异不该作为选型依据**（本书不做无出处性能承诺）。
3. **[模拟题] tuple 和 list 怎么选？**——参考回答：固定结构（坐标、多返回值、dict key、SQL 参数占位）用 tuple；会增删改的集合用 list。团队约定"传出去的参数集合尽量 tuple"可以防误改（引用语义下调用者拿到 list 就能改）。

### 待核实

- set/dict 的遍历顺序细节（哈希随机化、扩容重排）随解释器版本与运行环境变化，任何依赖"具体顺序"的代码都是 bug；本章示例对 set 一律用 `sorted()` 输出即为规避示范。

---

# 第 6 章 函数与作用域：默认参数、*args/**kwargs、LEGB 与闭包

> **本章目标**：掌握函数签名设计（默认参数、可变参数、keyword-only）、LEGB 作用域规则与闭包，能识别并修复两大经典陷阱（可变默认值、延迟绑定）。
> **前置知识**：ch04 的名字绑定模型（本章大量用到"绑定/重新绑定"）。
> **学完你能做什么**：设计出对调用方友好的函数签名；解释闭包捕获的是"变量"还是"值"；判断一段代码里某个名字到底解析到哪个作用域。

## 6.1 真实问题引入：两处"偶发"的线上问题

继续 4.1 的客服 AI 服务（合成案例）。转写者又写了两个函数：给任务队列加任务的 `add_task(task, tasks=[])`（想省一个判空），以及给每个流式回调注册处理器的循环 `for i in range(len(chunks)): handlers.append(lambda c: process(c, i))`。结果：任务跨请求堆积（默认列表共享）；所有回调里的 `i` 都是最后一个值。两个都是"Java 写不出来、Python 一不留神就中招"的问题——Java 没有默认参数（靠重载），Java lambda 只能捕获 effectively final 变量（想共享也共享不了）。本章把这两个坑连同签名设计、作用域规则一次讲清。

## 6.2 一句话解释 + 生活类比 + 类比边界

**一句话解释**：Python 函数是对象，签名由"位置参数 → 默认参数 → `*args` → keyword-only → `**kwargs`"组成；名字解析按 LEGB（Local → Enclosing → Global → Built-in）由内向外查找；闭包捕获**变量本身**（外层变量盒子），不是捕获时的值。

**生活类比**：默认参数是函数出厂时在门口挂的"公共备用品"——所有调用共享同一件（所以可变默认值会互相污染）；闭包像"带了自家钥匙的维修工"，钥匙（变量）是同一把，开的是同一个柜子，不是开柜瞬间的照片。

> 💡 类比边界：
> 1. Java 重载（同名不同参）在 Python 里**不存在**——两个同名函数后者覆盖前者；默认参数 + keyword-only 是惯用替代；
> 2. Java lambda 只能"看"effectively final 的局部变量（捕获值），Python 闭包可以"改"外层变量（要 `nonlocal` 声明）——边界在于：Python 捕获的是绑定关系，且延迟到调用时才查值；
> 3. `global`/`nonlocal` 不是"导入变量"，而是给编译器声明"这个名字的赋值发生在别的作用域"——没有赋值就不需要声明。

## 6.3 正式原理与准确术语

**默认参数（default parameter）**：在 `def` 执行时**求值一次**，存进 `函数对象.__defaults__`，之后所有调用共享——这是"可变默认值陷阱"的根因，也是"默认参数可以当缓存/固定值用"的原理。**可变位置参数（`*args`）**：多余的定位实参收进 tuple；**关键字可变参数（`**kwargs`）**：多余的关键字实参收进 dict。**keyword-only 参数**：`*` 之后的参数只能按关键字传，强制调用方写出参数名（API 演进友好，对应 Java Builder 的显式性）。**LEGB**：名字查找顺序 Local（函数内）→ Enclosing（外层函数）→ Global（模块级）→ Built-in（内建）。**闭包（closure）**：内层函数引用了外层作用域变量，且外层函数返回后该变量仍然存活（存在函数的 `__closure__` 单元里）。

Java↔Python 函数签名对照：

| 需求 | Java 惯用 | Python 惯用 |
|---|---|---|
| 可选参数 | 方法重载 / Builder | 默认参数 |
| 不定个数参数 | `String... args` | `*args` |
| "可选配置项"很多 | Builder 模式 | keyword-only + 默认值 |
| 命名传参 | 不支持（链式 setter 模拟） | `f(timeout=30, retries=2)` 原生支持 |

## 6.4 最小完整示例：可变默认参数陷阱

**EX-06-01 | examples/ch06_functions/ex_06_01_default_mutable.py（完整可运行）**

```python
# EX-06-01 | 可变默认参数陷阱 | 运行: python3 examples/ch06_functions/ex_06_01_default_mutable.py
def add_task_bad(task: str, tasks: list[str] = []) -> list[str]:
    tasks.append(task)      # 默认列表在 def 执行时创建一次，之后所有调用共享
    return tasks


def add_task_ok(task: str, tasks: list[str] | None = None) -> list[str]:
    if tasks is None:
        tasks = []          # 标准修复写法：哨兵 None，每次调用新建
    tasks.append(task)
    return tasks


def main() -> None:
    r1 = add_task_bad("a")
    r2 = add_task_bad("b")
    print(f"坏写法: r1 = {r1}")
    print(f"坏写法: r2 = {r2}（r1 也被改了）")
    print(f"两次返回同一个对象: {r1 is r2}")
    print(f"默认值本体被污染: {add_task_bad.__defaults__}")

    ok1 = add_task_ok("a")
    ok2 = add_task_ok("b")
    print(f"好写法: ok1 = {ok1}, ok2 = {ok2}")
    print(f"两次返回不同对象: {ok1 is not ok2}")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（Python 3.14.7）
坏写法: r1 = ['a', 'b']
坏写法: r2 = ['a', 'b']（r1 也被改了）
两次返回同一个对象: True
默认值本体被污染: (['a', 'b'],)
好写法: ok1 = ['a'], ok2 = ['b']
两次返回不同对象: True
```

## 6.5 逐段解释：签名三件套、LEGB、闭包与 lambda

**（1）`*args` / `**kwargs` 与 keyword-only**。`demo(a, b=2, *args, flag=False, **kwargs)` 的签名结构是：1 个必选位置参数、1 个默认位置参数、剩余位置进 `args` 元组、`flag` 及其后只能关键字传、剩余关键字进 `kwargs` 字典。调用处也可以反向解包：`f(*seq, **mapping)`。EX-06-02 里 `create_user(name, *, is_admin=False, timeout=30)` 是 API 设计的正例——布尔/数值参数强迫调用方写名字，调用点自解释，且未来加参数不会破坏位置兼容性。

**EX-06-02 | examples/ch06_functions/ex_06_02_args_kwargs.py（完整可运行）**

```python
# EX-06-02 | *args/**kwargs 与 keyword-only | 运行: python3 examples/ch06_functions/ex_06_02_args_kwargs.py
def demo(a: int, b: int = 2, *args: int, flag: bool = False, **kwargs: object) -> None:
    print(f"a = {a}, b = {b}")
    print(f"args = {args}")
    print(f"flag = {flag}")
    print(f"kwargs = {kwargs}")


def create_user(name: str, *, is_admin: bool = False, timeout: int = 30) -> str:
    """* 之后的参数只能按关键字传递（keyword-only）。"""
    role = "admin" if is_admin else "user"
    return f"{name}({role}, timeout={timeout})"


def main() -> None:
    demo(1, 20, 30, 40, flag=True, extra="hello")
    print("-" * 40)

    seq = [10, 20, 30]
    mapping = {"flag": True, "extra": "解包传入"}
    demo(*seq, **mapping)          # 调用处解包
    print("-" * 40)

    print(create_user("alice"))
    print(create_user("bob", is_admin=True, timeout=60))

    # keyword-only 参数按位置传 -> TypeError
    try:
        create_user("carol", True)
    except TypeError as exc:
        print(f"按位置传 keyword-only 参数 -> TypeError: {exc}")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（Python 3.14.7）
a = 1, b = 20
args = (30, 40)
flag = True
kwargs = {'extra': 'hello'}
----------------------------------------
a = 10, b = 20
args = (30,)
flag = True
kwargs = {'extra': '解包传入'}
----------------------------------------
alice(user, timeout=30)
bob(admin, timeout=60)
按位置传 keyword-only 参数 -> TypeError: create_user() takes 1 positional argument but 2 were given
```

**（2）LEGB 与 `global`/`nonlocal`**。**读**外层名字不需要任何声明（EX-06-03 的 `inner` 直接读到三层外的 `x`）；**写**（赋值）会让 Python 把该名字当作当前作用域的局部变量——于是"先读后写"直接 `UnboundLocalError`。要在全局赋值用 `global`，要在 enclosing 作用域赋值用 `nonlocal`。这与 Java 的块级作用域不同：Java 的 `{}` 内变量随块销毁，Python 的函数/类才产生新作用域，`if`/`for` 块**不产生**作用域。

**EX-06-03 | examples/ch06_functions/ex_06_03_legb.py（完整可运行）**

```python
# EX-06-03 | LEGB 与 global/nonlocal | 运行: python3 examples/ch06_functions/ex_06_03_legb.py
from collections.abc import Callable

counter_global: int = 0


def demo_legb() -> None:
    x: str = "local"               # Local（对 demo_legb 而言）

    def enclosing_fn() -> str:
        y: str = "enclosing"       # Enclosing

        def inner() -> str:
            z: str = "inner"       # Local（对 inner 而言）
            return f"{x}/{y}/{z}"  # 查找顺序 L -> E -> G -> B

        return inner()

    print(f"内层函数读到的名字: {enclosing_fn()}")


def read_global() -> int:
    return counter_global          # 只读全局：不需要声明


def bump_global_wrong() -> None:
    try:
        counter_global = counter_global + 1   # 出现赋值 -> Python 把它当局部变量
    except UnboundLocalError as exc:
        print(f"未声明 global 就赋值 -> UnboundLocalError: {exc}")


def bump_global_right() -> None:
    global counter_global
    counter_global += 1


def make_accumulator() -> Callable[[int], int]:
    total = 0

    def add(n: int) -> int:
        nonlocal total             # 声明"我要改外层函数的 total"
        total += n
        return total

    return add


def main() -> None:
    demo_legb()
    print(f"read_global(): {read_global()}")
    bump_global_wrong()
    bump_global_right()
    bump_global_right()
    print(f"global 计数: {counter_global}")

    acc = make_accumulator()
    print(f"acc(3) = {acc(3)}，acc(4) = {acc(4)}（闭包记住同一个 total）")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（Python 3.14.7）
内层函数读到的名字: local/enclosing/inner
read_global(): 0
未声明 global 就赋值 -> UnboundLocalError: cannot access local variable 'counter_global' where it is not associated with a value
global 计数: 2
acc(3) = 3，acc(4) = 7（闭包记住同一个 total）
```

**（3）闭包与延迟绑定坑**。循环里创建 lambda，三个闭包**共享同一个循环变量 `i`**——调用发生在循环结束后，读到的自然都是 2。修复思路是"在创建时把当时的值固定下来"：利用默认参数在 `def` 时求值一次的特性写 `lambda i=i: i`，或者用 `functools.partial`。`__closure__` 属性可以直观看到闭包捕获的内容，EX-06-04 里 `double.__closure__` 捕获的就是 `[2]`。

**EX-06-04 | examples/ch06_functions/ex_06_04_closure_late_binding.py（完整可运行）**

```python
# EX-06-04 | 闭包与延迟绑定经典坑 | 运行: python3 examples/ch06_functions/ex_06_04_closure_late_binding.py
from collections.abc import Callable


def make_functions_bad() -> list[Callable[[], int]]:
    fns: list[Callable[[], int]] = []
    for i in range(3):
        fns.append(lambda: i)      # 闭包捕获的是变量 i 本身，不是"当时的值"
    return fns


def make_functions_ok() -> list[Callable[[], int]]:
    fns: list[Callable[[], int]] = []
    for i in range(3):
        fns.append(lambda i=i: i)  # 默认参数在 def 时求值：把"当时的值"固定下来
    return fns


def multiplier(factor: int) -> Callable[[int], int]:
    """闭包的基本形态：记住定义时所处作用域里的变量。"""
    return lambda n: n * factor


def main() -> None:
    bad = make_functions_bad()
    print(f"坏写法: {[f() for f in bad]}   # 循环结束后 i = 2，三个闭包共享同一个 i")

    ok = make_functions_ok()
    print(f"好写法: {[f() for f in ok]}   # 每个闭包固定住各自的 i")

    double = multiplier(2)
    triple = multiplier(3)
    print(f"double(5) = {double(5)}，triple(5) = {triple(5)}")

    cells = [c.cell_contents for c in double.__closure__]
    print(f"double.__closure__ 捕获的内容: {cells}")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（Python 3.14.7）
坏写法: [2, 2, 2]   # 循环结束后 i = 2，三个闭包共享同一个 i
好写法: [0, 1, 2]   # 每个闭包固定住各自的 i
double(5) = 10，triple(5) = 15
double.__closure__ 捕获的内容: [2]
```

**（4）lambda 的适用与滥用**。lambda 是"单表达式匿名函数"，正确定位是**作为参数传递的小函数**：排序 key、`map`/`filter`、回调。两个滥用要避免：给 lambda 起名字（PEP 8 明确不推荐，用 `def`）；把复杂逻辑塞进嵌套三元的 lambda（可读性灾难，EX-06-05 里给的就是反面示范）。

**EX-06-05 | examples/ch06_functions/ex_06_05_lambda.py（完整可运行）**

```python
# EX-06-05 | lambda 的适用与滥用 | 运行: python3 examples/ch06_functions/ex_06_05_lambda.py
from collections.abc import Callable


def main() -> None:
    users: list[dict[str, object]] = [
        {"name": "alice", "age": 32},
        {"name": "bob", "age": 25},
        {"name": "carol", "age": 29},
    ]

    # 适用场景 1：作为 key 函数传给 sorted / max / min
    by_age = sorted(users, key=lambda u: u["age"])
    ages = [u["age"] for u in by_age]
    print(f"按年龄排序后的年龄序列: {ages}")

    # 适用场景 2：作为一次性小函数传给 map / filter（多数时候推导式更清晰）
    squares: list[int] = list(map(lambda n: n * n, range(5)))
    evens: list[int] = list(filter(lambda n: n % 2 == 0, range(10)))
    print(f"map: {squares}，filter: {evens}")

    # 滥用 1：给 lambda 起名字（PEP 8 明确不推荐）——需要复用就用 def
    # increment = lambda x: x + 1   <- 反例，不这么写
    def increment(x: int) -> int:
        return x + 1

    print(f"需要复用的函数用 def: increment(1) = {increment(1)}")

    # 滥用 2：把复杂逻辑塞进 lambda（只能写单表达式，可读性差）
    classify: Callable[[int], str] = (
        lambda s: "通过" if s >= 60 else ("补考" if s >= 40 else "重修")
    )
    print(f"嵌套三元 lambda: classify(50) = {classify(50)}   # 能看懂，但别这么写")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（Python 3.14.7）
按年龄排序后的年龄序列: [25, 29, 32]
map: [0, 1, 4, 9, 16]，filter: [0, 2, 4, 6, 8]
需要复用的函数用 def: increment(1) = 2
嵌套三元 lambda: classify(50) = 补考   # 能看懂，但别这么写
```

## 6.6 安装/文件位置/运行命令

- **依赖**：仅标准库（`collections.abc`），无新增安装。
- **文件位置**：`examples/ch06_functions/`（5 个示例）；测试 `tests/test_ch06.py`。
- **运行命令**：

```bash
cd /workspace/ai_application_course
python3 examples/ch06_functions/ex_06_01_default_mutable.py
python3 -m pytest tests/test_ch06.py -q
```

## 6.7 常见错误与排查

1. **`TypeError: create_user() takes 1 positional argument but 2 were given`**——给 keyword-only 参数按位置传值。这不是 bug，是签名在保护你；修复：按关键字 `create_user("carol", is_admin=True)`。
2. **`UnboundLocalError: cannot access local variable 'x' where it is not associated with a value`**——函数内对全局/外层变量赋值，导致它被编译成局部变量，而赋值前又读了它。修复：确实要改外层就加 `global`/`nonlocal`；若只是想读，删掉赋值语句。
3. **`TypeError: f() got multiple values for argument 'a'`**——同一个参数既收到位置实参又收到关键字实参（`f(1, a=2)`）。修复：统一传参方式；封装第三方 API 时用 `*args, **kwargs` 透传可避免硬编码参数位。
4. **可变默认值"幽灵共享"**（无报错）——EX-06-01 的场景。修复：哨兵 `None` + 函数体内新建；需要"跨调用累积"这个特性时请显式把容器作为参数传入，让共享可见。
5. **循环里注册回调全部拿到最后一个值**（无报错）——EX-06-04 的延迟绑定。修复：`lambda i=i: ...` 默认参数固定，或 `functools.partial(fn, i)`。

## 6.8 企业场景中的使用方式（Spring Boot 视角）

- **FastAPI 依赖注入**：`def handler(q: str | None = None, *, db: Session = Depends(get_db))` 的签名风格正是"默认参数 + keyword-only"组合；`**kwargs` 用于向 OpenAI 兼容 SDK 透传厂商私有参数（如 `extra_body`），但要白名单校验防注入。
- **工具函数库设计**：给 AI 编排写工具函数时，把"会演进的配置"全部设计成 keyword-only（`def search(query: str, *, top_k: int = 5, threshold: float = 0.7)`），调用点像 Java Builder 一样自解释，且新增参数不破坏存量调用。
- **装饰器的地基**：闭包是 ch10 装饰器的实现原理；"延迟绑定"坑在装饰器参数化（`@retry(times=3)`）里会再次出现，届时用同样的"默认参数固定"手法。
- **与 Java 线程池对照**：给线程池提交任务时 Java 需要小心捕获 effectively final；Python 侧提交闭包到 `ThreadPoolExecutor` 反而要**小心变量被并发重绑**——同一份变量，两种语言各有一个方向的坑。

## 6.9 练习

1. **（基础）**`def f(x, y=1, *args, z, **kwargs)` 这个签名里哪些参数可以按位置传？`z` 怎么传？调用 `f(1, 2, 3, 4, z=5, extra=6)` 时各变量分别是什么？
2. **（基础）**下面函数调用两次后返回什么？为什么？`def acc(n, box=[]): box.append(n); return box`。
3. **（代码）**写 `def make_greeters(*names) -> list[Callable[[], str]]`：返回一组"问候函数"，每个函数返回 `"你好, {name}"`；要求修复延迟绑定问题（每个 greeter 记住自己的 name）。
4. **（代码）**把 Java Builder 风格的调用 `new HttpOptions.Builder().timeout(30).retries(2).build()` 翻译成一个 Python 函数签名与调用（要求所有配置项 keyword-only）。
5. **（调试题）**下面的代码期望两次打印出不同的时间戳，实际输出什么？为什么？如何修复？

```python
import time

def schedule(msg: str, when: float = time.time()):
    print(f"{msg} @ {when:.0f}")

schedule("a")
time.sleep(1)
schedule("b")
```

### 参考答案

<details>
<summary>点开查看参考答案</summary>

1. `x`、`y` 可按位置传；`z` 是 keyword-only 必须写 `z=5`。结果：`x=1, y=2, args=(3, 4), z=5, kwargs={'extra': 6}`。
2. 返回共享的 `['a', 'b']`（若两次分别传 `"a"`、`"b"`）。默认列表在 def 时创建一次，所有未传 `box` 的调用共享同一个对象——与 EX-06-01 同根因。
3. `return [lambda name=name: f"你好, {name}" for name in names]`（默认参数固定当前 name）。
4. `def build_http_options(*, timeout: int = 30, retries: int = 2) -> HttpOptions: ...`，调用 `build_http_options(timeout=30, retries=2)`。可选：内部仍返回 frozen dataclass 保持"构建后不可变"。
5. 两次打印**同一个**时间戳（第一次 `def` 执行时求值并永久固定，隔 1 秒的第二次调用不会重新执行 `time.time()`）。默认值只在 def 时求值一次。修复：`when: float | None = None`，函数体内 `if when is None: when = time.time()`。

</details>

## 6.10 自测检查表

- 我能画出 `def f(a, b=1, *args, c, **kwargs)` 的五段式签名结构并正确调用它。
- 我能解释可变默认参数为什么共享（def 时求值一次），并用 `__defaults__` 演示。
- 我能说出 LEGB 四层含义，并解释"赋值让名字变局部"导致 UnboundLocalError 的机制。
- 我能写出用 `nonlocal` 实现的计数器闭包，并解释它与 Java effectively final 的差异。
- 我能识别并修复循环创建 lambda 的延迟绑定坑（至少两种方法）。
- 我能判断一段代码里该用 lambda 还是 def（复用性、可读性）。

## 6.11 面试追问

1. **[模拟题] Python 为什么会有可变默认参数这个"特性"而不是报错？**——参考回答：默认值在 def 时求值一次是语言的统一规则（lambda 捕获、装饰器参数都依赖它），函数对象的 `__defaults__` 让这一行为完全可见可预测；语言选择了"机制透明"而不是"特判可变对象"。工程上用 `None` 哨兵 + lint（如 ruff 的 B006 规则）防呆。
2. **[模拟题] 闭包捕获的是值还是变量？和 Java lambda 的本质区别？**——参考回答：Python 捕获变量（绑定），调用时才解引用，所以有延迟绑定现象，也可以用 `nonlocal` 写；Java lambda 捕获值，要求 effectively final，本质是"快照"。追问：如何让 Python 闭包表现成"捕获值"（默认参数/partial）。
3. **[模拟题] 什么场景必须用 `**kwargs`？什么场景它是坏味道？**——参考回答：必须：代理/装饰器透传签名、SDK 兼容多版本参数。坏味道：业务函数用 `**kwargs` 隐藏参数，调用方失去 IDE 提示与静态检查——签名要显式，透传层才允许 `**kwargs`。

### 待核实

- ruff/mypy 对可变默认值的具体检查规则编号（如 B006）以所用版本官方文档为准，本书未在沙箱中安装 lint 工具验证。

---

# 第 7 章 面向对象：类、魔术方法、property、dataclass 与 Protocol

> **本章目标**：掌握 Python 类模型的关键细节（`__init__` 的准确角色、类属性 vs 实例属性），会用魔术方法、`@property`、`@dataclass`，会用 Protocol 表达"结构化接口"。
> **前置知识**：ch04（对象模型）、ch05（可哈希性）、ch06（作用域）。
> **学完你能做什么**：写出与 Spring 服务层风格对接的业务类；用 dataclass 承载 AI 场景的配置与消息结构；用 Protocol 解耦"我们需要的接口"与"别人提供的实现"。

## 7.1 真实问题引入：把 Spring 的三层结构"翻译"过来翻了车

Java 工程师把一个文档问答服务的领域层翻译成 Python（合成案例），踩了四个坑：① 用 `__int__` 当构造器名（少一个字母），实例化时报 `TypeError: Order() takes no arguments`；② 把"部门成员列表"写成类属性 `members = []`，所有实例共享一份，A 部门加人 B 部门也看得见（对照 ch04 的可变类属性）；③ 想给 Java 式 getter/setter 全套补齐，写了一堆 `get_xxx()`，Python 评审意见是"先写属性，需要拦截时再上 property"；④ 给"可检索"能力定义了继承体系，结果第三方类无法接入——该用 Protocol 而不是继承。本章按"类模型 → 魔术方法 → property → dataclass → 组合 vs 继承 → Protocol"逐个拆解。

## 7.2 一句话解释 + 生活类比 + 类比边界

**一句话解释**：Python 类的实例通过 `__init__` 完成属性初始化（对象分配在更底层的 `__new__`）；类属性在类上只有一份、实例属性每个对象一份；对象行为大量通过魔术方法（`__len__`、`__eq__`……）接进语言协议；接口约束可以用"结构化"的 Protocol 表达——长得像就行，不用声明继承。

**生活类比**：类是图纸，实例是按图纸造的房子；类属性是"小区公告栏"（全小区一份），实例属性是"各家的门牌"；魔术方法像"给房子预留的水电气接口"，接对了，城市管网（语言内建函数）才能供水供电。

> 💡 类比边界：
> 1. `__init__` ≠ Java 构造器：Java 的 `new` 一步完成"分配+构造+初始化"，Python 里对象分配由更底层的 `__new__` 负责（只有不可变类型定制、单例等元编程场景才需要重写它，日常只重写 `__init__`），`__init__` 只负责把属性绑到 self 上——准确说法是"初始化器"不是"构造器"；
> 2. `@property` ↔ Java getter/setter 只像一半：Java 是"处处 getter/setter"的惯例，Python 是"先直接暴露属性，出现校验/派生需求时再升级为 property"——调用方代码不用改（`t.celsius = 100` 前后语法一致）；
> 3. Protocol ↔ Java interface 只像一半：Java interface 要类**显式 `implements`** 且 JVM 运行时可校验；Protocol 是**结构化**的（有方法就满足），静态检查器（mypy/pyright）在类型检查时校验，**运行时默认不校验**（`@runtime_checkable` 只能检查方法存在性，不检查签名/类型）。

## 7.3 正式原理与准确术语

**类属性（class attribute）与实例属性（instance attribute）**：类属性定义在类体、存于类的命名空间，所有实例共享；实例属性在 `__init__`（或其他时机）绑定到 `self.__dict__`。**属性查找顺序**：实例 `__dict__` → 类及其 MRO（方法解析顺序）→ 触发 `__getattr__`（若有）。**魔术方法（magic method / dunder method）**：双下划线包裹的方法，Python 通过它们把自定义对象接入语言协议——`len()` 找 `__len__`、`for` 找 `__iter__`/`__getitem__`、`==` 找 `__eq__`、`hash()` 找 `__hash__`。**dataclass**：`@dataclass` 装饰器按类注解字段自动生成 `__init__`/`__repr__`/`__eq__` 等。**Protocol（结构化子类型，structural subtyping）**：`typing.Protocol` 定义"需要哪些方法"的静态契约，任何具备这些方法的类都隐式满足。

Java↔Python 面向对象对照：

| Java | Python | 关键差异 |
|---|---|---|
| 构造器 `new Xxx()` | `Xxx()` 触发 `__new__`+`__init__` | `__init__` 只初始化，不分配 |
| static 字段 | 类属性 | Python 实例可"遮蔽"类属性（只影响自己） |
| `equals`/`hashCode` | `__eq__`/`__hash__` | 定义 `__eq__` 后 `__hash__` 被置 None，需显式定义 |
| `interface` + `implements` | `Protocol`（结构化） | 无需声明实现；运行时默认不校验 |
| Lombok `@Data` / record | `@dataclass` | record 不可变；dataclass 默认可变，`frozen=True` 才不可变 |
| getter/setter 惯例 | `@property` | 调用方语法不因加 property 而改变 |

## 7.4 最小完整示例：类与实例、类属性 vs 实例属性

**EX-07-01 | examples/ch07_classes/ex_07_01_class_basics.py（完整可运行）**

```python
# EX-07-01 | 类与实例、实例属性 vs 类属性 | 运行: python3 examples/ch07_classes/ex_07_01_class_basics.py
class Order:
    """订单示例：演示实例属性与类属性。"""

    tax_rate: float = 0.06          # 类属性：所有实例共享（类似 Java 的 static 字段）
    _seq: int = 0

    def __init__(self, item: str, amount: float) -> None:
        self.item = item            # 实例属性：每个对象一份（在 __init__ 里绑定到 self）
        self.amount = amount
        Order._seq += 1
        self.seq = Order._seq

    def with_tax(self) -> float:
        return self.amount * (1 + self.tax_rate)


def main() -> None:
    o1 = Order("键盘", 300.0)
    o2 = Order("鼠标", 150.0)
    print(f"o1 应付 {o1.with_tax():.2f}，o2 应付 {o2.with_tax():.2f}")

    # 类属性通过类或实例都可读
    print(f"Order.tax_rate = {Order.tax_rate}，o1.tax_rate = {o1.tax_rate}")

    # 通过实例赋值只是"新建实例属性遮住类属性"，不改类本身
    o1.tax_rate = 0.0               # o1 从此有了自己的 tax_rate
    print(f"遮蔽后: o1.tax_rate = {o1.tax_rate}，o2.tax_rate = {o2.tax_rate}，Order.tax_rate = {Order.tax_rate}")
    del o1.tax_rate                 # 删掉遮蔽，重新看到类属性
    print(f"删除遮蔽后 o1.tax_rate = {o1.tax_rate}")

    # 可变类属性的共享坑（对照 ch04 的引用语义）
    class Cart:
        items: list[str] = []       # 反例：所有购物车共享同一个列表

    c1, c2 = Cart(), Cart()
    c1.items.append("书")
    print(f"可变类属性被共享: c2.items = {c2.items}")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（Python 3.14.7）
o1 应付 318.00，o2 应付 159.00
Order.tax_rate = 0.06，o1.tax_rate = 0.06
遮蔽后: o1.tax_rate = 0.0，o2.tax_rate = 0.06，Order.tax_rate = 0.06
删除遮蔽后 o1.tax_rate = 0.06
可变类属性被共享: c2.items = ['书']
```

## 7.5 逐段解释：魔术方法、property、dataclass、组合与 Protocol

**（1）魔术方法：把对象接进语言协议**。EX-07-02 的 `Playlist` 实现了五个方法：`__len__` 让 `len(p)` 可用；`__getitem__` 让 `p[i]` 可用（顺带获得迭代能力）；`__iter__` 显式定义迭代行为；`__repr__` 决定调试显示（教程代码一律优先实现它，`print` 列表里嵌套对象时才有可读输出）；`__eq__`/`__hash__` 成对出现——**只定义 `__eq__` 不定义 `__hash__`，类会失去哈希能力**（Python 把 `__hash__` 置为 None），放进 set 会得到 `TypeError: unhashable type: 'Playlist'`。`__eq__` 返回 `NotImplemented`（不是 `False`！）表示"我与这个类型没法比，请让对方试一试或退回默认"。

**EX-07-02 | examples/ch07_classes/ex_07_02_magic_methods.py（完整可运行）**

```python
# EX-07-02 | 魔术方法 | 运行: python3 examples/ch07_classes/ex_07_02_magic_methods.py
from collections.abc import Iterator


class Playlist:
    """一个支持 len、下标、迭代、相等性的播放列表。"""

    def __init__(self, name: str, songs: list[str] | None = None) -> None:
        self.name = name
        # 注意 list(songs) 做了一次拷贝，避免与调用者的列表共享（对照 ch04）
        self._songs: list[str] = list(songs) if songs else []

    def add(self, song: str) -> None:
        self._songs.append(song)

    def __len__(self) -> int:                    # 支持 len(p)
        return len(self._songs)

    def __getitem__(self, index: int) -> str:    # 支持 p[i]，同时让对象可迭代
        return self._songs[index]

    def __iter__(self) -> Iterator[str]:         # 支持 for song in p
        return iter(self._songs)

    def __repr__(self) -> str:                   # 支持 repr(p)，调试显示也用它
        return f"Playlist({self.name!r}, songs={self._songs!r})"

    def __eq__(self, other: object) -> bool:     # 支持 p == q
        if not isinstance(other, Playlist):
            return NotImplemented
        return self.name == other.name and self._songs == other._songs

    def __hash__(self) -> int:                   # 定义了 __eq__ 就必须显式定义 __hash__ 才能进 set/dict
        return hash((self.name, tuple(self._songs)))


def main() -> None:
    p = Playlist("工作歌单", ["Env", "Beyond"])
    p.add("Focus")
    print(f"repr  -> {p!r}")
    print(f"len   -> {len(p)}")
    print(f"p[0]  -> {p[0]}，p[-1] -> {p[-1]}")
    print(f"迭代  -> {[s for s in p]}")

    q = Playlist("工作歌单", ["Env", "Beyond", "Focus"])
    print(f"p == q: {p == q}，p is q: {p is q}")
    print(f"hash(p) == hash(q): {hash(p) == hash(q)}")
    print(f"放进 set 去重后元素个数: {len({p, q})}")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（Python 3.14.7）
repr  -> Playlist('工作歌单', songs=['Env', 'Beyond', 'Focus'])
len   -> 3
p[0]  -> Env，p[-1] -> Focus
迭代  -> ['Env', 'Beyond', 'Focus']
p == q: True，p is q: False
hash(p) == hash(q): True
放进 set 去重后元素个数: 1
```

**（2）`@property`：把方法伪装成属性**。EX-07-03 中 `celsius` 用 property + setter 封装校验（低于绝对零度抛 `ValueError`），`fahrenheit` 是只有 getter 的派生属性。对调用方而言语法始终是属性访问——这正是与 Java getter/setter 的最大差别：**升级为 property 不破坏调用方代码**。构造函数里 `self.celsius = celsius` 也会走 setter，校验自动覆盖构造路径。

**EX-07-03 | examples/ch07_classes/ex_07_03_property.py（完整可运行）**

```python
# EX-07-03 | @property | 运行: python3 examples/ch07_classes/ex_07_03_property.py
class Temperature:
    """摄氏度存储，华氏度以只读 property 派生。"""

    def __init__(self, celsius: float) -> None:
        self.celsius = celsius       # 走下面的 setter，构造时同样校验

    @property
    def celsius(self) -> float:
        return self._celsius

    @celsius.setter
    def celsius(self, value: float) -> None:
        if value < -273.15:
            raise ValueError(f"温度低于绝对零度: {value}")
        self._celsius = float(value)

    @property
    def fahrenheit(self) -> float:   # 只读派生属性：只有 getter
        return self._celsius * 9 / 5 + 32


def main() -> None:
    t = Temperature(25.0)
    print(f"25 摄氏度 = {t.fahrenheit:.1f} 华氏度")

    t.celsius = 100                  # 像属性一样赋值，实际触发 setter
    print(f"100 摄氏度 = {t.fahrenheit:.1f} 华氏度")

    try:
        t.celsius = -300
    except ValueError as exc:
        print(f"非法赋值 -> ValueError: {exc}")

    # 派生属性只读：不能直接赋值
    try:
        t.fahrenheit = 32.0
    except AttributeError as exc:
        print(f"给只读 property 赋值 -> AttributeError: {exc}")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（Python 3.14.7）
25 摄氏度 = 77.0 华氏度
100 摄氏度 = 212.0 华氏度
非法赋值 -> ValueError: 温度低于绝对零度: -300
给只读 property 赋值 -> AttributeError: property 'fahrenheit' of 'Temperature' object has no setter
```

**（3）`@dataclass`：AI 场景的主力结构**。`@dataclass` 按字段注解自动生成 `__init__`、`__repr__`、`__eq__`。三条硬规则：① **可变默认值必须写 `field(default_factory=list)`**，直接写 `= []` 会在类定义时抛 `ValueError`（dataclass 帮你把 ch06 的陷阱堵死了一半）；② `__post_init__` 做"构造后的统一加工"（校验、派生字段），配合 `field(init=False)` 承载不在构造参数里的字段；③ `frozen=True` 得到不可变实例，因此可哈希、可放心做共享配置——对应 Java record 的"浅不可变"语义（字段引用的对象仍可能可变，与 4.5 的 tuple 同理）。

**EX-07-04 | examples/ch07_classes/ex_07_04_dataclass.py（完整可运行）**

```python
# EX-07-04 | @dataclass | 运行: python3 examples/ch07_classes/ex_07_04_dataclass.py
from dataclasses import asdict, dataclass, field


@dataclass
class ChatMessage:
    role: str
    content: str
    tokens: int = 0


@dataclass
class Conversation:
    title: str
    tags: list[str] = field(default_factory=list)     # 可变默认值必须用 default_factory
    messages: list[ChatMessage] = field(default_factory=list)
    turn: int = field(init=False, default=0)          # 不进 __init__ 的派生字段

    def __post_init__(self) -> None:
        """__init__ 之后的统一加工（校验/派生）。"""
        if not self.title.strip():
            raise ValueError("标题不能为空")
        self.turn = len(self.messages)

    def append(self, msg: ChatMessage) -> None:
        self.messages.append(msg)
        self.turn = len(self.messages)


@dataclass(frozen=True)
class ModelConfig:
    """frozen=True：不可变（浅），因此可哈希。"""
    model: str
    temperature: float = 0.7


def main() -> None:
    conv = Conversation(title="排障会话", tags=["prod"])
    conv.append(ChatMessage("user", "服务 502 了"))
    conv.append(ChatMessage("assistant", "先看网关日志", tokens=18))
    print(f"自动生成的 __repr__: {conv!r}")

    other = Conversation(title="排障会话", tags=["prod"])
    print(f"自动生成的 __eq__: conv == other -> {conv == other}（conv 多两条消息）")

    c1 = ModelConfig(model="gpt-demo", temperature=0.2)
    c2 = ModelConfig(model="gpt-demo", temperature=0.2)
    print(f"frozen 实例值相等: {c1 == c2}，可哈希: {hash(c1) == hash(c2)}")
    try:
        c1.temperature = 0.9
    except Exception as exc:  # dataclasses.FrozenInstanceError（AttributeError 的子类）
        print(f"修改 frozen 实例 -> {type(exc).__name__}: {exc}")

    print(f"asdict: {asdict(conv)}")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（Python 3.14.7）
自动生成的 __repr__: Conversation(title='排障会话', tags=['prod'], messages=[ChatMessage(role='user', content='服务 502 了', tokens=0), ChatMessage(role='assistant', content='先看网关日志', tokens=18)], turn=2)
自动生成的 __eq__: conv == other -> False（conv 多两条消息）
frozen 实例值相等: True，可哈希: True
修改 frozen 实例 -> FrozenInstanceError: cannot assign to field 'temperature'
asdict: {'title': '排障会话', 'tags': ['prod'], 'messages': [{'role': 'user', 'content': '服务 502 了', 'tokens': 0}, {'role': 'assistant', 'content': '先看网关日志', 'tokens': 18}], 'turn': 2}
```

> ⚠️ 常见坑：dataclass ↔ Java record/Lombok 的**不等价清单**——record 天生不可变且字段即 API；dataclass 默认可变，要 `frozen=True` 才等价；dataclass 的 `eq=True` 生成的 `__eq__` 不自动维护 `__hash__`（unfrozen 时哈希按身份），frozen+eq 才生成 `__hash__`；"带运行时校验的 DTO"请直接看 Pydantic `BaseModel`（ch16），dataclass 不做类型校验。

**（4）继承 vs 组合**。继承只用于**真 is-a** 且要复用多态的场景（EX-07-05 的检索器覆写）；"服务需要某个能力"一律组合——`AnswerPipeline` 持有 `retriever` 并接受一个可替换的重排函数，换实现不改管道代码。这与 Spring 的构造器注入思想一致：**依赖注入本质上是组合**，Java 里我们早就不用继承组装服务了，Python 同理。

**EX-07-05 | examples/ch07_classes/ex_07_05_inheritance_composition.py（完整可运行）**

```python
# EX-07-05 | 继承 vs 组合 | 运行: python3 examples/ch07_classes/ex_07_05_inheritance_composition.py
from collections.abc import Callable


# --- 继承：只在 is-a 关系上使用 ---
class Retriever:
    def search(self, query: str) -> list[str]:
        return [f"命中({query}-1)", f"命中({query}-2)"]


class KeywordRetriever(Retriever):
    def search(self, query: str) -> list[str]:      # 覆写：先按父类逻辑再过滤
        base = super().search(query)
        return [h for h in base if query in h] or base


# --- 组合：has-a / 可替换部件用组合（多数业务场景的正确选择） ---
class AnswerPipeline:
    def __init__(
        self,
        retriever: Retriever,
        rerank: Callable[[list[str]], list[str]] | None = None,
    ) -> None:
        self.retriever = retriever                  # 持有部件，而不是继承部件
        self.rerank = rerank

    def answer_contexts(self, query: str) -> list[str]:
        hits = self.retriever.search(query)
        if self.rerank is not None:
            hits = self.rerank(hits)
        return hits[:2]


def main() -> None:
    kr = KeywordRetriever()
    print(f"继承+覆写: {kr.search('订单超时')}")

    pipeline = AnswerPipeline(kr, rerank=lambda hits: list(reversed(hits)))
    print(f"组合可插拔: {pipeline.answer_contexts('订单超时')}")

    # 换一个实现，管道代码一行不改（多态来自"鸭子类型+一致的方法名"）
    class EmptyRetriever(Retriever):
        def search(self, query: str) -> list[str]:
            return []

    empty_pipeline = AnswerPipeline(EmptyRetriever())
    print(f"替换部件: {empty_pipeline.answer_contexts('任意')}（检索为空则上下文为空）")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（Python 3.14.7）
继承+覆写: ['命中(订单超时-1)', '命中(订单超时-2)']
组合可插拔: ['命中(订单超时-2)', '命中(订单超时-1)']
替换部件: []（检索为空则上下文为空）
```

**（5）Protocol：不需要 `implements` 的接口**。EX-07-06 的 `render` 函数类型上要求 `Summarizable`，但 `LogSnippet`、`Article` 与它毫无继承关系——只要有 `summarize` 方法就满足协议（结构化子类型）。**与 Java interface 的边界要背下来**：Java 在编译期+运行时都校验 `implements`；Protocol 的校验发生在静态检查阶段（mypy/pyright），运行时 `isinstance` 检查需要 `@runtime_checkable` 且**只检查方法名存在**，不检查签名与参数类型——所以"运行时安全"仍要靠调用时的异常或显式校验。

**EX-07-06 | examples/ch07_classes/ex_07_06_protocol.py（完整可运行）**

```python
# EX-07-06 | Protocol 结构化子类型 | 运行: python3 examples/ch07_classes/ex_07_06_protocol.py
from typing import Protocol, runtime_checkable


@runtime_checkable
class Summarizable(Protocol):
    """只要"长得像"（有 summarize 方法）就算实现，无需继承或声明。"""

    def summarize(self) -> str: ...


class LogSnippet:                           # 没有继承任何东西
    def __init__(self, text: str) -> None:
        self.text = text

    def summarize(self) -> str:
        return self.text[:10] + "..."


class Article:
    def __init__(self, title: str, body: str) -> None:
        self.title, self.body = title, body

    def summarize(self) -> str:
        return self.title


def render(item: Summarizable) -> str:      # 类型上要求满足 Summarizable 协议
    return f"[摘要] {item.summarize()}"


def main() -> None:
    print(render(LogSnippet("这是一段很长的服务日志内容，包含堆栈信息")))
    print(render(Article("Python 对象模型", "正文略")))

    # runtime_checkable 让 isinstance 按"有没有该方法"判断（结构化检查）
    print(f"isinstance(LogSnippet 实例, Summarizable): {isinstance(LogSnippet('x'), Summarizable)}")

    class NoMethod:                          # 没有 summarize：不满足协议
        pass

    print(f"isinstance(NoMethod 实例, Summarizable): {isinstance(NoMethod(), Summarizable)}")
    try:
        render(NoMethod())
    except AttributeError as exc:
        print(f"塞进不满足协议的对象 -> AttributeError: {exc}")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（Python 3.14.7）
[摘要] 这是一段很长的服务日...
[摘要] Python 对象模型
isinstance(LogSnippet 实例, Summarizable): True
isinstance(NoMethod 实例, Summarizable): False
塞进不满足协议的对象 -> AttributeError: 'NoMethod' object has no attribute 'summarize'
```

## 7.6 安装/文件位置/运行命令

- **依赖**：仅标准库（`dataclasses`、`typing`、`collections.abc`），无新增安装。
- **文件位置**：`examples/ch07_classes/`（6 个示例）；测试 `tests/test_ch07.py`。
- **运行命令**：

```bash
cd /workspace/ai_application_course
python3 examples/ch07_classes/ex_07_04_dataclass.py
python3 -m pytest tests/test_ch07.py -q
```

## 7.7 常见错误与排查

1. **`TypeError: OrderTypo() takes no arguments`**——构造器拼错成 `__int__`（或写成普通方法），Python 找不到 `__init__` 就用无参默认初始化，于是"传了参数却不认"。修复：检查双下划线拼写（IDE 模板生成最稳）。
2. **`TypeError: OrderNoSelf.with_tax() takes 0 positional arguments but 1 was given`**——实例方法忘写 `self`，调用时解释器自动把实例当第一个参数传入。修复：方法第一个参数写 `self`；staticmethod 才不需要。
3. **`ValueError: mutable default <class 'list'> for field tags is not allowed: use default_factory`**——dataclass 字段直接写可变默认值（在**类定义时**就抛错，不是实例化时）。修复：`field(default_factory=list)`。
4. **`FrozenInstanceError: cannot assign to field 'temperature'`**——给 frozen dataclass 赋值。修复：需要变更就用 `dataclasses.replace(c, temperature=0.9)` 生成新实例，或去掉 frozen（要想清楚为什么）。
5. **`AttributeError: property 'fahrenheit' of 'Temperature' object has no setter`**——给只有 getter 的 property 赋值。修复：补 `@fahrenheit.setter`，或确认语义上就该只读。
6. **可变类属性被所有实例共享**（无报错）——EX-07-01 的 `Cart.items`。修复：把初始化移进 `__init__` 写 `self.items = []`。

## 7.8 企业场景中的使用方式（Spring Boot 视角）

- **消息与配置结构**：AI 应用的 `ChatMessage`、`RetrievalHit`、`ModelConfig` 首选 dataclass（frozen 用于配置，普通用于消息）；需要**运行时类型校验、JSON Schema、遗漏字段报错**时换 Pydantic `BaseModel`（ch16），二者是"纯数据结构"与"边界校验 DTO"的分工，不是替代关系。
- **服务层与依赖注入**：Spring 的 `@Service` + 构造器注入翻译到 Python 就是"普通类 + 构造参数传入依赖"；FastAPI 的 `Depends` 是框架级版本（ch17）。不要用继承组装服务。
- **工具接口（Tool 接口）**：给 Agent 写工具时用 Protocol 定义"工具需要什么"（name/description/execute），第三方工具类零侵入接入——这正是 LangChain 工具生态的解耦思路（ch39 实操）。
- **魔术方法即"隐式协议"**：给 RAG 文档块实现 `__len__`（字符数）、`__eq__`/`__hash__`（去重入库）后，Python 内建函数与集合框架直接可用——相当于 Java 里实现 `CharSequence`/`Comparable` 的收益，但语法成本低一个量级。

## 7.9 练习

1. **（基础）**`Order.tax_rate = 0.1` 与 `order1.tax_rate = 0.1` 分别改了什么？第三个实例会看到什么值？
2. **（基础）**一个类定义了 `__eq__` 却没定义 `__hash__`，把它放进 set 会发生什么？为什么 Python 要这样设计（提示：值相等对象应哈希一致）？
3. **（代码）**为 EX-07-04 的 `ChatMessage` 增加 `is_user` 派生 property（`role == "user"`）；再给 `Conversation` 增加 `total_tokens` property（对 messages 求和），并写出对应断言测试。
4. **（代码）**定义 `@dataclass(frozen=True)` 的 `Chunk`（doc_id, start, end, text），让两个内容相同的 `Chunk` 能在 set 中去重；演示 `replace` 生成"start+1"的新实例。
5. **（调试题）**下面的代码想统计"每个模型的调用次数"，但计数永远不对，请指出两处问题：

```python
@dataclass
class Stats:
    counts: dict[str, int] = {}

    def bump(self, model: str) -> None:
        counts[model] = counts.get(model, 0) + 1   # 第 2 处问题在这里
```

### 参考答案

<details>
<summary>点开查看参考答案</summary>

1. `Order.tax_rate = 0.1` 改的是**类属性**，所有实例（未遮蔽的）都看到 0.1；`order1.tax_rate = 0.1` 只是给 order1 建了同名**实例属性**遮蔽类属性，其他实例与类不受影响。第三个未遮蔽实例：前者看到 0.1，后者仍看类上当时的值。
2. 得到 `TypeError: unhashable type: '...'`。因为 Python 约定"相等的对象必须有相同的哈希"，而默认 `__hash__`（按身份）无法满足自定义值相等的语义，于是定义 `__eq__` 后自动把 `__hash__` 置为 None，宁可不可哈希也不给出错误的哈希语义。要进 set 需显式定义 `__hash__`。
3. 在 `ChatMessage` 内加 `@property def is_user(self) -> bool: return self.role == "user"`；`Conversation` 内加 `@property def total_tokens(self) -> int: return sum(m.tokens for m in self.messages)`；断言示例：`assert ChatMessage("user", "hi").is_user is True`、`assert conv.total_tokens == 18`（对 EX-07-04 的数据）。
4. `@dataclass(frozen=True) class Chunk: doc_id: str; start: int; end: int; text: str`——frozen+eq 自动生成按字段的 `__hash__`，相同内容的 Chunk 在 set 中只留一个；`dataclasses.replace(chunk, start=chunk.start + 1)` 返回新实例且原实例不变。
5. ① 可变默认值：`counts: dict[str, int] = {}` 会让**所有 Stats 实例共享同一个类级字典**（dataclass 对 dict 同样禁止——其实这段代码在类定义时就会抛 `ValueError: mutable default <class 'dict'>`，需改 `field(default_factory=dict)`）；② `counts[...]` 少了 `self.`，`__init__`/方法里读不到这个名字会 `NameError`（或意外命中类属性）。正确写法：`self.counts[model] = self.counts.get(model, 0) + 1`。

</details>

## 7.10 自测检查表

- 我能准确说出"`__init__` 是初始化器不是构造器"以及 `__new__` 的角色。
- 我能演示实例属性遮蔽类属性、`del` 撤销遮蔽，并指出可变类属性的共享风险。
- 我能实现 `__repr__`/`__eq__`/`__hash__`/`__len__`/`__getitem__`/`__iter__` 并说清各自的触发时机。
- 我能写出带 setter 校验与只读派生属性的 `@property`，并解释它对调用方的零侵入性。
- 我能正确使用 `field(default_factory=...)`、`field(init=False)`、`__post_init__`、`frozen=True`。
- 我能说出 Protocol 与 Java interface 的两条边界（无需 implements；运行时默认不校验签名）。

## 7.11 面试追问

1. **[模拟题] dataclass 和 Pydantic BaseModel 怎么选？**——参考回答：内部数据结构、无需运行时类型校验的场景用 dataclass（轻、快）；服务边界（请求/响应、读外部配置、LLM 结构化输出）用 Pydantic——它是运行时校验器不是 DTO 翻译（FACTS 红线：Pydantic ≠ DTO），代价是解析开销。追问：frozen dataclass 与 Pydantic 的 `model_config = ConfigDict(frozen=True)`。
2. **[模拟题] 为什么定义了 `__eq__` 还要定义 `__hash__`？**——参考回答：哈希协议要求"a == b 则 hash(a) == hash(b)"；自定义值相等打破了默认按身份的哈希语义，Python 选择把 `__hash__` 置 None（显式不可哈希）避免静默错误。工程上常见写法 `__hash__ = hash((f1, f2))` 且被哈希的字段必须不可变。
3. **[模拟题] 组合优于继承在 Python 里有什么特别之处？**——参考回答：Python 有鸭子类型，多态不依赖继承，"换实现"比 Java 更廉价（EX-07-05 换 EmptyRetriever 一行不改）；加上 Protocol 可以在静态层把"需要的形状"写清楚，继承的两大用途（复用实现、表达子类型）都有更好的替代，除非有清晰的 is-a 层次（如多种 Retriever 的公共骨架）。

### 待核实

- Protocol 的 `@runtime_checkable` 校验范围（仅方法存在性、非数据成员）在 Python 3.12/3.14 的行为以官方 `typing` 文档为准；本书只演示了方法存在性检查，未依赖更细的行为。
- dataclass 的 `slots=True`/`kw_only=True` 参数（3.10+）本章未展开，使用前请以 `dataclasses` 官方文档核实语义。

---

# 第 8 章 异常体系：EAFP、自定义异常、异常链与上下文管理器

> **本章目标**：掌握 Python 异常类层次与捕获语义，建立业务异常基类设计，会用 `raise ... from ...` 保留排查链路，会用 `with` 与 `contextlib` 管理资源。
> **前置知识**：ch03 的异常堆栈阅读法；ch07 的类（自定义异常就是普通类）。
> **学完你能做什么**：为 AI 服务设计"基础设施异常 / 业务异常"两层体系；把底层 SDK 异常翻译成业务异常且不丢堆栈；用 with 保证资源（HTTP 客户端、文件、锁）在异常路径下也被释放。

## 8.1 真实问题引入：一次被"吞掉"的 429

Java 团队的 AI 网关服务（合成案例）调用 LLM 接口，转写者写了两段"看起来没问题"的代码：

```python
try:
    resp = client.chat(messages)
except Exception:            # 问题 1：吞掉一切，包括 KeyboardInterrupt 之外的编程错误
    return fallback()

try:
    resp = client.chat(messages)
except openai.RateLimitError as exc:
    raise RuntimeError("调用失败")   # 问题 2：原始 429 的信息（哪个模型、重试预算）全丢了
```

第一段把 `NameError`、`TypeError` 这类**编程 bug 与网络抖动混为一谈**，线上排障变成盲猜；第二段丢失了底层异常——Java 里 `catch (RateLimitException e) { throw new RuntimeException("调用失败"); }` 至少会自动把 `e` 作为 cause 附加，Python 需要**显式**写 `raise ... from exc`。本章解决三件事：哪些该捕获、如何保留链路、资源如何保证释放。

## 8.2 一句话解释 + 生活类比 + 类比边界

**一句话解释**：Python 所有异常都是 `BaseException` 的子类，业务代码捕获的层是 `Exception`（`KeyboardInterrupt`/`SystemExit` 属于 `BaseException` 直接分支，不该被业务捕获）；异常靠 `raise` 抛出、`try/except/else/finally` 处理；惯用 EAFP 风格"先做，出问题再处理"；资源清理交给 `with` 上下文管理器。

**生活类比**：try 块是把一件风险工作交给实习生，except 是你在旁边"只接得住的球"（声明的异常类型），finally 是无论成败都要做的下班锁门（资源清理），`raise ... from ...` 是"向上汇报时把原始现场照片附上"。

> 💡 类比边界：
> 1. Python **没有 checked exception**：所有异常都"unchecked"，方法签名也不声明异常——这像 Java 全部是 RuntimeException 的世界，因此"声明式地知道函数会抛什么"只能靠文档/类型注解（如 `Raises` 约定），设计上更要靠**异常分层**（8.3）来收敛；
> 2. `with` ↔ Java try-with-resources 只像一半：Java 要求类实现 `AutoCloseable` 且靠编译器强制 close；Python 的 `__exit__` 更强——它**参与异常决策**（返回 True 可以吞异常，默认 False 放行），且 `@contextmanager` 能用生成器语法把"任意代码段"包装成资源管理器，Java 没有直接对应物；
> 3. EAFP 不是"不要 if 检查"：多数分支逻辑仍然用 if；EAFP 指的是**错误路径**优先用异常表达，尤其在"检查与使用之间有竞态窗口"（文件、缓存、并发）的场景。

## 8.3 正式原理与准确术语

**异常类层次**：`BaseException` → `SystemExit` / `KeyboardInterrupt` / `Exception`；业务与库异常都挂在 `Exception` 下。常用内建异常：`ValueError`（值不合法）、`TypeError`（类型/用法错误）、`KeyError` / `IndexError`（容器访问越界/缺失）、`AttributeError`、`FileNotFoundError`（OSError 家族）、`RuntimeError`。**捕获语义**：`except` 按**顺序**匹配，子类异常分支必须写在父类之前；`except ... as e` 绑定异常实例；`else` 在无异常时执行；`finally` 无条件执行。**异常链（exception chaining）**：except 块内再抛新异常时，Python 自动把原异常挂到新异常的 `__context__`（隐式链，报错文案为 "During handling of the above exception, another exception occurred"）；`raise X from e` 显式指定为 `__cause__`（文案为 "The above exception was the direct cause of..."）；`raise X from None` 抑制内部细节（`__cause__`/`__context__` 置空显示）。**上下文管理器（context manager）**：实现 `__enter__`/`__exit__` 协议的对象，`with` 保证 `__exit__` 执行；`contextlib.contextmanager` 用生成器语法简化实现。

Java↔Python 异常对照：

| Java | Python | 关键差异 |
|---|---|---|
| checked / unchecked 二分 | 只有 unchecked | 签名不声明异常，靠异常分层+文档 |
| `catch (A \| B e)` | `except (A, B) as e` | 语法差异，语义相同 |
| `e.initCause(cause)` / 构造器 cause | `raise NewError(...) from e` | Python 必须**显式**写 from，否则只有隐式 `__context__` |
| try-with-resources（AutoCloseable） | `with`（`__enter__`/`__exit__`） | `__exit__` 可决定是否吞异常 |
| `finally` 中 return 警告 | 同样危险，3.14 已发 `SyntaxWarning` | 两语言共同大坑 |

**业务异常基类设计（推荐骨架）**：项目内所有业务异常继承统一基类，携带机器可读 `code` 与结构化 `detail`；基础设施异常（SDK 网络错误）在边界处翻译成业务异常或原样上抛，绝不裸 `except Exception` 吞掉。

## 8.4 最小完整示例：EAFP vs LBYL

**EX-08-01 | examples/ch08_exceptions/ex_08_01_eafp.py（完整可运行）**

```python
# EX-08-01 | EAFP vs LBYL | 运行: python3 examples/ch08_exceptions/ex_08_01_eafp.py
from pathlib import Path


def lbyl_get(mapping: dict[str, int], key: str) -> int | None:
    """Look Before You Leap：先检查再使用（Java 风格）。"""
    if key in mapping:
        return mapping[key]
    return None


def eafp_get(mapping: dict[str, int], key: str) -> int | None:
    """Easier to Ask Forgiveness than Permission：先做，出错再处理（Python 风格）。"""
    try:
        return mapping[key]
    except KeyError:
        return None


def main() -> None:
    scores: dict[str, int] = {"alice": 90}
    print(f"LBYL 命中: {lbyl_get(scores, 'alice')}，未命中: {lbyl_get(scores, 'bob')}")
    print(f"EAFP 命中: {eafp_get(scores, 'alice')}，未命中: {eafp_get(scores, 'bob')}")

    # EAFP 更顺手的场景：逐条转换"脏数据"，坏的跳过
    raw_values = ["42", "  7 ", "3.5", "abc", ""]
    for raw in raw_values:
        try:
            value: int | str = int(raw)
        except ValueError:
            value = f"失败({type(raw).__name__}无法转int)"
        print(f"int({raw!r}) -> {value}")

    # 对照：LBYL 的"检查"与"使用"之间存在竞态窗口；对文件更推荐直接 EAFP
    p = Path("/definitely/not/exist.txt")
    try:
        text = p.read_text(encoding="utf-8")
        print(f"读到 {len(text)} 字符")
    except FileNotFoundError as exc:
        print(f"直接读 -> FileNotFoundError: {exc.strerror}: {exc.filename}")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（Python 3.14.7）
LBYL 命中: 90，未命中: None
EAFP 命中: 90，未命中: None
int('42') -> 42
int('  7 ') -> 7
int('3.5') -> 失败(str无法转int)
int('abc') -> 失败(str无法转int)
int('') -> 失败(str无法转int)
直接读 -> FileNotFoundError: No such file or directory: /definitely/not/exist.txt
```

## 8.5 逐段解释：异常层次与业务基类、异常链、finally 与 with

**（1）自定义异常与业务异常基类**。EX-08-02 的 `AppError` 是全项目业务异常的根：带 `code`（机器可读，将来映射 HTTP 状态或错误码表）与 `detail`（结构化上下文，给前端/日志用）。**只捕获 `AppError` 的意义**：第三方 SDK 的 `ConnectionError`、程序 bug 的 `TypeError` 不会被业务分支误吞；`except AppError as exc` 一次接住全部子类。`try/except/else` 的 `else` 分支是"无异常时的正常路径"，比塞进 `try` 里更能收窄保护范围。

**EX-08-02 | examples/ch08_exceptions/ex_08_02_custom_exceptions.py（完整可运行）**

```python
# EX-08-02 | 自定义异常与业务异常基类 | 运行: python3 examples/ch08_exceptions/ex_08_02_custom_exceptions.py
class AppError(Exception):
    """本项目所有业务异常的基类：统一 code，方便上层一次捕获。"""

    code: str = "APP_ERROR"

    def __init__(self, message: str, *, detail: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.detail: dict[str, object] = detail or {}


class ValidationError(AppError):
    code = "VALIDATION_ERROR"


class NotFoundError(AppError):
    code = "NOT_FOUND"


class LlmQuotaExceededError(AppError):
    code = "LLM_QUOTA_EXCEEDED"


def find_order(order_id: str) -> str:
    orders = {"A1001": "已发货"}
    if not order_id.startswith("A"):
        raise ValidationError(f"订单号格式非法: {order_id!r}", detail={"field": "order_id"})
    if order_id not in orders:
        raise NotFoundError(f"订单不存在: {order_id}", detail={"order_id": order_id})
    return orders[order_id]


def main() -> None:
    for order_id in ["A1001", "A4040", "B2002"]:
        try:
            result = find_order(order_id)
        except AppError as exc:          # 只捕获业务基类：第三方错误不会被误吞
            print(f"[{exc.code}] {exc} detail={exc.detail}")
        else:
            print(f"查询成功: {order_id} -> {result}")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（Python 3.14.7）
查询成功: A1001 -> 已发货
[NOT_FOUND] 订单不存在: A4040 detail={'order_id': 'A4040'}
[VALIDATION_ERROR] 订单号格式非法: 'B2002' detail={'field': 'order_id'}
```

**（2）异常链：`raise X from Y` 对比 Java 的堆栈嵌套**。EX-08-03 里 `FileNotFoundError` 被翻译成业务语义 `DataLoadError`，`from exc` 把原始异常挂到 `__cause__`。打印完整堆栈时，Python 会**先打印原始异常再打印新异常**，中间用 "The above exception was the direct cause of the following exception" 连接——这就是 Python 版的 "Caused by:"。若不写 `from`，在 except 块内抛新异常也会有隐式链（`__context__`），文案是 "During handling of the above exception..."；`from None` 则把内部细节压掉，适合"对外接口不暴露存储路径"这类安全需求，但会丢排查线索，要注释说明。

**EX-08-03 | examples/ch08_exceptions/ex_08_03_exception_chain.py（完整可运行）**

```python
# EX-08-03 | 异常链 raise ... from ... | 运行: python3 examples/ch08_exceptions/ex_08_03_exception_chain.py
import json
import traceback
from pathlib import Path


class DataLoadError(Exception):
    """数据加载失败。"""


def load_records(path: str) -> list[dict[str, str]]:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError as exc:
        # 语义升级：底层细节 -> 业务语言，同时保留原始异常（__cause__）
        raise DataLoadError(f"知识库文件不可用: {path}") from exc


def load_records_quiet(path: str) -> list[dict[str, str]]:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError as exc:
        # from None：抑制内部细节（对外接口可用，但会丢排查线索，慎用）
        raise DataLoadError(f"知识库文件不可用: {path}") from None


def main() -> None:
    try:
        load_records("/definitely/missing.json")
    except DataLoadError:
        print("=== raise ... from exc 的完整堆栈 ===")
        print(traceback.format_exc())

    try:
        load_records_quiet("/definitely/missing.json")
    except DataLoadError as exc:
        print("=== raise ... from None 的堆栈 ===")
        print(f"只抛出 {type(exc).__name__}: {exc}，__cause__ = {exc.__cause__}（内部细节被抑制）")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（Python 3.14.7，路径中的绝对路径随运行目录而定）
=== raise ... from exc 的完整堆栈 ===
Traceback (most recent call last):
  File "/workspace/ai_application_course/examples/ch08_exceptions/ex_08_03_exception_chain.py", line 13, in load_records
    with open(path, encoding="utf-8") as f:
         ~~~~^^^^^^^^^^^^^^^^^^^^^^^^
FileNotFoundError: [Errno 2] No such file or directory: '/definitely/missing.json'

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "/workspace/ai_application_course/examples/ch08_exceptions/ex_08_03_exception_chain.py", line 31, in main
    load_records("/definitely/missing.json")
    ~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/workspace/ai_application_course/examples/ch08_exceptions/ex_08_03_exception_chain.py", line 17, in load_records
    raise DataLoadError(f"知识库文件不可用: {path}") from exc
DataLoadError: 知识库文件不可用: /definitely/missing.json

=== raise ... from None 的堆栈 ===
只抛出 DataLoadError: 知识库文件不可用: /definitely/missing.json，__cause__ = None（内部细节被抑制）
```

**（3）`finally` 与资源清理：为什么 Python 用 `with`**。`finally` 一定执行，但**在 `finally` 里写 `return`/`break` 会吞掉未处理的异常**（Python 3.14 已对该写法发 `SyntaxWarning: 'return' in a 'finally' block`），`finally` 只该放清理代码。而"清理代码"的标准载体是 `with`：EX-08-04 给出两种实现——类实现（`__enter__` 返回值交给 `as`；`__exit__(exc_type, exc, tb)` 返回 False 表示不吞异常）与 `@contextmanager` 生成器实现（`yield` 前是进入逻辑，`finally` 段是退出逻辑，异常会从 `yield` 处"路过"）。对照 Java：`Timer` 类 ≈ 实现 `AutoCloseable` 的资源类；`timer()` 生成器版 ≈ 没有直接 Java 对应物，最接近的是"模板方法+lambda"。

**EX-08-04 | examples/ch08_exceptions/ex_08_04_context_manager.py（完整可运行）**

```python
# EX-08-04 | 上下文管理器：类实现 + contextlib | 运行: python3 examples/ch08_exceptions/ex_08_04_context_manager.py
import time
from collections.abc import Iterator
from contextlib import contextmanager


class Timer:
    """类实现的上下文管理器：__enter__ / __exit__。"""

    def __enter__(self) -> "Timer":
        self._start: float = time.perf_counter()
        print("计时开始")
        return self                    # as 后面拿到的就是 __enter__ 的返回值

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        elapsed = time.perf_counter() - self._start
        print(f"计时结束: {elapsed * 1000:.1f} ms")
        return False                   # False = 不吞异常（返回 True 会吞掉，慎用）


@contextmanager
def timer(label: str) -> Iterator[str]:
    """生成器实现的等价物：yield 前是 __enter__，yield 后是 __exit__。"""
    start = time.perf_counter()
    print(f"[{label}] 开始")
    try:
        yield label                    # yield 的值交给 as
    finally:
        elapsed = time.perf_counter() - start
        print(f"[{label}] 结束: {elapsed * 1000:.1f} ms（即使中途抛异常也保证执行）")


def main() -> None:
    with Timer() as t:
        sum(range(100_000))
    print("-" * 40)

    with timer("清洗") as label:
        print(f"as 拿到: {label}")
        data = [x * 2 for x in range(1000)]
        print(f"处理了 {len(data)} 条")
    print("-" * 40)

    # 异常路径：清理逻辑依然执行
    try:
        with timer("会出错的任务"):
            raise RuntimeError("模拟业务异常")
    except RuntimeError as exc:
        print(f"捕获到: {exc}")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（Python 3.14.7；计时数值每次运行不同）
计时开始
计时结束: 2.2 ms
----------------------------------------
[清洗] 开始
as 拿到: 清洗
处理了 1000 条
[清洗] 结束: 0.1 ms（即使中途抛异常也保证执行）
----------------------------------------
[会出错的任务] 开始
[会出错的任务] 结束: 0.0 ms（即使中途抛异常也保证执行）
捕获到: 模拟业务异常
```

## 8.6 安装/文件位置/运行命令

- **依赖**：仅标准库（`contextlib`、`traceback`、`json`、`pathlib`、`time`），无新增安装。
- **文件位置**：`examples/ch08_exceptions/`（4 个示例）；测试 `tests/test_ch08.py`。
- **运行命令**：

```bash
cd /workspace/ai_application_course
python3 examples/ch08_exceptions/ex_08_03_exception_chain.py
python3 -m pytest tests/test_ch08.py -q
```

## 8.7 常见错误与排查

1. **`TypeError: exceptions must derive from BaseException`**——`raise "boom"`（抛的不是异常类/实例）。修复：`raise RuntimeError("boom")`；包装库函数时检查参数是不是 `Exception` 子类。
2. **`SyntaxWarning: 'return' in a 'finally' block`（且异常神秘消失）**——`finally` 里 `return` 把正在传播的异常吞掉。修复：把 return 移出 finally，finally 只放清理代码。
3. **更宽的 `except Exception` 写在前面**（无报错，逻辑 bug）——后面的 `except ValueError` 分支永远走不到。修复：**子类在前、父类在后**；能用具体异常就不用宽异常。
4. **裸 `except:` 或 `except Exception: pass`**（无报错，最难排查）——吞掉一切包括 `KeyboardInterrupt`（裸 except 属于 `BaseException` 层）与编程 bug，日志里只留下"神秘的重试成功/失败"。修复：捕获**具体异常类型**；确实要兜底时 `except Exception` + 记录日志 + `raise`（或重新抛出业务异常），绝不静默 `pass`。
5. **`raise RuntimeError("调用失败")` 丢了原始 429 信息**——except 块内抛新异常但没写 `from`。修复：`raise LlmCallError("调用失败") from exc`，让 `__cause__` 保留模型名/请求 ID 等排查线索。

## 8.8 企业场景中的使用方式（Spring Boot 视角）

- **AI 网关的异常分层**：对照 Spring 的 `@ControllerAdvice` 异常映射表，Python 侧的等价物是"业务异常基类 + FastAPI 异常处理器"（ch17）：`ValidationError`→400、`NotFoundError`→404、`LlmQuotaExceededError`→429/503。SDK 的 `APITimeoutError`/`RateLimitError` 在客户端封装层翻译成业务异常并 `from` 保留原链，重试逻辑只认异常类型不解析报错字符串。
- **资源管理**：httpx 客户端、文件、锁一律 `with`（`with httpx.Client(timeout=...) as client:`），与 Java try-with-resources 等价；自研的"计步骤耗时""临时切换配置"用 `@contextmanager` 包装成可复用块——这正是 LangGraph 节点里做计时/追踪的惯用法。
- **trace_id 贯穿**：Java 用 MDC 把 trace_id 塞进日志与异常消息；Python 侧惯例是把 trace_id 放进业务异常的 `detail`，由异常处理器统一写日志（避免每层手动拼字符串）。
- **多轮对话的补偿**：LLM 调用失败时历史已 append——正确做法是把"写历史"放进 `with` 管理的成功路径，或失败时显式回滚最后一条（对照 Spring 事务边界思想：副作用要么在事务内，要么可补偿）。

## 8.9 练习

1. **（基础）**`BaseException` 与 `Exception` 的直接子类各举两例；为什么 `except Exception` 接不住 `KeyboardInterrupt`？
2. **（基础）**`raise A(...) from e` 与"在 except 块里直接 `raise A(...)`"在 `__cause__`/`__context__` 上分别留下什么？
3. **（代码）**为 8.2 的 LLM 网关补全异常翻译层：定义 `LlmCallError(AppError)`（code="LLM_CALL_ERROR"），写函数 `def call_llm(fail: bool) -> str`（`fail=True` 时抛 `TimeoutError("upstream timeout")`），在调用方捕获 `TimeoutError` 并 `raise LlmCallError("上游超时", detail={"retry_after": 2}) from exc`；断言 `exc.__cause__` 是 `TimeoutError`。
4. **（代码）**用 `@contextmanager` 写 `suppress_to_log()`：进入时无动作，退出时若有异常则打印 `[suppressed] {type: msg}` 并吞掉异常（`__exit__` 等价物返回 True 的生成器写法：在 `except` 里处理且不再抛出）。演示"with 块内抛 `ValueError`，with 后代码继续执行"。
5. **（调试题）**下面的重试函数本意是"成功返回结果、失败重试 3 次后抛出"，实际却永远返回 `None` 且异常从不抛出，请指出问题：

```python
def retry(fn, times=3):
    for i in range(times):
        try:
            return fn()
        except ConnectionError:
            if i == times - 1:
                raise
        finally:
            log(f"attempt {i + 1} done")
            return None   # "顺手"在 finally 里收个尾
```

### 参考答案

<details>
<summary>点开查看参考答案</summary>

1. `BaseException` 直接子类：`SystemExit`、`KeyboardInterrupt`（另有 `GeneratorExit`、`BaseExceptionGroup`）；`Exception` 直接子类：`ValueError`、`RuntimeError`、`OSError` 等。`except Exception` 只匹配 `Exception` 及其后代，`KeyboardInterrupt` 挂在 `BaseException` 分支下，属于"用户要退出程序"的信号，语言刻意不让业务层顺手捕获。
2. `from e`：原异常存入新异常的 `__cause__`（同时 `__suppress_context__=False`，展示为 direct cause）。直接 `raise A(...)`：Python 隐式把正在处理的异常挂到 `__context__`（展示为 "During handling..."），`__cause__` 为 None。
3. 要点代码：

```python
class LlmCallError(AppError):
    code = "LLM_CALL_ERROR"

def call_llm(fail: bool) -> str:
    if fail:
        raise TimeoutError("upstream timeout")
    return "ok"

try:
    call_llm(True)
except TimeoutError as exc:
    raise LlmCallError("上游超时", detail={"retry_after": 2}) from exc
```
断言：`isinstance(exc.__cause__, TimeoutError)`（可用 pytest.raises 捕获后验证）。

4. 生成器内写法：

```python
from contextlib import contextmanager

@contextmanager
def suppress_to_log():
    try:
        yield
    except Exception as exc:
        print(f"[suppressed] {type(exc).__name__}: {exc}")

with suppress_to_log():
    raise ValueError("坏值")
print("继续执行")   # 会打印
```
原理：异常在 `yield` 处抛入生成器，被 except 处理后生成器正常结束，`contextlib` 据此视为"已处理"。

5. 根因是 `finally` 里的 `return None`：它无条件覆盖 `try` 里的 `return fn()`（返回值被丢弃），并把任何正在传播的异常（包括最后一次的 `raise`）吞掉——这正是 8.7 第 2 条的坑，Python 3.14 会给出 `SyntaxWarning: 'return' in a 'finally' block`。修复：`finally` 只放 `log(...)`，删掉 `return None`；`raise` 会自然向上传播。

</details>

## 8.10 自测检查表

- 我能画出 `BaseException` → `Exception` 的层次，并说出 `KeyboardInterrupt` 不该被业务捕获的原因。
- 我能对同一段代码分别写出 LBYL 与 EAFP 版本，并说清什么场景 EAFP 更稳（竞态窗口）。
- 我能设计带 `code`/`detail` 的业务异常基类，并解释"只捕获业务基类"的排障收益。
- 我能写出 `raise X from e` 并读完整链式堆栈（direct cause vs during handling）。
- 我能说出 `finally` 的三条铁律（一定执行、只放清理、别写 return）。
- 我能用类实现与 `@contextmanager` 两种方式写上下文管理器，并解释 `__exit__` 返回值的语义。

## 8.11 面试追问

1. **[模拟题] Python 为什么没有 checked exception？工程上如何补偿？**——参考回答：语言哲学上异常即流程控制的一部分（EAFP），强制声明在鸭子类型与高阶函数（装饰器、回调）下不可持续。补偿手段：业务异常分层与基类统一捕获、异常处理器集中映射错误码、关键函数文档/注解声明可能抛出的异常类型、监控按异常类型统计。
2. **[模拟题] `raise X from e`、`raise X`、`raise X from None` 三者的堆栈展示与排查影响？**——参考回答：from e → "direct cause"链，最完整；裸 raise X（在 except 内）→ 隐式 `__context__` 链 "During handling..."，完整但语义是"处理时顺带出错"而非因果；from None → 无链，适合对外接口隐藏内部细节（如不暴露存储路径），代价是丢排查线索，需注释说明。
3. **[模拟题] `__exit__` 返回 True 会发生什么？什么场景合理？**——参考回答：with 块内的异常被吞掉、代码继续执行。合理场景：`contextlib.suppress`（明确忽略某类异常）、测试工具、事务回滚后不再向上抛。业务代码中误返回 True 会造成"异常黑洞"，默认写 False/None。

### 待核实

- Python 3.11+ 的 `ExceptionGroup` 与 `except*` 语法（并发任务聚合异常时使用）本章未展开；在引入 asyncio 任务编排（ch13）后再结合官方文档核实与演示。

---

# 第二部分（上）小结与衔接

- **一条主线**：ch04 的"名字贴在对象上"贯穿全部——ch05 的可哈希性、ch06 的默认参数与闭包延迟绑定、ch07 的类属性共享、ch08 的资源清理，都是同一对象模型在不同场景的投影。
- **Java 迁移的核心清单**：变量模型（盒子→名字）、容器有序性（dict 保序）、函数签名（默认参数/keyword-only 替代重载）、`__init__` 与 property 的准确定位、dataclass 与 record 的不等价清单、无 checked exception 的补偿设计、with 替代 try-with-resources。
- **下一步**：第二部分（下）从 ch09 生成器开始——`yield` 正是 ch06 闭包与 ch08 上下文管理器（`@contextmanager`）的公共底层，随后 ch10 装饰器、ch11 模块与类型系统、ch12 标准库实战将把本章的类与异常体系接进真实工程。
- **验证记录**：本部分全部示例与测试的运行记录见 `verification/run_logs/part02a.md`。
