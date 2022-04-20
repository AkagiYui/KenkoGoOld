## 功能介绍

这是一个 `go-cqhttp守护程序` 

用来管理一个go-cqhttp进程

监听并转发事件

提供 `掉线重连` `风控提示` 等功能

并且只要给你的程序在api请求接口前添加`/api`，
即可完成对接。

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

### 使用方法

使用前建议先修改配置文件`config.yml`

```bash
cd ./server
python3 -m pip install -r requirements.txt
cd ./src
cp config.yml.bak config.yml
python3 ./main.py
```

## Client

编写环境 Python `3.9.10`

需要的包

`colorlog`
`ruamel.yaml`
`requests`
`websocket-client`

---

### 使用方法

使用前建议先修改配置文件`config.yml`

```bash
cd ./client
python3 -m pip install -r requirements.txt
cd ./src
python3 ./main.py
```