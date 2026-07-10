# 邮箱登录与邀请关系

## 目标

学习者登录采用“邮箱验证码 → 邮箱查询 → 选择学习者”的流程。同一邮箱可以绑定多个学习者，每个学习者保留独立的学习记录、画像、记忆和邀请码。新学习者必须使用有效邀请码注册，系统同时保存直接邀请人，便于后续确认家庭、同伴或团队关系。

## 用户流程

1. 用户输入必填邮箱，前端调用 `POST /api/email-verifications` 发送 6 位验证码。
2. 用户调用 `POST /api/email-verifications/confirm` 确认验证码，获得与该邮箱绑定的短期验证令牌。
3. 前端携带验证令牌调用 `POST /api/learners/lookup`；令牌邮箱不匹配、过期或被篡改都会返回 401。
4. 若邮箱已有学习者，系统返回最小账号摘要，用户选择后调用 `POST /api/learners/login`。
5. 若要新增学习者，用户输入昵称和邀请码，调用 `POST /api/learners`。
6. 注册成功后，新学习者获得唯一、可重复分享的邀请码，并记录 `invited_by_learner_id`。
7. 迁移前没有邮箱的旧学习者，在恢复本地会话后也必须先验证邮箱，再通过 `PUT /api/learners/{learner_id}/email` 绑定。

登录和注册已分离：登录不会因为邮箱或昵称不存在而静默创建学习者。

## 验证安全约束

- 验证码为 6 位数字，默认 10 分钟有效，同一邮箱默认 60 秒后才能重发。
- 每个挑战最多尝试 5 次；错误次数持久化，不能通过重启进程清零。
- 数据库只保存带随机盐的 HMAC-SHA256 验证码摘要，不保存验证码明文。
- 验证成功签发默认 10 分钟有效的 HMAC 签名令牌，令牌绑定规范化邮箱并包含随机 nonce。
- 账号查询、登录、注册和旧账号绑定邮箱都强制校验令牌，因此不能只凭知道邮箱地址枚举或进入账号。

## 数据约束

- `learners.email` 统一为去首尾空格的小写形式，可重复，并建立普通索引。
- `learners.invite_code` 必填且唯一，格式为 `BINN-` 加 10 位易读随机字符。
- `learners.invited_by_learner_id` 是指向 `learners.id` 的可空自引用外键；邀请人删除后置空，不删除被邀请人。
- 邀请码可重复邀请多个新学习者；关系只在注册时写入，当前不提供用户端改绑。

## 首个学习者

空数据库没有可用邀请人，因此首次注册使用环境变量：

```env
BINN_BOOTSTRAP_INVITE_CODE=replace-with-a-private-code
```

bootstrap 邀请码只在学习者数量为 0 时有效。首个学习者创建后，所有注册都必须使用某个学习者自己的邀请码。

integration/e2e 学习者模拟需要创建临时学习者时，使用 `--invite-code` 或 `BINN_SIMULATION_INVITE_CODE` 提供一个现有学习者的邀请码；contract mode 使用本地 mock，不需要真实邀请码。

## API 摘要

| 方法 | 路径 | 用途 |
|---|---|---|
| `POST` | `/api/email-verifications` | 发送验证码，执行重发冷却 |
| `POST` | `/api/email-verifications/confirm` | 校验验证码并签发短期邮箱验证令牌 |
| `POST` | `/api/learners/lookup` | 按规范化邮箱列出可选学习者摘要 |
| `POST` | `/api/learners/login` | 校验邮箱与所选 `learner_id` 的绑定并登录 |
| `POST` | `/api/learners` | 使用邮箱、昵称和邀请码注册 |
| `PUT` | `/api/learners/{learner_id}/email` | 为迁移前的无邮箱学习者绑定邮箱 |
| `GET` | `/api/learners/{learner_id}` | 恢复当前本地学习者会话和邀请码 |

## 邮件投递配置

本地开发默认使用 `BINN_EMAIL_DELIVERY_MODE=console`，验证码只写入后端日志。公开部署必须改为 `smtp`，设置独立随机签名密钥和 SMTP 参数：

```env
BINN_EMAIL_DELIVERY_MODE=smtp
BINN_EMAIL_VERIFICATION_SECRET=replace-with-a-long-random-secret
BINN_SMTP_HOST=smtp.example.com
BINN_SMTP_PORT=587
BINN_SMTP_USERNAME=your-user
BINN_SMTP_PASSWORD=your-password
BINN_SMTP_FROM_ADDRESS=no-reply@example.com
BINN_SMTP_STARTTLS=true
BINN_SMTP_USE_SSL=false
```

邮箱验证证明了当前操作者能接收该邮箱的邮件，但当前本地 MVP 仍使用浏览器学习者缓存，不是完整生产 session。远程多用户部署仍需继续把所有 learner-scoped API 收口到统一认证 session，并在网关层增加 IP / 邮箱组合限流、验证码发送审计和异常告警。
