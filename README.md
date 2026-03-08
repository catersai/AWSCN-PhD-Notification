# AWS中国区Personal Health Dashboard集中通知方案

## 项目概述

本项目实现AWS中国区多账号Personal Health Dashboard (PHD)事件的集中通知方案，支持将多个AWS账号的健康事件统一推送到飞书、钉钉、Teams、企业微信、Slack等即时通讯平台。

## 设计思路

### 架构模式
采用**Hub-Spoke模式**（中心辐射模式）：
- **集中通知账号（Hub）**：部署EventBridge自定义事件总线和Lambda通知函数
- **推送账号（Spoke）**：部署EventBridge规则，将PHD事件转发到集中账号

### 核心优势
1. **集中管理**：所有通知配置集中在一个账号，便于维护
2. **灵活扩展**：新增账号只需部署推送规则，无需修改通知逻辑
3. **多平台支持**：通过Webhook URL自动识别目标平台，无需额外配置
4. **跨账号支持**：支持同账号、跨账号、跨组织的事件转发

## 支持的通讯平台

| 平台 | URL特征 | 数据格式 |
|------|---------|----------|
| 飞书 | `feishu.cn` / `lark` | `{"msg_type": "text", "content": {"text": "..."}}` |
| 钉钉 | `dingtalk.com` | `{"msgtype": "text", "text": {"content": "..."}}` |
| Teams | `powerplatform.com` / `webhook.office.com` | Adaptive Card格式 |
| 企业微信 | `qyapi.weixin.qq.com` | `{"msgtype": "markdown", "markdown": {"content": "..."}}` |
| Slack | `hooks.slack.com` | `{"text": "..."}` |

## 文件说明

```
PhD/
├── CNPhDCentral.yaml          # 集中通知账号的CloudFormation模板
├── CNPhDPush.yaml             # 推送账号的CloudFormation模板
├── function/
│   ├── lambda_function.py     # Lambda通知函数代码
│   └── requests-layer-python314.zip  # Python requests库的Lambda Layer包
└── README.md                  # 本文档
```

## 部署步骤

### 前置准备

1. **获取Webhook地址**
   - 在目标通讯平台创建机器人/Webhook
   - 记录Webhook URL

2. **创建Lambda Layer包**（本地操作）

```bash
# 创建工作目录
mkdir -p python-layer/python
cd python-layer

# 安装requests库（Python 3.14）
pip install requests -t python/

# 打包Layer
zip -r requests-layer-python314.zip python/

# 验证包结构
unzip -l requests-layer-python314.zip
# 应该看到: python/requests/...
```

### 一、部署集中通知账号

#### 1. 上传Lambda Layer

```bash
aws lambda publish-layer-version \
  --layer-name requests-python314 \
  --description "Python 3.14 requests library" \
  --zip-file fileb://requests-layer-python314.zip \
  --compatible-runtimes python3.14 \
  --region cn-northwest-1
```

记录返回的Layer ARN，格式如：
```
arn:aws-cn:lambda:cn-northwest-1:123456789012:layer:requests-python314:1
```

#### 2. 部署CloudFormation栈

```bash
aws cloudformation create-stack \
  --stack-name PhDCentral \
  --template-body file://CNPhDCentral.yaml \
  --parameters \
    ParameterKey=WebhookUrl,ParameterValue=<你的Webhook地址> \
    ParameterKey=RequestsLayerArn,ParameterValue=<Layer的ARN> \
    ParameterKey=AllowedAccountIds,ParameterValue=<允许的账号ID列表,逗号分隔> \
  --capabilities CAPABILITY_IAM \
  --region cn-northwest-1
```

**参数说明：**
- `WebhookUrl`：通讯平台的Webhook地址（必填）
- `RequestsLayerArn`：上一步创建的Layer ARN（必填）
- `AllowedAccountIds`：允许推送事件的AWS账号ID列表，逗号分隔（可选）
- `AllowedOrganizationIds`：允许推送事件的AWS组织ID列表，逗号分隔（可选）

#### 3. 获取EventBus ARN

```bash
aws cloudformation describe-stacks \
  --stack-name PhDCentral \
  --query 'Stacks[0].Outputs[?OutputKey==`PhDEventBusArn`].OutputValue' \
  --output text \
  --region cn-northwest-1
```

记录输出的EventBus ARN，用于推送账号配置。

### 二、部署推送账号

在每个需要监控PHD事件的AWS账号中执行：

```bash
aws cloudformation create-stack \
  --stack-name PhDPush \
  --template-body file://CNPhDPush.yaml \
  --parameters \
    ParameterKey=PhDEventBusArn,ParameterValue=<集中账号的EventBus ARN> \
  --capabilities CAPABILITY_IAM \
  --region cn-northwest-1
```

**注意：** 如果推送账号与集中账号不同，需确保集中账号的EventBus策略允许该账号推送事件。

### 三、测试验证

#### 1. 发送测试事件

在推送账号执行：

```bash
aws events put-events \
  --entries '[
    {
      "Source": "self.test.aws.health",
      "DetailType": "AWS Health Event",
      "Detail": "{\"eventTypeCode\":\"TEST_EVENT\",\"service\":\"EC2\",\"region\":\"cn-northwest-1\",\"startTime\":\"2026-03-08T00:00:00Z\",\"eventDescription\":[{\"latestDescription\":\"This is a test event\"}]}"
    }
  ]' \
  --region cn-northwest-1
```

#### 2. 验证通知

检查目标通讯平台是否收到测试消息。

#### 3. 查看Lambda日志

```bash
aws logs tail /aws/lambda/PhDNotifyLambda --follow --region cn-northwest-1
```

## 更新Webhook地址

```bash
aws lambda update-function-configuration \
  --function-name PhDNotifyLambda \
  --environment "Variables={WEBHOOK_URL=<新的Webhook地址>}" \
  --region cn-northwest-1
```

## 故障排查

### Lambda执行失败
- 检查Layer是否正确安装：`aws lambda get-function --function-name PhDNotifyLambda`
- 查看CloudWatch日志：`/aws/lambda/PhDNotifyLambda`

### 未收到通知
- 验证EventBus策略是否允许推送账号
- 检查EventBridge规则是否启用
- 确认Webhook URL正确且未过期

### 通讯平台返回错误
- 飞书：检查`code`字段，0为成功
- 钉钉：检查`errcode`字段，0为成功
- Teams：HTTP 200或202为成功
- 企业微信：检查`errcode`字段，0为成功
- Slack：HTTP 200且响应体为"ok"为成功

## 成本估算（宁夏区定价）

### 免费额度
- **EventBridge**：AWS管理事件（包括PHD事件）摄取和同账号投递免费
- **Lambda**：每月100万次请求免费，40万GB-秒计算时间免费
- **CloudWatch Logs**：每月5GB日志摄取免费

### 付费定价
- **EventBridge跨账号投递**：¥6.75/百万次事件（AWS管理事件）
- **Lambda请求**：¥1.36/百万次请求（超出免费额度后）
- **Lambda计算**：¥0.000113477/GB-秒（超出免费额度后）

### 典型场景成本
**场景1：单账号部署（每月10次PHD事件）**
- EventBridge：免费（同账号投递）
- Lambda：免费（在免费额度内）
- **总成本：¥0/月**

**场景2：5个推送账号（每月50次PHD事件）**
- EventBridge跨账号投递：50次 × ¥6.75/百万 ≈ ¥0.0003
- Lambda：免费（在免费额度内）
- **总成本：约¥0/月（可忽略不计）**

**场景3：100个推送账号（每月1000次PHD事件）**
- EventBridge跨账号投递：1000次 × ¥6.75/百万 ≈ ¥0.007
- Lambda：免费（在免费额度内）
- **总成本：约¥0.01/月**

## 安全建议

1. **Webhook保密**：使用NoEcho参数保护Webhook URL
2. **最小权限**：EventBus策略仅允许必要的账号
3. **日志审计**：定期检查CloudWatch日志
4. **定期轮换**：定期更新Webhook地址

## 扩展功能

### 支持多个Webhook
修改Lambda代码，从环境变量读取多个Webhook并并发发送：
```python
WEBHOOK_URLS = os.environ.get('WEBHOOK_URLS', '').split(',')
```

### 自定义消息格式
修改`lambda_function.py`中的`message_content`变量，自定义消息模板。

### 添加过滤规则
在`CNPhDPush.yaml`的`EventPattern`中添加过滤条件，例如仅监控特定服务：
```yaml
EventPattern:
  source:
    - aws.health
  detail:
    service:
      - EC2
      - RDS
```

## 许可证

MIT License

## 联系方式

如有问题或建议，请提交Issue。
