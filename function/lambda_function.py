import logging
import requests
import json
import os

logger = logging.getLogger()
logger.setLevel(logging.INFO)
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')

def send_feishu(webhook_url, content):
    data = {"msg_type": "text", "content": {"text": content}}
    response = requests.post(webhook_url, headers={"Content-Type": "application/json"}, json=data, timeout=10)
    result = response.json()
    return result.get("code") == 0, result

def send_dingtalk(webhook_url, content):
    data = {"msgtype": "text", "text": {"content": content.strip()}}
    response = requests.post(webhook_url, headers={"Content-Type": "application/json"}, json=data, timeout=10, verify=False)
    result = response.json()
    return result.get("errcode") == 0, result

def send_teams(webhook_url, content):
    data = {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": {
                "type": "AdaptiveCard",
                "version": "1.5",
                "body": [{"type": "TextBlock", "text": content, "size": "Medium", "wrap": True}]
            }
        }]
    }
    response = requests.post(webhook_url, headers={"Content-Type": "application/json"}, json=data, timeout=10)
    return response.status_code in [200, 202], {"code": response.status_code}

def send_wecom(webhook_url, content):
    data = {"msgtype": "markdown", "markdown": {"content": content}}
    response = requests.post(webhook_url, headers={"Content-Type": "application/json"}, json=data, timeout=10)
    result = response.json()
    return result.get("errcode") == 0, result

def send_slack(webhook_url, content):
    data = {"text": content}
    response = requests.post(webhook_url, headers={"Content-Type": "application/json"}, json=data, timeout=10)
    return response.status_code == 200 and response.text == "ok", {"code": response.status_code, "msg": response.text}

def send_notification(webhook_url, content):
    try:
        if 'feishu.cn' in webhook_url or 'lark' in webhook_url:
            success, result = send_feishu(webhook_url, content)
            platform = "飞书"
        elif 'dingtalk.com' in webhook_url:
            success, result = send_dingtalk(webhook_url, content)
            platform = "钉钉"
        elif 'powerplatform.com' in webhook_url or 'webhook.office.com' in webhook_url:
            success, result = send_teams(webhook_url, content)
            platform = "Teams"
        elif 'qyapi.weixin.qq.com' in webhook_url:
            success, result = send_wecom(webhook_url, content)
            platform = "企业微信"
        elif 'hooks.slack.com' in webhook_url:
            success, result = send_slack(webhook_url, content)
            platform = "Slack"
        else:
            return False, {"error": "无法识别的Webhook URL"}
        
        if success:
            logger.info(f"{platform}消息发送成功")
        else:
            logger.error(f"{platform}消息发送失败：{result}")
        return success, result
    except Exception as e:
        logger.error(f"发送消息时发生错误：{str(e)}")
        return False, {"error": str(e)}

def lambda_handler(event, context):
    message_content = event if isinstance(event, str) else json.dumps(event, indent=2, ensure_ascii=False)
    
    if not WEBHOOK_URL:
        logger.error("未配置WEBHOOK_URL环境变量")
        return {'statusCode': 500, 'body': json.dumps({"error": "未配置WEBHOOK_URL"})}
    
    success, result = send_notification(WEBHOOK_URL, message_content)
    logger.info(f"消息发送响应：{result}")
    
    return {
        'statusCode': 200 if success else 500,
        'body': json.dumps({"message": "事件已处理", "send_result": result}, ensure_ascii=False)
    }
