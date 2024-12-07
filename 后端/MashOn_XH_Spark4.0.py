# -*- coding: utf-8 -*-
from fastapi import FastAPI, Request
import openai
from pydantic import BaseModel
from typing import List
import logging
# 设置日志记录
logging.basicConfig(level=logging.DEBUG)
class Attachment(BaseModel):
    id: str
    type: str
class ChatMessage(BaseModel):
    """通原课堂返回响应的数据格式"""
    chat_id: int
    content: str
    attachments: List[Attachment] = []

app = FastAPI()

# 初始化OpenAI客户端
client = openai.OpenAI(
    api_key="ak-pAaatlJfalEXlHUrxBVZUDoIxfkCsB",
    base_url='https://trufar.bupt.edu.cn/api/open/llm/ezcodingspark/v1'
)


@app.post("/chat")
async def chat(request: Request):
    # 获取用户发送的数据
    user_message = await request.json()

    # 检查是否包含必要的'message'字段
    if 'message' not in user_message:
        return {"error": "Message content is required."}

    # 创建对话完成请求
    prompt = user_message['message']
    completion = client.chat.completions.create(
        model='spark-4.0',
        messages=[{"role": "user", "content": prompt}],
        stream=True,
    )

    # 累积完整响应内容
    full_response = ""
    for message in completion:
        # 只有当存在增量内容时才添加
        if message.choices and message.choices[0].delta and message.choices[0].delta.content:
            full_response += message.choices[0].delta.content

    logging.debug(full_response)
    # 返回完整响应
    response_data = ChatMessage(
        chat_id=0,  # 替换为实际的对话 ID
        content=full_response,
        attachments=[]
    )
    return response_data


# 运行服务
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=9453)
