"""全局常量: 站点信息、请求头、选项表、密钥与运行默认参数"""

# 站点域名(若站点发生变更, 只需修改此处)
base_host = 'sdyb.fjhdrs.com'
base_url = f'http://{base_host}'

user_agent = 'Mozilla/5.0 (Linux; Android 10; HLK-AL00 Build/HONORHLK-AL00; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/78.0.3904.108 Mobile Safari/537.36 yiban_android'

# 选项表
options_list = ['A', 'B', 'C', 'D', 'E', 'F', 'G']
options_dict = {'A': 0, 'B': 1, 'C': 2, 'D': 3, 'E': 4, 'F': 5, 'G': 6}

# tikuAdapter 本地搜题服务
tiku_adapter_url = 'http://localhost:8060/adapter-service/search'
headers_tiku = {"content-type": "application/json"}

# decrypt 使用的固定密钥(由青马易战网页的js中获取, 有被修改的可能性)
decrypt_key_b64 = "ZDBmMTNiZGI3MDRhMWVhMWE3MTcwNjJiNTk0NzY0ODg="

# 交互输入的默认参数
default_target_times = 550
default_target_right_rate = 0.6
default_max_right_rate = 0.9
