# import requests
# import json
#
# # FastAPI 服务的 URL
# url = "http://127.0.0.1:9453/chat"
#
# # 要发送的消息内容
# data = {
#     "message": "你好，最近怎么样？"
# }
#
# # 发送 POST 请求
# response = requests.post(url, json=data)
#
# # 检查请求是否成功，并打印响应内容
# if response.status_code == 200:
#     print("来自服务器的响应：", response.json())
# else:
#     print(f"错误：{response.status_code}")

from elasticsearch_dsl import connections
from elasticsearch import Elasticsearch

# 连接到 Elasticsearch 实例并进行身份验证
connections.create_connection(
    alias='default',  # 连接的别名
    hosts=['http://10.3.244.173:9201'],  # Elasticsearch 的地址
    http_auth=('elastic', 'ctc123456'),  # 用户名和密码
    timeout=20  # 超时时间（秒）
)

# 使用底层的 Elasticsearch 客户端获取索引列表
es = Elasticsearch(hosts=['http://10.3.244.173:9201'], http_auth=('elastic', 'ctc123456'))

# 获取所有索引
indices = es.cat.indices(format="json")  # 使用 JSON 格式返回索引信息

# 输出索引列表
if indices:
    print("索引列表:")
    for index in indices:
        print(index['index'])
else:
    print("未找到索引！")




