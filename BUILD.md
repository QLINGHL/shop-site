# 构建说明

- 干净源码：`shop-deploy/*.html`（直接改这里）
- 受保护版本：`shop-deploy/dist/*.html`（线上跑的）
- 构建：`cd ~/workspace/shop-deploy/tools && python3 build.py`
  - 注入保护脚本（域名锁定+防右键/快捷键+反调试+防嵌套）
  - JS 混淆（javascript-obfuscator 高强度）
  - HTML/CSS 压缩
- 部署：`scp -i ~/.ssh/id_ed25519 shop-deploy/dist/*.html shop-deploy/dist/robots.txt qlinghl@ssh-qlinghl.alwaysdata.net:~/www/shop/`（robots.txt 需手动随同部署，不在构建脚本内）
- 域名白名单在 `tools/protect.js` 的 ALLOW 里，换域名时记得加
