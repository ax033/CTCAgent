# 导入SDK，发起请求
from openai import OpenAI

client = OpenAI(
    api_key="ak-pAaatlJfalEXlHUrxBVZUDoIxfkCsB", #这个apikey得自己向码上那边申请
    base_url = 'https://trufar.bupt.edu.cn/api/open/llm/ezcodingspark/v1'
)
completion = client.chat.completions.create(
    model='spark-4.0',
    messages=[
        {
            "role": "user",
            "content": "解释通信领域里的包络"
        }
    ],
    stream=True
)

for message in completion:
    print(message.choices[0].delta.content, end="", flush=True)

print()