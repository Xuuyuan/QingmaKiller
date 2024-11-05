# QingmaKiller 青马易战自动答题工具
## 功能支持
 * 从站点URL直接获取Cookie
 * 答题次数设定、答题正确率控制
 * 跳过防刷题题目、随机延迟
 * 题库缺失的题目对接网络题库进行搜题
## 使用方法
### 1. **拉取本仓库至本地**
    在仓库主页面中单击 Code 按钮，根据需求选择 Clone 或 Download ZIP 。
### 2. **运行 tikuAdapter**
    仓库中已经内置了 tikuAdapter_0.1.0-beta.26 的可执行文件，适用于Windows_amd64，可以直接打开。 
    若需要应用于其它系统，请前往 [tikuAdapter Releases](https://github.com/DokiDoki1103/tikuAdapter/releases) 下载。
### 3. **配置本地Python环境**
    请使用Python 3.8+环境运行。
    工具所需的软件包已在requirements.txt中注明，或可在终端中执行以下指令：
    
    pip install openpyxl
    pip install pycryptodome
    pip install requests
### 4. **运行程序**
    运行 main.py ，按照提示输入参数即可。
    URL获取方法：
        1. 进入青马易战主界面（有大视频播放的页面）
        2. 点击右上角交互按钮，复制链接(URL)
## 注意事项
* 目前青马易战站点所使用的域名为112.5.88.114:31101，若今后发生变更，请自行修改程序中对应部分。
* decrypt函数中固定了base64解密所使用的密钥，此固定密钥由青马易战网页的js中获取，在未来有被修改的可能性。若密钥发生变更，可自行打断点抓包获取并修改程序中对应部分。
* 本地已提供了科目9、10、12、173的部分题库。可以自行补充，亦可在答题工具运行过程中由工具自动完成填充。  
