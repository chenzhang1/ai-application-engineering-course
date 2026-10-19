# EX-29-01 | 与 AI 协作：让模型解释代码的提问模板 | 运行: python3 示例代码/ch29_ai_collab/ex_29_01_explain_code.py
"""完整可运行（Mock，脚本驱动）：用"上下文+任务+输出格式"模板让模型解释一段代码，
对比裸问题与好模板的产出差异；演示协作开发的第一步——把代码当输入数据喂给模型。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from 示例代码.公共.llm_client import MockLLM  # noqa: E402

CODE = '''def Deduped(items):
    seen = set()
    out = []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out'''

NAIVE_QUESTION = "这段代码干嘛的？"

GOOD_TEMPLATE = """\
## 上下文
这是一个 Python 3 项目里的工具函数，团队以 Java 为主。

## 任务
解释下面的函数：1) 逐行做什么；2) 时间复杂度；3) 一个 Java 工程师最容易踩的坑。

## 输出格式
三段小标题，总长不超过 200 字。

## 代码
```python
{code}
```"""


def main() -> None:
    llm = MockLLM(script=[
        # 裸问题：输出泛泛（脚本模拟真实模型最常见的"正确但没用"回答）
        {"content": "这个函数看起来是做去重的，就是去掉列表里重复的元素。"},
        # 好模板：三个小标题齐活（脚本模拟理想产出）
        {"content": "### 逐行行为\n用 set 记录已见元素，首次出现才追加到 out，保持原顺序去重。\n"
                    "### 复杂度\nO(n) 时间 / O(n) 空间；x in seen 是哈希查找 O(1)。\n"
                    "### Java 工程师易踩的坑\n元素必须可哈希（dict/set 的 key 规则）："
                    "传 list 的 list 会 TypeError；且它不排序，顺序敏感时别换成 LinkedHashSet 心智。"},
    ])

    print("[裸问题]")
    r1 = llm.chat([{"role": "user", "content": NAIVE_QUESTION + "\n" + CODE}])
    print(f"    问：{NAIVE_QUESTION}")
    print(f"    答：{r1.content}")
    print("    问题：没有任务拆解、没有读者画像、没有格式约束 → 得到'正确但没用'的科普。")

    print("\n[好模板]")
    r2 = llm.chat([{"role": "user", "content": GOOD_TEMPLATE.format(code=CODE)}])
    print(r2.content)

    print("\n[协作心法] 把'让 AI 解释代码'当成一次接口调用来设计：")
    print("    上下文（给足背景）+ 任务（动词开头、可判定）+ 输出格式（可断言）——")
    print("    和 ch26 的 prompt 三段式是同一件事。")


if __name__ == "__main__":
    main()
