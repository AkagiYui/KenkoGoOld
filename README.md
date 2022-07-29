# ! 停止维护 !

该项目已停止维护，请查看新项目 [**KenkoGoServer**](https://github.com/AkagiYui/KenkoGoServer)

## 功能介绍

这是一个 `go-cqhttp守护程序` 

用来管理一个go-cqhttp进程

监听并转发事件

提供 `掉线重连` `风控提示` 等功能

并且只要给你的程序在api请求接口前添加`/api`，
即可完成对接。

！注意！现在并未发布正式版，项目内容尚未完善，包括但不限于最常用的各种API

---

## 使用方法

请确保你的机器有`Python 3.9`以上的环境，其他版本未经测试。

首次打开建议先部署`Client`以更方便得获取登录二维码。

1. 安装运行环境

```bash
cd ./client
python -m pip install -r requirements.txt
```

2. 修改配置文件并运行

> 配置项说明
> 
> server.host: Server 地址
> 
> server.port: Server 端口
> 
> server.token: Server 密钥
> 
> 与后面将要配置的Server的配置文件一一对应（除了host）

```bash
cd ./src
cp config.yml.bak config.yml
vim config.yml
python ./main.py --debug
```

如果正常将可看到控制台一直输出`服务器连接失败`的字样

---

接下来部署`Server`

你可以选择另一台服务器或就在本地部署`Server`，通常来说`Server`不会一直关闭或重启，我们在`Client`端处理所有事务即可。

1. 安装运行环境

```bash
cd ./server
python -m pip install -r requirements.txt
```

2. 修改配置文件并运行

> 配置项说明
> 
> account.uin: 登录QQ号
> 
> gocq.version: 未找到go-cqhttp时下载的版本
> 
> port.http: 与 Client 端和 go-cqhttp 通信的端口，在未做端口转发的情况下，应与前文 `server.port` 保持一致
> 
> port.auto_change: 当上述端口被占用时，是否自动更换端口
> 
> host: 服务器监听地址，`0.0.0.0`表示监听所有地址
> 
> token: `Client` 与 `Server` 通信的密钥，应与前文 `server.token` 保持一致

```bash
cd ./src
cp config.yml.bak config.yml
vim config.yml
python ./main.py --debug --auto-start
```

> 命令行参数说明
> 
> --debug: 开启调试模式，将会输出更多信息
> 
> --auto-start: 启动时自动启动 `go-cqhttp`, 否则将在请求 `/start` 时启动

首次启动时会自动下载`go-cqhttp`，若你的服务器无法正常连接至Github，请手动将正确版本的`go-cqhttp可执行文件`下载到`server/src/gocq`目录下，并命名为`go-cqhttp`

如果正常将可以在双端看到连接成功的字样，并且 `Client` 会收到所有状态改变的提示

若前面没有使用`--auto-start`，在这里可以给 `http://服务器地址:端口/start` 发送POST请求，记得在Header带上token

当 `go-cqhttp` 状态到达等待扫描二维码时，双端都会提示，并且在 `Client` 端会提示二维码URL，在浏览器打开即可扫描，
或者直接访问 `http://服务器地址:端口/qrcode`。

使用手机QQ扫描此二维码即可登录 `go-cqhttp`

---

## Server

编写环境 Python `3.9.10`

需要的包

`distro`
`requests`
`ruamel.yaml`
`colorlog`
`fastapi`
`uvicorn[standard]`

---

## Client

编写环境 Python `3.9.10`

需要的包

`colorlog`
`ruamel.yaml`
`requests`
`websocket-client`

---
