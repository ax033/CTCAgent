import base64
from elasticsearch_dsl import connections, Text, Search, Q
import json
from fastapi import FastAPI, Request,HTTPException
import uvicorn
from pydantic import BaseModel
from typing import List
import httpx
import io
from PIL import Image
import tempfile
import os
import requests
class Attachment(BaseModel):
    id: str
    type: str

class BotChat(BaseModel):
    role: str
    content: str
    attachments: List[Attachment] = []

class ChatRequest(BaseModel):
    openid: str
    chat_id: int
    message: List[BotChat]

class ChatMessage(BaseModel):
    """通原课堂返回响应的数据格式"""
    chat_id: int
    content: str
    attachments: List[Attachment] = []

class Token(BaseModel):
    """access_token接口返回的数据结构"""
    access_token: str
    expire: int  # 多少秒后过期

token_pool={
    "ori_token":{
        # 普通的token和到期时间
        "access_token":None,
        "expires_at": 0.0
    },
    "model_token": {
        # 大模型的token（其实就是测试服务器的token）和到期时间
        "access_token": None,
        "expires_at": 0.0
    }
}

def restore_text_and_images(text_and_images):
    restored_content = text_and_images["paragraph_contents"]
    for docs in restored_content:
        for doc in docs["whole"]:
            if doc["type"] == 'text':
                pass
            elif doc["type"] == 'image' or doc["type"] == 'img':
                # 通原题库图片字段叫image ，学生老师问答图片字段叫img
                img_base64 = doc["content"]
                img_data = base64.b64decode(img_base64)
                doc["content"] = img_data
    return restored_content

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
    # url = "http://10.3.244.173:8082/get_image" #127.0.0.1
    url = "http://127.0.0.1:8082/upload_image"
    with open(file_path, 'rb') as file:
        files = {'image_file': file}
        response = requests.post(url,  files=files)

    if response.status_code == 200:
        response_data = response.json()
        return response_data.get("store_path")  # 假设返回的 JSON 中有一个 `store_path` 字段,表示前端存图片的相对路径
    else:
        raise HTTPException(status_code=response.status_code, detail=response.text)

def query_to_ctcDiscussion(qs,bot_id):
    img_attachments = [] #存储md中所有图片的attachments

    # ---------查询操作--------------
    # 1.Search
    # 创建一个查询对象
    search = Search(index="ctc_discussion1.5")

    # 添加一个match查询
    query = Q("match", question_pure_text=qs)  # 选择了下面的Q的查询方法，同理可以写mathc_phrase等
    s = search.query(query)
    # 执行查询
    result = s.execute()

    # 接收es的json信息用于显示
    receive_content = {
        "paragraph_contents": []
    }
    # 遍历查询结果
    for hit in result.hits:
        para_dict = {"whole": json.loads(hit.question_whole),
                     "answer":json.loads(hit.answer)}  # json转换成list
        receive_content["paragraph_contents"].append(para_dict)
    restored_content = restore_text_and_images(receive_content)

    """创建一个新的md文件并将内容写入其中"""
    count=0
    num=1 # 限制返回的对话数量
    # 创建一个字符串来存储Markdown格式的文本
    markdown_content = rf"根据您的提问，为您从通信原理课堂问答数据库中匹配到相关问答记录，如下："+'\n'+'\n'

    for docs in restored_content:
        if count<num:
            #每道题前面加一个标号
            markdown_content += f'{count+1}.'
            #学生的问题描述
            markdown_content += "学生提问："
            for doc in docs["whole"]:
                if doc["type"] == 'text':
                    markdown_content += doc["content"]
                elif doc["type"] == 'image' or doc["type"] == 'img':
                    # 通原题库图片字段叫image ，学生老师问答图片字段叫img
                    # 图像单独放一行
                    markdown_content+='\n'
                    markdown_content+='\n'

                    # 图片数据：1.上传码上侧的图片数据端口，获得图片的id 2.将图片id放入md字符串，eg：ezopen://{文件id}
                    # 将图片转换为二进制流
                    image_stream = io.BytesIO(doc["content"])

                    image = Image.open(image_stream)

                    # 保存图像对象到临时文件
                    temp_img_file = tempfile.NamedTemporaryFile(delete=False)
                    image.save(temp_img_file, format='PNG', quality=95)  # 保存为PNG格式

                    #1.上传数据库，得到图片id（码上用的）
                    attachment_id = upload_file(bot_id=bot_id,file_path=temp_img_file.name)
                    # 1. 上传数据库，得到图片 ID（测试前端用的）
                    markdown_img_path= upload_file_test(bot_id=bot_id, file_path=temp_img_file.name)
                    markdown_content += f"![图片]({markdown_img_path})"


                    #2.将id写入md文件（码上用的）
                    # markdown_content+=f" ezopen://{attachment_id} "

                     # 图像单独放一行
                    markdown_content+='\n'
                    markdown_content+='\n'

                    #3.将图片id和类型保存到img_attachments中
                    img_attachments.append(Attachment(id=attachment_id,type="img"))

                    # 关闭文件
                    temp_img_file.close()

                    # 删除临时文件
                    os.unlink(temp_img_file.name)

            #学生提问内容显示后，换行
            markdown_content += '\n'
            markdown_content += '\n'

            #老师的回答
            markdown_content += "教师回答："
            for doc in docs["answer"]:
                if doc["type"] == 'text':
                    markdown_content += doc["content"]
                elif doc["type"] == 'image':
                    # 图像单独放一行
                    markdown_content+='\n'
                    markdown_content+='\n'

                    # 图片数据：1.上传码上侧的图片数据端口，获得图片的id 2.将图片id放入md字符串，eg：ezopen://{文件id}
                    # 将图片转换为二进制流
                    image_stream = io.BytesIO(doc["content"])

                    image = Image.open(image_stream)

                    # 保存图像对象到临时文件
                    temp_img_file = tempfile.NamedTemporaryFile(delete=False)
                    image.save(temp_img_file, format='PNG', quality=95)  # 保存为PNG格式

                    #1.上传数据库，得到图片id（码上用的）
                    attachment_id = upload_file(bot_id=bot_id,file_path=temp_img_file.name)
                    # 1. 上传数据库，得到图片 ID（测试前端用的）
                    markdown_img_path= upload_file_test(bot_id=bot_id, file_path=temp_img_file.name)
                    markdown_content += f"![图片]({markdown_img_path})"


                    #2.将id写入md文件（码上用的）
                    # markdown_content+=f" ezopen://{attachment_id} "

                     # 图像单独放一行
                    markdown_content+='\n'
                    markdown_content+='\n'

                    #3.将图片id和类型保存到img_attachments中
                    img_attachments.append(Attachment(id=attachment_id,type="img"))

                    # 关闭文件
                    temp_img_file.close()

                    # 删除临时文件
                    os.unlink(temp_img_file.name)

            # #每个题目结束换行(再隔一行)
            # markdown_content+='\n'
            # markdown_content+='\n'
            count+=1 # 题目计数

    if count==0:
        markdown_content="未能从通信原理课堂问答数据库中匹配到相关题目"+ '\n\n'

    return markdown_content,img_attachments

"""连接elasticsearch"""
connections.create_connection(
    alias='default',  # 连接的别名
    hosts=['http://10.3.244.173:9201'],  # Elasticsearch 的地址
    http_auth=('elastic', 'ctc123456'),  # 用户名和密码
    timeout=20  # 超时时间（秒）
)
# 实例化总的路由对象
app = FastAPI()
XH_url = "https://101.42.12.233:10443/api"
base_url = "https://ezcoding.bupt.edu.cn:443/api"

# ctc的：
appId = "e143d737-d5d9-4805-89e8-dd93f2f58b79"  #appId也是botId
appSecret = "PrXKohjx7ZTLzyixOjqFpbEN5UofAoaI"
api_key = "ak-pAaatlJfalEXlHUrxBVZUDoIxfkCsB"  # 您的 API Key

@app.post("/discussion")
async def communication_theory_Query(request: Request):
    # 读取请求体中的 JSON 数据
    try:
        request_data = await request.json()  # 获取 JSON 数据并转化为字典
        # chat_request = ChatRequest(**request_data)  # 使用解包操作将字典传递给 ChatRequest 构造函数
        question = request_data["message"]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # # 获取当前轮的对话消息，也就是message列表的最后一个字典的内容
    # last_message = chat_request.message[-1]

    # question="" # 用户的提问
    empty_attachments = [Attachment(id="no_attachment", type="img")] #响应的attachments列表，主要是md文件图片的id值,这个是拿来占位的

    print(question)

    # 根据用户提问获取es中的匹配问答记录
    discussion_answer, discussion_img_attachments = query_to_ctcDiscussion(qs=question, bot_id=appId)

    # 拼接所有的回答
    final_answer = discussion_answer

    # 合并通原题目和问题记录数据库中的img_attachments的列表
    img_attachments =  discussion_img_attachments

    # 构造响应数据
    response_data = ChatMessage(
        chat_id=0,  # 替换为实际的对话 ID
        content=final_answer,
        attachments= img_attachments if len(img_attachments) != 0 else empty_attachments
    )
    return response_data

if __name__ == '__main__':
    uvicorn.run(app, host="127.0.0.1", port=9452)  # 第一个参数要写这个python脚本的名字，reload就是是否自动刷新
