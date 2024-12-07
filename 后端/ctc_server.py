import base64
import io
import os
import tempfile
from PIL import Image  # 使用PIL库处理图像
from elasticsearch_dsl import connections, Search, Q  # 用于连接和查询 Elasticsearch
import json
from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Header  # FastAPI 库
import uvicorn
from pydantic import BaseModel
from typing import List
import httpx
import requests

# 定义附件数据模型
class Attachment(BaseModel):
    id: str
    type: str

class BotChat(BaseModel):
    role: str
    content: str
    attachments: List[Attachment] = []  # 默认值为空列表

class ChatRequest(BaseModel):
    openid: str
    chat_id: int
    message: List[BotChat]

class ChatMessage(BaseModel):
    chat_id: int
    content: str
    attachments: List[Attachment] = []  # 默认值为空列表

# 连接 Elasticsearch
connections.create_connection(
    alias='default',  # 连接的别名
    hosts=['http://10.3.244.173:9201'],  # Elasticsearch 的地址
    http_auth=('elastic', 'ctc123456'),  # 用户名和密码
    timeout=20  # 超时时间（秒）
)
# 实例化 FastAPI 应用
app = FastAPI()
appId = "e143d737-d5d9-4805-89e8-dd93f2f58b79"  # botId
appSecret = "PrXKohjx7ZTLzyixOjqFpbEN5UofAoaI"  # 秘钥
api_key = "ak-pAaatlJfalEXlHUrxBVZUDoIxfkCsB"  # 您的 API Key

def restore_text_and_images(text_and_images):
    """解码并恢复文本和图像数据"""
    restored_content = text_and_images["paragraph_contents"]
    for docs in restored_content:
        for doc in docs["whole"]:
            if doc["type"] in ['image', 'img']:
                img_base64 = doc["content"]
                img_data = base64.b64decode(img_base64)
                doc["content"] = img_data  # 将解码后的数据赋值
    return restored_content

def query_to_ctcTopic(qs, bot_id):
    """根据查询字符串和 bot_id 查询相关题目"""
    img_attachments = []  # 存储图片附件

    search = Search(index="ctc2.5")  # 创建查询对象
    query = Q("match", pure_text=qs)  # 创建查询条件
    s = search.query(query)
    result = s.execute()  # 执行查询

    receive_content = {"paragraph_contents": []}
    for hit in result.hits:
        para_dict = {"pure_text": hit.pure_text, "whole": json.loads(hit.whole)}
        receive_content["paragraph_contents"].append(para_dict)

    restored_content = restore_text_and_images(receive_content)  # 恢复内容

    count = 0
    num = 2  # 限制返回的题目数量
    markdown_content = rf"根据您的提问，为您从通信原理题库中匹配到相关题目，如下：" + '\n\n'

    for docs in restored_content:
        if count < num:
            markdown_content += f'{count + 1}.'  # 标记题号
            for doc in docs["whole"]:
                if doc["type"] in ['text', 'latex']:
                    markdown_content += doc["content"]  # 添加文本或 LaTeX 内容
                elif doc["type"] == 'image':
                    markdown_content += '\n\n'  # 添加换行
                    image_stream = io.BytesIO(doc["content"])  # 转换为二进制流
                    image = Image.open(image_stream)  # 打开图像
                    temp_img_file = tempfile.NamedTemporaryFile(delete=False)  # 创建临时文件
                    image.save(temp_img_file, format='PNG', quality=95)  # 保存为 PNG 格式

                    # 1. 上传数据库，得到图片 ID（码上用的）
                    attachment_id = upload_file(bot_id=bot_id, file_path=temp_img_file.name)

                    # 1. 上传数据库，得到图片 ID（测试前端用的）
                    markdown_img_path= upload_file_test(bot_id=bot_id, file_path=temp_img_file.name)
                    markdown_content += f"![图片]({markdown_img_path})"

                    # 2. 将 ID 写入 Markdown 文件（码上用的）
                    # markdown_content += f" ezopen://{attachment_id} "
                    markdown_content += '\n\n'  # 添加换行
                    img_attachments.append(Attachment(id=attachment_id, type="img"))  # 保存附件

                    # 关闭并删除临时文件
                    temp_img_file.close()
                    os.unlink(temp_img_file.name)

                # markdown_content += '\n\n'  # 每个题目结束换行
                count += 1  # 题目计数

    if count==0:
        markdown_content="未能从通信原理题库中匹配到相关题目"+ '\n\n'

    return markdown_content, img_attachments

def upload_file(bot_id: str, file_path: str):
    """上传文件并返回文件 ID"""
    url = "https://trufar.bupt.edu.cn/api/open/file-hosting"

    headers = {
        "Authorization": f"Bearer {api_key}"
    }

    with open(file_path, 'rb') as file:
        files = {'file': file}
        response = httpx.post(url, headers=headers, files=files)

    if response.status_code == 200:
        response_data = response.json()
        return response_data.get("id")  # 假设返回的 JSON 中有一个 `id` 字段
    else:
        raise HTTPException(status_code=response.status_code, detail=response.text)

def upload_file_test(bot_id: str, file_path: str):
    """上传文件到测试的前端并返回文件 ID"""
    # url = "http://10.3.244.173:8082/upload_image" #127.0.0.1
    url = "http://127.0.0.1:8082/upload_image"

    with open(file_path, 'rb') as file:
        files = {'image_file': file}
        response = requests.post(url,  files=files)

    if response.status_code == 200:
        response_data = response.json()
        return response_data.get("store_path")  # 假设返回的 JSON 中有一个 `store_path` 字段,表示前端存图片的相对路径
    else:
        raise HTTPException(status_code=response.status_code, detail=response.text)

@app.post("/ctc_server")
async def communication_theory_Query(request: Request):
    """处理用户请求并返回相关题目"""
    try:
        request_data = await request.json()  # 获取 JSON 数据并转化为字典
        # chat_request = ChatRequest(**request_data)  # 验证并构造请求对象
        question = request_data["message"]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # last_message = chat_request.message[-1]  # 获取最后一条消息
    # question = ""  # 用户的提问
    empty_attachments = [Attachment(id="no_attachment", type="img")]  # 响应的占位附件

    # if len(last_message.attachments) == 0:
    #     question = last_message.content  # 提取用户问题
    #     print(question)

    # 根据用户提问获取相关题目
    topic_answer, topic_img_attachments = query_to_ctcTopic(qs=question, bot_id=appId)
    final_answer = topic_answer  # 拼接所有回答

    # 合并图像附件列表
    img_attachments = topic_img_attachments

    # 构造响应数据
    response_data = ChatMessage(
        chat_id=0,  # 替换为实际的对话 ID
        content=final_answer,
        attachments=img_attachments if len(img_attachments) != 0 else empty_attachments
    )
    return response_data  # 返回响应

if __name__ == '__main__':
    uvicorn.run(app, host="127.0.0.1", port=9451)  # 启动 FastAPI 应用
