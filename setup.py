from setuptools import setup, find_packages

setup(
    name="testcase-generator",
    version="1.0.0",
    description="知识库全流程自动化测试工具 — 从出题、过滤、评测到 API 测试",
    author="hust208",
    license="Apache-2.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    py_modules=["main"],
    install_requires=[
        "requests>=2.28.0",
        "numpy>=1.24.0",
        "pyyaml>=6.0",
        "jinja2>=3.1.0",
        "jsonpath-ng>=1.5.3",
        "rich>=13.0.0",
    ],
    entry_points={
        "console_scripts": [
            "tcg=main:main",
        ],
    },
    python_requires=">=3.8",
)
