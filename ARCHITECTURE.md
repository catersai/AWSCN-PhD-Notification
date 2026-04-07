# AWS中国区Personal Health Dashboard集中IM通知方案 - 架构图

## 架构概览

```mermaid
graph TB
    subgraph Spoke1["推送账号 1 (Spoke)"]
        PHD1["AWS Health"]
        EB1["EventBridge Default Bus"]
        Rule1["EventBridge Rule: PhDPush"]
        PHD1 -->|Health Events| EB1
        EB1 -->|匹配规则| Rule1
    end

    subgraph Spoke2["推送账号 2 (Spoke)"]
        PHD2["AWS Health"]
        EB2["EventBridge Default Bus"]
        Rule2["EventBridge Rule: PhDPush"]
        PHD2 -->|Health Events| EB2
        EB2 -->|匹配规则| Rule2
    end

    subgraph SpokeN["推送账号 N (Spoke)"]
        PHD3["AWS Health"]
        EB3["EventBridge Default Bus"]
        Rule3["EventBridge Rule: PhDPush"]
        PHD3 -->|Health Events| EB3
        EB3 -->|匹配规则| Rule3
    end

    subgraph Hub["集中通知账号 (Hub)"]
        CEB["EventBridge Custom Bus: PhDEventBus"]
        CRule["EventBridge Rule + InputTransformer"]
        Lambda["Lambda: PhDNotifyLambda"]
        Layer["Lambda Layer: requests-python314"]

        CEB -->|匹配规则| CRule
        CRule -->|触发| Lambda
        Layer -.->|依赖| Lambda
    end

    subgraph IM["通讯平台"]
        Feishu["飞书"]
        DingTalk["钉钉"]
        Teams["Teams"]
        WeCom["企业微信"]
        Slack["Slack"]
    end

    Rule1 -->|跨账号转发| CEB
    Rule2 -->|跨账号转发| CEB
    Rule3 -->|跨账号转发| CEB

    Lambda -->|Webhook| Feishu
    Lambda -->|Webhook| DingTalk
    Lambda -->|Webhook| Teams
    Lambda -->|Webhook| WeCom
    Lambda -->|Webhook| Slack

    style PHD1 fill:#FF9900,color:#fff
    style PHD2 fill:#FF9900,color:#fff
    style PHD3 fill:#FF9900,color:#fff
    style CEB fill:#FF6B6B,color:#fff
    style Lambda fill:#4CAF50,color:#fff
    style Layer fill:#2196F3,color:#fff
    style Feishu fill:#00D6B9,color:#fff
    style DingTalk fill:#0089FF,color:#fff
    style Teams fill:#5B5FC7,color:#fff
    style WeCom fill:#07C160,color:#fff
    style Slack fill:#4A154B,color:#fff
```

## 事件流程

```mermaid
sequenceDiagram
    participant PHD as AWS Health Dashboard
    participant Spoke as 推送账号 EventBridge
    participant Hub as 集中账号 EventBridge
    participant Lambda as Lambda Function
    participant IM as 即时通讯平台

    PHD->>Spoke: 1. 产生Health事件
    Spoke->>Spoke: 2. 规则匹配 (aws.health)
    Spoke->>Hub: 3. 跨账号转发事件
    Hub->>Hub: 4. 规则匹配 + InputTransformer格式化
    Hub->>Lambda: 5. 触发Lambda（已格式化的消息）
    Lambda->>Lambda: 6. 识别Webhook URL
    Lambda->>Lambda: 7. 构造平台特定格式
    Lambda->>IM: 8. 发送通知
    IM-->>Lambda: 9. 返回结果
    Lambda-->>Hub: 10. 返回执行状态
```

## 组件说明

### 推送账号 (Spoke)
- **AWS Health Dashboard**: 产生PHD事件
- **EventBridge Default Bus**: 接收AWS服务事件
- **EventBridge Rule**: 匹配Health事件并转发到集中账号

### 集中通知账号 (Hub)
- **EventBridge Custom Bus**: 接收来自多个推送账号的事件
- **EventBridge Rule**: 匹配事件，通过InputTransformer格式化消息后触发Lambda
- **Lambda Function**: 接收格式化消息并发送通知
- **Lambda Layer**: 提供requests库依赖

### 通讯平台
支持5个主流即时通讯平台，通过Webhook URL自动识别目标平台

## 关键特性

1. **Hub-Spoke架构**: 集中管理，便于维护
2. **自动识别**: 根据Webhook URL自动识别通讯平台
3. **跨账号支持**: 支持同账号、跨账号、跨组织部署
4. **低成本**: 基本在AWS免费额度内
5. **高可用**: 无服务器架构，自动扩展
