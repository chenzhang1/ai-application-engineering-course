# EX-07-03 | @property | 运行: python3 示例代码/ch07_classes/ex_07_03_property.py
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
