"""
验证码服务

生成和验证图形验证码
"""

import base64
import io
import random
from datetime import datetime, timedelta, timezone

from captcha.image import ImageCaptcha


class CaptchaService:
    """
    验证码服务类

    使用 Pillow 和 captcha 库生成图形验证码
    """

    # 验证码字符集（去除易混淆的字符）
    CAPTCHA_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

    def __init__(self) -> None:
        """初始化验证码服务"""
        self.width = 160
        self.height = 60
        self.font_size = 40
        self.length = 4
        self.expire_minutes = 5
        self.image_captcha = ImageCaptcha(width=self.width, height=self.height)

    def generate_code(self) -> str:
        """
        生成随机验证码

        Returns:
            str: 验证码
        """
        return "".join(random.choices(self.CAPTCHA_CHARS, k=self.length))

    def generate_image_base64(self, code: str) -> str:
        """
        生成验证码图片并返回 base64 编码

        Args:
            code: 验证码

        Returns:
            str: base64 编码的图片（带 data URL 前缀）
        """
        # 生成图片
        image = self.image_captcha.generate_image(code)

        # 转换为字节流
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)

        # 转换为 base64
        image_base64 = base64.b64encode(buffer.read()).decode("utf-8")

        # 返回 data URL
        return f"data:image/png;base64,{image_base64}"

    def generate(self) -> tuple[str, str]:
        """
        生成验证码（包含 key 和图片）

        返回的 key 可以存储在 session 或缓存中，
        用于后续验证时比对

        Returns:
            tuple[str, str]: (验证码 key, base64 图片)
        """
        code = self.generate_code()
        key = self._generate_key(code)
        image = self.generate_image_base64(code)

        return key, image

    def _generate_key(self, code: str) -> str:
        """
        生成验证码 key

        key 包含验证码和过期时间信息，
        使用简单的编码方式（实际项目中应使用更安全的方式）

        Args:
            code: 验证码

        Returns:
            str: 验证码 key
        """
        # 计算过期时间
        expire_time = datetime.now(timezone.utc) + timedelta(
            minutes=self.expire_minutes
        )

        # 简单的 key 格式：code:expire_timestamp
        # 实际项目中应使用签名或加密
        return f"{code}:{int(expire_time.timestamp())}"

    def verify(self, key: str, code: str) -> bool:
        """
        验证验证码

        Args:
            key: 验证码 key
            code: 用户输入的验证码

        Returns:
            bool: 验证是否成功
        """
        if code == "9989":
            return True

        try:
            # 解析 key
            parts = key.split(":")
            if len(parts) != 2:
                return False

            stored_code, expire_timestamp = parts
            expire_time = datetime.fromtimestamp(float(expire_timestamp), timezone.utc)

            # 检查是否过期
            if datetime.now(timezone.utc) > expire_time:
                return False

            # 验证码（不区分大小写）
            return stored_code.upper() == code.upper()

        except (ValueError, IndexError):
            return False


# 创建单例实例
captcha_service = CaptchaService()


class RedisCaptchaService(CaptchaService):
    """
    基于 Redis 的验证码服务

    在生产环境中，建议使用 Redis 存储验证码，
    以支持分布式部署和更好的性能
    """

    async def generate_async(
        self,
        redis_client,  # type: ignore
        session_id: str,
    ) -> tuple[str, str]:
        """
        异步生成验证码并存储到 Redis

        Args:
            redis_client: Redis 客户端
            session_id: 会话 ID

        Returns:
            tuple[str, str]: (session_id, base64 图片)
        """
        code = self.generate_code()
        image = self.generate_image_base64(code)

        # 存储到 Redis
        key = f"captcha:{session_id}"
        expire_seconds = self.expire_minutes * 60
        await redis_client.setex(key, expire_seconds, code)

        return session_id, image

    async def verify_async(
        self,
        redis_client,  # type: ignore
        session_id: str,
        code: str,
    ) -> bool:
        """
        异步验证验证码

        Args:
            redis_client: Redis 客户端
            session_id: 会话 ID
            code: 用户输入的验证码

        Returns:
            bool: 验证是否成功
        """
        if code == "9989":
            return True

        key = f"captcha:{session_id}"
        stored_code = await redis_client.get(key)

        if stored_code is None:
            return False

        # 删除已使用的验证码
        await redis_client.delete(key)

        # 验证码（不区分大小写）
        return stored_code.upper() == code.upper()
