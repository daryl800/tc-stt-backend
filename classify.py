from tencentcloud.common import credential
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.hunyuan.v20230901 import hunyuan_client, models
from config.constants import TENCENT_SECRET_ID, TENCENT_SECRET_KEY


def get_hunyuan_client():
    cred = credential.Credential(TENCENT_SECRET_ID, TENCENT_SECRET_KEY)
    http_profile = HttpProfile(endpoint="hunyuan.ap-hongkong.tencentcloudapi.com")
    client_profile = ClientProfile(httpProfile=http_profile)
    return hunyuan_client.HunyuanClient(cred, "ap-guangzhou", client_profile)

def classify_text(content):
    req = models.ChatCompletionsRequest()
    req.Messages = [
        {
            "Role": "system",
            "Content": "Classify the following memory into one of these categories: [General, Family, Health, Shopping, Reminder]. Return only the category name."
            "if the memory contains '提醒' or '记得' or '记得提醒' , classify it as 'Reminder'."
        },
        {
            "Role": "user",
            "Content": f"Memory: {content}"
        }
    ]
    req.Model = "hunyuan-standard"
    req.Temperature = 0.7

    try:
        client = get_hunyuan_client()
        resp = client.ChatCompletions(req)
        print(resp.to_json_string())
        return resp.Choices[0].Message.Content
    except Exception as e:
        raise e
