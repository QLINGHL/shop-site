# 后端部署手册 (AlwaysData 免费版)

代码: `~/workspace/shop-backend/` → 服务器 `~/www/shop-api/`

## 1. 面板建 Python 站点 (他接管或按面板实际标签来)
1. AlwaysData 面板 → Web → Sites → Add a site
2. 类型选 **Python (WSGI)**; 地址用面板自动分配的 `*.alwaysdata.net`
   (如 `api-qlinghl.alwaysdata.net`, 以面板实际为准)
3. 工作目录: `~/www/shop-api`; WSGI 入口文件: `wsgi.py`

## 2. SSH 传文件 + 装依赖
```bash
ssh -i /home/hatch/.ssh/id_ed25519 qlinghl@ssh-qlinghl.alwaysdata.net
mkdir -p ~/www/shop-api
# 传 app.py wsgi.py ji8_adapter.py requirements.txt 到 ~/www/shop-api/
cd ~/www/shop-api && python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
```
- 若 `bcrypt` 编译失败: 备选方案改用标准库 `hashlib.pbkdf2_hmac` (到时改 register/login 两处, 约 10 行)。

## 3. 环境变量 (面板 Sites → 该站点 → Environment variables)
- `JWT_SECRET`: 随机 32 位以上字符串 (`python3 -c "import secrets; print(secrets.token_hex(32))"`)
- `FRONTEND_ORIGIN`: `https://qlinghl.alwaysdata.net`
- `SHOP_DB`: `~/www/shop-api/shop.db` (默认就是这个, 可不设)
- ji8 的 Key/Secret: 文档到、实现 adapter 之后再加, 现在不加

## 4. 测试 (上线前必跑)
```bash
curl https://api-qlinghl.alwaysdata.net/api/health            # {"ok":true}
curl -X POST .../api/register -d '{"username":"t1","password":"123456"}'
curl -X POST .../api/login    -d '{"username":"t1","password":"123456"}'  # 拿 token
curl -X POST .../api/orders -H "Authorization: Bearer <token>" \
     -d '{"product_sku":"chatgpt-plus","contact":"微信:xxx"}'
curl .../api/orders -H "Authorization: Bearer <token>"        # 查到订单
```

## 5. 前端对接 (部署后做)
- 下单按钮: 改为 POST 到 `https://api-qlinghl.alwaysdata.net/api/orders`,
  带上 `product_sku` + `contact`(购买流程要加的"联系方式"字段, 规格已在 pending 里),
  登录态存 localStorage 的 JWT, 请求头加 `Authorization: Bearer <token>`
- 登录/注册弹框: 调 `/api/register`、`/api/login`

## 6. 安全现状 (对应他"怕被同行攻击")
- 注册/登录: 每 IP 每分钟 10 次, 爆破会被 429 挡掉
- 下单: 每 IP 每分钟 30 次
- 登录错误回统一文案, 不泄露用户名是否存在
- 密码 bcrypt, JWT 密钥只在服务器环境变量
- 真被打: AlwaysData 免费版没有 DDoS 盾; 但他这点流量, 上面这几层够用了。
  前端若搬到 Cloudflare Pages, 页面层另有免费 WAF (迁移手册已有)。

## 7. 回滚
删掉这个 Python 站点即可; 静态站 (#1083267) 完全不受影响。

## 未验证项
- 面板 Python 站点类型的确切标签名 (按面板实际来, 大差不差)
- ji8 发货逻辑: 等文档, 见 `ji8_adapter.py`
- 收款方式: 未定 — 订单先以 `pending` 落库, 付款钩子后加
