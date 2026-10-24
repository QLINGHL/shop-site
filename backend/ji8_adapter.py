"""ji8.ai 发货适配器 — 等官方 API 文档到了再填实现.

他已有 API Key + Secret (2026-10-08 在 /me/api 生成), 但 ji8 官网没有公开文档
(2026-10-08 已看过全站; 2026-10-09 全网搜索无结果), 只能找客服索取.

实现时按文档填:
    def fulfill(sku: str, contact: str) -> dict:
        # 用 Key/Secret 签名 -> 调 ji8 下单接口 -> 返回 {"ji8_order_id": ...}
        ...

在那之前调用直接抛错, 防止误发单. Key/Secret 只放服务器环境变量, 永不进前端.
"""


def fulfill(sku: str, contact: str):
    raise NotImplementedError("ji8.ai API 文档未到: 联系客服索取后实现此函数")
