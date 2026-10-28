# @Author  : 木森
# @weixin: python771
import base64
import hashlib
import random
import time

import requests
import rsa
from faker import Faker

fk = Faker(locale="zh_CN")
import os


def random_mobile():
    """随机生成手机号"""
    return fk.phone_number()


def random_addr():
    """随机生成一个地址"""
    return fk.address()


def random_city():
    """随机生成一个城市名"""
    return fk.city()


def random_company():
    """随机生成一个公司名"""
    return fk.company()


def random_project_name():
    """随机生成一个项目名称"""
    return fk.company()


def random_postcode():
    """随机生成一个邮编"""
    return fk.postcode()


def random_email():
    """随机生成一个邮箱号"""
    return fk.email()


def random_date():
    """随机生成一个日期"""
    return fk.date()


def radom_date_time():
    """随机生成一个时间"""
    return fk.date_time()


def random_ipv4():
    """随机生成一个ipv4的地址"""
    return fk.ipv4()


def get_timestamp():
    """生成当前时间戳"""
    return time.time()


def base64_encode(data: str):
    """base64编码"""
    return base64.b64encode(data.encode("utf-8")).decode("utf-8")


def md5_encrypt(data: str):
    """md5加密"""
    from hashlib import md5

    new_md5 = md5()
    new_md5.update(data.encode("utf-8"))
    return new_md5.hexdigest()


def rsa_encrypt(msg):
    """
    rsa加密
    :param msg: 待加密文本
    :param server_pub: 密钥
    :return:
    """
    server_pub = "XXXXXXX"
    msg = msg.encode("utf-8")
    pub_key = server_pub.encode("utf-8")
    public_key_obj = rsa.PublicKey.load_pkcs1_openssl_pem(pub_key)  #
    cryto_msg = rsa.encrypt(msg, public_key_obj)  # 生成加密文本
    cipher_base64 = base64.b64encode(cryto_msg)  # 将加密文本转化为 base64 编码
    return cipher_base64.decode()


def sha256_encrypt(data: str):
    """SHA256 加密"""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def hmac_sha256(key: str, data: str):
    """HMAC-SHA256 签名"""
    import hmac

    return hmac.new(
        key.encode("utf-8"), data.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def base64_decode(data: str):
    """base64解码"""
    return base64.b64decode(data.encode("utf-8")).decode("utf-8")


def aes_cbc_encrypt(data: str, key: str, iv: str):
    """AES CBC模式加密，返回base64编码的密文"""
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad

    cipher = AES.new(key.encode("utf-8"), AES.MODE_CBC, iv.encode("utf-8"))
    ct = cipher.encrypt(pad(data.encode("utf-8"), AES.block_size))
    return base64.b64encode(ct).decode("utf-8")


def aes_cbc_decrypt(data: str, key: str, iv: str):
    """AES CBC模式解密，输入base64编码的密文"""
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad

    ct = base64.b64decode(data)
    cipher = AES.new(key.encode("utf-8"), AES.MODE_CBC, iv.encode("utf-8"))
    pt = unpad(cipher.decrypt(ct), AES.block_size)
    return pt.decode("utf-8")


def random_string(length: int = 8):
    """生成指定长度的随机字符串（字母+数字）"""
    import string

    chars = string.ascii_letters + string.digits
    return "".join(random.choice(chars) for _ in range(length))


def current_timestamp_ms():
    """获取当前毫秒级时间戳"""
    return int(time.time() * 1000)


def url_encode(data: str):
    """URL编码"""
    from urllib.parse import quote

    return quote(data, safe="")


def url_decode(data: str):
    """URL解码"""
    from urllib.parse import unquote

    return unquote(data)


def ocr_captcha(
    image: str,
    typeid: int = 3,
    username: str = "",
    password: str = "",
    timeout: int = 60,
):
    """识别图片验证码中的具体内容（数字、英文、混合等）

    支持图片URL或base64编码的图片数据，账号密码从环境变量读取，也可调用时手动传入覆盖。
    typeid 常用值: 1纯数字, 2纯英文, 3数英混合, 4计算题, 7无汉字, 11汉字, 18缺口识别, 1033拖动拼图

    :param image: 图片URL（http/https开头）或 base64 编码的图片数据
    :param typeid: 验证码类型，默认3（数英混合）
    :param username: 图鉴账号（为空时从环境变量 TTSHITU_USERNAME 读取）
    :param password: 图鉴密码
    :param timeout: 超时时间（秒），默认60
    :return: 识别出的文字结果
    """

    # 账号密码优先使用传入值，否则从环境变量读取
    username = username or "musen123456"
    password = password or "Musen123456"

    # 处理图片数据：URL 下载转 base64，base64 直接使用
    if image.startswith("http://") or image.startswith("https://"):
        resp = requests.get(image, timeout=30)
        resp.raise_for_status()
        b64_image = base64.b64encode(resp.content).decode("utf-8")
    else:
        # 去掉 data:image/xxx;base64, 前缀
        b64_image = image.split(",", 1)[1] if image.startswith("data:") else image

    data = {
        "username": username,
        "password": password,
        "typeid": str(typeid),
        "image": b64_image,
    }

    # 最多重试3次
    for _ in range(3):
        resp = requests.post(
            "http://api.ttshitu.com/predict", json=data, timeout=timeout
        )
        result = resp.json()
        if result.get("success"):
            return result["data"]["result"]
        msg = str(result.get("message", ""))
        if any(x in msg for x in ["人工不足", "超时", "timeout", "请延长超时时间"]):
            time.sleep(2)
            continue
        raise RuntimeError(f"验证码识别失败: {msg}")

    raise RuntimeError("验证码识别失败: 重试3次仍失败")


def ocr_captcha_from_file(
    file_path: str,
    typeid: int = 3,
    username: str = "",
    password: str = "",
    timeout: int = 60,
):
    """识别本地图片文件验证码中的具体内容（数字、英文、混合等）

    读取本地图片文件并转为base64后调用图鉴API识别。
    typeid 常用值: 1纯数字, 2纯英文, 3数英混合, 4计算题, 7无汉字, 11汉字, 18缺口识别, 1033拖动拼图

    :param file_path: 图片文件路径
    :param typeid: 验证码类型，默认3（数英混合）
    :param username: 图鉴账号
    :param password: 图鉴密码
    :param timeout: 超时时间（秒），默认60
    :return: 识别出的文字结果
    """
    with open(file_path, "rb") as f:
        img_base64 = base64.b64encode(f.read()).decode("utf-8")
    return ocr_captcha(
        img_base64, typeid=typeid, username=username, password=password, timeout=timeout
    )


if __name__ == "__main__":
    print(random_mobile())
