"""全局常量: 站点信息、请求头、选项表、密钥与运行默认参数"""

# 站点域名(若站点发生变更, 只需修改此处)
base_host = 'sdyb.fjhdrs.com'
base_url = f'http://{base_host}'

# 易班OAuth授权页域名(未认证会话会被302到该页, 用于会话失效检测)
oauth_host = 'https://oauth.yiban.cn'

user_agent = 'Mozilla/5.0 (Linux; Android 10; HLK-AL00 Build/HONORHLK-AL00; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/78.0.3904.108 Mobile Safari/537.36 yiban_android'

# 选项表
options_list = ['A', 'B', 'C', 'D', 'E', 'F', 'G']

# 内置网络题库(搜题逻辑移植自 tikuAdapter, 各源启用与否及付费token配置见程序同目录的 banks.json)
banks_config_filename = 'banks.json'
buguake_api = 'https://easylearn.baidu.com/edu-web-go/bgk/searchlist'
icodef_api = 'https://cx.icodef.com/wyn-nb?v=4'
wanneng_free_api = 'http://lyck6.cn/scriptService/api/autoFreeAnswer'
wanneng_api = 'http://lyck6.cn/scriptService/api/autoAnswer/{}'
tikuhai_api = 'https://api.tikuhai.com/search'
enncy_api = 'https://tk.enncy.cn/query'
aidian_free_api = 'http://new.api.51aidian.com/publics/newapi/freedirect'
aidian_api = 'http://new.api.51aidian.com/publics/newapi/direct'
lemon_api = 'https://api.lemtk.xyz/api/v1/mcx'

# decrypt 使用的固定密钥(由青马易战网页的js中获取, 有被修改的可能性)
decrypt_key_b64 = "ZDBmMTNiZGI3MDRhMWVhMWE3MTcwNjJiNTk0NzY0ODg="

# 交互输入的默认参数
default_target_times = 550
default_target_right_rate = 0.6
default_max_right_rate = 0.9
