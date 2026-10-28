"""用户脚本执行环境构建器

为前后置脚本、全局函数测试等场景提供统一的 exec() 全局命名空间。
新增可用库只需在本模块顶部的 import 区添加即可，所有调用方自动生效。
"""

import base64
import hashlib
import hmac
import json
import random
import re
import secrets
import string
import time
import uuid
from datetime import datetime

import requests
from Crypto.Cipher import AES, DES, DES3, PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Util.Padding import pad, unpad
from faker import Faker

# 库说明：name → (显示名, 说明, 用法示例)
# 新增库时同步更新此字典，AI 生成提示词和内置函数文档会自动引用。
LIBRARY_DOCS: dict[str, tuple[str, str, str]] = {
    "time": (
        "time",
        "时间相关操作：获取时间戳、休眠、时间格式化",
        "timestamp = time.time()  # 获取当前时间戳",
    ),
    "random": (
        "random",
        "随机数生成：随机整数、随机选择、随机采样、随机浮点数",
        "num = random.randint(1, 100)  # 1-100 随机整数",
    ),
    "re": (
        "re",
        "正则表达式：模式匹配、搜索、替换、提取",
        "result = re.findall(r'\\d+', text)  # 提取所有数字",
    ),
    "uuid": (
        "uuid",
        "UUID 生成：唯一标识符",
        "uid = uuid.uuid4().hex  # 生成32位唯一ID",
    ),
    "hashlib": (
        "hashlib",
        "哈希加密：MD5、SHA1、SHA256 等摘要算法",
        "digest = hashlib.md5(data.encode()).hexdigest()",
    ),
    "hmac": (
        "hmac",
        "HMAC 签名：基于密钥的消息认证码",
        "sign = hmac.new(key.encode(), msg.encode(), hashlib.sha256).hexdigest()",
    ),
    "base64": (
        "base64",
        "Base64 编解码",
        "encoded = base64.b64encode(data.encode()).decode()",
    ),
    "secrets": (
        "secrets",
        "安全随机数：生成令牌、密钥等密码学安全的随机值",
        "token = secrets.token_hex(16)  # 生成32位随机十六进制字符串",
    ),
    "string": (
        "string",
        "字符串常量：字母表、数字、标点符号等字符集",
        "chars = string.ascii_letters + string.digits",
    ),
    "json": (
        "json",
        "JSON 处理：解析和序列化 JSON 数据",
        "data = json.loads(json_str)  # 解析JSON字符串",
    ),
    "datetime": (
        "datetime",
        "日期时间：获取当前时间、时间计算、格式化",
        'now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")',
    ),
    "requests": (
        "requests",
        "HTTP 请求：发送 GET/POST/PUT/DELETE 等 HTTP 请求",
        'resp = requests.get("https://httpbin.org/get")',
    ),
    "Faker": (
        "Faker",
        "测试数据生成：姓名、手机号、邮箱、地址等模拟数据",
        'fake = Faker("zh_CN"); name = fake.name()',
    ),
    "RSA": (
        "Crypto.PublicKey.RSA",
        "RSA 非对称加密：生成密钥对、导入导出密钥",
        "key = RSA.generate(2048)  # 生成2048位RSA密钥",
    ),
    "AES": (
        "Crypto.Cipher.AES",
        "AES 对称加密：支持 CBC/ECB/CTR 等模式",
        "cipher = AES.new(key, AES.MODE_CBC, iv); ct = cipher.encrypt(pad(data, AES.block_size))",
    ),
    "DES": (
        "Crypto.Cipher.DES",
        "DES 对称加密（8字节密钥，已不推荐用于生产）",
        "cipher = DES.new(key, DES.MODE_CBC, iv)",
    ),
    "DES3": (
        "Crypto.Cipher.DES3",
        "3DES 对称加密（Triple DES，24字节密钥）",
        "cipher = DES3.new(key, DES3.MODE_CBC, iv)",
    ),
    "PKCS1_OAEP": (
        "Crypto.Cipher.PKCS1_OAEP",
        "RSA OAEP 填充模式的加解密器",
        "cipher = PKCS1_OAEP.new(rsa_key); encrypted = cipher.encrypt(msg)",
    ),
    "pad": (
        "Crypto.Util.Padding.pad",
        "数据填充：将数据填充到指定块大小的倍数",
        "padded = pad(data, AES.block_size)",
    ),
    "unpad": (
        "Crypto.Util.Padding.unpad",
        "数据去填充：移除填充数据还原原始数据",
        "original = unpad(padded, AES.block_size)",
    ),
}


def build_script_globals(**extra: object) -> dict:
    """构建用户脚本 exec() 所需的 globals 字典。

    Args:
        **extra: 额外需要注入的名字，例如 ``global_function=ns``。

    Returns:
        可直接传给 ``exec(code, globals_dict, ...)`` 的字典。
    """
    globals_dict = {
        # ⚠️ 安全 TODO(S5,信任边界待定):此处注入完整 __builtins__,用户脚本
        # (用例/全局函数的 setup_script/teardown_script,能编辑脚本的项目成员即可写)
        # 可执行 __import__("os").system(...)、读 os.environ(DB 串/SECRET_KEY),
        # 与后端同进程同权限、无沙箱。多租户生产需收紧:__builtins__ 白名单
        # (去掉 open/eval/exec/compile/__import__)+ 限制可写脚本的角色 + 隔离到受限子进程。
        # 当前按"教学/自用、脚本作者可信"的信任边界暂留(木森 2026-06-18 拍板先标 TODO)。
        "__builtins__": __builtins__,
        # 标准库
        "time": time,
        "random": random,
        "re": re,
        "uuid": uuid,
        "hashlib": hashlib,
        "hmac": hmac,
        "base64": base64,
        "secrets": secrets,
        "string": string,
        "json": json,
        "datetime": datetime,
        # 第三方库
        "requests": requests,
        "Faker": Faker,
        # 加密库
        "RSA": RSA,
        "AES": AES,
        "DES": DES,
        "DES3": DES3,
        "PKCS1_OAEP": PKCS1_OAEP,
        "pad": pad,
        "unpad": unpad,
    }
    globals_dict.update(extra)
    # global_function 是注入的命名空间对象，不是真实模块。AI 生成的 setup/teardown 脚本
    # 常按习惯写 `import global_function`（甚至 `from global_function import x`），而它不在
    # sys.modules → ModuleNotFoundError: No module named 'global_function'。给本次 exec 装一个
    # 局部 __import__ 钩子，把对 global_function 的 import 解析到注入对象，其余 import 原样委托；
    # 仅作用于本 exec 的 __builtins__ 副本，绝不改进程级 sys.modules（并发脚本各自 ns 会串号）。
    gf_ns = extra.get("global_function")
    if gf_ns is not None:
        import builtins as _bi

        def _hooked_import(
            name, g=None, ls=None, fromlist=(), level=0, _real=_bi.__import__, _ns=gf_ns
        ):
            if level == 0 and name == "global_function":
                return _ns
            return _real(name, g, ls, fromlist, level)

        _b = dict(vars(_bi))
        _b["__import__"] = _hooked_import
        globals_dict["__builtins__"] = _b
    return globals_dict


def run_env_post_script(test_env_data: dict) -> None:
    """执行环境后置脚本（各执行驱动在全部用例跑完后调用一次）。

    历史缺陷：``__env_post_script__`` 被 env 构建器写入，但唯一消费点挂在
    CaseExecutor.execute_suite 这条死路径上——真实执行路径全是循环
    execute_single_case，配置了的清理脚本从不运行。收敛为公共函数由驱动显式调用。
    """
    script = test_env_data.get("__env_post_script__")
    if not (isinstance(script, str) and script.strip()):
        return
    # db 句柄注入：post_script 里 db.execute(...) 直连被测库清理测试数据（方案 A 主场景）
    extra: dict = {"db": test_env_data.get("__db_access__")}
    runtime_gf = test_env_data.get("__runtime_global_function__")
    if runtime_gf is not None:
        extra["global_function"] = runtime_gf
    script_globals = build_script_globals(**extra)
    exec(script, script_globals, {"env_data": test_env_data})


def get_libraries_description() -> str:
    """生成可用库的文档描述，用于 AI 提示词和前端展示。"""
    lines = []
    for name, (full_name, desc, example) in LIBRARY_DOCS.items():
        lines.append(f"- **{name}** ({full_name}): {desc}\n  示例: `{example}`")
    return "\n".join(lines)
