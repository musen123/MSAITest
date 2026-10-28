"""内置全局函数信息提取器

通过 Python inspect 模块自动提取 global_function 模块中所有函数的元信息，
包括函数名、参数列表、返回类型注解、docstring、源代码等。
"""

import inspect

from app.utils.script_runtime import global_function


def _get_return_type(func_obj) -> str:
    """提取函数的返回类型注解"""
    annotation = inspect.signature(func_obj).return_annotation
    if annotation is inspect.Parameter.empty:
        return "Any"
    if isinstance(annotation, str):
        return annotation
    return getattr(annotation, "__name__", str(annotation))


def inspect_model_func() -> list[dict]:
    """提取所有内置函数的完整元信息"""
    result = []
    func_list = inspect.getmembers(global_function, predicate=inspect.isfunction)
    for name, func_obj in func_list:
        if name.startswith("_"):
            continue

        sig = inspect.signature(func_obj)
        doc = inspect.getdoc(func_obj) or ""

        # 提取参数信息
        params_list = []
        for key, value in sig.parameters.items():
            param_info = {
                "name": key,
                "type": "str",
                "description": "",
                "required": True,
            }
            if value.annotation is not inspect.Parameter.empty:
                ann = value.annotation
                param_info["type"] = getattr(ann, "__name__", str(ann))
            if value.default is not inspect.Parameter.empty:
                param_info["required"] = False
                param_info["default"] = str(value.default)
            params_list.append(param_info)

        # 提取源代码
        try:
            source = inspect.getsource(func_obj)
        except (OSError, TypeError):
            source = ""

        result.append(
            {
                "name": name,
                "display_name": doc.split("，")[0] if doc else name,
                "language": "python",
                "code": source,
                "description": doc,
                "params": params_list,
                "return_type": _get_return_type(func_obj),
                "example": f"global_function.{name}()",
            }
        )
    return result


global_function_list = inspect_model_func()
