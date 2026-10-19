# EX-25-01 | 余弦相似度 numpy 手算实验 | 运行: python3 examples/ch25_embeddings/ex_25_01_cosine_manual.py
"""完整可运行：把余弦相似度拆成点积/模长/夹角三步手算，再对照 numpy 一行式；
最后验证"归一化向量的点积 == 余弦相似度"（检索系统加速的关键性质）。
"""
from __future__ import annotations

import math

import numpy as np

A = np.array([3.0, 4.0, 0.0])   # 向量 a
B = np.array([4.0, 3.0, 0.0])   # 向量 b
C = np.array([-3.0, -4.0, 0.0])  # 向量 c = -a（方向完全相反）


def main() -> None:
    print("[手算三步] a=[3,4,0]  b=[4,3,0]")
    dot = float(A @ B)
    na = math.sqrt(float(A @ A))
    nb = math.sqrt(float(B @ B))
    cos_ab = dot / (na * nb)
    angle = math.degrees(math.acos(cos_ab))
    print(f"    1) 点积     a·b = 3×4 + 4×3 + 0×0 = {dot}")
    print(f"    2) 模长     |a| = {na:.4f}, |b| = {nb:.4f}")
    print(f"    3) 相似度   cos = {dot:.4f} / ({na:.4f}×{nb:.4f}) = {cos_ab:.6f}，夹角 {angle:.2f}°")

    print("\n[numpy 一行式对照]：")
    cos_np = float(np.dot(A, B) / (np.linalg.norm(A) * np.linalg.norm(B)))
    print(f"    np.dot/(norm×norm) = {cos_np:.6f}  （与手算一致：{math.isclose(cos_ab, cos_np)}）")

    print("\n[方向决定一切]：")
    print(f"    cos(a, -a) = {float(A @ C / (np.linalg.norm(A) * np.linalg.norm(C))):.4f}  ← 完全反向 = -1")
    print(f"    cos(a, a)  = {float(A @ A / (np.linalg.norm(A) ** 2)):.4f}  ← 自己 = 1")

    print("\n[归一化后点积即余弦]（向量检索系统都靠这个性质省算力）：")
    a_unit, b_unit = A / np.linalg.norm(A), B / np.linalg.norm(B)
    print(f"    unit(a)·unit(b) = {float(a_unit @ b_unit):.6f} == cos(a,b)")
    print("    所以：embedding 入库前统一 L2 归一化，检索时只需一次点积。")


if __name__ == "__main__":
    main()
