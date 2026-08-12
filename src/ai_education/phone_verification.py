"""Alibaba Cloud PNVS SMS verification for phone-bound accounts."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Protocol

from ai_education.config import Settings
from ai_education.core.errors import InputValidationError

MOBILE_PATTERN = re.compile(r"^1[3-9]\d{9}$")


def normalize_phone(value: str) -> tuple[str, str]:
    compact = re.sub(r"[\s-]", "", value.strip())
    if compact.startswith("+86"):
        compact = compact[3:]
    elif compact.startswith("0086"):
        compact = compact[4:]
    if not MOBILE_PATTERN.fullmatch(compact):
        raise InputValidationError("请输入正确的中国大陆手机号")
    return compact, f"+86{compact}"


class PhoneVerificationProvider(Protocol):
    def send_code(self, phone: str) -> None: ...

    def check_code(self, phone: str, code: str) -> bool: ...


@dataclass(slots=True)
class AliyunPhoneVerificationService:
    settings: Settings

    def _client(self):
        try:
            from alibabacloud_dypnsapi20170525.client import Client
            from alibabacloud_tea_openapi import models as open_api_models
        except ImportError as exc:
            raise InputValidationError("手机号认证组件尚未安装，请联系管理员") from exc
        if not self.settings.aliyun_access_key_id or not self.settings.aliyun_access_key_secret:
            raise InputValidationError("手机号认证服务尚未完成密钥配置")
        config = open_api_models.Config(
            access_key_id=self.settings.aliyun_access_key_id,
            access_key_secret=self.settings.aliyun_access_key_secret,
        )
        config.endpoint = "dypnsapi.aliyuncs.com"
        return Client(config)

    def send_code(self, phone: str) -> None:
        try:
            from alibabacloud_dypnsapi20170525 import models as dypnsapi_models
            from alibabacloud_tea_util import models as util_models

            request = dypnsapi_models.SendSmsVerifyCodeRequest(
                phone_number=phone,
                country_code="86",
                sign_name=self.settings.phone_auth_sign_name,
                template_code=self.settings.phone_auth_template_code,
                template_param=json.dumps(
                    {
                        "code": "##code##",
                        "min": str(self.settings.phone_auth_code_ttl_seconds // 60),
                    },
                    ensure_ascii=False,
                ),
                scheme_name=self.settings.phone_auth_scheme_name,
                code_length=self.settings.phone_auth_code_length,
                valid_time=self.settings.phone_auth_code_ttl_seconds,
                interval=self.settings.phone_auth_resend_seconds,
                return_verify_code=False,
            )
            response = self._client().send_sms_verify_code_with_options(
                request, util_models.RuntimeOptions()
            )
        except InputValidationError:
            raise
        except Exception as exc:
            raise InputValidationError("验证码发送失败，请稍后重试") from exc
        if not response.body or response.body.code != "OK":
            raise InputValidationError("验证码发送失败，请稍后重试")

    def check_code(self, phone: str, code: str) -> bool:
        try:
            from alibabacloud_dypnsapi20170525 import models as dypnsapi_models
            from alibabacloud_tea_util import models as util_models

            request = dypnsapi_models.CheckSmsVerifyCodeRequest(
                phone_number=phone,
                country_code="86",
                verify_code=code,
                scheme_name=self.settings.phone_auth_scheme_name,
            )
            response = self._client().check_sms_verify_code_with_options(
                request, util_models.RuntimeOptions()
            )
        except InputValidationError:
            raise
        except Exception as exc:
            raise InputValidationError("验证码校验服务暂时不可用") from exc
        return bool(
            response.body
            and response.body.code == "OK"
            and response.body.model
            and response.body.model.verify_result == "PASS"
        )
