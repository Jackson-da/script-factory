"""
FastAPI 依赖注入（Dependency Injection）模块。

什么是依赖注入？
  路由函数声明参数 pipeline=Depends(get_pipeline)。
  FastAPI 在调用路由函数之前，自动执行 get_pipeline()，
  把返回值注入到 pipeline 参数里。

为什么用？
  传统做法：在每个路由函数里写 pipeline = run_pipeline
  依赖注入：统一管理"怎么获取这个依赖"，路由函数只声明"我需要什么"
  好处：可复用、方便测试时可替换为 mock、路由函数与具体实现解耦。

本模块只有一个依赖：get_pipeline。
它返回编排器函数 run_pipeline，router 拿到后自己调用来驱动流水线。
"""

from backend.app.pipeline.orchestator import run_pipeline


def get_pipeline():
    """返回流水线编排器函数（callable 对象本身，不是调用结果）。

    router.py 中的用法：
        async def generate_script(pipeline=Depends(get_pipeline)):
            state = pipeline(state)   # <- 这里才真正调用

    如果未来需要测试（替换为 mock 流水线），只需改这个函数：
        def get_pipeline():
            return mock_pipeline      # 返回假的，router 无感知

    Returns:
        callable: run_pipeline 函数，签名 run_pipeline(state: dict) -> dict
    """
    return run_pipeline
